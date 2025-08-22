# app/views/alumnos.py
from __future__ import annotations

from typing import Any, Dict, Tuple, Optional
from datetime import date

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    send_file,
    abort,
    request,
    current_app as app,
)
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload

from ..models import db, User, Proyecto, AlumnoProyecto, ReporteBimestral
from ..utils.docx_fill import render_docx

# ---- Fallback si hoy_yyyymmdd no está exportado por docx_fill ----
try:
    from ..utils.docx_fill import hoy_yyyymmdd  # type: ignore
except Exception:
    def hoy_yyyymmdd() -> str:
        """Fecha hoy en formato YYYY-MM-DD (fallback interno)."""
        return date.today().strftime("%Y-%m-%d")

alum_bp = Blueprint("alumnos", __name__, template_folder="../../templates/alumnos")


# ----------------- helpers -----------------
def _get_attr(o: Any, *names: str, default: Any = "") -> Any:
    """Devuelve el primer atributo existente en `o` de la lista `names` con valor no None."""
    for n in names:
        if hasattr(o, n):
            v = getattr(o, n)
            if v is not None:
                return v
    return default


def _nombre_partes(u: User) -> Dict[str, str]:
    """
    Normaliza nombre / apellidos del alumno para tokens:
    - Nombre, Apellido_Paterno, Apellido_Materno
    Acepta diferentes combinaciones de campos.
    """
    ap_pat = (_get_attr(u, "ap_paterno", "apellido_paterno", default="") or "").strip()
    ap_mat = (_get_attr(u, "ap_materno", "apellido_materno", default="") or "").strip()
    nombres = (_get_attr(u, "nombres", default="") or "").strip()

    if not (ap_pat or ap_mat or nombres):
        base = (u.nombre or "").strip()
        parts = base.split()
        if len(parts) >= 3:
            ap_pat = parts[0]
            ap_mat = parts[1]
            nombres = " ".join(parts[2:])
        else:
            return {"Nombre": base, "Apellido_Paterno": "", "Apellido_Materno": ""}

    if not nombres:
        base = (u.nombre or "").strip()
        if base:
            nombres = base

    return {"Nombre": nombres, "Apellido_Paterno": ap_pat, "Apellido_Materno": ap_mat}


def _as_x(val) -> str:
    return "X" if val in ("on", "X", True, 1, "1", "true", "True") else (val or "")


def _markers_5(prefix: str, value: Optional[int]) -> Dict[str, str]:
    """Genera marcadores prefix_0..prefix_4 con 'X' según value (0..4)."""
    d = {f"{prefix}_{i}": "" for i in range(5)}
    if value is not None:
        try:
            vi = int(value)
            if 0 <= vi <= 4:
                d[f"{prefix}_{vi}"] = "X"
        except Exception:
            pass
    return d


def _alias(d: Dict[str, Any], key: str, *aliases: str) -> None:
    """Duplica d[key] en cada alias si aún no existe."""
    if key not in d:
        return
    for a in aliases:
        d.setdefault(a, d[key])


# ----------------- consultas -----------------
def _alumno_asignacion() -> Tuple[Optional[Proyecto], Optional[AlumnoProyecto]]:
    """Devuelve (proyecto, asignacion) del alumno autenticado, o (None, None)."""
    ap = (
        AlumnoProyecto.query.options(
            selectinload(AlumnoProyecto.proyecto).selectinload(Proyecto.departamento),
            selectinload(AlumnoProyecto.proyecto).selectinload(Proyecto.responsable_user),
            selectinload(AlumnoProyecto.alumno),
        )
        .filter(AlumnoProyecto.alumno.has(User.id == current_user.id))
        .order_by(AlumnoProyecto.id.desc())
        .first()
    )
    return (ap.proyecto, ap) if ap else (None, None)


