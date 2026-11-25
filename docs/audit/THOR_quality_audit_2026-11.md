# THOR quality audit — November 2026

**Scope:** audit only. No product code was changed. No pull request was opened.
**Baseline:** branch `thor-audit-base` at `dd032f6f19aae2ec2599682f56a38dce4c5b86ea` (3 Nov 2026, `fix(sfn): el Starter manda siempre los campos del modo actualizacion`). This commit is the owner's latest `testing` tip.
**Question:** of the 15 Oct 2026 instructor findings, what is now implemented and actually invoked, what only logs, and what is still missing.

The October evaluation (recorded in `docs/spec-integridad-referencial-labs.md` §1 and the annex): labs 2.2/5, technical correctness 4.4/10, instruction clarity 4.1/10, rework above 75% in 10 of 14 courses. There is no `AGENTS.md`. The June, July and August `*Reporte_Actividades.md` files predate that evaluation. The change log for the following month is `docs/spec-integridad-referencial-labs.md` (§11–§46), plus `docs/fase-3-borrador.md`, `docs/informe-bloqueantes-2026-10-23.md`, `docs/relevo-noche-2026-10-23.md` and `docs/traslado-curricula-2026-10-31.md`. `docs/plan-implementacion-thor-requerimientos-abril.md` is an earlier PPT/book checklist; open rows from it are noted under item 8.

## How status was judged

A check counts as **wired** only if a live Lambda or a Step Functions state calls it. It counts as **blocking** only if a failed check stops the course (or forces another attempt and then fails the lab). Logging a JSON report, printing a warning, or `Catch` → `NotifyCompletion` is a flag, not a gate.

Three facts apply to almost every lab rule:

1. High-confidence findings in the lab writer retry only while `attempt < MAX_LAB_GENERATION_ATTEMPTS` (default 3). The third text is saved even if the findings remain (`CG-Backend/lambda/strands_lab_writer/strands_lab_writer.py` lines 2518–2540).
2. The planner keeps the plan with the fewest high-confidence A1 hits and continues (`strands_lab_planner.py` lines 1078–1094). A2 quantity copy, A3 duration copy and A5 objective copy do change the saved plan; they are not log-only.
3. `CheckLabValidation` blocks only a structural defect: no H1, more than one H1, or no step heading (`CG-Backend/current_state_machine.json` lines 393–418). It does not read `validation/referential-integrity.json`. Setup Guide, link audit and decks all `Catch` into `NotifyCompletion` (lines 859–897 and 1624–1654).

## Scorecard

