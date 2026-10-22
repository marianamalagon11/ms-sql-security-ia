"""
Página Streamlit: Fase Reactiva.

Permite subir un CSV de transacciones ya ejecutadas, dispararlo contra
fase_reactiva.modelo_deteccion + fase_reactiva.explicador_llm, y mostrar las
transacciones sospechosas junto con el reporte en lenguaje natural (por
plantillas). Si el modelo todavía no se entrenó (python
fase_reactiva/modelo_deteccion.py) se muestra un resultado de ejemplo para
dejar el flujo navegable de punta a punta.
"""

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402

sys.path.insert(0, str(common.RAIZ))

common.encabezado(
    "Fase Reactiva",
    "Sube un CSV de transacciones ya ejecutadas para detectar anomalías y generar un reporte.",
)
st.divider()

COLUMNAS_ESPERADAS = [
    "timestamp",
    "usuario",
    "rol",
    "ip_origen",
    "ip_destino",
    "aplicacion",
    "tabla_afectada",
    "columna_afectada",
    "tipo_operacion",
    "sentencia_sql",
    "filas_afectadas",
]

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
            "probabilidad_anomalia": 0.92,
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
            "probabilidad_anomalia": 0.87,
        },
    ]
)

TOTAL_MOCK = 180

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

def nivel_por_score(probabilidad: float) -> str:
    """Traduce la probabilidad de anomalía del modelo a un nivel de riesgo discreto."""
    if probabilidad >= 0.85:
        return "critico"
    if probabilidad >= 0.7:
        return "alto"
    if probabilidad >= 0.4:
        return "medio"
    return "bajo"

def grafica_scores(df: pd.DataFrame) -> alt.Chart:
    """Barras horizontales de la probabilidad de anomalía, ordenadas de mayor a menor."""
    datos = df.copy()
    datos["etiqueta"] = datos["usuario"] + " · " + datos["tabla_afectada"] + "." + datos["columna_afectada"]
    datos["score_texto"] = datos["probabilidad_anomalia"].map(lambda v: f"{v:.2f}")

    base = alt.Chart(datos).encode(
        y=alt.Y("etiqueta:N", sort="-x", title=None,
                axis=alt.Axis(labelColor=common.TEXTO_SUAVE, labelFontSize=12, domain=False, ticks=False)),
        x=alt.X("probabilidad_anomalia:Q", title="Probabilidad de anomalía",
                scale=alt.Scale(domain=[0, 1]),
                axis=alt.Axis(labelColor=common.TEXTO_SUAVE, titleColor=common.TEXTO_SUAVE,
                              gridColor="rgba(228,232,238,0.10)", domainColor="rgba(228,232,238,0.20)",
                              tickColor="rgba(228,232,238,0.20)")),
        tooltip=[
            alt.Tooltip("usuario:N", title="Usuario"),
            alt.Tooltip("rol:N", title="Rol"),
            alt.Tooltip("tabla_afectada:N", title="Tabla"),
            alt.Tooltip("columna_afectada:N", title="Columna"),
            alt.Tooltip("tipo_operacion:N", title="Operación"),
            alt.Tooltip("probabilidad_anomalia:Q", title="Probabilidad", format=".2f"),
        ],
    )

    barras = base.mark_bar(color=common.SERIES[0], height=18, cornerRadiusEnd=4)
    etiquetas = base.mark_text(
        align="left", dx=6, color=common.TEXTO, fontSize=12, fontWeight="bold"
    ).encode(text="score_texto:N")

    return (barras + etiquetas).properties(height=max(90, 46 * len(datos))).configure_view(
        stroke=None
    ).configure(background="transparent")

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
        st.markdown(", ".join(f"`{c}`" for c in COLUMNAS_ESPERADAS))

