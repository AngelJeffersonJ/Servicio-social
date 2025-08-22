from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.routing import BuildError

from app.models import db, User

auth_bp = Blueprint("auth", __name__)


def _home_por_rol(rol: str) -> str:
    """
    Devuelve el endpoint inicial según rol.
    - alumno -> alumnos.mis_documentos
    - admin  -> admin.index
    - jefe / laboratorista / otros -> proyectos.lista
    """
    if rol == "alumno":
        return "alumnos.mis_documentos"
    if rol == "admin":
        return "admin.index"
    return "proyectos.lista"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        u = User.query.filter_by(email=email).first()
        if not u or not u.check_password(password):
            flash("Credenciales inválidas.", "warning")
            return render_template("auth/login.html", form=request.form)

        login_user(u)

        # Redirección robusta (si un endpoint no existe, cae a proyectos.lista)
        endpoint = _home_por_rol((u.rol or "").strip())
        try:
            return redirect(url_for(endpoint))
        except BuildError:
            return redirect(url_for("proyectos.lista"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