| # | Item | Status | % | Evidence | Gaps |
|---|---|---|---|---|---|
| 1 | Anchor generation to the syllabus | Partial | 40 | A2/A3/A5 copy before save (`94592bc4`, `a1227778`, `a4079e71`); A1/B1 retry (`f8354a04`); A6 topics in the writer prompt (`e877fe21`); B3p logged (`92d78e8b`) | Names, places and forbidden recommendations have no rule. The quoted “revisión interna de seis fondos” sentence is dropped by the instruction filter. Missing inputs become `[POR CONFIRMAR]`, not fictitious annexes. Nothing fails the course on the last attempt. |
| 2 | Time budgeting and format | Partial | 45 | B6 band 4/3 (`4070a9b0`); per-lab step/block budget in the prompt (`af35dc9f`); pre-flight warning (`63bdcf35`); outline keeps source durations (`starter_api.py` 442–445) | Practice count is not capped for a 2 h conference. Pre-flight and A3 count mismatches only print. GUI/Copilot labs with no fenced code are invisible to B6. |
| 3 | Self-contained labs | Partial | 35 | B1 on undeclared `xlsx` (high, retried); B2 forward references (`2269ca88`); THOR rule 5 asks to embed data in the prompt (`strands_lab_writer.py` 553–563) | The live prompt still orders reuse of the previous lab (`1171–1197`). B3c treats files created in an earlier lab as legitimate. `.eml` is not an extension. SharePoint paths under `/sites/` are excluded on purpose. No annex files are generated. |
| 4 | Minimal functional Setup Guide | Partial | 50 | In the state machine after labs (`060dbf74`); software no longer dropped by substring and accesses no longer cut at 12 (`acabb691`); user request copied in (`9b7f737f`); unconfirmed license/version are markers | The guide is still an OS / software / hardware inventory. B5 only retries a contradiction with the plan; if the plan invented PowerShell, the lab may keep it. A guide failure does not fail the course. |
| 5 | Verifiable validation criteria | Partial | 30 | Prompt asks for measurable evidence (`THOR_QUALITY_RULES` item 6); `unmeasurable_validation` exists (`content_validator.py` 167–169, 560–568) | The pattern only matches “% success”, “5 generic tests”, “funciona correctamente” and “listo para producción”, and it is a WARNING. Every step still requires **Expected output**. The refinement pass invents concrete passwords. The gate ignores these warnings. |
| 6 | Currency and link checks | Partial | 30 | Planner prompt: exact version or `[ENLACE OFICIAL]`, and separate Copilot / Chat / Designer / Planner (`strands_lab_planner.py` 799–801). HTTP link report (`060dbf74`, `post_generation_audit.py`) | No retrieval against Learn or any other official source. Plan My Day, Researcher, Analyst, Agent Builder, Workflows/Frontier are not named in code. Dead links are evidence, not a gate (`spec` §39.3). |
| 7 | Audience adaptation | Partial | 20 | A syllabus item marked Demo stays a demo and is framed as instructor-led (`d46d1c60`, writer demo block). One line: a 90-minute seminar should prioritise tool use | `strands_content_gen.py` never reads `audience`. Nothing adds demos or cuts theory because the course is Copilot. |
| 8 | PPT quality | Partial | 40 | Native tables with navy header and white/light rows (`html_to_ppt_styled.py` 2077–2179); duplicate-orchestration fix (`7ed78c85`); full-bleed safety-net images (`6ecc3f80`); glossary from syllabus topics plus Glosario / Tips decks (`86b1fea9`) | Definitions are cut at 250 characters and the deck holds at most 80 terms. No slide-count cap, no duplicate-content check, no black-slide check. Deck failure does not fail the course. |
| 9 | Reuse LPI-010 as a golden example | Missing | 0 | The only hit is a duration anecdote: syllabus 168 min vs plan 252 min (`spec` §20.3, line 994) | No few-shot, no fixture, no prompt example. A3 would now overwrite that duration; that is not a quality reference. |
| 10 | Evaluation form | Out of repo | 0 | The spec annex says analysts dropped “Vue Intermedio” as form tests by hand | No form, scale, N/A option, test-submission filter, or multi-evaluator store in this repository. |
| 11 | Close the loop on the critical courses | Partial | 20 | `operation: "update-contents"` is wired (`starter_api.py` 1171–1239, `dd008402`, `dd032f6`). Proven on `260223-Docker-desde-cero` (`spec` §46.3) | No run, manifest or re-score in this repo for MS-4004.1, MS-4004.2, MS-4019, MS-4004.3, AI-3025, MS-4018 or COPCHAT_LD. The written policy is that existing courses are not regenerated. |

## Overall

Weights: items 1–5 are 14 points each (70). Items 6–9 are 5 each (20). Items 10–11 are 5 each (10). Completion is the estimated percent in the scorecard.

| Item | % | Weight | Points |
|---|---:|---:|---:|
| 1 | 40 | 14 | 5.60 |
| 2 | 45 | 14 | 6.30 |
| 3 | 35 | 14 | 4.90 |
| 4 | 50 | 14 | 7.00 |
| 5 | 30 | 14 | 4.20 |
| 6 | 30 | 5 | 1.50 |
| 7 | 20 | 5 | 1.00 |
| 8 | 40 | 5 | 2.00 |
| 9 | 0 | 5 | 0.00 |
| 10 | 0 | 5 | 0.00 |
| 11 | 20 | 5 | 1.00 |
| **All 11** | | **100** | **33.50** |

**Overall: 33.5%.**

High-priority items alone are 28.0 / 70 = **40%**. Product items 1–9, ignoring the two process rows, are 32.5 / 90 = **36%**. The month of work is real and mostly on the lab pipeline. It does not yet stop the failure modes that produced the 2.2/5.

## What each recommendation does in the running pipeline

### 1. Syllabus anchor — Partial, 40%

Wired and deterministic, before the plan is saved (`strands_lab_planner.py` 1229–1345):

