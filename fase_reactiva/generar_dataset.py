"""
Genera un dataset sintético de transacciones MS-SQL para entrenar y probar
el modelo de detección de anomalías de la fase reactiva.

Produce entre 150 y 200 filas con columnas: timestamp, usuario, rol,
ip_origen, ip_destino, aplicacion, tabla_afectada, tipo_operacion,
sentencia_sql y es_anomalo (etiqueta sintética usada como ground truth).

Aproximadamente un 10% de las filas se generan a propósito como casos
anómalos: acceso fuera de horario laboral, IP de origen externa/no
confiable, o acceso a una tabla/columna sensible por un rol no autorizado.

Uso:
    python fase_reactiva/generar_dataset.py
"""

import os
import random
from datetime import datetime, timedelta

import pandas as pd

RUTA_SALIDA = os.path.join(os.path.dirname(__file__), "datos", "transacciones_sinteticas.csv")

N_FILAS = 180
PROPORCION_ANOMALIAS = 0.10

USUARIOS_ROLES = [
    ("jgomez", "DBA"),
    ("mrodriguez", "RRHH"),
    ("cfernandez", "Analista_Financiero"),
    ("lsuarez", "Soporte"),
    ("aortiz", "Analista_Seguridad"),
    ("dpaez", "Desarrollador"),
]

TABLAS_OPERACIONES = [
    ("Clientes", "numero_documento", ["SELECT", "UPDATE"]),
    ("Clientes", "nombre_completo", ["SELECT", "UPDATE"]),
    ("Empleados", "salario", ["SELECT", "UPDATE"]),
    ("Empleados", "cuenta_bancaria", ["SELECT"]),
    ("Transacciones", "monto", ["SELECT", "INSERT"]),
    ("Transacciones", "tarjeta_credito", ["SELECT"]),
    ("Usuarios", "password_hash", ["SELECT", "UPDATE"]),
    ("Usuarios", "email", ["SELECT", "UPDATE"]),
    ("Productos", "precio", ["SELECT", "UPDATE", "INSERT"]),
    ("Pedidos", "estado", ["SELECT", "UPDATE"]),
]

APLICACIONES = ["ERP-Contable", "PortalWeb", "SSMS", "PowerBI", "AppMovil", "BatchNocturno"]

IPS_INTERNAS = ["10.0.1.{}", "10.0.2.{}", "192.168.1.{}"]
IPS_EXTERNAS = ["187.45.{}.{}", "45.227.{}.{}", "201.14.{}.{}"]

FECHA_BASE = datetime(2026, 8, 1)


def _generar_sentencia(tipo_operacion: str, tabla: str, columna: str) -> str:
    if tipo_operacion == "SELECT":
        return f"SELECT {columna} FROM {tabla} WHERE id_{tabla.lower()} = ?;"
    if tipo_operacion == "UPDATE":
        return f"UPDATE {tabla} SET {columna} = ? WHERE id_{tabla.lower()} = ?;"
    return f"INSERT INTO {tabla} ({columna}) VALUES (?);"


def _ip_interna() -> str:
    plantilla = random.choice(IPS_INTERNAS)
    return plantilla.format(random.randint(2, 254))


def _ip_externa() -> str:
    plantilla = random.choice(IPS_EXTERNAS)
    return plantilla.format(random.randint(1, 254), random.randint(1, 254))


def _timestamp_horario_laboral() -> datetime:
    dia = FECHA_BASE + timedelta(days=random.randint(0, 40))
    hora = random.randint(8, 18)
    minuto = random.randint(0, 59)
    return dia.replace(hour=hora, minute=minuto, second=random.randint(0, 59))


def _timestamp_fuera_de_horario() -> datetime:
    dia = FECHA_BASE + timedelta(days=random.randint(0, 40))
    hora = random.choice(list(range(0, 6)) + list(range(22, 24)))
    minuto = random.randint(0, 59)
    return dia.replace(hour=hora, minute=minuto, second=random.randint(0, 59))


def _generar_fila_normal() -> dict:
    usuario, rol = random.choice(USUARIOS_ROLES)
    tabla, columna, operaciones_validas = random.choice(TABLAS_OPERACIONES)
    tipo_operacion = random.choice(operaciones_validas)

    return {
        "timestamp": _timestamp_horario_laboral().isoformat(),
        "usuario": usuario,
        "rol": rol,
        "ip_origen": _ip_interna(),
        "ip_destino": "10.0.0.5",
        "aplicacion": random.choice(APLICACIONES),
        "tabla_afectada": tabla,
        "columna_afectada": columna,
        "tipo_operacion": tipo_operacion,
        "sentencia_sql": _generar_sentencia(tipo_operacion, tabla, columna),
        "es_anomalo": 0,
    }


def _generar_fila_anomala() -> dict:
    """
    Genera una fila anómala eligiendo aleatoriamente uno de tres patrones:
    fuera de horario, IP de origen externa, o acceso indebido (rol no
    autorizado sobre una tabla/columna sensible).
    """
    usuario, rol = random.choice(USUARIOS_ROLES)
    tabla, columna, _ = random.choice(TABLAS_OPERACIONES)
    tipo_operacion = random.choice(["SELECT", "UPDATE", "DELETE"])

    patron = random.choice(["fuera_de_horario", "ip_externa", "acceso_indebido"])

    if patron == "fuera_de_horario":
        ts = _timestamp_fuera_de_horario()
        ip_origen = _ip_interna()
    elif patron == "ip_externa":
        ts = _timestamp_horario_laboral()
        ip_origen = _ip_externa()
    else:  # acceso_indebido: rol sin relación típica con la tabla sensible
        ts = _timestamp_horario_laboral()
        ip_origen = _ip_interna()
        rol = "Soporte"  # rol con bajos privilegios accediendo a datos críticos

    return {
        "timestamp": ts.isoformat(),
        "usuario": usuario,
        "rol": rol,
        "ip_origen": ip_origen,
        "ip_destino": "10.0.0.5",
        "aplicacion": random.choice(APLICACIONES),
        "tabla_afectada": tabla,
        "columna_afectada": columna,
        "tipo_operacion": tipo_operacion,
        "sentencia_sql": _generar_sentencia(tipo_operacion, tabla, columna),
        "es_anomalo": 1,
    }


def generar_dataset(n_filas: int = N_FILAS, proporcion_anomalias: float = PROPORCION_ANOMALIAS) -> pd.DataFrame:
    """
    Genera un DataFrame sintético de transacciones MS-SQL.

    Args:
        n_filas: Número total de filas a generar.
        proporcion_anomalias: Proporción (0-1) de filas marcadas como anómalas.

    Returns:
        pd.DataFrame con las transacciones sintéticas, mezcladas aleatoriamente.
    """
    n_anomalas = max(1, round(n_filas * proporcion_anomalias))
    n_normales = n_filas - n_anomalas

    filas = [_generar_fila_normal() for _ in range(n_normales)]
    filas += [_generar_fila_anomala() for _ in range(n_anomalas)]

    random.shuffle(filas)
    return pd.DataFrame(filas)


def main() -> None:
    df = generar_dataset()
    os.makedirs(os.path.dirname(RUTA_SALIDA), exist_ok=True)
    df.to_csv(RUTA_SALIDA, index=False)
    print(f"Dataset sintético generado: {len(df)} filas -> {RUTA_SALIDA}")
    print(f"Casos anómalos: {int(df['es_anomalo'].sum())} ({df['es_anomalo'].mean():.1%})")


if __name__ == "__main__":
    main()
