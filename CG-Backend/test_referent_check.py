"""Pruebas de la verificación de integridad referencial (A1 en el plan, B1 en cada laboratorio).

El fallo que fijan estas pruebas es concreto y medido (16/10/2026): el plan maestro
generado afirmaba ``Demanda_Historica.xlsx``, ``Practica1_MAPE_SKU.xlsx`` y la carpeta
``C:\\Forecasting_Logistica\\``, ausentes **por completo** del temario y del manual. El
Writer, después, los obedecía letra por letra. Es decir: el dato inventado nace en el
plan y se propaga hacia abajo.

Regla de tres niveles que se verifica aquí:
    1. declarado en una fuente (temario, manual, documentos)  -> se puede afirmar;
    2. creado antes por el propio laboratorio                  -> se puede afirmar;
    3. ni una cosa ni la otra                                  -> se omite o se marca.

Disciplina de las pruebas: toda verificación nueva trae al menos una prueba que
**ejecuta el camino vivo** (el expansor de lotes, el prompt compacto del Writer, el
handler completo del Writer), no que busca texto en el fuente. Buscar texto no habría
detectado el fallo de propagación que motivó estas pruebas.

No requieren AWS, red, credenciales ni dependencias externas:

    python test_referent_check.py     # ejecución directa
    pytest test_referent_check.py     # si pytest está disponible
"""

import json
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_CARPETA_WRITER = os.path.join("lambda", "strands_lab_writer")
_CARPETA_PLANNER = os.path.join("lambda", "strands_lab_planner")
for _ruta in (_CARPETA_WRITER, _CARPETA_PLANNER, "lambda"):
    sys.path.insert(0, os.path.join(_HERE, _ruta))

from referent_check import (  # noqa: E402
    auditar_contrato,
    auditar_duraciones_curso,
    auditar_laboratorio,
    auditar_plan,
    canonico,
    duracion_declarada,
    extraer_referentes,
    mensaje_de_correccion,
    reconciliar_contrato,
    reconciliar_duraciones,
    referencias_a_labs_posteriores,
    referentes_creados,
    requisitos_declarados,
    salidas_de_laboratorios,
)

# --------------------------------------------------------------------------- #
# Fixtures: fuentes reales (temario + manual) y referentes inventados reales
# --------------------------------------------------------------------------- #

# El temario declara el laboratorio y el archivo que entrega el instructor.
_TEMARIO = """
course:
  title: "Analitica de inventario y demanda"
modules:
  - module_number: 1
    lessons:
      - lesson_number: 1
        title: "Exploracion de datos"
        lab_activities:
          - title: "Analizar la demanda historica"
            description: "Abrir el archivo datos_ventas.xlsx entregado por el instructor y calcular indicadores."
            duration_minutes: 45
"""

# El manual declara dos archivos y una carpeta generica. Nombra el concepto
# "demanda historica" en prosa, pero NO el fichero Demanda_Historica.xlsx.
_MANUAL = """
=== MANUAL: guia-analitica.pdf ===
El curso trabaja con el archivo datos_ventas.xlsx que entrega el instructor.
Guarde sus resultados en el archivo resultados.md.
Trabaje siempre dentro de la carpeta de trabajo indicada por el instructor.
La demanda historica se analiza por SKU en la segunda parte del curso.
"""

_FUENTES = _TEMARIO + "\n" + _MANUAL

# Referentes que la evidencia real demostró inventados.
_INVENTADOS = (
    "C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx",
    "Practica1_MAPE_SKU.xlsx",
    "C:\\Forecasting_Logistica\\",
)

_LAB_PLAN = {
    "lab_id": "01-01-01",
    "lab_title": "Analizar la demanda historica",
    "objectives": ["Calcular indicadores por SKU"],
    "scope": "Analisis de la serie de demanda",
    "estimated_duration": 45,
    "bloom_level": "Apply",
    "complexity": "medium",
    "prerequisites": [],
    "key_technologies": ["Excel"],
}


# --------------------------------------------------------------------------- #
# Utilidades: cargar módulos Lambda sin AWS
# --------------------------------------------------------------------------- #

class _ClienteSimulado:
    def __getattr__(self, _nombre):
        return lambda *a, **k: None


class _Cuerpo:
    def __init__(self, texto):
        self._texto = texto

    def read(self):
        return self._texto.encode("utf-8")


class _S3Simulado:
    """S3 en memoria: solo lo que usan el expansor y el handler del Writer."""

    def __init__(self, objetos=None):
        self.objetos = objetos or {}
        self.puts = []

    def get_object(self, Bucket=None, Key=None):  # noqa: N803 - firma de boto3
        if Key not in self.objetos:
            raise KeyError(f"objeto simulado inexistente: {Key}")
        return {"Body": _Cuerpo(self.objetos[Key])}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        cuerpo = kwargs.get("Body", "")
        if isinstance(cuerpo, bytes):
            cuerpo = cuerpo.decode("utf-8")
        self.objetos[kwargs.get("Key")] = cuerpo
        return {}


def _cargar_modulo(nombre, carpeta):
    """Importa un módulo Lambda con boto3 simulado: sin AWS ni credenciales."""
    nombres = ("boto3", "botocore", "botocore.config", "botocore.exceptions", nombre)
    previos = {n: sys.modules.get(n) for n in nombres}

    class _ClientErrorSimulado(Exception):
        pass

    boto3_sim = types.ModuleType("boto3")
    boto3_sim.client = lambda *a, **k: _ClienteSimulado()
    botocore_sim = types.ModuleType("botocore")
    config_sim = types.ModuleType("botocore.config")
    config_sim.Config = lambda *a, **k: None
    exceptions_sim = types.ModuleType("botocore.exceptions")
    exceptions_sim.ClientError = _ClientErrorSimulado
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

        modulo = importlib.import_module(nombre)
        return modulo
    finally:
        for clave, previo in previos.items():
            if previo is None:
                sys.modules.pop(clave, None)
            else:
                sys.modules[clave] = previo


# --------------------------------------------------------------------------- #
# Extracción de referentes
# --------------------------------------------------------------------------- #

def test_extrae_rutas_y_ficheros_ignorando_la_prosa():
    texto = (
        "Abre C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx y guarda "
        "Practica1_MAPE_SKU.xlsx. La demanda historica en general es estable."
    )
    valores = [r["valor"] for r in extraer_referentes(texto)]
    assert "C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx" in valores
    assert "Practica1_MAPE_SKU.xlsx" in valores
    assert all("demanda historica" not in v for v in valores), (
        "la prosa no debe confundirse con un referente de fichero"
    )


def test_el_nombre_de_fichero_no_se_confunde_con_su_descripcion():
    """«Demanda_Historica.xlsx» no está declarado porque el manual diga «demanda historica»."""
    assert canonico("Demanda_Historica.xlsx") == "demanda_historica.xlsx"
    referentes = extraer_referentes("Demanda_Historica.xlsx")
    assert len(referentes) == 1


def test_los_marcadores_no_son_referentes():
    """Un dato marcado como no declarado ya cumple la regla: no se le exige fuente."""
    assert extraer_referentes("[POR CONFIRMAR] el archivo de entrada") == []
    assert extraer_referentes("Trabaje en [RUTA DE TRABAJO POR CONFIRMAR]") == []


def test_las_url_no_son_referentes_de_fichero():
    """Medido sobre el plan real: las colas de URL se colaban como rutas locales.

    ``/support.microsoft.com/es-es/office/pronostico-lineal`` no es una ruta del
    equipo del alumno. Las URL pertenecen a la verificación C1 (que estén vivas),
    no a la trazabilidad contra el temario.
    """
    texto = (
        "Documentación: https://support.microsoft.com/es-es/office/pronostico-lineal "
        "y https://www.microsoft.com/es-mx/download/details.aspx"
    )
    assert extraer_referentes(texto) == []

    plan = {
        "software_requirements": [
            {"name": "Excel", "source": "https://www.microsoft.com/es-mx/download/details.aspx"}
        ]
    }
    assert auditar_plan(plan, _FUENTES)["ok"]


def test_la_puntuacion_de_la_frase_no_forma_parte_del_referente():
    """Medido sobre el plan real: «C:\\Forecasting_Logistica\\.» arrastraba el punto final."""
    referentes = extraer_referentes(r"Directorio de trabajo: C:\Datos\.")
    assert [r["valor"] for r in referentes] == ["C:\\Datos\\"]


# --------------------------------------------------------------------------- #
# A1: integridad referencial del plan
# --------------------------------------------------------------------------- #

def test_a1_detecta_los_referentes_inventados_de_la_evidencia_real():
    plan = {
        "overall_objectives": ["Analizar la demanda historica"],
        "lab_plans": [
            {
                **_LAB_PLAN,
                "scope": "Abrir C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx y calcular el MAPE.",
            }
        ],
        "special_considerations": ["Directorio de trabajo: C:\\Forecasting_Logistica\\"],
    }
    informe = auditar_plan(plan, _FUENTES)
    valores = {v["valor"] for v in informe["violaciones"]}

    assert "C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx" in valores
    assert "C:\\Forecasting_Logistica\\" in valores
    assert not informe["ok"]


def test_a1_no_marca_lo_que_declaran_las_fuentes():
    plan = {
        "lab_plans": [{**_LAB_PLAN, "scope": "Abrir datos_ventas.xlsx y volcar en resultados.md"}],
        "special_considerations": ["Guarde los entregables segun el manual"],
    }
    informe = auditar_plan(plan, _FUENTES)
    assert informe["ok"], informe["violaciones"]
    assert informe["total"] >= 2


def test_a1_indica_el_campo_donde_esta_el_referente():
    plan = {"special_considerations": ["Trabaje en Practica1_MAPE_SKU.xlsx"]}
    informe = auditar_plan(plan, _FUENTES)
    assert informe["violaciones"], "el referente inventado debe detectarse"
    assert informe["violaciones"][0]["campo"] == "special_considerations[0]"


def test_a1_una_ruta_se_declara_por_el_nombre_de_su_fichero():
    """La carpeta puede describirse en prosa; el fichero es lo que identifica la ruta."""
    plan = {"lab_plans": [{**_LAB_PLAN, "scope": "Abra el fichero datos_ventas.xlsx del directorio de trabajo"}]}
    assert auditar_plan(plan, _FUENTES)["ok"]


# --------------------------------------------------------------------------- #
# B1: integridad referencial de un laboratorio
# --------------------------------------------------------------------------- #

_LAB_QUE_CREA = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Analice los datos entregados.

### Paso 1: Crear el libro de trabajo
**Objective:** Preparar el libro de resultados.
**Instructions:**
1. Cree en Excel el archivo resultados.md y guarde una copia.
**Verification:** El libro existe.

### Paso 2: Volcar el analisis
**Instructions:**
1. Escriba el analisis en resultados.md.
"""

_LAB_QUE_USA_SIN_CREAR = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Analice los datos entregados.

### Paso 1: Preparar el analisis
**Objective:** Abrir el conjunto de datos.
**Instructions:**
1. Abra el archivo Demanda_Historica.xlsx y revise las columnas.
**Expected output:** El conjunto de datos abierto.
**Verification:** El archivo se abre sin errores.
"""


def test_b1_el_laboratorio_que_crea_y_luego_usa_no_viola():
    informe = auditar_laboratorio(_LAB_QUE_CREA, _FUENTES, plan="")
    assert informe["ok"], informe["violaciones"]


def test_b1_el_laboratorio_que_usa_sin_crear_viola():
    informe = auditar_laboratorio(_LAB_QUE_USA_SIN_CREAR, _FUENTES, plan="")
    valores = {v["valor"] for v in informe["violaciones"]}
    assert "Demanda_Historica.xlsx" in valores


def test_b1_lo_declarado_en_el_plan_esta_permitido():
    """El plan es una fuente para el Writer: si el plan lo declara, el laboratorio puede usarlo."""
    plan = "Entregable obligatorio: Practica1_MAPE_SKU.xlsx"
    informe = auditar_laboratorio(_LAB_QUE_USA_SIN_CREAR, _FUENTES, plan=plan)
    valores = {v["valor"] for v in informe["violaciones"]}
    assert "Demanda_Historica.xlsx" in valores
    assert "Practica1_MAPE_SKU.xlsx" not in valores


def test_b1_es_determinista():
    primero = auditar_laboratorio(_LAB_QUE_USA_SIN_CREAR, _FUENTES, plan="")
    segundo = auditar_laboratorio(_LAB_QUE_USA_SIN_CREAR, _FUENTES, plan="")
    assert primero == segundo


def test_el_mensaje_de_correccion_cita_los_referentes():
    informe = auditar_laboratorio(_LAB_QUE_USA_SIN_CREAR, _FUENTES, plan="")
    mensaje = mensaje_de_correccion(informe["violaciones"], "lab")
    assert "Demanda_Historica.xlsx" in mensaje
    assert "POR CONFIRMAR" in mensaje
    assert mensaje_de_correccion([], "lab") == ""


def test_las_dos_copias_del_modulo_son_identicas():
    """El módulo se replica en el planner y el writer: debe estar byte a byte idéntico."""
    rutas = [
        os.path.join(_HERE, _CARPETA_PLANNER, "referent_check.py"),
        os.path.join(_HERE, _CARPETA_WRITER, "referent_check.py"),
    ]
    with open(rutas[0], "rb") as f0, open(rutas[1], "rb") as f1:
        assert f0.read() == f1.read(), "las copias de referent_check.py se han desincronizado"


# --------------------------------------------------------------------------- #
# Camino vivo 1: el expansor de lotes debe propagar el contexto
# --------------------------------------------------------------------------- #

