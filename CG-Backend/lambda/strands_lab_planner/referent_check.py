"""Trazabilidad de referentes de fichero (verificaciones A1, B1, B2 y B3c).

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
las entidades con nombre llegan en la fase 3.

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
) -> dict:
    """B1/B2/B3: todo fichero referenciado debe estar declarado o haberse creado antes.

    Recorre las apariciones **en orden**. Una aparición es válida si el referente
    ya se introdujo antes en el propio laboratorio, si está declarado en las
    fuentes o en el plan, si lo creó un laboratorio **anterior** (``creados_antes``,
    B3) o si la aparición está en un contexto de creación.

    Una aparición es una dependencia hacia delante (B2) si el referente es una
    salida declarada de un laboratorio **posterior**, no está en las fuentes y este
    laboratorio no lo crea. Esas se marcan con ``verificacion="B2"``.

    Args:
        laboratorio_md: markdown del laboratorio.
        fuentes: temario + manual + documentos, concatenados.
        plan: plan maestro ya filtrado (sin los referentes que A1 marcó de alta).
        creados_antes: claves canónicas de lo que crearon los laboratorios previos.
        salidas_posteriores: ``{lab_id: [valores]}`` de los laboratorios posteriores.
        referencias_posteriores: salida de :func:`referencias_a_labs_posteriores`.

    Returns:
        ``{"total", "creados", "violaciones", "menciones_posteriores", "ok"}``.
        Cada violación lleva ``verificacion`` (``B1`` o ``B2``) y ``confianza``
        (``alta`` solo si el contexto presenta el referente como **aportado por el
        curso**, o si es una dependencia hacia delante). Las menciones de hoja de
        ruta van aparte y no afectan a ``ok``.
    """
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

    # Forma débil de B2: menciones explícitas a un laboratorio posterior. No son
    # violaciones (una hoja de ruta es normal): van en su propia clave del informe.
    menciones_posteriores = list(referencias_posteriores or ())

    return {
        "total": len(conocidos),
        "creados": sorted(creados),
        "violaciones": violaciones,
        "menciones_posteriores": menciones_posteriores,
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

    return "\n\n".join(bloques)

