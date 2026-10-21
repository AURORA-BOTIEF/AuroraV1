"""Trazabilidad de referentes de fichero (A1, B1, B2, B3c, B3p, B5 y B6).

Regla de tres niveles
---------------------
1. **Declarado** en una fuente (temario, manual, documentos): se afirma.
2. **Derivable / autocerrado**: el propio laboratorio lo crea antes de usarlo: se afirma.
3. **No declarado ni derivable**: no se afirma. Debe omitirse o marcarse con un
   marcador visible (``[POR CONFIRMAR]`` y similares).

El fallo que combate este módulo: un plan o un laboratorio que **nombra ficheros,
rutas o carpetas que ninguna fuente aporta**. Medición real (16/10/2026): el plan
generado contenía ``Demanda_Historica.xlsx``, ``C:\\Forecasting_Logistica\\`` y
``Practica1_MAPE_SKU.xlsx``, ausentes del temario y del manual.

Alcance de la fase 1
--------------------
Solo **referentes de fichero** (rutas y nombres con extensión). Las URL quedan
fuera a propósito: una URL inventada se combate comprobando que esté viva, no
buscándola en el temario, así que pertenece a la verificación C1. Las versiones y
las entidades con nombre llegan en la fase 3; de momento **B5** solo compara los
requisitos técnicos que el laboratorio exige con los que declara el plan, sin
juzgar si el plan acertó al declararlos (eso es A1/A2).

Alcance de la fase 2
--------------------
B1 solo veía un laboratorio aislado, así que no podía distinguir tres cosas:

- un fichero **creado en un laboratorio anterior** (legítimo) de uno inventado
  (verificación B3, cierre entre laboratorios de B1);
- una entrada que solo existe como **salida de un laboratorio posterior**
  (verificación B2, dependencia hacia delante);
- una mención de hoja de ruta («en el laboratorio 5 verás…»), que se registra
  pero no dispara reintento.

Para B3 basta con la unión de :func:`referentes_creados` de los laboratorios
anteriores. Para B2 se usan las salidas declaradas en el plan
(``expected_outcomes``) de los laboratorios posteriores: si el actual referencia
una de ellas sin que esté en las fuentes ni la cree él mismo, depende de algo que
aún no ha ocurrido.

Alcance de B3p (entregable producido)
-------------------------------------
El plan declara sus entregables en ``expected_outcomes``, casi siempre como prosa
(«Archivo ``data_transform.py`` con al menos 6 funciones»). B3p solo puede ser
determinista sobre los que **nombran un fichero**, y distingue tres estados:
creado, **mencionado sin creación reconocida** (hueco de extractor, baja) y **no
mencionado** (omisión, alta). Las alternativas («``deploy.sh`` o ``deploy.ps1``»)
son un solo requisito y los ficheros que el plan presenta como **entrada** del
curso no son entregables. Medición del 21/10/2026: 142 laboratorios con omisión;
por eso se registra y **no reintenta** salvo que se encienda ``DELIVERABLES_RETRY``.

Precisión (calibración del 16/10/2026)
--------------------------------------
Sobre 6.567 referentes marcados en el corpus real (164 proyectos, 1.244 labs),
una muestra de 80 revisada con contexto dio 78 falsos positivos. Las causas no
eran del curso sino del extractor, y se corrigen aquí:

1. **La extensión no estaba anclada** a fin de palabra: ``df.shape[0]`` producía
   el «fichero» ``df.sh``; ``matplotlib.pyplot`` producía ``matplotlib.py``.
2. **Identificadores punteados y claves de configuración** se trataban como
   fichas: ``math.log``, ``pyspark.sql``, ``parse.key=true``, ``transaction.state.log``.
3. **Rutas de sistema y de plataforma** (``/etc/*``, ``/dev/null``, ``/usr/*``)
   no son material del curso.
4. **Creación no detectada**: ``tee``, ``>``, ``BACKUP … TO DISK``, ``Out-File``,
   ``SPOOL``, y conjugaciones que faltaban (``guarde``, ``creado``, ``almacena``).
5. **Ausencia deliberada**: ``archivo_inexistente.json`` o «sin archivo X» son
   menciones de que el fichero **no** existe, no referentes que exigir.

Sin dependencias externas: solo biblioteca estándar.
"""

import json
import os
import re
import unicodedata

# --------------------------------------------------------------------------- #
# Patrones
# --------------------------------------------------------------------------- #

_EXTENSIONES = (
    "xlsx|xlsm|xls|csv|tsv|md|pbix|pbit|ps1|psm1|py|ipynb|json|txt|zip|rar|7z|"
    "png|jpg|jpeg|gif|svg|docx|doc|pptx|ppt|pdf|sql|sh|bat|cmd|yaml|yml|log|"
    "evtx|pem|pfx|cer|key|bak|db|sqlite|parquet|xml|html|css|js|ts"
)

# Corrección 1 (calibración 16/10/2026): la extensión debe terminar en límite de
# palabra. Sin este lookahead, ``df.shape`` casa ``df.sh`` y ``matplotlib.pyplot``
# casa ``matplotlib.py``: dos «ficheros» que no existen en el texto.
_FICHERO_RE = re.compile(
    r"(?<![\w.\-\\/])"
    r"(?P<nombre>[A-Za-z0-9_\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1]"
    r"[A-Za-z0-9_.\-\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1]*)"
    r"\.(?P<ext>" + _EXTENSIONES + r")"
    r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)

_RUTA_WINDOWS_RE = re.compile(r"(?<![\w])[A-Za-z]:\\[^\s`\"'<>|*?]+")
_RUTA_UNC_RE = re.compile(r"\\\\[^\s`\"'<>|*?]+")
_RUTA_UNIX_RE = re.compile(r"(?<![\w])/(?:[\w.\-]+/)+[\w.\-]+")

# Rutas **relativas** con directorio y extensión (``assets/mock.json``,
# ``src/app/components/product-list/product-list.component.ts``). Faltaban: la
# extracción solo veía nombres sueltos y rutas absolutas, así que el paso que crea
# el fichero (``cat > assets/mock.json``, ``ng generate component ...``) no existía
# para la comprobación y la mención posterior quedaba como referente inventado.
# Es la causa de la mayoría de los falsos positivos de alta confianza medidos el
# 20/10/2026.
_RUTA_RELATIVA_RE = re.compile(
    r"(?<![\w./\\-])"
    r"((?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z][A-Za-z0-9]{0,7})"
    r"(?![\w])"
)

# Las URL quedan FUERA a propósito de la fase 1. Una URL inventada se combate
# comprobando que esté viva (verificación C1), no buscándola en el temario. Si no se
# neutralizan antes de extraer, su cola («/support.microsoft.com/es-es/office/...»)
# se confunde con una ruta local y genera falsos positivos.
_URL_RE = re.compile(r"(?:https?|ftp|gs|s3|az)://[^\s`\"'<>\)\]]+")

# Los marcadores visibles ya expresan «dato no declarado»: no son un referente.
_MARCADOR_RE = re.compile(
    r"\[[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d10-9 _./:\-]{3,}\]|<[a-z_]{3,}>"
)

# Corrección 3 (calibración 16/10/2026): rutas del sistema operativo, de la
# plataforma o del contenedor. Existen en el entorno; no son material del curso y
# exigir que estén en el temario es un falso positivo (``/dev/null`` aparecía 240
# veces en el corpus). Se comparan sin distinguir mayúsculas y con ``\\`` → ``/``.
_PREFIJOS_EXCLUIDOS = (
    "/dev/", "/bin/", "/sbin/", "/etc/", "/usr/", "/lib/", "/lib64/", "/var/",
    "/proc/", "/sys/", "/opt/", "/root/", "/home/", "/mnt/", "/media/", "/srv/",
    "/tmp/", "/boot/", "/run/", "/data/data/", "/workspace/", "/dbfs/",
    "/filestore/", "/databricks-datasets/", "/volumes/",
    # Directorios de sistema de macOS y almacenamiento interno de una app Android.
    "/library/", "/system/", "/applications/", "/datastore/", "/shared_prefs/",
    "C:\\Users\\", "C:\\Windows\\", "C:\\Program Files", "C:\\ProgramData\\",
)

# Artefactos de una herramienta: lo que produce un build, un generador de código o
# un empaquetador no lo aporta el curso. Se comparan como segmento, no como prefijo,
# porque suelen aparecer al final de una ruta (``dist/main.js``).
_DIRECTORIOS_ARTEFACTO = (
    "/dist/", "/build/", "/out/", "/target/", "/node_modules/", "/.angular/",
    "/.next/", "/.nuxt/", "/coverage/", "/__pycache__/", "/.venv/", "/venv/",
    "/.gradle/", "/vendor/", "/obj/",
    # Andamiaje de un framework: el proyecto ya los trae (Laravel).
    "/resources/js/", "/resources/css/", "/resources/views/",
)

# Extensiones y sufijos que un generador añade al nombre del fichero.
_SUFIJOS_GENERADOS = (
    ".component.ts", ".service.ts", ".module.ts", ".spec.ts", ".d.ts",
    ".guard.ts", ".directive.ts", ".pipe.ts", ".resolver.ts", ".routes.ts",
    ".g.dart", ".generated.ts", ".designer.cs", ".pb.go", ".pb.ts",
    ".min.js", ".min.css", ".map",
    # Informes que produce una herramienta de medición (Lighthouse).
    ".report.json", ".report.html",
    # Un log o un temporal lo produce la ejecución, nunca lo aporta el curso.
    ".log", ".tmp",
)

# Bibliotecas que se referencian por su nombre de fichero (``plotly.js``,
# ``Node.js``). No son material que el alumno deba tener en disco.
_BIBLIOTECAS_JS = frozenset(
    {
        "plotly", "jquery", "bootstrap", "d3", "chart", "react", "vue",
        "angular", "lodash", "moment", "three", "leaflet", "axios", "node",
        "socket.io", "font-awesome",
    }
)

