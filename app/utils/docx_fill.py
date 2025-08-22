# app/utils/docx_fill.py
from __future__ import annotations
from io import BytesIO
import zipfile
import re
import html
from datetime import date
from typing import Dict, Iterable

# Caracteres invisibles que Word mete a veces dentro de runs
_ZERO_WIDTH = "\u200b\u200c\u200d\ufeff"

def hoy_yyyymmdd() -> str:
    """Fecha hoy en formato YYYY-MM-DD (disponible para quien lo importe)."""
    return date.today().strftime("%Y-%m-%d")

def _iter_word_xml(names: Iterable[str]) -> Iterable[str]:
    """Todas las partes XML bajo /word/ (document, headers, footers, etc.)."""
    for n in names:
        if n.startswith("word/") and n.endswith(".xml"):
            yield n

# ---- Normalización de placeholders ----
# Bloque contiguous por si viene limpio
_PLACEHOLDER_BLOCK = re.compile(r"\{\{(?:.|\s)*?\}\}")

# "Ruido" permitido entre llaves: espacios, zero-width y tags XML
_NOISE = r"(?:\s|(?:%s)|<[^>]+>)*" % "|".join(re.escape(ch) for ch in _ZERO_WIDTH)

# Dos llaves de apertura/cierre con "ruido" intercalado (runs partidos)
_SPLIT_BLOCK = re.compile(r"\{" + _NOISE + r"\{(?P<body>.*?)\}" + _NOISE + r"\}", re.DOTALL)

def _clean_inside(raw: str) -> str:
    """
    - Elimina TODAS las etiquetas XML
    - Elimina espacios, NBSP y caracteres zero-width
    - Deja sólo [A-Za-z0-9_{}]
    - Compacta llaves múltiples a {{...}}
    """
    text_only = re.sub(r"<[^>]+>", "", raw)
    text_only = text_only.replace("\xa0", "")
    for ch in _ZERO_WIDTH:
        text_only = text_only.replace(ch, "")
    text_only = re.sub(r"[^A-Za-z0-9_{}]+", "", text_only)
    text_only = re.sub(r"^\{+\{", "{{", text_only)
    text_only = re.sub(r"\}+\}$", "}}", text_only)
    return text_only

def render_docx(template_path_or_bytes, ctx: Dict[str, object]) -> BytesIO:
    """
    Rellena un DOCX con placeholders {{CLAVE}}.
    No modifica estructura ni estilos; sólo sustituye los tokens.
    """
    # Abrir la plantilla (ruta o BytesIO)
    zsrc = zipfile.ZipFile(template_path_or_bytes)
    files = {name: zsrc.read(name) for name in zsrc.namelist()}
    zsrc.close()

    for name in _iter_word_xml(files.keys()):
        xml = files[name].decode("utf-8", errors="ignore")

        # Quitar marcas que rompen la continuidad de runs
        xml = re.sub(r"</?w:proofErr[^>]*>", "", xml)
        xml = re.sub(r"</?w:smartTag[^>]*>", "", xml)

        # 1) Normaliza casos con llaves partidas:  { <tags> {  ... } <tags> }
        #    Aplica en bucle por si hay varios en la misma parte.
        while True:
            new_xml = _SPLIT_BLOCK.sub(lambda m: _clean_inside("{{" + m.group("body") + "}}"), xml)
            if new_xml == xml:
                break
            xml = new_xml

        # 2) Normaliza placeholders contiguos que tengan tags dentro: {{ ... }}
        xml = _PLACEHOLDER_BLOCK.sub(lambda m: _clean_inside(m.group(0)), xml)

        # 3) Reemplazos directos por contexto (escape XML)
        for k, v in ctx.items():
            vv = "" if v is None else str(v)
            xml = xml.replace("{{" + k + "}}", html.escape(vv))

        # (No borramos los que queden sin valor para poder diagnosticarlos)
        files[name] = xml.encode("utf-8")

    # Reempaquetar DOCX
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, data in files.items():
            zout.writestr(n, data)
    out.seek(0)
    return out

# ------------- util opcional de diagnóstico -------------
_UNFILLED_FINDER = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")

def debug_unfilled(docx_bytes: BytesIO) -> None:
    """Imprime en consola los placeholders que sobrevivieron sin llenar."""
    try:
        docx_bytes.seek(0)
        z = zipfile.ZipFile(docx_bytes)
        seen = set()
        for name in _iter_word_xml(z.namelist()):
            xml = z.read(name).decode("utf-8", errors="ignore")
            for m in _UNFILLED_FINDER.finditer(xml):
                seen.add(m.group(1))
        z.close()
        if seen:
            print("[docx_fill] Placeholders sin llenar:", sorted(seen))
        else:
            print("[docx_fill] Todo mapeado correctamente.")
    except Exception as e:
        print("[docx_fill] debug_unfilled error:", e)
