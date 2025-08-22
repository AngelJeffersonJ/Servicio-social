# wsgi.py
import os

# Intenta: from app import app
try:
    from app import app  # app debe ser una instancia de Flask
except Exception:
    # Fallback: factory pattern
    from app import create_app  # type: ignore
    app = create_app()          # instancia Flask

if __name__ == "__main__":
    # Útil para correr local con: python wsgi.py
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
