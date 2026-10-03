"""
Parser de sentencias MS-SQL (T-SQL) basado en sqlglot.

Extrae la información estructural necesaria para la fase proactiva:
tipo de operación, tablas y columnas afectadas, y señales estructurales de
riesgo (UPDATE/DELETE sin WHERE, SELECT *, tautologías tipo OR 1=1, etc.).

Un script puede traer varias sentencias (separadas por ";" o por líneas GO).
Cada sentencia se parsea por separado para que un error en una no tumbe el
análisis de las demás. Lo que sqlglot no soporta (DENY, WAITFOR, ALTER LOGIN,
...) se analiza con un respaldo basado en expresiones regulares y se marca
con parseado=False.
"""

import logging
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

DIALECTO = "tsql"

# sqlglot avisa por logging cada vez que cae a exp.Command; no aporta al usuario.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

_RE_GO = re.compile(r"^\s*GO\s*(\d+)?\s*$", re.IGNORECASE | re.MULTILINE)
_RE_TABLAS_RESPALDO = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|ON)\s+((?:\[?\w+\]?\.){0,3}\[?#{0,2}\w+\]?)",
    re.IGNORECASE,
)
# sqlglot no soporta DELETE/UPDATE TOP (n): se retira antes de parsear y se recuerda aparte.
_RE_DML_TOP = re.compile(r"^(\s*(?:DELETE|UPDATE))\s+TOP\s*\(\s*[^)]*\)\s*(?:PERCENT\b)?", re.IGNORECASE)
_RE_TAUTOLOGIA = re.compile(r"\bOR\s+('?)(\w+)\1\s*=\s*\1\2\1(?!\w)", re.IGNORECASE)

_PALABRAS_NO_TABLA = {"select", "where", "set", "values", "dbo", "login", "user", "role", "database", "server"}


def dividir_script(script_sql: str) -> list[str]:
    """
    Separa un script en sentencias individuales respetando strings y
    comentarios (usa el tokenizador de sqlglot, no un split ingenuo por ";").

    Args:
        script_sql: Texto crudo del script (puede contener GO).

    Returns:
        Lista de sentencias (texto) sin el ";" final, sin vacíos.
    """
    texto = _RE_GO.sub(";", script_sql)
    try:
        tokens = sqlglot.Dialect.get_or_raise(DIALECTO).tokenize(texto)
    except SqlglotError:
        return [s.strip() for s in texto.split(";") if s.strip()]

    sentencias, actual = [], []
    for token in tokens + [None]:
        if token is None or token.token_type == TokenType.SEMICOLON:
            if actual:
                sentencias.append(texto[actual[0].start : actual[-1].end + 1].strip())
            actual = []
        else:
            actual.append(token)
    return sentencias


def parsear_script(script_sql: str) -> list[dict]:
    """
    Parsea un script completo (una o varias sentencias).

    Returns:
        Lista de dicts, uno por sentencia, con el formato de parsear_sentencia.
    """
    return [parsear_sentencia(s) for s in dividir_script(script_sql)]


def parsear_sentencia(sentencia_sql: str) -> dict:
    """
    Parsea UNA sentencia T-SQL y extrae su información estructural.

    Args:
        sentencia_sql: Texto crudo de la sentencia SQL a analizar.

    Returns:
        dict con las claves:
            - tipo_operacion: str (SELECT, INSERT, UPDATE, DELETE, MERGE, DROP,
              ALTER, CREATE, TRUNCATE, GRANT, REVOKE, DENY, EXEC, ...)
            - tablas: list[str] tablas reales involucradas (sin alias ni CTEs)
            - columnas: list[str] nombres de columna involucrados
            - referencias_columnas: list[tuple[str | None, str]] pares
              (tabla resuelta o None si la columna no viene calificada, columna)
            - tiene_where: bool
            - tiene_top: bool (SELECT TOP n / DELETE TOP n)
            - select_asterisco: bool (SELECT * o alias.*)
            - solo_agregados: bool (todas las columnas proyectadas son agregados)
            - alcance_completo: bool la operación afecta a todas las columnas de
              las tablas (DELETE, DROP, TRUNCATE, SELECT *, GRANT sobre tabla...)
            - select_into: bool (SELECT ... INTO o INSERT ... SELECT)
            - procedimiento: str | None nombre del procedimiento en un EXEC
            - tautologia: bool (OR 1=1, OR 'a'='a')
            - parseado: bool False si se usó el respaldo por regex
            - error: str | None
            - sentencia_original: str
    """
    texto = sentencia_sql.strip().rstrip(";").strip()
    texto_parseable, dml_top = _RE_DML_TOP.subn(lambda m: m.group(1) + " ", texto)
    try:
        ast = sqlglot.parse_one(texto_parseable, read=DIALECTO)
    except SqlglotError as exc:
        return _parsear_respaldo(texto, f"{type(exc).__name__}: {str(exc).splitlines()[0]}")

    if ast is None or isinstance(ast, exp.Command):
        return _parsear_respaldo(texto, "Sintaxis no soportada por el parser estructural")

    tipo = clasificar_tipo_operacion(ast)
    alias = _mapa_alias(ast)
    tablas = extraer_tablas(ast)
    referencias = _referencias_columnas(ast, alias)
    columnas = _unicos(c for _, c in referencias)

    select_principal = ast if isinstance(ast, exp.Select) else None
    select_asterisco = bool(select_principal) and any(
        isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star))
        for e in select_principal.expressions
    )
    solo_agregados = bool(select_principal) and bool(select_principal.expressions) and all(
        isinstance(e.unalias(), exp.AggFunc) for e in select_principal.expressions
    )

    alcance_completo = (
        select_asterisco
        or tipo in {"DELETE", "TRUNCATE", "DROP", "ALTER", "GRANT", "REVOKE"}
        or (isinstance(ast, exp.Insert) and not isinstance(ast.this, exp.Schema))
    )

    procedimiento = None
    if isinstance(ast, exp.Execute):
        procedimiento = ast.this.name if isinstance(ast.this, exp.Table) else ast.this.sql(dialect=DIALECTO)
        tablas = []

    return {
        "tipo_operacion": tipo,
        "tablas": tablas,
        "columnas": columnas,
        "referencias_columnas": referencias,
        "tiene_where": ast.args.get("where") is not None,
        "tiene_top": bool(dml_top) or ast.args.get("limit") is not None,
        "select_asterisco": select_asterisco,
        "solo_agregados": solo_agregados,
        "alcance_completo": alcance_completo,
        "select_into": (isinstance(ast, exp.Select) and ast.args.get("into") is not None)
        or (isinstance(ast, exp.Insert) and isinstance(ast.expression, exp.Select)),
        "procedimiento": procedimiento,
        "tautologia": _tiene_tautologia(ast),
        "parseado": True,
        "error": None,
        "sentencia_original": texto,
    }


