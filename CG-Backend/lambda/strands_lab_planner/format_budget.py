"""Cap or merge planned practices so they fit the syllabus format.

The pre-flight used to print ``poco_tiempo`` and keep generating. This module is
the gate: before lab guides are written, the plan is reduced to the practice
minutes the syllabus actually budgets.

Profiles (conference / seminar / full course) come from explicit metadata and,
when that is absent, from duration plus ``percent_practice``. A 2-hour session
whose practice slice is about 30 minutes is a conference. The minute ceiling is
always the syllabus: ``duration_minutes × percent_practice`` per module, and
``total_duration_minutes`` for the course. Declared activity time that overruns
that ceiling is scaled down. Extra practices are merged, and a zero budget
drops them. Syllabus items that were combined are recorded on the plan.
"""

from __future__ import annotations

import copy
import re
import unicodedata

from referent_check import presupuesto_de_duracion

# Same floor as ``preflight_duracion`` (_MINUTOS_POR_LAB_PREFLIGHT). A practice
# shorter than this is what the pre-flight calls ``poco_tiempo``.
MINUTOS_MINIMOS = 12

# A short session whose practice share is about a 30-minute demo, not a workshop.
_CONFERENCIA_MAX_MINUTOS = 180
_CONFERENCIA_MAX_PRACTICA = 45
_CONFERENCIA_MAX_RATIO = 0.35
_SEMINARIO_MAX_MINUTOS = 480
_DEMO_CONFERENCIA_SIN_PORCENTAJE = 30

_CONFERENCE_RE = re.compile(
    r"\b(?:conferencias?|conferences?|charlas?|keynotes?|webinars?|ponencias?)\b"
)
_SEMINAR_RE = re.compile(
    r"\b(?:seminarios?|seminars?|talleres|taller|workshops?|bootcamps?|"
    r"masterclass(?:es)?|crash courses?)\b"
)
_COURSE_RE = re.compile(
    r"\b(?:curso completo|full courses?|diplomados?|certificaciones?|certifications?)\b"
)
_CLAVES_FORMATO = (
    "format",
    "formato",
    "delivery_mode",
    "modalidad",
    "course_type",
    "tipo",
    "delivery",
)

_ETIQUETA = {
    "conference": ("conferencia", "conference"),
    "seminar": ("seminario", "seminar"),
    "course": ("curso completo", "full course"),
}


def _minutos(valor) -> int | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        if not valor:
            return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        try:
            numero = int(float(valor))
        except (TypeError, ValueError):
            return None
    return numero if numero > 0 else None


def _porcentaje(valor) -> float | None:
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, str):
        valor = valor.strip().rstrip("%").strip()
        if not valor:
            return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero < 0:
        return 0.0
    if numero > 100:
        return 100.0
    return numero


def _fold(texto: str) -> str:
    # Local fold so this module does not depend on referent_check.normalizar,
    # which also rewrites underscores. Format keywords are plain words.
    plano = unicodedata.normalize("NFD", str(texto or ""))
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return plano.lower()


def _texto(curso: dict, claves) -> str:
    partes = []
    for clave in claves:
        valor = curso.get(clave)
        if isinstance(valor, str):
            partes.append(valor)
        elif isinstance(valor, (list, tuple)):
            partes.extend(str(item) for item in valor if item)
    return _fold(" ".join(partes))


def _clasificar(texto: str) -> str | None:
    if _CONFERENCE_RE.search(texto):
        return "conference"
    if _SEMINAR_RE.search(texto):
        return "seminar"
    if _COURSE_RE.search(texto):
        return "course"
    return None


def _modulos(curso: dict) -> list[dict]:
    return [m for m in (curso.get("modules") or []) if isinstance(m, dict)]


def _techo_desde_porcentaje(modulo: dict) -> int | None:
    duracion = _minutos(modulo.get("duration_minutes"))
    porcentaje = _porcentaje(modulo.get("percent_practice"))
    if duracion is None or porcentaje is None:
        return None
    presupuesto = min(float(duracion), duracion * porcentaje / 100.0)
    return int(presupuesto)


