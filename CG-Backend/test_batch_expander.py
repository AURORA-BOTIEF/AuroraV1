# -*- coding: utf-8 -*-
"""Actualización de contenidos en BatchExpander: la lista manda, lotes contiguos."""

import io
import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))

OUTLINE = """
course:
  title: Curso de prueba
  language: es
  modules:
    - title: 'Módulo 1'
      lessons:
        - title: 'L1'
        - title: 'L2'
        - title: 'L3'
    - title: 'Módulo 2'
      lessons:
        - title: 'L1'
        - title: 'L2'
        - title: 'L3'
"""


def _cargar_modulo():
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", "batch_expander")
    previos = {n: sys.modules.get(n) for n in nombres}

    class _Cuerpo:
        def __init__(self, bytes_data):
            self._bytes = bytes_data

        def read(self):
            return self._bytes

    class _S3:
        def __init__(self, objetos):
            self._objetos = objetos

        def get_object(self, Bucket, Key):
            return {"Body": _Cuerpo(self._objetos[Key])}

    boto3_sim = types.ModuleType("boto3")
    s3_sim = _S3({"c/o/.yaml": OUTLINE.encode()})
    boto3_sim.client = lambda *a, **k: s3_sim
    botocore_sim = types.ModuleType("botocore")
    config_sim = types.ModuleType("botocore.config")
    config_sim.Config = lambda *a, **k: None
    exceptions_sim = types.ModuleType("botocore.exceptions")
    exceptions_sim.ClientError = Exception
    botocore_sim.config = config_sim
    botocore_sim.exceptions = exceptions_sim
    sys.modules.update(
        {
            "boto3": boto3_sim,
            "botocore": botocore_sim,
            "botocore.config": config_sim,
            "botocore.exceptions": exceptions_sim,
        }
    )
    sys.modules.pop("batch_expander", None)
    ruta = os.path.join(_HERE, "lambda")
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    try:
        import importlib

        return importlib.import_module("batch_expander")
    finally:
        for clave, valor in previos.items():
            if valor is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = valor


def _evento(lesson_ids, single=None):
    return {
        "course_bucket": "b",
        "outline_s3_key": "c/o/.yaml",
        "project_folder": "p",
        "modules_to_generate": [1, 2],
        "lesson_ids_to_update": lesson_ids,
        "lesson_to_generate": single,
    }


def _resumen_batches(respuesta):
    items = []
    for batch in respuesta["batches"]:
        items.append((batch["module_number"], batch["batch_start_idx"], batch["batch_end_idx"]))
    return items


def test_la_lista_cubre_exactamente_las_lecciones_pedidas():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["01-2", "02-1", "02-3"]), None)
    assert respuesta["statusCode"] == 200, respuesta
    # '01-2' → módulo 1, lección 2 (idx 1). '02-1' e '02-3' NO son contiguas → grupos.
    items = _resumen_batches(respuesta)
    assert items == [
        (1, 1, 2),
        (2, 0, 1),
        (2, 2, 3),
    ], items
    for _, _, _, batch in [
        (b["module_number"], b["batch_start_idx"], b["batch_end_idx"], b) for b in respuesta["batches"]
    ]:
        assert batch["force_regenerate"] is True
        assert batch["update_contents"] is True


def test_lecciones_contiguas_se_juntan_en_un_lote():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["01-2", "01-3"]), None)
    assert _resumen_batches(respuesta) == [(1, 1, 3)]


def test_sin_lista_no_hay_lotes_nuevos():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento([]), None)
    # Sin selección: el flujo normal sigue (módulos completos, sin force).
    assert respuesta["total_batches"] == 6
    for batch in respuesta["batches"]:
        assert batch.get("update_contents") is None
        assert batch["force_regenerate"] is False


def test_la_lista_prevalece_sobre_la_individual():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["01-2"], single="01-03"), None)
    items = _resumen_batches(respuesta)
    assert items == [(1, 1, 2)], items


def test_unidades_filares_se_ignoran():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["basura", "02-2"]), None)
    assert _resumen_batches(respuesta) == [(2, 1, 2)]


def test_unicamente_a_fuera_de_rango():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["01-9"]), None)
    # No hay nada que actualizar: cero lotes (intención selectiva, sin derrames).
    assert respuesta.get("batches") == [] or respuesta["total_batches"] == 0


def test_unidades_fuera_de_rango_se_ignoran():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["01-9", "01-1"]), None)
    # Lección 9 fuera de rango (3 lecciones); queda solo la lección 1.
    assert _resumen_batches(respuesta) == [(1, 0, 1)]


def test_otros_modulos_no_se_tocan_en_actualizacion():
    modulo = _cargar_modulo()
    respuesta = modulo.lambda_handler(_evento(["02-2"]), None)
    assert _resumen_batches(respuesta) == [(2, 1, 2)], _resumen_batches(respuesta)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pruebas = [
        (nombre, funcion)
        for nombre, funcion in sorted(globals().items())
        if nombre.startswith("test_") and callable(funcion)
    ]
    fallos = []
    for nombre, funcion in pruebas:
        try:
            funcion()
        except Exception as exc:  # noqa: BLE001 - informe de test
            fallos.append((nombre, exc))
            print(f"FALLO  {nombre}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