def extraer_tablas(ast: exp.Expression) -> list[str]:
    """
    Extrae los nombres de tabla reales presentes en un AST de sqlglot,
    descartando alias (UPDATE e ... FROM Empleados e), CTEs y funciones de
    tabla como OPENROWSET.

    Args:
        ast: Expresión/AST ya parseado por sqlglot.

    Returns:
        Lista de nombres de tabla (sin duplicados, sin esquema).
    """
    alias = {a.lower() for a in _mapa_alias(ast)}
    ctes = {cte.alias.lower() for cte in ast.find_all(exp.CTE)}
    nombres = []
    for tabla in ast.find_all(exp.Table):
        nombre = tabla.name
        if not nombre or not isinstance(tabla.this, exp.Identifier):
            continue
        if nombre.lower() in ctes:
            continue
        # Un Table sin alias propio cuyo nombre coincide con un alias es una referencia al alias.
        if nombre.lower() in alias and not tabla.alias:
            continue
        nombres.append(nombre)
    return _unicos(nombres)


def extraer_columnas(ast: exp.Expression) -> list[str]:
    """
    Extrae los nombres de columna presentes en un AST de sqlglot (incluye
    las columnas listadas en INSERT INTO t (a, b)).

    Args:
        ast: Expresión/AST ya parseado por sqlglot.

    Returns:
        Lista de nombres de columna (sin duplicados).
    """
    return _unicos(c for _, c in _referencias_columnas(ast, _mapa_alias(ast)))


