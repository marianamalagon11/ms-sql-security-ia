"""
Motor de reglas de la fase proactiva: matriz de sensibilidad/criticidad,
evaluación de impacto y evaluación de escalamiento (bloque A de la
arquitectura).

El nivel de riesgo se calcula aquí de forma determinista y auditable:

    1. Cada sentencia se ubica en una categoría de operación (LECTURA,
       ESCRITURA, ELIMINACION, DDL, PRIVILEGIOS, EJECUCION, CONTROL).
    2. Se cruzan sus tablas/columnas contra el catálogo de objetos sensibles
       para obtener la sensibilidad máxima afectada y si el rol está autorizado.
    3. matriz_riesgo.csv (categoría x sensibilidad) da el nivel base.
    4. Los hallazgos (rol no autorizado, UPDATE sin WHERE, comando peligroso,
       posible inyección, ...) suben el nivel o le imponen un mínimo.
    5. El nivel del script es el de su sentencia más riesgosa, y
       matriz_escalamiento.csv define a quién se escala.

El LLM no decide el nivel: solo lo explica (ver analizador_llm.py).
"""

import re

import catalogo_activos
from fase_proactiva import parser_sql

NIVELES = ["bajo", "medio", "alto", "critico"]
SENSIBILIDADES = ["ninguno", "bajo", "medio", "alto"]

CATEGORIAS = {
    "SELECT": "LECTURA",
    "INSERT": "ESCRITURA",
    "UPDATE": "ESCRITURA",
    "MERGE": "ESCRITURA",
    "DELETE": "ELIMINACION",
    "TRUNCATE": "ELIMINACION",
    "DROP": "DDL",
    "ALTER": "DDL",
    "CREATE": "DDL",
    "GRANT": "PRIVILEGIOS",
    "REVOKE": "PRIVILEGIOS",
    "DENY": "PRIVILEGIOS",
    "EXEC": "EJECUCION",
    "WAITFOR": "EJECUCION",
    "USE": "CONTROL",
    "DECLARE": "CONTROL",
    "SET": "CONTROL",
    "TRANSACCION": "CONTROL",
}

# Objetos de servidor cuya manipulación es crítica sin importar la tabla.
_RE_OBJETO_SERVIDOR = re.compile(
    r"^(?:DROP|ALTER|CREATE)\s+(?:DATABASE|LOGIN|USER|SERVER|ROLE|SCHEMA)|^ALTER\s+AUTHORIZATION",
    re.IGNORECASE,
)

# Procedimientos/funciones que permiten ejecutar comandos del SO, cambiar la
# configuración del servidor o mover datos fuera de él.
PROCEDIMIENTOS_CRITICOS = {
    "xp_cmdshell": "ejecuta comandos del sistema operativo desde SQL Server",
    "sp_configure": "cambia la configuración del servidor",
    "sp_addsrvrolemember": "agrega un login a un rol de servidor (ej. sysadmin)",
    "sp_addrolemember": "agrega un usuario a un rol de base de datos",
    "sp_password": "cambia contraseñas de logins",
    "xp_regwrite": "escribe en el registro de Windows",
    "sp_oacreate": "instancia objetos COM con acceso al sistema",
    "xp_dirtree": "lista directorios y se usa para filtrar credenciales por red",
}
FUNCIONES_ACCESO_REMOTO = {
    "openrowset": "lee o envía datos a fuentes externas",
    "opendatasource": "abre conexiones ad hoc a otros servidores",
    "openquery": "ejecuta consultas en servidores vinculados",
}
PROCEDIMIENTOS_SQL_DINAMICO = {"sp_executesql"}


def _subir(nivel: str, pasos: int) -> str:
    return NIVELES[min(len(NIVELES) - 1, NIVELES.index(nivel) + pasos)]


def _max_nivel(niveles) -> str:
    return max(niveles, key=NIVELES.index, default="bajo")


def categoria_operacion(tipo_operacion: str) -> str:
    """Mapea el tipo de operación del parser a una categoría de la matriz."""
    principal = tipo_operacion.split()[0] if tipo_operacion else ""
    return CATEGORIAS.get(principal, "EJECUCION")


