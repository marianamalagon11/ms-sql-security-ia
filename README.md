# Evaluación de Seguridad en sentencias Microsoft SQL Server (MS-SQL) mediante IA

Sistema de evaluación de seguridad en ejecuciones MS-SQL mediante IA, con dos fases complementarias:

1. **Fase proactiva**: analiza un script SQL *antes* de ejecutarse. Parsea la sentencia con `sqlglot`, la contrasta contra un catálogo de objetos sensibles y permisos por rol, y usa un LLM (Claude) para generar nivel de riesgo, explicación en lenguaje natural y sugerencia de mitigación.
2. **Fase reactiva**: analiza en lote transacciones *ya ejecutadas* (CSV con usuario, IPs, aplicación, sentencia y timestamp). Un modelo de clasificación (regresión logística, scikit-learn) detecta anomalías y un LLM traduce los resultados a un reporte en lenguaje natural.

Ambas fases comparten el catálogo de objetos sensibles (tablas/columnas críticas y roles autorizados).

## Estructura del proyecto

```
ms-sql-security-ia/
├── catalogo_activos/       # Catálogo compartido: objetos sensibles y permisos por rol
├── fase_proactiva/         # Parser SQL (sqlglot) + análisis pre-ejecución vía LLM
├── fase_reactiva/          # Generación de dataset sintético, modelo de detección de anomalías y explicación vía LLM
│   └── datos/              # CSVs generados dinámicamente (no versionados)
├── front/                  # Aplicación Streamlit
│   ├── app.py               # Página principal / menú
│   └── pages/                # Página Fase Proactiva y página Fase Reactiva
├── docs/                   # Documentación del proyecto (paper, diagramas, etc.)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y agrega tu API key de Anthropic:

```bash
cp .env.example .env
```

## Cómo correr el front

```bash
streamlit run front/app.py
```

## Equipo

Proyecto desarrollado para la Escuela Colombiana de Ingeniería Julio Garavito:

- Juliana Briceño
- Mariana Malagón
- Jimmy Mancera

El estado del arte, la justificación del proyecto y el diagrama de arquitectura están documentados en [`docs/`](docs/).

## Estado actual

**Prototipo en desarrollo.** Actualmente se cuenta con la estructura base y los esqueletos de las funciones principales; la lógica de análisis (parser, modelo de detección, integración con el LLM) se está implementando de forma incremental.
