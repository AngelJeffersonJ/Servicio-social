# app/routes/reportes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from app.models import db, User, Proyecto  # <- ajusta import 'User' y 'Proyecto' a tu app
from app.models_extra import ReporteBimestral, ReporteFinal

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

# --------- util de permisos ----------
def roles_requeridos(*roles):
    def wrapper(fn):
        def inner(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if getattr(current_user, 'role', None) not in roles:
                abort(403)
            return fn(*args, **kwargs)
        inner.__name__ = fn.__name__
        return login_required(inner)
    return wrapper

# --------- helpers ----------
def _cargar_contexto(alumno_id, proyecto_id):
    alumno = User.query.get_or_404(alumno_id)     # alumno (rol = 'alumno')
    proyecto = Proyecto.query.get_or_404(proyecto_id)
    return alumno, proyecto

# --------- Bimestral ----------
@reportes_bp.route('/bimestral/<int:alumno_id>/<int:proyecto_id>/<int:num>', methods=['GET', 'POST'])
@roles_requeridos('admin', 'jefe', 'laboratorista')
def bimestral(alumno_id, proyecto_id, num):
    if num not in (1, 2, 3):
        abort(404)

    alumno, proyecto = _cargar_contexto(alumno_id, proyecto_id)
    reporte = ReporteBimestral.query.filter_by(
        alumno_id=alumno.id, proyecto_id=proyecto.id, num_reporte=num
    ).first()

    if request.method == 'POST':
        # Fechas
        dia1 = request.form.get('dia1') or None
        mes1 = request.form.get('mes1') or None
        anio1 = request.form.get('anio1') or None
        dia2 = request.form.get('dia2') or None
        mes2 = request.form.get('mes2') or None
        anio2 = request.form.get('anio2') or None

        # Actividades 1..8
        acts = [request.form.get(f'activ_{i}') or None for i in range(1,9)]

        # Evaluación 7 criterios (0..4)
        def _ival(name):
            v = request.form.get(name)
            return int(v) if v not in (None, '',) else None
        evals = [_ival(f'tp_{i}') for i in range(1,8)]

        obs = request.form.get('observaciones') or None

        if not reporte:
            reporte = ReporteBimestral(
                alumno_id=alumno.id,
                proyecto_id=proyecto.id,
                num_reporte=num
            )
            db.session.add(reporte)

        # set fields
        reporte.dia1, reporte.mes1, reporte.anio1 = dia1, mes1, anio1
        reporte.dia2, reporte.mes2, reporte.anio2 = dia2, mes2, anio2
        (reporte.actividad_1, reporte.actividad_2, reporte.actividad_3, reporte.actividad_4,
         reporte.actividad_5, reporte.actividad_6, reporte.actividad_7, reporte.actividad_8) = acts
        (reporte.tp_resp_1, reporte.tp_resp_2, reporte.tp_resp_3, reporte.tp_resp_4,
         reporte.tp_resp_5, reporte.tp_resp_6, reporte.tp_resp_7) = evals
        reporte.observaciones_responsable = obs

        try:
            db.session.commit()
            flash(f'Reporte bimestral {num} guardado correctamente.', 'success')
            return redirect(url_for('reportes.bimestral', alumno_id=alumno.id, proyecto_id=proyecto.id, num=num))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error al guardar el reporte bimestral.', 'danger')

    # GET o POST con errores: render
    return render_template('reportes/bimestral_form.html',
                           alumno=alumno, proyecto=proyecto, num=num, reporte=reporte)

# --------- Final ----------
@reportes_bp.route('/final/<int:alumno_id>/<int:proyecto_id>', methods=['GET', 'POST'])
@roles_requeridos('admin', 'jefe', 'laboratorista')
def final(alumno_id, proyecto_id):
    alumno, proyecto = _cargar_contexto(alumno_id, proyecto_id)
    reporte = ReporteFinal.query.filter_by(
        alumno_id=alumno.id, proyecto_id=proyecto.id
    ).first()

    if request.method == 'POST':
        periodo = request.form.get('periodo_final') or None
        fecha_entrega = request.form.get('fecha_entrega_final') or None
        municipio = request.form.get('municipio') or None
        estado = request.form.get('estado') or None

        acts = [request.form.get(f'act_{i}') or None for i in range(1,9)]
        logs = [request.form.get(f'log_{i}') or None for i in range(1,9)]
        aprs = [request.form.get(f'ap_{i}') or None for i in range(1,9)]
        bens = [request.form.get(f'ben_{i}') or None for i in range(1,9)]

        def _ival(name):
            v = request.form.get(name)
            return int(v) if v not in (None, '',) else None
        evals = [_ival(f'tp_final_{i}') for i in range(1,8)]

        obs = request.form.get('observaciones_encargado') or None

        if not reporte:
            reporte = ReporteFinal(alumno_id=alumno.id, proyecto_id=proyecto.id)
            db.session.add(reporte)

        reporte.periodo_final = periodo
        reporte.fecha_entrega_final = fecha_entrega
        reporte.municipio, reporte.estado = municipio, estado

        # set pares act/logro
        for i in range(1,9):
            setattr(reporte, f'actividad_{i}', acts[i-1])
            setattr(reporte, f'logro_{i}', logs[i-1])

        for i in range(1,8):
            setattr(reporte, f'tp_final_{i}', evals[i-1])

        for i in range(1,9):
            setattr(reporte, f'aprendizaje_{i}', aprs[i-1])
            setattr(reporte, f'beneficio_{i}', bens[i-1])

        reporte.observaciones_encargado = obs

        try:
            db.session.commit()
            flash('Reporte final guardado correctamente.', 'success')
            return redirect(url_for('reportes.final', alumno_id=alumno.id, proyecto_id=proyecto.id))
        except SQLAlchemyError:
            db.session.rollback()
            flash('Error al guardar el reporte final.', 'danger')

    return render_template('reportes/final_form.html',
                           alumno=alumno, proyecto=proyecto, reporte=reporte)
