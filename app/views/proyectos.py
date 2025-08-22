# app/views/proyectos.py
from __future__ import annotations
from typing import Optional, Dict, Any

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models import db, Proyecto, User, AlumnoProyecto, ReporteBimestral

proy_bp = Blueprint("proyectos", __name__)


# ---------------- Utilidades ----------------
def _val(v: Optional[str]) -> str:
    return (v or "").strip()


def _es_responsable_o_admin(p: Proyecto) -> bool:
    """Permite admin/jefe/laboratorista o el propio responsable del proyecto."""
    rol = getattr(current_user, "rol", None)
    if rol in {"admin", "jefe", "laboratorista"}:
        return True
    if getattr(p, "responsable_id", None) and p.responsable_id == current_user.id:
        return True
    return False


def _clamp_0_4(v: Optional[int]) -> Optional[int]:
    """Normaliza calificaciones a {0,1,2,3,4} o None si no viene."""
    if v is None:
        return None
    try:
        n = int(v)
    except Exception:
        return None
    if n < 0:
        n = 0
    if n > 4:
        n = 4
    return n


def _defaults_bimestre(proj: Proyecto) -> Dict[str, str]:
    """Semillas para el formulario NUEVO: supervisor/puesto del proyecto, resto vacío."""
    sup = proj.nombre_responsable or (proj.responsable_user.nombre if getattr(proj, "responsable_user", None) else "")
    cargo = proj.cargo_responsable or ""
    return {
        "dia1": "", "mes1": "", "ano1": "",
        "dia2": "", "mes2": "", "ano2": "",
        "nombre_supervisor": sup,
        "puesto_supervisor": cargo,
        "observaciones_responsable": "",
    }


def _rb_vals_from(mapping: Dict[str, Any]) -> Dict[str, Optional[int]]:
    """Extrae resp_1..resp_7 como enteros (o None) desde un dict (request.form o valores del modelo)."""
    out: Dict[str, Optional[int]] = {}
    for i in range(1, 8):
        raw = mapping.get(f"resp_{i}")
        if raw is None or raw == "":
            out[f"resp_{i}"] = None
        else:
            try:
                out[f"resp_{i}"] = _clamp_0_4(int(raw))
            except Exception:
                out[f"resp_{i}"] = None
    return out


# ------------- LISTA -------------
@proy_bp.route("/")
@login_required
def lista():
    proyectos = Proyecto.query.order_by(Proyecto.id.desc()).all()
    rows = []
    for p in proyectos:
        programa = p.nombre or p.nombre_programa or ""
        rows.append(
            {
                "id": p.id,
                "programa": programa,
                "dependencia": p.nombre_dependencia or "",
                "responsable": p.nombre_responsable
                or (p.responsable_user.nombre if getattr(p, "responsable_user", None) else ""),
                "cargo": p.cargo_responsable or "",
                "municipio": p.municipio or "",
                "estado": p.estado or "",
            }
        )
    return render_template("proyectos/lista.html", rows=rows)


# ------------- NUEVO -------------
@proy_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if request.method == "POST":
        programa = _val(request.form.get("nombre_programa"))
        dependencia = _val(request.form.get("nombre_dependencia"))
        responsable = _val(request.form.get("nombre_responsable"))
        cargo = _val(request.form.get("cargo_responsable"))
        municipio = _val(request.form.get("municipio"))
        estado = _val(request.form.get("estado"))

        errors = []
        if not programa:
            errors.append("El nombre del programa es obligatorio.")
        if not dependencia:
            errors.append("La dependencia es obligatoria.")
        if not responsable:
            errors.append("El nombre del responsable es obligatorio.")
        if not cargo:
            errors.append("El cargo del responsable es obligatorio.")
        if errors:
            for e in errors:
                flash(e, "warning")
            return render_template("proyectos/form.html", form=request.form)

        p = Proyecto(
            nombre=programa,
            nombre_programa=programa,
            nombre_dependencia=dependencia,
            nombre_responsable=responsable,
            cargo_responsable=cargo,
            municipio=municipio or None,
            estado=estado or None,
        )
        db.session.add(p)
        try:
            db.session.commit()
            flash("Proyecto creado correctamente.", "success")
            return redirect(url_for("proyectos.lista"))
        except IntegrityError:
            db.session.rollback()
            flash(
                "No se pudo crear: conflicto de unicidad o restricción en la base.",
                "warning",
            )
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al crear el proyecto en la base de datos.", "danger")

    return render_template("proyectos/form.html")


