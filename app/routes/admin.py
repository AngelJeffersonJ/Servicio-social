# app/views/admin.py
from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# ---------------------------------------------------------------------
# Imports tolerantes (no rompen si aún no tienes ciertos modelos)
# ---------------------------------------------------------------------
try:
    from app.models import db, User, Departamento  # type: ignore
except Exception:
    from app.models import db, User  # type: ignore
    Departamento = None  # type: ignore

try:
    from app.models_extra import AlumnoInfo, StaffInfo  # type: ignore
except Exception:
    AlumnoInfo = None  # type: ignore
    StaffInfo = None  # type: ignore


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------
def _roles() -> list[tuple[str, str]]:
    """(valor_en_bd, etiqueta)"""
    return [
        ("alumno", "Alumno"),
        ("laboratorista", "Laboratorista"),
        ("jefe", "Jefe"),
        ("admin", "Administrador"),
    ]


# ---------------------------------------------------------------------
# LISTA DE USUARIOS
# ---------------------------------------------------------------------
@admin_bp.route("/usuarios", endpoint="usuarios_list")
@login_required
def usuarios_list():
    try:
        all_users = User.query.order_by(User.id.desc()).all()
        # Si tu modelo tiene relación 'departamento' configurada, esto sirve:
        users = [(u, getattr(u, "departamento", None)) for u in all_users]
    except Exception:
        users = []
        flash("No se pudieron cargar los usuarios.", "danger")

    return render_template("admin/usuarios_list.html", users=users)


