"""Offline tests for THOR Setup Guide capabilities profile (audit backlog #7)."""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "lambda", "setup_guide_builder"))
sys.path.insert(0, os.path.join(_HERE, "lambda"))

from setup_guide_capabilities import (  # noqa: E402
    filter_hardware_requirements,
    filter_software_requirements,
    is_infrastructure_detail,
    software_to_capabilities,
    syllabus_requirement_corpus,
)
def test_omite_powershell_si_el_temario_no_lo_nombra():
    plan = {
        "software_requirements": [
            {"name": "PowerShell", "version": "7.4", "purpose": "Shell"},
            {"name": "Microsoft 365 Copilot", "version": "1.0", "license": "M365"},
        ]
    }
    corpus = ""
    filtrado = filter_software_requirements(plan["software_requirements"], corpus)
    assert [item["name"] for item in filtrado] == ["Microsoft 365 Copilot"]


def test_conserva_powershell_cuando_el_temario_lo_exige():
    plan = {
        "additional_requirements": "Laboratorios en PowerShell 7 sobre Windows Server",
        "software_requirements": [
            {"name": "PowerShell", "version": "7.4", "purpose": "Shell"},
            {"name": "VS Code", "version": "1.92", "purpose": "Editor"},
        ],
    }
    corpus = syllabus_requirement_corpus({}, plan, {})
    filtrado = filter_software_requirements(plan["software_requirements"], corpus)
    nombres = {item["name"] for item in filtrado}
    assert "PowerShell" in nombres
    assert "VS Code" not in nombres


def test_omite_rutas_locales_en_hardware():
    reqs = [
        "C:\\Forecasting_Logistica\\",
        "16 GB RAM",
    ]
    filtrado = filter_hardware_requirements(reqs, corpus="")
    assert filtrado == ["16 GB RAM"]


def test_capabilities_mapean_licencia_y_acceso():
    software = [
        {
            "name": "Azure OpenAI",
            "version": "2024-05-01",
            "license": "Enterprise",
            "source": "https://learn.microsoft.com/",
            "purpose": "Deployment access",
            "pending": False,
        }
    ]
    caps = software_to_capabilities(software)
    assert caps[0]["capability"] == "Azure OpenAI"
    assert caps[0]["license"] == "Enterprise"
    assert "learn.microsoft.com" in caps[0]["access"]
    assert caps[0]["permission"] == "Deployment access"


def test_is_infrastructure_detail_detecta_vscode():
    assert is_infrastructure_detail("Visual Studio Code 1.92")


def test_la_plantilla_prioriza_la_tabla_de_capacidades():
    from jinja2 import Template

    template_path = os.path.join(_HERE, "lambda", "setup_guide_builder", "setup_guide_template.py")
    namespace = {}
    with open(template_path, encoding="utf-8") as handle:
        exec(handle.read(), namespace)  # noqa: S102
    html = Template(namespace["SETUP_GUIDE_TEMPLATE"]).render(
        capabilities=[
            {
                "capability": "Microsoft 365 Copilot",
                "license": "M365 E3",
                "access": "https://learn.microsoft.com/",
                "permission": "Chat en Word",
                "version": "1.0",
                "pending": False,
            }
        ],
        software=[],
        infrastructure={"hardware": [], "network": []},
        previous_knowledge={"network": [], "accounts": [], "licenses": [], "permissions": [], "timing": []},
        accesses=[],
        preparation=[],
        validation={"checklist": [], "full_test": "", "troubleshooting": []},
        lab_matrix=[],
        references=[],
        identification={"links": []},
        counters=[],
        additional_requirements="",
        course_title="Demo",
        course_key="X",
        version="1",
        status="BORRADOR",
        last_validation="—",
        description="",
        date="Nov 2026",
        repo_url="",
        logo_path="",
    )
    assert "Capacidades, licencias y accesos" in html
    assert "PERFIL DE CAPACIDADES" in html
    assert "Microsoft 365 Copilot" in html


if __name__ == "__main__":
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    fallos = []
    for name, fn in tests:
        try:
            fn()
            print(f"ok     {name}")
        except Exception as exc:  # noqa: BLE001
            fallos.append((name, exc))
            print(f"FALLO  {name}: {exc}")
    print(f"\n{len(tests) - len(fallos)}/{len(tests)} pruebas correctas")
    sys.exit(1 if fallos else 0)