"""
Página Streamlit: Fase Reactiva.

Permite subir un CSV de transacciones ya ejecutadas, dispararlo contra
fase_reactiva.modelo_deteccion + fase_reactiva.explicador_llm, y mostrar las
transacciones sospechosas junto con el reporte en lenguaje natural. Mientras
la lógica real (modelo + LLM) no esté implementada, se muestran datos de
ejemplo/mock para dejar el flujo navegable de punta a punta.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fase_reactiva import explicador_llm, modelo_deteccion  # noqa: E402

st.set_page_config(page_title="Fase Reactiva | Evaluación de Seguridad MS-SQL mediante IA", layout="wide")

st.title("Fase Reactiva")
st.caption("Sube un CSV de transacciones ya ejecutadas para detectar anomalías y generar un reporte.")
st.divider()

TRANSACCIONES_MOCK = pd.DataFrame(
    [
        {
            "timestamp": "2026-08-14T03:12:45",
            "usuario": "lsuarez",
            "rol": "Soporte",
            "ip_origen": "45.227.10.201",
            "ip_destino": "10.0.0.5",
            "aplicacion": "SSMS",
            "tabla_afectada": "Empleados",
            "columna_afectada": "salario",
            "tipo_operacion": "SELECT",
            "sentencia_sql": "SELECT salario FROM Empleados;",
            "score_anomalia": 0.92,
        },
        {
            "timestamp": "2026-08-20T23:47:10",
            "usuario": "dpaez",
            "rol": "Desarrollador",
            "ip_origen": "10.0.1.15",
            "ip_destino": "10.0.0.5",
            "aplicacion": "SSMS",
            "tabla_afectada": "Usuarios",
            "columna_afectada": "password_hash",
            "tipo_operacion": "UPDATE",
            "sentencia_sql": "UPDATE Usuarios SET password_hash = ? WHERE id_usuarios = ?;",
            "score_anomalia": 0.87,
        },
    ]
)

REPORTE_MOCK = {
    "criticidad_resumida": "Se identificaron 2 transacciones de criticidad alta sobre un total de 180 analizadas (1.1%).",
    "anomalias_identificadas": [
        "Acceso fuera de horario laboral (03:12 AM) a la columna salario por un usuario con rol Soporte.",
        "Actualización de password_hash desde una cuenta de desarrollador fuera del flujo habitual de la aplicación.",
    ],
    "explicacion_simplificada": (
        "Dos usuarios accedieron a información sensible en condiciones inusuales: uno consultó datos de "
        "salarios en plena madrugada y otro modificó credenciales de usuarios sin pasar por el aplicativo "
        "correspondiente. Se recomienda validar ambos casos con los usuarios involucrados y sus superiores."
    ),
}

col_upload, col_formato = st.columns([2, 1], gap="large")

with col_upload:
    st.markdown("##### Transacciones a evaluar")
    archivo_csv = st.file_uploader(
        "Sube el CSV de transacciones",
        type=["csv"],
        label_visibility="collapsed",
    )
    generar = st.button("Generar reporte", type="primary")

with col_formato:
    with st.container(border=True):
        st.markdown("##### Formato esperado")
        st.markdown("`usuario`, `ip_origen`, `ip_destino`, `aplicacion`, `sentencia_sql`, `timestamp`")

if generar:
    if archivo_csv is None:
        st.warning("Sube un archivo CSV antes de generar el reporte.")
    else:
        df_transacciones = pd.read_csv(archivo_csv)

        try:
            # TODO: una vez implementado el modelo real y persistido, cargarlo aquí
            # en lugar de entrenar en cada request.
            modelo = modelo_deteccion.entrenar_modelo(df_transacciones, catalogo_sensibles=None)
            df_evaluado = modelo_deteccion.predecir_anomalias(modelo, df_transacciones, catalogo_sensibles=None)
            df_sospechosas = df_evaluado[df_evaluado["es_anomalo_predicho"]]
            reporte = explicador_llm.generar_reporte(df_sospechosas)
        except (NotImplementedError, KeyError):
            st.info("Lógica de detección/reporte aún no implementada — mostrando resultado de ejemplo (mock).")
            df_sospechosas = TRANSACCIONES_MOCK
            reporte = REPORTE_MOCK

        st.divider()

        with st.container(border=True):
            st.markdown("### Transacciones sospechosas")
            st.caption(f"{len(df_sospechosas)} transacción(es) marcada(s) por el modelo de detección.")
            st.dataframe(df_sospechosas, use_container_width=True)

        st.markdown("&nbsp;", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("### Reporte en lenguaje natural")

            st.markdown("**Criticidad resumida**")
            st.write(reporte.get("criticidad_resumida", "—"))

            st.markdown("**Anomalías identificadas**")
            for anomalia in reporte.get("anomalias_identificadas", []):
                st.markdown(f"- {anomalia}")

            st.markdown("**Explicación simplificada**")
            st.write(reporte.get("explicacion_simplificada", "—"))