def _total_minutos(curso: dict) -> int | None:
    total = _minutos(curso.get("total_duration_minutes"))
    if total:
        return total
    suma = 0
    alguno = False
    for modulo in _modulos(curso):
        minutos = _minutos(modulo.get("duration_minutes"))
        if minutos:
            suma += minutos
            alguno = True
    return suma if alguno else None


def _practica_declarada(curso: dict) -> int | None:
    suma = 0
    alguno = False
    for modulo in _modulos(curso):
        techo = _techo_desde_porcentaje(modulo)
        if techo is not None:
            suma += techo
            alguno = True
    return suma if alguno else None


def detectar_formato(curso: dict | None) -> str:
    """``conference``, ``seminar`` or ``course`` from syllabus metadata.

    An explicit format field wins. Otherwise the title and description are
    scanned. A session of at most 3 hours whose practice share is a short demo
    (about 30 minutes, and not more than 35% of the session) is a conference
    even when the syllabus never uses that word.
    """
    curso = curso or {}
    # The first explicit field that names a profile wins. `format` is ahead of
    # `formato` so a later alias cannot override the field the API sends.
    for clave in _CLAVES_FORMATO:
        valor = curso.get(clave)
        if isinstance(valor, str):
            explicito = _clasificar(_fold(valor))
            if explicito:
                return explicito
    narrado = _clasificar(
        _texto(curso, ("title", "description", "summary", "audience", "audiencia"))
    )
    if narrado:
        return narrado

    total = _total_minutos(curso)
    practica = _practica_declarada(curso)
    if (
        total
        and total <= _CONFERENCIA_MAX_MINUTOS
        and practica is not None
        and practica <= _CONFERENCIA_MAX_PRACTICA
        and practica / total <= _CONFERENCIA_MAX_RATIO
    ):
        return "conference"
    if total and total <= _SEMINARIO_MAX_MINUTOS:
        return "seminar"
    return "course"


def _techo_modulo(modulo: dict, perfil: str) -> int | None:
    """Practice minutes this module may spend, or the whole module when no percent is set."""
    desde_porcentaje = _techo_desde_porcentaje(modulo)
    if desde_porcentaje is not None:
        return desde_porcentaje
    duracion = _minutos(modulo.get("duration_minutes"))
    if perfil == "conference":
        # A conference that never states percent_practice still has a demo slot.
        if duracion:
            return min(_DEMO_CONFERENCIA_SIN_PORCENTAJE, duracion)
        return _DEMO_CONFERENCIA_SIN_PORCENTAJE
    return duracion


def _max_laboratorios(techo: int) -> int:
    if techo <= 0:
        return 0
    if techo < MINUTOS_MINIMOS:
        return 1
    return techo // MINUTOS_MINIMOS


def _minutos_plan(plan: dict) -> int:
    for clave in ("estimated_duration", "duration_minutes"):
        minutos = _minutos(plan.get(clave))
        if minutos:
            return minutos
    # Same default ``auditar_duraciones_curso`` uses when the model omitted it.
    return 30


def _titulo(plan: dict) -> str:
    return str(plan.get("lab_title") or plan.get("title") or plan.get("lab_id") or "").strip()


def _indice_modulo(plan: dict, cantidad: int) -> int | None:
    prefijo = str(plan.get("lab_id") or "")[:2]
    if not prefijo:
        return None
    for indice in range(1, cantidad + 1):
        if f"{indice:02d}" == prefijo:
            return indice
    return None


def _partir(items: list, grupos: int) -> list[list]:
    cantidad = len(items)
    if grupos <= 0:
        return []
    if grupos >= cantidad:
        return [[item] for item in items]
    base, resto = divmod(cantidad, grupos)
    trozos = []
    inicio = 0
    for indice in range(grupos):
        toma = base + (1 if indice < resto else 0)
        trozos.append(items[inicio : inicio + toma])
        inicio += toma
    return trozos


