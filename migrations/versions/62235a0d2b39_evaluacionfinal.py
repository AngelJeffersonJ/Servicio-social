"""EvaluacionFinal

Reestructura reportes_bimestrales para SQLite usando recreate="always"
y con nombres explícitos de constraints.
"""

from alembic import op
import sqlalchemy as sa

# IDs Alembic
revision = "62235a0d2b39"
down_revision = "c5c6d046cf9d"
branch_labels = None
depends_on = None


def upgrade():
    # En SQLite recreamos la tabla y definimos TODAS las constraints con nombre
    with op.batch_alter_table("reportes_bimestrales", recreate="always") as batch:
        # --- columnas nuevas (nullable=True durante recreación) ---
        batch.add_column(sa.Column("proyecto_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("alumno_id", sa.Integer(), nullable=True))

        batch.add_column(sa.Column("dia1", sa.String(10), nullable=True))
        batch.add_column(sa.Column("mes1", sa.String(10), nullable=True))
        batch.add_column(sa.Column("ano1", sa.String(10), nullable=True))
        batch.add_column(sa.Column("dia2", sa.String(10), nullable=True))
        batch.add_column(sa.Column("mes2", sa.String(10), nullable=True))
        batch.add_column(sa.Column("ano2", sa.String(10), nullable=True))

        batch.add_column(sa.Column("nombre_supervisor", sa.String(200), nullable=True))
        batch.add_column(sa.Column("puesto_supervisor", sa.String(200), nullable=True))
        batch.add_column(sa.Column("observaciones_responsable", sa.Text(), nullable=True))

        batch.add_column(sa.Column("resp_1", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resp_2", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resp_3", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resp_4", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resp_5", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resp_6", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resp_7", sa.Integer(), nullable=True))

        # --- columnas legacy que quitamos si existen ---
        for col in (
            "alumno_proyecto_id",
            "evaluador_id",
            "fecha_evaluacion",
            "fecha_inicio",
            "fecha_fin",
            "datos",
        ):
            try:
                batch.drop_column(col)
            except Exception:
                pass  # si no existe, seguimos

        # --- FKs y UNIQUE con nombres explícitos ---
        batch.create_foreign_key(
            "fk_rb_proyecto", "proyectos", ["proyecto_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_rb_alumno", "users", ["alumno_id"], ["id"]
        )
        try:
            batch.create_unique_constraint(
                "uq_bim_alumno_proyecto_num", ["proyecto_id", "alumno_id", "numero"]
            )
        except Exception:
            pass  # ya existe

        # --- ahora sí, NOT NULL en claves foráneas ---
        batch.alter_column("proyecto_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("alumno_id", existing_type=sa.Integer(), nullable=False)


def downgrade():
    # Downgrade best-effort: recreamos y retiramos lo agregado
    with op.batch_alter_table("reportes_bimestrales", recreate="always") as batch:
        for col in (
            "proyecto_id",
            "alumno_id",
            "dia1",
            "mes1",
            "ano1",
            "dia2",
            "mes2",
            "ano2",
            "nombre_supervisor",
            "puesto_supervisor",
            "observaciones_responsable",
            "resp_1",
            "resp_2",
            "resp_3",
            "resp_4",
            "resp_5",
            "resp_6",
            "resp_7",
        ):
            try:
                batch.drop_column(col)
            except Exception:
                pass
