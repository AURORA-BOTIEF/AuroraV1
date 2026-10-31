
"""Decks de Glosario y Tips & Tricks desde los artefactos del curso.

Fuentes trazables, cero invención:

- **Glosario**: ``{proyecto}/book/glosario.json`` (el BookBuilder escribe ahí los
  términos con su fuente) o la sección ``## Glosario`` del book.
- **Tips**: la sección «Solución de Problemas» / «Troubleshooting» de cada
  ``lab-*.md`` (2 casos realistas por laboratorio, con síntoma, causa y remedio).

Python‑pptx viene del PPTLayer. El estado del flujo lo invoca tras la auditoría
y **no bloquea**: un fallo de deck no invalida un curso ya generado.
"""

import io
import json
import os
import re
from datetime import datetime, timezone

import boto3
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

s3 = boto3.client("s3")
BUCKET_POR_DEFECTO = os.getenv("COURSE_BUCKET", "crewai-course-artifacts")

_COLOR_TITULO = RGBColor(0x1F, 0x3B, 0x73)
_COLOR_TEXTO = RGBColor(0x33, 0x33, 0x33)

_RE_LAB = re.compile(r"lab-(\d{2}-\d{2}-\d{2})-", re.IGNORECASE)
_RE_SOLUCION = re.compile(r"^##\s*(?:Solución de Problemas|Troubleshooting)\s*$", re.MULTILINE)
_RE_H3 = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_MD_LIMPIO = re.compile(r"[`*_>#\[\]]")


def _texto(clave, bucket=None):
    """(texto|None)."""
    try:
        cuerpo = s3.get_object(Bucket=bucket, Key=clave)["Body"].read()
        return cuerpo.decode("utf-8", "replace")
    except Exception:
        return None


def _limpiar(texto: str) -> str:
    texto = _MD_LIMPIO.sub("", texto or "")
    return re.sub(r"\s+", " ", texto).strip()


def _seccion_entre_h2(texto: str):
    """Trozos de la sección de solución de problemas de un laboratorio."""
    for m in _RE_SOLUCION.finditer(texto or ""):
        inicio = m.end()
        siguiente = _RE_SOLUCION.search(texto, inicio)
        proximo_h2 = re.search(r"^##\s+", texto[inicio:], re.MULTILINE)
        fin = inicio + (proximo_h2.start() if proximo_h2 else len(texto) - inicio)
        yield texto[inicio:fin]


def _tips_de_lab(texto: str, lab_id: str) -> list[dict]:
    """Por cada subencabezado del bloque de problemas: síntoma y remedio.

    Tolerante a las variantes del corpus: etiquetas con **negrita**, sin ella, y
    remedio en el último párrafo del bloque cuando no lleva etiqueta.
    """
    causas_res = re.compile(r"\s*[*-]?\s*\**\s*Causa\s*[:*]?", re.IGNORECASE)
    remedios_re = re.compile(
        r"\s*[*-]?\s*\**\s*(?:Soluci[oó]n|Remedio|Acciones\s+de\s+correcci[oó]n)\s*[:*]?", re.IGNORECASE
    )
    tips = []
    for tramo in _seccion_entre_h2(texto):
        encabezados = list(_RE_H3.finditer(tramo))
        for idx, m in enumerate(encabezados):
            titulo = _limpiar(m.group(1))[:110]
            cuerpo = tramo[
                m.end() : encabezados[idx + 1].start() if idx + 1 < len(encabezados) else len(tramo)
            ]
            lineas = [salida for salida in (salida.strip() for salida in cuerpo.splitlines()) if salida]
            if not lineas:
                continue
            sintoma, remedio_partes, viendo_remedio = "", [], False
            for salida in lineas:
                if causas_res.match(salida):
                    sintoma = _limpiar(causas_res.sub("", salida))
                    viendo_remedio = False
                elif remedios_re.match(salida):
                    remedio_partes.append(_limpiar(remedios_re.sub("", salida)))
                    viendo_remedio = True
                elif viendo_remedio:
                    remedio_partes.append(_limpiar(salida))
                elif not sintoma and len(_limpiar(salida)) >= 25:
                    sintoma = _limpiar(salida)
            remedio = _limpiar(" ".join(remedio_partes))
            if not remedio and sintoma:
                restantes = [salida for salida in lineas if _limpiar(salida) != sintoma]
                remedio = _limpiar(restantes[-1]) if restantes else ""
            if sintoma and remedio:
                tips.append(
                    {
                        "title": titulo,
                        "sintoma": sintoma[:260],
                        "remedio": remedio[:260],
                        "lab": lab_id,
                    }
                )
    return tips