# ------------- EDITAR -------------
@proy_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id: int):
    p = Proyecto.query.get_or_404(id)

    if request.method == "POST":
        programa = _val(request.form.get("nombre_programa"))
        dependencia = _val(request.form.get("nombre_dependencia"))
        responsable = _val(request.form.get("nombre_responsable"))
        cargo = _val(request.form.get("cargo_responsable"))
        municipio = _val(request.form.get("municipio"))
        estado = _val(request.form.get("estado"))

        errors = []
        if not programa:
            errors.append("El nombre del programa es obligatorio.")
        if not dependencia:
            errors.append("La dependencia es obligatoria.")
        if not responsable:
            errors.append("El nombre del responsable es obligatorio.")
        if not cargo:
            errors.append("El cargo del responsable es obligatorio.")
        if errors:
            for e in errors:
                flash(e, "warning")
            fake = type("X", (), {})()
            fake.nombre_programa = programa or (p.nombre_programa or p.nombre)
            fake.nombre_dependencia = dependencia or p.nombre_dependencia
            fake.nombre_responsable = responsable or p.nombre_responsable
            fake.cargo_responsable = cargo or p.cargo_responsable
            fake.municipio = municipio or (p.municipio or "")
            fake.estado = estado or (p.estado or "")
            return render_template("proyectos/form.html", proyecto=fake)

        # sincronizamos campos
        p.nombre = programa
        p.nombre_programa = programa
        p.nombre_dependencia = dependencia
        p.nombre_responsable = responsable
        p.cargo_responsable = cargo
        p.municipio = municipio or None
        p.estado = estado or None

        try:
            db.session.commit()
            flash("Proyecto actualizado correctamente.", "success")
            return redirect(url_for("proyectos.lista"))
        except IntegrityError:
            db.session.rollback()
            flash(
                "No se pudo actualizar: conflicto de unicidad o restricción.",
                "warning",
            )
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al actualizar el proyecto en la base de datos.", "danger")

    fake = type("X", (), {})()
    fake.nombre_programa = p.nombre_programa or p.nombre or ""
    fake.nombre_dependencia = p.nombre_dependencia or ""
    fake.nombre_responsable = p.nombre_responsable or (
        p.responsable_user.nombre if getattr(p, "responsable_user", None) else ""
    )
    fake.cargo_responsable = p.cargo_responsable or ""
    fake.municipio = p.municipio or ""
    fake.estado = p.estado or ""
    return render_template("proyectos/form.html", proyecto=fake)


