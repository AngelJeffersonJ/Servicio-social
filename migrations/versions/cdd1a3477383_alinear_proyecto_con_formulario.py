"""Alinear Proyecto con formulario; crear/alterar 'proyectos' de forma tolerante.

- Si la tabla 'proyectos' NO existe, la crea con las columnas usadas por el
  formulario: nombre_programa, nombre_dependencia, nombre_responsable,
  cargo_responsable, municipio, estado, departamento_id, responsable_id, extras.
- Si ya existe, agrega esas columnas si faltan y migra datos desde posibles
  columnas viejas (nombre, programa, dependencia, responsable, cargo).
"""

from alembic import op
import sqlalchemy as sa

# Revisions
revision = "cdd1a3477383_alinear_proyecto_con_formulario"
down_revision = None  # si tienes una revisión anterior, pon su id aquí
branch_labels = None
depends_on = None


def _tables(conn):
    insp = sa.inspect(conn)
    return set(insp.get_table_names())


def _cols(conn, table):
    insp = sa.inspect(conn)
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    tables = _tables(conn)

    # ------------------------------------------------------------------
    # 1) Si NO existe la tabla 'proyectos', créala desde cero
    # ------------------------------------------------------------------
    if "proyectos" not in tables:
        op.create_table(
            "proyectos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nombre_programa", sa.String(length=200), nullable=True),
            sa.Column("nombre_dependencia", sa.String(length=200), nullable=True),
            sa.Column("nombre_responsable", sa.String(length=200), nullable=True),
            sa.Column("cargo_responsable", sa.String(length=200), nullable=True),
            sa.Column("municipio", sa.String(length=120), nullable=True),
            sa.Column("estado", sa.String(length=120), nullable=True),
            sa.Column("departamento_id", sa.Integer(), sa.ForeignKey("departamentos.id"), nullable=True),
            sa.Column("responsable_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("extras", sa.JSON(), nullable=True, default=dict),
        )
        return  # nada que migrar si la tabla es nueva

    # ------------------------------------------------------------------
    # 2) Si SÍ existe, agrega columnas faltantes y migra datos
    # ------------------------------------------------------------------
    cols = _cols(conn, "proyectos")

    def add_if_missing(name, col):
        if name not in cols:
            op.add_column("proyectos", col)

    add_if_missing("nombre_programa", sa.Column("nombre_programa", sa.String(200), nullable=True))
    add_if_missing("nombre_dependencia", sa.Column("nombre_dependencia", sa.String(200), nullable=True))
    add_if_missing("nombre_responsable", sa.Column("nombre_responsable", sa.String(200), nullable=True))
    add_if_missing("cargo_responsable", sa.Column("cargo_responsable", sa.String(200), nullable=True))
    add_if_missing("municipio", sa.Column("municipio", sa.String(120), nullable=True))
    add_if_missing("estado", sa.Column("estado", sa.String(120), nullable=True))
    add_if_missing("departamento_id", sa.Column("departamento_id", sa.Integer(), sa.ForeignKey("departamentos.id"), nullable=True))
    add_if_missing("responsable_id", sa.Column("responsable_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    add_if_missing("extras", sa.Column("extras", sa.JSON(), nullable=True))

    # refrescar columnas
    cols = _cols(conn, "proyectos")

    def has(c): return c in cols

    # Migración de datos desde posibles columnas antiguas
    if has("nombre_programa"):
        if has("nombre"):
            op.execute("UPDATE proyectos SET nombre_programa = COALESCE(nombre_programa, nombre)")
        if has("programa"):
            op.execute("UPDATE proyectos SET nombre_programa = COALESCE(nombre_programa, programa)")
    if has("nombre_dependencia") and has("dependencia"):
        op.execute("UPDATE proyectos SET nombre_dependencia = COALESCE(nombre_dependencia, dependencia)")
    if has("nombre_responsable") and has("responsable"):
        op.execute("UPDATE proyectos SET nombre_responsable = COALESCE(nombre_responsable, responsable)")
    if has("cargo_responsable") and has("cargo"):
        op.execute("UPDATE proyectos SET cargo_responsable = COALESCE(cargo_responsable, cargo)")


def downgrade():
    # Conservador: no eliminamos columnas/tabla para no perder datos.
    pass
