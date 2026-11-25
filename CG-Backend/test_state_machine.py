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

import ast
import json
import os
import re
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
    "request_timestamp", "total_modules", "update_mode", "user_email", "user_id",
    "lesson_ids_to_update",
}

AUSENTE = object()

# Claves que el Starter añade sólo en la rama ``skip_theory_generation``
# (``execution_input["resume_from"]`` y ``master_lab_plan_result``).
ENTRADA_REANUDADA = {"resume_from", "master_lab_plan_result"}


def _definicion():
    with open(_RUTA_DEFINICION, encoding="utf-8") as fichero:
        return json.load(fichero)


def _raiz(ruta):
    """Primer segmento de una ruta JSONPath: ``$.a.b`` → ``a``."""
    return ruta[2:].split(".")[0].split("[")[0]


def _raices_resueltas(parametros):
    """Raíces de entrada que un objeto ``Parameters`` resuelve con JSONPath.

    A bare ``$.field`` is a reference path. An intrinsic such as
    ``States.ArrayContains($.field, 'x')`` also reads that field; the wildcard
    form ``$.items[*].field`` is a projection and is not a single reference.
    """
    raices = set()
    for clave, ruta in parametros.items():
        if not (clave.endswith(".$") and isinstance(ruta, str)):
            continue
        if ruta.startswith("$."):
            if _raiz(ruta):
                raices.add(_raiz(ruta))
            continue
        for hallazgo in re.findall(r"(?<!\$)\$\.([A-Za-z_][A-Za-z0-9_]*)", ruta):
            raices.add(hallazgo)
    return raices


def _raices_consumidas(estado):
    """Campos de la entrada que la tarea resuelve con JSONPath en su ``Payload``."""
    return _raices_resueltas((estado.get("Parameters") or {}).get("Payload") or {})


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


def _claves_que_envia_el_starter():
    """Claves que el Starter deja en ``execution_input``/``update_input``.

    Recoge el dict literal y las asignaciones por índice (``execution_input["x"]``),
    que es como se añaden los campos opcionales.
    """
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "lambda", "starter_api.py"
    )
    with open(ruta, encoding="utf-8") as fichero:
        arbol = ast.parse(fichero.read())
    objetivos = ("execution_input", "update_input")
    enviados = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if isinstance(destino, ast.Name) and destino.id in objetivos:
                if isinstance(nodo.value, ast.Dict):
                    enviados[destino.id] = {
                        clave.value
                        for clave in nodo.value.keys
                        if isinstance(clave, ast.Constant)
                    }
            elif isinstance(destino, ast.Subscript):
                nombre = getattr(destino.value, "id", None)
                clave = getattr(destino.slice, "value", None)
                if nombre in objetivos and isinstance(clave, str):
                    enviados.setdefault(nombre, set()).add(clave)
    return enviados