# Bundle con hash de contenido: ``main-a1b2c3d4.js``, ``styles-1a2b3c4d.css``.
_HASH_DE_BUILD_RE = re.compile(r"-[0-9a-f]{8,}\.[a-z0-9]+$", re.IGNORECASE)

# Ficheros de un chart de Helm, que crea ``helm create``.
_FICHEROS_DE_CHART = frozenset({"chart.yaml", "values.yaml", "chart.lock"})


def _es_artefacto_de_herramienta(valor: str) -> bool:
    """¿El referente lo produce una herramienta (build, generador, empaquetador)?"""
    v = valor.replace("\\", "/").lower()
    if "/../" in v or v.startswith("../"):
        return True
    # Las rutas relativas no empiezan por ``/``: se normalizan para que
    # ``dist/app.js`` y ``/dist/app.js`` caigan en la misma regla.
    if not v.startswith("/"):
        v = "/" + v
    if any(segmento in v for segmento in _DIRECTORIOS_ARTEFACTO):
        return True
    nombre = v.rsplit("/", 1)[-1]
    if _HASH_DE_BUILD_RE.search(nombre):
        return True
    if any(nombre.endswith(sufijo) for sufijo in _SUFIJOS_GENERADOS):
        return True
    if nombre.endswith((".js", ".css")) and nombre[:-3] in _BIBLIOTECAS_JS:
        return True
    return nombre in _FICHEROS_DE_CHART

# Rutas que no son del sistema de ficheros del alumno sino de una API o de un
# proveedor cloud (Elasticsearch, OpenAPI, Azure, SharePoint). Tampoco se exigen.
_SEGMENTOS_API = (
    "/subscriptions/", "/resourcegroups/", "/providers/", "/components/schemas/",
    "/_cat/", "/_cluster/", "/_search/", "/_create/", "/_refresh/", "/_doc",
    "/_bulk", "/_mapping", "/_template/", "/_alias/", "/_index/", "/sites/",
    "/settings/", "/api/",
    # Recursos de plataforma vistos en la muestra: CloudWatch (``/aws/lambda/...``),
    # Elasticsearch (``/_snapshot``, ``/_slm``, ``/_security``) y directorios de
    # trabajo de contenedor que no son del alumno.
    "/aws/", "/_snapshot/", "/_slm/", "/_security/", "/_ilm/", "/_ingest/",
    "/_nodes/",
    # Rutas de API de aplicaciones que el laboratorio levanta: Spring Actuator,
    # VAmPI (``/users/v1/…``) y Microsoft Graph (``/me/…``, ``/drive/…``).
    "/actuator/", "/users/v1/", "/me/", "/drive/",
    # Recurso REST de un catálogo de ejemplo (``/products/p-1`` en una aserción).
    "/products/",
)

# Corrección 2 (calibración 16/10/2026): espacios de nombres de código. Un
# ``math.log`` o un ``pyspark.sql`` son llamadas, no fichas que el alumno deba
# tener. Se comparan por el primer segmento, en minúsculas.
_NAMESPACIOS = frozenset(
    {
        "math", "json", "logging", "android", "kotlinx", "java", "process",
        "information_schema", "pyspark", "spark", "df", "pd", "np", "plt",
        "os", "sys", "re", "hashlib", "libs", "console", "wwv_flow",
        "matplotlib", "numpy", "pandas", "sklearn", "seaborn", "requests",
    }
)

# Metacaracteres de regex o de plantilla: una ruta real no los contiene.
_METACARACTERES = frozenset("[]^$+{}")

# Verbos que introducen (crean) un fichero. Si la primera aparición de un
# referente no declarado está en este contexto, el laboratorio lo crea: es válido.
#
# Se escriben en su forma NORMALIZADA (sin acentos) y se comparan por palabra
# completa. Comparar por subcadena haría que «general» activase «genera» y la
# comprobación quedaría vacua.
#
# Corrección 4 (calibración 16/10/2026): se añaden conjugaciones y vías de
# creación que la muestra evidenció ausentes («guarde», «creado», «almacena»,
# «conserva», ``tee``, ``Out-File``, ``SPOOL``, ``BACKUP … TO DISK``).
_VERBOS_CREACION = (
    "crea", "crear", "creas", "creara", "crearas", "creacion", "cree", "crees",
    "creado", "creada", "creados", "creadas",
    "guarda", "guardar", "guardaras", "guardar como", "guarde", "guardado",
    "guardada", "guardados", "guardadas",
    "genera", "generar", "generaras", "generacion", "genere", "generado",
    "generada", "generados", "generadas",
    "exporta", "exportar", "exportaras", "exportacion", "exporte", "exportado",
    "exportada",
    "descarga", "descargar", "descargaras", "descargue", "descargado",
    "descargada",
    "construye", "elabora", "escribe", "nombra", "renombra", "renombrar",
    "adjunta", "nuevo archivo", "nueva hoja", "crear una copia",
    "almacena", "almacenar", "almacene", "almacenado", "almacenada",
    "conserva", "conservar", "conserve", "conservado", "conservada",
    "salva", "salvar", "salve", "salvado", "salvada",
    "vuelca", "volcar", "volcado", "volcada",
    "respalda", "respaldar", "respaldo", "respalde", "backup",
    "redirige", "redirigir", "tee", "out-file", "spool", "dump",
    "deja", "deje", "dejar", "graba", "grabar", "grabe", "grabado",
)

_VERBOS_CREACION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in _VERBOS_CREACION) + r")\b"
)

# Corrección 5 (calibración 16/10/2026): frases que declaran que el fichero NO
# existe. ``archivo_inexistente.json`` es un fixture para probar el error; «sin
# archivo tailwind.config.js» describe una ausencia. No son referentes que exigir.
_MARCADORES_AUSENCIA = (
    "no existe", "si no existe", "sin archivo", "sin fichero", "si falta",
    "no encontrado", "no se encuentra", "inexistente", "no disponible",
    "no esta disponible", "archivo faltante", "fichero faltante",
)
_MARCADORES_AUSENCIA_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in _MARCADORES_AUSENCIA) + r")\b"
)

# Frases que declaran que un fichero lo **aporta el curso**. Es la clase que de
# verdad importa: si se inventa, el alumno no puede hacer el laboratorio. La
# calibración del 19/10/2026 mostró que casi todos los aciertos reales estaban en
# este contexto, y casi todos los falsos positivos en contextos de creación.
_MARCAS_ENTRADA = (
    "proporcionado por el instructor", "proporcionados por el instructor",
    "proporcionada por el instructor", "proporcionadas por el instructor",
    "aportado por el instructor", "aportados por el instructor",
    "compartido por el instructor", "compartidos por el instructor",
    "proporcionado por el curso", "proporcionados por el curso",
    "cargado en onedrive", "cargados en onedrive", "en tu onedrive",
    "almacenado en sharepoint", "almacenados en sharepoint", "en sharepoint",
    "archivo de fuente", "archivos de fuente", "archivo de entrada",
    "fichero de entrada", "datos de entrada", "documentos de laboratorio",
    "archivos de practica", "documentos fuente", "repositorio del curso",
    "se proporcionan", "se entregan",
    "descargado desde", "descargados desde", "descarga el archivo",
    "asegurate de tener", "verifica que tienes", "verifica que puedes ver",
    "debes tener", "el estudiante recibe", "el alumno recibe",
    "recibe un archivo", "recibira un archivo", "recibira el archivo",
    "disponible en el sitio", "deben estar en sharepoint",
    "get-content",
)

# Verbos de lectura inequívocos, **con su objeto**: «abra el archivo X» sí,
# «leer/escribir JSON» no. Se excluyen «cargar» y «usar»: aparecen tanto al leer
# un fichero existente como al volcar datos en uno nuevo.
_VERBOS_ENTRADA_RE = re.compile(
    r"\b(?:abre|abra|abrir|lee|lea|leer|importe|importa|importar)"
    r"\s+(?:(?:el|la|los|las)\s+)?[\w\\:.]"
)

# Verbos de **edición** de un fichero que ya existe en el proyecto. Medido en la
# muestra: «Abra el archivo de configuración de Vite `vite.config.js` … Reemplace
# su contenido» — el fichero lo crea el andamiaje, no lo aporta el curso. Un verbo
# de edición degrada la confianza; una marca explícita de entrada la mantiene.
_MARCAS_EDICION = (
    "reemplace", "reemplaza", "sustituya", "sustituye", "modifique", "modifica",
    "edite", "edita", "actualice", "actualiza", "agregue", "agrega", "pegue",
    "pegue el codigo", "sobrescriba",
)

# Marcas de creación que no son verbos: son **opciones o destinos**. Se buscan
# como subcadena sobre el contexto normalizado (minúsculas, ``_`` → espacio,
# ``\`` → ``/``) porque llevan guiones o dos puntos que un ``\b`` no delimita bien.
#
# Medido en la muestra: ``--log log_final.html``, ``--output output_pipeline.xml``,
# ``-OutFile ...txt``, ``-DestinationPath "C:\kubectl-plugins\"``,
# ``BACKUP … TO DISK = N'...bak'``, ``cat > fichero`` y ``… > fichero``.
_MARCAS_CREACION = (
    "--output", "--log", "--report", "--outputdir",
    "-outfile", "-destinationpath", "spool ", "to disk",
    "cat >", "cat >>", "| tee", "expand-archive", "invoke-webrequest",
    "savefig",
    # Salidas de datos (pandas / notebooks).
    "to csv", "to excel", "to parquet", "to json", "to pickle",
    "write text", "write bytes",
    # Creación de directorios y copias.
    "mkdir", "makedirs", "new-item", "touch ", "adb pull", "docker cp",
    # El laboratorio pide **borrar** versiones o restos: no son entradas.
    "elimina", "elimine", "eliminar", "borra", "borre", "borrar",
    # Bloque de «salida esperada»: un listado de lo que el laboratorio produce.
    # Medido: ``Salida esperada: - 00000000000000000000.json …`` y ``Verás una
    # salida similar a: main.js … polyfills.js``.
    "salida esperada", "resultado esperado", "salidas esperadas",
    "resultados esperados", "deberias ver", "deberia ver", "salida similar",
    # Herramientas que escriben un fichero de salida con una opción concreta.
    "-out ", "-outform", "se llamara", "se guardara como", "guarda el resultado",
    # Entregables declarados como tales.
    "el producto final", "archivo generado", "archivos generados",
    "generado en este laboratorio", "generados en este laboratorio",
    # Capturas de pantalla: el alumno las produce, no las recibe.
    "captura de pantalla", "capturas de pantalla", "screenshot", "pantallazo",
    "tome una captura", "toma una captura", "guarda la captura",
    # Retro-referencia de creación en pasado: «la copia que creaste en la
    # configuración inicial», «el informe que generaste en el paso 2». El fichero
    # existe porque un paso anterior (de este curso) lo produjo.
    "que creaste", "creaste en", "creaste el", "creaste la", "creaste un",
    "has creado", "que has creado", "generaste", "has generado", "que generaste",
    "creado en el paso", "creado en el laboratorio", "creado anteriormente",
    "se creo en", "que creo el", "que creo la", "definiste", "has definido",
    "que definiste",
)

