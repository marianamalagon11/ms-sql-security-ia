"""
Generación del reporte en lenguaje natural de la fase reactiva.

Toma las transacciones ya evaluadas por el modelo de detección
(fase_reactiva.modelo_deteccion) y usa un LLM (Claude) para traducir los
resultados técnicos en un reporte legible para perfiles no técnicos.
"""

import os

# TODO: cargar la API key desde variable de entorno ANTHROPIC_API_KEY
# (ver .env.example) usando python-dotenv + os.getenv("ANTHROPIC_API_KEY").
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def construir_prompt_reporte(transacciones_sospechosas: list[dict]) -> str:
    """
    Construye el prompt que se enviará al LLM para resumir el batch de
    transacciones marcadas como anómalas por el modelo de detección.

    Args:
        transacciones_sospechosas: lista de dicts, cada uno representando
            una transacción marcada con es_anomalo_predicho=True, incluyendo
            su score_anomalia y los campos originales (usuario, ips,
            aplicacion, sentencia_sql, timestamp, tabla_afectada, etc.).

    Returns:
        str con el prompt final a enviar al LLM.

    TODO: Diseñar el prompt para que el LLM devuelva una respuesta estructurada
    con criticidad_resumida, anomalias_identificadas y explicaciones_simplificadas.
    """
    raise NotImplementedError("TODO: construir el prompt de reporte para el LLM")


def generar_reporte(transacciones_evaluadas) -> dict:
    """
    Punto de entrada de la fase reactiva: filtra las transacciones
    sospechosas, arma el prompt y llama a la API de Claude para obtener el
    reporte en lenguaje natural.

    Args:
        transacciones_evaluadas: DataFrame o lista de dicts con el resultado
            de fase_reactiva.modelo_deteccion.predecir_anomalias.

    Returns:
        dict con las claves:
            - criticidad_resumida: str
            - anomalias_identificadas: list[str]
            - explicacion_simplificada: str

    TODO: Filtrar transacciones_evaluadas por es_anomalo_predicho == True.
    TODO: Llamar a construir_prompt_reporte(...) con esas transacciones.
    TODO: Invocar el cliente de Anthropic (anthropic.Anthropic(api_key=ANTHROPIC_API_KEY))
    y parsear la respuesta a un dict con las claves esperadas.
    """
    raise NotImplementedError("TODO: implementar generación del reporte vía LLM")