# ----------------- contextos DOCX -----------------
def _ctx_base_alumno_proyecto(p: Proyecto, alumno: User) -> Dict[str, Any]:
    nombre_parts = _nombre_partes(alumno)

    # Alumno / proyecto base (lo que ya tenías)
    no_ctrl = (_get_attr(alumno, "no_control", "num_control", "numero_control", default="") or "").strip()
    carrera = (_get_attr(alumno, "carrera", default="") or "").strip()
    extras = p.extras or {}
    dep_txt = (
        extras.get("AREA_RESPONSABLE")
        or (p.departamento.nombre if getattr(p, "departamento", None) else "")
        or (p.nombre_dependencia or "")
    )
    resp_txt = (
        extras.get("NOMBRE_RESPONSABLE")
        or (p.nombre_responsable or "")
        or (p.responsable_user.nombre if getattr(p, "responsable_user", None) else "")
    )
    cargo_txt = extras.get("CARGO_RESPONSABLE") or (p.cargo_responsable or "")
    programa_txt = (p.nombre_programa or p.nombre or "")

    ctx: Dict[str, Any] = {
        **nombre_parts,
        "No_Control": no_ctrl,
        "Num_Control": no_ctrl,
        "Carrera": carrera,

        "Nombre_Programa": programa_txt,
        "Nombre_programa": programa_txt,
        "Nombre_Proyecto": p.nombre or "",
        "Nombre_proyecto": p.nombre or "",  # <-- usado en Formato Interno

        "Nombre_Dependencia": dep_txt,
        "Departamento_Texto": dep_txt,
        "AREA_RESPONSABLE": dep_txt,

        "Nombre_Responsable": resp_txt,
        "Cargo_Responsable": cargo_txt,

        # ubicación / periodos compartidos
        "Municipio": extras.get("Municipio") or extras.get("municipio") or (p.municipio or ""),
        "Estado": extras.get("Estado") or extras.get("estado") or (p.estado or ""),
        "Periodo": extras.get("Periodo") or "",
        "Periodo_Final": extras.get("Periodo_Final") or extras.get("Periodo") or "",
        "Periodo_Bimestre": extras.get("Periodo") or "",
        "Fecha_Entrega_Final": extras.get("Fecha_Entrega_Final") or hoy_yyyymmdd(),
    }

    # ---------- CAMPOS DEL FORMATO INTERNO (DOCX) ----------
    # Contacto responsable
    ctx["TELEFONO_RESPONSABLE"] = extras.get("TELEFONO_RESPONSABLE", "")
    ctx["CORREO_RESPONSABLE"]   = extras.get("CORREO_RESPONSABLE", "")
    ctx["HORARIO_RESPONSABLE"]  = extras.get("HORARIO_RESPONSABLE", "")

    # Conteos / textos
    ctx["numero_personas"]   = extras.get("numero_personas", "")
    ctx["num_comunidades"]   = extras.get("num_comunidades", "")
    ctx["num_estudiantes"]   = extras.get("num_estudiantes", "")
    ctx["objetivos_proyecto"] = extras.get("objetivos_proyecto", "")
    ctx["metas_proyecto"]     = extras.get("metas_proyecto", "")

    # Checks: impactos, áreas, turnos, carreras
    for key in ["opcion1","opcion2","opcion3","turno1","turno2",
                "carrerera1","carrera2","carrera3","carrera4","carrera5","carrera6","carrera7","carrera8","carrera9",
                "area1","area2","area3","area4","area5","area6"]:
        ctx[key] = _as_x(extras.get(key))

    # Cronograma: actividades (texto) y meses (checks -> "X")
    months = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
    for i in range(1, 6):
        ctx[f"actividad{i}"] = extras.get(f"actividad{i}", "")
        for m in months:
            ctx[f"{m}{i}"] = _as_x(extras.get(f"{m}{i}"))

    # Sinónimos ya existentes
    _alias(ctx, "Nombre_Dependencia", "DEPENDENCIA", "Dependencia", "nombre_dependencia")
    _alias(ctx, "Nombre_Responsable", "NOMBRE_RESPONSABLE", "Nombre_responsable")
    _alias(ctx, "Cargo_Responsable", "CARGO_RESPONSABLE", "Puesto_Responsable", "puesto_responsable")
    _alias(ctx, "Nombre_Programa", "Programa_Nombre", "Nombre_Programa_")
    _alias(ctx, "No_Control", "no_control", "NO_CONTROL")
    _alias(ctx, "Carrera", "carrera", "CARRERA")
    _alias(ctx, "Nombre", "Nombres", "nombre")

    return ctx


def _rb_val(rb: Optional[ReporteBimestral], i: int) -> Optional[int]:
    """Obtiene rb.resp_i si rb existe; si no, None."""
    if rb is None:
        return None
    try:
        return getattr(rb, f"resp_{i}")
    except Exception:
        return None