# Andamiaje: si el paso ejecuta un generador, los ficheros que menciona los crea
# la herramienta. Medido en la muestra: proyectos Angular, Vue, Spring y .NET.
_MARCAS_ANDAMIAJE = (
    "ng new", "ng generate", "ng add", "npm create", "npx create",
    "npm init", "yarn create", "pnpm create", "dotnet new", "mvn archetype",
    "django-admin startproject", "rails new", "helm create", "kubeadm init",
    "git clone", "cookiecutter", "vue create", "nest new",
    "create-react-app", "express-generator",
)

# Líneas que **no describen una entrada**:
#  - árbol de directorios de entregables (``├──``, ``└──``, ``│``);
#  - importaciones, ``require``, ``href``/``src`` e ``@import`` (ficheros del proyecto);
#  - citas de una fuente externa (``[Fuente 1: …]``).
_LINEA_ARBOL_RE = re.compile(r"[├└│]")
_LINEA_IMPORT_RE = re.compile(
    r"(?:\bimport\b|\brequire\s*\(|\bfrom\s+['\"]|\bhref\s*=|\bsrc\s*=|@import\b|#include\b"
    r"|\bResource\s+\.\./|\bLibrary\s+\w)"
)
_LINEA_CITA_RE = re.compile(r"\[(?:fuente|referencia|source)\b", re.IGNORECASE)

# Rótulos de un bloque de **salida esperada**: lo que hay dentro lo produce el
# laboratorio o la herramienta. Medido: ``**Salida esperada:** - 0000…json``
# (logs Delta) y ``Verás una salida similar a: main.js, polyfills.js`` (build de
# Angular). El rótulo está en la línea anterior a la verja de apertura del bloque.
_MARCADORES_SALIDA = (
    "salida esperada", "salidas esperadas", "resultado esperado",
    "resultados esperados", "salida similar", "deberias ver", "deberia ver",
    "veras una salida", "la salida es",
)

# Clave de configuración al inicio de la línea: ``xpack.security.ssl.key: certs/…``
# o ``dashboardproviders.yaml:``. Se detecta en la extracción, no en la auditoría.
_CLAVE_YAML_RE = re.compile(r"\s*:")

# Valor de una clave de configuración: ``ssl.key: certs/es01.key``. La parte de la
# línea anterior al valor es solo una clave que termina en dos puntos.
_CLAVE_VALOR_RE = re.compile(r"^\s*[\w.\-]+\s*:\s*$")

# Destino de una redirección de shell: ``… > archivo``, ``… >> archivo``,
# ``… > "archivo"``, ``… > ~/archivo`` (la ruta empieza tras ``~/``).
_REDIRECCION_RE = re.compile(r">\s*[\"']?~?$")

# Nombre puesto como **ejemplo** justo antes del referente: «(ej: tests/Login.robot)»,
# «normalmente `src/router/index.ts`». Es ilustrativo: no afirma que el curso lo
# aporte ni que el alumno lo tenga. Se mira solo el texto inmediatamente anterior,
# para no confundirlo con un «abra X» del mismo paso (que sí es una entrada).
_EJEMPLO_PREVIO_RE = re.compile(
    r"(?:\bej\s*\.?\s*(?::|,)?\s*"
    r"|\bejemplo\s*(?::|,)?\s*"
    r"|\bp\s*\.\s*ej\s*\.?\s*(?::|,)?\s*"
    r"|\be\s*\.\s*g\s*\.?\s*(?::|,)?\s*"
    r"|\bnormalmente\s+"
    r"|\bt[ií]picamente\s+"
    r"|\bsuele(?:n)? ser\s+"
    r"|\bdel tipo\s+)(?:[\"'`(«]\s*)*$",
    re.IGNORECASE,
)

# Un ejemplo puede enunciar **varias alternativas**: «el archivo de rutas,
# normalmente `src/router/index.js` o `src/router/index.ts`». La segunda no lleva
# la marca delante, así que se busca la marca hasta 120 caracteres antes y se
# exige que entre ambas solo haya conectores, comillas y el nombre anterior. Si
# aparece un verbo de entrada («por ejemplo, abra el archivo X»), manda el verbo.
_EJEMPLO_LEJANO_RE = re.compile(
    r"(?:\bej\s*\.?\s*(?::|,)|"
    r"\bejemplo\s*(?::|,)|"
    r"\bp\s*\.\s*ej\s*\.?\s*(?::|,)|"
    r"\be\s*\.\s*g\s*\.?\s*(?::|,)|"
    r"\bnormalmente|"
    r"\bt[ií]picamente|"
    r"\bsuele(?:n)? ser|"
    r"\bdel tipo)\s*",
    re.IGNORECASE,
)
_SOLO_CONECTORES_RE = re.compile(r"[\w./\\\-`\"'«»(),;:\s]*")

_VENTANA_CONTEXTO = 260

# Referencias a un laboratorio por número, para la parte débil de B2: una mención
# de hoja de ruta («en el laboratorio 5 verás…») se registra aparte, pero no cuenta
# como violación ni dispara reintento. Solo se comparan unidades que son
# laboratorios: un «módulo 2» no se corresponde con la posición de un laboratorio.
_NUMEROS_PALABRA = {
    "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
}
_NUMEROS_ROMANOS = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
    "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
}
_UNIDADES_LAB = "laboratorio|lab|practica|ejercicio"
_UNIDAD_NUMERO_RE = re.compile(
    r"\b(?:" + _UNIDADES_LAB + r")"
    r"\s*(?:n[umero.º]*\s*)?"
    r"(\d{1,2}|" + "|".join(_NUMEROS_PALABRA) + r"|[ivx]{1,4})"
    r"(?![\w-]|\s*-\s*\d)"
)
_UNIDAD_SIGUIENTE_RE = re.compile(
    r"\b(?:(?:siguiente|proximo|proxima|posterior|posteriores)\s+"
    r"(?:" + _UNIDADES_LAB + r")"
    r"|(?:" + _UNIDADES_LAB + r")\s+"
    r"(?:siguiente|proximo|proxima|posterior|posteriores))\b"
)


# --------------------------------------------------------------------------- #
# Normalización
# --------------------------------------------------------------------------- #

def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con separadores unificados (``\\`` y ``_`` → espacio)."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower().replace("\\", "/")
    texto = re.sub(r"[\s_]+", " ", texto)
    return texto


def canonico(referente: str) -> str:
    """Forma canónica de un referente para comparar sin falsos negativos.

    A diferencia de :func:`normalizar`, aquí los ``_`` y los ``.`` **se conservan**:
    ``Demanda_Historica.xlsx`` no debe confundirse con «demanda histórica».
    """
    if not referente:
        return ""
    texto = unicodedata.normalize("NFD", str(referente))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower().replace("\\", "/").strip(" \t.`\"'()[],;:*")
    return texto


def quitar_marcadores(texto: str) -> str:
    """Sustituye los marcadores visibles por espacios (misma longitud)."""
    return _MARCADOR_RE.sub(lambda m: " " * len(m.group(0)), texto or "")


# --------------------------------------------------------------------------- #
# Extracción
# --------------------------------------------------------------------------- #

def _es_ruta_excluida(valor: str) -> bool:
    """Ruta del sistema, de la plataforma o de una API: no es material del curso."""
    v = valor.replace("\\", "/").lower()
    if any(v.startswith(p.replace("\\", "/").lower()) for p in _PREFIJOS_EXCLUIDOS):
        return True
    return any(marca in v for marca in _SEGMENTOS_API)


def _es_codigo(valor: str, texto: str, fin: int) -> bool:
    """¿El candidato es código (API, espacio de nombres o clave) y no un fichero?

    La calibración del 16/10/2026 mostró que la mayoría de lo que A1/B1 marcaban
    eran expresiones de código: ``df.shape`` (como ``df.sh``), ``math.log``,
    ``transaction.state.log``, ``parse.key=true``. No son fichas que el alumno
    necesite, así que se descartan en la extracción.
    """
    if "/" in valor or "\\" in valor:
        return False

    segmentos = valor.split(".")

    # Llamada o asignación: ``r.json()``, ``parse.key=true``.
    despues = texto[fin:fin + 1]
    if despues in ("(", "="):
        return True
    # Continuación de una cadena punteada (``transaction.state.log.replication``),
    # pero NO el punto de fin de frase: ``Practica1_MAPE_SKU.xlsx.`` sigue siendo
    # un fichero. Solo cuenta si tras el punto hay otro segmento.
    if despues == "." and re.match(r"[A-Za-z0-9_]", texto[fin + 1:fin + 2] or ""):
        return True

    # Espacio de nombres de código conocido en el primer segmento. No se usa una
    # regla genérica de «3+ segmentos» a propósito: eliminaría ficheros reales como
    # ``tailwind.config.js``, ``next.config.js`` o ``app.module.ts``.
    return segmentos[0].lower() in _NAMESPACIOS


