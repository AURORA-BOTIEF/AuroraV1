"""Contrato de la máquina de estados: ningún flujo puede perder campos por el camino.

Artefacto bajo prueba: ``CG-Backend/current_state_machine.json``, que es el
``DefinitionUri`` del stack (el despliegue publica exactamente este JSON). No se
inspecciona el fuente de ninguna Lambda: se recorre el grafo que se despliega con
una entrada realista y se comprueba que cada tarea encuentra los campos que pide.

Fallo real que fijan estas pruebas (22/10/2026): ``ExpandLabsToBatchesBoth`` pide
``$.manual_text_s3_key``, pero los ``Pass`` que construyen su entrada enumeran los
campos a mano y lo omitían. Un curso de 2 módulos murió en ese estado con
``States.Runtime`` **después** de pagar teoría e imágenes. Ninguna prueba de unidad
lo veía: sólo existe en el cableado.

Segundo fallo que apareció al escribir esta prueba: el flujo sólo-teoría
(``PrepareNewCourseParams``) también perdía los manuales antes de
``ExpandModulesToBatches``, que los exige. Es decir, ``content_type='theory'`` no
podía arrancar.

Por qué una simulación y no una búsqueda de texto: los caminos se bifurcan por
``content_type``, así que un ``Pass`` puede omitir un campo que su consumidor pide
sin que ese consumidor sea alcanzable desde él. La simulación evalúa las
condiciones y sólo exige el contrato en los caminos que de verdad se recorren.
"""

import json
import os
import sys

_RUTA_DEFINICION = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "current_state_machine.json"
)

# Claves que el StarterApi deja siempre en el input de la ejecución
# (starter_api.py, construcción de ``execution_input``).
ENTRADA = {
    "allow_openai_fallback", "content_source", "content_type", "course_bucket",
    "course_duration_hours", "course_language", "course_topic", "image_model",
    "lab_ids_to_regenerate", "lab_requirements", "lesson_requirements",
    "lesson_to_generate", "manual_s3_keys", "manual_text_s3_key", "model_provider",
    "modules_to_generate", "outline_s3_key", "performance_mode", "project_folder",
    "request_timestamp", "total_modules", "user_email", "user_id",
}

AUSENTE = object()


def _definicion():
    with open(_RUTA_DEFINICION, encoding="utf-8") as fichero:
        return json.load(fichero)


def _raiz(ruta):
    """Primer segmento de una ruta JSONPath: ``$.a.b`` → ``a``."""
    return ruta[2:].split(".")[0].split("[")[0]


def _raices_consumidas(estado):
    """Campos de la entrada que el estado resuelve con JSONPath."""
    payload = (estado.get("Parameters") or {}).get("Payload") or {}
    raices = set()
    for clave, ruta in payload.items():
        if clave.endswith(".$") and isinstance(ruta, str) and ruta.startswith("$."):
            if _raiz(ruta):
                raices.add(_raiz(ruta))
    return raices


def _raices_de_parametros(parametros):
    """Campos que quedan disponibles cuando un Pass construye el objeto a mano.

    Un ``Pass`` con ``Parameters`` produce exactamente esas claves: ``foo.$`` pasa a
    ser ``foo``, con el valor ya resuelto. Lo que importa para el consumidor es el
    nombre resultante, no de dónde salió el valor.
    """
    return {
        clave[:-2] if clave.endswith(".$") else clave
        for clave in parametros
    }


def _result_path(estado, claves):
    ruta = estado.get("ResultPath")
    if ruta is None or ruta == "$":
        # Reemplaza la entrada entera: la simulación dejaría de saber qué hay.
        raise AssertionError(
            f"'{estado}' no declara ResultPath; la simulación necesita saber qué "
            f"campos siguen disponibles después de la tarea"
        )
    claves.add(_raiz(ruta))


def _datos_del_flujo(modo, resume):
    datos = {
        "content_type": modo,
        "lesson_to_generate": None,
        "lesson_requirements": "",
        "resume_from": "post_theory" if resume else None,
        "provider_lock": {"acquired": True},
        "batch_expansion": {"Payload": {"statusCode": 200, "batches": [{"lab_ids": []}]}},
        "lab_batch_expansion": {"Payload": {"statusCode": 200, "batches": [{"lab_ids": []}]}},
        "lab_validation_result": {"all_valid": True},
    }
    if modo in ("both", "labs"):
        datos["master_lab_plan_result"] = {
            "Payload": {"statusCode": 200, "total_labs": 2, "master_plan_key": "plan.json"}
        }
        datos["lab_planner_result"] = {
            "Payload": {"statusCode": 200, "total_labs": 2, "master_plan_key": "plan.json"}
        }
    return datos