def _asignar(pesos: list[int], techo: int, minimo: int) -> list[int]:
    """Scale weights down so they sum to ``techo``. Never increases a total."""
    cantidad = len(pesos)
    techo = max(0, int(techo))
    if cantidad == 0:
        return []
    if techo == 0:
        return [0] * cantidad
    pesos = [max(0, int(peso)) for peso in pesos]
    if sum(pesos) == 0:
        return [1 if indice < techo else 0 for indice in range(cantidad)]
    minimo = max(0, int(minimo))
    if cantidad * minimo > techo:
        minimo = 0
    if minimo == 0 and techo < cantidad:
        orden = sorted(range(cantidad), key=lambda i: (pesos[i], -i), reverse=True)
        resultado = [0] * cantidad
        for indice in orden[:techo]:
            resultado[indice] = 1
        return resultado
    base = [minimo] * cantidad
    extra = techo - cantidad * minimo
    if extra == 0:
        return base
    total = sum(pesos) or 1
    cuota = [extra * (peso / total) for peso in pesos]
    enteros = [int(valor) for valor in cuota]
    resto = extra - sum(enteros)
    orden = sorted(
        range(cantidad),
        key=lambda i: (cuota[i] - enteros[i], pesos[i], -i),
        reverse=True,
    )
    for indice in orden[:resto]:
        enteros[indice] += 1
    return [base[i] + enteros[i] for i in range(cantidad)]


def _unir_listas(grupo: list[dict], clave: str) -> list:
    vistos = []
    ya = set()
    for plan in grupo:
        for item in plan.get(clave) or []:
            if isinstance(item, str):
                token = " ".join(item.split())
                marca = token
            else:
                token = item
                marca = str(item)
            if not marca or marca in ya:
                continue
            ya.add(marca)
            vistos.append(token if isinstance(item, str) else item)
    return vistos


def _en_espanol(curso: dict) -> bool:
    raw = (curso or {}).get("language")
    if raw is None or not str(raw).strip():
        return True
    texto = str(raw).strip().lower()
    if texto.startswith("en") or "english" in texto or "inglés" in texto or "ingles" in texto:
        return False
    return True


def _nota(titulos: list[str], perfil: str, espanol: bool) -> str:
    etiqueta = _ETIQUETA.get(perfil, ("curso", "course"))[0 if espanol else 1]
    lista = "; ".join(titulo for titulo in titulos if titulo)
    if espanol:
        return (
            "Actividades del temario reunidas en esta práctica porque el formato "
            f"({etiqueta}) no da minutos para guiarlas por separado: {lista}."
        )
    return (
        "Syllabus activities combined into this practice because the "
        f"{etiqueta} format does not budget enough minutes to guide them separately: {lista}."
    )


def _fijar_duracion(plan: dict, minutos: int) -> None:
    minutos = int(minutos)
    plan["estimated_duration"] = minutos
    if "duration_minutes" in plan:
        plan["duration_minutes"] = minutos
    plan["presupuesto_duracion"] = presupuesto_de_duracion(minutos)


def _referencia(plan: dict) -> dict:
    return {
        "lab_id": plan.get("lab_id"),
        "titulo": _titulo(plan),
        "minutos": _minutos_plan(plan),
    }


def _fusionar(grupo: list[dict], minutos: int, perfil: str, espanol: bool) -> dict:
    cabeza = copy.deepcopy(grupo[0])
    if len(grupo) > 1:
        fuentes = [_referencia(item) for item in grupo]
        cabeza["syllabus_items_combined"] = fuentes
        titulos = [fuente["titulo"] for fuente in fuentes]
        nota = _nota(titulos, perfil, espanol)
        scopes = [nota]
        for item in grupo:
            texto = str(item.get("scope") or "").strip()
            if texto and texto not in scopes:
                scopes.append(texto)
        cabeza["scope"] = "\n".join(scopes)
        cabeza["objectives"] = _unir_listas(grupo, "objectives")
        cabeza["expected_outcomes"] = _unir_listas(grupo, "expected_outcomes")
        if any(item.get("context_topics") for item in grupo):
            cabeza["context_topics"] = _unir_listas(grupo, "context_topics")
    _fijar_duracion(cabeza, minutos)
    return cabeza


