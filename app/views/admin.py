# app/views/admin.py
from __future__ import annotations
from jinja2 import TemplateNotFound
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Modelos base
try:
    from app.models import db, User, Departamento  # type: ignore
except Exception:  # pragma: no cover
    from app.models import db, User  # type: ignore
    Departamento = None  # type: ignore

# Modelos extendidos (opcionales)
try:
    from app.models_extra import AlumnoInfo, StaffInfo  # type: ignore
except Exception:  # pragma: no cover
    AlumnoInfo = None  # type: ignore
    StaffInfo = None  # type: ignore

# Importante: este BP trae su propio url_prefix="/admin"
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------- Utilidades ----------------
def _roles() -> list[tuple[str, str]]:
    return [
        ("alumno", "Alumno"),
        ("laboratorista", "Laboratorista"),
        ("jefe", "Jefe"),
        ("admin", "Administrador"),
    ]


def _rol_valido(valor: str) -> bool:
    return valor in {k for k, _ in _roles()}


def _solo_admin():
    if not getattr(current_user, "rol", None) == "admin":
        abort(403)


def _set_if_has(obj, field: str, value):
    """Setea obj.field=value sólo si obj tiene ese atributo (para esquemas variables)."""
    if hasattr(obj, field):
        setattr(obj, field, value)


# ---------------- Dashboard ----------------
@admin_bp.route("/", endpoint="index")
@login_required
def index():
    try:
        return render_template("admin/index.html")
    except TemplateNotFound:
        return redirect(url_for("admin.usuarios_list"))


# ---------------- Departamentos ----------------
@admin_bp.route("/departamentos", methods=["GET"], endpoint="departamentos_list")
@login_required
def departamentos_list():
    deps = Departamento.query.order_by(Departamento.id.desc()).all()
    return render_template("admin/departamentos_list.html", deps=deps)