def test_el_expansor_de_lotes_propaga_temario_y_manual():
    """Regresión real: el lote de laboratorios no llevaba el temario ni el manual.

    Consecuencia medida: ``LabBatchExpander`` no los recibía, así que el Writer no
    podía contrastar nada contra las fuentes y el manual solo llegaba (recortado y
    mal etiquetado) por el atajo de ``additional_requirements`` del plan.
    """
    modulo = _cargar_modulo("lab_batch_expander", "lambda")
    plan = {"lab_plans": [{"lab_id": "01-01-01", "lab_title": "Lab uno"}]}
    modulo.s3_client = _S3Simulado(
        {"p/labguide/lab-master-plan.json": json.dumps(plan)}
    )
    modulo.list_lesson_files = lambda *a, **k: []

    salida = modulo.lambda_handler(
        {
            "course_bucket": "bucket",
            "master_plan_key": "p/labguide/lab-master-plan.json",
            "project_folder": "p",
            "model_provider": "bedrock",
            "outline_s3_key": "p/outline.yaml",
            "manual_text_s3_key": "p/manual.txt",
        },
        None,
    )

    assert salida["statusCode"] == 200, salida
    lote = salida["batches"][0]
    assert lote["outline_s3_key"] == "p/outline.yaml", "el lote no lleva el temario"
    assert lote["manual_text_s3_key"] == "p/manual.txt", "el lote no lleva el manual"


def test_la_state_machine_pasa_el_contexto_al_expansor_de_lotes():
    with open(os.path.join(_HERE, "current_state_machine.json"), encoding="utf-8") as fh:
        definicion = json.load(fh)

    encontrados = 0
    for nombre, estado in definicion["States"].items():
        parametros = estado.get("Parameters") or {}
        if not str(parametros.get("FunctionName", "")).endswith(":function:LabBatchExpander"):
            continue
        encontrados += 1
        payload = parametros.get("Payload") or {}
        assert "outline_s3_key.$" in payload, f"{nombre} no pasa el temario al expansor"
        assert "manual_text_s3_key.$" in payload, f"{nombre} no pasa el manual al expansor"

    assert encontrados >= 2, "se esperaban dos invocaciones (solo labs y teoría+labs)"


# --------------------------------------------------------------------------- #
# Camino vivo 2: el prompt compacto del Writer
# --------------------------------------------------------------------------- #

def test_el_prompt_vivo_del_writer_incluye_la_correccion():
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)
    correccion = mensaje_de_correccion(
        [{"valor": "Demanda_Historica.xlsx", "tipo": "fichero", "inicio": 0}], "lab"
    )
    contexto = {
        "target_language": "Spanish (Español)",
        "referential_correction": correccion,
    }
    prompt = modulo._compact_single_lab_prompt(_LAB_PLAN, contexto, "", "resumen del lab")
    assert "CORRECCIÓN OBLIGATORIA" in prompt
    assert "Demanda_Historica.xlsx" in prompt


# --------------------------------------------------------------------------- #
# Camino vivo 3: el handler del Writer reintenta y corrige
# --------------------------------------------------------------------------- #

_LAB_CON_INVENTO = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Analice los datos entregados.

### Paso 1: Preparar el analisis
**Objective:** Abrir el conjunto de datos.
**Instructions:**
1. Abra el archivo Demanda_Historica.xlsx y revise las columnas.
**Expected output:** El conjunto de datos abierto.
**Verification:** El archivo se abre sin errores.
"""

_LAB_CORREGIDO = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Analice los datos entregados.

### Paso 1: Preparar el analisis
**Objective:** Abrir el conjunto de datos.
**Instructions:**
1. Abra el archivo datos_ventas.xlsx y revise las columnas.
**Expected output:** El conjunto de datos abierto.
**Verification:** El archivo se abre sin errores.
"""


def _ejecutar_writer(
    plan,
    contenidos,
    max_intentos=1,
    lab_ids=None,
    objetos=None,
    existentes=None,
    almacen=None,
):
    """Ejecuta el handler real del Writer con S3 y el modelo simulados.

    ``contenidos`` es la lista de respuestas del modelo simulado: la primera llamada
    devuelve la primera, la segunda la segunda, y así sucesivamente.
    ``existentes`` mapea ``lab_id`` → clave S3 de un laboratorio ya escrito (B3).
    ``almacen`` permite compartir el mismo S3 entre invocaciones, como ocurre en
    producción, donde cada lote del Writer es una invocación distinta.
    """
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)

    base = {"p/outline.yaml": _TEMARIO, "p/manual.txt": _MANUAL, **(objetos or {})}
    if almacen is None:
        s3 = _S3Simulado(base)
    else:
        almacen.objetos.update(base)
        s3 = almacen
    modulo.s3_client = s3
    modulo.MAX_LAB_GENERATION_ATTEMPTS = max_intentos
    contextos = []

    def _generador_falso(lab_plans, master_context, model_provider="bedrock",
                         lesson_content="", previous_lab_context=""):
        contextos.append(dict(master_context))
        indice = min(len(contextos), len(contenidos)) - 1
        return {lab_plans[0]["lab_id"]: contenidos[indice]}

    modulo.generate_all_labs_batch = _generador_falso
    modulo._verify_and_refine_lab_guide = lambda guide, plan_, ctx, model_provider="bedrock": guide
    modulo._finalize_lab_markdown = lambda markdown, is_demo, is_spanish=True: markdown
    modulo.load_master_plan_from_s3 = lambda bucket, key: plan
    modulo.save_lab_guide_to_s3 = lambda **kw: f"p/labguide/lab-{kw['lab_id']}.md"
    modulo._lab_skip_if_exists_enabled = lambda: False
    modulo._find_existing_lab_guide_key = lambda bucket, project, lab_id: (
        (existentes or {}).get(lab_id)
    )

    resultado = modulo.lambda_handler(
        {
            "course_bucket": "bucket",
            "master_plan_key": "p/labguide/lab-master-plan.json",
            "project_folder": "p",
            "outline_s3_key": "p/outline.yaml",
            "manual_text_s3_key": "p/manual.txt",
            "lab_ids": lab_ids or ["01-01-01"],
            "lab_lesson_keys": {},
        },
        None,
    )
    informes = [
        json.loads(p["Body"])
        for p in s3.puts
        if p["Key"].endswith("labs-referential-integrity.json")
    ]
    return resultado, informes, contextos


def test_el_writer_reintenta_y_corrige_referentes_inventados():
    """Camino vivo: el handler genera, detecta un referente inventado, reintenta
    con la lista de corrección y acepta el segundo intento."""
    plan = {"lab_plans": [_LAB_PLAN]}
    resultado, informes, contextos = _ejecutar_writer(
        plan,
        [_LAB_CON_INVENTO, _LAB_CORREGIDO],
        max_intentos=3,
    )

    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 2, "el Writer debió reintentar tras detectar el referente inventado"
    assert not contextos[0].get("referential_correction"), (
        "el primer intento no debe llevar corrección"
    )
    correccion = contextos[1].get("referential_correction") or ""
    assert "Demanda_Historica.xlsx" in correccion, (
        "el reintento debe citar el referente inventado que hay que eliminar"
    )
    assert informes, "no se escribió el informe B1"
    assert informes[0]["ok"] is True, informes[0]


def test_el_informe_referencial_conserva_todos_los_laboratorios_del_curso():
    """Camino vivo: dos invocaciones del Writer (una por lote, como en producción)
    deben dejar un único artefacto con los dos laboratorios.

    Antes, cada invocación sobrescribía ``validation/labs-referential-integrity.json``
    y un curso de dos laboratorios conservaba un solo informe: se perdía justo la
    evidencia con la que se decide cuándo encender los interruptores como ERROR.
    """
    almacen = _S3Simulado({})

    _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]},
        [_LAB_CORREGIDO],
        almacen=almacen,
        lab_ids=["01-01-01"],
    )
    _ejecutar_writer(
        {"lab_plans": [{**_LAB_PLAN, "lab_id": "02-00-01",
                        "lab_title": "Comparar los resultados"}]},
        [_LAB_CORREGIDO],
        almacen=almacen,
        lab_ids=["02-00-01"],
    )

    clave = "p/validation/labs-referential-integrity.json"
    assert clave in almacen.objetos, sorted(almacen.objetos)
    informe = json.loads(almacen.objetos[clave])
    assert informe["labs"] == 2, informe
    assert sorted(informe["por_laboratorio"]) == ["01-01-01", "02-00-01"], informe


_LAB_QUE_USA_LA_CARPETA_INVENTADA = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Localice los datos de partida.

### Paso 1: Preparar el analisis
**Objective:** Localizar el conjunto de datos.
**Instructions:**
1. Abra el explorador de archivos en C:\\Forecasting_Logistica\\ y localice los datos.
"""

_LAB_QUE_CALCULA_EL_ENTREGABLE = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Elabore el informe de resultados.

### Paso 1: Analizar la serie
**Objective:** Obtener el error del pronostico.
**Instructions:**
1. Abra el libro Practica1_MAPE_SKU.xlsx y revise la hoja de calculos.
"""


def test_b1_no_acepta_como_fuente_un_referente_que_a1_declaro_inventado():
    """Composición de las dos capas: A1 marca el referente inventado en el plan y B1
    no lo acepta después como fuente. Sin esto, el laboratorio podría repetir el dato
    inventado del plan y B1 lo daría por declarado."""
    plan = {
        "lab_plans": [_LAB_PLAN],
        "special_considerations": ["Directorio de trabajo: C:\\Forecasting_Logistica\\"],
        "metadata": {
            "referential_integrity": {
                "check": "A1",
                "total_referentes": 1,
                "violaciones": [
                    {"campo": "special_considerations[0]", "valor": "C:\\Forecasting_Logistica\\"}
                ],
                "ok": False,
            }
        },
    }
    resultado, informes, _ = _ejecutar_writer(
        plan, [_LAB_QUE_USA_LA_CARPETA_INVENTADA], max_intentos=1
    )

    assert resultado["statusCode"] == 200, resultado
    assert informes, "no se escribió el informe B1"
    violaciones = [
        v["valor"]
        for informe in informes
        for r in informe["por_laboratorio"].values()
        for v in r["violaciones"]
    ]
    assert any("Forecasting_Logistica" in v for v in violaciones), (
        f"B1 aceptó como declarada una carpeta que A1 marcó como inventada: {violaciones}"
    )


def test_b1_si_acepta_lo_que_el_plan_declara_y_a1_no_marco():
    plan = {
        "lab_plans": [_LAB_PLAN],
        "special_considerations": ["Entregable obligatorio: Practica1_MAPE_SKU.xlsx"],
        "metadata": {"referential_integrity": {"check": "A1", "violaciones": [], "ok": True}},
    }
    resultado, informes, _ = _ejecutar_writer(
        plan, [_LAB_QUE_CALCULA_EL_ENTREGABLE], max_intentos=1
    )

    assert resultado["statusCode"] == 200, resultado
    assert informes[0]["ok"] is True, informes[0]


# --------------------------------------------------------------------------- #
# Camino vivo 4: A1 con reintento correctivo en el planner
# --------------------------------------------------------------------------- #

def test_el_planner_conserva_el_plan_con_menos_referentes_sin_declarar():
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)

    plan_malo = {
        "lab_plans": [{**_LAB_PLAN, "scope": "Abrir C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx"}],
        "special_considerations": ["Directorio de trabajo: C:\\Forecasting_Logistica\\"],
    }
    plan_bueno = {
        "lab_plans": [{**_LAB_PLAN, "scope": "Abrir datos_ventas.xlsx y volcar en resultados.md"}],
        "special_considerations": [],
    }

    correcciones = []

    def _regenerar(correccion):
        correcciones.append(correccion)
        return plan_bueno

    plan, informe = modulo.auditar_y_corregir_plan(plan_malo, _FUENTES, _regenerar)

    assert correcciones, "no se pidió el reintento correctivo"
    assert "Demanda_Historica.xlsx" in correcciones[0]
    assert informe["ok"], informe["violaciones"]
    assert plan is plan_bueno


def test_el_planner_no_sustituye_el_plan_si_el_reintento_empeora():
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)

    plan_malo = {"lab_plans": [{**_LAB_PLAN, "scope": "Abrir Demanda_Historica.xlsx"}]}
    plan_peor = {"lab_plans": [{**_LAB_PLAN, "scope": "Abrir Demanda_Historica.xlsx y Practica1_MAPE_SKU.xlsx"}]}

    plan, informe = modulo.auditar_y_corregir_plan(
        plan_malo, _FUENTES, lambda correccion: plan_peor
    )

    assert plan is plan_malo, "un reintento que empeora no debe sustituir al plan anterior"
    assert not informe["ok"]


# --------------------------------------------------------------------------- #
# Calibración 16/10/2026: las cinco correcciones del extractor
#
# Cada corrección se prueba sobre el módulo que corre en producción
# (``extraer_referentes`` / ``auditar_laboratorio``), no sobre su fuente. Los
# controles aseguran que la corrección no se lleva por delante un referente real.
# --------------------------------------------------------------------------- #

def test_c1_la_extension_se_ancla_a_fin_de_palabra():
    """``df.shape`` ya no produce el «fichero» ``df.sh``; ``pyplot`` no produce ``.py``."""
    for codigo in (
        "df.shape[0]",
        "matplotlib.pyplot",
        "kpis.show(truncate=False)",
        "X_val_prep.shape",
        "hashlib.md5('x')",
        "Object.keys(x)",
        "robot.language-server.python",
    ):
        assert extraer_referentes(codigo) == [], f"{codigo!r} no debe producir referente"

    # Control: un fichero real, incluso al final de la frase, se sigue extrayendo.
    assert [r["valor"] for r in extraer_referentes("Guarde Practica1_MAPE_SKU.xlsx.")] == [
        "Practica1_MAPE_SKU.xlsx"
    ]


def test_c2_los_identificadores_y_claves_de_configuracion_no_son_ficheros():
    for codigo in (
        "math.log(2)",
        "pyspark.sql",
        "transaction.state.log.replication.factor",
        "parse.key=true",
        "android.util.Log",
        "json.JSON",
        "console.log('x')",
    ):
        assert extraer_referentes(codigo) == [], f"{codigo!r} no debe producir referente"

    # Control: nombres de fichero reales con un único punto se conservan.
    for fichero in ("response.json", "data1.csv", "informe_final.xlsx"):
        valores = [r["valor"] for r in extraer_referentes(fichero)]
        assert valores == [fichero], f"{fichero!r} debe seguir siendo un referente"