- **A2** `reconciliar_cantidades` replaces a changed number+noun with the syllabus figure (`referent_check.py` 2516–2572). Commit `94592bc4` (24 Oct), filter tightened in `861110cc`.
- **A3** `reconciliar_duraciones` copies each lab’s syllabus minutes onto `estimated_duration` (`2587–2624`). Commit `a1227778`.
- **A5** `reconciliar_contrato` copies the declared objective and description verbatim (`2686–2745`). Commit `a4079e71`. The writer also inserts the objective if the model rewrote it (`strands_lab_writer.py` 1511–1546).
- **A6** lesson topics are stored on the plan and printed as “do not introduce subject matter beyond them” (`e877fe21`, writer `_resumen_de_labs` around 1576–1599). A coverage marker was measured and then refused (`spec` §37, commit `6074bc0d`): a lab that covers one lesson was being scored against every topic in the module.

Wired with retry, then accepted if still wrong:

- **A1 / B1** file and path referents. High confidence only when the text presents the file as supplied by the course. Commit `f8354a04` and the calibration commits through `875cd912`. The report is `validation/referential-integrity.json`.
- **B3p** a file-shaped `expected_outcomes` entry that the lab never mentions is high confidence (`2066–2078`). `DELIVERABLES_RETRY` defaults to **off** (`strands_lab_writer.py` 92–102, commit `92d78e8b`). Omission is recorded and the lab ships.
- **C2** shells and OS named in the free-text user request are audited (`d73dae98`). A prohibition that lives only in the syllabus, with no `additional_requirements`, is not parsed.

Explicitly not built, after measurement (`spec` §32, commits `58e3dcc6` / the code was reverted before deploy):

- **Names.** “CIBEST CAPITAL” → “Northstar Digital” has no check. Proper-noun extraction marked every guide (14,670 distinct strings). The owner’s decision: do not ship it without a declared entity list.
- **Stability of figures across labs (B4).** Measured at 27–60% of courses, mostly legitimate recounts. Removed.
- **Places.** Nothing compares “El Salvador” with “Spain” or “EU”.
- **Fictitious annexes.** The level-3 behaviour is a visible marker (`[POR CONFIRMAR]`, and since `7e811661` also `[VERSIÓN POR VALIDAR]` and the rest of that family). No `.xlsx`, `.docx` or `.eml` is generated and attached.

`auditar_duraciones_curso` records a mismatch in the number of practices (`2627–2655`) and the handler only prints it (`1312–1318`). Ten historical projects had the wrong count; the spec says that is recorded, not corrected (§20.3).

### 2. Time and format — Partial, 45%

For a lab that contains fenced shell or code, the budget is real:

- `presupuesto_de_duracion` uses 2.0 min per action step and 0.75 min per block, targets 0.7 of the declared minutes, and is injected into the writer prompt as a hard limit (`referent_check.py` 1221–1252, writer 1403–1425). Commit `af35dc9f`.
- `auditar_duracion` is a high-confidence **B6** when `ceil(max(steps×2, blocks×0.75))` exceeds declared × 4/3 (`1317–1358`). `DURATION_RETRY` defaults on. Commit `4070a9b0`.
- The outline converter is told to keep a 1.5 h seminar at 90 minutes and not to inflate (`starter_api.py` 442–445).

What a 2 h conference still gets:

- One lab guide per source “Práctica / Lab / Demo”, and a repair pass that **adds** labs until the count matches the source (`starter_api.py` 340–376 and 466–472, commit `d46d1c60`). It does not remove or merge extras.
- `preflight_duracion` warns when practice minutes per lab fall under 12, or when declared lab activities exceed `duration × percent_practice` (`2300–2375`). The handler prints the warning and stores `metadata.preflight_duracion`. It does not block (`1337–1345`). There is no conference / seminar / full-course profile and no “30 min demo” budget.

GUI labs are outside B6. The function returns ok with “sin pasos de acción suficientes para comparar” when there are fewer than 3 action steps or no fenced block (`1333–1335`). `_LENGUAJES_ACCION` is shells and programming languages (`1176–1188`). A Copilot lab made of prompts is not work, as far as the rule is concerned. The owner already recorded this for M365 (`docs/traslado-curricula-2026-10-31.md` §4). The old word-count duration check remains INFO with a 20–160 words/min band (`content_validator.py` 604–627), which does not represent “17 minutes just to read”.

