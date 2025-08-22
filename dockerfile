FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app

# NO: RUN flask db upgrade

# Usa CMD/ENTRYPOINT para migrar en runtime
CMD sh -c "flask --app wsgi.py db upgrade && gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8080}"
