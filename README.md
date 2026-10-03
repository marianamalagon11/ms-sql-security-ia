# Evaluación de Seguridad en sentencias Microsoft SQL Server (MS-SQL) mediante IA

Sistema de evaluación de seguridad en ejecuciones MS-SQL mediante IA, con dos fases complementarias:

1. **Fase proactiva**: analiza un script SQL *antes* de ejecutarse. Parsea cada sentencia con `sqlglot`, la contrasta contra el catálogo de objetos sensibles y el rol del usuario, y un motor de reglas determinista (matriz de riesgo + hallazgos) calcula el nivel de riesgo y el escalamiento. El LLM (Claude) solo redacta la explicación y la mitigación; mientras no haya API key se usa una explicación por plantillas.
2. **Fase reactiva**: analiza en lote transacciones *ya ejecutadas* (CSV con usuario, IPs, aplicación, sentencia y timestamp). Un modelo de clasificación (regresión logística, scikit-learn) detecta anomalías y un LLM traduce los resultados a un reporte en lenguaje natural.

Ambas fases comparten el catálogo de `catalogo_activos/`:

| Archivo | Contenido |
|---|---|
| `objetos_sensibles.csv` | Tablas/columnas sensibles, nivel de sensibilidad y roles autorizados (separados por `\|`) |
| `perfiles.csv` | Usuarios, rol, aplicaciones habituales y horario laboral |
| `listas_blancas.csv` | Redes internas/VPN, aplicaciones y servidores permitidos |
| `matriz_riesgo.csv` | Nivel de riesgo base: categoría de operación × sensibilidad |
| `matriz_escalamiento.csv` | Escalamiento, responsable y acción por nivel de riesgo |

### Cómo se calcula el riesgo (fase proactiva)

1. Cada sentencia se clasifica en una categoría (LECTURA, ESCRITURA, ELIMINACION, DDL, PRIVILEGIOS, EJECUCION, CONTROL).
2. Sus tablas/columnas se cruzan con el catálogo → sensibilidad máxima afectada.
3. `matriz_riesgo.csv` da el nivel base.
4. Los hallazgos lo ajustan: `ROL_NO_AUTORIZADO`, `SIN_WHERE`, `EXPOSICION_MASIVA`, `COPIA_DATOS` suben un nivel; `POSIBLE_INYECCION`, `SQL_DINAMICO`, `ACCESO_REMOTO` imponen mínimo alto; `COMANDO_PELIGROSO` (xp_cmdshell, sp_configure…) y `OBJETO_SERVIDOR` (LOGIN, DATABASE…) imponen crítico.
5. El script toma el nivel de su sentencia más riesgosa y `matriz_escalamiento.csv` define el escalamiento.

## Estructura del proyecto

