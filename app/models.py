# app/models.py
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint, event

db = SQLAlchemy()

# -------------------------
#  Departamento
# -------------------------
class Departamento(db.Model):
    __tablename__ = "departamentos"

    id      = db.Column(db.Integer, primary_key=True)
    nombre  = db.Column(db.String(120), nullable=False)

    # Jefe del departamento (usuario con rol "jefe")
    jefe_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    jefe    = db.relationship(
        "User",
        foreign_keys=[jefe_id],
        backref="departamentos_dirigidos",
    )

    def __repr__(self) -> str:
        return f"<Departamento {self.id} {self.nombre!r}>"


# -------------------------
#  Usuario
# -------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    nombre        = db.Column(db.String(120), nullable=False)          # nombre para mostrar
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol           = db.Column(db.String(20), nullable=False, default="alumno")
    activo        = db.Column(db.Boolean, default=True)

    # Datos opcionales de alumno (para DOCX)
    ap_paterno = db.Column(db.String(120))
    ap_materno = db.Column(db.String(120))
    nombres    = db.Column(db.String(120))  # si lo quieres separado
    no_control = db.Column(db.String(50))
    carrera    = db.Column(db.String(120))

    # Departamento al que pertenece el usuario (si aplica)
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"))
    departamento    = db.relationship(
        "Departamento",
        foreign_keys=[departamento_id],   # evita ambigüedad
        backref="miembros",
    )

    # Helpers de contraseña
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email!r} rol={self.rol}>"


# -------------------------
#  Proyecto (con columna legacy `nombre`)
# -------------------------
class Proyecto(db.Model):
    __tablename__ = "proyectos"

    id = db.Column(db.Integer, primary_key=True)

    # ---- LEGACY: existe en la BD con NOT NULL, lo seguimos usando y sincronizamos
    nombre = db.Column(db.String(200), nullable=False)

    # ---- Campos que usa el formulario
    nombre_programa    = db.Column(db.String(200), nullable=True)
    nombre_dependencia = db.Column(db.String(200), nullable=True)
    nombre_responsable = db.Column(db.String(200), nullable=True)
    cargo_responsable  = db.Column(db.String(200), nullable=True)

    # Ubicación
    municipio = db.Column(db.String(120))
    estado    = db.Column(db.String(120))

    # Relaciones opcionales
    departamento_id = db.Column(db.Integer, db.ForeignKey("departamentos.id"), nullable=True)
    responsable_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    extras          = db.Column(db.JSON, default=dict)

    departamento = db.relationship("Departamento", foreign_keys=[departamento_id], backref="proyectos")
    # Evitamos chocar con nombre_responsable (string)
    responsable_user = db.relationship("User", foreign_keys=[responsable_id], backref="proyectos_responsables")

    # --------- Otros campos (si los usas para DOCX/cronograma)
    resp_cargo   = db.Column(db.String(120))
    resp_tel     = db.Column(db.String(50))
    resp_correo  = db.Column(db.String(120))
    resp_horario = db.Column(db.String(120))

    periodo_realizacion       = db.Column(db.String(120))
    beneficiarios_personas    = db.Column(db.Integer)
    beneficiarios_comunidades = db.Column(db.Integer)

    impacto_pais      = db.Column(db.Boolean, default=False)
    impacto_inclusion = db.Column(db.Boolean, default=False)
    impacto_medioamb  = db.Column(db.Boolean, default=False)

    num_estudiantes = db.Column(db.Integer)

    # Carreras (checks)
    car_tics        = db.Column(db.Boolean, default=False)
    car_admon       = db.Column(db.Boolean, default=False)
    car_quimica     = db.Column(db.Boolean, default=False)
    car_industrial  = db.Column(db.Boolean, default=False)
    car_mecanica    = db.Column(db.Boolean, default=False)
    car_electrica   = db.Column(db.Boolean, default=False)
    car_electronica = db.Column(db.Boolean, default=False)
    car_ges_emp     = db.Column(db.Boolean, default=False)
    car_materiales  = db.Column(db.Boolean, default=False)

    turno_mat = db.Column(db.Boolean, default=False)
    turno_ves = db.Column(db.Boolean, default=False)

    objetivo = db.Column(db.Text)
    metas    = db.Column(db.Text)

    # Área del conocimiento
    area_agro    = db.Column(db.Boolean, default=False)
    area_salud   = db.Column(db.Boolean, default=False)
    area_exactas = db.Column(db.Boolean, default=False)
    area_social  = db.Column(db.Boolean, default=False)
    area_edu     = db.Column(db.Boolean, default=False)
    area_ing     = db.Column(db.Boolean, default=False)

    cronograma_json = db.Column(db.Text)

    def __repr__(self) -> str:
        return f"<Proyecto {self.id} {self.nombre!r}>"


# ---- Listeners: sincronizan nombre <-> nombre_programa
@event.listens_for(Proyecto, "before_insert")
def _sync_nombre_before_insert(mapper, connection, target: Proyecto):
    if not getattr(target, "nombre", None):
        np = getattr(target, "nombre_programa", None)
        if np:
            target.nombre = np