def _ctx_bimestral_markers(rb: ReporteBimestral) -> Dict[str, Any]:
    """
    Mapea resp_1..7 a los prefijos “raros” de la plantilla bimestral:
      1->TP_resp3, 2->TP_resp5, 3->TP_resp7, 4->TP_resp9, 5->TP_resp11, 6->TP_resp14, 7->TP_resp15
    Añade fechas con y sin acentos y variantes de supervisor/puesto/observaciones.
    También marca bim1/bim2/bim3 y el número de reporte.
    """
    ctx: Dict[str, Any] = {}

    # Radios 0..4 por cada criterio
    mapping = {
        "TP_resp3":  rb.resp_1,
        "TP_resp5":  rb.resp_2,
        "TP_resp7":  rb.resp_3,
        "TP_resp9":  rb.resp_4,
        "TP_resp11": rb.resp_5,
        "TP_resp14": rb.resp_6,
        "TP_resp15": rb.resp_7,
    }
    for prefix, val in mapping.items():
        ctx.update(_markers_5(prefix, val))

    # Fechas (todas las variantes + “degradadas” por tildes en runs)
    d1 = rb.dia1 or ""
    m1 = rb.mes1 or ""
    a1 = rb.ano1 or ""
    d2 = rb.dia2 or ""
    m2 = rb.mes2 or ""
    a2 = rb.ano2 or ""

    ctx.update({
        # sin acento y Camel
        "dia1": d1, "mes1": m1, "ano1": a1,
        "Dia1": d1, "Mes1": m1, "Ano1": a1,
        "dia2": d2, "mes2": m2, "ano2": a2,
        "Dia2": d2, "Mes2": m2, "Ano2": a2,
        # con acentos
        "día1": d1, "año1": a1,
        "día2": d2, "año2": a2,
        # variantes “rotas” comunes cuando Word pierde las tildes
        "da1": d1,   # por 'día1'
        "da2": d2,   # por 'día2'
        "ao1": a1,   # por 'año1'
        "ao2": a2,   # por 'año2'
    })

    # Supervisor / observaciones (con varias variantes)
    ctx.update({
        "Nombre_supervisor": rb.nombre_supervisor or "",
        "Puesto_supervisor": rb.puesto_supervisor or "",
        "observaciones_responsable": rb.observaciones_responsable or "",
    })
    _alias(ctx, "Nombre_supervisor", "Supervisor_Nombre", "NOMBRE_SUPERVISOR")
    _alias(ctx, "Puesto_supervisor", "Supervisor_Puesto", "PUESTO_SUPERVISOR")
    _alias(ctx, "observaciones_responsable", "Observaciones_Responsable", "OBSERVACIONES_RESPONSABLE")

    # Número de reporte y “bimX”
    ctx["num_reporte1_2_3"] = rb.numero or ""
    ctx["bim1"] = "X" if rb.numero == 1 else ""
    ctx["bim2"] = "X" if rb.numero == 2 else ""
    ctx["bim3"] = "X" if rb.numero == 3 else ""

    return ctx


def _ctx_final_markers_from_rb(rb: Optional[ReporteBimestral]) -> Dict[str, Any]:
    """Para la plantilla FINAL: TP_resp_1_* .. TP_resp_7_* (reusa bimestre 3 si no hay final propio)."""
    vals = (
        (_rb_val(rb, 1), _rb_val(rb, 2), _rb_val(rb, 3),
         _rb_val(rb, 4), _rb_val(rb, 5), _rb_val(rb, 6), _rb_val(rb, 7))
        if rb else (None,) * 7
    )
    ctx: Dict[str, Any] = {}
    for i, val in enumerate(vals, start=1):
        ctx.update(_markers_5(f"TP_resp_{i}", val))

    # Además, si en el bimestre 3 hay supervisor/puesto/observaciones, propágalos al FINAL
    if rb:
        if getattr(rb, "nombre_supervisor", None):
            ctx["Nombre_supervisor"] = rb.nombre_supervisor
        if getattr(rb, "puesto_supervisor", None):
            ctx["Puesto_supervisor"] = rb.puesto_supervisor
        if getattr(rb, "observaciones_responsable", None):
            ctx["observaciones_responsable"] = rb.observaciones_responsable

    return ctx


# ----------------- vistas -----------------
@alum_bp.route("/mis-documentos")
@login_required
def mis_documentos():
    p, ap = _alumno_asignacion()
    return render_template("alumnos/mis_documentos.html", proyecto=p, asignacion=ap)


@alum_bp.route("/descargar/<string:tipo>")
@login_required
def descargar(tipo: str):
    """
    tipo ∈ {'interno', 'bimestral', 'final'}.
    Para 'bimestral' se acepta ?num=1|2|3 (si no, toma el último existente).
    """
    p, ap = _alumno_asignacion()
    if not p or not ap:
        abort(403)

    alumno = current_user
    ctx = _ctx_base_alumno_proyecto(p, alumno)

    if tipo == "interno":
        tpl = app.config["TEMPLATE_INTERNO"]
        fname = f"Formato_Interno_{p.nombre or 'proyecto'}.docx"

    elif tipo == "bimestral":
        numero = request.args.get("num", type=int)
        q = ReporteBimestral.query.filter_by(proyecto_id=p.id, alumno_id=alumno.id)
        rb = (
            q.order_by(ReporteBimestral.numero.desc()).first()
            if not numero
            else q.filter_by(numero=numero).first()
        )
        if not rb:
            flash("Aún no tienes reporte bimestral capturado.", "warning")
            abort(404)

        ctx.update(_ctx_bimestral_markers(rb))
        tpl = app.config["TEMPLATE_BIMESTRAL"]
        fname = f"Reporte_Bimestral_{rb.numero}_{p.nombre or 'proyecto'}.docx"

    elif tipo == "final":
        rb3 = ReporteBimestral.query.filter_by(
            proyecto_id=p.id, alumno_id=alumno.id, numero=3
        ).first()
        ctx.update(_ctx_final_markers_from_rb(rb3))
        tpl = app.config["TEMPLATE_FINAL"]
        fname = f"Reporte_Final_{p.nombre or 'proyecto'}.docx"

    else:
        abort(404)

    buf = render_docx(tpl, ctx)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=fname,
    )