```
ms-sql-security-ia/
├── catalogo_activos/       # Catálogo compartido: objetos sensibles, perfiles, listas blancas y matrices
├── fase_proactiva/         # Parser SQL (sqlglot), motor de reglas y análisis pre-ejecución
├── fase_reactiva/          # Generación de dataset sintético, modelo de detección de anomalías y explicación vía LLM
│   └── datos/              # CSVs generados dinámicamente (no versionados)
├── front/                  # Aplicación Streamlit
│   ├── app.py               # Página principal / menú
│   └── pages/                # Página Fase Proactiva y página Fase Reactiva
├── tests/                  # Pruebas (pytest)
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

## Datos sintéticos (fase reactiva)

```bash
python fase_reactiva/generar_dataset.py                     # 5000 filas de entrenamiento + lote demo de 400
python fase_reactiva/generar_dataset.py --filas 20000 --anomalias 0.08 --semilla 7
```

Genera en `fase_reactiva/datos/`:

- `transacciones_sinteticas.csv`: dataset etiquetado (`es_anomalo`, `tipo_anomalia`) para entrenar. `tipo_anomalia` es solo ground truth; no debe usarse como feature.
- `transacciones_demo.csv`: lote sin etiquetas con otra semilla, para subir en la página de Fase Reactiva.

## Cómo correr el front

```bash
streamlit run front/app.py
```

## Pruebas

```bash
python -m pytest
```

## Equipo

Proyecto desarrollado para la Escuela Colombiana de Ingeniería Julio Garavito:

- Juliana Briceño
- Mariana Malagón
- Jimmy Mancera

El estado del arte, la justificación del proyecto y el diagrama de arquitectura están documentados en [`docs/`](docs/).

## Estado actual

**Prototipo en desarrollo.**

- [x] Parser T-SQL (`fase_proactiva/parser_sql.py`)
- [x] Motor de reglas, matriz de riesgo y matriz de escalamiento (`fase_proactiva/motor_reglas.py`)
- [x] Generador de dataset sintético (`fase_reactiva/generar_dataset.py`)
- [ ] Integración con el LLM (explicación de la fase proactiva y reporte de la reactiva)
- [ ] Modelo de detección de anomalías (`fase_reactiva/modelo_deteccion.py`)

## Bitácora de avances

### Adelanto — 3 de octubre de 2026

**Fase proactiva: parser T-SQL** (`fase_proactiva/parser_sql.py`)

- Divide scripts con varias sentencias (separadas por `;` o `GO`) respetando strings y comentarios; un error en una sentencia no detiene el análisis de las demás.
- Extrae tipo de operación, tablas y columnas, resolviendo alias (`UPDATE e ... FROM Empleados e`), esquemas (`dbo.`) y CTEs.
- Detecta señales estructurales: `UPDATE`/`DELETE` sin `WHERE`, `TOP`, `SELECT *`, consultas solo con agregados, `SELECT INTO` / `INSERT ... SELECT`, procedimientos invocados con `EXEC` y tautologías tipo `OR 1=1`.
- Parser de respaldo por expresiones regulares para la sintaxis que sqlglot no soporta (`DENY`, `WAITFOR`, `ALTER LOGIN`, `DELETE TOP (n)`); esas sentencias se evalúan de forma conservadora.

**Fase proactiva: motor de reglas y escalamiento** (`fase_proactiva/motor_reglas.py`)

- Implementa los bloques "Matriz de sensibilidad y criticidad", "Evaluación de impacto" y "Evaluación de escalamiento" del diagrama de arquitectura.
- El nivel de riesgo (bajo, medio, alto, crítico) se calcula de forma determinista y auditable a partir de la matriz de riesgo, el rol del usuario y los hallazgos (ver [Cómo se calcula el riesgo](#cómo-se-calcula-el-riesgo-fase-proactiva)).
- Evaluación de impacto por sentencia: dimensión comprometida (confidencialidad, integridad, disponibilidad) y alcance (filtrado, masivo, estructural).
- Escalamiento N0–N3 con responsable y acción según `matriz_escalamiento.csv`.
- Explicación y mitigación en lenguaje natural generadas con plantillas; el LLM solo las redactará mejor cuando se integre, sin cambiar el nivel de riesgo.
- `analizador_llm.analizar_riesgo` ya devuelve resultados reales usando el motor.

**Catálogo compartido** (`catalogo_activos/`)

- Nuevos archivos: `perfiles.csv` (15 usuarios con rol, horario y aplicaciones habituales), `listas_blancas.csv`, `matriz_riesgo.csv` y `matriz_escalamiento.csv`, además de un módulo de carga (`catalogo_activos/__init__.py`).
- `objetos_sensibles.csv` ahora admite varios roles autorizados por columna (`DBA|Servicio_App`). Por segregación de funciones, el DBA no está autorizado sobre salarios ni cuentas bancarias.

**Fase reactiva: dataset sintético** (`fase_reactiva/generar_dataset.py`)

- Pasa de 180 a 5000 filas de entrenamiento (configurable con `--filas`, `--anomalias` y `--semilla`), más un lote de demo de 400 filas sin etiquetas para subir en el front.
- Las transacciones normales respetan los perfiles: horario, aplicaciones, tablas habituales del rol y permisos sobre columnas sensibles. Esto corrige las etiquetas inconsistentes de la versión anterior.
- 8 patrones de anomalía (fuera de horario, IP externa, acceso no autorizado, exfiltración masiva, operación destructiva, escalamiento de privilegios, aplicación no habitual y comando peligroso), con un 30% de anomalías que combinan dos señales.
- Casos normales "difíciles" (VPN, procesos batch nocturnos, reportes grandes, mantenimiento de DBAs) para que el modelo no aprenda reglas triviales.
- Nuevas columnas `filas_afectadas` y `tipo_anomalia` (esta última es solo ground truth).

**Front (Streamlit)**

- Fase proactiva: usa el catálogo real en lugar del mock, tiene selector de usuario/rol (el nivel cambia según el rol), selector con 12 ejemplos de sentencias, badge de riesgo con escalamiento y una tabla de detalle por sentencia.
- Fase reactiva: se corrigió un bug por el que entrenaba el modelo con el CSV subido, que no trae etiquetas. Ahora carga un modelo ya entrenado (`modelo_deteccion.cargar_modelo`) y le pasa el catálogo real; mientras el modelo no exista se sigue mostrando el ejemplo.
- Inicio: el número de objetos sensibles se calcula desde el catálogo.

**Pruebas**

- 26 pruebas con pytest (`tests/`) para el parser, el motor de reglas (incluye verificar que los ejemplos den el nivel esperado) y el generador de datos.

**Pendiente**

- Integrar el LLM (requiere API key de Anthropic) para la explicación de la fase proactiva y el reporte de la reactiva.
- Implementar y entrenar el modelo de detección de anomalías.
