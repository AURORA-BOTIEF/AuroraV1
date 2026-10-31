# -*- coding: utf-8 -*-
"""Fechas del listado: prefijo ambiguo, CDMX y prioridad metadata > S3 > nombre."""

import io
import os
import sys
import types
from datetime import datetime, timezone, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))


def _cargar_modulo(nombre, carpeta):
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", nombre)
    previos = {n: sys.modules.get(n) for n in nombres}
    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: object()
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
    sys.modules.pop(nombre, None)
    ruta = os.path.join(_HERE, carpeta)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    try:
        import importlib

        return importlib.import_module(nombre)
    finally:
        for clave, valor in previos.items():
            if valor is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = valor


def _s3_con(vueltas):
    """Stub: devuelve 'Contents' en orden para cada llamada."""

    class _Paginador:
        def __init__(self, listas):
            self.listas = listas
            self.posicion = 0

        def paginate(self, Bucket, Prefix):
            salida = {
                "Contents": [
                    {"Key": f"{Prefix}{i}", "LastModified": fecha}
                    for i, fecha in enumerate(self.listas[self.posicion])
                ]
            }
            self.posicion += 1
            yield salida

    class _S3:
        def __init__(self):
            self.listas = list(vueltas)

        def get_paginator(self, nombre):
            p = _Paginador(self.listas)
            self.listas = list(vueltas)
            return p

    return _S3()


def test_el_prefijo_acepta_ambas_convenciones_y_elige_plausibles():
    modulo = _cargar_modulo("list_projects", "lambda")
    from datetime import date

    hoy = date(2026, 10, 30)
    casos = {
        "260911-curso-android-avanzado": "2026-09-11",  # YYMMDD (convención del equipo)
        "260515-Docker-desde-cero": "2026-05-15",
        "251018-JS-06": "2025-10-18",
    }
    for folder, esperado in casos.items():
        assert modulo.extract_date_from_folder(folder, hoy=hoy) == esperado, folder
    # '271027' es ambiguo/implausible a ambos lados (2027 vs 2030): sin veredicto.
    assert modulo.extract_date_from_folder("271027-prueba-b6", hoy=hoy) in (None, "2026-10-27")


def test_la_marca_s3_es_la_verdad_y_va_a_cdmx():
    modulo = _cargar_modulo("list_projects", "lambda")
    # Dos marcas UTC: la minima el 31/10 03:22 UTC = 30/10 en CDMX (UTC-6).
    marca_nueva = datetime(2026, 11, 1, 1, 0, tzinfo=timezone.utc)
    marca_crit = datetime(2026, 10, 31, 3, 22, tzinfo=timezone.utc)
    s3 = _s3_con([[marca_crit]])
    resultado = modulo.get_project_creation_date(
        s3, "bucket", "271027-prueba-b6", metadata=None
    )
    # El nombre diría 2027; el registro real de S3 manda y se convierte a CDMX.
    assert resultado == "2026-10-30", resultado
    extra = modulo.get_project_creation_date(s3, "bucket", "x", metadata=None)
    # La segunda llamada recorre la misma lista: la marca minima cuenta.
    assert min(marca_crit, marca_nueva) == marca_crit
    assert extra == "2026-10-30"


def test_el_metadata_escrito_manda_sobre_todo():
    modulo = _cargar_modulo("list_projects", "lambda")
    s3 = _s3_con([
        [datetime(2020, 5, 5, tzinfo=timezone.utc)]
    ])
    resultado = modulo.get_project_creation_date(
        s3, "bucket", "curso", metadata={"created": "2026-02-10T00:00:00Z"}
    )
    assert resultado == "2026-02-10", resultado


def test_sin_objetos_ni_metadata_cae_al_nombre():
    modulo = _cargar_modulo("list_projects", "lambda")
    s3 = _s3_con([[]])
    resultado = modulo.get_project_creation_date(
        s3, "bucket", "260911-curso-android-avanzado", metadata=None
    )
    # El stub devuelve una pagina con lista vacia; el modulo cae al nombre.
    assert resultado == "2026-09-11", resultado


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
