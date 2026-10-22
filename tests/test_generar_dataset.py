import catalogo_activos
from fase_reactiva.generar_dataset import generar_dataset

IPS_EXTERNAS = ("187.45.", "45.227.", "201.14.", "103.21.")


def _sensibles():
    return {(o["tabla"], o["columna"]): o["roles_autorizados"] for o in catalogo_activos.cargar_objetos_sensibles()}


def test_tamano_proporcion_y_reproducibilidad():
    df = generar_dataset(1000, 0.1, semilla=1)
    assert len(df) == 1000
    assert df["es_anomalo"].sum() == 100
    assert df.equals(generar_dataset(1000, 0.1, semilla=1))


def test_normales_respetan_perfiles_y_autorizaciones():
    df = generar_dataset(2000, 0.1, semilla=3)
    perfiles = {p["usuario"]: p for p in catalogo_activos.cargar_perfiles()}
    sensibles = _sensibles()

    for fila in df[df["es_anomalo"] == 0].itertuples():
        assert perfiles[fila.usuario]["rol"] == fila.rol
        roles = sensibles.get((fila.tabla_afectada, fila.columna_afectada))
        assert roles is None or fila.rol in roles, fila
        assert not fila.ip_origen.startswith(IPS_EXTERNAS)


def test_acceso_no_autorizado_es_realmente_no_autorizado():
    df = generar_dataset(3000, 0.2, semilla=5)
    sensibles = _sensibles()
    casos = df[df["tipo_anomalia"].fillna("").str.startswith("acceso_no_autorizado")]
    assert len(casos) > 0
    for fila in casos.itertuples():
        assert fila.rol not in sensibles[(fila.tabla_afectada, fila.columna_afectada)]
