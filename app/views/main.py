# app/views/main.py
from __future__ import annotations
from flask import Blueprint, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint("main", __name__)

@main_bp.route("/", endpoint="form_view")
@login_required
def form_view():
    rol = getattr(current_user, "rol", None)
    if rol == "alumno":
        return redirect(url_for("alumnos.mis_documentos"))
    return redirect(url_for("proyectos.lista"))

@main_bp.route("/ping")
def ping():
    return "ok", 200