@event.listens_for(Proyecto, "before_update")
def _sync_nombre_before_update(mapper, connection, target: Proyecto):
    np = getattr(target, "nombre_programa", None)
    if np and np != getattr(target, "nombre", None):
        target.nombre = np


# -------------------------
#  Asignación alumno-proyecto
# -------------------------
class AlumnoProyecto(db.Model):
    __tablename__ = "alumnos_proyectos"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    proyecto_id = db.Column(db.Integer, db.ForeignKey("proyectos.id"), nullable=False)

    alumno   = db.relationship("User",     foreign_keys=[user_id],     backref="asignaciones")
    proyecto = db.relationship(
        "Proyecto",
        foreign_keys=[proyecto_id],
        backref=db.backref(
            "alumnos_asignados",
            cascade="all, delete-orphan",
            passive_deletes=False,
        ),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "proyecto_id", name="uq_user_proyecto"),
    )

    def __repr__(self) -> str:
        return f"<AlumnoProyecto u={self.user_id} p={self.proyecto_id}>"


# -------------------------
#  Reporte bimestral (3 por alumno)
# -------------------------
# --- pega dentro de app/models.py (debajo de Proyecto y User) ---

class ReporteBimestral(db.Model):
    __tablename__ = "reportes_bimestrales"

    id = db.Column(db.Integer, primary_key=True)
    # 1, 2 o 3
    numero = db.Column(db.Integer, nullable=False, default=1)

    # relaciones directas (ya migradas)
    proyecto_id = db.Column(db.Integer, db.ForeignKey("proyectos.id"), nullable=False)
    alumno_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # rangos de fechas (texto partido por requisitos de plantilla)
    dia1 = db.Column(db.String(10))
    mes1 = db.Column(db.String(10))
    ano1 = db.Column(db.String(10))
    dia2 = db.Column(db.String(10))
    mes2 = db.Column(db.String(10))
    ano2 = db.Column(db.String(10))

    # supervisor/observaciones en el bimestre
    nombre_supervisor        = db.Column(db.String(200))
    puesto_supervisor        = db.Column(db.String(200))
    observaciones_responsable = db.Column(db.Text)

    # evaluaciones del responsable (0..4)
    resp_1 = db.Column(db.Integer)
    resp_2 = db.Column(db.Integer)
    resp_3 = db.Column(db.Integer)
    resp_4 = db.Column(db.Integer)
    resp_5 = db.Column(db.Integer)
    resp_6 = db.Column(db.Integer)
    resp_7 = db.Column(db.Integer)

    proyecto = db.relationship("Proyecto", foreign_keys=[proyecto_id], backref="bimestres")
    alumno   = db.relationship("User",     foreign_keys=[alumno_id],   backref="bimestres")

    __table_args__ = (
        db.UniqueConstraint("proyecto_id", "alumno_id", "numero", name="uq_bim_alumno_proyecto_num"),
    )

    def __repr__(self) -> str:
        return f"<RB #{self.numero} alumno={self.alumno_id} proyecto={self.proyecto_id}>"

# -------------------------
#  Evaluación final (1 por alumno)
# -------------------------
class EvaluacionFinal(db.Model):
    __tablename__ = "evaluaciones_finales"

    id          = db.Column(db.Integer, primary_key=True)
    proyecto_id = db.Column(db.Integer, db.ForeignKey("proyectos.id"), nullable=False)
    alumno_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # 7 criterios, valor 0..4
    resp_1 = db.Column(db.Integer)
    resp_2 = db.Column(db.Integer)
    resp_3 = db.Column(db.Integer)
    resp_4 = db.Column(db.Integer)
    resp_5 = db.Column(db.Integer)
    resp_6 = db.Column(db.Integer)
    resp_7 = db.Column(db.Integer)

    observaciones = db.Column(db.Text)
    responsable_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("proyecto_id", "alumno_id", name="uq_final_alumno_proyecto"),
    )

    alumno      = db.relationship("User", foreign_keys=[alumno_id])
    proyecto    = db.relationship("Proyecto", foreign_keys=[proyecto_id])
    responsable = db.relationship("User", foreign_keys=[responsable_id])

    def __repr__(self) -> str:
        return f"<EvaluacionFinal proyecto={self.proyecto_id} alumno={self.alumno_id}>"

class AlumnoInfo(db.Model):
    __tablename__ = "alumno_info"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    nombre = db.Column(db.String(120))
    apellido_paterno = db.Column(db.String(120))
    apellido_materno = db.Column(db.String(120))
    no_control = db.Column(db.String(50))
    carrera = db.Column(db.String(120))
    user = db.relationship("User", backref=db.backref("alumno_info", uselist=False))

class StaffInfo(db.Model):
    __tablename__ = "staff_info"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    nombre = db.Column(db.String(120))
    apellido_paterno = db.Column(db.String(120))
    apellido_materno = db.Column(db.String(120))
    cargo = db.Column(db.String(120))
    user = db.relationship("User", backref=db.backref("staff_info", uselist=False))
