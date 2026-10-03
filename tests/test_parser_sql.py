from fase_proactiva.parser_sql import dividir_script, parsear_script, parsear_sentencia


def test_select_basico():
    r = parsear_sentencia("SELECT id_producto, nombre FROM Productos WHERE categoria = 'X'")
    assert r["tipo_operacion"] == "SELECT"
    assert r["tablas"] == ["Productos"]
    assert set(r["columnas"]) == {"id_producto", "nombre", "categoria"}
    assert r["tiene_where"] and not r["select_asterisco"] and r["parseado"]


def test_alias_y_esquema_se_resuelven():
    r = parsear_sentencia("UPDATE e SET e.salario = 1 FROM dbo.Empleados e WHERE e.id_empleado = 3")
    assert r["tablas"] == ["Empleados"]
    assert ("Empleados", "salario") in r["referencias_columnas"]


def test_cte_no_cuenta_como_tabla():
    r = parsear_sentencia("WITH x AS (SELECT salario FROM Empleados) SELECT * FROM x")
    assert r["tablas"] == ["Empleados"]


def test_insert_con_lista_de_columnas():
    r = parsear_sentencia("INSERT INTO Clientes (nombre_completo, ciudad) VALUES ('a', 'b')")
    assert r["tipo_operacion"] == "INSERT"
    assert set(r["columnas"]) == {"nombre_completo", "ciudad"}
    assert not r["alcance_completo"]


def test_delete_top_y_sin_where():
    r = parsear_sentencia("DELETE TOP (100) FROM Pedidos")
    assert r["tablas"] == ["Pedidos"] and r["tiene_top"] and not r["tiene_where"]


def test_agregados_y_asterisco():
    assert parsear_sentencia("SELECT COUNT(*) FROM Pedidos")["solo_agregados"]
    assert not parsear_sentencia("SELECT COUNT(*) FROM Pedidos")["select_asterisco"]
    assert parsear_sentencia("SELECT c.* FROM Clientes c")["select_asterisco"]


def test_exec_y_tautologia():
    r = parsear_sentencia("EXEC xp_cmdshell 'dir'")
    assert r["tipo_operacion"] == "EXEC" and r["procedimiento"] == "xp_cmdshell" and r["tablas"] == []
    assert parsear_sentencia("SELECT * FROM Usuarios WHERE id = 1 OR 1=1")["tautologia"]


def test_respaldo_para_sintaxis_no_soportada():
    r = parsear_sentencia("DENY SELECT ON Empleados TO dpaez")
    assert not r["parseado"] and r["tipo_operacion"] == "DENY" and r["tablas"] == ["Empleados"]
    assert parsear_sentencia("ALTER LOGIN sa ENABLE")["tipo_operacion"] == "ALTER LOGIN"


def test_dividir_script_respeta_strings_y_go():
    script = "SELECT ';' FROM a;\nGO\nSELECT 2 FROM b\nGO\n"
    assert dividir_script(script) == ["SELECT ';' FROM a", "SELECT 2 FROM b"]


def test_error_en_una_sentencia_no_tumba_las_demas():
    r = parsear_script("SELECT a FROM t; WAITFOR DELAY '00:00:05'; DELETE FROM t2")
    assert [s["tipo_operacion"] for s in r] == ["SELECT", "WAITFOR", "DELETE"]
    assert [s["parseado"] for s in r] == [True, False, True]
