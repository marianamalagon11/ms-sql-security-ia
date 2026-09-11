"""
Análisis de riesgo pre-ejecución vía LLM (Claude).

Combina la sentencia SQL parseada (fase_proactiva.parser_sql) con el
contexto de negocio (rol del usuario, catálogo de objetos sensibles) para
producir un veredicto de riesgo explicado en lenguaje natural.
"""

import os

# TODO: cargar la API key desde variable de entorno ANTHROPIC_API_KEY
# (ver .env.example) usando python-dotenv + os.getenv("ANTHROPIC_API_KEY").
# No hardcodear la API key en el código.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def construir_prompt(sentencia_parseada: dict, contexto_usuario: dict, catalogo_sensibles: list[dict]) -> str:
    """
    Construye el prompt que se enviará al LLM para evaluar el riesgo de la sentencia.

    Args:
        sentencia_parseada: dict devuelto por parser_sql.parsear_sentencia
            (tipo_operacion, tablas, columnas, sentencia_original).
        contexto_usuario: dict con información del usuario que ejecuta la
            sentencia (ej. {"usuario": "jperez", "rol": "Soporte"}).
        catalogo_sensibles: lista de dicts del catálogo de objetos sensibles
            (tabla, columna, nivel_sensibilidad, rol_autorizado).

    Returns:
        str con el prompt final a enviar al LLM.

    TODO: Diseñar el prompt para que el LLM devuelva una respuesta estructurada
    (ej. JSON) con nivel_riesgo, explicacion y sugerencia_mitigacion.
    """
    raise NotImplementedError("TODO: construir el prompt para el LLM")


def analizar_riesgo(sentencia_sql: str, contexto_usuario: dict, catalogo_sensibles: list[dict]) -> dict:
    """
    Punto de entrada de la fase proactiva: parsea la sentencia, arma el
    prompt y llama a la API de Claude para obtener el veredicto de riesgo.

    Args:
        sentencia_sql: Texto crudo de la sentencia SQL a analizar.
        contexto_usuario: dict con información del usuario (rol, permisos).
        catalogo_sensibles: catálogo de objetos sensibles (ver catalogo_activos/).

    Returns:
        dict con las claves:
            - nivel_riesgo: str ("bajo", "medio", "alto")
            - explicacion: str en lenguaje natural
            - sugerencia_mitigacion: str
            - requiere_validacion_adicional: bool

    TODO: Llamar a fase_proactiva.parser_sql.parsear_sentencia(sentencia_sql).
    TODO: Llamar a construir_prompt(...) con el resultado del parseo.
    TODO: Invocar el cliente de Anthropic (anthropic.Anthropic(api_key=ANTHROPIC_API_KEY))
    y parsear la respuesta a un dict con las claves esperadas.
    """
    raise NotImplementedError("TODO: implementar llamada al LLM y orquestación")