### 3. Self-contained labs — Partial, 35%

B1 will retry an undeclared `Ventas_MultiRegional_2024.xlsx` presented as a course input (sanity check below). The extension list (`referent_check.py` 82–85) includes `xlsx`, `docx`, `doc`, `pptx`, `pdf`. It does not include `eml`. Paths containing `/sites/` are classified as API/SharePoint and are not required (`203–207`). So the SharePoint failure mode is excluded by design, and a `.eml` the lab tells the student to open is invisible.

B2 flags a file that is an output of a **later** lab. B3c does the opposite for earlier labs: files created in a previous guide are added to `creados_antes` and then treated as known (`strands_lab_writer.py` 1144–1168, and the audit call at 2455–2459). The same handler loads the previous guide and tells the model to reuse database names, ports and directories and not to recreate them (`1171–1197`). That prompt is the dependency the instructors asked to remove.

THOR rule 5 (“embed in the prompts any information that does not require an external file”) is prompt text only, and it conflicts with the continuity block above. No component writes a fictitious data annex into the course package.

### 4. Setup Guide — Partial, 50%

`InvokeSetupGuide` runs after the lab book (`current_state_machine.json` 824–893, commits `060dbf74` and `9b7f737f`). The builder is deterministic: it consolidates outline, plan and labs, and emits `[LICENCIA POR VALIDAR]`, `[VERSIÓN POR VALIDAR]`, `[ENLACE OFICIAL]` rather than inventing them (`setup_guide_builder.py` 45–55). Commit `acabb691` stopped `build_software` from deleting “GitHub Copilot” because “git” was a substring, and removed the 12-row cap on accesses. `additional_requirements` is copied through when present (A7).

The output is still software name + version + hardware + paths. Nothing rewrites a requirement into “license, access, permission” or strips VS Code, PowerShell, a local disk path or a mandatory folder unless the syllabus named it. B5 (`1768–1849`) retries only when the lab contradicts an OS or major version the **plan** already declared. An OS the plan never mentioned is an “ampliación” at low confidence and is not retried (`2054–2063`). Circular invention (plan and lab agree on an OS the syllabus never asked for) passes. A Setup Guide exception continues to `NotifyCompletion`.

### 5. Validation criteria — Partial, 30%

The compact prompt, which is the path `generate_all_labs_batch` actually calls (line 1645), still requires **Expected output** and **Verification** on every step (lines 1335–1351). `THOR_QUALITY_RULES` item 6 says the criterion must be measurable and forbids “production-ready from five generic tests”. `validate_evidence_quality` implements a narrow WARNING (`167–169`, `560–568`). `all_valid` ignores warnings, and `CheckLabValidation` is the only consumer.

`_verify_and_refine_lab_guide` (1203–1256) runs on the live path before the referential check. If it sees `<YOUR_PASSWORD>` or `[INSERT …]` it asks the model to replace them with “real, explicit, production-ready values (e.g. `pg_password_123`, `/var/lib/app`)”. That is the opposite of “never rely on information that was not provided”.

### 6. Currency and links — Partial, 30%

The planner prompt says “verify against official documentation” and “never invent versions, licenses, capabilities or availability” (`strands_lab_planner.py` 799–801). There is no tool call, no Learn fetch, and no allow-list for Plan My Day, Researcher, Analyst, Agent Builder or Frontier. The model is on its training data. C2 checks the environment the **user typed**, not whether a Copilot button still exists (`spec` §4, C2 originally “not verifiable”).

`InvokePostGenerationAudit` writes `labguide/enlaces.json`. A link is dead only on 404, 410 or NXDOMAIN; 403/429/5xx are “not verifiable” (`post_generation_audit.py` 1–16). Templates, private IPs and XML namespaces are dropped. The state comment says it is evidence, not a gate. On the first production sample the spec records 17 real dead Learn links and does not block (§42). `vague_version` in the content validator is a WARNING (`544–557`).

### 7. Audience — Partial, 20%

Demos that the syllabus already labels as demos survive: the outline converter maps them to `type: demo` (`starter_api.py` 473–475), the planner prompt says the instructor performs them (line 805), and the writer adds the instructor-led notice. That preserves a demo. It does not create more demos, shorten theory, or cut steps because the audience is Copilot. `strands_content_gen.py` has no read of `audience` or `audiencia`. The single adaptation sentence is THOR rule 4: “for a 90-minute seminar prioritize effective tool usage”.