def _resolver(datos, ruta):
    if not ruta.startswith("$."):
        return AUSENTE
    actual = datos
    for parte in ruta[2:].split("."):
        nombre = parte.split("[")[0]
        if not isinstance(actual, dict) or nombre not in actual:
            return AUSENTE
        actual = actual[nombre]
    return actual


def _cumple(condicion, datos):
    variable = condicion.get("Variable")
    valor = _resolver(datos, variable)
    if condicion.get("IsPresent"):
        return valor is not AUSENTE
    if "IsNull" in condicion:
        if valor is AUSENTE:
            return False
        return (valor is None) == bool(condicion["IsNull"])
    if "StringEquals" in condicion:
        return valor == condicion["StringEquals"]
    if "NumericEquals" in condicion:
        return valor == condicion["NumericEquals"]
    if "BooleanEquals" in condicion:
        return valor is condicion["BooleanEquals"]
    return False


def _recorrer(estados, modo, resume=False):
    """Sigue el camino que tomaría el motor y valida cada tarea que visita."""
    datos = _datos_del_flujo(modo, resume)
    claves = set(ENTRADA)
    actual = _definicion()["StartAt"]
    visitados = []

    for _ in range(200):
        estado = estados[actual]
        visitados.append(actual)
        tipo = estado.get("Type")

        if tipo in ("Succeed", "Fail"):
            return visitados

        if tipo == "Task":
            faltan = _raices_consumidas(estado) - claves
            assert not faltan, (
                f"en el flujo content_type='{modo}', el estado '{actual}' pide "
                f"{sorted(faltan)} y la entrada ya no los tiene: en ejecución "
                f"fallaría con States.Runtime"
            )
            _result_path(estado, claves)
        elif tipo == "Pass":
            if estado.get("Parameters"):
                claves = _raices_de_parametros(estado["Parameters"])
        elif tipo == "Choice":
            destino = estado.get("Default")
            for eleccion in estado.get("Choices") or []:
                condiciones = eleccion.get("And") or [eleccion]
                if all(_cumple(c, datos) for c in condiciones):
                    destino = eleccion["Next"]
                    break
            assert destino, f"'{actual}' no tiene salida posible"
            actual = destino
            continue
        elif tipo in ("Map", "Parallel"):
            _result_path(estado, claves)
            # No se inspeccionan los iteradores: dentro de un Map la entrada es el
            # ítem, no el objeto de la ejecución.
        elif tipo != "Wait":
            raise AssertionError(f"tipo de estado no contemplado en '{actual}': {tipo}")

        actual = estado["Next"]

    raise AssertionError("el recorrido no terminó: ¿hay un ciclo sin salida?")


def test_el_flujo_solo_teoria_llega_al_final_sin_perder_campos():
    visitados = _recorrer(_definicion()["States"], "theory")
    assert visitados[-1] == "SuccessState", visitados[-1]
    assert "ExpandModulesToBatches" in visitados
    assert "ExpandLabsToBatchesBoth" not in visitados


def test_el_flujo_solo_laboratorios_llega_al_final_sin_perder_campos():
    visitados = _recorrer(_definicion()["States"], "labs")
    assert visitados[-1] == "SuccessState", visitados[-1]
    assert "ExpandLabsToBatches" in visitados


def test_el_flujo_teoria_y_laboratorios_llega_al_final_sin_perder_campos():
    visitados = _recorrer(_definicion()["States"], "both")
    assert visitados[-1] == "SuccessState", visitados[-1]
    assert "ExpandModulesToBatches" in visitados
    assert "ExpandLabsToBatchesBoth" in visitados


def test_el_flujo_reanudado_tras_la_teoria_llega_al_final_sin_perder_campos():
    visitados = _recorrer(_definicion()["States"], "both", resume=True)
    assert visitados[-1] == "SuccessState", visitados[-1]
    assert "ResumePostTheoryBranch" in visitados
    assert "ExpandLabsToBatchesBoth" in visitados


def test_los_lotes_de_laboratorio_siguen_siendo_secuenciales():
    """El informe referencial se acumula en un único objeto de S3.

    La acumulación es segura porque el Writer procesa un laboratorio por lote y los
    lotes van de uno en uno (``MaxConcurrency: 1``). Si alguien sube la concurrencia,
    dos invocaciones leerían el mismo objeto y la última pisaría a la otra: el
    artefacto volvería a perder laboratorios en silencio.
    """
    estados = _definicion()["States"]
    for mapa in ("ProcessLabBatchesInParallel", "ProcessLabBatchesInParallelBoth"):
        assert estados[mapa].get("MaxConcurrency") == 1, (
            f"{mapa} debe mantener MaxConcurrency 1 mientras el informe referencial "
            f"se acumule en S3"
        )


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