@admin_bp.route("/departamentos/nuevo", methods=["GET", "POST"], endpoint="departamentos_new")
@login_required
def departamentos_new():
    _solo_admin()

    # SOLO usuarios con rol "jefe"
    jefes = User.query.filter_by(rol="jefe").order_by(User.nombre).all()

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        jefe_id = request.form.get("jefe_id", type=int)

        if not nombre:
            flash("El nombre es obligatorio.", "warning")
            return render_template("admin/departamentos_new.html", jefes=jefes, form=request.form)

        # Validar que el jefe elegido sea realmente un usuario con rol 'jefe'
        jefe_obj = None
        if jefe_id:
            jefe_obj = User.query.filter_by(id=jefe_id, rol="jefe").first()
            if not jefe_obj:
                flash("El jefe seleccionado no es válido (debe tener rol 'jefe').", "warning")
                return render_template("admin/departamentos_new.html", jefes=jefes, form=request.form)

        dep = Departamento(nombre=nombre, jefe_id=(jefe_obj.id if jefe_obj else None))
        db.session.add(dep)
        try:
            db.session.commit()
            flash("Departamento creado.", "success")
            return redirect(url_for("admin.departamentos_list"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo crear el departamento.", "danger")

    return render_template("admin/departamentos_new.html", jefes=jefes)


@admin_bp.route("/departamentos/<int:did>/editar", methods=["GET","POST"], endpoint="departamentos_edit")
@login_required
def departamentos_edit(did: int):
    _solo_admin()

    d = Departamento.query.get_or_404(did)
    # SOLO usuarios con rol "jefe"
    jefes = User.query.filter_by(rol="jefe").order_by(User.nombre).all()

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        jefe_id = request.form.get("jefe_id", type=int)

        if not nombre:
            flash("El nombre es obligatorio.", "warning")
            return render_template("admin/departamentos_edit.html", d=d, jefes=jefes)

        # Validar jefe
        jefe_obj = None
        if jefe_id:
            jefe_obj = User.query.filter_by(id=jefe_id, rol="jefe").first()
            if not jefe_obj:
                flash("El jefe seleccionado no es válido (debe tener rol 'jefe').", "warning")
                return render_template("admin/departamentos_edit.html", d=d, jefes=jefes)

        d.nombre = nombre
        d.jefe_id = jefe_obj.id if jefe_obj else None

        try:
            db.session.commit()
            flash("Departamento actualizado.", "success")
            return redirect(url_for("admin.departamentos_list"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo actualizar el departamento.", "danger")

    return render_template("admin/departamentos_edit.html", d=d, jefes=jefes)


@admin_bp.route("/departamentos/<int:did>/eliminar", methods=["POST"], endpoint="departamentos_eliminar")
@login_required
def departamentos_eliminar(did: int):
    _solo_admin()

    d = Departamento.query.get_or_404(did)
    db.session.delete(d)
    try:
        db.session.commit()
        flash("Departamento eliminado.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("No se pudo eliminar (puede tener relaciones activas).", "warning")

    return redirect(url_for("admin.departamentos_list"))


# ---------------- Usuarios ----------------
@admin_bp.route("/usuarios", endpoint="usuarios_list")
@login_required
def usuarios_list():
    _solo_admin()
    try:
        all_users = User.query.order_by(User.id.desc()).all()
        users = [(u, getattr(u, "departamento", None)) for u in all_users]
    except Exception:
        users = []
    return render_template("admin/usuarios_list.html", users=users)


@admin_bp.route("/usuarios/nuevo", methods=["GET", "POST"], endpoint="usuarios_new")
@login_required
def usuarios_new():
    _solo_admin()

    # deps
    if Departamento is not None:
        try:
            departamentos = Departamento.query.order_by(Departamento.nombre).all()
        except Exception:
            departamentos = []
    else:
        departamentos = []

    roles = _roles()

    if request.method == "POST":
        nombre   = (request.form.get("nombre") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        role     = (request.form.get("role") or "alumno").strip()
        dept_id_raw = request.form.get("departamento_id") or None

        # alumno
        ap_pat  = (request.form.get("apellido_paterno") or "").strip()
        ap_mat  = (request.form.get("apellido_materno") or "").strip()
        no_ctrl = (request.form.get("no_control") or "").strip()
        carrera = (request.form.get("carrera") or "").strip()
        # staff
        cargo   = (request.form.get("cargo") or "").strip()

        errors: list[str] = []
        if not nombre:   errors.append("El nombre es obligatorio.")
        if not email:    errors.append("El email es obligatorio.")
        if not password: errors.append("La contraseña es obligatoria.")
        if not _rol_valido(role): errors.append("Rol inválido.")

        if role == "alumno":
            if not ap_pat:  errors.append("Apellido paterno es obligatorio para alumnos.")
            if not ap_mat:  errors.append("Apellido materno es obligatorio para alumnos.")
            if not no_ctrl: errors.append("No. de control es obligatorio para alumnos.")
            if not carrera: errors.append("Carrera es obligatoria para alumnos.")
        else:
            if not cargo:   errors.append("Cargo/Puesto es obligatorio para roles distintos a alumno.")

        if email:
            try:
                if User.query.filter_by(email=email).first():
                    errors.append("El email ya está registrado.")
            except Exception:
                pass

        if errors:
            for e in errors: flash(e, "warning")
            return render_template("admin/usuarios_form.html",
                                   roles=roles, departamentos=departamentos, form=request.form)

        u = User(nombre=nombre, email=email, rol=role)
        if dept_id_raw and hasattr(u, "departamento_id"):
            try:
                u.departamento_id = int(dept_id_raw)  # type: ignore[attr-defined]
            except Exception:
                pass
        u.set_password(password)

        # sincroniza SIEMPRE en la propia tabla users si existen esas columnas
        _set_if_has(u, "apellido_paterno", ap_pat or None)
        _set_if_has(u, "apellido_materno", ap_mat or None)
        _set_if_has(u, "no_control", no_ctrl or None)
        _set_if_has(u, "carrera", carrera or None)
        _set_if_has(u, "cargo", cargo or None)

        db.session.add(u)
        db.session.flush()  # u.id

        # modelos extendidos, si los tienes
        try:
            if role == "alumno" and AlumnoInfo:
                ai = AlumnoInfo(
                    user_id=u.id,
                    nombre=nombre,
                    apellido_paterno=ap_pat,
                    apellido_materno=ap_mat,
                    no_control=no_ctrl,
                    carrera=carrera,
                )
                db.session.add(ai)
            elif role != "alumno" and StaffInfo:
                si = StaffInfo(
                    user_id=u.id,
                    nombre=nombre,
                    apellido_paterno=ap_pat,
                    apellido_materno=ap_mat,
                    cargo=cargo,
                )
                db.session.add(si)
        except Exception:
            pass

        try:
            db.session.commit()
            flash("Usuario creado correctamente.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo crear: el email ya existe o hay conflicto de unicidad.", "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error de base de datos al crear usuario.", "danger")

    return render_template("admin/usuarios_form.html", roles=roles, departamentos=departamentos)


@admin_bp.route("/usuarios/<int:uid>/editar", methods=["GET", "POST"], endpoint="usuarios_edit")
@login_required
def usuarios_edit(uid: int):
    _solo_admin()
    u = User.query.get_or_404(uid)

    if Departamento is not None:
        try:
            deps = Departamento.query.order_by(Departamento.nombre).all()
        except Exception:
            deps = []
    else:
        deps = []

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
        nombre   = (request.form.get("nombre") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()
        role     = (request.form.get("role") or request.form.get("rol") or u.rol).strip()
        password = (request.form.get("password") or "").strip()
        dept_id  = request.form.get("departamento_id") or None

        ap_pat  = (request.form.get("apellido_paterno") or "").strip() or None
        ap_mat  = (request.form.get("apellido_materno") or "").strip() or None
        no_ctrl = (request.form.get("no_control") or "").strip() or None
        carrera = (request.form.get("carrera") or "").strip() or None
        cargo   = (request.form.get("cargo") or "").strip() or None

        errors = []
        if not nombre: errors.append("El nombre es obligatorio.")
        if not email:  errors.append("El email es obligatorio.")
        if role not in {"alumno", "laboratorista", "jefe", "admin"}:
            errors.append("Rol inválido.")
        if role == "alumno":
            if not ap_pat:  errors.append("Apellido paterno es obligatorio para alumnos.")
            if not ap_mat:  errors.append("Apellido materno es obligatorio para alumnos.")
            if not no_ctrl: errors.append("No. de control es obligatorio para alumnos.")
            if not carrera: errors.append("Carrera es obligatoria para alumnos.")
        else:
            if not cargo:   errors.append("Cargo/Puesto es obligatorio para roles distintos a alumno.")

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

        # base
        u.nombre = nombre
        u.email  = email
        u.rol    = role
        if dept_id and hasattr(u, "departamento_id"):
            try:
                u.departamento_id = int(dept_id)
            except Exception:
                pass
        if password:
            u.set_password(password)

        # sincroniza SIEMPRE en tabla users (si existen columnas)
        _set_if_has(u, "apellido_paterno", ap_pat)
        _set_if_has(u, "apellido_materno", ap_mat)
        _set_if_has(u, "no_control", no_ctrl)
        _set_if_has(u, "carrera", carrera)
        _set_if_has(u, "cargo", cargo)

        # extendidos
        try:
            if role == "alumno":
                if AlumnoInfo:
                    if ai is None:
                        ai = AlumnoInfo(user_id=u.id)
                        db.session.add(ai)
                    ai.nombre = nombre
                    ai.apellido_paterno = ap_pat
                    ai.apellido_materno = ap_mat
                    ai.no_control = no_ctrl
                    ai.carrera = carrera
                if StaffInfo and si is not None:
                    db.session.delete(si); si = None
            else:
                if StaffInfo:
                    if si is None:
                        si = StaffInfo(user_id=u.id)
                        db.session.add(si)
                    si.nombre = nombre
                    si.apellido_paterno = ap_pat
                    si.apellido_materno = ap_mat
                    si.cargo = cargo or ""
                if AlumnoInfo and ai is not None:
                    db.session.delete(ai); ai = None
        except Exception:
            pass

        # bloque robusto de commit con manejo de errores
        try:
            db.session.commit()
            flash("Usuario actualizado correctamente.", "success")
            return redirect(url_for("admin.usuarios_list"))
        except IntegrityError:
            db.session.rollback()
            import traceback
            print("IntegrityError en usuarios_edit:\n", traceback.format_exc())
            flash("No se pudo actualizar: conflicto de unicidad (email).", "danger")
        except SQLAlchemyError:
            db.session.rollback()
            import traceback
            print("SQLAlchemyError en usuarios_edit:\n", traceback.format_exc())
            flash("Error al actualizar el usuario en la base de datos.", "danger")

    return render_template("admin/usuarios_edit.html", u=u, deps=deps)



@admin_bp.route("/usuarios/<int:uid>/eliminar", methods=["POST"], endpoint="usuarios_delete")
@login_required
def usuarios_delete(uid: int):
    _solo_admin()
    u = User.query.get_or_404(uid)
    try:
        db.session.delete(u)
        db.session.commit()
        flash("Usuario eliminado.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Error al eliminar el usuario.", "danger")
    return redirect(url_for("admin.usuarios_list"))
