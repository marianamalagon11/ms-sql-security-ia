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
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fase_reactiva.modelo_deteccion import construir_features  # noqa: E402

NIVELES_PROBABILIDAD = [("critico", 0.85), ("alto", 0.7), ("medio", 0.4), ("bajo", 0.0)]

NIVELES_LEGIBLES = {"critico": "crítica", "alto": "alta", "medio": "media", "bajo": "baja"}

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

_VACIOS = {None, "", "-", "*"}


def _vacio(valor) -> bool:
    return valor in _VACIOS or valor != valor  # el segundo caso descarta NaN


def _nivel_por_probabilidad(probabilidad: float) -> str:
    for nivel, minimo in NIVELES_PROBABILIDAD:
        if probabilidad >= minimo:
            return nivel
    return "bajo"


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


def _motivos(fila, senales) -> list[str]:
    """Traduce a lenguaje llano las señales por las que la transacción destaca."""
    motivos = []

    if senales["fuera_de_horario"]:
        hora = pd.to_datetime(fila.get("timestamp")).strftime("%H:%M")
        motivos.append(f"ocurrió a las {hora}, fuera del horario habitual de esta persona")

    if senales["es_ip_externa"]:
        motivos.append(f"se conectó desde una red ajena a la organización (IP {fila.get('ip_origen')})")

    aplicacion = fila.get("aplicacion")
    if not senales["aplicacion_habitual"]:
        if _vacio(aplicacion) or aplicacion == "desconocida":
            motivos.append("se hizo desde una aplicación que no se pudo identificar")
        else:
            motivos.append(f"se hizo desde {aplicacion}, que no es la herramienta que suele usar")

    if not senales["autorizado"]:
        motivos.append(
            f"su rol ({fila.get('rol')}) no está autorizado para acceder a esa información"
        )
    elif senales["nivel_sensibilidad"] >= 3:
        motivos.append("se trata de información clasificada como altamente sensible")

    operacion = fila.get("tipo_operacion")
    if operacion in OPERACIONES_DESTRUCTIVAS:
        motivos.append("es una operación destructiva: la información borrada no se recupera sola")
    elif operacion in OPERACIONES_DE_PERMISOS:
        motivos.append("cambia los permisos de acceso de otras personas sobre esos datos")
    elif operacion in OPERACIONES_ESTRUCTURALES:
        motivos.append("altera la estructura de la base de datos, no solo la información que contiene")

    filas_afectadas = fila.get("filas_afectadas")
    if filas_afectadas is not None and filas_afectadas == filas_afectadas and filas_afectadas >= VOLUMEN_INUSUAL:
        cantidad = f"{int(filas_afectadas):,}".replace(",", ".")
        motivos.append(f"tocó {cantidad} registros de una sola vez")

    return motivos


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
            - criticidad_resumida: str
            - anomalias_identificadas: list[str]
            - explicacion_simplificada: str
    """
    df = transacciones_sospechosas
    if df.empty:
        return {
            "criticidad_resumida": "No se identificaron transacciones sospechosas en este lote.",
            "anomalias_identificadas": [],
            "explicacion_simplificada": (
                "Todas las transacciones evaluadas son consistentes con los perfiles, horarios y "
                "permisos registrados en el catálogo."
            ),
        }

    niveles = df["probabilidad_anomalia"].map(_nivel_por_probabilidad)
    conteo = niveles.value_counts()
    resumen_niveles = _enumerar(
        [
            f"{conteo[nivel]} {NIVELES_LEGIBLES[nivel]}" + ("" if conteo[nivel] == 1 else "s")
            for nivel, _ in NIVELES_PROBABILIDAD
            if nivel in conteo
        ]
    )
    senales = construir_features(df)

    return {
        "criticidad_resumida": f"Se identificaron {len(df)} transacción(es) sospechosa(s): {resumen_niveles}.",
        "anomalias_identificadas": [
            _describir_fila(fila, senal)
            for (_, fila), (_, senal) in zip(df.iterrows(), senales.iterrows())
        ],
        "explicacion_simplificada": (
            "Estas transacciones se desvían de los patrones normales de uso (horario, aplicación, IP de "
            "origen o permisos sobre datos sensibles) registrados en el catálogo. Se recomienda validarlas "
            "con los usuarios y responsables involucrados, priorizando las de mayor criticidad."
        ),
    }
