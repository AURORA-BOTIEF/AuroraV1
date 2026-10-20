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
    auditar_laboratorio,
    auditar_plan,
    canonico,
    extraer_referentes,
    mensaje_de_correccion,
    referencias_a_labs_posteriores,
    referentes_creados,
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
):
    """Ejecuta el handler real del Writer con S3 y el modelo simulados.

    ``contenidos`` es la lista de respuestas del modelo simulado: la primera llamada
    devuelve la primera, la segunda la segunda, y así sucesivamente.
    ``existentes`` mapea ``lab_id`` → clave S3 de un laboratorio ya escrito (B3).
    """
    modulo = _cargar_modulo("strands_lab_writer", _CARPETA_WRITER)

    s3 = _S3Simulado(
        {"p/outline.yaml": _TEMARIO, "p/manual.txt": _MANUAL, **(objetos or {})}
    )
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