def _es_ejemplo(texto: str, inicio: int) -> bool:
    """¿El nombre está puesto como ejemplo (``ej: …``, ``normalmente …``)?"""
    if _EJEMPLO_PREVIO_RE.search(texto[max(0, inicio - 40):inicio]):
        return True
    largo = texto[max(0, inicio - 120):inicio]
    marca = _EJEMPLO_LEJANO_RE.search(largo)
    if not marca:
        return False
    entre = largo[marca.end():]
    if _VERBOS_ENTRADA_RE.search(entre):
        return False
    return bool(_SOLO_CONECTORES_RE.fullmatch(entre))


def extraer_referentes(texto: str, deduplicar: bool = True) -> list[dict]:
    """Referentes de fichero de ``texto``, en orden de aparición.

    Cada elemento: ``{"tipo": "ruta"|"fichero", "valor": str, "inicio": int}``.

    Args:
        texto: texto donde buscar.
        deduplicar: si es ``True`` (por defecto) devuelve solo la **primera**
            aparición de cada referente. La auditoría de laboratorio pide
            ``False``: un fichero mencionado primero en una tabla y creado más
            tarde debe verse en su contexto de creación, no en el primero.
    """
    if not texto:
        return []
    # Se neutralizan primero los marcadores (ya expresan «sin confirmar») y las URL
    # (fuera de alcance): ambos con espacios, para no desplazar los índices.
    limpio = _URL_RE.sub(lambda m: " " * len(m.group(0)), quitar_marcadores(texto))

    hallados: list[dict] = []
    vistos: set[str] = set()
    posiciones: set[tuple[str, int]] = set()

    def anadir(tipo: str, valor: str, inicio: int, fin: int) -> None:
        # La puntuación de la frase no forma parte del referente:
        # «... en C:\Datos\.» no es la ruta «C:\Datos\.».
        valor = valor.rstrip(".,;:")
        clave = canonico(valor)
        if not clave:
            return
        if (valor, inicio) in posiciones:
            return
        if deduplicar and clave in vistos:
            return
        # Metacaracteres de regex/plantilla: no es una ruta real.
        if any(c in valor for c in _METACARACTERES):
            return
        # Artefacto de una herramienta (build, generador, biblioteca): no es una
        # entrada que el curso deba aportar.
        if _es_artefacto_de_herramienta(valor):
            return
        # Nombre citado como ejemplo («ej: …», «normalmente …»): ilustra, no exige.
        if _es_ejemplo(limpio, inicio):
            return
        if tipo == "ruta":
            # Secuencias de escape literales (``\\nVariance`` dentro de una cadena
            # Python) que la regla de rutas UNC confunde con una ruta.
            if valor.startswith("\\\\") and valor[2:3] in ("n", "r", "t"):
                return
            if _es_ruta_excluida(valor):
                return
        else:
            if _es_codigo(valor, limpio, fin):
                return
            # Clave de configuración al inicio de línea (``xpack.security…key:``).
            inicio_linea = limpio.rfind("\n", 0, inicio) + 1
            if not limpio[inicio_linea:inicio].strip():
                if _CLAVE_YAML_RE.match(limpio[fin:fin + 3] or ""):
                    return
        if tipo == "ruta":
            # Valor de una clave YAML/INI (``ssl.key: certs/es01.key``): es
            # configuración del proyecto, no un fichero que el curso aporte.
            inicio_linea = limpio.rfind("\n", 0, inicio) + 1
            if _CLAVE_VALOR_RE.match(limpio[inicio_linea:inicio]):
                return
        posiciones.add((valor, inicio))
        vistos.add(clave)
        hallados.append({"tipo": tipo, "valor": valor, "inicio": inicio})

    for patron, tipo in (
        (_RUTA_WINDOWS_RE, "ruta"),
        (_RUTA_UNC_RE, "ruta"),
        (_RUTA_UNIX_RE, "ruta"),
        (_RUTA_RELATIVA_RE, "ruta"),
    ):
        for m in patron.finditer(limpio):
            anadir(tipo, m.group(0), m.start(), m.end())

    for m in _FICHERO_RE.finditer(limpio):
        anadir("fichero", m.group(0), m.start(), m.end())

    hallados.sort(key=lambda r: r["inicio"])
    return hallados


def claves_de(referente: dict) -> list[str]:
    """Claves con las que se considera declarado un referente.

    Un fichero se declara por su nombre completo. Una ruta se declara por la ruta
    completa **o** por el nombre de su último componente (el directorio puede
    estar descrito aparte).
    """
    valor = referente["valor"]
    claves = [canonico(valor)]
    if referente["tipo"] == "ruta":
        nombre = os.path.basename(valor.replace("\\", "/").rstrip("/"))
        if nombre:
            claves.append(canonico(nombre))
    return [c for c in claves if c]


def referentes_creados(texto: str) -> set[str]:
    """Claves de los referentes que el texto **crea**, no los que consume.

    Es el contexto que le faltaba a B1 entre laboratorios: un fichero creado en un
    laboratorio anterior es legítimo en el actual. Solo cuenta la creación
    explícita (verbo, opción de salida, redirección, andamiaje); una mención suelta
    no legitima nada.
    """
    creados: set[str] = set()
    for referente in extraer_referentes(texto or "", deduplicar=False):
        if _es_creacion(texto, referente):
            creados.update(claves_de(referente))
    return creados


def salidas_de_laboratorios(plan: dict) -> dict[str, list[str]]:
    """Entregables que el plan declara producir en cada laboratorio.

    ``expected_outcomes`` es una salida **por definición**: A1 lo marca siempre con
    confianza baja porque no es una entrada aportada por el curso. Aquí se usa para
    lo contrario: si un laboratorio anterior lo referencia, está usando como entrada
    algo que todavía no existe (verificación B2).
    """
    salidas: dict[str, list[str]] = {}
    for laboratorio in (plan or {}).get("lab_plans") or []:
        lab_id = laboratorio.get("lab_id")
        if not lab_id:
            continue
        valores: list[str] = []
        esperados = laboratorio.get("expected_outcomes") or []
        if isinstance(esperados, str):
            esperados = [esperados]
        for texto in esperados:
            if isinstance(texto, str):
                valores.extend(r["valor"] for r in extraer_referentes(texto))
        salidas[lab_id] = valores
    return salidas


def _numero_de(token: str) -> int:
    """Número de laboratorio a partir de un dígito, una palabra o un romano."""
    token = (token or "").strip().lower()
    if token.isdigit():
        return int(token)
    if token in _NUMEROS_PALABRA:
        return _NUMEROS_PALABRA[token]
    return _NUMEROS_ROMANOS.get(token, 0)


def referencias_a_labs_posteriores(
    texto: str, posicion: int, orden: list[str]
) -> list[dict]:
    """Menciones explícitas a un laboratorio **posterior** al actual.

    Es la forma débil de B2: una hoja de ruta («en el laboratorio 5 verás…») no es
    una dependencia. Por eso se devuelve **aparte** de las violaciones: el Writer la
    deja en el informe, pero no cuenta para ``ok`` ni dispara reintento. La forma
    fuerte (usar como entrada una salida de un laboratorio posterior) la resuelve
    :func:`auditar_laboratorio` con ``salidas_posteriores``.

    Args:
        texto: markdown del laboratorio.
        posicion: índice **0-based** del laboratorio actual dentro de ``orden``.
        orden: identificadores de laboratorio en el orden del plan.
    """
    if not texto or not orden:
        return []
    actual = posicion + 1
    normalizado = normalizar(texto)
    hallados: list[dict] = []
    vistos: set[str] = set()

    def anadir(valor: str, destino: str) -> None:
        clave = valor.strip().lower()
        if not clave or clave in vistos:
            return
        vistos.add(clave)
        hallados.append(
            {
                "valor": valor.strip(),
                "laboratorio_posterior": destino,
                "confianza": "baja",
            }
        )

    for coincidencia in _UNIDAD_NUMERO_RE.finditer(normalizado):
        numero = _numero_de(coincidencia.group(1))
        if not numero or numero <= actual or numero > len(orden):
            continue
        anadir(coincidencia.group(0), orden[numero - 1])

    if posicion + 1 < len(orden):
        for coincidencia in _UNIDAD_SIGUIENTE_RE.finditer(normalizado):
            anadir(coincidencia.group(0), orden[posicion + 1])

    return hallados


# --------------------------------------------------------------------------- #
# Auditoría del plan (A1)
# --------------------------------------------------------------------------- #

_CAMPOS_IGNORADOS = ("generated_at", "referential_integrity")


def _textos_del_plan(plan: dict) -> list[tuple[str, str]]:
    """Pares ``(campo, texto)`` del plan, para saber dónde está cada referente."""
    salida: list[tuple[str, str]] = []

    def recorrer(objeto, camino: str) -> None:
        if isinstance(objeto, dict):
            for clave, valor in objeto.items():
                if clave in _CAMPOS_IGNORADOS:
                    continue
                recorrer(valor, f"{camino}.{clave}" if camino else str(clave))
        elif isinstance(objeto, list):
            for i, valor in enumerate(objeto):
                recorrer(valor, f"{camino}[{i}]")
        elif isinstance(objeto, str) and objeto.strip():
            salida.append((camino, objeto))

    recorrer(plan, "")
    return salida


