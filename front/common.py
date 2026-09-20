"""
Utilidades compartidas por las páginas Streamlit: configuración de página,
tokens visuales, CSS y componentes de presentación.
"""

from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "assets"

LOGO = str(ASSETS / "logo_eci_blanco.png")
MARCA = str(ASSETS / "logo_eci_marca.png")
FAVICON = str(ASSETS / "favicon_eci.png")

CATALOGO_SENSIBLES = RAIZ / "catalogo_activos" / "objetos_sensibles.csv"

FONDO = "#0F1620"
SUPERFICIE = "#1B2530"
ACENTO = "#3E7CB1"
TEXTO = "#E4E8EE"
TEXTO_SUAVE = "#9AA5B1"
HAIRLINE = "rgba(228, 232, 238, 0.12)"

RIEL = 68
ANCHO_BARRA = 215

SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500"]

RIESGO = {
    "bajo": {"color": "#0ca30c", "forma": "●", "etiqueta": "BAJO"},
    "medio": {"color": "#fab219", "forma": "◆", "etiqueta": "MEDIO"},
    "alto": {"color": "#ec835a", "forma": "▲", "etiqueta": "ALTO"},
    "critico": {"color": "#d03b3b", "forma": "✖", "etiqueta": "CRÍTICO"},
}

_CSS = f"""
<style>
  .app-subtitle {{
      color: {TEXTO_SUAVE};
      font-size: 1.05rem;
      margin-top: -0.6rem;
  }}
  .eci-tag {{
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.09em;
      padding: 0.18rem 0.6rem;
      border-radius: 4px;
      margin-bottom: 0.6rem;
      background-color: rgba(62, 124, 177, 0.18);
      color: #7FB2DE;
      border: 1px solid rgba(62, 124, 177, 0.35);
  }}
  .eci-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      padding: 0.3rem 0.7rem;
      border-radius: 6px;
  }}
  .eci-mock {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      font-size: 0.74rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      padding: 0.22rem 0.62rem;
      border-radius: 4px;
      color: #C9B458;
      background-color: rgba(250, 178, 25, 0.12);
      border: 1px solid rgba(250, 178, 25, 0.38);
  }}
  .eci-pie {{
      color: {TEXTO_SUAVE};
      font-size: 0.8rem;
      border-top: 1px solid {HAIRLINE};
      padding-top: 0.9rem;
      margin-top: 2rem;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"] {{
      border-radius: 8px;
  }}
  div[data-testid="stMetric"] {{
      background-color: {SUPERFICIE};
      border: 1px solid {HAIRLINE};
      border-radius: 8px;
      padding: 0.85rem 1rem;
  }}
  div[data-testid="stMetricLabel"] p {{
      font-size: 0.78rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: {TEXTO_SUAVE};
  }}

  section[data-testid="stSidebar"][aria-expanded="true"] {{
      width: {ANCHO_BARRA}px !important;
      min-width: {ANCHO_BARRA}px !important;
      max-width: {ANCHO_BARRA}px !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
      padding: 0.6rem 0.75rem 0.2rem 0.75rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
      padding-top: 0.2rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] {{
      padding-top: 0;
      padding-bottom: 0;
      gap: 0.1rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
      padding-top: 0.35rem;
      padding-bottom: 0.35rem;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
      padding-bottom: 0;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"] {{
      display: none !important;
  }}

  section[data-testid="stSidebar"][aria-expanded="false"] {{
      width: {RIEL}px !important;
      min-width: {RIEL}px !important;
      max-width: {RIEL}px !important;
      transform: none !important;
      visibility: visible !important;
      border-right: 1px solid {HAIRLINE};
  }}
  section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"] {{
      overflow-x: hidden;
  }}
  section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] {{
      justify-content: center;
      padding-left: 0;
      padding-right: 0;
      gap: 0;
  }}
  section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] > *:last-child {{
      display: none !important;
  }}
  section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarUserContent"] {{
      display: none !important;
  }}
  [data-testid="stExpandSidebarButton"] {{
      margin-left: {RIEL}px;
  }}
</style>
"""

def configurar_app() -> None:
    """Configura la página, pinta el logo e inyecta el CSS. Solo en el entrypoint."""
    st.set_page_config(
        page_title="Evaluación de Seguridad MS-SQL mediante IA",
        page_icon=FAVICON,
        layout="wide",
    )
    if hasattr(st, "logo"):
        st.logo(LOGO, icon_image=MARCA, size="medium")
    st.markdown(_CSS, unsafe_allow_html=True)

def badge_riesgo(nivel: str) -> str:
    """HTML de un badge de riesgo."""
    datos = RIESGO.get(str(nivel).strip().lower(), RIESGO["medio"])
    return (
        f'<span class="eci-badge" style="color:{datos["color"]};'
        f'background-color:{datos["color"]}22;'
        f'border:1px solid {datos["color"]}66;">'
        f'{datos["forma"]} {datos["etiqueta"]}</span>'
    )

def tag(texto: str) -> str:
    """HTML de una etiqueta de sección (ej. el rótulo de fase)."""
    return f'<span class="eci-tag">{texto}</span>'

def badge_mock() -> str:
    """Aviso de que lo que se muestra es un resultado de ejemplo."""
    return '<span class="eci-mock">◇ DATOS DE EJEMPLO</span>'

def encabezado(titulo: str, subtitulo: str) -> None:
    """Encabezado de página: logo a la izquierda, título y bajada a la derecha."""
    col_logo, col_texto = st.columns([1, 4], vertical_alignment="center")
    with col_logo:
        st.image(LOGO, width="stretch")
    with col_texto:
        st.title(titulo)
        st.markdown(f'<p class="app-subtitle">{subtitulo}</p>', unsafe_allow_html=True)

def pie() -> None:
    """Pie institucional, igual en todas las páginas."""
    st.markdown(
        '<p class="eci-pie">Escuela Colombiana de Ingeniería Julio Garavito · '
        "Proyecto universitario — prototipo en desarrollo.</p>",
        unsafe_allow_html=True,
    )
