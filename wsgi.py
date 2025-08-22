# wsgi.py
from app import create_app  # importa la factory

app = create_app()  # Gunicorn espera "app"