def auditar_plan(plan: dict, fuentes: str) -> dict:
    """A1: todo referente de fichero del plan debe estar en las fuentes.

    Args:
        plan: plan maestro ya construido.
        fuentes: texto de temario + manual + documentos, concatenado.

    Returns:
        ``{"total": n, "violaciones": [{"campo", "valor"}], "ok": bool}``
    """
    fuentes_norm = canonico(fuentes)
    violaciones: list[dict] = []
    vistos: set[str] = set()
    total = 0

    for campo, texto in _textos_del_plan(plan or {}):
        for referente in extraer_referentes(texto):
            total += 1
            claves = claves_de(referente)
            if any(clave and clave in fuentes_norm for clave in claves):
                continue
            if referente["valor"] in vistos:
                continue
            vistos.add(referente["valor"])
            # ``expected_outcomes`` describe lo que el estudiante **produce**: es una
            # salida por definición, no una entrada aportada por el curso. Se registra
            # siempre como baja confianza para que nunca dispare un reintento.
            es_salida_declarada = "expected_outcomes" in campo
            confianza = "baja" if es_salida_declarada else (
                "alta" if _es_entrada(texto, referente) else "baja"
            )
            violaciones.append(
                {
                    "campo": campo,
                    "valor": referente["valor"],
                    "confianza": confianza,
                }
            )

    return {"total": total, "violaciones": violaciones, "ok": not violaciones}


# --------------------------------------------------------------------------- #
# Auditoría de un laboratorio (B1)
# --------------------------------------------------------------------------- #

def _limites_de_paso(texto: str, posicion: int) -> tuple[int, int]:
    """Inicio y fin del bloque que contiene ``posicion``.

    El bloque es el «paso» (delimitado por encabezados) o el párrafo.
    """
    inicio = texto.rfind("\n###", 0, posicion)
    inicio = 0 if inicio == -1 else inicio
    fin = texto.find("\n###", posicion)
    fin = len(texto) if fin == -1 else fin
    return inicio, fin


def _linea_de(texto: str, posicion: int) -> str:
    """Línea que contiene ``posicion`` (sin el salto de línea)."""
    inicio = texto.rfind("\n", 0, posicion) + 1
    fin = texto.find("\n", posicion)
    fin = len(texto) if fin == -1 else fin
    return texto[inicio:fin]


def _contexto_de(texto: str, referente: dict) -> str:
    """Contexto normalizado: encabezado del paso + ventana alrededor del referente.

    La ventana se recorta a los límites del paso. Sin ese recorte, un «guarde el
    resultado» del paso siguiente exculpaba un «abra el archivo» del paso actual, y
    la comprobación se volvía vacua justo en los laboratorios con varios pasos.
    """
    inicio_paso, fin_paso = _limites_de_paso(texto, referente["inicio"])
    fin_encabezado = texto.find("\n", inicio_paso)
    if fin_encabezado == -1:
        fin_encabezado = len(texto)
    encabezado = texto[inicio_paso:fin_encabezado]

    desde = max(inicio_paso, referente["inicio"] - _VENTANA_CONTEXTO)
    hasta = min(fin_paso, referente["inicio"] + len(referente["valor"]) + _VENTANA_CONTEXTO)
    return normalizar(encabezado + " " + texto[desde:hasta])


def _en_bloque_de_salida(texto: str, posicion: int) -> bool:
    """¿El referente está dentro de un bloque de código rotulado «salida esperada»?"""
    apertura = texto.rfind("```", 0, posicion)
    if apertura == -1:
        return False
    linea_previa = _linea_de(texto, max(0, apertura - 1))
    return any(marca in normalizar(linea_previa) for marca in _MARCADORES_SALIDA)


def _es_creacion(texto: str, referente: dict) -> bool:
    """¿La aparición del referente está en un contexto de creación o de ausencia?

    El contexto es deliberadamente estrecho: la línea de encabezado del paso (que
    declara la intención, p. ej. «### Paso 3: Crear un informe») más una ventana
    alrededor del referente. **No** se acepta cualquier verbo presente en el
    cuerpo del paso: si se aceptase, un paso que dice «crearás un informe»
    blanquearía todos los ficheros que ese paso inventa, y la comprobación sería
    vacua.
    """
    contexto = _contexto_de(texto, referente)
    if _VERBOS_CREACION_RE.search(contexto):
        return True
    if any(marca in contexto for marca in _MARCAS_CREACION):
        return True
    if any(marca in contexto for marca in _MARCAS_ANDAMIAJE):
        return True
    # Líneas que no describen una entrada: árbol de entregables, importación de un
    # fichero del propio proyecto, o cita de una fuente externa.
    linea = _linea_de(texto, referente["inicio"])
    if _LINEA_ARBOL_RE.search(linea):
        return True
    if _LINEA_IMPORT_RE.search(linea):
        return True
    if _LINEA_CITA_RE.search(linea):
        return True
    if _en_bloque_de_salida(texto, referente["inicio"]):
        return True
    # Destino de una redirección de shell. Se mira el texto CRUDO inmediatamente
    # anterior: ``cat > fichero``, ``echo … > fichero``, ``> "fichero"``.
    antes = texto[max(0, referente["inicio"] - 8):referente["inicio"]]
    if _REDIRECCION_RE.search(antes):
        return True
    # Un bloque que abre con ``#!`` define un script, y su nombre en el comentario
    # de cabecera (``#!/bin/bash`` / ``# monitor_rebalance.sh``) es el del fichero
    # que el propio laboratorio crea.
    inicio_linea = texto.rfind("\n", 0, referente["inicio"]) + 1
    linea = _linea_de(texto, referente["inicio"])
    if linea.lstrip().startswith("#") and inicio_linea > 1:
        anterior = _linea_de(texto, inicio_linea - 2)
        if anterior.lstrip().startswith("#!"):
            return True
    # Corrección 5: la mención de ausencia también exime (el fichero no debe existir).
    return bool(_MARCADORES_AUSENCIA_RE.search(contexto))


def _es_entrada(texto: str, referente: dict) -> bool:
    """¿El contexto presenta el fichero como **aportado por el curso**?

    Es la confianza que autoriza un reintento correctivo. Un fichero que el
    laboratorio crea, que pertenece al proyecto o que es una salida esperada no
    debe provocar un reintento (la calibración lo midió: ~90 % de los marcados
    eran de ese tipo). Un fichero que el curso dice **proporcionar** y que no está
    en el temario sí: el alumno no lo tendrá.
    """
    contexto = _contexto_de(texto, referente)
    if any(marca in contexto for marca in _MARCAS_ENTRADA):
        return True
    if any(marca in contexto for marca in _MARCAS_EDICION):
        return False
    return bool(_VERBOS_ENTRADA_RE.search(contexto))


# --------------------------------------------------------------------------- #
# Duración declarada contra trabajo real (B6)
# --------------------------------------------------------------------------- #

_PASO_RE = re.compile(r"^###\s+(?:Paso|Step)\s+\d+.*$", re.MULTILINE)
_BLOQUE_RE = re.compile(r"```([\w+-]*)\n(.*?)```", re.DOTALL)
_DURACION_LAB_RE = re.compile(
    r"(?:\|\s*(?:Duraci[oó]n|Duration)\s*\|\s*(\d+)\s*(?:minutos?|minutes?|min)\b"
    r"|(?:Duraci[oó]n|Duration)\s*:\s*\**\s*(\d+)\s*(?:minutos?|minutes?|min)\b)",
    re.IGNORECASE,
)

_LENGUAJES_SHELL = frozenset(
    {"bash", "sh", "shell", "powershell", "ps1", "cmd", "bat", "zsh", "console", "terminal"}
)
# Bloques que el alumno **ejecuta o escribe**. Los de salida (``text``, ``log``,
# ``diff``, ``csv``) no cuestan tiempo de acción: contarlos inflaba la carga.
_LENGUAJES_ACCION = _LENGUAJES_SHELL | frozenset(
    {
        "python", "py", "javascript", "js", "typescript", "ts", "java", "csharp",
        "cs", "go", "sql", "yaml", "yml", "json", "xml", "html", "css", "vue",
        "php", "ruby", "rb", "kotlin", "swift", "dockerfile", "ini", "toml",
        "properties", "tf", "hcl", "psql", "plsql",
    }
)

# Umbrales medidos sobre el corpus (1.018 laboratorios con duración en el plan):
# p05 de minutos por paso con acción = 2,5; p05 de minutos por bloque = 0,4. Se
# marca solo lo que incumple **las dos** condiciones: menos de 2 minutos por paso
# con acción y menos de 45 segundos por bloque. Medido: 15 casos en 1.018, todos
# imposibles (instalar Kali en 15 min; `ng new` + 77 líneas de CSS en 12 min).
_MINUTOS_POR_PASO_ACCION = 2.0
_MINUTOS_POR_BLOQUE = 0.75
_PASOS_ACCION_MINIMOS = 3


def duracion_declarada(laboratorio_md: str) -> int | None:
    """Minutos que declara el propio laboratorio en sus metadatos, si los trae."""
    coincidencia = _DURACION_LAB_RE.search(laboratorio_md or "")
    if not coincidencia:
        return None
    valor = coincidencia.group(1) or coincidencia.group(2)
    return int(valor) if valor else None


def carga_de_laboratorio(laboratorio_md: str) -> dict:
    """Pasos y bloques de acción del laboratorio escrito.

    Un **paso con acción** es un ``### Paso`` que contiene al menos un bloque de
    shell o de un lenguaje que el alumno escribe. Los bloques de salida no cuentan.
    """
    cortes = [m.start() for m in _PASO_RE.finditer(laboratorio_md or "")]
    if not cortes:
        return {"pasos": 0, "con_accion": 0, "shell": 0, "codigo": 0, "bloques": 0}
    cortes.append(len(laboratorio_md))
    shell = codigo = con_accion = 0
    for i in range(len(cortes) - 1):
        tramo = laboratorio_md[cortes[i]:cortes[i + 1]]
        tiene = False
        for lenguaje, _cuerpo in _BLOQUE_RE.findall(tramo):
            lenguaje = (lenguaje or "").strip().lower()
            if lenguaje in _LENGUAJES_SHELL:
                shell += 1
                tiene = True
            elif lenguaje in _LENGUAJES_ACCION:
                codigo += 1
                tiene = True
        if tiene:
            con_accion += 1
    return {
        "pasos": len(cortes) - 1,
        "con_accion": con_accion,
        "shell": shell,
        "codigo": codigo,
        "bloques": shell + codigo,
    }