### 8. PPT — Partial, 40%

Since 1–8 Oct, and then again on 30 Oct:

- `7ed78c85` stops duplicate orchestrations and places images.
- `6ecc3f80` renders a safety-net image full-bleed instead of a generic bullet slide.
- `html_to_ppt_styled.py` `add_table_block` (2077–2179) builds a real PowerPoint table: header `#003366` with white text, body white or light blue. That is the current answer to “black boxes / unusable tables”, for tables that arrive as `<table class="slide-table">`. Code blocks are still a dark gradient (`html_first_generator.py` around 4885).
- `extract_glossary_entries` takes syllabus topics first, labels the source `temario` or `leccion`, and writes `book/glosario.json` (`book_builder.py` 1189 and 1210, call sites pass `max_entries=80`). Commit `86b1fea9`. `DeckBuilderFunction` builds `deck/Glosario.pptx` (4 terms per slide) and `Tips_and_Tricks.pptx`. It does not block (`current_state_machine.json` 1624–1654).
- Definitions are sliced at 250 characters (`book_builder.py` 1189) and the PPT parser adds an ellipsis at 240 (`html_to_ppt_styled.py` 243–249). The “glossary truncated” complaint is still the designed behaviour, with a source tag added.
- Nothing counts slides against course length. `course_duration_hours` exists on the infographic API; the April plan still has the row “the UI / Step Functions do not send it” (`plan-implementacion-thor-requerimientos-abril.md` §6). The 87→41 reduction is not reproduced by a cap in this code. Duplicate slide text is not checked. `overflow: hidden` is still required in the HTML layouts, so a dense slide is clipped rather than rejected.

### 9. LPI-010 — Missing, 0%

Search of prompts, fixtures and tests finds LPI-010 only as the example where a plan inflated 168 minutes to 252 (`spec` §20.3). A3 now overwrites per-lab durations from the syllabus. The course is not loaded as a few-shot, a golden file, or a scoring rubric.

### 10. Evaluation form — Out of repo, 0%

No form component, no scale definition, no “N/A” for PPT, no filter for test submissions, no table of multiple evaluations per course. The spec annex says the October analysts excluded Vue Intermedio because they were form tests. That filter lived in the analysis, not in Aurora.

### 11. Re-generation of the critical courses — Partial, 20%

The product can regenerate a chosen lesson (`MM-LL`) or lab (`MM-LL-NN`) and write `labguide/updates-manifest.json` (`starter_api.py` 1171–1239, commits `dd008402` through `dd032f6`). The only end-to-end proof in the spec is `update-260223-Docker-desde-cero-1793506341` (§46.3). The seven named courses appear as measurements (MS-4019 quantities, MS-4004-2 pre-flight, COPCHAT duration), not as update executions. `docs/informe-bloqueantes-2026-10-23.md` and `docs/traslado-curricula-2026-10-31.md` both say the project fixes future generation and does not correct the existing courses. The manifest still does not hash `lessons/` or `book/` (§46.3), so a lesson update is invisible in the diff.

## Sanity check of the failure examples

Run offline against `referent_check.py` on this commit. No model call.

