# scripts/migrate_sqlite_to_postgres.py
import os
import sqlite3
import psycopg2
from contextlib import closing

SQLITE_PATH = os.environ.get("SQLITE_PATH", "servicio.db")
PG_DSN = os.environ["DATABASE_URL"]  # postgresql://USER:PASS@HOST:PORT/DB

# Orden que respeta FKs típicas
TABLE_ORDER = [
    "departamentos",
    "users",
    "proyectos",
    "alumnos_proyectos",
    "reportes_bimestrales",
    "evaluaciones_finales",
]

def main():
    with closing(sqlite3.connect(SQLITE_PATH)) as sconn, closing(psycopg2.connect(PG_DSN)) as pconn:
        sconn.row_factory = sqlite3.Row
        pconn.autocommit = False
        with pconn.cursor() as pc:
            # Evita checar FKs mientras insertamos en bulk
            try:
                pc.execute("SET session_replication_role = replica;")
            except Exception:
                pass

            for table in TABLE_ORDER:
                cur = sconn.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                if not rows:
                    print(f"➡ {table}: 0 filas (nada que migrar)")
                    continue

                cols = [d[0] for d in cur.description]
                placeholders = ", ".join(["%s"] * len(cols))
                col_list = ", ".join([f'"{c}"' for c in cols])

                # Limpia destino primero (opcional)
                pc.execute(f'DELETE FROM "{table}";')

                for r in rows:
                    pc.execute(
                        f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders});',
                        [r[c] for c in cols],
                    )

                print(f"✔ {table}: {len(rows)} filas migradas")

            try:
                pc.execute("SET session_replication_role = DEFAULT;")
            except Exception:
                pass

            # Ajusta secuencias de IDs
            for t in TABLE_ORDER:
                try:
                    pc.execute(
                        f"SELECT setval(pg_get_serial_sequence('\"{t}\"','id'), "
                        f"(SELECT COALESCE(MAX(id),1) FROM \"{t}\"));"
                    )
                except Exception:
                    pass

        pconn.commit()
        print("✅ Migración completada.")

if __name__ == "__main__":
    main()
