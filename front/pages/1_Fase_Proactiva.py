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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fase_proactiva import analizador_llm  # noqa: E402

st.set_page_config(page_title="Fase Proactiva | Evaluación de Seguridad MS-SQL mediante IA", layout="wide")

st.title("Fase Proactiva")
st.caption("Analiza un script SQL antes de su ejecución e identifica riesgos de seguridad.")
st.divider()

# TODO: reemplazar por el contexto real del usuario autenticado
CONTEXTO_USUARIO_MOCK = {"usuario": "jperez", "rol": "Soporte"}

# TODO: cargar el catálogo real desde catalogo_activos/objetos_sensibles.csv
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

# Paleta de riesgo: versiones atenuadas (no los rojo/naranja/verde saturados por defecto)
# para mantener coherencia con el tema oscuro y sobrio de la app.
RIESGO_ESTILO = {
    "bajo": {"color": "#2F9E5B", "bg": "rgba(47, 158, 91, 0.14)", "label": "RIESGO BAJO"},
    "medio": {"color": "#D6A419", "bg": "rgba(214, 164, 25, 0.14)", "label": "RIESGO MEDIO"},
    "alto": {"color": "#C4453D", "bg": "rgba(196, 69, 61, 0.16)", "label": "RIESGO ALTO"},
}
ESTILO_DESCONOCIDO = {"color": "#8892A0", "bg": "rgba(136, 146, 160, 0.14)", "label": "RIESGO DESCONOCIDO"}

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
        try:
            # TODO: una vez implementada la lógica real, esta llamada reemplaza el mock.
            resultado = analizador_llm.analizar_riesgo(
                sentencia_sql, CONTEXTO_USUARIO_MOCK, CATALOGO_MOCK
            )
        except NotImplementedError:
            st.info("Lógica de análisis aún no implementada — mostrando resultado de ejemplo (mock).")
            resultado = RESULTADO_MOCK

        nivel = resultado.get("nivel_riesgo", "desconocido")
        estilo = RIESGO_ESTILO.get(nivel, ESTILO_DESCONOCIDO)

        st.divider()
        st.markdown("### Resultado del análisis")

        with st.container(border=True):
            st.markdown(
                f"""
                <div style="
                    display:inline-block;
                    padding: 0.3rem 0.9rem;
                    border-radius: 6px;
                    background-color: {estilo['bg']};
                    color: {estilo['color']};
                    font-weight: 700;
                    letter-spacing: 0.04em;
                    font-size: 0.85rem;
                    margin-bottom: 0.75rem;
                ">
                    {estilo['label']}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("**Explicación**")
            st.write(resultado.get("explicacion", "—"))

            st.markdown("**Sugerencia de mitigación**")
            st.write(resultado.get("sugerencia_mitigacion", "—"))

            if resultado.get("requiere_validacion_adicional"):
                st.warning("Esta sentencia requiere validación adicional antes de ejecutarse en producción.")