# ------------- ELIMINAR -------------
@proy_bp.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar(id: int):
    p = Proyecto.query.get_or_404(id)
    db.session.delete(p)
    try:
        db.session.commit()
        flash("Proyecto eliminado correctamente.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("No se pudo eliminar el proyecto (relaciones o restricciones).", "warning")
    return redirect(url_for("proyectos.lista"))


# ------------- DETALLE -------------
@proy_bp.route("/detalle/<int:id>")
@login_required
def detalle(id: int):
    p = Proyecto.query.get_or_404(id)
    data = {
        "id": p.id,
        "programa": p.nombre or p.nombre_programa or "",
        "dependencia": p.nombre_dependencia or "",
        "responsable": p.nombre_responsable
        or (p.responsable_user.nombre if getattr(p, "responsable_user", None) else ""),
        "cargo": p.cargo_responsable or "",
        "municipio": p.municipio or "",
        "estado": p.estado or "",
    }
    return render_template("proyectos/detalle.html", proyecto=data)


# =========================================================
#      ASIGNAR ALUMNO A PROYECTO
# =========================================================
@proy_bp.route("/asignar", methods=["GET", "POST"], endpoint="asignar_alumno")
@login_required
def asignar_alumno():
    # Permisos básicos
    rol = getattr(current_user, "rol", None)
    if rol not in {"admin", "jefe", "laboratorista"}:
        flash("No tienes permisos para asignar alumnos.", "danger")
        return redirect(url_for("proyectos.lista"))

    # Alumnos (siempre todos)
    alumnos = User.query.filter_by(rol="alumno").order_by(User.nombre).all()

    # Proyectos según rol:
    q = Proyecto.query
    if rol == "laboratorista":
        # Solo proyectos donde el usuario es responsable
        q = q.filter(Proyecto.responsable_id == current_user.id)
    elif rol == "jefe":
        # Si ambos tienen departamento_id, filtramos; si no, mostramos todos
        dep_id = getattr(current_user, "departamento_id", None)
        if dep_id:
            q = q.filter(Proyecto.departamento_id == dep_id)
    proyectos = q.order_by(Proyecto.nombre).all()

    if request.method == "POST":
        alumno_id = request.form.get("alumno_id", type=int)
        proyecto_id = request.form.get("proyecto_id", type=int)

        if not alumno_id or not proyecto_id:
            flash("Selecciona alumno y proyecto.", "warning")
            return render_template(
                "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
            )

        if not User.query.get(alumno_id):
            flash("Alumno no válido.", "danger")
            return render_template(
                "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
            )
        p = Proyecto.query.get(proyecto_id)
        if not p:
            flash("Proyecto no válido.", "danger")
            return render_template(
                "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
            )

        # Restringimos nuevamente por seguridad
        if rol == "laboratorista" and p.responsable_id != current_user.id:
            flash("No puedes asignar alumnos a proyectos ajenos.", "warning")
            return render_template(
                "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
            )
        if rol == "jefe":
            dep_id = getattr(current_user, "departamento_id", None)
            if dep_id and p.departamento_id != dep_id:
                flash("Ese proyecto no pertenece a tu departamento.", "warning")
                return render_template(
                    "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
                )

        # evita duplicados por constraint uq_user_proyecto
        exists = AlumnoProyecto.query.filter_by(
            user_id=alumno_id, proyecto_id=proyecto_id
        ).first()
        if exists:
            flash("Ese alumno ya está asignado a ese proyecto.", "info")
            return render_template(
                "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
            )

        ap = AlumnoProyecto(user_id=alumno_id, proyecto_id=proyecto_id)
        db.session.add(ap)
        try:
            db.session.commit()
            flash("Asignación creada.", "success")
            return redirect(url_for("proyectos.lista"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo asignar (restricción de BD).", "danger")

    return render_template(
        "proyectos/asignar.html", alumnos=alumnos, proyectos=proyectos
    )


# =========================================================
#      ASIGNAR JEFE / LABORATORISTA A PROYECTO
# =========================================================
@proy_bp.route("/asignar-staff", methods=["GET", "POST"], endpoint="asignar_staff")
@login_required
def asignar_staff():
    # Solo admin / jefe
    if getattr(current_user, "rol", None) not in {"admin", "jefe"}:
        flash("Sin permisos para asignar personal a proyectos.", "warning")
        return redirect(url_for("proyectos.lista"))

    proyectos = Proyecto.query.order_by(Proyecto.nombre).all()
    staff = (
        User.query.filter(User.rol.in_(["jefe", "laboratorista"]))
        .order_by(User.nombre)
        .all()
    )

    if request.method == "POST":
        proyecto_id = request.form.get("proyecto_id", type=int)
        responsable_id = request.form.get("responsable_id", type=int)

        if not proyecto_id or not responsable_id:
            flash("Selecciona proyecto y responsable.", "warning")
            return render_template(
                "proyectos/asignar_staff.html", proyectos=proyectos, staff=staff
            )

        p = Proyecto.query.get(proyecto_id)
        r = User.query.get(responsable_id)
        if not p or not r:
            flash("Selección inválida.", "danger")
            return render_template(
                "proyectos/asignar_staff.html", proyectos=proyectos, staff=staff
            )

        # Seteamos responsable del proyecto y opcionalmente el nombre/cargo de texto
        p.responsable_id = r.id
        p.nombre_responsable = r.nombre or p.nombre_responsable
        if getattr(r, "rol", "") == "jefe":
            p.cargo_responsable = "Jefe de Departamento"
        elif getattr(r, "rol", "") == "laboratorista":
            p.cargo_responsable = "Laboratorista"

        try:
            db.session.commit()
            flash("Responsable asignado al proyecto.", "success")
            return redirect(url_for("proyectos.lista"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo asignar el responsable.", "danger")

    return render_template("proyectos/asignar_staff.html", proyectos=proyectos, staff=staff)


# =========================================================
#      SELECTOR PARA CAPTURAR BIMESTRAL (1/2/3)
# =========================================================
@proy_bp.route("/reportes/selector", methods=["GET", "POST"], endpoint="reportes_selector")
@login_required
def reportes_selector():
    """Pantalla simple para elegir Alumno + Proyecto y saltar a bimestres_list."""
    rol = getattr(current_user, "rol", None)
    if rol not in {"admin", "jefe", "laboratorista"}:
        flash("Sin permisos para capturar reportes.", "warning")
        return redirect(url_for("proyectos.lista"))

    alumnos = User.query.filter_by(rol="alumno").order_by(User.nombre).all()

    # Proyectos visibles según rol
    q = Proyecto.query
    if rol == "laboratorista":
        q = q.filter(Proyecto.responsable_id == current_user.id)
    elif rol == "jefe":
        dep_id = getattr(current_user, "departamento_id", None)
        if dep_id:
            q = q.filter(Proyecto.departamento_id == dep_id)
    proyectos = q.order_by(Proyecto.nombre).all()

    if request.method == "POST":
        alumno_id = request.form.get("alumno_id", type=int)
        proyecto_id = request.form.get("proyecto_id", type=int)
        if alumno_id and proyecto_id:
            return redirect(
                url_for(
                    "proyectos.bimestres_list",
                    alumno_id=alumno_id,
                    proyecto_id=proyecto_id,
                )
            )
        flash("Selecciona alumno y proyecto.", "warning")

    return render_template(
        "proyectos/reportes_selector.html", alumnos=alumnos, proyectos=proyectos
    )


# =========================================================
#      REPORTE BIMESTRAL (1,2,3)
# =========================================================
@proy_bp.route("/bimestres/<int:alumno_id>/<int:proyecto_id>")
@login_required
def bimestres_list(alumno_id: int, proyecto_id: int):
    alumno = User.query.get_or_404(alumno_id)
    proj = Proyecto.query.get_or_404(proyecto_id)

    if not _es_responsable_o_admin(proj):
        flash("Sin permisos para editar bimestres de este proyecto.", "warning")
        return redirect(url_for("proyectos.lista"))

    existentes = {
        rb.numero: rb
        for rb in ReporteBimestral.query.filter_by(
            alumno_id=alumno_id, proyecto_id=proyecto_id
        ).all()
    }

    return render_template(
        "proyectos/bimestres_list.html",
        alumno=alumno,
        proyecto=proj,
        existentes=existentes,
    )


@proy_bp.route(
    "/bimestres/<int:alumno_id>/<int:proyecto_id>/nuevo/<int:numero>",
    methods=["GET", "POST"],
)
@login_required
def bimestre_nuevo(alumno_id: int, proyecto_id: int, numero: int):
    alumno = User.query.get_or_404(alumno_id)
    proj = Proyecto.query.get_or_404(proyecto_id)

    if numero not in (1, 2, 3):
        flash("Número de bimestre inválido.", "danger")
        return redirect(
            url_for(
                "proyectos.bimestres_list",
                alumno_id=alumno_id,
                proyecto_id=proyecto_id,
            )
        )

    if not _es_responsable_o_admin(proj):
        flash("Sin permisos.", "warning")
        return redirect(url_for("proyectos.lista"))

    if request.method == "POST":
        data = {
            "dia1": _val(request.form.get("dia1")),
            "mes1": _val(request.form.get("mes1")),
            "ano1": _val(request.form.get("ano1")),
            "dia2": _val(request.form.get("dia2")),
            "mes2": _val(request.form.get("mes2")),
            "ano2": _val(request.form.get("ano2")),
            "nombre_supervisor": _val(request.form.get("nombre_supervisor")),
            "puesto_supervisor": _val(request.form.get("puesto_supervisor")),
            "observaciones_responsable": _val(
                request.form.get("observaciones_responsable")
            ),
            "resp_1": _clamp_0_4(request.form.get("resp_1", type=int)),
            "resp_2": _clamp_0_4(request.form.get("resp_2", type=int)),
            "resp_3": _clamp_0_4(request.form.get("resp_3", type=int)),
            "resp_4": _clamp_0_4(request.form.get("resp_4", type=int)),
            "resp_5": _clamp_0_4(request.form.get("resp_5", type=int)),
            "resp_6": _clamp_0_4(request.form.get("resp_6", type=int)),
            "resp_7": _clamp_0_4(request.form.get("resp_7", type=int)),
        }

        rb = ReporteBimestral(
            numero=numero, proyecto_id=proyecto_id, alumno_id=alumno_id, **data
        )
        db.session.add(rb)
        try:
            db.session.commit()
            flash(f"Reporte bimestral #{numero} guardado.", "success")
            return redirect(
                url_for(
                    "proyectos.bimestres_list",
                    alumno_id=alumno_id,
                    proyecto_id=proyecto_id,
                )
            )
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe ese bimestre para este alumno y proyecto.", "warning")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al guardar el bimestre.", "danger")

    return render_template(
        "proyectos/bimestre_form.html",
        alumno=alumno,
        proyecto=proj,
        numero=numero,
        rb=None,
        rb_vals={},  # para el template (sin usar getattr/attribute)
        form_data=_defaults_bimestre(proj),
    )


@proy_bp.route("/bimestres/<int:rb_id>/editar", methods=["GET", "POST"])
@login_required
def bimestre_editar(rb_id: int):
    rb = ReporteBimestral.query.get_or_404(rb_id)
    proj = rb.proyecto

    if not _es_responsable_o_admin(proj):
        flash("Sin permisos.", "warning")
        return redirect(url_for("proyectos.lista"))

    if request.method == "POST":
        for k in (
            "dia1",
            "mes1",
            "ano1",
            "dia2",
            "mes2",
            "ano2",
            "nombre_supervisor",
            "puesto_supervisor",
            "observaciones_responsable",
        ):
            setattr(rb, k, _val(request.form.get(k)))
        # calificaciones normalizadas 0..4
        for k in ("resp_1", "resp_2", "resp_3", "resp_4", "resp_5", "resp_6", "resp_7"):
            setattr(rb, k, _clamp_0_4(request.form.get(k, type=int)))

        try:
            db.session.commit()
            flash(f"Reporte bimestral #{rb.numero} actualizado.", "success")
            return redirect(
                url_for(
                    "proyectos.bimestres_list",
                    alumno_id=rb.alumno_id,
                    proyecto_id=rb.proyecto_id,
                )
            )
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al actualizar.", "danger")

    # valores seleccionados para radios
    rb_vals = {f"resp_{i}": getattr(rb, f"resp_{i}", None) for i in range(1, 8)}

    return render_template(
        "proyectos/bimestre_form.html",
        alumno=rb.alumno,
        proyecto=proj,
        numero=rb.numero,
        rb=rb,
        rb_vals=rb_vals,  # para el template (sin usar getattr/attribute)
        form_data={
            "dia1": rb.dia1 or "", "mes1": rb.mes1 or "", "ano1": rb.ano1 or "",
            "dia2": rb.dia2 or "", "mes2": rb.mes2 or "", "ano2": rb.ano2 or "",
            "nombre_supervisor": rb.nombre_supervisor or "",
            "puesto_supervisor": rb.puesto_supervisor or "",
            "observaciones_responsable": rb.observaciones_responsable or "",
        },
    )

# =========================================================
#      FORMATO INTERNO (editar campos en Proyecto.extras)
# =========================================================
# --- dentro de app/views/proyectos.py ---

@proy_bp.route("/interno/<int:proyecto_id>/editar", methods=["GET", "POST"], endpoint="interno_editar")
@login_required
def interno_editar(proyecto_id: int):
    p = Proyecto.query.get_or_404(proyecto_id)

    if not _es_responsable_o_admin(p):
        flash("Sin permisos.", "warning")
        return redirect(url_for("proyectos.lista"))

    # si viene desde bimestres_list, traemos alumno_id de la query (?alumno_id=...)
    alumno_id = request.args.get("alumno_id", type=int)

    months = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

    keys_text = [
        "NOMBRE_RESPONSABLE","CARGO_RESPONSABLE","AREA_RESPONSABLE",
        "TELEFONO_RESPONSABLE","CORREO_RESPONSABLE","HORARIO_RESPONSABLE",
        "numero_personas","num_comunidades","num_estudiantes",
        "objetivos_proyecto","metas_proyecto",
        "Periodo",
    ]
    keys_checks = (
        ["opcion1","opcion2","opcion3"] +
        [f"area{i}" for i in range(1,7)] +
        ["turno1","turno2","carrerera1"] +
        [f"carrera{i}" for i in range(2,10)] +
        [f"{m}{i}" for i in range(1,6) for m in months]
    )
    keys_acts = [f"actividad{i}" for i in range(1,6)]
    all_keys = keys_text + keys_checks + keys_acts

    if request.method == "POST":
        ex = dict(p.extras or {})
        # textos
        for k in keys_text + keys_acts:
            ex[k] = (request.form.get(k) or "").strip()
        # checks
        for k in keys_checks:
            ex[k] = "on" if request.form.get(k) else ""

        p.extras = ex
        try:
            db.session.commit()
            flash("Formato interno actualizado.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo guardar el formato interno.", "danger")

        # Redirige correctamente: si tenemos alumno_id, volvemos a bimestres_list; si no, a la lista
        if alumno_id:
            return redirect(url_for("proyectos.bimestres_list", alumno_id=alumno_id, proyecto_id=proyecto_id))
        return redirect(url_for("proyectos.lista"))

    form_data = {k: (p.extras or {}).get(k, "") for k in all_keys}
    volver_url = (
        url_for("proyectos.bimestres_list", alumno_id=alumno_id, proyecto_id=proyecto_id)
        if alumno_id else url_for("proyectos.lista")
    )
    return render_template("proyectos/interno_form.html", proyecto=p, form_data=form_data, volver_url=volver_url)



# =========================================================
#      REPORTE FINAL (complementa datos finales y/o usa bimestre 3)
# =========================================================
@proy_bp.route("/final/<int:alumno_id>/<int:proyecto_id>/editar", methods=["GET", "POST"], endpoint="final_editar")
@login_required
def final_editar(alumno_id: int, proyecto_id: int):
    alumno = User.query.get_or_404(alumno_id)
    p = Proyecto.query.get_or_404(proyecto_id)

    if not _es_responsable_o_admin(p):
        flash("Sin permisos.", "warning")
        return redirect(url_for("proyectos.lista"))

    # Bimestre 3 (base para evaluación final)
    rb3 = ReporteBimestral.query.filter_by(
        alumno_id=alumno_id, proyecto_id=proyecto_id, numero=3
    ).first()

    if request.method == "POST":
        # --- 1) Campos finales que guardaremos en Proyecto.extras ---
        ex = dict(p.extras or {})

        ex["Municipio"] = _val(request.form.get("Municipio"))
        ex["Estado"] = _val(request.form.get("Estado"))
        ex["Periodo_Final"] = _val(request.form.get("Periodo_Final"))
        ex["Fecha_Entrega_Final"] = _val(request.form.get("Fecha_Entrega_Final"))
        ex["Observaciones_Encargado"] = _val(request.form.get("Observaciones_Encargado"))

        # Actividades/Logros 1..8
        for i in range(1, 9):
            ex[f"Actividad_Final_{i}"] = _val(request.form.get(f"Actividad_Final_{i}"))
            ex[f"Logro_Final_{i}"] = _val(request.form.get(f"Logro_Final_{i}"))

        # Aprendizajes/Beneficios 1..8
        for i in range(1, 9):
            ex[f"Aprendizaje_Final_{i}"] = _val(request.form.get(f"Aprendizaje_Final_{i}"))
            ex[f"Beneficio_Final_{i}"] = _val(request.form.get(f"Beneficio_Final_{i}"))

        # Reasignamos para que SQLAlchemy detecte cambio en JSON
        p.extras = ex

        # --- 2) Calificaciones finales (0..4) en rb3 ---
        # Si no existe rb3 y vienen valores, lo creamos.
        resp_vals = {}
        for k in ("resp_1", "resp_2", "resp_3", "resp_4", "resp_5", "resp_6", "resp_7"):
            resp_vals[k] = _clamp_0_4(request.form.get(k, type=int))

        if rb3 is None:
            rb3 = ReporteBimestral(
                numero=3, proyecto_id=proyecto_id, alumno_id=alumno_id,
                dia1=None, mes1=None, ano1=None, dia2=None, mes2=None, ano2=None,
                nombre_supervisor=None, puesto_supervisor=None, observaciones_responsable=None,
                **resp_vals
            )
            db.session.add(rb3)
        else:
            for k, v in resp_vals.items():
                setattr(rb3, k, v)

        try:
            db.session.commit()
            flash("Reporte final guardado correctamente.", "success")
            return redirect(url_for("proyectos.bimestres_list", alumno_id=alumno_id, proyecto_id=proyecto_id))
        except SQLAlchemyError:
            db.session.rollback()
            flash("Error al guardar el reporte final.", "danger")

    # --- GET: prellenar formulario ---
    ex = p.extras or {}
    form_data = {}

    # Copiamos lo que haya en extras
    for k in (
        "Municipio", "Estado", "Periodo_Final", "Fecha_Entrega_Final", "Observaciones_Encargado"
    ):
        form_data[k] = ex.get(k, "")

    for i in range(1, 9):
        form_data[f"Actividad_Final_{i}"] = ex.get(f"Actividad_Final_{i}", "")
        form_data[f"Logro_Final_{i}"] = ex.get(f"Logro_Final_{i}", "")
        form_data[f"Aprendizaje_Final_{i}"] = ex.get(f"Aprendizaje_Final_{i}", "")
        form_data[f"Beneficio_Final_{i}"] = ex.get(f"Beneficio_Final_{i}", "")

    # Calificaciones: si hay rb3, úsalo
    if rb3:
        for i in range(1, 8):
            form_data[f"resp_{i}"] = getattr(rb3, f"resp_{i}", None)
    else:
        for i in range(1, 8):
            form_data[f"resp_{i}"] = None

    volver_url = url_for("proyectos.bimestres_list", alumno_id=alumno_id, proyecto_id=proyecto_id)
    return render_template(
        "proyectos/final_form.html",
        alumno=alumno,
        proyecto=p,
        form_data=form_data,
        volver_url=volver_url,
    )
