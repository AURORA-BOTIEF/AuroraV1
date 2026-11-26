"""Offline tests for the LPI-010 golden lab few-shot (THOR audit item 9)."""

import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock

_HERE = os.path.dirname(os.path.abspath(__file__))
_WRITER_DIR = os.path.join(_HERE, "lambda", "strands_lab_writer")


def _cargar_writer_sin_aws():
    previos = {nombre: sys.modules.get(nombre) for nombre in list(sys.modules)}
    boto3_sim = MagicMock()
    botocore_sim = MagicMock()
    botocore_sim.exceptions = MagicMock()
    sys.modules.update(
        {
            "boto3": boto3_sim,
            "botocore": botocore_sim,
            "botocore.config": MagicMock(),
            "botocore.exceptions": botocore_sim.exceptions,
        }
    )
    for nombre in (
        "strands_lab_writer",
        "golden_lab_example",
        "optional_fields",
        "audience_adaptation",
        "referent_check",
        "measurable_evidence",
        "reading_budget",
    ):
        sys.modules.pop(nombre, None)
    if _WRITER_DIR in sys.path:
        sys.path.remove(_WRITER_DIR)
    sys.path.insert(0, _WRITER_DIR)
    try:
        return importlib.import_module("strands_lab_writer")
    finally:
        for nombre, previo in previos.items():
            if previo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = previo


def _cargar_golden():
    sys.modules.pop("golden_lab_example", None)
    if _WRITER_DIR in sys.path:
        sys.path.remove(_WRITER_DIR)
    sys.path.insert(0, _WRITER_DIR)
    return importlib.import_module("golden_lab_example")


def _lab_plan_tecnico():
    return {
        "lab_id": "02-01-01",
        "lab_title": "Gestionar permisos en Linux",
        "estimated_duration": 25,
        "bloom_level": "Apply",
        "objectives": ["Interpretar permisos con ls -l"],
        "scope": "Práctica de línea de comandos en Ubuntu",
        "prerequisites": [],
        "key_technologies": ["Linux", "bash"],
        "expected_outcomes": [],
        "outline_objective": "Aplicar chmod y chown sobre ficheros de práctica.",
        "outline_description": "El alumno trabaja solo en el directorio del laboratorio.",
    }


def _master_context_es():
    return {
        "target_language": "Spanish (Español)",
        "manual_reference_text": "",
        "additional_requirements": "",
        "hardware_requirements": [],
        "software_requirements": [],
        "special_considerations": [],
        "overall_objectives": [],
    }


class GoldenLabExampleTests(unittest.TestCase):
    def test_la_fixture_se_carga_y_contiene_el_marcador_de_recorte(self):
        golden = _cargar_golden()
        texto = golden.load_golden_lab_slice()
        self.assertIn("GOLDEN_SLICE_END", texto)
        self.assertIn("### Paso 1:", texto)
        self.assertLess(len(texto), 6000, "el few-shot debe mantenerse pequeño")

    def test_el_prompt_vivo_incluye_el_ejemplo_para_lab_tecnico_especificado(self):
        modulo = _cargar_writer_sin_aws()
        golden = _cargar_golden()
        prompt = modulo._compact_single_lab_prompt(
            _lab_plan_tecnico(),
            _master_context_es(),
            "",
            "resumen del lab",
        )
        self.assertIn(golden.GOLDEN_LAB_SECTION_MARKER, prompt)
        self.assertIn("---BEGIN GOLDEN LAB SLICE---", prompt)
        self.assertIn("Inspeccionar permisos y propiedad en Linux", prompt)
        self.assertIn("chmod 750 scripts/backup.sh", prompt)

    def test_el_prompt_vivo_omite_el_ejemplo_en_demo(self):
        modulo = _cargar_writer_sin_aws()
        golden = _cargar_golden()
        plan = dict(_lab_plan_tecnico(), lab_title="Demo: Mostrar permisos en Linux")
        prompt = modulo._compact_single_lab_prompt(plan, _master_context_es(), "", "resumen")
        self.assertNotIn(golden.GOLDEN_LAB_SECTION_MARKER, prompt)

    def test_el_prompt_vivo_omite_el_ejemplo_sin_contrato_de_temario(self):
        modulo = _cargar_writer_sin_aws()
        golden = _cargar_golden()
        plan = dict(_lab_plan_tecnico())
        plan.pop("outline_objective")
        plan.pop("outline_description")
        plan["objectives"] = []
        plan["key_technologies"] = []
        prompt = modulo._compact_single_lab_prompt(plan, _master_context_es(), "", "resumen")
        self.assertNotIn(golden.GOLDEN_LAB_SECTION_MARKER, prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)