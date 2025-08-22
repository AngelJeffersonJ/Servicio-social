from __future__ import annotations
import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from flask import Flask, redirect, url_for, Response, request, current_app
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

from .models import db, User
from .roles import register_template_utils  # helpers de roles / jinja

login_manager = LoginManager()
migrate = Migrate()


def _normalize_database_url(raw: str) -> str:
    """
    Normaliza DSN para SQLAlchemy:
    - Reescribe 'postgres://' -> 'postgresql+psycopg2://'
    - Añade sslmode=require cuando se usa el host público de Railway (proxy.rlwy.net)
      o cuando se define FORCE_DB_SSL=true.
    """
    if not raw:
        return raw

    # 1) postgres -> postgresql+psycopg2
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg2://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+psycopg2://" + raw[len("postgresql://"):]

    # 2) sslmode=require si corresponde
    u = urlparse(raw)
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    need_ssl = (
        os.environ.get("FORCE_DB_SSL", "").lower() in {"1", "true", "yes"}
        or (u.hostname or "").endswith("proxy.rlwy.net")
        or (u.hostname or "").endswith("railway.app")
    )
    if need_ssl and "sslmode" not in q:
        q["sslmode"] = "require"

    raw = urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))
    return raw


def create_app() -> Flask:
    # Localiza carpetas raíz del proyecto para que encuentre /templates y /static
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )

    # --- Config base
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    # Base de datos: por defecto SQLite en instance/, o bien DATABASE_URL (Railway)
    os.makedirs(app.instance_path, exist_ok=True)
    default_db = "sqlite:///" + os.path.join(app.instance_path, "servicio.db")
    raw_dsn = os.environ.get("DATABASE_URL", default_db)
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(raw_dsn)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Conexión más robusta para Postgres gestionado
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {
        "pool_pre_ping": True,
        "pool_recycle": 300,   # recicla conexiones cada 5 min
    })

    # Rutas absolutas a las plantillas DOCX (carpeta dentro del paquete app/)
    app.config["TEMPLATE_INTERNO"] = os.environ.get(
        "TEMPLATE_INTERNO",
        os.path.join(app.root_path, "templates_docx", "formato interno de proyecto.docx"),
    )
    app.config["TEMPLATE_BIMESTRAL"] = os.environ.get(
        "TEMPLATE_BIMESTRAL",
        os.path.join(app.root_path, "templates_docx", "Reporte_Bimestral_Plantilla.docx"),
    )
    app.config["TEMPLATE_FINAL"] = os.environ.get(
        "TEMPLATE_FINAL",
        os.path.join(app.root_path, "templates_docx", "Reporte_Final_Lleno.docx"),
    )

    # --- DB & Migrations
    db.init_app(app)
    migrate.init_app(app, db)  # usa Flask-Migrate si está instalado

    # Si estás en local sin migraciones aplicadas, descomenta una vez:
    # with app.app_context():
    #     db.create_all()

    # --- Login
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # --- Helpers Jinja (roles/can/is_role)
    register_template_utils(app)

    # Helper para comprobar existencia de endpoints desde plantillas (opcional)
    @app.context_processor
    def _endpoint_helper():
        def has_endpoint(name: str) -> bool:
            return name in current_app.view_functions
        return dict(has_endpoint=has_endpoint)

    # CSRF opcional si no usas Flask-WTF
    app.jinja_env.globals.setdefault("csrf_token", lambda: "")

    # --- Blueprints
    from .views.auth import auth_bp
    from .views.proyectos import proy_bp
    from .views.admin import admin_bp
    from .views.alumnos import alum_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(proy_bp, url_prefix="/proyectos")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(alum_bp, url_prefix="/alumnos")

    try:
        from .views.main import main_bp
        app.register_blueprint(main_bp)
    except Exception:
        pass

    # --- Ruta raíz
    @app.route("/", methods=["GET"])
    def root_index():
        return redirect(url_for("proyectos.lista"))

    # --- 403: evita bucles cuando el 403 proviene de rutas de alumnos
    @app.errorhandler(403)
    def forbidden(e):
        try:
            if getattr(current_user, "is_authenticated", False) and getattr(current_user, "rol", None) == "alumno":
                if request.endpoint and request.endpoint.startswith("alumnos."):
                    return Response("Forbidden", status=403)
                return redirect(url_for("alumnos.mis_documentos"))
        except Exception:
            pass
        return Response("Forbidden", status=403)

    return app