def _ajustar_grupo(
    grupo: list[dict],
    techo: int | None,
    perfil: str,
    espanol: bool,
) -> tuple[list[dict], dict]:
    minutos_antes = sum(_minutos_plan(plan) for plan in grupo)
    info = {
        "antes": len(grupo),
        "minutos_antes": minutos_antes,
        "presupuesto_practica": techo,
        "max_laboratorios": None if techo is None else _max_laboratorios(techo),
        "minutos_max_por_laboratorio": techo,
        "combinados": [],
        "descartados": [],
    }
    if techo is None:
        resultado = [copy.deepcopy(plan) for plan in grupo]
        for plan in resultado:
            _fijar_duracion(plan, _minutos_plan(plan))
        info.update(
            {
                "despues": len(resultado),
                "minutos_despues": sum(_minutos_plan(plan) for plan in resultado),
                "duraciones": [_minutos_plan(plan) for plan in resultado],
            }
        )
        return resultado, info

    techo = int(techo)
    if techo <= 0:
        info["descartados"] = [_referencia(plan) for plan in grupo]
        info.update({"despues": 0, "minutos_despues": 0, "duraciones": [], "max_laboratorios": 0})
        return [], info

    maximo = _max_laboratorios(techo)
    info["max_laboratorios"] = maximo
    trozos = _partir(grupo, maximo) if len(grupo) > maximo else [[plan] for plan in grupo]
    pesos = [sum(_minutos_plan(plan) for plan in trozo) for trozo in trozos]
    if sum(pesos) > techo:
        minimo = MINUTOS_MINIMOS if len(trozos) * MINUTOS_MINIMOS <= techo else 1
        asignados = _asignar(pesos, techo, minimo)
    else:
        asignados = pesos

    resultado = []
    for trozo, minutos in zip(trozos, asignados):
        if minutos <= 0:
            info["descartados"].extend(_referencia(plan) for plan in trozo)
            continue
        fusion = _fusionar(trozo, minutos, perfil, espanol)
        resultado.append(fusion)
        if len(trozo) > 1:
            info["combinados"].append(
                {
                    "lab_id": fusion.get("lab_id"),
                    "fuentes": [plan.get("lab_id") for plan in trozo],
                    "titulos": [_titulo(plan) for plan in trozo],
                }
            )
    info.update(
        {
            "despues": len(resultado),
            "minutos_despues": sum(_minutos_plan(plan) for plan in resultado),
            "duraciones": [_minutos_plan(plan) for plan in resultado],
        }
    )
    return resultado, info


def _escalar_al_curso(planes: list[dict], techo: int) -> list[dict]:
    if not planes:
        return planes
    pesos = [_minutos_plan(plan) for plan in planes]
    if sum(pesos) <= techo:
        return planes
    minimo = MINUTOS_MINIMOS if len(planes) * MINUTOS_MINIMOS <= techo else 1
    asignados = _asignar(pesos, techo, minimo)
    conservados = []
    for plan, minutos in zip(planes, asignados):
        if minutos <= 0:
            continue
        _fijar_duracion(plan, minutos)
        conservados.append(plan)
    return conservados


def _refrescar_detalle(detalle: list[dict], planes: list[dict]) -> None:
    asignados: set[int] = set()
    for info in detalle:
        indice = info.get("modulo") or 0
        if not indice:
            continue
        prefijo = f"{indice:02d}"
        del_modulo = [plan for plan in planes if str(plan.get("lab_id") or "")[:2] == prefijo]
        info["despues"] = len(del_modulo)
        info["minutos_despues"] = sum(_minutos_plan(plan) for plan in del_modulo)
        info["duraciones"] = [_minutos_plan(plan) for plan in del_modulo]
        asignados.update(id(plan) for plan in del_modulo)
    huerfanos = [plan for plan in planes if id(plan) not in asignados]
    for info in detalle:
        if info.get("modulo"):
            continue
        info["despues"] = len(huerfanos)
        info["minutos_despues"] = sum(_minutos_plan(plan) for plan in huerfanos)
        info["duraciones"] = [_minutos_plan(plan) for plan in huerfanos]