def test_c3_las_rutas_de_sistema_y_de_api_no_son_material_del_curso():
    for ruta in (
        "/etc/hosts",
        "/dev/null",
        "/usr/share/nginx/html",
        "C:\\Users\\",
        "/subscriptions/xxxx/resourceGroups/rg-lab-contenedores",
        "/_cat/count",
        "/components/schemas/ErrorResponse",
    ):
        assert extraer_referentes(ruta) == [], f"{ruta!r} no debe producir referente"

    # Control: la ruta inventada de la evidencia real sigue detectándose.
    ruta_real = "C:\\Forecasting_Logistica\\Datos\\Demanda_Historica.xlsx"
    assert [r["valor"] for r in extraer_referentes(ruta_real)] == [ruta_real]


_LAB_TEE = """# Lab
### Paso 1: Listar los nodos
```bash
kubectl get nodes -o wide | tee ~/k8s-intro/analisis/nodos-wide.txt
```
"""

_LAB_BACKUP = """# Lab
### Paso 1: Respaldo completo
```sql
BACKUP DATABASE Sql2025Lab
TO DISK = N'C:\\SQLLab2025\\Backups\\Sql2025Lab_TDE_FULL.bak'
```
"""

_LAB_OUT_FILE = """# Lab
### Paso 1: Exportar la muestra
```powershell
Invoke-Sqlcmd -Query "SELECT 1" | Out-File -Encoding utf8 "C:\\DAF\\Batch_01\\02_quality\\02_muestra_ids_repetidos.txt"
```
"""


def test_c4_la_creacion_por_tee_redireccion_backup_y_out_file_exime():
    """Medido en el corpus: el laboratorio crea el fichero y aun así se marcaba."""
    for lab in (_LAB_TEE, _LAB_BACKUP, _LAB_OUT_FILE):
        informe = auditar_laboratorio(lab, "", plan="")
        assert informe["ok"], informe["violaciones"]


def test_c4_control_sin_creacion_el_fichero_sigue_marcandose():
    lab = "### Paso 1: Abrir\nAbra el archivo C:\\DAF\\Batch_01\\02_quality\\02_muestra_ids_repetidos.txt"
    informe = auditar_laboratorio(lab, "", plan="")
    assert not informe["ok"]


_LAB_ABSURDO = """# Lab
### Paso 4: Archivo que no existe
```
ERROR | Archivo no encontrado: data/archivo_inexistente.json
```
"""

_LAB_SIN_CONFIG = """# Lab
### Paso 3: Configurar Tailwind
Implementar Tailwind CSS v4 sin archivo tailwind.config.js clasico.
"""


def test_c5_la_mencion_de_ausencia_exime():
    for lab in (_LAB_ABSURDO, _LAB_SIN_CONFIG):
        informe = auditar_laboratorio(lab, "", plan="")
        assert informe["ok"], informe["violaciones"]


def test_c5_control_sin_ausencia_el_fichero_sigue_marcandose():
    lab = "### Paso 1: Editar\nEdite el archivo tailwind.config.js con la configuracion del curso."
    informe = auditar_laboratorio(lab, "", plan="")
    assert not informe["ok"]


_LAB_REDIRECCION = """# Lab
### Paso 1: Crear el script de validación
```bash
cat > ~/lab-01-00-01/validate.sh << 'EOF'
#!/bin/bash
echo ok
EOF
```
### Paso 2: Ejecutar
```bash
bash ~/lab-01-00-01/validate.sh
```
"""

_LAB_ECHO_REDIRECCION = """# Lab
### Paso 1: Guardar la evidencia
```bash
kubectl get pods -A > ~/evidencias/lab-06/pods.txt
```
"""

_LAB_OPCIONES = """# Lab
### Paso 1: Ejecutar las pruebas
```bash
pytest --log log_final.html --report reporte_final.html
```
### Paso 2: Exportar la tubería
```powershell
python pipeline.py --output output_pipeline.xml
```
"""

_LAB_DESTINATION = """# Lab
### Paso 1: Instalar los plugins
```powershell
Expand-Archive -Path plugins.zip -DestinationPath "C:\\kubectl-plugins\\"
```
"""


def test_c4b_la_redireccion_y_las_opciones_eximen():
    """Medido en la muestra: ``cat >``, ``> ~/…``, ``--log``, ``--output`` y
    ``-DestinationPath`` crean el fichero, pero se marcaba como no declarado."""
    for lab, fuentes in (
        (_LAB_REDIRECCION, ""),
        (_LAB_ECHO_REDIRECCION, ""),
        (_LAB_OPCIONES, ""),
        (_LAB_DESTINATION, "plugins.zip"),
    ):
        informe = auditar_laboratorio(lab, fuentes, plan="")
        assert informe["ok"], informe["violaciones"]


_LAB_MENCION_PREVIA = """# Lab
### Paso 1: Entregables
El entregable final es `resultado_final.json`.
### Paso 2: Generar el resultado
```bash
cat > resultado_final.json << 'EOF'
{"ok": true}
EOF
```
"""

_LAB_MENCION_PREVIA_SIN_CREAR = """# Lab
### Paso 1: Entregables
El entregable final es `resultado_final.json`.
### Paso 2: Publicar
Publique el contenido de resultado_final.json en el portal del curso.
"""


def test_c4c_la_creacion_posterior_exime_la_mencion_previa():
    """Un fichero puede nombrarse antes (tabla, árbol de directorios) y crearse
    después. Se recorren todas las apariciones, no solo la primera."""
    informe = auditar_laboratorio(_LAB_MENCION_PREVIA, "", plan="")
    assert informe["ok"], informe["violaciones"]


def test_c4c_control_sin_creacion_la_mencion_previa_sigue_marcandose():
    informe = auditar_laboratorio(_LAB_MENCION_PREVIA_SIN_CREAR, "", plan="")
    assert not informe["ok"]


_LAB_ARBOL = """# Lab
### Paso 1: Entregables
```text
data/
├── duplicated_code.py
├── hardcoded_secret.py
└── sql_injection.py
```
"""

_LAB_IMPORT = """# Lab
### Paso 1: Rutas
```js
import ReportsView from '@/views/ReportsView.vue'
```
"""

_LAB_CLAVE_YAML = """# Lab
### Paso 1: Configurar TLS
```yaml
xpack.security.http.ssl.key: certs/es01.key
dashboardproviders.yaml:
  apiVersion: 1
```
"""

_LAB_ANDAMIAJE = """# Lab
### Paso 1: Generar el componente
```bash
ng generate component components/task-list
```
### Paso 2: Verificar
```bash
cat src/app/components/task-list/task-list.component.ts
```
"""

_LAB_CITA = """# Lab
### Paso 1: Analizar
[Fuente 1: Reporte_Sectorial_Enero_2024.pdf - Editor: McKinsey & Co]
"""

_LAB_TO_CSV = """# Lab
### Paso 1: Exportar los errores
```python
errores_test.to_csv(RUTA_REPORTES / "errores_clasificacion_test.csv", index=False)
```
"""

_LAB_BORRAR = """# Lab
### Paso 1: Limpieza
Elimine los archivos de prueba restantes, por ejemplo `zz_quality_warn.csv`.
"""


def test_c6_las_reglas_estructurales_no_marcan_ficheros_del_proyecto():
    """Árboles de entregables, imports, claves YAML, andamiaje, citas, salidas
    ``to_csv`` y ficheros que se piden borrar: ninguno es una entrada inventada."""
    for lab in (
        _LAB_ARBOL,
        _LAB_IMPORT,
        _LAB_CLAVE_YAML,
        _LAB_ANDAMIAJE,
        _LAB_CITA,
        _LAB_TO_CSV,
        _LAB_BORRAR,
    ):
        informe = auditar_laboratorio(lab, "", plan="")
        assert informe["ok"], (lab[:40], informe["violaciones"])


def test_c6_las_claves_yaml_y_las_secuencias_de_escape_no_se_extraen():
    for texto in (
        "xpack.security.http.ssl.key: certs/es01.key",
        "dashboardproviders.yaml:",
        "'Untagged\\\\nSpend', 'Budget\\\\nVariance'",
    ):
        assert extraer_referentes(texto) == [], texto


def test_c6_control_una_entrada_citada_sin_contexto_sigue_marcandose():
    lab = "### Paso 1: Abrir\nAbra el archivo datos_inventados_2024.xlsx"
    informe = auditar_laboratorio(lab, "", plan="")
    assert not informe["ok"]


_LAB_PYTHON_REAL = """# Lab
### Paso 1: Cargar y graficar
```python
import matplotlib.pyplot as plt
import math
df = pd.read_csv("ventas.csv")
print(df.shape[0])
print(math.log(2))
plt.show()
```
"""


def test_integracion_un_laboratorio_de_python_no_produce_falsos_positivos():
    """El caso que dominaba el corpus: código Python con ``shape``, ``pyplot`` y
    ``math.log``. Con el fichero de datos declarado, no debe quedar violación."""
    informe = auditar_laboratorio(_LAB_PYTHON_REAL, "ventas.csv", plan="")
    assert informe["ok"], informe["violaciones"]


_LAB_ENTREGABLE_NO_APORTADO = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Revise el informe de resultados.

### Paso 1: Revisar el informe
**Objective:** Revisar los resultados.
**Instructions:**
1. El informe Datos_Inventados.xlsx contiene los resultados del analisis.
"""


def test_la_confianza_alta_aisla_los_ficheros_que_aporta_el_curso():
    plan = {
        "lab_plans": [
            {
                **_LAB_PLAN,
                "scope": "Archivos proporcionados por el instructor: Datos_Inventados.xlsx.",
            }
        ]
    }
    informe = auditar_plan(plan, _FUENTES)
    assert informe["violaciones"]
    assert informe["violaciones"][0]["confianza"] == "alta"


def test_la_confianza_alta_reconoce_onedrive_sharepoint_y_descargas():
    for texto in (
        "Documentos de laboratorio cargados en OneDrive for Business: LAB05_Datos.xlsx",
        "Archivos de práctica proporcionados por el instructor: M4_Datos.xlsx",
        "Verifica que tienes los siguientes archivos descargados desde SharePoint: caso.pdf",
    ):
        informe = auditar_laboratorio(f"### Paso 1: Preparar\n{texto}", "")
        assert informe["violaciones"], texto
        assert informe["violaciones"][0]["confianza"] == "alta", texto


def test_la_confianza_baja_marca_los_entregables_que_crea_el_laboratorio():
    plan = {
        "lab_plans": [
            {**_LAB_PLAN, "scope": "El informe Datos_Inventados.xlsx contiene los resultados."}
        ]
    }
    informe = auditar_plan(plan, _FUENTES)
    assert informe["violaciones"]
    assert informe["violaciones"][0]["confianza"] == "baja"


def test_el_planner_no_reintenta_si_solo_hay_referentes_de_baja_confianza():
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)
    plan = {
        "lab_plans": [
            {**_LAB_PLAN, "scope": "El informe Datos_Inventados.xlsx contiene los resultados."}
        ]
    }
    llamadas = []
    plan_final, informe = modulo.auditar_y_corregir_plan(
        plan, _FUENTES, lambda correccion: llamadas.append(correccion) or plan
    )

    assert llamadas == [], "un entregable de baja confianza no debe provocar reintento"
    assert informe["violaciones"], "la violación debe quedar registrada"
    assert plan_final is plan


def test_el_writer_no_reintenta_si_solo_hay_referentes_de_baja_confianza():
    plan = {"lab_plans": [_LAB_PLAN]}
    resultado, informes, contextos = _ejecutar_writer(
        plan, [_LAB_ENTREGABLE_NO_APORTADO], max_intentos=3
    )

    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "no debe reintentar sobre un entregable de baja confianza"
    assert informes and informes[0]["ok"] is False, informes[0]
    assert any(
        v.get("confianza") == "baja"
        for r in informes[0]["por_laboratorio"].values()
        for v in r["violaciones"]
    )


def test_la_edicion_de_un_fichero_del_proyecto_baja_la_confianza():
    """«Abra `vite.config.js` y reemplace su contenido»: es un fichero del proyecto
    (lo crea el andamiaje), no una entrada que aporte el curso."""
    lab = (
        "### Paso 1: Configurar Vite\n"
        "Abra el archivo de configuración de Vite `vite.config.js` en la raíz del proyecto. "
        "Reemplace su contenido para importar el plugin de Tailwind.\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["violaciones"], "debe seguir registrándose"
    assert informe["violaciones"][0]["confianza"] == "baja"


def test_una_marca_de_entrada_gana_al_verbo_de_edicion():
    lab = (
        "### Paso 1: Preparar\n"
        "Abra el archivo `datos_curso.xlsx` proporcionado por el instructor y reemplace los valores.\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["violaciones"][0]["confianza"] == "alta"


_LAB_BLOQUE_SALIDA = """# Lab
### Paso 1: Crear la tabla
```python
spark.sql("CREATE TABLE ecommerce.productos (id INT)")
```
**Salida esperada:**
```
Archivos en _delta_log:
  - 00000000000000000000.json (1234 bytes)
  - 00000000000000000001.json (987 bytes)
```
### Paso 2: Compilar
```bash
ng serve --open
```
Verás una salida similar a:
```
Initial chunk files | Names
main.js             | main
polyfills.js        | polyfills
```
"""

_LAB_MARCADOR_MAYUSCULAS = """# Lab
### Paso 1: Instrucciones
Debes referenciar los documentos fuente que están en mi OneDrive:
- Estructura del proceso actual: [PEGAR_AQUÍ_URL_DE_PROCESO_ACTUAL.MD]
- Cuellos de botella: [PEGAR_AQUÍ_URL_DE_ANALISIS_PROCESO.MD]
"""


def test_c7_los_bloques_de_salida_esperada_no_son_entradas():
    """Los listados rotulados «Salida esperada» o «Verás una salida similar a»
    muestran lo que produce el laboratorio; no exigen un fichero aportado."""
    informe = auditar_laboratorio(_LAB_BLOQUE_SALIDA, "", plan="")
    assert informe["ok"], informe["violaciones"]


def test_c7_los_marcadores_en_mayusculas_con_punto_no_se_extraen():
    informe = auditar_laboratorio(_LAB_MARCADOR_MAYUSCULAS, "", plan="")
    assert informe["ok"], informe["violaciones"]


def test_un_expected_outcome_nunca_dispara_reintento():
    """``expected_outcomes`` describe lo que el estudiante produce: es salida por
    definición, aunque el texto diga «recibe» o «proporcionado»."""
    plan = {
        "lab_plans": [
            {
                **_LAB_PLAN,
                "expected_outcomes": [
                    "Script main.py que importa y ejecuta funcionalidad de múltiples módulos"
                ],
            }
        ]
    }
    informe = auditar_plan(plan, _FUENTES)
    del_entregable = [v for v in informe["violaciones"] if v["valor"] == "main.py"]
    assert del_entregable, "debe registrarse"
    assert del_entregable[0]["confianza"] == "baja"


def test_el_reintento_se_puede_desactivar_sin_cambiar_el_plan():
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)
    plan = {"lab_plans": [{**_LAB_PLAN, "scope": "Abrir Demanda_Historica.xlsx"}]}
    llamadas = []
    anterior = os.environ.get("REFERENTIAL_RETRY")
    os.environ["REFERENTIAL_RETRY"] = "0"
    try:
        plan_final, informe = modulo.auditar_y_corregir_plan(
            plan, _FUENTES, lambda correccion: llamadas.append(correccion) or plan
        )
    finally:
        if anterior is None:
            os.environ.pop("REFERENTIAL_RETRY", None)
        else:
            os.environ["REFERENTIAL_RETRY"] = anterior

    assert llamadas == [], "REFERENTIAL_RETRY=0 debe dejar solo registro"
    assert plan_final is plan
    assert informe["violaciones"], "el informe se sigue generando"


def test_el_writer_con_reintento_desactivado_no_regenera_el_lab():
    plan = {"lab_plans": [_LAB_PLAN]}
    anterior = os.environ.get("REFERENTIAL_RETRY")
    os.environ["REFERENTIAL_RETRY"] = "0"
    try:
        resultado, informes, contextos = _ejecutar_writer(
            plan, [_LAB_CON_INVENTO], max_intentos=3
        )
    finally:
        if anterior is None:
            os.environ.pop("REFERENTIAL_RETRY", None)
        else:
            os.environ["REFERENTIAL_RETRY"] = anterior

    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "REFERENTIAL_RETRY=0 no debe regenerar el laboratorio"
    assert informes and informes[0]["ok"] is False


# --------------------------------------------------------------------------- #
# Fase 2: B3 (creado en un laboratorio anterior) y B2 (salida de uno posterior)
# --------------------------------------------------------------------------- #

_LAB_QUE_CREA_LA_ENTRADA = """# Lab 01-01-01: Preparar el conjunto de datos

