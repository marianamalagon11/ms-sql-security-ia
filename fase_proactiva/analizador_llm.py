"""
Análisis de riesgo pre-ejecución de la fase proactiva.

Combina la sentencia SQL parseada (fase_proactiva.parser_sql) con el
contexto de negocio (rol del usuario, catálogo de objetos sensibles) para
producir un veredicto de riesgo explicado en lenguaje natural.

El nivel de riesgo y el escalamiento los calcula el motor de reglas
(fase_proactiva.motor_reglas), de forma determinista y auditable; la
explicación y la mitigación se redactan con plantillas
(motor_reglas.explicar_evaluacion). Las plantillas son la implementación
final de esta entrega, no un placeholder: el proyecto se delimitó a un
análisis semántico basado en reglas, sin depender de una API externa.

El diseño queda abierto a reemplazar la redacción por un LLM en el futuro
(ver construir_prompt), pero eso no es parte del alcance actual.
"""

from fase_proactiva import motor_reglas


def construir_prompt(sentencia_parseada: dict, contexto_usuario: dict, catalogo_sensibles: list[dict]) -> str:
    """
    Extensión futura (fuera del alcance actual): arma el prompt para que un
    LLM redacte la explicación y la mitigación en lugar de las plantillas de
    motor_reglas.explicar_evaluacion, sin cambiar el nivel de riesgo que
    calcula el motor de reglas.

    Args:
        sentencia_parseada: dict devuelto por parser_sql.parsear_sentencia
            (tipo_operacion, tablas, columnas, sentencia_original).
        contexto_usuario: dict con información del usuario que ejecuta la
            sentencia (ej. {"usuario": "jperez", "rol": "Soporte"}).
        catalogo_sensibles: lista de dicts del catálogo de objetos sensibles
            (tabla, columna, nivel_sensibilidad, rol_autorizado).

    Returns:
        str con el prompt a enviar al LLM.
    """
    raise NotImplementedError("Extensión futura: no es parte del alcance actual del proyecto")


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
            - fuente_explicacion: "plantilla" (único valor actual; "llm"
              queda reservado para si se integra construir_prompt a futuro)
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
