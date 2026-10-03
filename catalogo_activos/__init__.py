"""
Carga del catálogo compartido por ambas fases (bloque C de la arquitectura):
objetos sensibles, perfiles de usuario, listas blancas y matrices de riesgo
y escalamiento.

Los roles autorizados y las aplicaciones habituales se guardan en el CSV
separados por "|" y aquí se exponen como listas.
"""

import csv
from pathlib import Path

DIR_CATALOGO = Path(__file__).resolve().parent

RUTA_OBJETOS_SENSIBLES = DIR_CATALOGO / "objetos_sensibles.csv"
RUTA_PERFILES = DIR_CATALOGO / "perfiles.csv"
RUTA_LISTAS_BLANCAS = DIR_CATALOGO / "listas_blancas.csv"
RUTA_MATRIZ_RIESGO = DIR_CATALOGO / "matriz_riesgo.csv"
RUTA_MATRIZ_ESCALAMIENTO = DIR_CATALOGO / "matriz_escalamiento.csv"


def _leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def separar_lista(valor) -> list[str]:
    """Convierte "A|B|C" en ["A", "B", "C"]; acepta también una lista ya separada."""
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor if str(v).strip()]
    return [v.strip() for v in str(valor or "").split("|") if v.strip()]


def cargar_objetos_sensibles() -> list[dict]:
    """
    Returns:
        Lista de dicts con tabla, columna, nivel_sensibilidad, rol_autorizado
        (texto original) y roles_autorizados (lista).
    """
    filas = _leer_csv(RUTA_OBJETOS_SENSIBLES)
    for fila in filas:
        fila["roles_autorizados"] = separar_lista(fila["rol_autorizado"])
    return filas


def cargar_perfiles() -> list[dict]:
    """
    Returns:
        Lista de dicts con usuario, rol, aplicaciones_habituales (lista),
        hora_inicio y hora_fin (int). Si hora_inicio > hora_fin el horario
        cruza la medianoche (ej. 22 a 5).
    """
    filas = _leer_csv(RUTA_PERFILES)
    for fila in filas:
        fila["aplicaciones_habituales"] = separar_lista(fila["aplicaciones_habituales"])
        fila["hora_inicio"] = int(fila["hora_inicio"])
        fila["hora_fin"] = int(fila["hora_fin"])
    return filas


def cargar_listas_blancas() -> dict[str, list[str]]:
    """
    Returns:
        dict tipo -> lista de valores, ej. {"red": ["10.0.0.0/8", ...],
        "aplicacion": [...], "servidor": [...]}.
    """
    listas: dict[str, list[str]] = {}
    for fila in _leer_csv(RUTA_LISTAS_BLANCAS):
        listas.setdefault(fila["tipo"], []).append(fila["valor"])
    return listas


def cargar_matriz_riesgo() -> dict[str, dict[str, str]]:
    """
    Returns:
        dict categoria_operacion -> {nivel_sensibilidad -> nivel_riesgo_base}.
    """
    return {
        fila.pop("categoria_operacion"): fila
        for fila in _leer_csv(RUTA_MATRIZ_RIESGO)
    }


def cargar_matriz_escalamiento() -> dict[str, dict]:
    """
    Returns:
        dict nivel_riesgo -> {escalamiento, responsable,
        requiere_validacion_adicional (bool), accion}.
    """
    matriz = {}
    for fila in _leer_csv(RUTA_MATRIZ_ESCALAMIENTO):
        fila["requiere_validacion_adicional"] = fila["requiere_validacion_adicional"].strip().lower() == "si"
        matriz[fila.pop("nivel_riesgo")] = fila
    return matriz


def esta_en_horario(hora: int, hora_inicio: int, hora_fin: int) -> bool:
    """True si `hora` cae dentro del horario del perfil (soporta cruce de medianoche)."""
    if hora_inicio <= hora_fin:
        return hora_inicio <= hora <= hora_fin
    return hora >= hora_inicio or hora <= hora_fin