def _datos_del_flujo(modo, resume):
    datos = {
        "content_type": modo,
        "lesson_to_generate": None,
        "lesson_ids_to_update": None,
        "update_mode": None,
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
    if "Not" in condicion:
        return not _cumple(condicion["Not"], datos)
    variable = condicion.get("Variable")
    valor = _resolver(datos, variable)
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
    claves = set(ENTRADA) | (ENTRADA_REANUDADA if resume else set())
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
                faltan = _raices_resueltas(estado["Parameters"]) - claves
                assert not faltan, (
                    f"en el flujo content_type='{modo}', el Pass '{actual}' resuelve "
                    f"{sorted(faltan)} con JSONPath y la entrada ya no los tiene: en "
                    f"ejecución fallaría con States.Runtime"
                )
                # ResultPath "$" replaces the input. Any other ResultPath keeps the
                # input and writes the Pass result at that node.
                ruta = estado.get("ResultPath", "$")
                if ruta in (None, "$"):
                    claves = _raices_de_parametros(estado["Parameters"])
                else:
                    claves.add(_raiz(ruta))
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


def test_el_starter_envia_las_claves_que_el_flujo_exige():
    """La simulación asume que el Starter siempre manda ``ENTRADA``: hay que verificarlo.

    Fallo real que fija esta prueba (03/11/2026): el §46 añadió ``update_mode`` y
    ``lesson_ids_to_update`` a los ``Pass`` y a los ``Payload``, y la simulación —que
    parte de ``ENTRADA``— seguía en verde. Pero ``execution_input`` del Starter no los
    incluía: **toda** generación nueva (y todo reanudado tras la teoría) moría en
    ``BothTheoryAndLabsBranch`` con ``States.Runtime`` a los pocos segundos, cinco
    ejecuciones seguidas, antes de pagar una sola llamada al modelo.

    Se lee el fuente con ``ast`` (importar el módulo arrastraría boto3 y S3): los
    literales de ``execution_input``/``update_input`` son el contrato con el cableado.
    """
    enviados = _claves_que_envia_el_starter()
    for nombre in ("execution_input", "update_input"):
        assert nombre in enviados, (
            f"no se encontró el dict literal '{nombre}' en lambda/starter_api.py"
        )
        faltan = ENTRADA - enviados[nombre]
        assert not faltan, (
            f"'{nombre}' no envía {sorted(faltan)}, que el flujo resuelve con JSONPath: "
            f"la ejecución fallaría con States.Runtime"
        )
    faltan = ENTRADA_REANUDADA - enviados["execution_input"]
    assert not faltan, (
        f"'execution_input' no añade {sorted(faltan)} en la rama de reanudación: "
        f"ResumePostTheoryBranch fallaría con States.Runtime"
    )


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


def test_la_setup_guide_se_genera_despues_de_los_labs_y_no_bloquea():
    """La guía consume el plan y los ``lab-*.md``: va después del escritor.

    Un fallo de la guía no puede invalidar un curso ya generado: el ``Catch``
    vuelve a ``NotifyCompletion`` y deja el error en ``$.setup_guide_error``.
    """
    estados = _definicion()["States"]
    assert estados["InvokeLabGuideBuilder"]["Next"] == "InvokeSetupGuide"
    guia = estados["InvokeSetupGuide"]
    assert guia["Next"] == "InvokePostGenerationAudit"
    assert guia["Parameters"]["Payload"]["project_folder.$"] == "$.project_folder"
    assert guia["Parameters"]["Payload"]["course_bucket.$"] == "$.course_bucket"
    atrapa = guia["Catch"][0]
    assert atrapa["Next"] == "NotifyCompletion", (
        "un fallo de la Setup Guide no debe invalidar el curso"
    )
    assert atrapa["ResultPath"] == "$.setup_guide_error"


def test_la_auditoria_posterior_cierra_el_flujo_sin_bloquear():
    """Manifiesto y enlaces son evidencia: un fallo no invalida el curso."""
    estados = _definicion()["States"]
    assert estados["InvokeSetupGuide"]["Next"] == "InvokePostGenerationAudit"
    auditoria = estados["InvokePostGenerationAudit"]
    assert auditoria["Next"] == "InvokeDeckBuilder"
    assert auditoria["Parameters"]["Payload"]["project_folder.$"] == "$.project_folder"
    assert auditoria["Catch"][0]["Next"] == "NotifyCompletion"
    assert auditoria["Catch"][0]["ResultPath"] == "$.audit_error"


def _destino_de_choice(estado, datos):
    destino = estado.get("Default")
    for eleccion in estado.get("Choices") or []:
        condiciones = eleccion.get("And") or [eleccion]
        if all(_cumple(c, datos) for c in condiciones):
            return eleccion["Next"]
    return destino


def test_la_puerta_no_entrega_hallazgos_de_alta_confianza():
    """After the final retry, high-confidence findings leave the success path.

    Structural errors still go to NotifyFailure. Shadow mode still bypasses.
    A clean lab (all_valid, no needs_review) still builds the book.
    """
    estados = _definicion()["States"]
    puerta = estados["CheckLabValidation"]

    assert _destino_de_choice(puerta, {
        "lab_validation_result": {"all_valid": True},
        "lab_quality_decision": {"needs_review": True},
    }) == "StampLabWriterQuality"

    assert _destino_de_choice(puerta, {
        "lab_validation_shadow": True,
        "lab_validation_result": {"all_valid": False},
        "lab_quality_decision": {"needs_review": True},
    }) == "InvokeLabGuideBuilder"

    assert _destino_de_choice(puerta, {
        "lab_validation_result": {"all_valid": False},
        "lab_quality_decision": {"needs_review": False},
    }) == "NotifyFailure"

    assert _destino_de_choice(puerta, {
        "lab_validation_result": {"all_valid": True},
        "lab_quality_decision": {"needs_review": False},
    }) == "InvokeLabGuideBuilder"

    fallo = estados["FailLabQualityGate"]
    assert fallo["Type"] == "Fail"
    assert fallo["Error"] == "LabQualityNeedsReview"
    assert fallo["CausePath"] == "$.quality_gate.cause"
    aviso = estados["NotifyQualityReview"]
    assert aviso["Parameters"]["Payload"]["status"] == "needs_review"
    assert aviso["Next"] == "FailLabQualityGate"
    assert aviso["Catch"][0]["Next"] == "FailLabQualityGate"


def test_el_plan_con_hallazgos_de_alta_no_sigue_como_exito():
    estados = _definicion()["States"]
    solo_labs = _destino_de_choice(estados["CheckLabPlannerResult"], {
        "lab_planner_result": {
            "Payload": {
                "statusCode": 200,
                "master_plan_key": "plan.json",
                "total_labs": 2,
                "quality_status": "needs_review",
            }
        }
    })
    assert solo_labs == "StampLabsPlanQuality"
    limpio = _destino_de_choice(estados["CheckLabPlannerResult"], {
        "lab_planner_result": {
            "Payload": {
                "statusCode": 200,
                "master_plan_key": "plan.json",
                "total_labs": 2,
                "quality_status": "passed",
            }
        }
    })
    assert limpio == "ExpandLabsToBatches"

    ambos = _destino_de_choice(estados["CheckMasterLabPlanResult"], {
        "master_lab_plan_result": {
            "Payload": {"statusCode": 200, "quality_status": "needs_review"}
        }
    })
    assert ambos == "StampBothPlanQuality"


def test_los_lotes_propagan_el_estado_de_calidad():
    estados = _definicion()["States"]
    for mapa, completo in (
        ("ProcessLabBatchesInParallel", "LabBatchComplete"),
        ("ProcessLabBatchesInParallelBoth", "LabBatchCompleteBoth"),
    ):
        parametros = estados[mapa]["Iterator"]["States"][completo]["Parameters"]
        assert parametros["quality_status.$"] == "$.lab_result.Payload.quality_status"
        assert parametros["labs_needing_review.$"] == "$.lab_result.Payload.labs_needing_review"
    for nombre, evaluacion in (
        ("CombineLabResults", "EvaluateLabQualityGate"),
        ("CombineLabResultsBoth", "EvaluateLabQualityGateBoth"),
    ):
        parametros = estados[nombre]["Parameters"]
        assert parametros["lab_quality_statuses.$"] == (
            "$.all_lab_batches_results[*].quality_status"
        )
        assert "States.ArrayContains" not in parametros["lab_quality_statuses.$"]
        assert estados[nombre]["Next"] == evaluacion
        decision = estados[evaluacion]
        assert decision["ResultPath"] == "$.lab_quality_decision"
        assert decision["Parameters"]["needs_review.$"] == (
            "States.ArrayContains($.lab_quality_statuses, 'needs_review')"
        )
    assert "States.JsonToString($.lab_quality_summaries)" in (
        estados["StampLabWriterQuality"]["Parameters"]["cause.$"]
    )
    selector = estados["GenerateLabMasterPlan"]["ResultSelector"]["Payload"]
    assert selector["quality_status.$"] == "$.Payload.quality_status"
    assert selector["quality_summary.$"] == "$.Payload.quality_summary"


def test_los_decks_se_generan_tras_la_auditoria_y_no_bloquean():
    """Glosario y Tips & Tricks son evidencia adicional: su fallo no invalida el curso."""
    estados = _definicion()["States"]
    assert estados["InvokePostGenerationAudit"]["Next"] == "InvokeDeckBuilder"
    decks = estados["InvokeDeckBuilder"]
    assert decks["Next"] == "NotifyCompletion"
    assert decks["Parameters"]["FunctionName"] == "${DeckBuilderArn}"
    assert decks["Parameters"]["Payload"]["project_folder.$"] == "$.project_folder"
    assert decks["Parameters"]["Payload"]["course_bucket.$"] == "$.course_bucket"
    atrapa = decks["Catch"][0]
    assert atrapa["Next"] == "NotifyCompletion"
    assert atrapa["ResultPath"] == "$.decks_error"


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
