from __future__ import annotations
from flask import current_app
from flask_login import current_user

# Muy simple: define "can" por rol.
# Amplíalo si necesitas permisos más finos.
def _can(user, perm: str) -> bool:
    rol = getattr(user, "rol", None)
    if rol == "admin":
        return True
    if rol in {"jefe", "laboratorista"}:
        # Permisos de proyectos
        if perm.startswith("project."):
            return perm in {"project.read", "project.create", "project.assign"}
        # Permisos admin (solo lectura de listados)
        if perm.startswith("admin."):
            return perm in {"admin.view"}
    if rol == "alumno":
        # No tiene capacidades de admin/proyecto por default
        return False
    return False

def register_template_utils(app):
    @app.context_processor
    def inject_perms():
        return {
            "can": (lambda p: _can(current_user, p)),
            "is_role": (lambda r: getattr(current_user, "rol", None) == r),
        }
