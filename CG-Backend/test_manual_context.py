"""Pruebas del paso 0 de calidad: selección del manual por relevancia.

Regresión que fijan estas pruebas: el pipeline recortaba el manual por encabezado
(``manual[:10000]``/``[:12000]``/``[:14000]``). En un manual real (~230.000
caracteres) eso es ~5% del documento, así que el contenido específico de cada
laboratorio quedaba fuera del prompt y el modelo lo inventaba. Aquí se verifica
que ese contenido ahora se recupera aunque esté muy al final del manual.

No requieren AWS, red ni dependencias externas. Se pueden ejecutar de dos formas:

    python test_manual_context.py     # ejecución directa
    pytest test_manual_context.py     # si pytest está disponible
"""

import io
import os
import sys
import tokenize
from contextlib import contextmanager

_HERE = os.path.dirname(os.path.abspath(__file__))
for _carpeta in ("strands_lab_writer", "strands_lab_planner", "strands_content_gen"):
    sys.path.insert(0, os.path.join(_HERE, "lambda", _carpeta))

from manual_context import (  # noqa: E402
    _normalize,
    flatten_to_text,
    select_manual_context,
)

# Relleno sin términos de la consulta: simula las primeras ~43.000 letras de un
# manual real, que es todo lo que veía el modelo con el recorte por encabezado.
_PADDING = (
    "El documento describe consideraciones generales de la plataforma y su "
    "operacion habitual dentro de la organizacion. "
) * 400

_RELEVANT = """
Procedimiento de memoria de intercambio
Crear el archivo swapfile reservando el espacio con fallocate, ajustar los
permisos con chmod, inicializarlo con mkswap y activarlo con swapon antes de
declararlo en fstab para que persista tras el reinicio.
"""

_MANUAL = "=== MANUAL: guia.pdf ===\n" + _PADDING + _RELEVANT


@contextmanager
def _entorno(**valores):
    """Fija variables de entorno y las restaura al salir (sin depender de pytest)."""
    previos = {k: os.environ.get(k) for k in valores}
    os.environ.update(valores)
    try:
        yield
    finally:
        for clave, previo in previos.items():
            if previo is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = previo


def test_recupera_contenido_mas_alla_del_recorte_por_encabezado():
    """El fallo original: lo relevante está al final y el recorte por encabezado lo pierde."""
    presupuesto = 5_000
    encabezado = _normalize(_MANUAL[:presupuesto])
    assert "swapfile" not in encabezado.split(), (
        "precondición: el recorte por encabezado NO debe ver el contenido relevante"
    )

    excerpt = select_manual_context(
        _MANUAL,
        "crear swapfile con fallocate y activarlo con mkswap y swapon",
        title_text="Configurar memoria swap persistente",
        max_chars=presupuesto,
    )

    terminos = set(_normalize(excerpt).split())
    assert "swapfile" in terminos
    assert "fallocate" in terminos
    assert "mkswap" in terminos
    assert "swapon" in terminos


def test_respeta_el_presupuesto():
    for presupuesto in (1_000, 3_000, 8_000):
        excerpt = select_manual_context(
            _MANUAL, "swapfile fallocate", title_text="swap", max_chars=presupuesto
        )
        assert len(excerpt) <= presupuesto, presupuesto


def test_es_determinista():
    kwargs = dict(title_text="configurar ram", max_chars=6_000)
    primero = select_manual_context(_MANUAL, "mkswap swapon", **kwargs)
    segundo = select_manual_context(_MANUAL, "mkswap swapon", **kwargs)
    assert primero == segundo


def test_insensible_a_acentos_y_mayusculas():
    """El temario viene en YAML con acentos y el manual de un PDF: deben coincidir."""
    manual = _PADDING + "\nConfiguracion de la memoria de intercambio persistente.\n"
    excerpt = select_manual_context(
        manual, "CONFIGURACIÓN de la MEMORIA de intercambio", max_chars=4_000
    )
    assert "intercambio" in _normalize(excerpt)


def test_manual_pequeno_se_devuelve_completo():
    manual = "Manual corto de prueba."
    assert select_manual_context(manual, "cualquier cosa", max_chars=30_000) == manual


def test_sin_consulta_cae_al_recorte_por_encabezado():
    """Degradación segura: sin consulta útil se mantiene el comportamiento anterior."""
    assert select_manual_context(_MANUAL, "", max_chars=4_000) == _MANUAL[:4_000]


def test_texto_vacio_no_falla():
    assert select_manual_context("", "swapfile") == ""
    assert select_manual_context("   ", "swapfile") == ""