def _excede(detalle: list[dict], suma: int, techo_curso: int | None) -> bool:
    if techo_curso is not None and suma > techo_curso:
        return True
    for info in detalle:
        techo = info.get("presupuesto_practica")
        if isinstance(techo, int) and info.get("minutos_despues", 0) > techo:
            return True
    return False


def _planes(master_plan: dict) -> list[dict]:
    return [plan for plan in (master_plan.get("lab_plans") or []) if isinstance(plan, dict)]


def _informe(
    *,
    perfil: str,
    ajustado: bool,
    excede: bool,
    motivo: str | None,
    labs_antes: int,
    labs_despues: int,
    suma_antes: int,
    suma_despues: int,
    techo_curso: int | None,
    modulos: list[dict],
    recorte_total_curso: bool = False,
) -> dict:
    informe = {
        "perfil": perfil,
        "ajustado": ajustado,
        "excede": excede,
        "minutos_min_por_laboratorio": MINUTOS_MINIMOS,
        "labs_antes": labs_antes,
        "labs_despues": labs_despues,
        "suma_antes": suma_antes,
        "suma_despues": suma_despues,
        "techo_curso": techo_curso,
        "recorte_total_curso": recorte_total_curso,
        "modulos": modulos,
    }
    if motivo:
        informe["motivo"] = motivo
    return informe


def sin_ajuste(curso: dict | None, master_plan: dict, motivo: str) -> dict:
    """Report used when the gate must not rewrite an existing plan."""
    curso = curso or {}
    planes = _planes(master_plan)
    suma = sum(_minutos_plan(plan) for plan in planes)
    return _informe(
        perfil=detectar_formato(curso),
        ajustado=False,
        excede=False,
        motivo=motivo,
        labs_antes=len(planes),
        labs_despues=len(planes),
        suma_antes=suma,
        suma_despues=suma,
        techo_curso=_minutos(curso.get("total_duration_minutes")),
        modulos=[],
    )


def escalar_plan_existente(curso: dict | None, master_plan: dict) -> dict:
    """Scale a legacy plan onto the format ceiling without dropping labs.

    A selective update must keep every lab the caller asked to regenerate.
    Minutes are scaled to the module practice ceiling and then to the course
    ceiling. ``excede`` stays true only when the scaled plan still cannot fit.
    """
    curso = curso or {}
    planes = _planes(master_plan)
    perfil = detectar_formato(curso)
    techo_curso = _total_minutos(curso)
    practica = _practica_declarada(curso)
    if practica is not None:
        techo_curso = practica if techo_curso is None else min(techo_curso, practica)
    suma_antes = sum(_minutos_plan(plan) for plan in planes)
    modulos = _modulos(curso)
    grupos: dict[int, list[dict]] = {}
    for plan in planes:
        indice = _indice_modulo(plan, len(modulos) or 1)
        grupos.setdefault(0 if indice is None else indice, []).append(plan)
    detalle: list[dict] = []
    cambio = False
    for indice, grupo in sorted(grupos.items()):
        modulo = modulos[indice] if indice < len(modulos) else {}
        techo = _techo_modulo(modulo, perfil) if modulo else None
        antes = sum(_minutos_plan(plan) for plan in grupo)
        if isinstance(techo, int) and antes > techo and grupo:
            minimo = MINUTOS_MINIMOS if len(grupo) * MINUTOS_MINIMOS <= techo else 1
            asignados = _asignar([_minutos_plan(plan) for plan in grupo], techo, minimo)
            for plan, minutos in zip(grupo, asignados):
                if minutos > 0 and minutos != _minutos_plan(plan):
                    _fijar_duracion(plan, minutos)
                    cambio = True
        despues = sum(_minutos_plan(plan) for plan in grupo)
        detalle.append(
            {
                "modulo": indice + 1,
                "presupuesto_practica": techo,
                "minutos_antes": antes,
                "minutos_despues": despues,
                "labs_antes": len(grupo),
                "labs_despues": len(grupo),
            }
        )
    suma = sum(_minutos_plan(plan) for plan in planes)
    recorte = False
    if isinstance(techo_curso, int) and suma > techo_curso and planes:
        minimo = MINUTOS_MINIMOS if len(planes) * MINUTOS_MINIMOS <= techo_curso else 1
        asignados = _asignar([_minutos_plan(plan) for plan in planes], techo_curso, minimo)
        for plan, minutos in zip(planes, asignados):
            if minutos > 0 and minutos != _minutos_plan(plan):
                _fijar_duracion(plan, minutos)
                recorte = True
                cambio = True
        _refrescar_detalle(detalle, planes)
        suma = sum(_minutos_plan(plan) for plan in planes)
    return _informe(
        perfil=perfil,
        ajustado=cambio,
        excede=_excede(detalle, suma, techo_curso),
        motivo="actualizacion_selectiva",
        labs_antes=len(planes),
        labs_despues=len(planes),
        suma_antes=suma_antes,
        suma_despues=suma,
        techo_curso=techo_curso,
        modulos=detalle,
        recorte_total_curso=recorte,
    )


