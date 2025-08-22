# patch_db.py
import os, sqlite3

db_path = os.path.join("instance", "servicio.db")
print("Usando DB:", db_path)
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Ver columnas actuales
cur.execute("PRAGMA table_info(proyectos)")
cols = {r[1] for r in cur.fetchall()}
print("Columnas actuales en 'proyectos':", sorted(cols))

def add(col, coltype):
    if col not in cols:
        sql = f"ALTER TABLE proyectos ADD COLUMN {col} {coltype}"
        print("->", sql)
        cur.execute(sql)
        cols.add(col)

# Añadir SOLO si faltan (tipos simples para SQLite)
add("nombre_programa",    "TEXT")
add("nombre_dependencia", "TEXT")
add("nombre_responsable", "TEXT")
add("cargo_responsable",  "TEXT")
add("municipio",          "TEXT")
add("estado",             "TEXT")
add("departamento_id",    "INTEGER")
add("responsable_id",     "INTEGER")
add("extras",             "TEXT")  # JSON en SQLite se almacena como TEXT

conn.commit()
conn.close()
print("Parche aplicado.")