def objetos_sensibles_afectados(sentencia: dict, rol: str, catalogo: list[dict]) -> list[dict]:
    """
    Cruza las tablas/columnas de una sentencia parseada contra el catálogo.

    Si la operación afecta filas completas (DELETE, DROP, SELECT *, ...) se
    consideran afectadas todas las columnas sensibles de sus tablas; si no,
    solo las columnas referenciadas.

    Returns:
        Lista de dicts {tabla, columna, nivel_sensibilidad, roles_autorizados, autorizado}.
    """
    tablas = {t.lower() for t in sentencia["tablas"]}
    refs = [((t or "").lower() or None, c.lower()) for t, c in sentencia["referencias_columnas"]]

    afectados = []
    for obj in catalogo:
        tabla, columna = obj["tabla"].lower(), obj["columna"].lower()
        if tabla not in tablas:
            continue
        tocada = sentencia["alcance_completo"] or any(
            c == columna and (t is None or t == tabla) for t, c in refs
        )
        if not tocada:
            continue
        roles = catalogo_activos.separar_lista(obj.get("roles_autorizados") or obj.get("rol_autorizado"))
        afectados.append({
            "tabla": obj["tabla"],
            "columna": obj["columna"],
            "nivel_sensibilidad": obj["nivel_sensibilidad"].strip().lower(),
            "roles_autorizados": roles,
            "autorizado": rol.lower() in {r.lower() for r in roles},
        })
    return afectados


def detectar_hallazgos(sentencia: dict, categoria: str, afectados: list[dict]) -> list[dict]:
    """
    Señales de riesgo de la sentencia más allá de la matriz base.

    Cada hallazgo trae `incremento` (niveles que suma) y/o `minimo` (nivel
    mínimo que impone), además de una descripción y una mitigación.
    """
    hallazgos = []
    texto = sentencia["sentencia_original"]
    texto_min = texto.lower()
    tipo = sentencia["tipo_operacion"]
    sensibles = [o for o in afectados if o["nivel_sensibilidad"] in {"medio", "alto"}]

    def agregar(codigo, descripcion, mitigacion, incremento=0, minimo=None):
        hallazgos.append({
            "codigo": codigo,
            "descripcion": descripcion,
            "mitigacion": mitigacion,
            "incremento": incremento,
            "minimo": minimo,
        })

    no_autorizados = [o for o in sensibles if not o["autorizado"]]
    if no_autorizados:
        columnas = ", ".join(f"{o['tabla']}.{o['columna']}" for o in no_autorizados)
        roles = sorted({r for o in no_autorizados for r in o["roles_autorizados"]})
        agregar(
            "ROL_NO_AUTORIZADO",
            f"El rol del usuario no está autorizado sobre {columnas}.",
            f"Solicitar la ejecución o aprobación a un rol autorizado ({', '.join(roles)}).",
            incremento=1,
        )

    if tipo in {"UPDATE", "DELETE"} and not sentencia["tiene_where"]:
        agregar(
            "SIN_WHERE",
            f"El {tipo} no tiene cláusula WHERE: afecta todos los registros de la tabla.",
            "Agregar un WHERE que limite los registros afectados y validar antes con un SELECT COUNT(*).",
            incremento=1,
        )
    if tipo == "TRUNCATE":
        agregar(
            "SIN_WHERE",
            "TRUNCATE elimina todos los registros de la tabla y no puede filtrarse.",
            "Usar DELETE con WHERE si solo se requiere limpiar un subconjunto, y respaldar la tabla antes.",
            incremento=1,
        )

    if (
        categoria == "LECTURA"
        and sensibles
        and not sentencia["tiene_where"]
        and not sentencia["tiene_top"]
        and not sentencia["solo_agregados"]
    ):
        agregar(
            "EXPOSICION_MASIVA",
            "Lee columnas sensibles sin filtro: expone todos los registros de la tabla.",
            "Agregar un WHERE selectivo o devolver solo agregados (COUNT, SUM) en lugar de datos individuales.",
            incremento=1,
        )

    if sentencia["select_asterisco"] and afectados:
        agregar(
            "SELECT_ASTERISCO",
            "Usa SELECT * sobre una tabla con columnas sensibles.",
            "Listar explícitamente solo las columnas necesarias.",
        )

    if sentencia["select_into"] and sensibles:
        agregar(
            "COPIA_DATOS",
            "Copia datos sensibles a otra tabla, lo que los saca del control de acceso original.",
            "Evitar copias de datos sensibles; si son necesarias, enmascarar o anonimizar las columnas.",
            incremento=1,
        )

    for nombre, efecto in PROCEDIMIENTOS_CRITICOS.items():
        if re.search(rf"\b{nombre}\b", texto_min):
            agregar(
                "COMANDO_PELIGROSO",
                f"Invoca {nombre}, que {efecto}.",
                f"No ejecutar {nombre} desde scripts; debe hacerlo un administrador con aprobación de Seguridad.",
                minimo="critico",
            )
    for nombre, efecto in FUNCIONES_ACCESO_REMOTO.items():
        if re.search(rf"\b{nombre}\b", texto_min):
            agregar(
                "ACCESO_REMOTO",
                f"Usa {nombre.upper()}, que {efecto}.",
                "Usar servidores vinculados aprobados y revisar con Seguridad cualquier movimiento de datos fuera del servidor.",
                minimo="alto",
            )

    if (sentencia["procedimiento"] or "").lower() in PROCEDIMIENTOS_SQL_DINAMICO or re.match(r"^exec(ute)?\s*\(", texto_min):
        agregar(
            "SQL_DINAMICO",
            "Ejecuta SQL dinámico, cuyo contenido real no puede verificarse antes de la ejecución.",
            "Reemplazar por sentencias estáticas o parametrizadas.",
            minimo="alto",
        )

    if sentencia["tautologia"]:
        agregar(
            "POSIBLE_INYECCION",
            "Contiene una condición siempre verdadera (ej. OR 1=1), patrón típico de inyección SQL.",
            "Revisar el origen de la sentencia; usar consultas parametrizadas en la aplicación.",
            minimo="alto",
        )
    if tipo == "WAITFOR" or "waitfor delay" in texto_min:
        agregar(
            "POSIBLE_INYECCION",
            "Usa WAITFOR DELAY, técnica común en inyección SQL basada en tiempo.",
            "Revisar el origen de la sentencia; usar consultas parametrizadas en la aplicación.",
            minimo="alto",
        )

    if _RE_OBJETO_SERVIDOR.match(texto):
        agregar(
            "OBJETO_SERVIDOR",
            f"Modifica un objeto de servidor o de seguridad ({tipo}).",
            "Tramitar el cambio por control de cambios con aprobación de Seguridad de la información.",
            minimo="critico",
        )

    if not sentencia["parseado"]:
        agregar(
            "NO_PARSEADO",
            "La sentencia no pudo analizarse estructuralmente; se evaluó de forma conservadora.",
            "Revisar manualmente la sentencia antes de ejecutarla.",
            minimo="medio",
        )

    return hallazgos


