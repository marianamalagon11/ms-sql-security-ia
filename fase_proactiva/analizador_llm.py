"""
Análisis de riesgo pre-ejecución vía LLM (Claude).

Combina la sentencia SQL parseada (fase_proactiva.parser_sql) con el
contexto de negocio (rol del usuario, catálogo de objetos sensibles) para
producir un veredicto de riesgo explicado en lenguaje natural.

El nivel de riesgo y el escalamiento los calcula el motor de reglas
(fase_proactiva.motor_reglas); el LLM solo redacta la explicación y la
mitigación. Mientras no haya API key configurada se usa la explicación por
plantillas del motor.
"""

import os

from fase_proactiva import motor_reglas

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
    (ej. JSON) con explicacion y sugerencia_mitigacion. El prompt debe incluir
    la evaluación del motor de reglas (nivel, hallazgos, objetos sensibles,
    escalamiento) para que el LLM la explique sin cambiar el nivel.
    """
    raise NotImplementedError("TODO: construir el prompt para el LLM")


def analizar_riesgo(sentencia_sql: str, contexto_usuario: dict, catalogo_sensibles: list[dict]) -> dict:
    """
    Punto de entrada de la fase proactiva: evalúa el script con el motor de
    reglas y genera la explicación en lenguaje natural.

    Args:
        sentencia_sql: Texto crudo del script SQL a analizar (una o varias sentencias).
        contexto_usuario: dict con información del usuario ({"usuario", "rol"}).
        catalogo_sensibles: catálogo de objetos sensibles (ver catalogo_activos/).

    Returns:
        dict con las claves:
            - nivel_riesgo: str ("bajo", "medio", "alto", "critico")
            - explicacion: str en lenguaje natural
            - sugerencia_mitigacion: str
            - requiere_validacion_adicional: bool
            - escalamiento: dict de la matriz de escalamiento
            - evaluacion: dict completo del motor (detalle por sentencia)
            - fuente_explicacion: "plantilla" o "llm"

    TODO: cuando haya API key, llamar a construir_prompt(...) e invocar el
    cliente de Anthropic para reemplazar la explicación por plantilla; si la
    llamada falla, conservar la de plantilla.
    """
    evaluacion = motor_reglas.evaluar_script(
        sentencia_sql, contexto_usuario.get("rol", ""), catalogo_sensibles
    )
    textos = motor_reglas.explicar_evaluacion(evaluacion)

    return {
        "nivel_riesgo": evaluacion["nivel_riesgo"],
        "explicacion": textos["explicacion"],
        "sugerencia_mitigacion": textos["sugerencia_mitigacion"],
        "requiere_validacion_adicional": evaluacion["requiere_validacion_adicional"],
        "escalamiento": evaluacion["escalamiento"],
        "evaluacion": evaluacion,
        "fuente_explicacion": "plantilla",
    }
