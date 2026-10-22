"""
Punto de entrada de la aplicación Streamlit del proyecto Evaluación de
Seguridad en sentencias MS-SQL mediante IA.

Ejecutar con: `streamlit run front/app.py`
"""

import streamlit as st

import common

common.configurar_app()

paginas = [
    st.Page("inicio.py", title="Inicio", icon=":material/home:", default=True),
    st.Page("pages/1_Fase_Proactiva.py", title="Fase Proactiva", icon=":material/shield:"),
    st.Page("pages/2_Fase_Reactiva.py", title="Fase Reactiva", icon=":material/monitoring:"),
]

st.navigation(paginas).run()