def auditar_duracion(laboratorio_md: str, duracion_min) -> dict:
    """B6: ¿la duración declarada es compatible con el trabajo que pide el laboratorio?

    Solo se pronuncia cuando hay duración y al menos tres pasos con acción: por
    debajo de eso, la proporción no significa nada. Es determinista y se calcula
    sobre el laboratorio escrito, que es donde existen los pasos.
    """
    unidades = carga_de_laboratorio(laboratorio_md)
    try:
        duracion = int(duracion_min or 0)
    except (TypeError, ValueError):
        duracion = 0
    informe = {"ok": True, "duracion": duracion, "motivo": "", **unidades}
    if duracion <= 0:
        informe["motivo"] = "sin duración declarada"
        return informe
    if unidades["con_accion"] < _PASOS_ACCION_MINIMOS or unidades["bloques"] < 1:
        informe["motivo"] = "sin pasos de acción suficientes para comparar"
        return informe
    minutos_paso = duracion / unidades["con_accion"]
    minutos_bloque = duracion / unidades["bloques"]
    informe["minutos_por_paso"] = round(minutos_paso, 2)
    informe["minutos_por_bloque"] = round(minutos_bloque, 2)
    if (
        minutos_paso < _MINUTOS_POR_PASO_ACCION
        and minutos_bloque < _MINUTOS_POR_BLOQUE
    ):
        informe["ok"] = False
        informe["motivo"] = (
            f"{duracion} minutos para {unidades['con_accion']} pasos con accion y "
            f"{unidades['bloques']} bloques de comando o codigo "
            f"({minutos_paso:.1f} min/paso, {minutos_bloque:.2f} min/bloque)"
        )
    return informe


# --------------------------------------------------------------------------- #
# Requisitos técnicos del laboratorio contra los del plan (B5)
# --------------------------------------------------------------------------- #

_PROSA_RE = re.compile(r"```.*?```", re.DOTALL)

_OS_RE = re.compile(
    r"\b(Windows(?: Server)?|macOS|Apple iOS|Ubuntu|Debian|CentOS|RHEL|Fedora|Rocky|Android|Linux)\b",
    re.IGNORECASE,
)
_OS_PLAN_RE = re.compile(
    r"\b(windows(?: server)?|macos|apple ios|ubuntu|debian|centos|rhel|"
    r"red hat enterprise linux|fedora|rocky|android|linux)\b"
)
# Familias: pedir Ubuntu cuando el plan declara Linux no es contradecirlo, y
# Windows Server es Windows. ``IOS`` a secas se deja fuera a propósito: en este
# corpus casi siempre es el IOS de Cisco, no el de Apple.
_FAMILIA_OS = {
    "windows": "windows",
    "windows server": "windows",
    "linux": "linux",
    "ubuntu": "linux",
    "debian": "linux",
    "centos": "linux",
    "rhel": "linux",
    "red hat enterprise linux": "linux",
    "fedora": "linux",
    "rocky": "linux",
    "oracle linux": "linux",
    "amazon linux": "linux",
    "macos": "macos",
    "apple ios": "apple-ios",
    "android": "android",
}
_VERSION_RE = re.compile(
    r"\b(Node(?:\.js)?|Python|Java|\.NET|Angular|Vue|React|Docker|Kubernetes|"
    r"Chrome|Firefox|Edge|PowerShell|npm|pnpm|yarn|PostgreSQL|MySQL|SQL Server|"
    r"Oracle)\s+v?(\d+(?:\.\d+){1,3})\b",
    re.IGNORECASE,
)
_HW_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(GB|TB|MB)\s*(?:de\s+)?(?:RAM|memoria|disco|almacenamiento)\b"
    r"|\b(\d+(?:[.,]\d+)?)\s*(GHz|n[uú]cleos|cores)\b",
    re.IGNORECASE,
)
# Solo se mira la prosa: una salida de `free -h` no es un requisito del alumno.
_PRESCRIPTIVO = (
    "requiere", "requerira", "requerido", "necesita", "necesitara", "debe tener",
    "debes tener", "debera tener", "asegurate de tener", "asegurese de tener",
    "instale", "instala", "instalar", "descargue e instale", "su equipo",
    "su maquina", "su pc", "su computadora", "su ordenador", "el participante debe",
    "el alumno debe", "el estudiante debe", "verifique que tiene", "hardware",
    "requisito", "minimo", "minima",
)
# Una especificación de la VM, el contenedor o la instancia del ejercicio no es un
# requisito del equipo del alumno: no cuenta como B5.
_EXCLUYENTE = (
    "maquina virtual", "virtualbox", "vmware", "hyper-v", "contenedor",
    "docker", "cluster", "nodo", "servidor", "instancia", "iso", "kubernetes",
    "pod", "namespace", " vm ", " vms ", "pdb", "cdb", "srv1", "srv2", "invitado",
)


def requisitos_declarados(software=None, hardware=None) -> str:
    """Texto normalizado de los requisitos que declara el plan."""
    return normalizar(
        json.dumps(software or [], ensure_ascii=False)
        + "\n"
        + json.dumps(hardware or [], ensure_ascii=False)
    )


def _es_ilustrativo(prosa: str, inicio: int, fin: int) -> bool:
    """¿La mención es un ejemplo, una alternativa o una etiqueta de interfaz?

    Tres falsos positivos medidos el 21/10/2026 en 1.294 laboratorios reales:

    - «un cliente ssh (como Putty o terminal de **macOS/Linux**)» → alternativa;
    - «`c:/...` (**Windows**) o `~/...` (**macOS**)» → rutas alternativas;
    - «View -> Tool **Windows** -> AI Assistant» → etiqueta de la interfaz, no un
      sistema operativo.
    """
    antes = prosa[max(0, inicio - 16):inicio]
    despues = prosa[fin:fin + 16]
    if antes.rstrip().endswith("(") or antes.rstrip().endswith("/"):
        return True
    if despues.lstrip().startswith("/"):
        return True
    if normalizar(antes).rstrip().endswith("tool"):
        return True
    return False


def _magnitudes(texto: str) -> set[tuple[str, str]]:
    salida = set()
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*(gb|tb|mb|ghz|nucleos|cores)\b", texto):
        salida.add((m.group(1).replace(",", "."), m.group(2)))
    return salida


# --------------------------------------------------------------------------- #
# Entregables declarados en el plan (B3p)
# --------------------------------------------------------------------------- #

# El plan declara el entregable como una entrada que aporta el curso, no como algo
# que produzca el alumno. Citarlo en un comando no lo convierte en entregable.
_ENTREGABLE_ENTRADA = (
    "entrada", "input", "proporcionad", "entregad por el instructor",
    "recibid", "--variable", "aportad por el curso",
)
_ALTERNATIVA = ("o", "u", "or", "/")


def entregables_declarados(expected_outcomes) -> list[list[str]]:
    """Grupos de entregables que el plan declara **producidos** por el alumno.

    Cada grupo es una lista de alternativas: «``deploy.sh`` o ``deploy.ps1``» es un
    solo requisito, no dos. Una frase que presenta el fichero como **entrada** del
    curso se descarta: no es un entregable.
    """
    grupos: list[list[str]] = []
    for salida in expected_outcomes or ():
        if not isinstance(salida, str):
            continue
        if any(marca in normalizar(salida) for marca in _ENTREGABLE_ENTRADA):
            continue
        referentes = extraer_referentes(salida, deduplicar=False)
        if not referentes:
            continue
        actual = [referentes[0]["valor"]]
        for anterior, siguiente in zip(referentes, referentes[1:]):
            entre = salida[
                anterior["inicio"] + len(anterior["valor"]):siguiente["inicio"]
            ].strip().lower()
            if entre in _ALTERNATIVA:
                actual.append(siguiente["valor"])
            else:
                grupos.append(actual)
                actual = [siguiente["valor"]]
        grupos.append(actual)
    return grupos


def auditar_entregables(laboratorio_md: str, expected_outcomes) -> dict:
    """B3p: ¿todo entregable que el plan declara producido aparece en el laboratorio?

    Tres estados, y solo uno es una omisión:

    - **creado**: la detección de creación de B1 lo ve (``cat >``, andamiaje, opción
      de salida…);
    - **mencionado sin creación reconocida** (``baja``): aparece en el texto, pero
      la frase de creación no se reconoce. Es el mismo hueco de extractor que B1,
      no una omisión;
    - **no mencionado** (``alta``): el nombre no aparece ni una vez. El laboratorio
      no produce el entregable que el plan declara.

    Medición del 21/10/2026 sobre 1.294 laboratorios: 145 con alguna omisión y 12
    solo con menciones sin creación. Por eso **no reintenta por defecto**
    (``DELIVERABLES_RETRY=0``).
    """
    grupos = entregables_declarados(expected_outcomes)
    informe = {"ok": True, "declarados": len(grupos), "omitidos": [], "mencionados": []}
    if not grupos:
        return informe
    creados = referentes_creados(laboratorio_md or "")
    texto = (laboratorio_md or "").lower()

    for grupo in grupos:
        claves = set()
        for valor in grupo:
            claves.add(canonico(valor))
            claves.add(canonico(valor.replace("\\", "/").split("/")[-1]))
        if claves & creados:
            continue
        if any(valor.replace("\\", "/").split("/")[-1].lower() in texto for valor in grupo):
            informe["mencionados"].extend(grupo)
        else:
            informe["omitidos"].extend(grupo)

    informe["ok"] = not informe["omitidos"] and not informe["mencionados"]
    return informe


def _versiones_declaradas(declarado: str, herramienta: str) -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(re.escape(herramienta) + r"[^\n]{0,80}?(\d+(?:\.\d+){1,3})", declarado)
    ]


