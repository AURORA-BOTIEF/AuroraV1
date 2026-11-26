"""Image-loop degradation and optional start fields. No AWS and no model calls."""

from __future__ import annotations

import importlib.util
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_LAMBDA = os.path.join(_AQUI, "lambda")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")


def _cargar(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_lote = _cargar(os.path.join(_LAMBDA, "images_gen", "image_batch.py"), "image_batch_under_test")
_opcionales = _cargar(os.path.join(_LAMBDA, "optional_fields.py"), "optional_fields_root")
_planner = _cargar(
    os.path.join(_LAMBDA, "strands_lab_planner", "optional_fields.py"),
    "optional_fields_planner",
)
_writer = _cargar(
    os.path.join(_LAMBDA, "strands_lab_writer", "optional_fields.py"),
    "optional_fields_writer",
)


def _prompts():
    return [
        {"id": "01-01-0001", "description": "diagrama"},
        {"id": "01-01-0002", "description": "tabla"},
    ]


def test_un_lote_fallido_consume_los_prompts_y_avisa():
    fallos = [
        {"id": "01-01-0001", "status": "failed", "error": "404 models/none"},
        {"id": "01-01-0002", "status": "failed", "error": "404 models/none"},
    ]
    cierre = _lote.cerrar_lote(_prompts(), 2, fallos, fallos, [], None)
    assert cierre["remaining_prompts"] == []
    assert cierre["statistics_remaining"] == 0
    assert cierre["quality_issue"]["step"] == "GenerateBatchImages"
    assert cierre["quality_issue"]["severity"] == "warning"
    assert "no se reintentan" in cierre["quality_issue"]["error"]
    assert "will not be retried" in cierre["quality_issue"]["error"]
    assert "01-01-0001" in cierre["quality_issue"]["error"]


def test_el_timeout_conserva_solo_lo_no_intentado():
    fallos = [{"id": "01-01-0001", "status": "failed", "error": "429"}]
    prompts = _prompts() + [{"id": "01-01-0003", "description": "mapa"}]
    cierre = _lote.cerrar_lote(prompts, 1, fallos, fallos, [], None)
    assert [item["id"] for item in cierre["remaining_prompts"]] == ["01-01-0002", "01-01-0003"]
    assert cierre["statistics_remaining"] == 2
    assert "01-01-0001" in cierre["quality_issue"]["error"]
    assert "01-01-0002" not in cierre["quality_issue"]["error"]


def test_un_lote_exitoso_no_inventa_un_hallazgo_y_conserva_el_previo():
    previo = {
        "step": "GenerateBatchImages",
        "severity": "warning",
        "error": "1 imagen(es) fallaron y no se reintentan: 01-01-0001. 1 image(s) failed and will not be retried: 01-01-0001.",
    }
    nuevas = [{"id": "01-01-0002", "status": "ok", "s3_key": "p/images/01-01-0002.png"}]
    cierre = _lote.cerrar_lote(_prompts(), 2, [], nuevas, [{"id": "01-01-0001", "status": "failed"}], previo)
    assert cierre["quality_issue"]["error"] == previo["error"]
    assert [item["id"] for item in cierre["accumulated_images"]] == ["01-01-0001", "01-01-0002"]
    assert cierre["statistics_remaining"] == 0


def test_states_array_anidado_se_aplana():
    anidado = [[[], [{"id": "a", "status": "ok"}]], [{"id": "b", "status": "ok"}]]
    assert [item["id"] for item in _lote.fusionar_imagenes(anidado, [{"id": "c", "status": "ok"}])] == [
        "a",
        "b",
        "c",
    ]
    assert _lote.fusionar_imagenes([[], [{"id": "a", "status": "ok"}]], [])[0]["id"] == "a"


def test_none_y_vacio_desactivan_el_modelo_y_un_modelo_real_no():
    assert _lote.modelo_desactivado("none") is True
    assert _lote.modelo_desactivado(" None ") is True
    assert _lote.modelo_desactivado("") is True
    assert _lote.modelo_desactivado("   ") is True
    assert _lote.modelo_desactivado(None) is False
    assert _lote.modelo_desactivado("models/gemini-2.5-flash-image") is False
    respuesta = _lote.respuesta_sin_imagenes(
        course_bucket="b",
        project_folder="p",
        accumulated_images=[[], [{"id": "a", "status": "ok"}]],
        message="Modelo de imagen vacío o 'none': no se generan imágenes. image_model is empty or 'none': images are not generated.",
    )
    assert respuesta["statistics"]["remaining"] == 0
    assert respuesta["remaining_prompts"] == []
    assert respuesta["quality_issue"] is None
    assert respuesta["accumulated_images"][0]["id"] == "a"
    assert "no se generan imágenes" in respuesta["message"]
    assert "images are not generated" in respuesta["message"]


def test_el_handler_con_modelo_none_no_deja_prompts_pendientes():
    sys.path.insert(0, os.path.join(_LAMBDA, "images_gen"))
    import images_gen

    class _Ctx:
        def get_remaining_time_in_millis(self):
            return 900000

    salida = images_gen.lambda_handler(
        {
            "course_bucket": "bucket",
            "project_folder": "curso",
            "image_model": "none",
            "prompts": _prompts(),
            "accumulated_images": [],
        },
        _Ctx(),
    )
    assert salida["statusCode"] == 200
    assert salida["statistics"]["remaining"] == 0
    assert salida["remaining_prompts"] == []
    assert salida["image_mappings"] == {}
    assert "quality_issue" in salida
    assert salida["quality_issue"] is None


def test_los_opcionales_se_leen_con_get_y_no_pisan_un_valor_real():
    for modulo in (_opcionales, _planner, _writer):
        assert modulo.CAMPOS_OPCIONALES_DE_INICIO == _opcionales.CAMPOS_OPCIONALES_DE_INICIO
        completo = {
            "lab_requirements": "usar Docker",
            "manual_s3_keys": ["manual.pdf"],
            "manual_text_s3_key": "curso/manual.txt",
            "lab_ids_to_regenerate": ["01-01-01"],
            "lesson_to_generate": "01-02",
            "lesson_requirements": "incluir un diagrama",
            "lesson_ids_to_update": ["01-02"],
            "quality_issues": {"ready": True},
            "provider_lock": {"acquired": True},
            "course_bucket": "bucket",
        }
        leido = modulo.leer_campos_opcionales(completo)
        assert leido["lab_requirements"] == "usar Docker"
        assert leido["manual_s3_keys"] == ["manual.pdf"]
        assert leido["lesson_ids_to_update"] == ["01-02"]
        assert "quality_issues" not in leido
        assert "provider_lock" not in leido
        vacio = modulo.leer_campos_opcionales({"course_bucket": "bucket", "outline_s3_key": "o.yaml"})
        assert all(valor is None for valor in vacio.values())
        assert modulo.leer_campos_opcionales(None)["lab_requirements"] is None


def test_la_clave_del_plan_real_gana_y_el_estado_completo_tambien_sirve():
    estado = {
        "course_bucket": "bucket",
        "project_folder": "curso",
        "lab_planner_result": {"Payload": {"master_plan_key": "anidado.json"}},
        "master_lab_plan_result": {"Payload": {"master_plan_key": "ambos.json"}},
    }
    assert _opcionales.resolver_master_plan_key(estado) == "anidado.json"
    assert _opcionales.resolver_master_plan_key({"master_plan_key": "real.json", **estado}) == "real.json"
    solo_ambos = {"master_lab_plan_result": {"Payload": {"master_plan_key": "ambos.json"}}}
    assert _writer.resolver_master_plan_key(solo_ambos) == "ambos.json"


def test_el_reintento_estructural_no_pisa_un_lote_con_lab_ids():
    lote = {
        "lab_ids": ["01-01-01"],
        "force_regenerate": False,
        "master_plan_key": "plan.json",
        "manual_text_s3_key": "curso/manual.txt",
        "course_bucket": "bucket",
        "extra": {"no": "importa"},
    }
    normal = _writer.normalizar_evento_writer(lote)
    assert normal["lab_ids"] == ["01-01-01"]
    assert normal["force_regenerate"] is False
    assert normal["manual_text_s3_key"] == "curso/manual.txt"
    assert normal["extra"] == {"no": "importa"}

    estado = {
        "course_bucket": "bucket",
        "project_folder": "curso",
        "master_plan_key": "plan.json",
        "lab_validation_result": {"invalid_lab_ids": ["01-02-01", ""]},
        "quality_issues": {"ready": True},
        "manual_text_s3_key": "curso/manual.txt",
    }
    reintento = _writer.normalizar_evento_writer(estado)
    assert reintento["lab_ids"] == ["01-02-01"]
    assert reintento["force_regenerate"] is True
    assert reintento["structural_retry"] is True
    assert reintento["manual_text_s3_key"] == "curso/manual.txt"
    assert reintento["lab_requirements"] is None

    sin_manual = _writer.normalizar_evento_writer(
        {
            "master_lab_plan_result": {"Payload": {"master_plan_key": "ambos.json"}},
            "lab_validation_result": {"invalid_lab_ids": ["01-01-01"]},
            "course_bucket": "bucket",
        }
    )
    assert sin_manual["master_plan_key"] == "ambos.json"
    assert sin_manual["lab_ids"] == ["01-01-01"]
    assert sin_manual["manual_text_s3_key"] is None


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
        except Exception as exc:
            fallos.append((nombre, exc))
            print(f"FALLO  {nombre}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
