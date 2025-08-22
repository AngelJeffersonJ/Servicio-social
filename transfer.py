# transfer.py
# ------------------------------------------------------------
# Copia TODOS los datos desde una base SQLite a PostgreSQL
# usando SQLAlchemy, preservando IDs y respetando el orden
# de dependencias por llaves foráneas.
#
# Uso (desde tu laptop con conexión pública de Railway):
#   py -m pip install "SQLAlchemy>=2.0" psycopg2-binary
#   py .\transfer.py "sqlite:///instance/servicio.db" "postgresql+psycopg2://postgres:PASS@HOST:PORT/railway?sslmode=require" --truncate
#
# Uso (dentro de Railway, con host interno):
#   python transfer.py "sqlite:///instance/servicio.db" "postgresql+psycopg2://postgres:PASS@postgres.railway.internal:5432/railway"
#
# Parámetros opcionales:
#   --truncate     Vacía tablas destino antes de insertar
#   --tables a,b   Limita la migración a tablas específicas (separadas por comas)
#   --batch 5000   Tamaño de lote para inserts (default 1000)
# ------------------------------------------------------------

from __future__ import annotations

import sys
import argparse
from typing import Dict, List, Set, Tuple, Optional

from sqlalchemy import create_engine, MetaData, Table, select, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, IntegrityError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrar datos de SQLite a PostgreSQL preservando IDs."
    )
    parser.add_argument("sqlite_dsn", help='Ej: sqlite:///instance/servicio.db')
    parser.add_argument(
        "pg_dsn",
        help=(
            'Ej interno Railway: "postgresql+psycopg2://postgres:PASS@postgres.railway.internal:5432/railway"\n'
            'Ej público Railway: "postgresql+psycopg2://postgres:PASS@shinkansen.proxy.rlwy.net:PORT/railway?sslmode=require"'
        ),
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Vaciar tablas destino antes de insertar (TRUNCATE CASCADE).",
    )
    parser.add_argument(
        "--tables",
        type=str,
        default="",
        help="Lista de tablas a migrar separadas por comas (por defecto todas).",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1000,
        help="Tamaño de lote para inserts.",
    )
    return parser.parse_args()


def reflect_metadata(engine: Engine) -> Tuple[MetaData, object]:
    meta = MetaData()
    meta.reflect(bind=engine)
    insp = inspect(engine)
    return meta, insp


def topo_sort_tables(meta: MetaData, limit_to: Optional[Set[str]] = None) -> List[str]:
    """
    Orden topológico por dependencias de FKs (origen -> destino).
    Si limit_to se da, reduce el grafo a ese subconjunto.
    No usa meta.sorted_tables para evitar warnings cuando hay ciclos.
    """
    # Diccionario {nombre_tabla: Table}
    tables: Dict[str, Table] = {name: tbl for name, tbl in meta.tables.items()}
    if limit_to:
        tables = {k: v for k, v in tables.items() if k in limit_to}

    # Grafo de dependencias
    deps: Dict[str, Set[str]] = {name: set() for name in tables}
    reverse: Dict[str, Set[str]] = {name: set() for name in tables}

    for name, tbl in tables.items():
        for fk in tbl.foreign_keys:
            ref = fk.column.table.name
            if ref in tables and ref != name:
                deps[name].add(ref)
                reverse[ref].add(name)

    # Kahn
    no_incoming = [n for n, d in deps.items() if not d]
    order: List[str] = []

    while no_incoming:
        n = no_incoming.pop()
        order.append(n)
        for m in list(reverse[n]):
            deps[m].discard(n)
            reverse[n].discard(m)
            if not deps[m]:
                no_incoming.append(m)

    # si quedaron ciclos, agrega como vengan (orden estable por inserción)
    remaining = [n for n, d in deps.items() if d]
    order += remaining

    # Filtra por el conjunto final de tablas
    return [n for n in order if n in tables]


def truncate_all(engine: Engine, table_names: List[str]) -> None:
    if not table_names:
        return
    # TRUNCATE en orden inverso para evitar FKs
    with engine.begin() as conn:
        try:
            conn.execute(text("SET session_replication_role = 'replica'"))
        except Exception:
            # No tenemos súper-usuario; ignora
            pass
        try:
            conn.execute(
                text(
                    "TRUNCATE {} RESTART IDENTITY CASCADE".format(
                        ", ".join(f'"{t}"' for t in table_names[::-1])
                    )
                )
            )
        finally:
            try:
                conn.execute(text("SET session_replication_role = 'origin'"))
            except Exception:
                pass


