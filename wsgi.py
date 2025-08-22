try:
    from app import create_app
    app = create_app()
except Exception:
    from app import app as app
