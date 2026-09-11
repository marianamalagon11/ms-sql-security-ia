"""
Página principal de la aplicación Streamlit del proyecto Evaluación de
Seguridad en sentencias MS-SQL mediante IA.

Punto de entrada: `streamlit run front/app.py`
Las páginas de cada fase viven en front/pages/ y son detectadas
automáticamente por Streamlit en el menú lateral.
"""

import streamlit as st

st.set_page_config(
    page_title="Evaluación de Seguridad en sentencias MS-SQL mediante IA",
    layout="wide",
)

st.markdown(
    """
    <style>
    .app-subtitle {
        color: #9AA5B1;
        font-size: 1.05rem;
        margin-top: -0.6rem;
    }
    .phase-tag {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        padding: 0.15rem 0.55rem;
        border-radius: 4px;
        margin-bottom: 0.6rem;
        background-color: rgba(62, 124, 177, 0.18);
        color: #7FB2DE;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Evaluación de Seguridad en sentencias Microsoft SQL Server (MS-SQL) mediante IA")
st.markdown(
    '<p class="app-subtitle">Evaluación de seguridad en sentencias MS-SQL mediante IA</p>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    Este proyecto es un sistema que apoya a equipos de DBAs y seguridad en la
    evaluación del riesgo de operaciones sobre bases de datos Microsoft SQL Server,
    combinando análisis de contexto (roles, objetos sensibles) con modelos de IA.

    Proyecto universitario — Escuela Colombiana de Ingeniería Julio Garavito.
    """
)

st.divider()
st.subheader("Módulos del sistema")
st.caption("Usa el menú lateral para navegar entre las dos fases.")

col1, col2 = st.columns(2, gap="medium")

with col1:
    with st.container(border=True):
        st.markdown('<span class="phase-tag">FASE 01 · PRE-EJECUCIÓN</span>', unsafe_allow_html=True)
        st.markdown("#### Fase Proactiva")
        st.markdown(
            """
            Analiza un **script SQL antes de su ejecución**.

            - Parsea la sentencia (tablas, columnas, tipo de operación).
            - La contrasta contra el catálogo de objetos sensibles y el rol del usuario.
            - Devuelve nivel de riesgo, explicación en lenguaje natural y sugerencia de mitigación.
            """
        )

with col2:
    with st.container(border=True):
        st.markdown('<span class="phase-tag">FASE 02 · POST-EJECUCIÓN</span>', unsafe_allow_html=True)
        st.markdown("#### Fase Reactiva")
        st.markdown(
            """
            Analiza un **lote de transacciones ya ejecutadas** (CSV).

            - Detecta anomalías con un modelo de clasificación entrenado sobre datos sintéticos.
            - Contrasta contra listas blancas y perfiles autorizados.
            - Genera un reporte de criticidad en lenguaje natural.
            """
        )

st.divider()
st.caption(
    "Prototipo en desarrollo. Los resultados mostrados en las páginas de cada fase pueden ser "
    "datos de ejemplo mientras se completa la integración con el LLM y el modelo de detección."
)