def copy_table(
    src_engine: Engine,
    dst_engine: Engine,
    src_tbl: Table,
    dst_tbl: Table,
    batch_size: int = 1000,
) -> int:
    """Copia filas de src_tbl a dst_tbl. Devuelve cantidad de filas copiadas."""
    # columnas comunes (por nombre)
    dst_cols = {c.name for c in dst_tbl.columns}
    cols = [c for c in src_tbl.columns if c.name in dst_cols]
    if not cols:
        return 0

    total = 0
    offset = 0

    with src_engine.connect() as sconn, dst_engine.begin() as dconn:
        # intenta desactivar triggers/constraints si se puede (no siempre)
        try:
            dconn.execute(text("SET session_replication_role = 'replica'"))
        except Exception:
            pass

        try:
            while True:
                chunk = (
                    sconn.execute(select(*cols).limit(batch_size).offset(offset))
                    .mappings()
                    .all()
                )
                if not chunk:
                    break

                rows = [dict(row) for row in chunk]

                # Inserta
                dconn.execute(dst_tbl.insert(), rows)
                total += len(rows)
                offset += batch_size
        finally:
            try:
                dconn.execute(text("SET session_replication_role = 'origin'"))
            except Exception:
                pass

    return total


def reset_identity_sequences(dst_engine: Engine, table_names: List[str]) -> None:
    """
    Ajusta las secuencias en Postgres para tablas con PK entero autoincremental.
    No es crítico si falla (solo afecta próximos INSERTs sin ID manual).
    """
    with dst_engine.begin() as conn:
        for tname in table_names:
            # Detectar PK única y tipo entero con introspección SQL
            try:
                pk_row = conn.execute(
                    text(
                        """
                        SELECT a.attname AS col
                        FROM   pg_index i
                        JOIN   pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                        WHERE  i.indrelid = :t::regclass
                        AND    i.indisprimary;
                        """
                    ),
                    {"t": tname},
                ).first()
            except Exception:
                pk_row = None
            if not pk_row:
                continue
            pk_col = pk_row[0]

            try:
                seq_name = conn.execute(
                    text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                    {"tbl": tname, "col": pk_col},
                ).scalar()
                if not seq_name:
                    continue

                max_id = conn.execute(
                    text(f'SELECT MAX("{pk_col}") FROM "{tname}"')
                ).scalar()
                if max_id is None:
                    max_id = 0
                conn.execute(
                    text("SELECT setval(:seq, :newval, :is_called)"),
                    {"seq": seq_name, "newval": int(max_id), "is_called": True},
                )
            except Exception:
                # No detengas la migración si falla el setval
                pass


def main() -> None:
    args = parse_args()

    sqlite_dsn = args.sqlite_dsn
    pg_dsn = args.pg_dsn

    # Motores
    src_engine = create_engine(sqlite_dsn, future=True)
    dst_engine = create_engine(pg_dsn, future=True)

    # Reflexión
    src_meta, _ = reflect_metadata(src_engine)
    dst_meta, _ = reflect_metadata(dst_engine)

    if not src_meta.tables:
        print("✖ La BD origen no tiene tablas (¿ruta correcta a SQLite?).")
        sys.exit(1)
    if not dst_meta.tables:
        print("✖ La BD destino no tiene tablas (crea el esquema/migraciones primero).")
        sys.exit(1)

    # Filtrado de tablas si se especificó --tables
    requested: Optional[Set[str]] = None
    if args.tables.strip():
        requested = {t.strip() for t in args.tables.split(",") if t.strip()}

    # Intersección de tablas existentes en ambos esquemas
    common_tables = [t for t in src_meta.tables.keys() if t in dst_meta.tables]
    if requested:
        common_tables = [t for t in common_tables if t in requested]

    if not common_tables:
        print("✖ No hay tablas comunes entre origen y destino para copiar.")
        sys.exit(1)

    # Orden por dependencias (usamos metadata de destino, que es quien aplica constraints)
    order = topo_sort_tables(dst_meta, set(common_tables))

    print("Tablas a copiar (en orden):")
    for t in order:
        print(f"  - {t}")

    if args.truncate:
        print("→ TRUNCATE CASCADE de tablas destino (RESTART IDENTITY)")
        truncate_all(dst_engine, order)

    total_copiadas = 0
    for tname in order:
        src_tbl = src_meta.tables.get(tname)
        dst_tbl = dst_meta.tables.get(tname)
        # 👇 evitar evaluación booleana de Table (TypeError)
        if src_tbl is None or dst_tbl is None:
            print(f"• Omitiendo {tname} (no existe en ambos esquemas).")
            continue

        try:
            count = copy_table(src_engine, dst_engine, src_tbl, dst_tbl, batch_size=args.batch)
            print(f"✔ {tname}: {count} filas copiadas.")
            total_copiadas += count
        except IntegrityError as ie:
            print(f"✖ {tname}: conflicto de integridad: {ie}")
            sys.exit(1)
        except SQLAlchemyError as se:
            print(f"✖ {tname}: error SQL: {se}")
            sys.exit(1)

    # Ajustar secuencias
    try:
        reset_identity_sequences(dst_engine, order)
    except Exception:
        pass

    print(f"\n✅ Migración terminada. Total filas copiadas: {total_copiadas}")


if __name__ == "__main__":
    main()
