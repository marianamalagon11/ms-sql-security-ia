from fase_reactiva import explicador_llm
from fase_reactiva.generar_dataset import generar_dataset

ORDEN_NIVELES = {"critico": 0, "alto": 1, "medio": 2, "bajo": 3}


def _sospechosas(probabilidades):
    df = generar_dataset(len(probabilidades) * 10, 0.3, semilla=5)
    df = df[df["es_anomalo"] == 1].head(len(probabilidades)).drop(columns=["es_anomalo", "tipo_anomalia"])
    return df.assign(es_anomalo_predicho=True, probabilidad_anomalia=probabilidades)


def test_detallar_transacciones_agrega_nivel_y_motivo():
    detalle = explicador_llm.detallar_transacciones(_sospechosas([0.5, 0.95, 0.75]))

    assert {"nivel", "motivo"} <= set(detalle.columns)
    assert detalle["motivo"].str.len().gt(0).all()
    assert detalle["motivo"].str[0].str.isupper().all()


def test_detallar_transacciones_ordena_de_mas_a_menos_grave():
    detalle = explicador_llm.detallar_transacciones(_sospechosas([0.5, 0.95, 0.75, 0.99]))

    assert detalle["nivel"].tolist() == ["critico", "critico", "alto", "medio"]
    rangos = detalle["nivel"].map(ORDEN_NIVELES)
    assert rangos.is_monotonic_increasing
    assert detalle["probabilidad_anomalia"].iloc[0] == 0.99


def test_detallar_transacciones_vacio():
    vacio = _sospechosas([0.9]).iloc[0:0]

    detalle = explicador_llm.detallar_transacciones(vacio)

    assert detalle.empty
    assert {"nivel", "motivo"} <= set(detalle.columns)


CLAVES_REPORTE = {
    "resumen",
    "patrones",
    "usuarios_destacados",
    "anomalias_identificadas",
}


def test_generar_reporte_devuelve_el_resumen_ejecutivo():
    sospechosas = explicador_llm.detallar_transacciones(_sospechosas([0.9] * 8))

    reporte = explicador_llm.generar_reporte(sospechosas)

    assert set(reporte) == CLAVES_REPORTE
    assert reporte["resumen"].startswith("Se marcaron 8 transacciones sospechosas")
    assert "(es)" not in reporte["resumen"] and "(s)" not in reporte["resumen"]
    assert len(reporte["anomalias_identificadas"]) == 8
    assert sum(int(p.split(": ")[1].split()[0]) for p in reporte["patrones"]) >= 8


def test_generar_reporte_vacio():
    reporte = explicador_llm.generar_reporte(_sospechosas([0.9]).iloc[0:0])

    assert set(reporte) == CLAVES_REPORTE
    assert reporte["resumen"].startswith("No se identificaron")
    assert reporte["anomalias_identificadas"] == []