| Example | Result on this code |
|---|---|
| Syllabus “El escenario consta de seis fondos multiactivo.” Plan “Trabaja con tres fondos multiactivo.” | **Stopped in the plan.** `reconciliar_cantidades` writes “6 fondos”. Covered by `test_a2_la_reconciliacion_copia_la_cantidad_del_temario` and by the live planner test `test_el_planner_reconcilia_la_cantidad_del_temario`. |
| The sentence the spec quotes from the real MS-4019 syllabus: “una revisión interna de seis fondos multiactivo” | **Not extracted.** `revisión` matches the instruction filter `revis\w*` inside the 110-character window (`referent_check.py` 2420–2445). `_cantidades` returns only `revision: 1`, and the plurality rule then ignores a 1. “análisis comparativo de tres fondos” is also dropped, because `comparativo` matches `compar\w*`. If those are the only mentions, A2 is silent. The October measurement on course `260915` still found hits, so that file had at least one “seis fondos” outside this window. The unit tests never use the quoted sentence. |
| “CIBEST CAPITAL” → “Northstar Digital”; “El Salvador” → “Spain / EU” | **Not checked.** No function compares proper names or place names. |
| Undeclared `Ventas_MultiRegional_2024.xlsx` opened from OneDrive | **B1, high confidence.** Would be retried up to 3 times, then saved if still present. |
| `caso.eml` and a SharePoint `/sites/` path | **No violation.** `.eml` is not in `_EXTENSIONES`. `/sites/` is an excluded segment. |
| “Presentación ejecutiva” / “Idea Coach” with no filename | **No B3p hit.** The same names as `Idea_Coach.pptx` are high-confidence omissions, and `DELIVERABLES_RETRY` is off, so they are logged only. |
| 15 min lab, 9 fenced steps, 36 bash blocks (the shape of the 23 Oct blockers, and of “minutes add up, steps do not”) | **B6 fails.** Minimum 27 min, ceiling 20. Budget for 15 min is at most 7 steps and 20 blocks. |
| 10 min Copilot lab, three prose steps, no fences (“17 min just to read”) | **B6 ok**, reason “sin pasos de acción suficientes”. |
| 2 h module, 25% practice (30 min), 11 labs | **Pre-flight warning only:** 2.7 min/lab, signal `poco_tiempo`. Generation continues. A3 `ok` is false when the plan has more labs than the syllabus, and the handler prints that and saves the plan. |

So: a clean “six funds / three funds” in the plan is corrected. A scenario rename, a country change, a `.eml`, a SharePoint folder, a nameless deliverable, a GUI lab that is too long to read, and eleven practices in a two-hour conference are not stopped.

## Backlog to 100%

Ordered by how much of the weighted score they move. Effort is scope, not a calendar.