def clasificar_tipo_operacion(ast: exp.Expression) -> str:
    """
    Determina el tipo de operación DML/DDL/DCL de la sentencia.

    Args:
        ast: Expresión/AST ya parseado por sqlglot.

    Returns:
        Nombre del tipo de operación en mayúsculas.
    """
    tipos = [
        (exp.Select, "SELECT"),
        (exp.Union, "SELECT"),
        (exp.Insert, "INSERT"),
        (exp.Update, "UPDATE"),
        (exp.Delete, "DELETE"),
        (exp.Merge, "MERGE"),
        (exp.TruncateTable, "TRUNCATE"),
        (exp.Drop, "DROP"),
        (exp.Alter, "ALTER"),
        (exp.Create, "CREATE"),
        (exp.Grant, "GRANT"),
        (exp.Revoke, "REVOKE"),
        (exp.Execute, "EXEC"),
        (exp.Use, "USE"),
        (exp.Declare, "DECLARE"),
        (exp.Transaction, "TRANSACCION"),
        (exp.Commit, "TRANSACCION"),
        (exp.Rollback, "TRANSACCION"),
        (exp.Set, "SET"),
    ]
    for clase, nombre in tipos:
        if isinstance(ast, clase):
            if nombre in {"DROP", "CREATE", "ALTER"} and str(ast.args.get("kind") or "").upper() in {"DATABASE", "SCHEMA"}:
                return f"{nombre} {str(ast.args['kind']).upper()}"
            return nombre
    return ast.key.upper()


def _mapa_alias(ast: exp.Expression) -> dict[str, str]:
    """alias -> nombre real de la tabla."""
    mapa = {}
    for tabla in ast.find_all(exp.Table):
        if tabla.alias and tabla.name:
            mapa[tabla.alias] = tabla.name
    return mapa


def _referencias_columnas(ast: exp.Expression, alias: dict[str, str]) -> list[tuple[str | None, str]]:
    alias_min = {k.lower(): v for k, v in alias.items()}
    refs = []
    for col in ast.find_all(exp.Column):
        if isinstance(col.this, exp.Star) or not col.name:
            continue
        calificador = col.table or None
        tabla = alias_min.get(calificador.lower(), calificador) if calificador else None
        refs.append((tabla, col.name))

    # INSERT INTO t (a, b): las columnas destino son Identifiers dentro de un Schema.
    if isinstance(ast, exp.Insert) and isinstance(ast.this, exp.Schema):
        destino = ast.this.this.name if isinstance(ast.this.this, exp.Table) else None
        for ident in ast.this.expressions:
            if isinstance(ident, exp.Identifier):
                refs.append((destino, ident.name))

    vistos, unicos = set(), []
    for ref in refs:
        clave = ((ref[0] or "").lower(), ref[1].lower())
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(ref)
    return unicos


def _tiene_tautologia(ast: exp.Expression) -> bool:
    """Detecta comparaciones siempre verdaderas entre literales (1=1, 'a'='a')."""
    for eq in ast.find_all(exp.EQ):
        izq, der = eq.this, eq.expression
        if isinstance(izq, exp.Literal) and isinstance(der, exp.Literal) and izq.this == der.this:
            return True
    return False


def _parsear_respaldo(texto: str, error: str) -> dict:
    """Análisis mínimo por regex para sentencias que sqlglot no puede parsear."""
    palabras = texto.split()
    primera = palabras[0].upper() if palabras else "DESCONOCIDO"
    tipo = {"EXECUTE": "EXEC", "BEGIN": "TRANSACCION", "COMMIT": "TRANSACCION", "ROLLBACK": "TRANSACCION"}.get(primera, primera)
    if tipo in {"ALTER", "CREATE", "DROP"} and len(palabras) > 1:
        tipo = f"{tipo} {palabras[1].upper()}"

    tablas = []
    for m in _RE_TABLAS_RESPALDO.finditer(texto):
        nombre = m.group(1).split(".")[-1].strip("[]")
        if nombre.lower() not in _PALABRAS_NO_TABLA:
            tablas.append(nombre)

    procedimiento = palabras[1].strip("[]();'") if tipo == "EXEC" and len(palabras) > 1 else None

    return {
        "tipo_operacion": tipo,
        "tablas": _unicos(tablas),
        "columnas": [],
        "referencias_columnas": [],
        "tiene_where": re.search(r"\bWHERE\b", texto, re.IGNORECASE) is not None,
        "tiene_top": re.search(r"\bTOP\b", texto, re.IGNORECASE) is not None,
        "select_asterisco": re.search(r"\bSELECT\s+(TOP\s+\S+\s+)?\*", texto, re.IGNORECASE) is not None,
        "solo_agregados": False,
        # Sin AST no sabemos qué columnas toca: se asume lo peor.
        "alcance_completo": True,
        "select_into": False,
        "procedimiento": procedimiento,
        "tautologia": _RE_TAUTOLOGIA.search(texto) is not None,
        "parseado": False,
        "error": error,
        "sentencia_original": texto,
    }


def _unicos(valores) -> list[str]:
    vistos, salida = set(), []
    for v in valores:
        if v.lower() not in vistos:
            vistos.add(v.lower())
            salida.append(v)
    return salida