# ---------------------------------------------------------------------
# CREAR USUARIO
# ---------------------------------------------------------------------
@admin_bp.route("/usuarios/nuevo", methods=["GET", "POST"], endpoint="nuevo_usuario")
@login_required
def nuevo_usuario():
    # Cargar departamentos si el modelo existe
    if Departamento is not None:
        try:
            departamentos = Departamento.query.order_by(Departamento.nombre).all()
        except Exception:
            departamentos = []
    else:
        departamentos = []

    roles = _roles()

    if request.method == "POST":
        # ----- Campos base -----
        nombre = (request.form.get("nombre") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        role = (request.form.get("role") or request.form.get("rol") or "alumno").strip()
        depto_id = request.form.get("departamento_id") or None

        # ----- Campos por rol -----
        ap_pat = (request.form.get("apellido_paterno") or "").strip() or None
        ap_mat = (request.form.get("apellido_materno") or "").strip() or None
        no_control = (request.form.get("no_control") or "").strip() or None
        carrera = (request.form.get("carrera") or "").strip() or None
        cargo = (request.form.get("cargo") or "").strip() or None

        # ----- Validaciones -----
        errors: list[str] = []
        if not nombre:
            errors.append("El nombre es obligatorio.")
        if not email:
            errors.append("El email es obligatorio.")
        if not password:
            errors.append("La contraseña es obligatoria.")
        if role not in {r for r, _ in roles}:
            errors.append("Rol inválido.")

        if role == "alumno":
            if not ap_pat:
                errors.append("Apellido paterno es obligatorio para alumnos.")
            if not ap_mat:
                errors.append("Apellido materno es obligatorio para alumnos.")
            if not no_control:
                errors.append("No. de control es obligatorio para alumnos.")
            if not carrera:
                errors.append("Carrera es obligatoria para alumnos.")
        else:
            if not cargo:
                errors.append("Cargo/Puesto es obligatorio para roles distintos a alumno.")

        # email duplicado (si tu modelo tiene UNIQUE, esto solo previene anticipadamente)
        if email:
            try:
                if User.query.filter_by(email=email).first():
                    errors.append("El email ya está registrado.")
            except Exception:
                pass

        if errors:
            for e in errors:
                flash(e, "warning")
            return render_template(
                "admin/usuarios_form.html",
                roles=roles,
                departamentos=departamentos,
                form=request.form,
            )

        # ----- Crear usuario -----
        # OJO: tu modelo usa 'nombre' y 'rol' (no 'name'/'role')
        u = User(nombre=nombre, email=email, rol=role)
        if depto_id and hasattr(u, "departamento_id"):
            try:
                u.departamento_id = int(depto_id)  # type: ignore[attr-defined]
            except Exception:
                pass

        if hasattr(u, "set_password"):
            u.set_password(password)
        else:
            u.password = password  # type: ignore[attr-defined]  # si aún no usas hashing

        db.session.add(u)
        db.session.flush()  # para obtener u.id

        # ----- Info extendida (opcional) -----
        try:
            if role == "alumno" and AlumnoInfo:
                ai = AlumnoInfo(
                    user_id=u.id,
                    nombre=nombre,
                    apellido_paterno=ap_pat,
                    apellido_materno=ap_mat,
                    no_control=no_control,
                    carrera=carrera,
                )
                db.session.add(ai)
            elif role != "alumno" and StaffInfo:
                si = StaffInfo(
                    user_id=u.id,
                    nombre=nombre,
                    apellido_paterno=ap_pat,
                    apellido_materno=ap_mat,
                    cargo=cargo or "",
                )
                db.session.add(si)
        except Exception:
            # No bloquear el alta si las tablas extra fallan/no existen
            pass

        # ----- Commit -----
        try:
            db.session.commit()
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo crear: email duplicado u otra restricción de unicidad.", "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al crear el usuario en la base de datos.", "danger")

    # GET
    return render_template("admin/usuarios_form.html", roles=roles, departamentos=departamentos)


# ---------------------------------------------------------------------
# EDITAR USUARIO
# ---------------------------------------------------------------------
@admin_bp.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"], endpoint="usuarios_edit")
@login_required
def usuarios_edit(uid: int):
    u = User.query.get_or_404(uid)

    # Departamentos
    if Departamento is not None:
        try:
            deps = Departamento.query.order_by(Departamento.nombre).all()
        except Exception:
            deps = []
    else:
        deps = []

    # Info extendida actual
    ai = None
    si = None
    try:
        if AlumnoInfo:
            ai = AlumnoInfo.query.filter_by(user_id=u.id).first()
        if StaffInfo:
            si = StaffInfo.query.filter_by(user_id=u.id).first()
    except Exception:
        pass

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        role = (request.form.get("role") or request.form.get("rol") or u.rol).strip()
        password = (request.form.get("password") or "").strip()
        dept_id = request.form.get("departamento_id") or None

        ap_pat = (request.form.get("apellido_paterno") or "").strip() or None
        ap_mat = (request.form.get("apellido_materno") or "").strip() or None
        no_ctrl = (request.form.get("no_control") or "").strip() or None
        carrera = (request.form.get("carrera") or "").strip() or None
        cargo = (request.form.get("cargo") or "").strip() or None

        errors: list[str] = []
        if not nombre:
            errors.append("El nombre es obligatorio.")
        if not email:
            errors.append("El email es obligatorio.")
        if role not in {"alumno", "laboratorista", "jefe", "admin"}:
            errors.append("Rol inválido.")

        if role == "alumno":
            if not ap_pat:
                errors.append("Apellido paterno es obligatorio para alumnos.")
            if not ap_mat:
                errors.append("Apellido materno es obligatorio para alumnos.")
            if not no_ctrl:
                errors.append("No. de control es obligatorio para alumnos.")
            if not carrera:
                errors.append("Carrera es obligatoria para alumnos.")
        else:
            if not cargo:
                errors.append("Cargo/Puesto es obligatorio para roles distintos a alumno.")

        # email duplicado si cambió
        if email and email != u.email:
            try:
                if User.query.filter_by(email=email).first():
                    errors.append("El email ya está registrado.")
            except Exception:
                pass

        if errors:
            for e in errors:
                flash(e, "warning")
            return render_template("admin/usuarios_edit.html", u=u, deps=deps)

        # Actualizar usuario
        u.nombre = nombre
        u.email = email
        u.rol = role
        if dept_id and hasattr(u, "departamento_id"):
            try:
                u.departamento_id = int(dept_id)
            except Exception:
                pass

        if password:
            if hasattr(u, "set_password"):
                u.set_password(password)
            else:
                u.password = password  # type: ignore[attr-defined]

        # Sincronizar info extendida
        try:
            if role == "alumno":
                # Asegurar AlumnoInfo
                if AlumnoInfo:
                    if ai is None:
                        ai = AlumnoInfo(user_id=u.id)
                        db.session.add(ai)
                    ai.nombre = nombre
                    ai.apellido_paterno = ap_pat
                    ai.apellido_materno = ap_mat
                    ai.no_control = no_ctrl
                    ai.carrera = carrera
                # Borrar StaffInfo si existía
                if StaffInfo and si is not None:
                    db.session.delete(si)
                    si = None
            else:
                # Staff
                if StaffInfo:
                    if si is None:
                        si = StaffInfo(user_id=u.id)
                        db.session.add(si)
                    si.nombre = nombre
                    si.apellido_paterno = ap_pat
                    si.apellido_materno = ap_mat
                    si.cargo = cargo or ""
                # Borrar AlumnoInfo si existía
                if AlumnoInfo and ai is not None:
                    db.session.delete(ai)
                    ai = None
        except Exception:
            pass

        try:
            db.session.commit()
            flash("Usuario actualizado correctamente.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo actualizar: conflicto de unicidad (email).", "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al actualizar el usuario en la base de datos.", "danger")

    # GET
    return render_template("admin/usuarios_edit.html", u=u, deps=deps)


# ---------------------------------------------------------------------
# ELIMINAR USUARIO
# ---------------------------------------------------------------------
@admin_bp.route("/usuarios/<int:uid>/eliminar", methods=["POST"], endpoint="usuarios_delete")
@login_required
def usuarios_delete(uid: int):
    u = User.query.get_or_404(uid)

    # Eliminar info extendida primero
    try:
        if AlumnoInfo:
            ai = AlumnoInfo.query.filter_by(user_id=u.id).first()
            if ai:
                db.session.delete(ai)
        if StaffInfo:
            si = StaffInfo.query.filter_by(user_id=u.id).first()
            if si:
                db.session.delete(si)
    except Exception:
        pass

    db.session.delete(u)

    try:
        db.session.commit()
        flash("Usuario eliminado correctamente.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Error al eliminar el usuario.", "danger")

    return redirect(url_for("admin.usuarios_list"))


# ---------------------------------------------------------------------
# LISTA DE DEPARTAMENTOS (para evitar 404 en el navbar)
# ---------------------------------------------------------------------
@admin_bp.route("/departamentos", endpoint="departamentos_list")
@login_required
def departamentos_list():
    deps = []
    if Departamento is not None:
        try:
            deps = Departamento.query.order_by(Departamento.nombre).all()
        except Exception:
            flash("No se pudieron cargar los departamentos.", "danger")
    else:
        flash("El modelo Departamento no está definido todavía.", "warning")

    return render_template("admin/departamentos_list.html", deps=deps)
