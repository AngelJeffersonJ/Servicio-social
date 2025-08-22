# scripts/create_tables.py
import os, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Intenta factory create_app(); si no, usa app global
try:
    from app import create_app
    app = create_app()
except Exception:
    from app import app as _app
    app = _app

from app.models import db

with app.app_context():
    db.create_all()
    print("✔ Tablas creadas en la base configurada por SQLALCHEMY_DATABASE_URI")
