# Evaluación de Seguridad en sentencias Microsoft SQL Server (MS-SQL) mediante IA

Sistema de evaluación de seguridad en ejecuciones MS-SQL mediante IA, con dos fases complementarias:

1. **Fase proactiva**: analiza un script SQL *antes* de ejecutarse. Parsea cada sentencia con `sqlglot`, la contrasta contra el catálogo de objetos sensibles y el rol del usuario, y un motor de reglas determinista (matriz de riesgo + hallazgos) calcula el nivel de riesgo y el escalamiento. La explicación y la mitigación en lenguaje natural se redactan con plantillas a partir de esa evaluación.
2. **Fase reactiva**: analiza en lote transacciones *ya ejecutadas* (CSV con usuario, IPs, aplicación, sentencia y timestamp). Un modelo de clasificación (regresión logística, scikit-learn) entrenado sobre el dataset sintético detecta anomalías, y un reporte por plantillas traduce los resultados a lenguaje natural.

> El análisis en ambas fases se resuelve con reglas de negocio deterministas y plantillas, sin depender de una API externa — es una decisión de alcance del proyecto, no una funcionalidad pendiente. El diseño queda abierto a integrar un LLM a futuro (ver `construir_prompt` en `fase_proactiva/analizador_llm.py` y `construir_prompt_reporte` en `fase_reactiva/explicador_llm.py`).

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

## Datos sintéticos (fase reactiva)

```bash
python fase_reactiva/generar_dataset.py                     # 5000 filas de entrenamiento + lote demo de 400
python fase_reactiva/generar_dataset.py --filas 20000 --anomalias 0.08 --semilla 7
```

Genera en `fase_reactiva/datos/`:

- `transacciones_sinteticas.csv`: dataset etiquetado (`es_anomalo`, `tipo_anomalia`) para entrenar. `tipo_anomalia` es solo ground truth; no debe usarse como feature.
- `transacciones_demo.csv`: lote sin etiquetas con otra semilla, para subir en la página de Fase Reactiva.

## Modelo de detección de anomalías (fase reactiva)

```bash
python fase_reactiva/modelo_deteccion.py
```

Entrena una regresión logística (`scikit-learn`, `class_weight="balanced"`) sobre `transacciones_sinteticas.csv` y guarda el pipeline completo (preprocesamiento + modelo) en `fase_reactiva/datos/modelo_deteccion.joblib`. Imprime en consola el reporte de clasificación (precisión, recall, F1) y la matriz de confusión sobre un split de prueba del 20%. Mientras este archivo no exista, la página de Fase Reactiva muestra un resultado de ejemplo.

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
- [x] Modelo de detección de anomalías (`fase_reactiva/modelo_deteccion.py`)
- [x] Explicación en lenguaje natural (plantillas) en ambas fases — sin dependencia de API externa, por decisión de alcance del proyecto.

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

- Ninguno para el alcance actual. La integración de un LLM para redactar las explicaciones (en lugar de las plantillas) queda como extensión futura fuera de alcance.

### Adelanto — 7 de octubre de 2026

**Decisión de alcance: explicación por plantillas, sin LLM externo**

- La explicación de la fase proactiva (ya resuelta por `motor_reglas.explicar_evaluacion`) y el nuevo reporte de la fase reactiva (`fase_reactiva/explicador_llm.generar_reporte`) se dejan como la implementación final de esta entrega: reglas de negocio deterministas + plantillas, sin llamar a una API externa.
- Se retiraron `anthropic` y `python-dotenv` de `requirements.txt` (no se usaban en ningún import) y el código muerto relacionado (`ANTHROPIC_API_KEY = os.getenv(...)`) de `analizador_llm.py`. Los hooks de extensión (`construir_prompt`, `construir_prompt_reporte`) se conservan documentados para una futura integración de LLM, fuera del alcance actual.

**Fase reactiva: modelo de detección de anomalías** (`fase_reactiva/modelo_deteccion.py`)

- `construir_features` deriva, por transacción: hora del día y día de la semana, si cae fuera del horario habitual del usuario, si la aplicación es la habitual, si la IP de origen es externa, la sensibilidad del objeto tocado y si el rol está autorizado sobre él (cruce contra `catalogo_activos`), y `filas_afectadas` en escala logarítmica; además de las categóricas tipo de operación, tabla, aplicación y rol. `tipo_anomalia` nunca se usa como feature.
- `entrenar_modelo` arma un `Pipeline` de scikit-learn (`OneHotEncoder` + `StandardScaler` + `LogisticRegression` con `class_weight="balanced"`), evalúa con un split 80/20 estratificado por `es_anomalo` e imprime precisión/recall/F1 y la matriz de confusión. El pipeline completo se persiste con `joblib` en `fase_reactiva/datos/modelo_deteccion.joblib`.
- `cargar_modelo` retorna `None` si el modelo no se ha entrenado (en vez de lanzar una excepción), y `predecir` aplica el mismo preprocesamiento a transacciones nuevas y agrega `es_anomalo_predicho` y `probabilidad_anomalia`.
- Con el dataset de 5000 filas (`--semilla` por defecto) el modelo da precisión, recall y F1 de 1.000 tanto en el split de prueba (1000 filas) como en un lote de 3000 filas generado con una semilla completamente distinta (777), sin falsos positivos ni falsos negativos. **Por qué es perfecto y no una señal de fuga de datos:** cada patrón de anomalía en `generar_dataset.py` se genera a partir de una regla de negocio exacta (rol no autorizado sobre la tabla/columna, hora fuera del horario del perfil, IP fuera de los rangos internos/VPN, operación que ningún rol tiene habitual, volumen de filas muy por fuera del rango normal), y `construir_features` deriva esas mismas señales de negocio. El dataset es, por diseño, linealmente separable con esas features. Con datos reales (con ruido, perfiles desactualizados y comportamiento humano menos consistente) es esperable que las métricas bajen; el valor de esta prueba es confirmar que el pipeline de features captura las señales correctas, no que el modelo sea infalible.

**Front (Streamlit)**

- Fase reactiva: ahora llama a `modelo_deteccion.predecir` (ya no al antiguo `predecir_anomalias`) y usa `probabilidad_anomalia` en vez de `score_anomalia` en la tabla, el gráfico y los badges de nivel. Si `cargar_modelo()` devuelve `None`, se muestra el resultado de ejemplo sin pasar por manejo de excepciones.

**Pruebas**

- Nuevas pruebas en `tests/test_modelo_deteccion.py`: el modelo se entrena y persiste sin error, `predecir` devuelve las columnas esperadas con valores en rango, y `cargar_modelo` retorna `None` cuando el archivo no existe.