def aplicar_presupuesto_de_formato(curso: dict | None, master_plan: dict) -> dict:
    """Merge or drop ``lab_plans`` until they fit the syllabus format budget.

    Mutates ``master_plan``. Returns the record of the decision, including which
    syllabus items were combined. ``excede`` stays true only when the plan is
    still over a known ceiling; the planner treats that as a hard stop.
    """
    curso = curso or {}
    perfil = detectar_formato(curso)
    espanol = _en_espanol(curso)
    planes = _planes(master_plan)
    suma_antes = sum(_minutos_plan(plan) for plan in planes)
    labs_antes = len(planes)
    modulos = _modulos(curso)
    techo_curso = _minutos(curso.get("total_duration_minutes"))

    grupos: dict[int | None, list[dict]] = {}
    orden: list[int | None] = []
    for plan in planes:
        clave = _indice_modulo(plan, len(modulos))
        if clave not in grupos:
            grupos[clave] = []
            orden.append(clave)
        grupos[clave].append(plan)

    nuevos: list[dict] = []
    detalle: list[dict] = []
    for clave in orden:
        grupo = grupos[clave]
        if clave is None:
            techo = None
            titulo = ""
            indice = 0
        else:
            modulo = modulos[clave - 1]
            techo = _techo_modulo(modulo, perfil)
            titulo = str(modulo.get("title") or "")[:80]
            indice = clave
        ajustados, info = _ajustar_grupo(grupo, techo, perfil, espanol)
        info["modulo"] = indice
        info["titulo"] = titulo
        if clave is None:
            # Orphan ids are capped only by the course total below.
            info["presupuesto_practica"] = None
            info["max_laboratorios"] = None
            info["minutos_max_por_laboratorio"] = None
        detalle.append(info)
        nuevos.extend(ajustados)

    recorte_curso = False
    if techo_curso is not None and sum(_minutos_plan(plan) for plan in nuevos) > techo_curso:
        recorte_curso = True
        nuevos = _escalar_al_curso(nuevos, techo_curso)
        _refrescar_detalle(detalle, nuevos)

    for plan in nuevos:
        plan["presupuesto_duracion"] = presupuesto_de_duracion(plan.get("estimated_duration"))

    suma_despues = sum(_minutos_plan(plan) for plan in nuevos)
    firma_antes = [(plan.get("lab_id"), _minutos_plan(plan)) for plan in planes]
    firma_despues = [(plan.get("lab_id"), _minutos_plan(plan)) for plan in nuevos]
    combinados = any(info.get("combinados") or info.get("descartados") for info in detalle)
    ajustado = firma_antes != firma_despues or combinados
    excede = _excede(detalle, suma_despues, techo_curso)

    if ajustado:
        master_plan["lab_plans"] = nuevos

    return _informe(
        perfil=perfil,
        ajustado=ajustado,
        excede=excede,
        motivo=None,
        labs_antes=labs_antes,
        labs_despues=len(nuevos) if ajustado else labs_antes,
        suma_antes=suma_antes,
        suma_despues=suma_despues if ajustado else suma_antes,
        techo_curso=techo_curso,
        modulos=detalle,
        recorte_total_curso=recorte_curso,
    )