| Pri | Tag | Effort | Item | Work |
|---|---|---|---|---|
| 1 | COMPLEX | Large | 1, 2, 3, 5 | After the last retry, fail the lab (or the execution) when a high-confidence A1/A2/B1/B2/B6/C2 finding remains. Point `CheckLabValidation` at that report, or raise from the writer on attempt 3. Today the tests can be green and the course still ships the bad lab. Turn `DELIVERABLES_RETRY` on only after a false-positive pass; until then, still fail file-shaped omissions that the current tests already treat as high confidence. |
| 2 | SIMPLE | Small | 1 | Stop treating `revis\w*` and `compar\w*` as instructions when they are nouns (`revisión`, `comparativo`). Add a regression test whose syllabus sentence is the §31.3 quote (“una revisión interna de seis fondos”) and whose guide says “análisis comparativo de tres fondos”. Re-measure on the corpus before widening the window: the filter exists because the naïve rule produced 146 hits. |
| 3 | COMPLEX | Large | 1 | Entity and place lock. Do not revive “any capitalised phrase missing from the syllabus” (§32: 100% of guides, 14,670 names). Require the names and places that **do** appear in the syllabus (CIBEST CAPITAL, El Salvador) to appear unchanged, and reject a different proper name in the same role. That needs a declared list or a much narrower extractor, plus a calibration set. |
| 4 | COMPLEX | Large | 2 | Format budget. Define three profiles from duration and `percent_practice`: conference (about 30 min of demo), seminar, full course. When pre-flight says `poco_tiempo` or the practice count exceeds the profile, merge or drop labs **before** generation and record which syllabus items were combined. The outline prompt currently forbids merging (`starter_api.py` 466–472), so this is a product rule, not a prompt tweak. Make the pre-flight a gate once the rule exists. |
| 5 | SIMPLE | Medium | 2 | Count GUI work. Treat a fenced prompt, a numbered Copilot instruction, and a reading-time ceiling (words in the student-facing steps) as load. Calibrate on the M365 courses, where B6 currently cannot fire. This is the “17 minutes just to read” case. |
| 6 | COMPLEX | Large | 3 | Make each lab runnable alone. Remove the “reuse the previous lab, do not recreate” prompt, or gate it on an explicit syllabus flag. Do not let B3c satisfy an input the student does not have in this chapter. When a lab needs a file the syllabus did not supply, write an annex (csv/xlsx/docx/eml) marked fictitious, and add `eml` to `_EXTENSIONES`. SharePoint inputs should be files in the package, not a `/sites/` exemption. |
| 7 | SIMPLE | Medium | 4 | Setup Guide profile “capabilities”. Emit license, access and permission. Drop OS, editor, shell, local path and folder tree unless the syllabus or `additional_requirements` names them. Keep the existing markers for anything still unknown. B5 should compare the lab to the syllabus, not only to the plan. |
| 8 | SIMPLE | Small | 5 | In the compact prompt, say that **Expected output** for an AI step is a structure or a list of required elements, never a full deterministic paragraph. Extend `UNMEASURABLE_PATTERN` to that shape. Delete or reverse the refinement instruction that invents `pg_password_123`. Promote the rule to ERROR only after a corpus count; until then it can still block inside the writer retry if the pattern is tight. |
| 9 | COMPLEX | Large | 6 | Before a lab may name a Copilot surface (Plan My Day, Researcher, Analyst, Agent Builder, Workflows/Frontier, or a button label), resolve it against current Learn (or the uploaded manual). Otherwise emit `[POR CONFIRMAR]`. Keep link checks as a report unless the URL was invented rather than copied from the manual; §39.3 is right that a moved Learn page should not fail a course by itself. |
| 10 | SIMPLE | Medium | 7 | Pass `audience` and a short-course flag into the planner and `strands_content_gen`. For Copilot titles or a seminar under a few hours: more `type: demo`, fewer steps, theory chapters that point at the demo instead of restating it. |
| 11 | SIMPLE | Medium | 8 | Paginate glossary definitions instead of cutting at 250/240 characters, or raise the cap and add a “continued” slide. Send `course_duration_hours` from the start path and cap slide count from it. Fail a slide that is a full-bleed near-black image with no text, or a table whose body cells are empty. Duplicate-title detection can be a hash of slide text. |
| 12 | SIMPLE | Small | 9 | Check in one LPI-010 outline plus its accepted lab (or a redacted slice) and inject it as a single few-shot on the planner and the writer when the syllabus is technical and fully specified. Do not fine-tune. |
| 13 | COMPLEX | Out of repo | 10 | Evaluation form: N/A for PPT, one scale, drop submissions tagged as tests, store more than one evaluation per course. Not in AuroraV1. |
| 14 | SIMPLE | Medium, operational | 11 | Re-run the seven courses with `update-contents` (or a full generation) on this baseline, then have the same instructors score them. Extend the manifest to `lessons/` and `book/` so the diff shows theory, not only labs. The API is already here; the runs are not. |

Items 2, 5, 7, 8, 10, 11 and 12 are local code plus tests. Items 1 (the gate), 3, 4, 6 and 9 need a product decision because the owner already rejected the naïve version on measured false positives. Items 13 and 14 are outside this repository’s generation pipeline; 14 can start as soon as someone lists the seven `project_folder` values.

## Test results

Offline, on this commit, 25 Nov 2026. No AWS calls and no paid model calls. `pytest` was not installed in the image; the suites that have a `__main__` runner were executed with `python3`. `xhtml2pdf` had to be installed before the five Setup Guide tests inside `test_referent_check.py` could import. Log: `/opt/cursor/artifacts/thor_offline_tests.log`.

| Suite | Result |
|---|---|
| `CG-Backend/test_referent_check.py` | **175/175** after `xhtml2pdf` was installed. First run was 170/175, all five failures `No module named 'xhtml2pdf'`. |
| `test_content_validator.py` | **15/15** |
| `test_state_machine.py` | **9/9** |
| `test_post_generation_audit.py` | **8/8** |
| `test_audit_diff.py` | **4/4** |
| `test_batch_expander.py` | **8/8** |
| `test_deck_builder.py` | **4/4** |
| `test_manual_context.py` | **19/19** |
| `test_list_projects.py` | **4/4** |
| `test_pixel_validation.py` | script completed, overflow case reported as detected |
| `test_visual_optimizer.py` | script completed, overflow detected |
| `pytest` on `test_provider_lock.py`, `test_lab_heading_normalization.py`, `test_demos_support.py`, `test_starter_api_converter.py` | **38 passed, 1 failed** |
| `test_notification.py`, `test_notification_gmail.py` | **not runnable.** Import builds a boto3 client and raises `NoRegionError`. |
| `test_bedrock_models.py`, `test_gemini_3.5.py`, `test_imagen_4.py` | **not run.** They call live models. |
| Frontend | `package.json` has `dev`, `build`, `lint`, `preview`. **No `npm test` script.** No tests under `src/`. |