### Paso 1: Crear el conjunto limpio
cat > C:\\Curso\\ventas_limpias.csv
"""

_LAB_QUE_ABRE_LO_DEL_LAB_ANTERIOR = """# Lab 01-01-02: Analizar la demanda

### Paso 1: Abrir el conjunto de datos
Abra el archivo ventas_limpias.csv y calcule el MAPE del pronostico.

### Paso 2: Guardar el entregable
cat > Practica1_MAPE_SKU.xlsx
"""

_LAB_QUE_USA_LA_SALIDA_POSTERIOR = """# Lab 01-01-01: Preparar el analisis

### Paso 1: Revisar el entregable
Abra el libro Practica1_MAPE_SKU.xlsx y revise los calculos por SKU.
"""

_PLAN_DOS_LABS = {
    "lab_plans": [
        {**_LAB_PLAN, "expected_outcomes": []},
        {
            **_LAB_PLAN,
            "lab_id": "01-01-02",
            "lab_title": "Calcular el MAPE",
            "expected_outcomes": ["Practica1_MAPE_SKU.xlsx"],
        },
    ]
}


def test_b3_lo_creado_en_un_laboratorio_anterior_es_legitimo():
    creados = referentes_creados(_LAB_QUE_CREA_LA_ENTRADA)
    informe = auditar_laboratorio(
        _LAB_QUE_ABRE_LO_DEL_LAB_ANTERIOR, fuentes=_FUENTES, creados_antes=creados
    )
    assert informe["ok"] is True, informe["violaciones"]
    assert informe["violaciones"] == []


def test_b3_control_sin_el_laboratorio_anterior_el_fichero_sigue_marcandose():
    informe = auditar_laboratorio(_LAB_QUE_ABRE_LO_DEL_LAB_ANTERIOR, fuentes=_FUENTES)
    valores = [v["valor"] for v in informe["violaciones"]]
    assert "ventas_limpias.csv" in valores, informe["violaciones"]
    alta = [v for v in informe["violaciones"] if v["valor"] == "ventas_limpias.csv"][0]
    assert alta["confianza"] == "alta"
    assert alta["verificacion"] == "B1"


def test_b3_una_mencion_sin_creacion_no_legitima():
    """El laboratorio anterior solo *abre* el fichero: no lo crea, así que no puede
    servir de coartada para el siguiente."""
    solo_menciona = (
        "# Lab 01-01-01: Preparar\n\n### Paso 1: Abrir\n"
        "Abra el archivo ventas_limpias.csv y revise las columnas.\n"
    )
    assert referentes_creados(solo_menciona) == set()
    informe = auditar_laboratorio(
        _LAB_QUE_ABRE_LO_DEL_LAB_ANTERIOR,
        fuentes=_FUENTES,
        creados_antes=referentes_creados(solo_menciona),
    )
    assert informe["ok"] is False, "una mención no es una creación"


def test_salidas_de_laboratorios_usa_los_expected_outcomes():
    salidas = salidas_de_laboratorios(_PLAN_DOS_LABS)
    assert salidas["01-01-01"] == []
    assert salidas["01-01-02"] == ["Practica1_MAPE_SKU.xlsx"]


def test_b2_usar_una_salida_del_laboratorio_posterior_es_violacion():
    informe = auditar_laboratorio(
        _LAB_QUE_USA_LA_SALIDA_POSTERIOR,
        fuentes=_FUENTES,
        salidas_posteriores={"01-01-02": ["Practica1_MAPE_SKU.xlsx"]},
    )
    assert len(informe["violaciones"]) == 1, informe["violaciones"]
    violacion = informe["violaciones"][0]
    assert violacion["valor"] == "Practica1_MAPE_SKU.xlsx"
    assert violacion["verificacion"] == "B2"
    assert violacion["laboratorio_posterior"] == "01-01-02"
    assert violacion["confianza"] == "alta"


def test_b2_el_plan_no_blanquea_una_salida_posterior():
    """El plan contiene el ``expected_outcome`` del laboratorio posterior. Si el plan
    se usara como fuente antes de comprobar B2, la dependencia hacia delante quedaría
    invisible: es justo el fallo que esta prueba fija."""
    informe = auditar_laboratorio(
        _LAB_QUE_USA_LA_SALIDA_POSTERIOR,
        fuentes=_FUENTES,
        plan="Entregable del laboratorio 2: Practica1_MAPE_SKU.xlsx",
        salidas_posteriores={"01-01-02": ["Practica1_MAPE_SKU.xlsx"]},
    )
    assert [v["verificacion"] for v in informe["violaciones"]] == ["B2"]


def test_b2_control_si_esta_en_el_temario_no_es_dependencia():
    informe = auditar_laboratorio(
        _LAB_QUE_USA_LA_SALIDA_POSTERIOR,
        fuentes=_FUENTES + "\nEl instructor entrega Practica1_MAPE_SKU.xlsx",
        salidas_posteriores={"01-01-02": ["Practica1_MAPE_SKU.xlsx"]},
    )
    assert informe["ok"] is True, informe["violaciones"]


def test_b2_control_si_lo_crea_este_laboratorio_no_es_dependencia():
    lo_crea = (
        "# Lab 01-01-01: Preparar\n\n### Paso 1: Generar el entregable\n"
        "cat > Practica1_MAPE_SKU.xlsx\n"
    )
    informe = auditar_laboratorio(
        lo_crea,
        fuentes=_FUENTES,
        salidas_posteriores={"01-01-02": ["Practica1_MAPE_SKU.xlsx"]},
    )
    assert informe["ok"] is True, informe["violaciones"]


def test_b2_una_mencion_de_hoja_de_ruta_se_registra_pero_no_es_violacion():
    texto = (
        "# Lab 01-01-01: Preparar\n\n### Paso 1: Resumen\n"
        "Como veras en el laboratorio 2, aplicaras el modelo.\n"
    )
    referencias = referencias_a_labs_posteriores(
        texto, 0, ["01-01-01", "01-01-02", "01-01-03"]
    )
    assert referencias and referencias[0]["laboratorio_posterior"] == "01-01-02"
    informe = auditar_laboratorio(
        texto, fuentes=_FUENTES, referencias_posteriores=referencias
    )
    assert informe["ok"] is True, "una hoja de ruta no es una dependencia"
    assert informe["violaciones"] == []
    assert [m["laboratorio_posterior"] for m in informe["menciones_posteriores"]] == [
        "01-01-02"
    ]


def test_b2_control_un_laboratorio_anterior_o_el_propio_no_es_posterior():
    assert referencias_a_labs_posteriores(
        "En el laboratorio 1 y en el laboratorio 2.", 1, ["a", "b", "c"]
    ) == []
    # Un identificador de laboratorio no es una referencia cruzada.
    assert referencias_a_labs_posteriores(
        "Configura el lab-03-01 ahora.", 0, ["a", "b", "c"]
    ) == []
    # Un módulo no se corresponde con la posición de un laboratorio.
    assert referencias_a_labs_posteriores(
        "En el modulo 5 y en el capitulo 3.", 0, ["a", "b", "c"]
    ) == []


def test_el_writer_acepta_un_fichero_creado_en_el_laboratorio_anterior():
    """Camino vivo de B3: el lote escribe el lab 2 y lee del S3 el lab 1 ya generado."""
    resultado, informes, contextos = _ejecutar_writer(
        _PLAN_DOS_LABS,
        [_LAB_QUE_ABRE_LO_DEL_LAB_ANTERIOR],
        max_intentos=3,
        lab_ids=["01-01-02"],
        objetos={
            "p/labguide/lab-01-01-01-preparar.md": _LAB_QUE_CREA_LA_ENTRADA,
        },
        existentes={"01-01-01": "p/labguide/lab-01-01-01-preparar.md"},
    )

    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "B3 debe evitar el reintento: el fichero lo creó el lab 1"
    assert informes and informes[0]["ok"] is True, informes


def test_el_writer_reintenta_si_depende_de_la_salida_del_laboratorio_posterior():
    """Camino vivo de B2: el lab 1 usa un entregable que solo declara el lab 2."""
    resultado, informes, contextos = _ejecutar_writer(
        _PLAN_DOS_LABS,
        [_LAB_QUE_USA_LA_SALIDA_POSTERIOR, _LAB_CORREGIDO],
        max_intentos=3,
        lab_ids=["01-01-01"],
    )

    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 2, "debe reintentar por dependencia hacia delante"
    correccion = contextos[1].get("referential_correction") or ""
    assert "POSTERIOR" in correccion
    assert "Practica1_MAPE_SKU.xlsx" in correccion
    assert informes and informes[0]["ok"] is True, informes
    assert informes[0]["total_b2"] == 0


def test_el_writer_registra_b2_sin_reintentar_si_el_interruptor_esta_apagado():
    anterior = os.environ.get("REFERENTIAL_RETRY")
    os.environ["REFERENTIAL_RETRY"] = "0"
    try:
        resultado, informes, contextos = _ejecutar_writer(
            _PLAN_DOS_LABS,
            [_LAB_QUE_USA_LA_SALIDA_POSTERIOR],
            max_intentos=3,
            lab_ids=["01-01-01"],
        )
    finally:
        if anterior is None:
            os.environ.pop("REFERENTIAL_RETRY", None)
        else:
            os.environ["REFERENTIAL_RETRY"] = anterior

    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "REFERENTIAL_RETRY=0 no debe regenerar"
    assert informes and informes[0]["total_b2"] == 1, informes


# --------------------------------------------------------------------------- #
# Artefactos de herramientas y rutas relativas con directorio
# --------------------------------------------------------------------------- #

def test_la_ruta_relativa_con_directorio_se_extrae():
    texto = "Crea el fichero en src/main/resources/data/empleados.csv"
    valores = [r["valor"] for r in extraer_referentes(texto)]
    assert "src/main/resources/data/empleados.csv" in valores


def test_la_ruta_relativa_permite_ver_el_paso_que_crea():
    """El fallo real: `cat > assets/mock.json` no se extraía, así que la mención
    posterior parecía un fichero inventado. Ahora la creación se ve."""
    lab = """# Lab
### Paso 1: Crear el mock
```bash
cat > assets/mock.json << 'EOF'
[{"id": 1}]
EOF
```

### Paso 2: Consumirlo
La aplicacion hace fetch de assets/mock.json al arrancar.
"""
    informe = auditar_laboratorio(lab, fuentes="temario base")
    assert informe["ok"] is True, informe["violaciones"]


def test_la_ruta_relativa_sin_creacion_sigue_marcandose():
    lab = """# Lab
