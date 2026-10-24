"""
Generación del reporte en lenguaje natural de la fase reactiva.

Toma las transacciones marcadas como sospechosas por el modelo de detección
(fase_reactiva.modelo_deteccion.predecir) y arma un reporte en lenguaje
natural con plantillas: criticidad resumida, el detalle de cada anomalía y
una explicación simplificada. Las plantillas son la implementación final de
esta entrega (no un placeholder); el diseño queda abierto a reemplazarlas
por un LLM en el futuro, pero eso no es parte del alcance actual del
proyecto (ver construir_prompt_reporte).
"""

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fase_reactiva.modelo_deteccion import construir_features  # noqa: E402

NIVELES_PROBABILIDAD = [("critico", 0.85), ("alto", 0.7), ("medio", 0.4), ("bajo", 0.0)]


ACCIONES = {
    "SELECT": "consultó",
    "INSERT": "registró nueva información sobre",
    "UPDATE": "modificó",
    "DELETE": "borró registros de",
    "TRUNCATE": "eliminó todos los registros de",
    "DROP": "eliminó por completo",
    "ALTER": "cambió la estructura de",
    "GRANT": "otorgó permisos de acceso sobre",
    "DENY": "quitó permisos de acceso sobre",
    "EXEC": "ejecutó un proceso interno sobre",
    "CREATE": "creó un objeto nuevo sobre",
}

OPERACIONES_DESTRUCTIVAS = {"DELETE", "TRUNCATE", "DROP"}
OPERACIONES_DE_PERMISOS = {"GRANT", "DENY"}
OPERACIONES_ESTRUCTURALES = {"ALTER", "CREATE"}

TABLAS_LEGIBLES = {
    "Empleados": "empleados",
    "Clientes": "clientes",
    "Usuarios": "usuarios",
    "Transacciones": "transacciones",
    "Pedidos": "pedidos",
    "Productos": "productos",
    "Auditoria": "auditoría",
}

COLUMNAS_LEGIBLES = {
    "salario": "los salarios",
    "cuenta_bancaria": "las cuentas bancarias",
    "password_hash": "las contraseñas",
    "email": "los correos electrónicos",
    "numero_documento": "los números de documento",
    "nombre_completo": "los nombres completos",
    "nombre": "los nombres",
    "cargo": "los cargos",
    "ciudad": "las ciudades",
    "activo": "el estado de activación",
    "log_acceso": "los registros de acceso",
    "fecha_evento": "las fechas de los eventos",
    "fecha_registro": "las fechas de registro",
    "fecha_pedido": "las fechas de los pedidos",
    "monto": "los montos",
    "total": "los totales",
    "estado": "los estados",
    "precio": "los precios",
    "categoria": "las categorías",
}

VOLUMEN_INUSUAL = 1000

# Señales que puede tener una transacción sospechosa: frase para el resumen y
# etiqueta para las listas.
SENALES = {
    "permisos": {"en_resumen": "el cambio de permisos de acceso", "etiqueta": "Cambio de permisos de acceso"},
    "destructiva": {"en_resumen": "las operaciones destructivas", "etiqueta": "Operación destructiva"},
    "rol_no_autorizado": {"en_resumen": "el acceso de roles no autorizados", "etiqueta": "Acceso de un rol no autorizado"},
    "ip_externa": {"en_resumen": "la conexión desde redes externas", "etiqueta": "Conexión desde una red externa"},
    "estructural": {
        "en_resumen": "el cambio de estructura de la base de datos",
        "etiqueta": "Cambio en la estructura de la base de datos",
    },
    "volumen": {
        "en_resumen": "las operaciones masivas de registros",
        "etiqueta": f"Más de {VOLUMEN_INUSUAL:,} registros en una sola operación".replace(",", "."),
    },
    "dato_muy_sensible": {
        "en_resumen": "el acceso a información altamente sensible",
        "etiqueta": "Información altamente sensible",
    },
    "fuera_de_horario": {"en_resumen": "el acceso fuera del horario habitual", "etiqueta": "Fuera del horario habitual del usuario"},
    "aplicacion_no_habitual": {
        "en_resumen": "el uso de aplicaciones no habituales",
        "etiqueta": "Aplicación que el usuario no suele usar",
    },
}

MAX_USUARIOS_CONCENTRACION = 5

_VACIOS = {None, "", "-", "*"}


def _vacio(valor) -> bool:
    return valor in _VACIOS or valor != valor  # el segundo caso descarta NaN


def _nivel_por_probabilidad(probabilidad: float) -> str:
    for nivel, minimo in NIVELES_PROBABILIDAD:
        if probabilidad >= minimo:
            return nivel
    return "bajo"


