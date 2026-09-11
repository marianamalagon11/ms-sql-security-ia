-- ============================================================
-- Ejemplos de sentencias T-SQL para pruebas de la fase proactiva
-- Niveles de riesgo indicados a modo de referencia manual.
-- ============================================================

-- [RIESGO BAJO] Consulta de solo lectura sobre datos no sensibles
SELECT id_producto, nombre, precio
FROM Productos
WHERE categoria = 'Electronica';

-- [RIESGO BAJO] Conteo agregado sin exponer datos individuales
SELECT COUNT(*) AS total_pedidos
FROM Pedidos
WHERE fecha_pedido >= '2026-01-01';

-- [RIESGO MEDIO] Lectura de columnas con sensibilidad media (email)
SELECT id_usuario, email
FROM Usuarios
WHERE activo = 1;

-- [RIESGO MEDIO] Actualización de un campo no crítico en una tabla sensible
UPDATE Clientes
SET nombre_completo = 'Juan Perez Actualizado'
WHERE id_cliente = 1024;

-- [RIESGO ALTO] Acceso masivo a columnas altamente sensibles sin filtro selectivo
SELECT numero_documento, tarjeta_credito, password_hash
FROM Clientes c
JOIN Usuarios u ON c.id_cliente = u.id_cliente;

-- [RIESGO ALTO] Eliminación de registros en tabla crítica
DELETE FROM Transacciones
WHERE fecha_transaccion < '2020-01-01';

-- [RIESGO ALTO] Operación DDL destructiva sobre tabla sensible
DROP TABLE Empleados;