### Paso 1: Consumirlo
La aplicacion hace fetch de assets/mock.json al arrancar.
"""
    informe = auditar_laboratorio(lab, fuentes="temario base")
    valores = [v["valor"] for v in informe["violaciones"]]
    assert "assets/mock.json" in valores, informe["violaciones"]


def test_los_artefactos_de_build_no_son_referentes():
    for texto in (
        "El bundle queda en dist/app.js",
        "Los nombres incluyen un hash (ej. main-a1b2c3d4.js)",
        "styles-1a2b3c4d.css cambia en cada build",
        "El chart define values.yaml y Chart.yaml",
        "Incluye plotly.js embebido",
        "Requisito: Node.js 20 o superior",
    ):
        assert extraer_referentes(texto) == [], texto


def test_los_sufijos_generados_no_son_referentes():
    for texto in (
        "Edita src/app/components/product-list/product-list.component.ts",
        "Crea tests/e2e/todo.flaky.spec.ts",
        "El bundle app.min.js se sirve comprimido",
        "El fichero app.d.ts declara los tipos",
    ):
        assert extraer_referentes(texto) == [], texto


def test_los_ficheros_normales_con_guion_o_numero_no_se_confunden_con_un_hash():
    """Control negativo: la regla del hash no puede comerse ficheros reales."""
    valores = [r["valor"] for r in extraer_referentes("Abre datos-2024.xlsx")]
    assert valores == ["datos-2024.xlsx"]

    valores = [r["valor"] for r in extraer_referentes("Ejecuta monitor_rebalance.sh")]
    assert valores == ["monitor_rebalance.sh"]


def test_las_rutas_de_plataforma_o_de_prueba_no_son_referentes():
    for texto in (
        "Ejecuta ~/Library/Android/sdk/cmdline-tools/latest/bin/sdkmanager",
        "Revisa /datastore/settings_datastore.preferences_pb",
        "Prueba con el valor ../../etc/passwd",
        "La asercion espera /products/p-1",
    ):
        assert extraer_referentes(texto) == [], texto


def test_los_nombres_citados_como_ejemplo_no_son_referentes():
    for texto in (
        "Selecciona la suite cuyo nombre sea Login (ej: tests/Login.robot)",
        "El archivo de rutas, normalmente src/router/index.ts",
        "Un bundle con hash (p. ej. main-a1b2c3d4.js)",
    ):
        assert extraer_referentes(texto) == [], texto


def test_una_alternativa_heredan_la_marca_de_ejemplo():
    """«normalmente `a` o `b`»: la segunda también es ilustrativa."""
    texto = "El archivo de rutas, normalmente `src/router/index.js` o `src/router/index.ts`."
    assert extraer_referentes(texto) == []


def test_un_verbo_de_entrada_sobre_un_ejemplo_sigue_contando():
    """Control negativo: «abra X» manda sobre la marca de ejemplo si van juntos."""
    texto = "Por ejemplo, abra el archivo datos_ventas.xlsx de la carpeta del curso"
    valores = [r["valor"] for r in extraer_referentes(texto)]
    assert valores == ["datos_ventas.xlsx"], valores


def test_los_logs_y_los_informes_de_herramienta_no_son_referentes():
    for texto in (
        "Abre logs/snowflake_pipeline.log y verifica la traza",
        "El informe queda en docs/performance-artifacts/report.report.json",
        "Queda un temporal en disco.tmp",
    ):
        assert extraer_referentes(texto) == [], texto


def test_el_andamiaje_de_laravel_no_es_un_fichero_del_curso():
    assert extraer_referentes("@vite(['resources/js/app.js'])") == []
    # Control negativo: un fichero del proyecto que sí es del alumno.
    valores = [r["valor"] for r in extraer_referentes("Edita src/views/CatalogView.vue")]
    assert valores == ["src/views/CatalogView.vue"]


def test_un_script_definido_con_shebang_es_creacion():
    """Camino vivo: el bloque que abre con `#!` define el script que luego se cita."""
    lab = """# Lab 08-01-01: Rebalanceo

### Paso 1: Crear el monitor
```bash
#!/bin/bash
# monitor_rebalance.sh
echo "Iniciando monitoreo"
```

### Paso 2: Ejecutarlo
```bash
bash monitor_rebalance.sh
```
"""
    informe = auditar_laboratorio(lab, fuentes="temario base")
    assert informe["ok"] is True, informe["violaciones"]


def test_una_retro_referencia_de_creacion_exime_el_fichero():
    """«copia de trabajo que creaste en la configuración inicial»: ya existe."""
    lab = """# Lab 01-00-01: Configuracion

### Paso 1: Crear la copia de trabajo
Copie el libro y guardelo como M1_Catalogo_Cuentas_TRABAJO.xlsx.

### Paso 2: Abrirlo
1. Abre el archivo M1_Catalogo_Cuentas_TRABAJO.xlsx (copia de trabajo que creaste
   en la configuracion inicial).
2. Observa la estructura.
"""
    informe = auditar_laboratorio(lab, fuentes="temario base")
    assert informe["ok"] is True, informe["violaciones"]


def test_el_writer_no_reintenta_por_un_fichero_que_crea_el_propio_lab():
    """Camino vivo: el lab crea `assets/mock.json` y lo menciona después."""
    lab = """# Lab 01-01-01: Analizar la demanda historica

## Descripcion General
Analice los datos entregados.

### Paso 1: Crear el mock
```bash
cat > assets/mock.json << 'EOF'
[{"id": 1}]
EOF
```

