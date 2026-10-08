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

NIVELES_PROBABILIDAD = [("critico", 0.85), ("alto", 0.7), ("medio", 0.4), ("bajo", 0.0)]


def _nivel_por_probabilidad(probabilidad: float) -> str:
    for nivel, minimo in NIVELES_PROBABILIDAD:
        if probabilidad >= minimo:
            return nivel
    return "bajo"


def _describir_fila(fila, nivel: str) -> str:
    probabilidad = fila.get("probabilidad_anomalia")
    detalle = f" (probabilidad {probabilidad:.0%})" if probabilidad is not None else ""
    return (
        f"[{nivel.upper()}] {fila.get('usuario', '—')} ejecutó {fila.get('tipo_operacion', '—')} sobre "
        f"{fila.get('tabla_afectada', '—')}.{fila.get('columna_afectada', '—')} desde {fila.get('ip_origen', '—')} "
        f"usando {fila.get('aplicacion', '—')}{detalle}."
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
    resumen_niveles = ", ".join(f"{conteo[nivel]} {nivel}" for nivel, _ in NIVELES_PROBABILIDAD if nivel in conteo)

    return {
        "criticidad_resumida": f"Se identificaron {len(df)} transacción(es) sospechosa(s) ({resumen_niveles}).",
        "anomalias_identificadas": [
            _describir_fila(fila, nivel) for (_, fila), nivel in zip(df.iterrows(), niveles)
        ],
        "explicacion_simplificada": (
            "Estas transacciones se desvían de los patrones normales de uso (horario, aplicación, IP de "
            "origen o permisos sobre datos sensibles) registrados en el catálogo. Se recomienda validarlas "
            "con los usuarios y responsables involucrados, priorizando las de mayor probabilidad."
        ),
    }
