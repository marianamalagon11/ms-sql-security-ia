"""
Página Streamlit: Fase Proactiva.

Permite pegar un script SQL, elegir el usuario que lo va a ejecutar y
evaluarlo con fase_proactiva.analizador_llm (parser + motor de reglas +
explicación). Muestra el veredicto global, el escalamiento y el detalle por
sentencia.
"""

import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402

sys.path.insert(0, str(common.RAIZ))

import catalogo_activos  # noqa: E402
from fase_proactiva import analizador_llm  # noqa: E402

RUTA_EJEMPLOS = common.RAIZ / "fase_proactiva" / "ejemplos_sentencias.sql"

common.encabezado(
    "Fase Proactiva",
    "Analiza un script SQL antes de su ejecución e identifica riesgos de seguridad.",
)
st.divider()


@st.cache_data
def cargar_ejemplos() -> dict[str, str]:
    """Bloques "-- @ejemplo: <descripción>" de ejemplos_sentencias.sql."""
    texto = RUTA_EJEMPLOS.read_text(encoding="utf-8")
    bloques = re.split(r"^--\s*@ejemplo:\s*(.+)$", texto, flags=re.MULTILINE)
    return {bloques[i].strip(): bloques[i + 1].strip() for i in range(1, len(bloques) - 1, 2)}


catalogo = catalogo_activos.cargar_objetos_sensibles()
perfiles = catalogo_activos.cargar_perfiles()
ejemplos = cargar_ejemplos()

if "proactiva_sql" not in st.session_state:
    st.session_state["proactiva_sql"] = ""


def _usar_ejemplo() -> None:
    elegido = st.session_state.get("proactiva_ejemplo")
    if elegido in ejemplos:
        st.session_state["proactiva_sql"] = ejemplos[elegido]


col_input, col_contexto = st.columns([2, 1], gap="large")

with col_input:
    st.markdown("##### Sentencia SQL")
    st.selectbox(
        "Cargar un ejemplo",
        list(ejemplos),
        index=None,
        placeholder="Cargar un ejemplo…",
        key="proactiva_ejemplo",
        on_change=_usar_ejemplo,
        label_visibility="collapsed",
    )
    sentencia_sql = st.text_area(
        "Pega aquí el script SQL a analizar",
        height=220,
        placeholder="SELECT numero_documento, tarjeta_credito FROM Clientes;",
        label_visibility="collapsed",
        key="proactiva_sql",
    )
    analizar = st.button("Analizar", type="primary")

with col_contexto:
    with st.container(border=True):
        st.markdown("##### Contexto de la evaluación")
        perfil = st.selectbox(
            "Usuario que ejecutará el script",
            perfiles,
            format_func=lambda p: f"{p['usuario']} · {p['rol']}",
        )
        st.markdown(f"**Rol:** {perfil['rol']}")
        autorizados = [f"{o['tabla']}.{o['columna']}" for o in catalogo if perfil["rol"] in o["roles_autorizados"]]
        st.markdown(
            f"**Autorizado sobre:** {', '.join(autorizados) if autorizados else 'ningún objeto sensible'}"
        )
        st.caption(f"Catálogo: {len(catalogo)} objetos sensibles cargados.")

if analizar:
    if not sentencia_sql.strip():
        st.warning("Pega una sentencia SQL antes de analizar.")
    else:
        contexto_usuario = {"usuario": perfil["usuario"], "rol": perfil["rol"]}
        with st.spinner("Analizando la sentencia…"):
            st.session_state["proactiva_resultado"] = analizador_llm.analizar_riesgo(
                sentencia_sql, contexto_usuario, catalogo
            )
            st.session_state["proactiva_contexto"] = contexto_usuario

if "proactiva_resultado" in st.session_state:
    resultado = st.session_state["proactiva_resultado"]
    contexto = st.session_state["proactiva_contexto"]
    evaluacion = resultado["evaluacion"]
    escalamiento = resultado["escalamiento"]

    st.divider()
    st.markdown("### Resultado del análisis")
    st.caption(
        f"Evaluado para {contexto['usuario']} (rol {contexto['rol']}). "
        + (
            "Explicación generada con plantillas a partir del motor de reglas (sin LLM)."
            if resultado["fuente_explicacion"] == "plantilla"
            else "Explicación redactada por el LLM a partir del motor de reglas."
        )
    )

    with st.container(border=True):
        col_badge, col_esc = st.columns([1, 3], vertical_alignment="center")
        col_badge.markdown(common.badge_riesgo(resultado["nivel_riesgo"]), unsafe_allow_html=True)
        col_esc.markdown(f"**{escalamiento['escalamiento']}** · responsable: {escalamiento['responsable']}")

        st.markdown("**Explicación**")
        st.write(resultado["explicacion"])

        st.markdown("**Sugerencia de mitigación**")
        st.write(resultado["sugerencia_mitigacion"])

        if resultado["requiere_validacion_adicional"]:
            st.warning(escalamiento["accion"])

    sentencias = evaluacion["sentencias"]
    if sentencias:
        with st.container(border=True):
            st.markdown("##### Detalle por sentencia")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "#": i + 1,
                            "Nivel": common.RIESGO[s["nivel_riesgo"]]["etiqueta"],
                            "Operación": s["tipo_operacion"],
                            "Categoría": s["categoria"],
                            "Tablas": ", ".join(s["tablas"]),
                            "Objetos sensibles": ", ".join(
                                f"{o['tabla']}.{o['columna']}" + ("" if o["autorizado"] else " ✖")
                                for o in s["objetos_sensibles"]
                            ),
                            "Hallazgos": ", ".join(h["codigo"] for h in s["hallazgos"]),
                            "Impacto": f"{', '.join(s['impacto']['dimensiones']) or '—'} · {s['impacto']['alcance']}",
                        }
                        for i, s in enumerate(sentencias)
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption("✖ = el rol no está autorizado sobre ese objeto.")

            no_parseadas = [i + 1 for i, s in enumerate(sentencias) if not s["parseado"]]
            if no_parseadas:
                st.info(
                    "Sentencias analizadas con el parser de respaldo (sintaxis no soportada por sqlglot): "
                    + ", ".join(map(str, no_parseadas))
                )

common.pie()
