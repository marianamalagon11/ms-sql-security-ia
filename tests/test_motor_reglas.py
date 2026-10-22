import re
from pathlib import Path

import pytest

from fase_proactiva import motor_reglas

RUTA_EJEMPLOS = Path(__file__).resolve().parents[1] / "fase_proactiva" / "ejemplos_sentencias.sql"


def nivel(sql, rol):
    return motor_reglas.evaluar_script(sql, rol)["nivel_riesgo"]


def codigos(sql, rol):
    ev = motor_reglas.evaluar_script(sql, rol)
    return {h["codigo"] for s in ev["sentencias"] for h in s["hallazgos"]}


def test_datos_no_sensibles_son_bajo():
    assert nivel("SELECT nombre, precio FROM Productos WHERE id_producto = 1", "Desarrollador") == "bajo"


def test_el_rol_cambia_el_nivel():
    sql = "SELECT id_usuario, email FROM Usuarios WHERE activo = 1"
    assert nivel(sql, "Soporte") == "bajo"
    assert nivel(sql, "Desarrollador") == "medio"
    assert "ROL_NO_AUTORIZADO" in codigos(sql, "Desarrollador")


def test_update_sin_where_sube_nivel():
    assert "SIN_WHERE" in codigos("UPDATE Pedidos SET estado = 'X'", "DBA")
    assert nivel("UPDATE Pedidos SET estado = 'X' WHERE id_pedido = 1", "DBA") == "bajo"
    assert nivel("UPDATE Pedidos SET estado = 'X'", "DBA") == "medio"


def test_agregados_no_son_exposicion_masiva():
    assert "EXPOSICION_MASIVA" not in codigos("SELECT SUM(salario) FROM Empleados", "RRHH")
    assert "EXPOSICION_MASIVA" in codigos("SELECT salario FROM Empleados", "RRHH")


@pytest.mark.parametrize("sql", [
    "EXEC xp_cmdshell 'dir'",
    "ALTER LOGIN sa ENABLE",
    "DROP DATABASE Ventas",
    "EXEC sp_addsrvrolemember 'x', 'sysadmin'",
])
def test_comandos_de_servidor_son_criticos_para_cualquier_rol(sql):
    assert nivel(sql, "DBA") == "critico"


def test_inyeccion_minimo_alto():
    assert nivel("SELECT nombre FROM Productos WHERE id_producto = 1 OR 1=1", "DBA") == "alto"


def test_script_toma_la_sentencia_mas_riesgosa():
    ev = motor_reglas.evaluar_script("SELECT nombre FROM Productos WHERE id_producto=1; DROP TABLE Empleados;", "DBA")
    assert ev["sentencia_critica"] == 1
    assert ev["nivel_riesgo"] == "critico"
    assert ev["requiere_validacion_adicional"]


def test_script_vacio():
    ev = motor_reglas.evaluar_script("   ", "DBA")
    assert ev["nivel_riesgo"] == "bajo" and ev["sentencias"] == []
    assert motor_reglas.explicar_evaluacion(ev)["explicacion"]


def test_explicacion_menciona_objetos_y_escalamiento():
    ev = motor_reglas.evaluar_script("SELECT salario FROM Empleados", "Soporte")
    texto = motor_reglas.explicar_evaluacion(ev)["explicacion"]
    assert "Empleados.salario" in texto and ev["escalamiento"]["escalamiento"] in texto


def test_ejemplos_coinciden_con_nivel_esperado_para_desarrollador():
    texto = RUTA_EJEMPLOS.read_text(encoding="utf-8")
    bloques = re.split(r"^--\s*@ejemplo:\s*(.+)$", texto, flags=re.MULTILINE)
    assert len(bloques) > 3
    equivalencias = {"BAJO": "bajo", "MEDIO": "medio", "ALTO": "alto", "CRÍTICO": "critico"}
    for i in range(1, len(bloques) - 1, 2):
        etiqueta = re.match(r"\[(\w+)\]", bloques[i].strip()).group(1)
        assert nivel(bloques[i + 1], "Desarrollador") == equivalencias[etiqueta], bloques[i]
