"""create alumno_info & staff_info (conditional)"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_alumno_staff_info_conditional"
down_revision = None  # o coloca aquí la última revision id de tu proyecto si usas una cadena real
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    insp = sa.inspect(conn)
    return name in insp.get_table_names()


def upgrade():
    conn = op.get_bind()

    # --- alumno_info
    if not _table_exists(conn, "alumno_info"):
        op.create_table(
            "alumno_info",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("nombre", sa.String(length=120)),
            sa.Column("apellido_paterno", sa.String(length=120)),
            sa.Column("apellido_materno", sa.String(length=120)),
            sa.Column("no_control", sa.String(length=50)),
            sa.Column("carrera", sa.String(length=120)),
        )

    # --- staff_info
    if not _table_exists(conn, "staff_info"):
        op.create_table(
            "staff_info",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("nombre", sa.String(length=120)),
            sa.Column("apellido_paterno", sa.String(length=120)),
            sa.Column("apellido_materno", sa.String(length=120)),
            sa.Column("cargo", sa.String(length=120)),
        )


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, "staff_info"):
        op.drop_table("staff_info")

    if _table_exists(conn, "alumno_info"):
        op.drop_table("alumno_info")
