# app/models_extra.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Este archivo asume que 'db' ya está creado en app.models o similar.
# Importamos la instancia global de db desde tus modelos existentes.
from app.models import db  # <- ajusta si tu db vive en otro módulo
from sqlalchemy import UniqueConstraint

# --------------------------
# Info extendida por tipo de usuario
# --------------------------

class AlumnoInfo(db.Model):
    __tablename__ = 'alumno_info'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)  # <- ajusta nombre de tabla de usuarios si difiere
    nombre = db.Column(db.String(120), nullable=False)
    apellido_paterno = db.Column(db.String(120), nullable=False)
    apellido_materno = db.Column(db.String(120), nullable=False)
    no_control = db.Column(db.String(20), nullable=False)
    carrera = db.Column(db.String(140), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StaffInfo(db.Model):
    __tablename__ = 'staff_info'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)  # <- ajusta
    nombre = db.Column(db.String(120), nullable=False)
    apellido_paterno = db.Column(db.String(120), nullable=True)
    apellido_materno = db.Column(db.String(120), nullable=True)
    cargo = db.Column(db.String(140), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --------------------------
# Reportes
# --------------------------

class ReporteBimestral(db.Model):
    __tablename__ = 'reporte_bimestral'
    id = db.Column(db.Integer, primary_key=True)

    alumno_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)      # alumno (rol=alumno)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyectos.id'), nullable=False)  # <- ajusta si tu tabla es distinta
    num_reporte = db.Column(db.Integer, nullable=False)  # 1,2,3

    # Fechas del periodo
    dia1 = db.Column(db.String(2))
    mes1 = db.Column(db.String(15))
    anio1 = db.Column(db.String(4))
    dia2 = db.Column(db.String(2))
    mes2 = db.Column(db.String(15))
    anio2 = db.Column(db.String(4))

    # Actividades (1..8)
    actividad_1 = db.Column(db.Text); actividad_2 = db.Column(db.Text)
    actividad_3 = db.Column(db.Text); actividad_4 = db.Column(db.Text)
    actividad_5 = db.Column(db.Text); actividad_6 = db.Column(db.Text)
    actividad_7 = db.Column(db.Text); actividad_8 = db.Column(db.Text)

    # Evaluación del responsable (7 criterios, valor 0..4)
    tp_resp_1 = db.Column(db.Integer)
    tp_resp_2 = db.Column(db.Integer)
    tp_resp_3 = db.Column(db.Integer)
    tp_resp_4 = db.Column(db.Integer)
    tp_resp_5 = db.Column(db.Integer)
    tp_resp_6 = db.Column(db.Integer)
    tp_resp_7 = db.Column(db.Integer)

    observaciones_responsable = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('alumno_id', 'proyecto_id', 'num_reporte', name='uq_bim_alumno_proyecto_num'),
    )

class ReporteFinal(db.Model):
    __tablename__ = 'reporte_final'
    id = db.Column(db.Integer, primary_key=True)

    alumno_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)      # <- ajusta
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyectos.id'), nullable=False)  # <- ajusta

    periodo_final = db.Column(db.String(80))
    fecha_entrega_final = db.Column(db.String(20))
    municipio = db.Column(db.String(120))
    estado = db.Column(db.String(120))

    # Actividades y logros (1..8)
    actividad_1 = db.Column(db.Text); logro_1 = db.Column(db.Text)
    actividad_2 = db.Column(db.Text); logro_2 = db.Column(db.Text)
    actividad_3 = db.Column(db.Text); logro_3 = db.Column(db.Text)
    actividad_4 = db.Column(db.Text); logro_4 = db.Column(db.Text)
    actividad_5 = db.Column(db.Text); logro_5 = db.Column(db.Text)
    actividad_6 = db.Column(db.Text); logro_6 = db.Column(db.Text)
    actividad_7 = db.Column(db.Text); logro_7 = db.Column(db.Text)
    actividad_8 = db.Column(db.Text); logro_8 = db.Column(db.Text)

    # Aprendizajes y beneficios (1..8)
    aprendizaje_1 = db.Column(db.Text); beneficio_1 = db.Column(db.Text)
    aprendizaje_2 = db.Column(db.Text); beneficio_2 = db.Column(db.Text)
    aprendizaje_3 = db.Column(db.Text); beneficio_3 = db.Column(db.Text)
    aprendizaje_4 = db.Column(db.Text); beneficio_4 = db.Column(db.Text)
    aprendizaje_5 = db.Column(db.Text); beneficio_5 = db.Column(db.Text)
    aprendizaje_6 = db.Column(db.Text); beneficio_6 = db.Column(db.Text)
    aprendizaje_7 = db.Column(db.Text); beneficio_7 = db.Column(db.Text)
    aprendizaje_8 = db.Column(db.Text); beneficio_8 = db.Column(db.Text)

    # Evaluación final del responsable (7 criterios 0..4)
    tp_final_1 = db.Column(db.Integer)
    tp_final_2 = db.Column(db.Integer)
    tp_final_3 = db.Column(db.Integer)
    tp_final_4 = db.Column(db.Integer)
    tp_final_5 = db.Column(db.Integer)
    tp_final_6 = db.Column(db.Integer)
    tp_final_7 = db.Column(db.Integer)

    observaciones_encargado = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