def auditar_requisitos(laboratorio_md: str, requisitos_texto: str) -> dict:
    """B5: ¿el laboratorio exige algo que el plan no declara?

    Se separan dos cosas que no valen lo mismo:

    - **Contradicción** (``alta``): el plan declara un sistema operativo o una
      versión para una herramienta y el laboratorio dice otro. Es inequívoco.
    - **Ampliación** (``baja``): el laboratorio exige una magnitud de hardware o una
      versión que el plan no menciona. Es una señal, pero también puede ser la
      sección de entorno del propio laboratorio; se registra y no se reintenta.

    Medición del 21/10/2026 sobre 1.294 laboratorios reales: 0 contradicciones y
    59 laboratorios (4,6 %) con ampliaciones, todas de hardware.
    """
    declarado = requisitos_texto or ""
    informe = {"ok": True, "contradicciones": [], "ampliaciones": []}
    if not declarado.strip():
        return informe

    prosa_original = _PROSA_RE.sub(lambda m: " " * len(m.group(0)), laboratorio_md or "")
    familias_plan = {
        _FAMILIA_OS.get(normalizar(m.group(1)), normalizar(m.group(1)))
        for m in _OS_PLAN_RE.finditer(declarado)
    }
    magnitudes_plan = _magnitudes(declarado)

    def contexto(inicio: int, fin: int) -> str:
        # El contexto se normaliza solo para decidir; el valor conserva su forma.
        return normalizar(prosa_original[max(0, inicio - 160):fin + 160])

    for m in _OS_RE.finditer(prosa_original):
        ctx = contexto(m.start(), m.end())
        if not any(p in ctx for p in _PRESCRIPTIVO) or any(x in ctx for x in _EXCLUYENTE):
            continue
        if _es_ilustrativo(prosa_original, m.start(), m.end()):
            continue
        familia = _FAMILIA_OS.get(normalizar(m.group(1)), normalizar(m.group(1)))
        if familia in familias_plan:
            continue
        if familias_plan:
            informe["contradicciones"].append(
                {"tipo": "os", "valor": m.group(1), "declarado": sorted(familias_plan)}
            )
        else:
            informe["ampliaciones"].append({"tipo": "os", "valor": m.group(1)})

    for m in _VERSION_RE.finditer(prosa_original):
        ctx = contexto(m.start(), m.end())
        if not any(p in ctx for p in _PRESCRIPTIVO) or any(x in ctx for x in _EXCLUYENTE):
            continue
        if _es_ilustrativo(prosa_original, m.start(), m.end()):
            continue
        herramienta, version = normalizar(m.group(1)), m.group(2)
        declaradas = _versiones_declaradas(declarado, herramienta)
        if not declaradas:
            if herramienta in declarado:
                informe["ampliaciones"].append(
                    {"tipo": "version", "valor": f"{m.group(1)} {version}"}
                )
            continue
        if version.split(".")[0] not in {v.split(".")[0] for v in declaradas}:
            informe["contradicciones"].append(
                {
                    "tipo": "version",
                    "valor": f"{m.group(1)} {version}",
                    "declarado": declaradas,
                }
            )

    for m in _HW_RE.finditer(prosa_original):
        ctx = contexto(m.start(), m.end())
        if not any(p in ctx for p in _PRESCRIPTIVO) or any(x in ctx for x in _EXCLUYENTE):
            continue
        if _es_ilustrativo(prosa_original, m.start(), m.end()):
            continue
        numero = (m.group(1) or m.group(3)).replace(",", ".")
        unidad = normalizar(m.group(2) or m.group(4))
        if (numero, unidad) not in magnitudes_plan:
            informe["ampliaciones"].append({"tipo": "hardware", "valor": f"{numero} {unidad}"})

    informe["ok"] = not informe["contradicciones"] and not informe["ampliaciones"]
    return informe


def _indice_de_salidas(salidas_posteriores) -> dict[str, str]:
    """``{clave_canonica: lab_id}`` de los entregables de laboratorios posteriores."""
    indice: dict[str, str] = {}
    if isinstance(salidas_posteriores, dict):
        entradas = salidas_posteriores.items()
    else:
        entradas = (
            ((e or {}).get("lab_id", ""), (e or {}).get("valores") or ())
            for e in (salidas_posteriores or ())
        )
    for lab_id, valores in entradas:
        for valor in valores or ():
            clave = canonico(valor)
            if clave:
                indice.setdefault(clave, lab_id)
    return indice


def auditar_laboratorio(
    laboratorio_md: str,
    fuentes: str,
    plan: str = "",
    creados_antes=None,
    salidas_posteriores=None,
    referencias_posteriores=None,
    duracion_min=None,
    requisitos_texto=None,
    expected_outcomes=None,
) -> dict:
    """B1/B2/B3/B6: cierre de referentes y de duración.

    Recorre las apariciones **en orden**. Una aparición es válida si el referente
    ya se introdujo antes en el propio laboratorio, si está declarado en las
    fuentes o en el plan, si lo creó un laboratorio **anterior** (``creados_antes``,
    B3) o si la aparición está en un contexto de creación.

    Una aparición es una dependencia hacia delante (B2) si el referente es una
    salida declarada de un laboratorio **posterior**, no está en las fuentes y este
    laboratorio no lo crea. Esas se marcan con ``verificacion="B2"``.

    B6 es independiente de los referentes: compara la duración declarada con los
    pasos con acción y los bloques de comando o código del propio laboratorio.
    B5 compara los requisitos técnicos que el laboratorio exige con los que declara
    el plan.

    Args:
        laboratorio_md: markdown del laboratorio.
        fuentes: temario + manual + documentos, concatenados.
        plan: plan maestro ya filtrado (sin los referentes que A1 marcó de alta).
        creados_antes: claves canónicas de lo que crearon los laboratorios previos.
        salidas_posteriores: ``{lab_id: [valores]}`` de los laboratorios posteriores.
        referencias_posteriores: salida de :func:`referencias_a_labs_posteriores`.
        duracion_min: minutos del laboratorio. Si es ``None`` se toma la duración
            que el propio laboratorio declara en sus metadatos.
        requisitos_texto: requisitos de software y hardware del plan, ya normalizados
            con :func:`requisitos_declarados`.
        expected_outcomes: salidas esperadas del laboratorio según el plan. Si se
            pasan, se comprueba B3p.

    Returns:
        ``{"total", "creados", "violaciones", "menciones_posteriores", "duracion",
        "requisitos", "entregables", "ok"}``. Cada violación lleva ``verificacion``
        (``B1``, ``B2``, ``B3p``, ``B5`` o ``B6``) y ``confianza`` (``alta`` si el
        contexto presenta el referente como **aportado por el curso**, si es una
        dependencia hacia delante, si es una duración imposible, si contradice al
        plan o si el plan declara un entregable que el laboratorio ni menciona;
        ``baja`` si el laboratorio amplía un requisito o menciona un entregable sin
        una creación reconocible). Las menciones de hoja de ruta van aparte y no
        afectan a ``ok``.
    """
    if duracion_min is None:
        duracion_min = duracion_declarada(laboratorio_md or "")
    fuentes_norm = canonico(fuentes)
    plan_norm = canonico(plan)
    conocidos: set[str] = set(creados_antes or ())
    posteriores = _indice_de_salidas(salidas_posteriores)
    creados: set[str] = set()
    candidatos: list[dict] = []

    # Se recorren **todas** las apariciones (no solo la primera): un fichero puede
    # mencionarse antes en una tabla o en un árbol de directorios y crearse después
    # con ``cat >``, ``--output`` o ``> fichero``. Basta con que una aparición sea
    # de creación para eximirlo; por eso las no exentas se guardan y se deciden al
    # final, cuando ya se vio el laboratorio completo.
    for referente in extraer_referentes(laboratorio_md or "", deduplicar=False):
        claves = claves_de(referente)
        if any(clave in conocidos for clave in claves):
            conocidos.update(claves)
            continue
        creacion = _es_creacion(laboratorio_md, referente)
        if creacion:
            creados.update(claves)
        # B2: la salida de un laboratorio posterior no puede ser la entrada de este.
        # Se comprueba antes que «declarado en el plan», porque el plan contiene
        # precisamente los ``expected_outcomes`` del laboratorio posterior.
        origen = next((posteriores[c] for c in claves if c in posteriores), "")
        if origen and not any(clave in fuentes_norm for clave in claves) and not creacion:
            candidatos.append(dict(referente, _posterior=origen))
            continue
        declarado = any(
            clave and (clave in fuentes_norm or clave in plan_norm) for clave in claves
        )
        if declarado or creacion:
            conocidos.update(claves)
            continue
        candidatos.append(referente)

    violaciones: list[dict] = []
    violados: set[str] = set()
    for referente in candidatos:
        claves = claves_de(referente)
        if any(clave in conocidos for clave in claves):
            continue
        clave = canonico(referente["valor"])
        if clave in violados:
            continue
        violados.add(clave)
        posterior = referente.get("_posterior") or ""
        alta = _es_entrada(laboratorio_md, referente)
        violacion = {
            "valor": referente["valor"],
            "tipo": referente["tipo"],
            "inicio": referente["inicio"],
            "confianza": "alta" if alta else "baja",
            "verificacion": "B2" if posterior else "B1",
        }
        if posterior:
            violacion["laboratorio_posterior"] = posterior
        violaciones.append(violacion)

    # B6: la duración declarada contra el trabajo real del laboratorio. Se comprueba
    # sobre el texto escrito (ahí están los pasos), no sobre el plan: el plan no
    # tiene pasos y una comprobación ahí sería vacua.
    duracion = auditar_duracion(laboratorio_md or "", duracion_min)
    if not duracion["ok"]:
        violaciones.append(
            {
                "valor": duracion["motivo"],
                "tipo": "duracion",
                "inicio": 0,
                "confianza": "alta",
                "verificacion": "B6",
                "duracion": duracion["duracion"],
                "pasos": duracion["con_accion"],
                "bloques": duracion["bloques"],
            }
        )

    # B5: requisitos técnicos que el laboratorio exige y el plan no declara. La
    # contradicción es de alta confianza; la ampliación se registra con baja.
    requisitos = auditar_requisitos(laboratorio_md or "", requisitos_texto or "")
    for hallazgo in requisitos["contradicciones"]:
        violaciones.append(
            {
                "valor": hallazgo["valor"],
                "tipo": "requisito",
                "inicio": 0,
                "confianza": "alta",
                "verificacion": "B5",
                "declarado": hallazgo.get("declarado"),
                "detalle": hallazgo["tipo"],
            }
        )
    for hallazgo in requisitos["ampliaciones"]:
        violaciones.append(
            {
                "valor": hallazgo["valor"],
                "tipo": "requisito",
                "inicio": 0,
                "confianza": "baja",
                "verificacion": "B5",
                "detalle": hallazgo["tipo"],
            }
        )

    # B3p: entregables que el plan declara producidos. La omisión (no se menciona
    # ni una vez) es de alta confianza; la mención sin creación reconocida es el
    # hueco de extractor de B1 y se registra con baja.
    entregables = auditar_entregables(laboratorio_md or "", expected_outcomes)
    for valor in entregables["omitidos"]:
        violaciones.append(
            {
                "valor": valor,
                "tipo": "entregable",
                "inicio": 0,
                "confianza": "alta",
                "verificacion": "B3p",
            }
        )
    for valor in entregables["mencionados"]:
        violaciones.append(
            {
                "valor": valor,
                "tipo": "entregable",
                "inicio": 0,
                "confianza": "baja",
                "verificacion": "B3p",
            }
        )

    # Forma débil de B2: menciones explícitas a un laboratorio posterior. No son
    # violaciones (una hoja de ruta es normal): van en su propia clave del informe.
    menciones_posteriores = list(referencias_posteriores or ())

    return {
        "total": len(conocidos),
        "creados": sorted(creados),
        "violaciones": violaciones,
        "menciones_posteriores": menciones_posteriores,
        "duracion": duracion,
        "requisitos": requisitos,
        "entregables": entregables,
        "ok": not violaciones,
    }


