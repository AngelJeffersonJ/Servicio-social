# app/routes/proyectos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError

from app.models import db, Proyecto  # <- ajusta nombre/ubicación del modelo

proy_bp = Blueprint('proyectos', __name__, url_prefix='/proyectos')

@proy_bp.route('/')
@login_required
def lista():
    proyectos = Proyecto.query.order_by(Proyecto.id.desc()).all()
    return render_template('proyectos/lista.html', proyectos=proyectos)

@proy_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo():
    if request.method == 'POST':
        nombre_programa = request.form.get('nombre_programa') or ''
        nombre_dependencia = request.form.get('nombre_dependencia') or ''
        nombre_responsable = request.form.get('nombre_responsable') or ''
        cargo_responsable = request.form.get('cargo_responsable') or ''
        municipio = request.form.get('municipio') or ''
        estado = request.form.get('estado') or ''

        if not nombre_programa or not nombre_dependencia or not nombre_responsable or not cargo_responsable:
            flash('Programa, Dependencia, Responsable y Cargo son obligatorios.', 'warning')
            return render_template('proyectos/form.html', form=request.form)

        p = Proyecto(
            nombre_programa=nombre_programa,
            nombre_dependencia=nombre_dependencia,
            nombre_responsable=nombre_responsable,
            cargo_responsable=cargo_responsable,
            municipio=municipio, estado=estado
        )

        db.session.add(p)
        try:
            db.session.commit()
            flash('Proyecto creado correctamente.', 'success')
            return redirect(url_for('proyectos.lista'))
        except SQLAlchemyError:
            db.session.rollback()
            flash('Error al crear proyecto.', 'danger')

    return render_template('proyectos/form.html')

@proy_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    p = Proyecto.query.get_or_404(id)
    if request.method == 'POST':
        p.nombre_programa = request.form.get('nombre_programa') or p.nombre_programa
        p.nombre_dependencia = request.form.get('nombre_dependencia') or p.nombre_dependencia
        p.nombre_responsable = request.form.get('nombre_responsable') or p.nombre_responsable
        p.cargo_responsable = request.form.get('cargo_responsable') or p.cargo_responsable
        p.municipio = request.form.get('municipio') or p.municipio
        p.estado = request.form.get('estado') or p.estado

        try:
            db.session.commit()
            flash('Proyecto actualizado correctamente.', 'success')
            return redirect(url_for('proyectos.lista'))
        except SQLAlchemyError:
            db.session.rollback()
            flash('Error al actualizar el proyecto.', 'danger')

    return render_template('proyectos/form.html', proyecto=p)

@proy_bp.route('/detalle/<int:id>')
@login_required
def detalle(id):
    p = Proyecto.query.get_or_404(id)
    return render_template('proyectos/detalle.html', proyecto=p)
