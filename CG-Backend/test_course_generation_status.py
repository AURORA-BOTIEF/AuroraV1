"""Tests for visible course status when non-blocking steps fail."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lambda"))

from course_generation_status import course_status_label, warnings_from_execution_output  # noqa: E402


def test_setup_guide_error_produces_warning_status():
    output = {
        "project_folder": "demo",
        "setup_guide_error": {"Error": "Runtime", "Cause": "PDF failed"},
    }
    assert course_status_label("SUCCEEDED", output) == "SUCCEEDED_WITH_WARNINGS"
    warnings = warnings_from_execution_output(output)
    assert len(warnings) == 1
    assert warnings[0]["code"] == "setup_guide_error"
    assert warnings[0]["component"] == "Setup Guide"


def test_clean_success_stays_succeeded():
    output = {"project_folder": "demo"}
    assert course_status_label("SUCCEEDED", output) == "SUCCEEDED"
    assert warnings_from_execution_output(output) == []


def test_failed_execution_untouched():
    assert course_status_label("FAILED", {"setup_guide_error": {}}) == "FAILED"


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