def evaluar_impacto(sentencia: dict, categoria: str, afectados: list[dict]) -> dict:
    """
    Evaluación de impacto: qué dimensión de seguridad (confidencialidad,
    integridad, disponibilidad) compromete la sentencia y con qué alcance.
    """
    dimensiones = {
        "LECTURA": ["confidencialidad"],
        "ESCRITURA": ["integridad"],
        "ELIMINACION": ["integridad", "disponibilidad"],
        "DDL": ["integridad", "disponibilidad"],
        "PRIVILEGIOS": ["confidencialidad", "integridad"],
        "EJECUCION": ["confidencialidad", "integridad", "disponibilidad"],
        "CONTROL": [],
    }[categoria]
    if sentencia["select_into"] and "integridad" not in dimensiones:
        dimensiones = dimensiones + ["integridad"]

    if categoria in {"DDL", "PRIVILEGIOS"}:
        alcance = "estructural"
    elif categoria in {"CONTROL", "EJECUCION"} or not sentencia["tablas"]:
        alcance = "sin tablas" if categoria != "EJECUCION" else "servidor"
    elif sentencia["tipo_operacion"] == "TRUNCATE" or not (sentencia["tiene_where"] or sentencia["tiene_top"]):
        alcance = "masivo"
    else:
        alcance = "filtrado"

    return {
        "dimensiones": dimensiones,
        "alcance": alcance,
        "objetos_sensibles": len(afectados),
    }


def evaluar_sentencia(sentencia: dict, rol: str, catalogo: list[dict], matriz_riesgo: dict) -> dict:
    """
    Evalúa una sentencia ya parseada.

    Returns:
        dict con la sentencia parseada más: categoria, objetos_sensibles,
        sensibilidad_maxima, nivel_base, hallazgos, impacto y nivel_riesgo.
    """
    categoria = categoria_operacion(sentencia["tipo_operacion"])
    afectados = objetos_sensibles_afectados(sentencia, rol, catalogo)
    sensibilidad = max((o["nivel_sensibilidad"] for o in afectados), key=SENSIBILIDADES.index, default="ninguno")

    nivel_base = matriz_riesgo[categoria][sensibilidad]
    hallazgos = detectar_hallazgos(sentencia, categoria, afectados)

    nivel = _subir(nivel_base, sum(h["incremento"] for h in hallazgos))
    nivel = _max_nivel([nivel] + [h["minimo"] for h in hallazgos if h["minimo"]])

    return {
        **sentencia,
        "categoria": categoria,
        "objetos_sensibles": afectados,
        "sensibilidad_maxima": sensibilidad,
        "nivel_base": nivel_base,
        "hallazgos": hallazgos,
        "impacto": evaluar_impacto(sentencia, categoria, afectados),
        "nivel_riesgo": nivel,
    }