The failing test is `test_convert_non_yaml_preserves_short_course_guidance`. The prompt still contains the duration sentences the test checks (“NEVER inflate…”, “1.5-hour seminar”). It no longer contains the English phrases “SAME laboratory procedure”, “NEVER create a `lessons[]` entry” and “they are NOT lessons”. Those were replaced when the outline prompt was rewritten in Spanish (`d46d1c60` and follow-ups). The test is stale; the duration rule it cares about is still in `starter_api.py` lines 442–445.

## Risks and regressions

- **Green tests, shipped defects.** Referential tests call `auditar_laboratorio` and expect a violation object. The writer then saves the lab on the third attempt. A passing suite does not mean a bad lab is rejected.
- **A2 false negative on the complaint’s own sentence.** The filter that removed 146 false hits also hides “revisión interna de seis fondos”. Tightening it without a corpus rerun will bring the noise back; leaving it means the headline example depends on a second, cleaner sentence being present.
- **Continuity vs self-contained.** B3c plus the previous-lab prompt will keep producing chapter-to-chapter file dependencies while item 3 stays open.
- **Refinement invents secrets and paths** (`pg_password_123`, `/var/lib/app`) after the quality rules told the model not to invent.
- **Non-blocking tail.** Setup Guide, link audit and decks failing still end in `NotifyCompletion`. A course can be “SUCCEEDED” with no guide, no link report and no glossary deck. That happened once for real: the first deck run died on arm64 vs an x86_64 layer and the course stayed successful (`spec` §44.3).
- **Selective update already broke normal generation once.** §46 added `lesson_ids_to_update.$` to Pass states; a normal start omitted the field and five executions died in about 90 seconds with no S3 output. `dd032f6` (this HEAD) makes the starter always send the fields. Any new `.$` field has the same failure mode. The state-machine test now reads the starter dict; that test is why 9/9 is meaningful.
- **Update diff is blind to theory.** Lessons and the book are not in the manifest (§46.3). A “successful” content update can change a lesson and show only lab hashes.
- **Plan-invented files stay in the plan.** SEM-M365 had 15 invented filenames that then appeared in labs (`spec` §43.4, `docs/traslado-curricula-2026-10-31.md` §3). A1 records high-confidence ones and does not fail the planner.
- **Glossary truncation is still shipped**, now with a source label. Reviewers can mistake “temario” for “complete definition”.
- **April PPT rows still open:** empty references slide, typography not unified across title layouts, GitHub Pages URL not passed into the lab slide, `course_duration_hours` not sent from the UI.
- **B6 cannot see the courses that scored worst.** M365 Copilot labs are GUI. The duration work is calibrated on shell-and-code labs. Applying it and declaring time “done” will not move the Copilot scores.

## Commits that carry the evidence

| Date | Commit | What it actually wired |
|---|---|---|
| 16 Oct | `f8354a04` | A1/B1 plus manual context into the writer |
| 19–21 Oct | `ee82daee`, `2269ca88`, `323f5284`, `8a7c1f19`, `92d78e8b` | B2, B3c, tool paths, B6/B5, B3p |
| 21 Oct | `a1227778` | A3 duration copy |
| 22 Oct | `a4079e71`, `b70bdb64` | A5 contract; structural gate |
| 24 Oct | `4070a9b0`, `63bdcf35`, `94592bc4`, `861110cc` | 4/3 band, pre-flight, A2, instruction-window fix |
| 24–25 Oct | `7e811661`, `acabb691` | `[POR VALIDAR]` counts; Setup Guide dedup and no 12-row cap |
| 26 Oct | `e877fe21`, `9b7f737f`, `060dbf74` | Topics to the writer; user request into the guide; guide + audit in the state machine |
| 27–28 Oct | `af35dc9f`, `d73dae98` | Duration budget in the writer; C2 environment audit |
| 30 Oct | `86b1fea9` | Glossary JSON and the two decks |
| 31 Oct–3 Nov | `dd008402` … `dd032f6` | Selective update, then the normal-start regression fix |
