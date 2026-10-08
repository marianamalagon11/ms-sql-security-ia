"""
Entrenamiento y uso de un modelo de regresión logística (scikit-learn) para
detectar transacciones anómalas sobre el dataset generado por
fase_reactiva.generar_dataset.

Features construidas a partir de las columnas crudas (ver construir_features):
hora del día y día de la semana (de timestamp), si la hora cae fuera del
horario habitual del usuario, si la aplicación es la habitual del usuario, si
la IP de origen es externa, la sensibilidad del objeto tocado y si el rol
está autorizado sobre él (según catalogo_activos), filas_afectadas (log) y
las categóricas tipo_operacion, tabla_afectada, aplicacion y rol.

`es_anomalo` es la etiqueta de entrenamiento; `tipo_anomalia` es solo ground
truth y nunca se usa como feature.

El pipeline (preprocesamiento + modelo) se persiste junto en un solo archivo
con joblib, así la codificación de categóricas usada en inferencia es
siempre la misma que la de entrenamiento.
"""

import ipaddress
import math
import os
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalogo_activos  # noqa: E402

RUTA_DATASET = os.path.join(os.path.dirname(__file__), "datos", "transacciones_sinteticas.csv")
RUTA_MODELO = os.path.join(os.path.dirname(__file__), "datos", "modelo_deteccion.joblib")

NIVELES_SENSIBILIDAD = ["ninguno", "bajo", "medio", "alto"]

COLUMNAS_CATEGORICAS = ["tipo_operacion", "tabla_afectada", "aplicacion", "rol"]
COLUMNAS_NUMERICAS = [
    "hora_del_dia",
    "dia_semana",
    "fuera_de_horario",
    "aplicacion_habitual",
    "es_ip_externa",
    "nivel_sensibilidad",
    "autorizado",
    "filas_afectadas_log",
]