def evaluar_script(
    script_sql: str,
    rol: str,
    catalogo: list[dict] | None = None,
    matriz_riesgo: dict | None = None,
    matriz_escalamiento: dict | None = None,
) -> dict:
    """
    Punto de entrada del motor: parsea y evalúa un script completo.

    Args:
        script_sql: Script T-SQL (una o varias sentencias).
        rol: Rol del usuario que va a ejecutarlo.
        catalogo / matrices: si no se pasan se cargan de catalogo_activos/.

    Returns:
        dict con:
            - nivel_riesgo: nivel de la sentencia más riesgosa
            - escalamiento: fila de matriz_escalamiento para ese nivel
            - requiere_validacion_adicional: bool
            - sentencias: lista de evaluaciones por sentencia
            - sentencia_critica: índice de la sentencia más riesgosa (o None)
    """
    catalogo = catalogo if catalogo is not None else catalogo_activos.cargar_objetos_sensibles()
    matriz_riesgo = matriz_riesgo or catalogo_activos.cargar_matriz_riesgo()
    matriz_escalamiento = matriz_escalamiento or catalogo_activos.cargar_matriz_escalamiento()

    sentencias = [
        evaluar_sentencia(s, rol, catalogo, matriz_riesgo)
        for s in parser_sql.parsear_script(script_sql)
    ]

    if sentencias:
        critica = max(range(len(sentencias)), key=lambda i: NIVELES.index(sentencias[i]["nivel_riesgo"]))
        nivel = sentencias[critica]["nivel_riesgo"]
    else:
        critica, nivel = None, "bajo"

    escalamiento = matriz_escalamiento[nivel]
    return {
        "nivel_riesgo": nivel,
        "escalamiento": escalamiento,
        "requiere_validacion_adicional": escalamiento["requiere_validacion_adicional"],
        "sentencias": sentencias,
        "sentencia_critica": critica,
        "rol": rol,
    }


def explicar_evaluacion(evaluacion: dict) -> dict:
    """
    Explicación en lenguaje natural armada con plantillas, a partir de la
    evaluación del motor. Es la salida por defecto mientras no haya LLM y el
    respaldo si la llamada al LLM falla.

    Returns:
        dict con explicacion (str) y sugerencia_mitigacion (str).
    """
    sentencias = evaluacion["sentencias"]
    if not sentencias:
        return {
            "explicacion": "El script no contiene sentencias para analizar.",
            "sugerencia_mitigacion": "—",
        }

    s = sentencias[evaluacion["sentencia_critica"]]
    nivel = evaluacion["nivel_riesgo"]
    partes = []

    if len(sentencias) > 1:
        partes.append(
            f"El script tiene {len(sentencias)} sentencias; la de mayor riesgo es la número "
            f"{evaluacion['sentencia_critica'] + 1}."
        )

    tablas = ", ".join(s["tablas"]) or "ninguna tabla"
    partes.append(f"Es una operación {s['tipo_operacion']} ({s['categoria'].lower()}) sobre {tablas}.")

    if s["objetos_sensibles"]:
        detalle = ", ".join(
            f"{o['tabla']}.{o['columna']} ({o['nivel_sensibilidad']})" for o in s["objetos_sensibles"]
        )
        partes.append(f"Afecta objetos sensibles del catálogo: {detalle}.")
    elif s["categoria"] not in {"CONTROL", "EJECUCION"}:
        partes.append("No afecta objetos registrados como sensibles en el catálogo.")

    for h in s["hallazgos"]:
        partes.append(h["descripcion"])

    impacto = s["impacto"]
    if impacto["dimensiones"]:
        partes.append(
            f"Compromete la {' y la '.join(impacto['dimensiones'])} de los datos con alcance {impacto['alcance']}."
        )

    esc = evaluacion["escalamiento"]
    partes.append(f"Nivel de riesgo {nivel.upper()} → {esc['escalamiento']}: {esc['accion']}")

    mitigaciones = []
    for sent in sentencias:
        for h in sent["hallazgos"]:
            if h["mitigacion"] not in mitigaciones:
                mitigaciones.append(h["mitigacion"])
    if not mitigaciones:
        mitigaciones.append(
            "No se requieren acciones adicionales." if nivel == "bajo"
            else f"Validar la sentencia con {esc['responsable']} antes de ejecutarla."
        )

    return {
        "explicacion": " ".join(partes),
        "sugerencia_mitigacion": " ".join(mitigaciones),
    }
