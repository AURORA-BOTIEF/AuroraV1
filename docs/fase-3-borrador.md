# Fase 3 — borrador de alcance (A2, B7, B8)

**Estado:** borrador, sin código. 24/10/2026. Nace de §28.5: la fase 3 necesita su propia spec y,
antes, decidir de dónde salen sus entradas.

La restricción de siempre: **nada de campos obligatorios nuevos en el temario** y ningún cambio que
exija regenerar cursos.

## Por qué A2 no es como B1

B1 compara nombres de fichero: el temario los declara o no. **A2** compara *entidades y cantidades*
(«seis fondos» → «tres», «CIBEST CAPITAL» → «Northstar Digital»), y eso no tiene una fuente
equivalente. La pregunta que decide la fase es:

> ¿Dónde está la lista de entidades y cantidades del curso?

Hoy no existe un campo que la declare. Hay tres salidas, y cada una cambia el alcance:

| Salida | Qué implica | Riesgo |
|---|---|---|
| Extraerlas del temario en prosa | A2 solo puede comprobar lo que el temario **dice** («seis fondos»); lo que no dice, no se puede contradecir | cobertura baja; puede dar una falsa sensación de verificación |
| Derivarlas del plan como «declaración» | el plan se convierte en la fuente; A2 comprueba la guía contra el plan | el plan puede inventar, y entonces A2 bendice la invención |
| No implementar A2 y dejarlo como está | se documenta el límite | se pierde el fallo real del informe del instructor |

**Primer paso, barato y decisivo:** medir cuántos temarios declaran cantidades o entidades de forma
comprobable (cifras + sustantivo, nombres propios entrecomillados). Si son pocos, A2 nace con un
alcance pequeño y hay que decirlo antes de construirlo.

## B7 — Setup Guide y laboratorios, en ambos sentidos

**Qué comprueba:** todo prerequisito que un laboratorio asume está en el Setup Guide, y todo lo que
el Setup Guide incluye está justificado por el plan o por algún laboratorio.

**Entradas:** el Setup Guide (lo genera `setup_guide_builder` desde el plan y el temario) y las guías
de laboratorio (las genera el Writer). Ambas existen y son deterministas.

**Dónde correría:** en el validador de conjunto, que ya recorre todos los laboratorios (§6 de la
spec: B2, B4 y B7 son verificaciones del conjunto).

**Riesgo principal:** circularidad. Los dos artefactos se generan del mismo plan, así que una
invención compartida —el plan inventa una herramienta y el Setup Guide la repite— pasaría la
comprobación. B7 detecta **desacuerdos**, no invenciones; para las invenciones está A1/B1.

**Medición de arranque:** sobre los cursos reales, cuántos prerequisitos de laboratorio no aparecen
en su Setup Guide (y al revés). Si el número es alto, el frente tiene valor; si es cero, se cierra
en una tarde.

## B8 — el marcador cuenta como señal

**Qué comprueba:** todo específico no declarado va marcado, y el marcador **se ve** en el informe de
revisión.

**El problema actual, verificado en el código:** el Setup Guide emite su propia familia de marcas
(`[VERSION POR VALIDAR]`, `[LICENCIA POR VALIDAR]`, `[DOMINIOS, PUERTOS Y PROXY POR VALIDAR]`), el
`content_validator` las reporta como **INFO** (`validate_placeholders`) y el chequeo referencial
reconoce `[POR CONFIRMAR]` y «… por confirmar» en prosa. Resultado: el marcador existe, pero no
cuenta como señal en ninguno de los dos sitios.

**Decisión que hay que tomar (una sola):**

1. **Unificar el vocabulario**: el Setup Guide emite `[POR CONFIRMAR]` (o `[DATO POR CONFIRMAR]`) y
   el chequeo ya lo reconoce. Barato, pero cambia la estética del Setup Guide.
2. **Enseñar la familia al chequeo**: aceptar `[X POR VALIDAR]` como marca de confirmación. Aún más
   barato, pero el vocabulario queda con dos familias.

**Primer paso:** censo de marcadores en el corpus real (cuántos y de qué formas). Sin ese censo,
cualquiera de las dos opciones se elige a ciegas.

## Orden recomendado

1. **B8** — un censo y una decisión de vocabulario; medible en una tarde.
2. **B7** — autocontenido, con entradas que ya existen; el riesgo es la circularidad, no la falta de
   datos.
3. **A2** — última, porque primero hay que decidir de dónde sale la lista de entidades. Sin esa
   decisión, implementarla sería construir sobre arena.

## Lo que este borrador no decide

- Si A2 se implementa o se documenta como límite.
- Qué familia de marcadores gana en B8.
- Si B7 debe bloquear o solo registrar (hoy la spec lo pone en MARCADOR).