def construir_features(df_transacciones: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la matriz de features a partir del dataset crudo de
    transacciones, cruzando usuario/rol contra el catálogo compartido
    (perfiles y objetos sensibles) para derivar señales de comportamiento.

    No usa es_anomalo ni tipo_anomalia aunque estén presentes: se ignoran.

    Args:
        df_transacciones: DataFrame con columnas timestamp, usuario, rol,
            ip_origen, aplicacion, tabla_afectada, columna_afectada,
            tipo_operacion, filas_afectadas (las mismas que genera
            generar_dataset.py, con o sin las columnas de etiqueta).

    Returns:
        DataFrame con las columnas de COLUMNAS_NUMERICAS + COLUMNAS_CATEGORICAS,
        listo para pasar al ColumnTransformer del pipeline.
    """
    perfiles = {p["usuario"]: p for p in catalogo_activos.cargar_perfiles()}
    sensibles = {(o["tabla"], o["columna"]): o for o in catalogo_activos.cargar_objetos_sensibles()}

    timestamps = pd.to_datetime(df_transacciones["timestamp"])

    def fuera_de_horario(usuario, hora):
        perfil = perfiles.get(usuario)
        if perfil is None:
            return False
        return not catalogo_activos.esta_en_horario(hora, perfil["hora_inicio"], perfil["hora_fin"])

    def aplicacion_habitual(usuario, aplicacion):
        perfil = perfiles.get(usuario)
        return perfil is not None and aplicacion in perfil["aplicaciones_habituales"]

    def es_ip_externa(ip):
        try:
            return not ipaddress.ip_address(ip).is_private
        except ValueError:
            return True

    def nivel_sensibilidad(tabla, columna):
        obj = sensibles.get((tabla, columna))
        return NIVELES_SENSIBILIDAD.index(obj["nivel_sensibilidad"]) if obj else 0

    def autorizado(rol, tabla, columna):
        obj = sensibles.get((tabla, columna))
        return obj is None or rol in obj["roles_autorizados"]

    horas = timestamps.dt.hour
    usuarios = df_transacciones["usuario"]

    return pd.DataFrame({
        "hora_del_dia": horas,
        "dia_semana": timestamps.dt.dayofweek,
        "fuera_de_horario": [int(fuera_de_horario(u, h)) for u, h in zip(usuarios, horas)],
        "aplicacion_habitual": [
            int(aplicacion_habitual(u, a)) for u, a in zip(usuarios, df_transacciones["aplicacion"])
        ],
        "es_ip_externa": [int(es_ip_externa(ip)) for ip in df_transacciones["ip_origen"]],
        "nivel_sensibilidad": [
            nivel_sensibilidad(t, c)
            for t, c in zip(df_transacciones["tabla_afectada"], df_transacciones["columna_afectada"])
        ],
        "autorizado": [
            int(autorizado(r, t, c))
            for r, t, c in zip(
                df_transacciones["rol"], df_transacciones["tabla_afectada"], df_transacciones["columna_afectada"]
            )
        ],
        "filas_afectadas_log": df_transacciones["filas_afectadas"].astype(float).apply(math.log1p),
        "tipo_operacion": df_transacciones["tipo_operacion"].values,
        "tabla_afectada": df_transacciones["tabla_afectada"].values,
        "aplicacion": df_transacciones["aplicacion"].values,
        "rol": df_transacciones["rol"].values,
    })


def entrenar_modelo(
    ruta_csv: str = RUTA_DATASET,
    ruta_modelo: str = RUTA_MODELO,
    semilla: int = 42,
) -> Pipeline:
    """
    Entrena el modelo de detección de anomalías sobre el dataset sintético
    etiquetado y persiste el pipeline (preprocesamiento + clasificador) en disco.

    Args:
        ruta_csv: CSV generado por generar_dataset.py (debe traer la columna
            es_anomalo; tipo_anomalia se ignora, es solo ground truth).
        ruta_modelo: dónde guardar el pipeline entrenado (joblib).
        semilla: semilla del split entrenamiento/prueba, para reproducibilidad.

    Returns:
        El pipeline ya entrenado.

    Imprime en consola, sobre un split 80/20 estratificado por es_anomalo:
    precisión, recall y F1 por clase (classification_report) y la matriz de
    confusión.
    """
    df = pd.read_csv(ruta_csv)
    X = construir_features(df)
    y = df["es_anomalo"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=semilla
    )

    pipeline = Pipeline([
        ("preprocesamiento", ColumnTransformer([
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), COLUMNAS_CATEGORICAS),
            ("numericas", StandardScaler(), COLUMNAS_NUMERICAS),
        ])),
        ("clasificador", LogisticRegression(class_weight="balanced", max_iter=1000)),
    ])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print(f"Entrenado con {len(X_train)} filas, evaluado sobre {len(X_test)} filas de prueba.")
    print("Reporte de clasificación (conjunto de prueba):")
    print(classification_report(y_test, y_pred, target_names=["normal", "anomalo"], digits=3))
    print("Matriz de confusión [[VN, FP], [FN, VP]]:")
    print(confusion_matrix(y_test, y_pred))

    os.makedirs(os.path.dirname(ruta_modelo), exist_ok=True)
    joblib.dump(pipeline, ruta_modelo)
    print(f"Modelo guardado en {ruta_modelo}")

    return pipeline


def cargar_modelo(ruta: str = RUTA_MODELO):
    """
    Carga el pipeline persistido por entrenar_modelo.

    Returns:
        El pipeline entrenado, o None si todavía no existe en `ruta` (el
        front muestra un resultado de ejemplo mientras tanto).
    """
    if not os.path.exists(ruta):
        return None
    return joblib.load(ruta)


def predecir(modelo: Pipeline, df_transacciones: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica el modelo entrenado sobre un nuevo batch de transacciones (ej. el
    CSV subido en la página de Fase Reactiva, sin la columna es_anomalo).

    Args:
        modelo: pipeline entrenado (ver entrenar_modelo / cargar_modelo).
        df_transacciones: transacciones a evaluar.

    Returns:
        df_transacciones con dos columnas nuevas:
            - es_anomalo_predicho: bool
            - probabilidad_anomalia: float, probabilidad de la clase anómala
    """
    X = construir_features(df_transacciones)
    probabilidades = modelo.predict_proba(X)[:, 1]
    predicciones = modelo.predict(X)

    resultado = df_transacciones.copy()
    resultado["es_anomalo_predicho"] = predicciones.astype(bool)
    resultado["probabilidad_anomalia"] = probabilidades
    return resultado


if __name__ == "__main__":
    entrenar_modelo()
