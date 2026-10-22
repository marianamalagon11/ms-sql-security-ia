import pandas as pd
import pytest

from fase_reactiva import modelo_deteccion
from fase_reactiva.generar_dataset import generar_dataset


@pytest.fixture
def ruta_dataset(tmp_path):
    df = generar_dataset(600, 0.15, semilla=11)
    ruta = tmp_path / "transacciones_sinteticas.csv"
    df.to_csv(ruta, index=False)
    return ruta


def test_entrenar_modelo_no_lanza_error_y_guarda_el_pipeline(tmp_path, ruta_dataset):
    ruta_modelo = tmp_path / "modelo_deteccion.joblib"

    pipeline = modelo_deteccion.entrenar_modelo(ruta_csv=str(ruta_dataset), ruta_modelo=str(ruta_modelo))

    assert pipeline is not None
    assert ruta_modelo.exists()


def test_predecir_devuelve_las_columnas_esperadas(tmp_path, ruta_dataset):
    ruta_modelo = tmp_path / "modelo_deteccion.joblib"
    pipeline = modelo_deteccion.entrenar_modelo(ruta_csv=str(ruta_dataset), ruta_modelo=str(ruta_modelo))

    nuevas = generar_dataset(50, 0.2, semilla=99).drop(columns=["es_anomalo", "tipo_anomalia"])
    resultado = modelo_deteccion.predecir(pipeline, nuevas)

    assert "es_anomalo_predicho" in resultado.columns
    assert "probabilidad_anomalia" in resultado.columns
    assert resultado["es_anomalo_predicho"].dtype == bool
    assert resultado["probabilidad_anomalia"].between(0, 1).all()
    assert len(resultado) == len(nuevas)
    # predecir no debe perder ni alterar las columnas originales del batch.
    for columna in nuevas.columns:
        assert resultado[columna].equals(nuevas[columna])


def test_cargar_modelo_retorna_none_si_no_existe(tmp_path):
    assert modelo_deteccion.cargar_modelo(ruta=str(tmp_path / "no_existe.joblib")) is None


def test_cargar_modelo_carga_lo_entrenado(tmp_path, ruta_dataset):
    ruta_modelo = tmp_path / "modelo_deteccion.joblib"
    modelo_deteccion.entrenar_modelo(ruta_csv=str(ruta_dataset), ruta_modelo=str(ruta_modelo))

    modelo = modelo_deteccion.cargar_modelo(ruta=str(ruta_modelo))

    assert modelo is not None
    predicciones = modelo_deteccion.predecir(modelo, generar_dataset(20, 0.2, semilla=7).drop(
        columns=["es_anomalo", "tipo_anomalia"]
    ))
    assert isinstance(predicciones, pd.DataFrame)
