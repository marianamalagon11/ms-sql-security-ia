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
            "nivel": "critico",
            "motivo": (
                "Ocurrió a las 03:12, fuera del horario habitual de esta persona; "
                "se conectó desde una red ajena a la organización (IP 45.227.10.201)."
            ),
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
            "nivel": "critico",
            "motivo": "Su rol (Desarrollador) no está autorizado para acceder a esa información.",
        },
    ]
)

TOTAL_MOCK = 180

DETALLE_POR_PAGINA = 10


def _ir_a_pagina(pagina: int) -> None:
    st.session_state["reactiva_pagina_detalle"] = pagina


REPORTE_MOCK = {
    "resumen": (
        "Se marcaron 2 transacciones sospechosas de 2 usuarios distintos. La señal más frecuente es el "
        "acceso de roles no autorizados (1 caso)."
    ),
    "patrones": [
        "Acceso de un rol no autorizado: 1 transacción.",
        "Conexión desde una red externa: 1 transacción.",
        "Fuera del horario habitual del usuario: 1 transacción.",
    ],
    "usuarios_destacados": [],
    "anomalias_identificadas": [
        "**lsuarez** consultó los salarios en la tabla de empleados. Llama la atención porque ocurrió a las 03:12, "
        "fuera del horario habitual de esta persona y se conectó desde una red ajena a la organización (IP 45.227.10.201).",
        "**dpaez** modificó las contraseñas en la tabla de usuarios. Llama la atención porque su rol (Desarrollador) "
        "no está autorizado para acceder a esa información.",
    ],
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
                    df_sospechosas = explicador_llm.detallar_transacciones(
                        df_evaluado[df_evaluado["es_anomalo_predicho"]]
                    )
                    reporte = explicador_llm.generar_reporte(df_sospechosas)
                    total_analizadas = len(df_transacciones)
                    es_mock = False
                except KeyError as exc:
                    # El modelo sí existe: el problema es el archivo. No se muestra el ejemplo
                    # para no hacer pasar datos inventados por un resultado del CSV.
                    for clave in [k for k in st.session_state if k.startswith("reactiva_")]:
                        del st.session_state[clave]
                    columnas = ", ".join(f"`{c}`" for c in faltantes) if faltantes else f"`{exc.args[0]}`"
                    st.error(
                        f"No se pudo evaluar el archivo: le faltan columnas que el modelo necesita ({columnas}). "
                        "Revisa el formato esperado e inténtalo de nuevo.",
                        icon=":material/error:",
                    )
                    st.stop()

        st.session_state["reactiva_sospechosas"] = df_sospechosas
        st.session_state["reactiva_reporte"] = reporte
        st.session_state["reactiva_total"] = total_analizadas
        st.session_state["reactiva_es_mock"] = es_mock
        st.session_state["reactiva_filas_csv"] = len(df_transacciones)
        st.session_state["reactiva_faltantes"] = faltantes
        st.session_state["reactiva_pagina_detalle"] = 0
        st.session_state.pop("reactiva_filtro_detalle", None)

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

    # Barra delgada bajo las sospechosas: cómo se reparten por nivel de riesgo.
    k2.markdown(common.barra_niveles(df_sospechosas["nivel"].value_counts().to_dict()), unsafe_allow_html=True)

    st.markdown("")

    with st.container(border=True):
        st.markdown("##### Transacciones sospechosas")
        st.caption(
            f"{sospechosas} {'transacción marcada' if sospechosas == 1 else 'transacciones marcadas'} "
            "por el modelo de detección, de la más a la menos grave."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Nivel": df_sospechosas["nivel"].map(
                        lambda n: f"{common.RIESGO[n]['forma']} {common.RIESGO[n]['etiqueta']}"
                    ),
                    "Fecha": pd.to_datetime(df_sospechosas["timestamp"]).dt.strftime("%d/%m/%Y %H:%M"),
                    "Usuario": df_sospechosas["usuario"],
                    "Rol": df_sospechosas["rol"],
                    "Operación": df_sospechosas["tipo_operacion"],
                    "Objeto": [
                        # Sin columna concreta (vacía o "*") se muestra solo la tabla.
                        f"{tabla}.{columna}" if pd.notna(columna) and columna not in {"", "-", "*"} else tabla
                        for tabla, columna in zip(df_sospechosas["tabla_afectada"], df_sospechosas["columna_afectada"])
                    ],
                    "Motivo": df_sospechosas["motivo"],
                    "IP de origen": df_sospechosas["ip_origen"],
                    "Aplicación": df_sospechosas["aplicacion"],
                    "Confianza del modelo": df_sospechosas["probabilidad_anomalia"] * 100,
                    "Sentencia SQL": df_sospechosas["sentencia_sql"],
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Motivo": st.column_config.TextColumn(width="large"),
                "Confianza del modelo": st.column_config.ProgressColumn(
                    min_value=0,
                    max_value=100,
                    format="%.0f%%",
                    help="Qué tan seguro está el modelo de que la transacción es anómala. No mide la gravedad: esa la indica el Nivel.",
                ),
            },
        )
        st.download_button(
            "Descargar transacciones sospechosas (CSV)",
            data=df_sospechosas.drop(columns=["es_anomalo_predicho"], errors="ignore")
            .to_csv(index=False)
            .encode("utf-8-sig"),
            file_name="transacciones_sospechosas.csv",
            mime="text/csv",
            icon=":material/download:",
            type="primary",
        )

    with st.container(border=True):
        st.markdown("##### Reporte en lenguaje natural")

        st.markdown("**Resumen ejecutivo**")
        st.write(reporte.get("resumen", "—"))

        def _lista(titulo: str, elementos: list[str]) -> None:
            if elementos:
                st.markdown(f"**{titulo}**")
                st.markdown("\n".join(f"- {e}" for e in elementos))

        col_patrones, col_usuarios = st.columns(2, gap="medium")
        with col_patrones:
            _lista("Patrones detectados", reporte.get("patrones", []))
        with col_usuarios:
            _lista("Usuarios con más alertas", reporte.get("usuarios_destacados", []))

        anomalias = reporte.get("anomalias_identificadas", [])
        if anomalias:
            # Las frases vienen en el mismo orden que df_sospechosas (de la más a la menos grave),
            # así que cada una toma su nivel y fecha de la fila correspondiente.
            detalle = list(
                zip(
                    df_sospechosas["nivel"],
                    pd.to_datetime(df_sospechosas["timestamp"]).dt.strftime("%d/%m/%Y %H:%M"),
                    anomalias,
                )
            )
            por_nivel = df_sospechosas["nivel"].value_counts()

            etiqueta = (
                "Ver detalle de la transacción"
                if len(detalle) == 1
                else f"Ver detalle de las {len(detalle)} transacciones"
            )
            with st.expander(etiqueta):
                # Acceso rápido: filtra el detalle por nivel; "Todos" muestra el lote completo.
                opciones = ["todos"] + [n for n in ["critico", "alto", "medio", "bajo"] if n in por_nivel]
                filtro = st.pills(
                    "Mostrar",
                    opciones,
                    default="todos",
                    key="reactiva_filtro_detalle",
                    on_change=_ir_a_pagina,
                    args=(0,),
                    format_func=lambda n: (
                        f"Todos ({len(detalle)})"
                        if n == "todos"
                        else f"{common.RIESGO[n]['forma']} {common.RIESGO[n]['etiqueta'].capitalize()} ({por_nivel[n]})"
                    ),
                    label_visibility="collapsed",
                ) or "todos"
                filtrado = detalle if filtro == "todos" else [d for d in detalle if d[0] == filtro]

                paginas = -(-len(filtrado) // DETALLE_POR_PAGINA)
                pagina = min(st.session_state.get("reactiva_pagina_detalle", 0), paginas - 1)
                inicio = pagina * DETALLE_POR_PAGINA
                visibles = filtrado[inicio : inicio + DETALLE_POR_PAGINA]
                for nivel in dict.fromkeys(n for n, _, _ in visibles):
                    n_nivel = int(por_nivel[nivel])
                    st.markdown(
                        f"{common.badge_riesgo(nivel)}&nbsp; "
                        f"{n_nivel} {'transacción' if n_nivel == 1 else 'transacciones'} en total",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        "".join(common.item_detalle(n, fecha, texto) for n, fecha, texto in visibles if n == nivel),
                        unsafe_allow_html=True,
                    )

                if paginas > 1:
                    col_ant, col_pos, col_sig = st.columns([1, 2, 1], vertical_alignment="center")
                    col_ant.button(
                        "‹ Anterior",
                        key="detalle_anterior",
                        disabled=pagina == 0,
                        on_click=_ir_a_pagina,
                        args=(pagina - 1,),
                        width="stretch",
                    )
                    col_pos.markdown(
                        f'<p style="text-align:center;margin:0;color:{common.TEXTO_SUAVE};">'
                        f"Página {pagina + 1} de {paginas} · transacciones {inicio + 1}–{inicio + len(visibles)} "
                        f"de {len(filtrado)}</p>",
                        unsafe_allow_html=True,
                    )
                    col_sig.button(
                        "Siguiente ›",
                        key="detalle_siguiente",
                        disabled=pagina >= paginas - 1,
                        on_click=_ir_a_pagina,
                        args=(pagina + 1,),
                        width="stretch",
                    )

common.pie()