def mensaje_de_correccion(violaciones: list[dict], ambito: str) -> str:
    """Instrucción para el reintento correctivo: **nunca borrar un entregable**.

    La calibración del 19/10/2026 midió que la clase de alta confianza todavía
    contiene falsos positivos, así que la corrección debe ser no destructiva: se
    marca o se define la creación, pero no se elimina lo que el estudiante produce.
    """
    if not violaciones:
        return ""
    if ambito == "plan":
        lineas = [f"- «{v['valor']}» (campo {v['campo']})" for v in violaciones[:20]]
        intro = (
            "El plan presenta estos ficheros o rutas como APORTADOS POR EL CURSO, pero no "
            "aparecen en el temario ni en el manual: el alumno no los tendrá. Corrígelos sin "
            "cambiar lo que el temario sí define:\n"
            "- si el curso debe aportarlo, escribe «[POR CONFIRMAR]» junto a su mención;\n"
            "- si el estudiante lo crea o lo genera, describe en qué paso se crea;\n"
            "- si sobra, sustitúyelo por una descripción funcional sin nombre de fichero.\n"
            "No inventes nombres de fichero y no elimines entregables que produce el estudiante."
        )
        return intro + "\n" + "\n".join(lineas)

    bloques: list[str] = []

    b1 = [v for v in violaciones if v.get("verificacion", "B1") == "B1"]
    if b1:
        lineas = [f"- «{v['valor']}»" for v in b1[:20]]
        intro = (
            "El laboratorio presenta estos ficheros o rutas como aportados por el curso, pero no "
            "están en el temario, ni en el manual, ni en el plan, y no se crean en ningún paso "
            "anterior. Corrígelos sin borrar entregables:\n"
            "- si el curso debe aportarlo, escribe «[POR CONFIRMAR]» junto a su mención;\n"
            "- si el laboratorio lo genera, añade en un paso anterior la orden que lo crea;\n"
            "- si sobra, sustitúyelo por una descripción funcional sin nombre de fichero.\n"
            "No elimines ficheros que el estudiante produce ni nombres de fichero que el temario "
            "declare."
        )
        bloques.append(intro + "\n" + "\n".join(lineas))

    b2 = [v for v in violaciones if v.get("verificacion") == "B2"]
    if b2:
        lineas = [
            f"- «{v['valor']}» (solo aparece en el laboratorio posterior "
            f"{v.get('laboratorio_posterior') or 'siguiente'})"
            for v in b2[:20]
        ]
        intro = (
            "Este laboratorio usa como entrada algo que solo existe en un laboratorio POSTERIOR. "
            "Un laboratorio no puede depender de uno que aún no ha ocurrido:\n"
            "- si este laboratorio puede producirlo, añade antes el paso que lo crea;\n"
            "- si el curso debe aportarlo, escribe «[POR CONFIRMAR]» junto a su mención;\n"
            "- si sobra, sustitúyelo por una descripción funcional sin nombre de fichero.\n"
            "No adelantes contenido del laboratorio posterior ni elimines entregables de este "
            "laboratorio."
        )
        bloques.append(intro + "\n" + "\n".join(lineas))

    b3p = [v for v in violaciones if v.get("verificacion") == "B3p"]
    if b3p:
        lineas = [f"- `{v['valor']}`" for v in b3p[:20]]
        intro = (
            "El plan declara estos entregables y este laboratorio no los menciona ni una vez. "
            "Añade el paso que los produce:\n"
            "- intégralo en el paso que ya construye esa parte, sin crear un laboratorio aparte;\n"
            "- el entregable debe quedar nombrado con el mismo nombre que usa el plan;\n"
            "- no elimines ningún entregable que ya produzca el laboratorio."
        )
        bloques.append(intro + "\n" + "\n".join(lineas))

    b5 = [v for v in violaciones if v.get("verificacion") == "B5"]
    if b5:
        lineas = [
            f"- «{v['valor']}» (el plan declara: {', '.join(v.get('declarado') or []) or 'nada'})"
            for v in b5[:20]
        ]
        intro = (
            "Este laboratorio exige un requisito técnico que contradice al plan del curso. "
            "Alinealo con el plan:\n"
            "- si el laboratorio puede hacerse con lo que declara el plan, corrige la mención;\n"
            "- si de verdad necesita ese sistema o esa versión, no la cambies aquí: el plan es "
            "el contrato y debe declararla antes;\n"
            "- no elimines entregables ni pasos por este motivo."
        )
        bloques.append(intro + "\n" + "\n".join(lineas))

    b6 = [v for v in violaciones if v.get("verificacion") == "B6"]
    if b6:
        lineas = [f"- {v['valor']}" for v in b6]
        intro = (
            "La duración declarada no es compatible con el trabajo que pide el laboratorio. "
            "Corrige el volumen, no la duración del plan:\n"
            "- reduce los pasos de exploración o repetitivos y los bloques de comando o código "
            "que no sean imprescindibles;\n"
            "- conserva todos los entregables que produce el estudiante y los pasos de "
            "verificación;\n"
            "- no cambies la duración del plan ni el número de laboratorio.\n"
            "Cada paso con acción debe tener al menos 3 minutos y cada bloque, al menos 1."
        )
        bloques.append(intro + "\n" + "\n".join(lineas))

    return "\n\n".join(bloques)


# --------------------------------------------------------------------------- #
# Duración del curso (A3): el temario es el contrato
# --------------------------------------------------------------------------- #


def _minutos(valor) -> int | None:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def reconciliar_duraciones(master_plan: dict, labs) -> dict:
    """A3: fija ``estimated_duration`` a la duración que declara el temario.

    No es un reintento: es una corrección determinista. El planificador ya recibe
    la duración de cada ``lab_activity`` en ``labs``; cuando el modelo la cambia
    («el temario dice 18 minutos y el plan pone 40»), el valor del temario manda.

    Devuelve ``{"corregidos": [...], "con_contrato": n, "sin_contrato": n}``.
    """
    contrato = {}
    for lab in labs or ():
        lab_id = (lab or {}).get("lab_id")
        minutos = _minutos((lab or {}).get("duration_minutes"))
        if lab_id and minutos:
            contrato[lab_id] = minutos

    corregidos = []
    sin_contrato = 0
    for lab_plan in master_plan.get("lab_plans") or ():
        esperado = contrato.get(lab_plan.get("lab_id"))
        if esperado is None:
            sin_contrato += 1
            continue
        actual = lab_plan.get("estimated_duration")
        if _minutos(actual) != esperado:
            corregidos.append(
                {
                    "lab_id": lab_plan.get("lab_id"),
                    "antes": actual,
                    "despues": esperado,
                }
            )
            lab_plan["estimated_duration"] = esperado
    return {
        "corregidos": corregidos,
        "con_contrato": len(contrato),
        "sin_contrato": sin_contrato,
    }


def auditar_duraciones_curso(master_plan: dict, labs=None, total_curso=None) -> dict:
    """A3: la suma de los laboratorios cabe en el curso y su número cuadra.

    Dos comprobaciones independientes:

    - ``suma_plan <= total_duration_minutes`` del temario;
    - el plan tiene un laboratorio por cada ``lab_activity`` declarada.

    Medición del 21/10/2026 (164 proyectos con temario y plan): el total se excede
    en 1 proyecto (3 minutos) y el número de prácticas no cuadra en 10. Se registra;
    no dispara reintento, porque el arreglo del total no es determinista (habría que
    decidir qué práctica se recorta).
    """
    labs = list(labs or ())
    lab_plans = list(master_plan.get("lab_plans") or ())
    suma = sum(_minutos(p.get("estimated_duration")) or 30 for p in lab_plans)
    total = _minutos(total_curso)
    informe = {
        "suma_plan": suma,
        "total_curso": total,
        "excede_total": bool(total and suma > total),
        "labs_temario": len(labs),
        "labs_plan": len(lab_plans),
        "faltan": max(0, len(labs) - len(lab_plans)),
        "sobran": max(0, len(lab_plans) - len(labs)),
        "ok": True,
    }
    informe["ok"] = not informe["excede_total"] and not informe["faltan"] and not informe["sobran"]
    return informe

