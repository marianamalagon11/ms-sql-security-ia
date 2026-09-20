"""
Página Streamlit: Fase Proactiva.

Permite pegar un script SQL, dispararlo contra fase_proactiva.analizador_llm
y mostrar el veredicto de riesgo. Mientras la lógica real (parser + LLM) no
esté implementada, se muestran datos de ejemplo/mock para dejar el flujo
navegable de punta a punta.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402

sys.path.insert(0, str(common.RAIZ))

common.encabezado(
    "Fase Proactiva",
    "Analiza un script SQL antes de su ejecución e identifica riesgos de seguridad.",
)
st.divider()

CONTEXTO_USUARIO_MOCK = {"usuario": "jperez", "rol": "Soporte"}

CATALOGO_MOCK = [
    {"tabla": "Clientes", "columna": "numero_documento", "nivel_sensibilidad": "alto", "rol_autorizado": "DBA"},
    {"tabla": "Usuarios", "columna": "password_hash", "nivel_sensibilidad": "alto", "rol_autorizado": "DBA"},
]

RESULTADO_MOCK = {
    "nivel_riesgo": "alto",
    "explicacion": (
        "La sentencia accede a columnas altamente sensibles (numero_documento, tarjeta_credito) "
        "sin una condición de filtrado selectiva, lo que implica una posible exposición masiva de "
        "datos de clientes. El usuario actual (rol Soporte) no está entre los roles autorizados "
        "para este tipo de acceso según el catálogo de objetos sensibles."
    ),
    "sugerencia_mitigacion": (
        "Restringir la consulta a los campos estrictamente necesarios, agregar una cláusula WHERE "
        "selectiva y solicitar aprobación de un DBA antes de ejecutar en producción."
    ),
    "requiere_validacion_adicional": True,
}

col_input, col_contexto = st.columns([2, 1], gap="large")

with col_input:
    st.markdown("##### Sentencia SQL")
    sentencia_sql = st.text_area(
        "Pega aquí el script SQL a analizar",
        height=220,
        placeholder="SELECT numero_documento, tarjeta_credito FROM Clientes;",
        label_visibility="collapsed",
    )
    analizar = st.button("Analizar", type="primary")

with col_contexto:
    with st.container(border=True):
        st.markdown("##### Contexto de la evaluación")
        st.markdown(f"**Usuario:** {CONTEXTO_USUARIO_MOCK['usuario']}")
        st.markdown(f"**Rol:** {CONTEXTO_USUARIO_MOCK['rol']}")
        st.markdown("**Catálogo:** objetos sensibles cargados")

if analizar:
    if not sentencia_sql.strip():
        st.warning("Pega una sentencia SQL antes de analizar.")
    else:
        from fase_proactiva import analizador_llm

        with st.spinner("Analizando la sentencia…"):
            try:
                resultado = analizador_llm.analizar_riesgo(
                    sentencia_sql, CONTEXTO_USUARIO_MOCK, CATALOGO_MOCK
                )
                es_mock = False
            except NotImplementedError:
                resultado = RESULTADO_MOCK
                es_mock = True

        st.session_state["proactiva_resultado"] = resultado
        st.session_state["proactiva_es_mock"] = es_mock

if "proactiva_resultado" in st.session_state:
    resultado = st.session_state["proactiva_resultado"]
    nivel = str(resultado.get("nivel_riesgo", "medio"))

    st.divider()
    fila_titulo, fila_aviso = st.columns([3, 1], vertical_alignment="center")
    fila_titulo.markdown("### Resultado del análisis")
    if st.session_state.get("proactiva_es_mock"):
        fila_aviso.markdown(common.badge_mock(), unsafe_allow_html=True)

    if st.session_state.get("proactiva_es_mock"):
        st.caption(
            "La lógica de análisis aún no está implementada, así que este veredicto es "
            "un ejemplo fijo y no depende de la sentencia que pegaste."
        )

    with st.container(border=True):
        st.markdown(common.badge_riesgo(nivel), unsafe_allow_html=True)

        st.markdown("**Explicación**")
        st.write(resultado.get("explicacion", "—"))

        st.markdown("**Sugerencia de mitigación**")
        st.write(resultado.get("sugerencia_mitigacion", "—"))

        if resultado.get("requiere_validacion_adicional"):
            st.warning("Esta sentencia requiere validación adicional antes de ejecutarse en producción.")

common.pie()
