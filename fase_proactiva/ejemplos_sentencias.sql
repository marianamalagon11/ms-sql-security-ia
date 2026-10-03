-- ============================================================
-- Ejemplos de sentencias T-SQL para pruebas de la fase proactiva.
-- Cada bloque empieza con "-- @ejemplo: <descripción>" y el front los
-- ofrece en el selector de ejemplos. El nivel de riesgo depende del rol que
-- ejecuta la sentencia (ver catalogo_activos/objetos_sensibles.csv); entre
-- corchetes va el nivel esperado para el rol Desarrollador.
-- ============================================================

-- @ejemplo: [BAJO] Consulta de solo lectura sobre datos no sensibles
SELECT id_producto, nombre, precio
FROM Productos
WHERE categoria = 'Electronica';

-- @ejemplo: [BAJO] Conteo agregado sin exponer datos individuales
SELECT COUNT(*) AS total_pedidos
FROM Pedidos
WHERE fecha_pedido >= '2026-01-01';

-- @ejemplo: [MEDIO] Lectura de columnas con sensibilidad media (email)
SELECT id_usuario, email
FROM Usuarios
WHERE activo = 1;

-- @ejemplo: [MEDIO] Actualización puntual de un campo medio en una tabla sensible
UPDATE Clientes
SET nombre_completo = 'Juan Perez Actualizado'
WHERE id_cliente = 1024;

-- @ejemplo: [CRÍTICO] Acceso masivo a columnas altamente sensibles sin filtro
SELECT numero_documento, password_hash
FROM Clientes c
JOIN Usuarios u ON c.id_cliente = u.id_usuario;

-- @ejemplo: [CRÍTICO] Eliminación de registros en tabla crítica
DELETE FROM Transacciones
WHERE fecha_transaccion < '2020-01-01';

-- @ejemplo: [CRÍTICO] Operación DDL destructiva sobre tabla sensible
DROP TABLE Empleados;

-- @ejemplo: [CRÍTICO] UPDATE masivo de salarios sin WHERE
UPDATE Empleados
SET salario = salario * 1.10;

-- @ejemplo: [ALTO] Posible inyección SQL (tautología OR 1=1)
SELECT *
FROM Usuarios
WHERE email = 'admin@empresa.com' OR 1=1;

-- @ejemplo: [CRÍTICO] Ejecución de comandos del sistema operativo
EXEC xp_cmdshell 'dir C:\';

-- @ejemplo: [CRÍTICO] Escalamiento de privilegios
GRANT SELECT ON Empleados TO dpaez;

-- @ejemplo: [CRÍTICO] Script con varias sentencias (copia de datos sensibles)
BEGIN TRAN;
SELECT numero_documento, nombre_completo INTO #respaldo_clientes FROM Clientes;
UPDATE Pedidos SET estado = 'ENVIADO' WHERE id_pedido = 553;
COMMIT;