if generar:
    if archivo_csv is None:
        st.warning("Sube un archivo CSV antes de generar el reporte.")
    else:
        try:
            df_transacciones = pd.read_csv(archivo_csv)
        except Exception as exc:
            st.error(f"No se pudo leer el CSV: {exc}")
            st.stop()

        faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df_transacciones.columns]

        from fase_reactiva import explicador_llm, modelo_deteccion

        with st.spinner("Detectando anomalías y redactando el reporte…"):
            # El modelo se entrena offline con el dataset sintético etiquetado
            # (python fase_reactiva/modelo_deteccion.py); el CSV subido no trae
            # la etiqueta es_anomalo, solo se evalúa con él.
            modelo = modelo_deteccion.cargar_modelo()
            if modelo is None:
                df_sospechosas = TRANSACCIONES_MOCK
                reporte = REPORTE_MOCK
                total_analizadas = TOTAL_MOCK
                es_mock = True
            else:
                try:
                    df_evaluado = modelo_deteccion.predecir(modelo, df_transacciones)
                    df_sospechosas = df_evaluado[df_evaluado["es_anomalo_predicho"]]
                    reporte = explicador_llm.generar_reporte(df_sospechosas)
                    total_analizadas = len(df_transacciones)
                    es_mock = False
                except KeyError:
                    df_sospechosas = TRANSACCIONES_MOCK
                    reporte = REPORTE_MOCK
                    total_analizadas = TOTAL_MOCK
                    es_mock = True

        st.session_state["reactiva_sospechosas"] = df_sospechosas
        st.session_state["reactiva_reporte"] = reporte
        st.session_state["reactiva_total"] = total_analizadas
        st.session_state["reactiva_es_mock"] = es_mock
        st.session_state["reactiva_filas_csv"] = len(df_transacciones)
        st.session_state["reactiva_faltantes"] = faltantes

if "reactiva_reporte" in st.session_state:
    df_sospechosas = st.session_state["reactiva_sospechosas"]
    reporte = st.session_state["reactiva_reporte"]
    total = st.session_state["reactiva_total"]
    es_mock = st.session_state["reactiva_es_mock"]

    st.divider()

    fila_titulo, fila_aviso = st.columns([3, 1], vertical_alignment="center")
    fila_titulo.markdown("### Resultado del análisis")
    if es_mock:
        fila_aviso.markdown(common.badge_mock(), unsafe_allow_html=True)

    if es_mock:
        st.caption(
            f"El modelo de detección todavía no se ha entrenado (python fase_reactiva/modelo_deteccion.py). "
            f"Tu archivo se leyó correctamente ({st.session_state['reactiva_filas_csv']} filas), pero lo que "
            f"ves abajo es un resultado de ejemplo fijo y no proviene de él."
        )

    if st.session_state.get("reactiva_faltantes"):
        st.warning(
            "Al CSV le faltan columnas que el modelo necesitará: "
            + ", ".join(f"`{c}`" for c in st.session_state["reactiva_faltantes"])
        )

    sospechosas = len(df_sospechosas)
    porcentaje = (sospechosas / total * 100) if total else 0.0

    k1, k2, k3 = st.columns(3, gap="medium")
    k1.metric("Transacciones analizadas", f"{total:,}".replace(",", "."))
    k2.metric("Sospechosas", sospechosas)
    k3.metric("Tasa de anomalía", f"{porcentaje:.1f}%")

    st.markdown("")

    col_grafica, col_niveles = st.columns([3, 1], gap="large")

    with col_grafica:
        with st.container(border=True):
            st.markdown("##### Probabilidad de anomalía por transacción")
            if "probabilidad_anomalia" in df_sospechosas.columns and not df_sospechosas.empty:
                st.altair_chart(grafica_scores(df_sospechosas), width="stretch")
            else:
                st.caption("El modelo no devolvió probabilidades para graficar.")

    with col_niveles:
        with st.container(border=True):
            st.markdown("##### Nivel")
            if "probabilidad_anomalia" in df_sospechosas.columns:
                for _, fila in df_sospechosas.iterrows():
                    st.markdown(
                        common.badge_riesgo(nivel_por_score(fila["probabilidad_anomalia"])),
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{fila['usuario']} · {fila['tabla_afectada']}")
            else:
                st.caption("Sin probabilidad disponible.")

    with st.container(border=True):
        st.markdown("##### Transacciones sospechosas")
        st.caption(f"{sospechosas} transacción(es) marcada(s) por el modelo de detección.")
        st.dataframe(df_sospechosas, width="stretch", hide_index=True)

    with st.container(border=True):
        st.markdown("##### Reporte en lenguaje natural")

        st.markdown("**Criticidad resumida**")
        st.write(reporte.get("criticidad_resumida", "—"))

        st.markdown("**Anomalías identificadas**")
        for anomalia in reporte.get("anomalias_identificadas", []):
            st.markdown(f"- {anomalia}")

        st.markdown("**Explicación simplificada**")
        st.write(reporte.get("explicacion_simplificada", "—"))

common.pie()
