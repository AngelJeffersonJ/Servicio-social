release: flask --app wsgi.py db upgrade
web: gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8080}