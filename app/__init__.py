from __future__ import annotations
import os
from flask import Flask, redirect, url_for, Response, request, current_app
from flask_login import LoginManager, current_user
from flask_migrate import Migrate

from .models import db, User
from .roles import register_template_utils  # helpers de roles / jinja

login_manager = LoginManager()
migrate = Migrate()


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

    # Base de datos en la carpeta instance/
    os.makedirs(app.instance_path, exist_ok=True)
    default_db = "sqlite:///" + os.path.join(app.instance_path, "servicio.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", default_db)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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
    with app.app_context():
        from . import models  # asegura que Alembic vea los modelos
        db.create_all()
    migrate.init_app(app, db)

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

    # CSRF opcional “vacío” si no usas Flask-WTF (evita errores en forms con {{ csrf_token() }})
    app.jinja_env.globals.setdefault("csrf_token", lambda: "")

    # --- Blueprints (registro explícito con url_prefix)
    from .views.auth import auth_bp
    from .views.proyectos import proy_bp
    from .views.admin import admin_bp
    from .views.alumnos import alum_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(proy_bp, url_prefix="/proyectos")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(alum_bp, url_prefix="/alumnos")

    # (Opcional) otros blueprints si existen
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
                # Si el 403 viene de vistas de alumnos, no hagas redirect para no ciclar
                if request.endpoint and request.endpoint.startswith("alumnos."):
                    return Response("Forbidden", status=403)
                return redirect(url_for("alumnos.mis_documentos"))
        except Exception:
            pass
        return Response("Forbidden", status=403)

    return app
