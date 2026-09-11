"""
Entrenamiento y uso de un modelo de regresión logística (scikit-learn) para
detectar transacciones anómalas sobre el dataset generado por
fase_reactiva.generar_dataset.

Features candidatas: hora del día, si la IP de origen es externa, si el rol
del usuario está autorizado para la tabla/columna afectada (según el
catálogo de objetos sensibles), tipo de operación, etc.
"""

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def construir_features(df_transacciones: pd.DataFrame, catalogo_sensibles: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la matriz de features a partir del dataset crudo de
    transacciones y el catálogo de objetos sensibles.

    Args:
        df_transacciones: DataFrame con columnas timestamp, usuario, rol,
            ip_origen, ip_destino, aplicacion, tabla_afectada,
            columna_afectada, tipo_operacion, sentencia_sql.
        catalogo_sensibles: DataFrame del catálogo (catalogo_activos/objetos_sensibles.csv).

    Returns:
        DataFrame de features numéricas/categóricas codificadas, listas
        para entrenar o para inferencia.

    TODO: Extraer hora_del_dia desde timestamp.
    TODO: Derivar es_ip_externa a partir de ip_origen (ej. fuera de rangos 10.x/192.168.x).
    TODO: Cruzar rol + tabla_afectada + columna_afectada contra catalogo_sensibles
    para derivar acceso_no_autorizado.
    TODO: Codificar variables categóricas (tipo_operacion, aplicacion, etc.).
    """
    raise NotImplementedError("TODO: implementar construcción de features")


def entrenar_modelo(df_transacciones: pd.DataFrame, catalogo_sensibles: pd.DataFrame) -> LogisticRegression:
    """
    Entrena un modelo de regresión logística para clasificar transacciones
    como normales o anómalas, usando la columna 'es_anomalo' como etiqueta.

    Args:
        df_transacciones: dataset de transacciones (incluye columna es_anomalo
            cuando se usa el dataset sintético de entrenamiento).
        catalogo_sensibles: catálogo de objetos sensibles.

    Returns:
        Instancia de LogisticRegression ya entrenada.

    TODO: Llamar a construir_features(...).
    TODO: train_test_split de X, y (columna 'es_anomalo').
    TODO: Escalar features con StandardScaler si aplica.
    TODO: Entrenar LogisticRegression y reportar métricas básicas (accuracy, recall).
    TODO: Persistir el modelo entrenado (ej. con joblib) para reutilizarlo en el front.
    """
    raise NotImplementedError("TODO: implementar entrenamiento del modelo")


def predecir_anomalias(modelo: LogisticRegression, df_transacciones: pd.DataFrame, catalogo_sensibles: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica el modelo entrenado sobre un nuevo batch de transacciones
    (ej. el CSV subido desde el front) y agrega columnas de predicción.

    Args:
        modelo: modelo entrenado por entrenar_modelo.
        df_transacciones: batch de transacciones a evaluar.
        catalogo_sensibles: catálogo de objetos sensibles.

    Returns:
        df_transacciones con columnas adicionales:
            - es_anomalo_predicho: bool
            - score_anomalia: float (probabilidad del modelo)

    TODO: Llamar a construir_features(...) sobre el nuevo batch.
    TODO: Usar modelo.predict / modelo.predict_proba y anexar resultados al DataFrame original.
    """
    raise NotImplementedError("TODO: implementar inferencia sobre nuevas transacciones")


if __name__ == "__main__":
    # TODO: cargar fase_reactiva/datos/transacciones_sinteticas.csv y
    # catalogo_activos/objetos_sensibles.csv, entrenar el modelo y
    # opcionalmente persistirlo.
    raise NotImplementedError("TODO: implementar script de entrenamiento end-to-end")
