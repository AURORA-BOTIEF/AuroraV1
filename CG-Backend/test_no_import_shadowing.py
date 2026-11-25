"""Static guard: no function-level import may shadow a module global used earlier.

THOR QA 25/11/2026: ``generate_complete_course`` had ``import os`` inside an
``if`` block, so ``os.environ`` at its top raised UnboundLocalError and every
PPT batch failed.
"""
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_FILES = [
    os.path.join(_HERE, "lambda", "strands_infographic_generator", "html_first_generator.py"),
    os.path.join(_HERE, "lambda", "strands_infographic_generator", "infographic_generator.py"),
]


def _shadowing(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    globales = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                globales.add((alias.asname or alias.name).split(".")[0])
    problemas = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        locales = {}
        for node in ast.walk(func):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    nombre = (alias.asname or alias.name).split(".")[0]
                    if nombre in globales:
                        locales.setdefault(nombre, node.lineno)
        for nombre, linea in locales.items():
            usos = [
                n.lineno for n in ast.walk(func)
                if isinstance(n, ast.Name) and n.id == nombre and n.lineno < linea
            ]
            if usos:
                problemas.append(f"{os.path.basename(path)}:{func.name}: {nombre} used at {usos[0]} before local import at {linea}")
    return problemas


def test_ninguna_importacion_local_tapa_un_global_usado_antes():
    problemas = []
    for path in _FILES:
        if os.path.exists(path):
            problemas.extend(_shadowing(path))
    assert not problemas, problemas


if __name__ == "__main__":
    test_ninguna_importacion_local_tapa_un_global_usado_antes()
    print("1/1 pruebas correctas")