def _cantidad(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _enumerar(frases: list[str]) -> str:
    if len(frases) == 1:
        return frases[0]
    return ", ".join(frases[:-1]) + f" y {frases[-1]}"


def _frase_objeto(tabla, columna) -> str:
    if _vacio(tabla):
        return "un objeto de la base de datos que no se pudo identificar"
    tabla_legible = TABLAS_LEGIBLES.get(tabla, str(tabla).lower())
    if _vacio(columna):
        return f"la tabla de {tabla_legible}"
    columna_legible = COLUMNAS_LEGIBLES.get(columna, f"el campo {str(columna).replace('_', ' ')}")
    return f"{columna_legible} en la tabla de {tabla_legible}"


def _senales_detectadas(fila, senales) -> list[tuple[str, str]]:
    """
    Señales por las que la transacción destaca, como pares (clave, frase en
    lenguaje llano). La clave es una de las de SENALES y sirve para agrupar y
    priorizar en el resumen; la frase es la que se muestra en el detalle.
    """
    detectadas = []

    if senales["fuera_de_horario"]:
        hora = pd.to_datetime(fila.get("timestamp")).strftime("%H:%M")
        detectadas.append(("fuera_de_horario", f"ocurrió a las {hora}, fuera del horario habitual de esta persona"))

    if senales["es_ip_externa"]:
        detectadas.append(
            ("ip_externa", f"se conectó desde una red ajena a la organización (IP {fila.get('ip_origen')})")
        )

    aplicacion = fila.get("aplicacion")
    if not senales["aplicacion_habitual"]:
        if _vacio(aplicacion) or aplicacion == "desconocida":
            frase = "se hizo desde una aplicación que no se pudo identificar"
        else:
            frase = f"se hizo desde {aplicacion}, que no es la herramienta que suele usar"
        detectadas.append(("aplicacion_no_habitual", frase))

    if not senales["autorizado"]:
        detectadas.append(
            ("rol_no_autorizado", f"su rol ({fila.get('rol')}) no está autorizado para acceder a esa información")
        )
    elif senales["nivel_sensibilidad"] >= 3:
        detectadas.append(("dato_muy_sensible", "se trata de información clasificada como altamente sensible"))

    operacion = fila.get("tipo_operacion")
    if operacion in OPERACIONES_DESTRUCTIVAS:
        detectadas.append(("destructiva", "es una operación destructiva: la información borrada no se recupera sola"))
    elif operacion in OPERACIONES_DE_PERMISOS:
        detectadas.append(("permisos", "cambia los permisos de acceso de otras personas sobre esos datos"))
    elif operacion in OPERACIONES_ESTRUCTURALES:
        detectadas.append(
            ("estructural", "altera la estructura de la base de datos, no solo la información que contiene")
        )

    filas_afectadas = fila.get("filas_afectadas")
    if filas_afectadas is not None and filas_afectadas == filas_afectadas and filas_afectadas >= VOLUMEN_INUSUAL:
        cantidad = f"{int(filas_afectadas):,}".replace(",", ".")
        detectadas.append(("volumen", f"tocó {cantidad} registros de una sola vez"))

    return detectadas


def _motivos(fila, senales) -> list[str]:
    """Traduce a lenguaje llano las señales por las que la transacción destaca."""
    return [frase for _, frase in _senales_detectadas(fila, senales)]


def _describir_fila(fila, senales) -> str:
    usuario = fila.get("usuario") if not _vacio(fila.get("usuario")) else "Un usuario no identificado"
    accion = ACCIONES.get(fila.get("tipo_operacion"), "realizó una operación sobre")
    objeto = _frase_objeto(fila.get("tabla_afectada"), fila.get("columna_afectada"))

    motivos = _motivos(fila, senales)
    if motivos:
        explicacion = f"Llama la atención porque {_enumerar(motivos)}."
    else:
        explicacion = "Se apartó del comportamiento que esta persona registra habitualmente."

    return f"**{usuario}** {accion} {objeto}. {explicacion}"


def detallar_transacciones(transacciones_sospechosas) -> pd.DataFrame:
    """
    Agrega a cada transacción sospechosa su nivel y el motivo en lenguaje
    llano, y las ordena de la más a la menos grave.

    Args:
        transacciones_sospechosas: DataFrame con el resultado de
            fase_reactiva.modelo_deteccion.predecir ya filtrado a las filas
            sospechosas (incluye columna probabilidad_anomalia).

    Returns:
        Copia del DataFrame con las columnas nivel y motivo, ordenada por
        nivel y luego por probabilidad_anomalia descendente.
    """
    df = transacciones_sospechosas.copy()
    if df.empty:
        return df.assign(nivel=pd.Series(dtype=str), motivo=pd.Series(dtype=str))

    senales = construir_features(df)
    motivos = []
    for (_, fila), (_, senal) in zip(df.iterrows(), senales.iterrows()):
        frases = _motivos(fila, senal) or ["se apartó del comportamiento que esta persona registra habitualmente"]
        texto = "; ".join(frases)
        motivos.append(texto[0].upper() + texto[1:] + ".")

    df["nivel"] = df["probabilidad_anomalia"].map(_nivel_por_probabilidad)
    df["motivo"] = motivos
    orden = {nivel: i for i, (nivel, _) in enumerate(NIVELES_PROBABILIDAD)}
    return df.sort_values(
        ["nivel", "probabilidad_anomalia"],
        ascending=[True, False],
        key=lambda col: col.map(orden) if col.name == "nivel" else col,
        kind="stable",
    )


def construir_prompt_reporte(transacciones_sospechosas: list[dict]) -> str:
    """
    Extensión futura (fuera del alcance actual): arma el prompt para que un
    LLM redacte el reporte en lugar de las plantillas de generar_reporte.

    Args:
        transacciones_sospechosas: lista de dicts, cada uno representando
            una transacción con es_anomalo_predicho=True, incluyendo su
            probabilidad_anomalia y los campos originales (usuario, ips,
            aplicacion, sentencia_sql, timestamp, tabla_afectada, etc.).

    Returns:
        str con el prompt a enviar al LLM.
    """
    raise NotImplementedError("Extensión futura: no es parte del alcance actual del proyecto")


def generar_reporte(transacciones_sospechosas) -> dict:
    """
    Punto de entrada de la fase reactiva: arma el reporte en lenguaje
    natural a partir de las transacciones que el modelo de detección marcó
    como sospechosas (es_anomalo_predicho=True).

    Args:
        transacciones_sospechosas: DataFrame con el resultado de
            fase_reactiva.modelo_deteccion.predecir ya filtrado a las filas
            sospechosas (incluye columna probabilidad_anomalia).

    Returns:
        dict con las claves:
            - resumen: str con la síntesis del lote en dos o tres frases.
            - patrones: list[str], cuántas transacciones tienen cada señal.
            - usuarios_destacados: list[str], usuarios con más de una alerta.
            - anomalias_identificadas: list[str], una frase por transacción.
    """
    df = transacciones_sospechosas
    if df.empty:
        return {
            "resumen": (
                "No se identificaron transacciones sospechosas en este lote. Todas las transacciones "
                "evaluadas son consistentes con los perfiles, horarios y permisos registrados en el catálogo."
            ),
            "patrones": [],
            "usuarios_destacados": [],
            "anomalias_identificadas": [],
        }

    senales = construir_features(df)
    casos = []
    for (_, fila), (_, senal) in zip(df.iterrows(), senales.iterrows()):
        casos.append({
            "fila": fila,
            "usuario": str(fila.get("usuario")),
            "descripcion": _describir_fila(fila, senal),
            "claves": [clave for clave, _ in _senales_detectadas(fila, senal)],
        })

    conteo = Counter(c for caso in casos for c in caso["claves"])
    patrones = [
        f"{SENALES[clave]['etiqueta']}: {_cantidad(n, 'transacción', 'transacciones')}."
        for clave, n in conteo.most_common()
    ]

    usuarios_destacados = []
    for usuario, n in Counter(caso["usuario"] for caso in casos).most_common():
        if n < 2 or len(usuarios_destacados) == MAX_USUARIOS_CONCENTRACION:
            break
        suyos = [caso for caso in casos if caso["usuario"] == usuario]
        texto = f"**{usuario}** ({suyos[0]['fila'].get('rol')}): {_cantidad(n, 'transacción sospechosa', 'transacciones sospechosas')}"
        claves_usuario = Counter(c for caso in suyos for c in caso["claves"])
        if claves_usuario:
            principal, veces = claves_usuario.most_common(1)[0]
            texto += f"; señal principal: {SENALES[principal]['etiqueta'].lower()} (en {veces} de {n})"
        usuarios_destacados.append(texto + ".")

    resumen = (
        f"Se marcaron {_cantidad(len(casos), 'transacción sospechosa', 'transacciones sospechosas')} "
        f"de {_cantidad(df['usuario'].nunique(), 'usuario', 'usuarios distintos')}."
    )
    if conteo:
        principal, veces = conteo.most_common(1)[0]
        resumen += (
            f" La señal más frecuente es {SENALES[principal]['en_resumen']} "
            f"({_cantidad(veces, 'caso', 'casos')})."
        )

    return {
        "resumen": resumen,
        "patrones": patrones,
        "usuarios_destacados": usuarios_destacados,
        "anomalias_identificadas": [caso["descripcion"] for caso in casos],
    }