def terminos_del_glosario(bucket: str, project: str) -> list[dict]:
    data = _texto(f"{project}/book/glosario.json", bucket)
    if data:
        try:
            return json.loads(data).get("terminos") or []
        except json.JSONDecodeError:
            pass
    if data is None:
        for clave in _prefijos(bucket, f"{project}/book/"):
            if clave.endswith("_complete.md"):
                book = _texto(clave, bucket)
                m = re.search(r"^##\s*Glosario\s*$", book or "", re.MULTILINE)
                if m:
                    tramo = book[m.end():] if book else ""
                    tramo = tramo[: tramo.find("\n## ")] if "\n## " in tramo else tramo
                    return [
                        {"term": t.group(1), "definition": t.group(2), "fuente": "book"}
                        for t in re.finditer(r"^\s*[-*]\s+\*\*([^*]{2,80})\*\*:\s*(.+)$", tramo, re.MULTILINE)
                    ]
    return []


def _prefijos(bucket: str, prefijo: str):
    return [
        o["Key"]
        for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefijo)
        for o in pagina.get("Contents", [])
    ]


def _labs(bucket: str, project: str):
    labs = []
    for clave in _prefijos(bucket, f"{project}/labguide/"):
        nombre = clave.split("/")[-1]
        m = _RE_LAB.match(nombre)
        if m and nombre.endswith(".md"):
            texto = _texto(clave, bucket)
            if texto:
                labs.append((m.group(1), texto))
    return sorted(labs)


def _deck(titulo: str, subtitulo: str, slides: list[dict]) -> "Presentation":
    presentacion = Presentation()
    presentacion.slide_width = Inches(13.33)
    presentacion.slide_height = Inches(7.5)

    portada = presentacion.slides.add_slide(presentacion.slide_layouts[0])
    portada.shapes.title.text = titulo
    portada.placeholders[1].text = subtitulo
    for marco in portada.placeholders:
        for parrafo in marco.text_frame.paragraphs:
            for trozo in parrafo.runs:
                trozo.font.color.rgb = _COLOR_TITULO

    for slide_data in slides:
        slide = presentacion.slides.add_slide(presentacion.slide_layouts[1])
        slide.shapes.title.text = slide_data["title"]
        cuerpo = slide.placeholders[1].text_frame
        cuerpo.word_wrap = True
        for idx, linea in enumerate(slide_data["bullets"]):
            parrafo = cuerpo.paragraphs[0] if idx == 0 else cuerpo.add_paragraph()
            parrafo.text = linea[:400]
            parrafo.level = 0
            parrafo.font.size = Pt(16)
            parrafo.font.color.rgb = _COLOR_TEXTO
    return presentacion


def _bytes(presentacion) -> bytes:
    buffer = io.BytesIO()
    presentacion.save(buffer)
    return buffer.getvalue()


def lambda_handler(event, context):
    course_bucket = (event or {}).get("course_bucket") or BUCKET_POR_DEFECTO
    project = ((event or {}).get("project_folder") or "").strip()
    if not project:
        return {"statusCode": 400, "body": json.dumps({"error": "project_folder es requerido"})}

    generados = []

    # --- Glosario --------------------------------------------------------------
    terminos = terminos_del_glosario(course_bucket, project)
    if terminos:
        slides, tramo = [], []
        for idx, entrada in enumerate(terminos):
            definicion = _limpiar(entrada.get("definition") or "")
            tramo.append(f"{_limpiar(entrada['term'])}: {definicion[:300]}")
            if len(tramo) == 4:
                desde = idx - (len(tramo) - 1)
                slides.append(
                    {"title": f"Glosario ({desde + 1} a {idx + 1})", "bullets": list(tramo)}
                )
                tramo = []
        if tramo:
            slides.append({"title": "Glosario (cont.)", "bullets": tramo})
        presentacion = _deck(
            "Glosario", f"{project}", slides or [{"title": "Glosario", "bullets": ["sin términos verificados"]}]
        )
        s3.put_object(
            Bucket=course_bucket,
            Key=f"{project}/deck/Glosario.pptx",
            Body=_bytes(presentacion),
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        generados.append({"deck": "Glosario", "terminos": len(terminos)})

    # --- Tips & Tricks ---------------------------------------------------------
    tips = []
    for lab_id, texto in _labs(course_bucket, project):
        tips.extend(_tips_de_lab(texto, f"Lab {lab_id}"))
    if tips:
        slides = []
        for idx in range(0, len(tips), 2):
            par = tips[idx : idx + 2]
            bullets = []
            for tip in par:
                bullets.append(f"💡 {tip['title']} ({tip['lab']})")
                bullets.append(f"Lectura: {tip['sintoma']}"[:420])
                if tip.get("remedio"):
                    bullets.append(f"Remedio: {tip['remedio']}"[:420])
            slides.append({"title": f"Tips & Tricks ({idx + 1})" if idx else "Tips & Tricks", "bullets": bullets})
        presentacion = _deck("Tips & Tricks", f"{project}", slides)
        s3.put_object(
            Bucket=course_bucket,
            Key=f"{project}/deck/Tips_and_Tricks.pptx",
            Body=_bytes(presentacion),
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        generados.append({"deck": "Tips & Tricks", "tips": len(tips), "labs": len({t['lab'] for t in tips})})

    resumen = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_folder": project,
        "generados": generados,
    }
    s3.put_object(
        Bucket=course_bucket,
        Key=f"{project}/deck/resumen.json",
        Body=json.dumps(resumen, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return {"statusCode": 200, **resumen}