### Paso 2: Consumirlo
La aplicacion hace fetch de assets/mock.json al arrancar.
"""
    resultado, informes, contextos = _ejecutar_writer(
        {"lab_plans": [_LAB_PLAN]}, [lab], max_intentos=3
    )
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, informes
    assert informes and informes[0]["ok"] is True, informes


def test_b6_marca_un_laboratorio_imposible_de_terminar():
    """15 minutos para 4 pasos con 12 bloques es 1,25 min por paso: imposible."""
    lab = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=None)
    informe = auditar_laboratorio(lab, fuentes="temario base", duracion_min=5)
    assert informe["ok"] is False
    b6 = [v for v in informe["violaciones"] if v["verificacion"] == "B6"]
    assert len(b6) == 1, informe["violaciones"]
    assert b6[0]["confianza"] == "alta"


def test_b6_no_marca_un_laboratorio_con_tiempo_suficiente():
    lab = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=None)
    informe = auditar_laboratorio(lab, fuentes="temario base", duracion_min=45)
    assert informe["ok"] is True, informe["violaciones"]
    assert informe["duracion"]["minutos_por_paso"] == 11.25


def test_b6_no_cuenta_los_bloques_de_salida():
    """Una salida esperada en un bloque `text` no es trabajo del alumno."""
    lab = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=None, lenguaje="text")
    informe = auditar_laboratorio(lab, fuentes="temario base", duracion_min=5)
    assert informe["ok"] is True
    assert informe["duracion"]["bloques"] == 0


def test_b6_lee_la_duracion_declarada_en_el_laboratorio():
    lab = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=5)
    assert duracion_declarada(lab) == 5
    informe = auditar_laboratorio(lab, fuentes="temario base")
    assert any(v["verificacion"] == "B6" for v in informe["violaciones"])


def test_b6_sin_duracion_no_se_pronuncia():
    lab = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=None)
    assert duracion_declarada(lab) is None
    informe = auditar_laboratorio(lab, fuentes="temario base")
    assert informe["ok"] is True


def test_el_writer_reintenta_por_una_duracion_imposible():
    """Camino vivo: el plan declara 5 minutos para un laboratorio de 12 bloques."""
    plan = {"lab_plans": [{**_LAB_PLAN, "estimated_duration": 5}]}
    imposible = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=None)
    plausible = _lab_con_bloques(pasos=2, bloques_por_paso=1, duracion=None)
    resultado, informes, contextos = _ejecutar_writer(
        plan, [imposible, plausible], max_intentos=3
    )
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 2, "debe regenerar el laboratorio"
    assert "duración declarada" in contextos[1]["referential_correction"]
    # El artefacto recoge el laboratorio **aceptado** (el segundo), no el rechazado.
    assert informes and informes[0]["por_laboratorio"]["01-01-01"]["duracion"]["duracion"] == 5


def test_el_writer_no_reintenta_por_duracion_con_el_interruptor_apagado():
    anterior = os.environ.get("DURATION_RETRY")
    os.environ["DURATION_RETRY"] = "0"
    try:
        plan = {"lab_plans": [{**_LAB_PLAN, "estimated_duration": 5}]}
        imposible = _lab_con_bloques(pasos=4, bloques_por_paso=3, duracion=None)
        resultado, informes, contextos = _ejecutar_writer(
            plan, [imposible], max_intentos=3
        )
    finally:
        if anterior is None:
            os.environ.pop("DURATION_RETRY", None)
        else:
            os.environ["DURATION_RETRY"] = anterior
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "DURATION_RETRY=0 debe dejar solo registro"
    assert informes and informes[0]["total_b6"] == 1
    assert informes[0]["por_laboratorio"]["01-01-01"]["duracion"]["ok"] is False


def test_b5_contradice_el_sistema_operativo_del_plan():
    lab = "## Descripción\nEste laboratorio requiere Windows 11 para ejecutar las herramientas.\n"
    requisitos = requisitos_declarados(
        [{"name": "Sistema operativo", "version": "Ubuntu 24.04 LTS", "purpose": "entorno"}],
        [],
    )
    informe = auditar_laboratorio(lab, fuentes="temario", requisitos_texto=requisitos)
    b5 = [v for v in informe["violaciones"] if v["verificacion"] == "B5"]
    assert [v["valor"] for v in b5] == ["Windows"]
    assert b5[0]["confianza"] == "alta"

def test_b5_contradice_la_version_de_una_herramienta():
    lab = "## Descripción\nEl entorno requiere Node 22.14.0 para ejecutar las pruebas.\n"
    requisitos = requisitos_declarados(
        [{"name": "Node.js", "version": "18.20.4", "purpose": "runtime"}], []
    )
    informe = auditar_laboratorio(lab, fuentes="temario", requisitos_texto=requisitos)
    b5 = [v for v in informe["violaciones"] if v["verificacion"] == "B5"]
    assert any(v["valor"] == "Node 22.14.0" and v["confianza"] == "alta" for v in b5), b5


def test_b5_registra_el_hardware_ampliado_sin_reintentar():
    lab = "## Requisitos\nHardware: 8 GB RAM mínimo para ejecutar el entorno.\n"
    requisitos = requisitos_declarados([{"name": "Python", "version": "3.12"}], [])
    informe = auditar_laboratorio(lab, fuentes="temario", requisitos_texto=requisitos)
    b5 = [v for v in informe["violaciones"] if v["verificacion"] == "B5"]
    assert b5 and all(v["confianza"] == "baja" for v in b5), b5


def test_b5_no_cuenta_la_especificacion_de_una_maquina_virtual():
    lab = "## Entorno\nLa VM srv1 requiere 2 GB de RAM y 2 núcleos.\n"
    requisitos = requisitos_declarados([{"name": "Ubuntu", "version": "24.04"}], [])
    informe = auditar_laboratorio(lab, fuentes="temario", requisitos_texto=requisitos)
    assert not [v for v in informe["violaciones"] if v["verificacion"] == "B5"]


def test_b5_no_comprueba_si_el_plan_no_declara_requisitos():
    lab = "## Descripción\nRequiere Windows 11 y 16 GB de RAM.\n"
    informe = auditar_laboratorio(lab, fuentes="temario", requisitos_texto="")
    assert not [v for v in informe["violaciones"] if v["verificacion"] == "B5"]


def test_el_writer_reintenta_por_una_contradiccion_de_requisito():
    plan = {
        "lab_plans": [_LAB_PLAN],
        "software_requirements": [{"name": "Node.js", "version": "18.20.4", "purpose": "runtime"}],
    }
    contradictorio = (
        "## Descripción\nEl entorno requiere Node 22.14.0 o superior.\n\n"
        "### Paso 1: Ejecutar\n```bash\necho ok\n```\n"
    )
    alineado = (
        "## Descripción\nEl entorno usa Node 18.20.4, el declarado por el curso.\n\n"
        "### Paso 1: Ejecutar\n```bash\necho ok\n```\n"
    )
    resultado, _informes, contextos = _ejecutar_writer(
        plan, [contradictorio, alineado], max_intentos=3
    )
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 2, "debe regenerar el laboratorio"
    assert "Alinealo con el plan" in contextos[1]["referential_correction"]


def test_el_writer_no_reintenta_por_hardware_ampliado():
    plan = {"lab_plans": [_LAB_PLAN], "software_requirements": [{"name": "Python", "version": "3.12"}]}
    ampliado = (
        "## Requisitos\nHardware: 16 GB RAM mínimo.\n\n"
        "### Paso 1: Ejecutar\n```bash\necho ok\n```\n"
    )
    resultado, informes, contextos = _ejecutar_writer(plan, [ampliado], max_intentos=3)
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "una ampliación de baja confianza no debe regenerar"
    assert informes and informes[0]["total_b5"] >= 1
    assert informes[0]["total_alta_confianza"] == 0


def test_el_writer_no_reintenta_por_requisito_con_el_interruptor_apagado():
    anterior = os.environ.get("REQUIREMENTS_RETRY")
    os.environ["REQUIREMENTS_RETRY"] = "0"
    try:
        plan = {
            "lab_plans": [_LAB_PLAN],
            "software_requirements": [{"name": "Node.js", "version": "18.20.4"}],
        }
        contradictorio = (
            "## Descripción\nEl entorno requiere Node 22.14.0 o superior.\n\n"
            "### Paso 1: Ejecutar\n```bash\necho ok\n```\n"
        )
        resultado, informes, contextos = _ejecutar_writer(
            plan, [contradictorio], max_intentos=3
        )
    finally:
        if anterior is None:
            os.environ.pop("REQUIREMENTS_RETRY", None)
        else:
            os.environ["REQUIREMENTS_RETRY"] = anterior
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "REQUIREMENTS_RETRY=0 debe dejar solo registro"
    assert informes and informes[0]["total_b5"] == 1


def test_b3p_marca_un_entregable_que_el_laboratorio_no_menciona():
    lab = "### Paso 1: Preparar\n```bash\necho hola\n```\n"
    informe = auditar_laboratorio(
        lab,
        fuentes="temario",
        expected_outcomes=["Archivo 'data_transform.py' con al menos 6 funciones"],
    )
    b3p = [v for v in informe["violaciones"] if v["verificacion"] == "B3p"]
    assert [v["valor"] for v in b3p] == ["data_transform.py"]
    assert b3p[0]["confianza"] == "alta"


def test_b3p_no_marca_el_entregable_que_el_laboratorio_crea():
    lab = "### Paso 1: Crear el módulo\n```bash\ncat > data_transform.py << 'EOF'\nEOF\n```\n"
    informe = auditar_laboratorio(
        lab,
        fuentes="temario",
        expected_outcomes=["Archivo 'data_transform.py' con al menos 6 funciones"],
    )
    assert not [v for v in informe["violaciones"] if v["verificacion"] == "B3p"]


def test_b3p_registra_como_baja_el_entregable_mencionado_sin_creacion():
    lab = "### Paso 1: Revisar\nAbra `data_transform.py` y observe las funciones.\n"
    informe = auditar_laboratorio(
        lab,
        fuentes="temario",
        expected_outcomes=["Archivo 'data_transform.py' con al menos 6 funciones"],
    )
    b3p = [v for v in informe["violaciones"] if v["verificacion"] == "B3p"]
    assert b3p and all(v["confianza"] == "baja" for v in b3p), b3p


def test_b3p_acepta_una_alternativa_del_plan():
    lab = "### Paso 1: Crear el script\n```bash\ncat > deploy.ps1 << 'EOF'\nEOF\n```\n"
    informe = auditar_laboratorio(
        lab,
        fuentes="temario",
        expected_outcomes=["Script de despliegue (deploy.sh o deploy.ps1) que importa la aplicación"],
    )
    assert not [v for v in informe["violaciones"] if v["verificacion"] == "B3p"]


def test_b3p_ignora_un_fichero_que_es_entrada_del_curso():
    lab = "### Paso 1: Ejecutar\n```bash\necho ok\n```\n"
    informe = auditar_laboratorio(
        lab,
        fuentes="temario",
        expected_outcomes=["Proceso ejecutable con 'robot --variable INPUT_FILE:orders.xlsx rpa.robot'"],
    )
    assert not [v for v in informe["violaciones"] if v["verificacion"] == "B3p"]


def test_el_writer_no_reintenta_por_entregable_omitido_por_defecto():
    plan = {
        "lab_plans": [
            {**_LAB_PLAN, "expected_outcomes": ["Archivo 'data_transform.py' con 6 funciones"]}
        ]
    }
    lab = "### Paso 1: Preparar\n```bash\necho ok\n```\n"
    resultado, informes, contextos = _ejecutar_writer(plan, [lab], max_intentos=3)
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 1, "B3p no debe reintentar por defecto"
    assert informes and informes[0]["total_b3p"] == 1


def test_el_writer_reintenta_por_entregable_omitido_si_se_enciende():
    anterior = os.environ.get("DELIVERABLES_RETRY")
    os.environ["DELIVERABLES_RETRY"] = "1"
    try:
        plan = {
            "lab_plans": [
                {**_LAB_PLAN, "expected_outcomes": ["Archivo 'data_transform.py' con 6 funciones"]}
            ]
        }
        lab = "### Paso 1: Preparar\n```bash\necho ok\n```\n"
        corregido = (
            "### Paso 1: Crear el módulo\n```bash\ncat > data_transform.py << 'EOF'\nEOF\n```\n"
        )
        resultado, _informes, contextos = _ejecutar_writer(
            plan, [lab, corregido], max_intentos=3
        )
    finally:
        if anterior is None:
            os.environ.pop("DELIVERABLES_RETRY", None)
        else:
            os.environ["DELIVERABLES_RETRY"] = anterior
    assert resultado["statusCode"] == 200, resultado
    assert len(contextos) == 2, "con DELIVERABLES_RETRY=1 debe regenerar"
    assert "no los menciona ni una vez" in contextos[1]["referential_correction"]


def test_a3_fija_la_duracion_que_declara_el_temario():
    """Caso real: el temario declara 18 minutos y el plan puso 40."""
    plan = {"lab_plans": [{"lab_id": "01-00-01", "estimated_duration": 40}]}
    labs = [{"lab_id": "01-00-01", "duration_minutes": 18}]
    informe = reconciliar_duraciones(plan, labs)
    assert plan["lab_plans"][0]["estimated_duration"] == 18
    assert informe["corregidos"] == [{"lab_id": "01-00-01", "antes": 40, "despues": 18}]


def test_a3_no_toca_lo_que_ya_coincide():
    plan = {"lab_plans": [{"lab_id": "01-00-01", "estimated_duration": 45}]}
    informe = reconciliar_duraciones(plan, [{"lab_id": "01-00-01", "duration_minutes": 45}])
    assert informe["corregidos"] == []
    assert plan["lab_plans"][0]["estimated_duration"] == 45


def test_a3_no_inventa_duracion_para_un_lab_sin_contrato():
    plan = {"lab_plans": [{"lab_id": "09-00-01", "estimated_duration": 30}]}
    informe = reconciliar_duraciones(plan, [{"lab_id": "01-00-01", "duration_minutes": 45}])
    assert informe["corregidos"] == []
    assert informe["sin_contrato"] == 1
    assert plan["lab_plans"][0]["estimated_duration"] == 30


def test_a3_detecta_que_el_plan_excede_el_curso():
    plan = {"lab_plans": [{"estimated_duration": 120}, {"estimated_duration": 90}]}
    informe = auditar_duraciones_curso(plan, [], total_curso=180)
    assert informe["suma_plan"] == 210
    assert informe["excede_total"] is True
    assert informe["ok"] is False


def test_a3_detecta_el_numero_de_practicas():
    plan = {"lab_plans": [{"estimated_duration": 20}]}
    labs = [{"lab_id": "01"}, {"lab_id": "02"}, {"lab_id": "03"}]
    informe = auditar_duraciones_curso(plan, labs, total_curso=180)
    assert informe["faltan"] == 2
    assert informe["ok"] is False


def test_a3_con_todo_cuadrado():
    plan = {"lab_plans": [{"estimated_duration": 45}, {"estimated_duration": 45}]}
    labs = [{"lab_id": "01"}, {"lab_id": "02"}]
    informe = auditar_duraciones_curso(plan, labs, total_curso=180)
    assert informe["ok"] is True


def test_a3_sobre_un_caso_real_del_corpus():
    """El caso de 260627-COP-CHAT-LEGAL: el temario declara 50 y el plan puso 90."""
    plan = {
        "lab_plans": [
            {"lab_id": "01-00-01", "estimated_duration": 60},
            {"lab_id": "02-00-01", "estimated_duration": 90},
            {"lab_id": "03-00-01", "estimated_duration": 90},
            {"lab_id": "04-00-01", "estimated_duration": 60},
        ]
    }
    labs = [
        {"lab_id": "01-00-01", "duration_minutes": 50},
        {"lab_id": "02-00-01", "duration_minutes": 50},
        {"lab_id": "03-00-01", "duration_minutes": 50},
        {"lab_id": "04-00-01", "duration_minutes": 50},
    ]
    reconciliar_duraciones(plan, labs)
    informe = auditar_duraciones_curso(plan, labs, total_curso=240)
    assert [p["estimated_duration"] for p in plan["lab_plans"]] == [50, 50, 50, 50]
    assert informe["suma_plan"] == 200
    assert informe["ok"] is True


def test_el_planner_aplica_a3_antes_de_guardar():
    """Camino vivo: el plan guardado lleva la duración del temario, no la del modelo."""
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)
    outline = {
        "course": {
            "title": "Curso de prueba",
            "total_duration_minutes": 120,
            "modules": [
                {
                    "title": "Modulo 1",
                    "lab_activities": [
                        {"title": "Practica uno", "duration_minutes": 18},
                        {"title": "Practica dos", "duration_minutes": 22},
                    ],
                }
            ],
        }
    }
    guardado = {}
    modulo.load_outline_from_s3 = lambda *a, **k: outline
    modulo.generate_lab_master_plan = lambda **k: {
        "lab_plans": [
            {"lab_id": "01-00-01", "lab_title": "Practica uno", "estimated_duration": 40,
             "objectives": ["a"], "scope": "b", "expected_outcomes": ["c"]},
            {"lab_id": "01-00-02", "lab_title": "Practica dos", "estimated_duration": 30,
             "objectives": ["a"], "scope": "b", "expected_outcomes": ["c"]},
        ]
    }
    modulo.auditar_y_corregir_plan = lambda plan, **k: (plan, {"total": 0, "violaciones": [], "ok": True})
    modulo.save_master_plan_to_s3 = lambda bucket, project_folder, master_plan: (
        guardado.update({"plan": master_plan}) or "p/labguide/lab-master-plan.json"
    )
    modulo.s3_client = _S3Simulado({})

    resultado = modulo.lambda_handler(
        {
            "course_bucket": "bucket",
            "outline_s3_key": "p/outline/curso.yaml",
            "project_folder": "p",
            "model_provider": "bedrock",
        },
        None,
    )

    assert resultado["statusCode"] == 200, resultado
    plan = guardado["plan"]
    assert [p["estimated_duration"] for p in plan["lab_plans"]] == [18, 22]
    assert plan["metadata"]["duration_integrity"]["suma_plan"] == 40
    assert plan["metadata"]["duration_integrity"]["corregidos"][0]["antes"] == 40


def _handler_de_planificador_con_temario(modulo, outline, plan_del_modelo):
    """Ejecuta el handler real con el temario y el plan del modelo dados."""
    guardado = {}
    modulo.load_outline_from_s3 = lambda *a, **k: outline
    modulo.generate_lab_master_plan = lambda **k: plan_del_modelo
    modulo.auditar_y_corregir_plan = lambda plan, **k: (
        plan,
        {"total": 0, "violaciones": [], "ok": True},
    )
    modulo.save_master_plan_to_s3 = lambda bucket, project_folder, master_plan: (
        guardado.update({"plan": master_plan}) or "p/labguide/lab-master-plan.json"
    )
    modulo.s3_client = _S3Simulado({})
    resultado = modulo.lambda_handler(
        {
            "course_bucket": "bucket",
            "outline_s3_key": "p/outline/curso.yaml",
            "project_folder": "p",
            "model_provider": "bedrock",
        },
        None,
    )
    assert resultado["statusCode"] == 200, resultado
    return guardado["plan"]


def test_el_planner_copia_al_plan_el_objetivo_del_temario():
    """Camino vivo: el temario manda y el plan guardado lo reproduce literal."""
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)
    declarado = "Automatizar la conciliacion de inventario con un script de Python."
    descripcion = "El alumno lee inventario.txt, calcula totales y escribe resumen.txt."
    outline = {
        "course": {
            "title": "Curso de prueba",
            "total_duration_minutes": 120,
            "modules": [
                {
                    "title": "Modulo 1",
                    "lab_activities": [
                        {
                            "title": "Practica uno",
                            "duration_minutes": 30,
                            "objective": declarado,
                            "description": descripcion,
                        }
                    ],
                }
            ],
        }
    }
    plan_del_modelo = {
        "lab_plans": [
            {
                "lab_id": "01-00-01",
                "lab_title": "Practica uno",
                "estimated_duration": 30,
                "objectives": ["Comprender la estructura de un fichero de texto"],
                "scope": "Leer un fichero y escribir otro.",
                "expected_outcomes": ["c"],
            }
        ]
    }

    plan = _handler_de_planificador_con_temario(modulo, outline, plan_del_modelo)
    lab = plan["lab_plans"][0]

    assert lab["objectives"][0] == declarado
    assert lab["objectives"][1] == "Comprender la estructura de un fichero de texto"
    assert lab["outline_objective"] == declarado
    assert lab["outline_description"] == descripcion

    informe = plan["metadata"]["contract_integrity"]
    assert informe["ok"] is True, informe["conflictos"]
    assert informe["con_declaracion"] == 1
    assert informe["labs"] == 1


def test_el_contrato_no_obliga_al_temario_a_declarar_nada():
    """Camino vivo: sin ``objective`` ni ``description`` el plan no cambia.

    Es la garantía de que A5 no añade campos obligatorios al temario: 422 de 1.279
    laboratorios reales no declaran objetivo.
    """
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)
    outline = {
        "course": {
            "title": "Curso de prueba",
            "total_duration_minutes": 120,
            "modules": [
                {
                    "title": "Modulo 1",
                    "lab_activities": [{"title": "Practica uno", "duration_minutes": 30}],
                }
            ],
        }
    }
    plan_del_modelo = {
        "lab_plans": [
            {
                "lab_id": "01-00-01",
                "lab_title": "Practica uno",
                "estimated_duration": 30,
                "objectives": ["Comprender la estructura de un fichero de texto"],
                "scope": "Leer un fichero y escribir otro.",
                "expected_outcomes": ["c"],
            }
        ]
    }

    plan = _handler_de_planificador_con_temario(modulo, outline, plan_del_modelo)
    lab = plan["lab_plans"][0]

    assert lab["objectives"] == ["Comprender la estructura de un fichero de texto"]
    assert "outline_objective" not in lab
    assert "outline_description" not in lab
    informe = plan["metadata"]["contract_integrity"]
    assert informe["ok"] is True
    assert informe["con_declaracion"] == 0
    assert informe["sin_declaracion"] == 1


def test_el_contrato_detecta_un_objetivo_reescrito():
    """La comprobación no es vacua: ve el defecto que había antes de A5."""
    declarado = "Automatizar la conciliacion de inventario con un script de Python."
    labs = [
        {
            "lab_id": "01-00-01",
            "lab_title": "Practica uno",
            "duration_minutes": 30,
            "objective": declarado,
            "description": "",
        }
    ]
    plan = {
        "lab_plans": [
            {
                "lab_id": "01-00-01",
                "lab_title": "Practica uno",
                "estimated_duration": 30,
                "objectives": ["Comprender la estructura de un fichero de texto"],
            }
        ]
    }

    informe = auditar_contrato(plan, labs)

    assert informe["ok"] is False
    assert [conflicto["campo"] for conflicto in informe["conflictos"]] == ["objective"]
    assert informe["conflictos"][0]["temario"] == declarado


def test_reconciliar_contrato_deja_el_plan_auditable():
    """Reconciliar y auditar componen: después de copiar, no hay conflictos."""
    declarado = "Automatizar la conciliacion de inventario."
    labs = [
        {
            "lab_id": "01-00-01",
            "lab_title": "Practica uno",
            "duration_minutes": 30,
            "objective": declarado,
            "description": "Leer inventario.txt y escribir resumen.txt.",
        }
    ]
    plan = {
        "lab_plans": [
            {
                "lab_id": "01-00-01",
                "lab_title": "Practica uno",
                "estimated_duration": 30,
                "objectives": ["Objetivo inventado por el modelo"],
            }
        ]
    }

    reconciliado = reconciliar_contrato(plan, labs)
    informe = auditar_contrato(plan, labs)

    assert reconciliado["anadidos"] == [{"lab_id": "01-00-01", "campo": "objectives"}]
    assert plan["lab_plans"][0]["objectives"] == [declarado, "Objetivo inventado por el modelo"]
    assert informe["ok"] is True, informe["conflictos"]


def test_el_planificador_entrega_al_modelo_lo_que_declara_el_temario():
    """Camino vivo del prompt: el modelo ve el objetivo declarado, no solo el título."""
    modulo = _cargar_modulo("strands_lab_planner", _CARPETA_PLANNER)
    prompts = []

    def modelo_de_prueba(prompt, model_id):
        prompts.append(prompt)
        return json.dumps(
            {
                "overall_objectives": [],
                "hardware_requirements": [],
                "software_requirements": [],
                "lab_plans": [
                    {
                        "lab_id": "01-00-01",
                        "lab_title": "Practica uno",
                        "objectives": ["y"],
                        "scope": "z",
                        "estimated_duration": 30,
                        "bloom_level": "Apply",
                        "prerequisites": [],
                        "key_technologies": [],
                        "expected_outcomes": [],
                        "complexity": "easy",
                    }
                ],
                "special_considerations": [],
            }
        )

    modulo.call_bedrock_agent = modelo_de_prueba
    labs = [
        {
            "lab_id": "01-00-01",
            "module_number": 1,
            "lesson_number": 0,
            "lab_title": "Practica uno",
            "duration_minutes": 30,
            "bloom_level": "Apply",
            "context_topics": ["ficheros"],
            "objective": "Automatizar la conciliacion de inventario.",
            "description": "El alumno lee inventario.txt y escribe resumen.txt.",
        }
    ]

    modulo.generate_lab_master_plan(
        labs=labs,
        course_info={"title": "Curso", "language": "es"},
        additional_requirements=None,
        model_provider="bedrock",
    )

    assert prompts, "no se construyó ningún prompt"
    assert "DECLARED OBJECTIVE (outline, verbatim): Automatizar la conciliacion" in prompts[0]
    assert "DECLARED DESCRIPTION (outline, verbatim): El alumno lee inventario.txt" in prompts[0]
    assert "Outline Contract (A5)" in prompts[0]


def test_el_writer_recibe_el_contrato_declarado_en_el_temario():
    """Camino vivo del prompt del Writer (lote de 1: el constructor compacto)."""
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)
    prompts = []

    def modelo_de_prueba(prompt, model_id):
        prompts.append(prompt)
        return (
            "---LAB_START---\nLAB_ID: 01-00-01\n---MARKDOWN---\n"
            "# Lab 01-00-01: Practica uno\n\n## Descripcion General\n\nTexto.\n"
            "---LAB_END---"
        )

    modulo.call_bedrock_agent = modelo_de_prueba
    for nombre in ("call_openai_agent", "call_gemini_agent"):
        setattr(modulo, nombre, lambda *a, **k: prompts.append("otro") or "")
    plan_lab = {
        "lab_id": "01-00-01",
        "lab_title": "Practica uno",
        "estimated_duration": 30,
        "bloom_level": "Apply",
        "objectives": ["Automatizar la conciliacion de inventario."],
        "scope": "Leer inventario y escribir resumen.",
        "prerequisites": [],
        "key_technologies": [],
        "expected_outcomes": [],
        "outline_objective": "Automatizar la conciliacion de inventario.",
        "outline_description": "El alumno lee inventario.txt y escribe resumen.txt.",
    }
    contexto = {
        "target_language": "Spanish",
        "hardware_requirements": [],
        "software_requirements": [],
        "special_considerations": [],
        "overall_objectives": [],
        "additional_requirements": "",
    }

    modulo.generate_all_labs_batch([plan_lab], contexto)

    assert prompts, "no se construyó ningún prompt"
    assert "copy the objective verbatim" in prompts[0]
    assert "El alumno lee inventario.txt y escribe resumen.txt." in prompts[0]


def test_el_writer_no_inventa_contrato_si_el_temario_no_declaro():
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)
    prompts = []

    def modelo_de_prueba(prompt, model_id):
        prompts.append(prompt)
        return (
            "---LAB_START---\nLAB_ID: 01-00-01\n---MARKDOWN---\n"
            "# Lab 01-00-01: Practica uno\n\n## Descripcion General\n\nTexto.\n"
            "---LAB_END---"
        )

    modulo.call_bedrock_agent = modelo_de_prueba
    plan_lab = {
        "lab_id": "01-00-01",
        "lab_title": "Practica uno",
        "estimated_duration": 30,
        "bloom_level": "Apply",
        "objectives": ["Comprender la estructura de un fichero de texto"],
        "scope": "Leer inventario y escribir resumen.",
        "prerequisites": [],
        "key_technologies": [],
        "expected_outcomes": [],
    }
    contexto = {
        "target_language": "Spanish",
        "hardware_requirements": [],
        "software_requirements": [],
        "special_considerations": [],
        "overall_objectives": [],
        "additional_requirements": "",
    }

    modulo.generate_all_labs_batch([plan_lab], contexto)

    assert prompts
    assert "DECLARED BY THE INSTRUCTOR" not in prompts[0]


def test_la_guia_recibe_el_objetivo_del_temario_si_el_modelo_lo_reescribe():
    """Camino vivo del Writer: el modelo parafrasea y la guía sale con el texto aprobado."""
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)
    declarado = "Instalar Python y VS Code, crear un entorno virtual y resolver ejercicios cortos."

    def modelo_de_prueba(prompt, model_id):
        return (
            "---LAB_START---\nLAB_ID: 01-00-01\n---MARKDOWN---\n"
            "# Lab 01-00-01: Practica uno\n\n"
            "## Objetivos de Aprendizaje\n\n"
            "- [ ] Verificar la instalacion de Python 3.12.3.\n"
            "- [ ] Crear y activar un entorno virtual.\n\n"
            "## Prerrequisitos\n\nNinguno.\n"
            "---LAB_END---"
        )

    modulo.call_bedrock_agent = modelo_de_prueba
    plan_lab = {
        "lab_id": "01-00-01",
        "lab_title": "Practica uno",
        "estimated_duration": 30,
        "bloom_level": "Apply",
        "objectives": [declarado, "Verificar la instalacion de Python 3.12.3."],
        "scope": "Instalar y probar.",
        "prerequisites": [],
        "key_technologies": [],
        "expected_outcomes": [],
        "outline_objective": declarado,
    }
    contexto = {
        "target_language": "Spanish",
        "hardware_requirements": [],
        "software_requirements": [],
        "special_considerations": [],
        "overall_objectives": [],
        "additional_requirements": "",
    }

    guias = modulo.generate_all_labs_batch([plan_lab], contexto)
    guia = guias["01-00-01"]

    assert f"- [ ] {declarado}" in guia
    assert guia.count(declarado) == 1, "el objetivo declarado se duplicó"
    posicion_declarado = guia.index(declarado)
    posicion_parafrasis = guia.index("Verificar la instalacion de Python 3.12.3.")
    assert posicion_declarado < posicion_parafrasis, "el objetivo del temario debe ir primero"


def test_asegurar_objetivo_declarado_no_duplica_ni_inventa():
    """Sin objetivo declarado no hace nada; si ya está en la guía, tampoco."""
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)
    markdown = (
        "# Lab\n\n## Objetivos de Aprendizaje\n\n"
        "- [ ] Automatizar la conciliacion de inventario.\n\n## Prerrequisitos\n"
    )
    plan = {"outline_objective": "Automatizar la conciliacion de inventario."}

    salida, insertado = modulo.asegurar_objetivo_declarado(markdown, plan)
    assert insertado is False
    assert salida == markdown

    salida, insertado = modulo.asegurar_objetivo_declarado(markdown, {})
    assert insertado is False
    assert salida == markdown


def _lab_con_bloques(pasos, bloques_por_paso, duracion, lenguaje="bash"):
    """Laboratorio sintético con pasos y bloques, sin referentes de fichero."""
    cabecera = "# Lab 01-01-01: Analizar la demanda historica\n\n"
    if duracion:
        cabecera += f"| Duración | {duracion} minutos |\n\n"
    cuerpo = []
    for paso in range(1, pasos + 1):
        cuerpo.append(f"### Paso {paso}: Ejecutar la comprobacion {paso}\n")
        for bloque in range(1, bloques_por_paso + 1):
            cuerpo.append(f"```{lenguaje}\necho paso {paso} bloque {bloque}\n```\n")
    return cabecera + "\n".join(cuerpo)


# --------------------------------------------------------------------------- #
# Calibración del 22/10/2026 (spec §24): los estrechamientos
# --------------------------------------------------------------------------- #

def test_el_marcador_por_confirmar_exime_el_referente():
    """Nivel 3 de la regla: el fichero se señala, no se afirma.

    Sin esto la corrección que el propio Writer prescribe no converge: se midió que
    insertar el marcador dejaba el hallazgo intacto y el reintento acababa tumbando
    el curso (`RuntimeError` → `LabBatchFailState`).
    """
    lab = (
        "### Paso 1: Revisar los datos\n"
        "Abra el archivo `Ventas_MultiRegional_2024.xlsx` desde OneDrive [POR CONFIRMAR] "
        "y revise las hojas del libro.\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["violaciones"] == []
    assert [m["valor"] for m in informe["marcados"]] == ["Ventas_MultiRegional_2024.xlsx"]


def test_el_marcador_de_la_introduccion_exime_las_filas_de_la_tabla():
    """El marcador va en la línea que introduce la tabla, no en la fila del nombre."""
    lab = (
        "### Paso 1: Verificar las fuentes\n"
        "El instructor debe confirmar que la carpeta de fuentes contiene los siguientes "
        "archivos ficticios y anonimizados:\n\n"
        "| Archivo de fuente | Uso |\n"
        "|---|---|\n"
        "| `BA_05-00-01_DueDiligence_NubeSur_v01.docx` | contexto contractual |\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["violaciones"] == []
    assert informe["marcados"]


def test_un_nombre_que_solo_vive_en_un_bloque_de_codigo_no_es_entrada():
    """El falso positivo medido en `260129-IA-GEN-ESS-V2` (bloqueaba el curso).

    Los nombres son un listado de ejemplo; el «Abre el PDF» de la frase siguiente
    habla de otro fichero. Al quedar como baja se sigue registrando, pero no dispara
    el reintento correctivo.
    """
    lab = (
        "### Paso 3: Trocear el documento\n"
        "Si el archivo es muy grande, divídelo en secciones más pequeñas:\n"
        "```\n"
        "politica_vacaciones_parte1.txt\n"
        "politica_vacaciones_parte2.txt\n"
        "```\n"
        "3. Si es un PDF con problemas, conviértelo a .txt:\n"
        "- Abre el PDF\n"
        "- Copia el texto en un archivo nuevo\n"
    )
    informe = auditar_laboratorio(lab, "")
    confianzas = {v["valor"]: v["confianza"] for v in informe["violaciones"]}
    assert confianzas["politica_vacaciones_parte1.txt"] == "baja"
    assert confianzas["politica_vacaciones_parte2.txt"] == "baja"


def test_un_fichero_nombrado_en_prosa_sigue_siendo_entrada():
    """La contraparte: el verdadero positivo de `251209-copilot-365-4-h` no se pierde."""
    lab = (
        "### Paso 1: Explorar el workbook\n"
        '1. Abra el archivo "Ventas_MultiRegional_2024.xlsx" desde OneDrive en Excel de escritorio.\n'
        "2. Haga clic en Copilot y pida un resumen de las hojas.\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["violaciones"][0]["valor"] == "Ventas_MultiRegional_2024.xlsx"
    assert informe["violaciones"][0]["confianza"] == "alta"


def test_la_duracion_estimada_del_metadato_se_lee():
    """El corpus escribe `| **Duración estimada** | …`: antes se ignoraba y B6 tomaba
    la duración del plan, que es de donde salían los falsos positivos."""
    assert duracion_declarada("| **Duración estimada** | 13 minutos |") == 13
    assert duracion_declarada("| Duración | 15 minutos |") == 15
    assert duracion_declarada("**Duración total:** 40 minutos") == 40
    assert duracion_declarada("sin metadatos") is None


def test_la_duracion_de_un_desglose_toma_el_mayor():
    lab = (
        "| Propiedad | Valor |\n"
        "|---|---|\n"
        "| **Duración** | 15 minutos (creación VM) + 35–45 minutos (instalación OS) + "
        "15 minutos (post-instalación) |\n"
    )
    assert duracion_declarada(lab) == 45


def test_b6_no_marca_un_laboratorio_con_duracion_compuesta():
    """El falso positivo de B6 en `260924-Temario-fortinet-…` lab `02-00-02`.

    Ocho pasos con ocho bloques cada uno: con la duración mal leída (15 min) salía
    «imposible»; con el desglose bien leído (45 min) el laboratorio entra en lo
    razonable y B6 no debe marcarlo.
    """
    cuerpo = []
    for paso in range(1, 9):
        cuerpo.append(f"### Paso {paso}: Ejecutar la comprobación {paso}\n")
        for bloque in range(1, 9):
            cuerpo.append(f"```bash\necho paso {paso} bloque {bloque}\n```\n")
    lab = (
        "# Lab 02-00-02: Instalación\n\n"
        "| Propiedad | Valor |\n|---|---|\n"
        "| **Duración** | 15 minutos (creación VM) + 35–45 minutos (instalación OS) + "
        "15 minutos (post-instalación) |\n\n" + "\n".join(cuerpo)
    )
    informe = auditar_laboratorio(lab, "")
    assert [v for v in informe["violaciones"] if v["verificacion"] == "B6"] == []


def _lab_tipo_angular(duracion):
    """Laboratorio con la forma medida en `260728-angular-essentials`/`06-00-01`.

    Ocho pasos con acción y 27 bloques: `ng new`, tres `ng generate`, las
    plantillas y los estilos de dos componentes y las comprobaciones. El caso
    real declara **12 minutos**; el 23/10/2026 se leyó entero y se etiquetó como
    imposible, no como falso positivo.
    """
    pasos = [
        ("Crear el proyecto y entrar", [
            ("bash", "ng new lab-componentes --routing=false --style=css"),
            ("bash", "cd lab-componentes"),
            ("bash", "ls -la src/app"),
        ]),
        ("Arrancar la aplicación", [
            ("bash", "ng serve --open"),
            ("bash", "curl -I http://localhost:4200"),
        ]),
        ("Generar los componentes", [
            ("bash", "ng generate component tarjeta-producto"),
            ("bash", "ng generate component lista-productos"),
            ("bash", "ng generate component detalle-producto"),
            ("bash", "tree src/app"),
        ]),
        ("Definir el modelo y los componentes", [
            ("typescript", "export interface Producto {\n  nombre: string;\n  precio: number;\n}"),
            ("typescript", "@Input() producto!: Producto;"),
            ("typescript", "productos: Producto[] = [];"),
            ("typescript", "ngOnChanges(cambios: SimpleChanges): void {}"),
        ]),
        ("Maquetar la tarjeta", [
            ("html", "<article class=\"tarjeta\">\n  <h3>{{ producto.nombre }}</h3>\n</article>"),
            ("css", ".tarjeta {\n  border-radius: 8px;\n}"),
            ("html", "<app-tarjeta-producto [producto]=\"producto\" />"),
            ("typescript", "import { TarjetaProductoComponent } from './tarjeta-producto/tarjeta-producto.component';"),
        ]),
        ("Componer la lista", [
            ("typescript", "import { Producto } from '../models/producto.model';"),
            ("html", "<app-tarjeta-producto *ngFor=\"let p of productos\" [producto]=\"p\" />"),
            ("css", ".lista {\n  display: grid;\n}"),
            ("html", "<p>Total: {{ productos.length }}</p>"),
        ]),
        ("Compilar y probar", [
            ("bash", "ng build"),
            ("bash", "npm test -- --watch=false"),
            ("bash", "ls dist/lab-componentes"),
        ]),
        ("Documentar y limpiar", [
            ("markdown", "# Primer componente\n\nSe generó con Angular CLI."),
            ("bash", "git add ."),
            ("bash", "git commit -m \"feat: primer componente\""),
            ("bash", "git log --oneline -1"),
        ]),
    ]
    cuerpo = ["# Lab 06-00-01: Crear el primer componente\n\n"
              f"| **Duración** | {duracion} minutos |\n"
              "| **Complejidad** | Fácil |\n"]
    for numero, (titulo, bloques) in enumerate(pasos, start=1):
        cuerpo.append(f"### Paso {numero}: {titulo}\n")
        for lenguaje, contenido in bloques:
            cuerpo.append(f"```{lenguaje}\n{contenido}\n```\n")
    return "\n".join(cuerpo)


def test_b6_marca_el_caso_angular_de_12_minutos():
    """12 minutos para `ng new` + tres `ng generate` + dos plantillas: imposible.

    Es el caso real `260728-angular-essentials`/`06-00-01`, leído el 23/10/2026:
    1,5 min por paso y 0,44 min por bloque. B6 debe marcarlo con confianza alta.
    """
    lab = _lab_tipo_angular(12)
    informe = auditar_laboratorio(lab, "")
    assert informe["duracion"]["con_accion"] == 8, informe["duracion"]
    assert informe["duracion"]["bloques"] == 27, informe["duracion"]
    assert informe["duracion"]["minutos_por_paso"] == 1.5
    assert informe["duracion"]["minutos_por_bloque"] == 0.44
    b6 = [v for v in informe["violaciones"] if v["verificacion"] == "B6"]
    assert len(b6) == 1, informe["violaciones"]
    assert b6[0]["confianza"] == "alta"
    # max(8 × 2,0 = 16; 27 × 0,75 = 20,25) → 21.
    assert b6[0]["duracion_minima"] == 21


def test_b6_no_marca_el_mismo_caso_angular_con_45_minutos():
    """El mismo trabajo con una duración plausible deja de ser una contradicción.

    Fija el otro lado del umbral: si un cambio futuro moviera ``_MINUTOS_POR_PASO_ACCION``
    o ``_MINUTOS_POR_BLOQUE``, uno de los dos lados de esta pareja se rompe.
    """
    lab = _lab_tipo_angular(45)
    informe = auditar_laboratorio(lab, "")
    assert [v for v in informe["violaciones"] if v["verificacion"] == "B6"] == []
    assert informe["duracion"]["minutos_por_paso"] == 5.62
    assert informe["duracion"]["minutos_por_bloque"] == 1.67
    assert informe["duracion"]["duracion_minima"] == 21
    assert informe["duracion"]["duracion_maxima"] == 60


def test_b6_admite_una_desviacion_dentro_del_techo():
    """60 minutos declarados admiten hasta 80: 100 bloques son 75 minutos y caben."""
    lab = _lab_con_bloques(pasos=5, bloques_por_paso=20, duracion=60)
    informe = auditar_laboratorio(lab, "")
    assert informe["ok"] is True, informe["violaciones"]
    assert informe["duracion"]["duracion_minima"] == 75
    assert informe["duracion"]["duracion_maxima"] == 80


def test_b6_marca_cuando_el_trabajo_pasa_del_techo():
    """Los mismos 60 minutos con 108 bloques (81 minutos) ya no admiten la desviación."""
    lab = _lab_con_bloques(pasos=6, bloques_por_paso=18, duracion=60)
    informe = auditar_laboratorio(lab, "")
    b6 = [v for v in informe["violaciones"] if v["verificacion"] == "B6"]
    assert len(b6) == 1, informe["violaciones"]
    assert b6[0]["duracion_minima"] == 81
    assert b6[0]["duracion_maxima"] == 80


def test_b6_una_desviacion_pequena_no_marca():
    """La forma de `06-00-02`: 13 minutos con 14 de mínimo y 17 de techo no es desviación."""
    lab = _lab_con_bloques(pasos=6, bloques_por_paso=3, duracion=13)
    informe = auditar_laboratorio(lab, "")
    duracion = informe["duracion"]
    assert duracion["duracion_minima"] == 14
    assert duracion["duracion_maxima"] == 17
    assert [v for v in informe["violaciones"] if v["verificacion"] == "B6"] == []


def test_el_mensaje_de_b6_pide_el_techo_y_no_cambiar_la_duracion():
    """El reintento debe saber cuánto recortar, y que la duración no se toca.

    La duración viene del plan: pedir «pon 21 minutos» no convergería. El mensaje da
    el techo del hueco (4/3 de lo declarado) y pide reducir el volumen.
    """
    lab = _lab_tipo_angular(12)
    informe = auditar_laboratorio(lab, "")
    b6 = [v for v in informe["violaciones"] if v["verificacion"] == "B6"]
    assert b6[0]["duracion_minima"] == 21
    assert b6[0]["duracion_maxima"] == 16
    mensaje = mensaje_de_correccion(informe["violaciones"], "laboratorio")
    assert "16 minutos" in mensaje
    assert "no cambies la duración del plan" in mensaje


def test_la_nota_al_instructor_que_pide_verificar_exime_el_material():
    """Nivel 3 escrito en prosa, tal como aparece en el corpus real.

    Caso medido el 23/10/2026 en el curso de nóminas: «**Nota para el instructor:**
    … verificar que el sitio de SharePoint del curso contenga las siguientes carpetas
    y archivos». La guía no afirma el material: lo deja a la vista de quien imparte,
    que es exactamente la resolución que la regla de tres niveles admite.
    """
    lab = (
        "## Material del curso\n\n"
        "> **Nota para el instructor:** Antes de iniciar la práctica, verificar que el "
        "sitio de SharePoint del curso contenga las siguientes carpetas y archivos en "
        "la biblioteca de documentos:\n"
        "> - `/Modulo1/Normativos/LFT_Vigente_Ficticio.pdf`\n"
        "> - `/Modulo1/Normativos/LSS_Cuotas_IMSS_2024_Ficticio.pdf`\n\n"
        "### Paso 1: Abrir el material\n```bash\nls /Modulo1/Normativos\n```\n"
    )
    informe = auditar_laboratorio(lab, _FUENTES)
    assert informe["violaciones"] == [], informe["violaciones"]
    marcados = {m["valor"] for m in informe["marcados"]}
    assert "/Modulo1/Normativos/LSS_Cuotas_IMSS_2024_Ficticio.pdf" in marcados


def test_una_nota_al_instructor_que_solo_declara_la_entrada_no_exime():
    """No basta con la nota: tiene que pedir **verificar la presencia**.

    Si la nota solo describe una entrada («el alumno debe descargar X»), el temario
    sigue sin declararla y el defecto es real. Sin esta condición, añadir «nota para
    el instructor» habría exonerado entradas de verdad.
    """
    lab = (
        "**Nota para el instructor:** el alumno trabajará con "
        "`Datos_Financieros_Q4.xlsx` durante la práctica.\n\n"
        "### Paso 1: Abrirlo\n```bash\nls\n```\n"
    )
    informe = auditar_laboratorio(lab, _FUENTES)
    b1 = [v for v in informe["violaciones"] if v["verificacion"] == "B1"]
    assert len(b1) == 1, informe["violaciones"]


def test_una_nota_al_instructor_en_otro_parrafo_no_exime():
    """El ámbito del marcador es el párrafo del referente, no la página."""
    lab = (
        "**Nota para el instructor:** verificar que el sitio contenga el material.\n\n"
        "Rellene la tabla con los resultados obtenidos.\n\n"
        "| Fichero |\n|---|\n| `Datos_Financieros_Q4.xlsx` |\n\n"
        "### Paso 1: Abrirlo\n```bash\nls\n```\n"
    )
    informe = auditar_laboratorio(lab, _FUENTES)
    b1 = [v for v in informe["violaciones"] if v["verificacion"] == "B1"]
    assert len(b1) == 1, informe["violaciones"]


def test_el_segundo_nombre_de_una_lista_de_ejemplos_no_es_entrada():
    """«(ej. 'X_BASE.xlsx', 'X_SOLUCION.xlsx')»: los dos son nomenclatura.

    La marca delante solo cubre el primer nombre. Medido el 23/10/2026 en
    `P11_Clasificacion_Demanda_SOLUCION.xlsx`, que A1 marcaba como entrada.
    """
    plan = {
        "special_considerations": [
            "Nomenclatura consistente (ej. 'P11_Clasificacion_Demanda_BASE.xlsx', "
            "'P11_Clasificacion_Demanda_SOLUCION.xlsx') para evitar confusiones."
        ]
    }
    informe = auditar_plan(plan, _FUENTES)
    assert informe["ok"], informe["violaciones"]


def test_un_endpoint_de_metricas_no_es_un_fichero_del_curso():
    """`/_prometheus/metrics` es una URL de servicio, no material del curso.

    Caso medido el 23/10/2026: A1 la marcaba como ruta en las notas de instalación
    de Couchbase.
    """
    plan = {
        "software_requirements": [
            {
                "name": "Couchbase",
                "installation_notes": "Couchbase expone métricas en formato Prometheus "
                "en /_prometheus/metrics.",
            }
        ]
    }
    informe = auditar_plan(plan, _FUENTES)
    assert informe["ok"], informe["violaciones"]


def test_un_ejercicio_entre_parentesis_no_es_un_ejemplo():
    """«(ejercicio 3: `datos.xlsx`)» es una entrada, no una ilustración.

    La marca tiene que ser «ej.» o «ej:»: el prefijo «ej» de «ejercicio» no vale.
    """
    plan = {
        "special_considerations": [
            "Ver el ejercicio 3: (`Datos_Privados_Q3.xlsx`) para el cálculo de indicadores."
        ]
    }
    informe = auditar_plan(plan, _FUENTES)
    valores = {v["valor"] for v in informe["violaciones"]}
    assert "Datos_Privados_Q3.xlsx" in valores, informe["violaciones"]


def test_un_listado_de_python_no_es_un_marcador():
    """`['pendientes']` exoneraba un fichero de salida real: el marcador va en
    mayúsculas, o el corchete **es** la marca. Medido sobre el corpus."""
    lab = (
        "### Paso 2: Exportar el reporte\n"
        "```python\n"
        "def exportar(reporte, archivo='data/reporte.txt'):\n"
        "    prioridades = ['pendientes', 'en curso']\n"
        "    return archivo\n"
        "```\n"
        "El alumno escribe data/reporte.txt con el resultado.\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["marcados"] == []
    assert not any(m["valor"] == "data/reporte.txt" for m in informe["marcados"])


def test_una_cerca_huerfana_no_saca_el_codigo_del_bloque():
    """Medido en `260527-COP-CHAT-IT-Priv`: el modelo abrió una cerca para citar el
    enunciado y no la cerró. La cerca con lenguaje siguiente no puede cerrarla, así
    que el script sigue dentro de un bloque y su ``C:\\users.txt`` no es entrada."""
    lab = (
        "### Paso 1: Revisar el script\n"
        "```\n"
        "Actúa como un experto en PowerShell.\n"
        "```powershell\n"
        '$users = Get-Content "C:\\users.txt"\n'
        "```\n"
        "Responde con el análisis completo.\n"
    )
    informe = auditar_laboratorio(lab, "")
    confianzas = {v["valor"]: v["confianza"] for v in informe["violaciones"]}
    assert confianzas["C:\\users.txt"] == "baja"


def test_para_confirmar_no_es_un_marcador():
    """«Ejecute esto para confirmar que…» es prosa corriente. El detector amplio la
    confundía con «a confirmar» y exoneraba el párrafo entero: 70 exoneraciones
    medidas sobre el corpus, casi todas por esta confusión."""
    lab = (
        "### Paso 2: Verificar\n"
        "Ejecute el siguiente comando para confirmar que el pipeline funciona:\n"
        "```bash\n"
        "python pipeline/run_pipeline.py\n"
        "```\n"
        "Abra el archivo `Datos_Financieros_Q4.xlsx` desde OneDrive y revise las hojas.\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["marcados"] == []
    confianzas = {v["valor"]: v["confianza"] for v in informe["violaciones"]}
    assert confianzas["Datos_Financieros_Q4.xlsx"] == "alta"


def test_una_plantilla_completar_no_exime():
    """`[COMPLETAR]` es un hueco que rellena el alumno, no una marca de confirmación
    para el instructor: no puede exonerar el fichero de la misma tabla."""
    lab = (
        "### Paso 4: Documentar\n"
        "Rellene la tabla de la plantilla:\n\n"
        "| Campo | Valor |\n"
        "|---|---|\n"
        "| Nombre del archivo | [COMPLETAR] |\n"
        "| Archivo de entrada | `informe_final.docx` |\n"
    )
    informe = auditar_laboratorio(lab, "")
    assert informe["marcados"] == []


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
        except Exception as exc:  # noqa: BLE001 - informe de test
            fallos.append((nombre, exc))
            print(f"FALLO  {nombre}: {exc}")
        else:
            print(f"ok     {nombre}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    sys.exit(1 if fallos else 0)
