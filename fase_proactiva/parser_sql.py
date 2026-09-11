"""
Parser de sentencias MS-SQL (T-SQL) basado en sqlglot.

Extrae la información estructural necesaria para la fase proactiva:
tipo de operación, tablas y columnas afectadas.
"""

import sqlglot
from sqlglot import exp


def parsear_sentencia(sentencia_sql: str) -> dict:
    """
    Parsea una sentencia T-SQL y extrae su información estructural.

    Args:
        sentencia_sql: Texto crudo de la sentencia SQL a analizar.

    Returns:
        dict con al menos las siguientes claves:
            - tipo_operacion: str (ej. "SELECT", "UPDATE", "DELETE", "INSERT", "DROP", ...)
            - tablas: list[str] con los nombres de las tablas involucradas
            - columnas: list[str] con los nombres de las columnas involucradas
            - sentencia_original: str, la sentencia tal como fue recibida

    TODO: Usar sqlglot.parse_one(sentencia_sql, read="tsql") para obtener el AST.
    TODO: Recorrer el AST (exp.Table, exp.Column) para poblar tablas y columnas.
    TODO: Manejar sentencias con múltiples statements (batch) y errores de parseo.
    """
    raise NotImplementedError("TODO: implementar el parseo con sqlglot")


def extraer_tablas(ast: exp.Expression) -> list[str]:
    """
    Extrae los nombres de tabla presentes en un AST de sqlglot.

    Args:
        ast: Expresión/AST ya parseado por sqlglot.

    Returns:
        Lista de nombres de tabla (sin duplicados).

    TODO: Recorrer ast.find_all(exp.Table) y devolver ast.name para cada una.
    """
    raise NotImplementedError("TODO: implementar extracción de tablas")


def extraer_columnas(ast: exp.Expression) -> list[str]:
    """
    Extrae los nombres de columna presentes en un AST de sqlglot.

    Args:
        ast: Expresión/AST ya parseado por sqlglot.

    Returns:
        Lista de nombres de columna (sin duplicados).

    TODO: Recorrer ast.find_all(exp.Column) y devolver ast.name para cada una.
    """
    raise NotImplementedError("TODO: implementar extracción de columnas")


def clasificar_tipo_operacion(ast: exp.Expression) -> str:
    """
    Determina el tipo de operación DML/DDL de la sentencia (SELECT, INSERT,
    UPDATE, DELETE, DROP, ALTER, etc.).

    Args:
        ast: Expresión/AST ya parseado por sqlglot.

    Returns:
        Nombre del tipo de operación en mayúsculas.

    TODO: Inspeccionar el tipo de nodo raíz del AST (isinstance contra exp.Select,
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, etc.).
    """
    raise NotImplementedError("TODO: implementar clasificación de operación")