def test_interruptor_de_apagado_vuelve_al_recorte_por_encabezado():
    with _entorno(MANUAL_CONTEXT_ENABLED="0"):
        excerpt = select_manual_context(
            _MANUAL, "swapfile mkswap", title_text="swap", max_chars=4_000
        )
    assert excerpt == _MANUAL[:4_000]


def test_presupuesto_por_variable_de_entorno():
    with _entorno(MANUAL_CONTEXT_MAX_CHARS="2500"):
        excerpt = select_manual_context(_MANUAL, "swapfile mkswap", title_text="swap")
    assert len(excerpt) <= 2500


def test_variable_de_entorno_invalida_usa_el_valor_por_defecto():
    with _entorno(MANUAL_CONTEXT_MAX_CHARS="no-es-un-numero"):
        excerpt = select_manual_context(_MANUAL[:20_000], "swapfile", title_text="swap")
    assert len(excerpt) <= 30_000


def test_consulta_con_tipos_inesperados_no_falla():
    for inesperado in (None, {}, [], 123, {"a": None}):
        excerpt = select_manual_context(
            _MANUAL, flatten_to_text(inesperado), title_text="", max_chars=3_000
        )
        assert isinstance(excerpt, str)


def test_flatten_to_text_aplana_estructuras():
    plan = {
        "lab_title": "Practica de red",
        "objectives": ["configurar interfaz", "validar enlace"],
        "scope": {"detalle": "ajustar mtu"},
        "duracion": 45,
    }
    texto = flatten_to_text(plan)
    assert "Practica de red" in texto
    assert "configurar interfaz" in texto
    assert "ajustar mtu" in texto
    assert "45" in texto
    assert "objectives" not in texto  # las claves no ensucian la consulta


def test_las_tres_copias_del_modulo_son_identicas():
    """El módulo se replica en tres Lambdas: debe mantenerse byte a byte idéntico."""
    rutas = [
        os.path.join(_HERE, "lambda", c, "manual_context.py")
        for c in ("strands_lab_writer", "strands_lab_planner", "strands_content_gen")
    ]
    with open(rutas[0], "rb") as f0, open(rutas[1], "rb") as f1, open(rutas[2], "rb") as f2:
        assert f0.read() == f1.read() == f2.read(), (
            "las copias de manual_context.py se han desincronizado"
        )


def _sin_comentarios(codigo: str) -> str:
    """Sustituye los comentarios por espacios (misma longitud y offsets).

    Necesario porque los comentarios que documentan el arreglo citan el recorte
    antiguo, y no queremos que esa cita cuente como si el recorte siguiera ahí.
    """
    lineas = codigo.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(codigo).readline):
        if token.type == tokenize.COMMENT:
            fila, columna = token.start
            fin = token.end[1]
            linea = lineas[fila - 1]
            lineas[fila - 1] = linea[:columna] + " " * (fin - columna) + linea[fin:]
    return "".join(lineas)


def test_el_pipeline_ya_no_recorta_el_manual_por_encabezado():
    """El recorte literal [:N] sobre el manual no debe volver a aparecer en el código."""
    objetivos = [
        ("strands_lab_writer", "strands_lab_writer.py", ["manual_ref_text[:12000]"]),
        ("strands_content_gen", "strands_content_gen.py", ["manual_reference_text[:14000]"]),
        ("strands_lab_planner", "strands_lab_planner.py", ["man_text[:10000]"]),
    ]
    for carpeta, archivo, fragmentos in objetivos:
        with open(os.path.join(_HERE, "lambda", carpeta, archivo), encoding="utf-8") as fh:
            codigo = _sin_comentarios(fh.read())
        for fragmento in fragmentos:
            assert fragmento not in codigo, f"{archivo} volvió a recortar el manual: {fragmento}"


def test_las_tres_lambdas_usan_el_selector():
    for carpeta, archivo in [
        ("strands_lab_writer", "strands_lab_writer.py"),
        ("strands_content_gen", "strands_content_gen.py"),
        ("strands_lab_planner", "strands_lab_planner.py"),
    ]:
        with open(os.path.join(_HERE, "lambda", carpeta, archivo), encoding="utf-8") as fh:
            codigo = fh.read()
        assert "select_manual_context(" in codigo, f"{archivo} no usa el selector"


if __name__ == "__main__":
    pruebas = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    fallos = []
    for nombre, funcion in pruebas:
        try:
            funcion()
        except AssertionError as exc:
            fallos.append((nombre, exc))
            print(f"FALLO  {nombre}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
