"""
Contenido de la página de inicio.
"""

import sys

import streamlit as st

import common

sys.path.insert(0, str(common.RAIZ))

import catalogo_activos  # noqa: E402

common.encabezado(
    "Evaluación de Seguridad en sentencias MS-SQL mediante IA",
    "Análisis de riesgo sobre operaciones de Microsoft SQL Server, antes y después de ejecutarlas.",
)

st.markdown(
    """
    Este proyecto es un sistema que apoya a equipos de DBAs y seguridad en la
    evaluación del riesgo de operaciones sobre bases de datos Microsoft SQL Server,
    combinando análisis de contexto (roles, objetos sensibles) con modelos de IA.
    """
)

st.divider()

col_a, col_b = st.columns(2, gap="medium")
col_a.metric("Fases del sistema", "2", help="Proactiva (pre-ejecución) y reactiva (post-ejecución)")
col_b.metric(
    "Objetos sensibles en catálogo",
    str(len(catalogo_activos.cargar_objetos_sensibles())),
    help="catalogo_activos/objetos_sensibles.csv",
)

st.divider()
st.subheader("Módulos del sistema")
st.caption("Usa el menú lateral para navegar entre las dos fases.")

col1, col2 = st.columns(2, gap="medium")

with col1:
    with st.container(border=True):
        st.markdown(common.tag("FASE 01 · PRE-EJECUCIÓN"), unsafe_allow_html=True)
        st.markdown("#### Fase Proactiva")
        st.markdown(
            """
            Analiza un **script SQL antes de su ejecución**.

            - Parsea la sentencia (tablas, columnas, tipo de operación).
            - La contrasta contra el catálogo de objetos sensibles y el rol del usuario.
            - Devuelve nivel de riesgo, explicación en lenguaje natural y sugerencia de mitigación.
            """
        )
        st.page_link("vistas/1_Fase_Proactiva.py", label="Ir a Fase Proactiva", icon=":material/arrow_forward:")

with col2:
    with st.container(border=True):
        st.markdown(common.tag("FASE 02 · POST-EJECUCIÓN"), unsafe_allow_html=True)
        st.markdown("#### Fase Reactiva")
        st.markdown(
            """
            Analiza un **lote de transacciones ya ejecutadas** (CSV).

            - Detecta anomalías con un modelo de clasificación entrenado sobre datos sintéticos.
            - Contrasta contra listas blancas y perfiles autorizados.
            - Genera un reporte de criticidad en lenguaje natural.
            """
        )
        st.page_link("vistas/2_Fase_Reactiva.py", label="Ir a Fase Reactiva", icon=":material/arrow_forward:")

st.divider()

with st.container(border=True):
    st.markdown("##### Niveles de riesgo")
    st.caption("Cada nivel se identifica por forma, texto y color — nunca por color solo.")
    cols = st.columns(4)
    for col, nivel in zip(cols, ["bajo", "medio", "alto", "critico"]):
        col.markdown(common.badge_riesgo(nivel), unsafe_allow_html=True)

common.pie()
