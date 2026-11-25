# THOR release candidate — November 2026

Integrates the twelve open quality-fix pull requests onto `thor-audit-base` (`dd032f6`, client production testing `79b770c` plus the local audit-base commit). This branch is a release candidate. It was not deployed, and no paid AWS or LLM API was called while it was built.

Baseline and weights: `docs/audit/THOR_quality_audit_2026-11.md` (branch `cursor/thor-quality-audit-bf07`, commit `195e8190`). That document scored the October instructor findings at **33.5%**. The percents below are an estimate of how far the wired checks close those gaps. They are not a new instructor review of generated courses. Items 10 and 11 did not move.

## Merge order

Each merge is `git merge --no-ff` onto `thor-release-candidate`, which was created from `origin/thor-audit-base`. Prompts and `referent_check.py` were merged before the state machine so later prompt edits sat on one writer file. The quality gate (PR 10) landed before the link gate (PR 12) so the terminal states could be joined once.

| Order | PR | Fix | Head | Merge commit |
| --- | --- | --- | --- | --- |
| 1 | 2 | 2 instruction filter | `ab769046` | `17eb44c5` |
| 2 | 6 | 5 duration counting | `06440f81` | `e25e83c0` |
| 3 | 11 | 4 practice cap | `55143c03` | `783e9b8f` |
| 4 | 8 | 11 PPT | `8a1e1391` | `cd930c16` |
| 5 | 5 | 7 Setup Guide and `SUCCEEDED_WITH_WARNINGS` | `6326f6dc` | `ab7fe5d7` |
| 6 | 7 | 10 audience | `1c56f19a` | `887bb975` |
| 7 | 3 | 12 LPI-010 example | `7420adbf` | `6418ce7c` |
| 8 | 4 | 8 verifiable validation | `993180f8` | `4f87f602` |
| 9 | 9 | 6 self-contained labs | `4ad9cbbb` | `383405bf` |
| 10 | 13 | 3 entity lock | `676aee2c` | `10c1491c` |
| 11 | 10 | 1 quality gate | `2ba6e1e4` | `79247a4b` |
| 12 | 12 | 9 Copilot catalog and link audit | `27946ed6` | `399479e5` |

PR 5 does not add Step Functions states. It adds `SUCCEEDED_WITH_WARNINGS` in `course_generation_status.py` and keeps the Setup Guide catch non-blocking. PR 10 and PR 12 add the fail states.

The two copies of `referent_check.py` (planner and writer) are byte-identical after every merge that touched them.

## Conflicts and resolutions

PRs 2, 6, 11, 8, 5, and 7 merged clean. The writer prompt and the writer loop conflicted from PR 3 onward. Every behavior was kept.

| Merge | Files | Resolution |
| --- | --- | --- |
| PR 3 | `strands_lab_writer.py` imports | Kept `audience_adaptation` and `golden_lab_example`. |
| PR 4 | writer prompt | Kept the golden-lab section and the measurable-evidence section. |
| PR 9 | writer retry loop | Kept the evidence retry. Audits with `creados_antes=None` and adds the fictitious annex. Did not restore `creados_antes.update` (that variable is gone and would treat another lab's files as declared). |
| PR 13 | writer prompt, `master_context`, audit call, both `test_referent_check.py` | Kept the audience profile and `syllabus_text`. Kept golden, evidence, and anchor sections. Audit call uses `creados_antes=None` and `temario=outline_reference_text`. Both test blocks stayed (196 tests at that merge). |
| PR 10 | `exec_status.py`, `strands_notification.py`, writer | `needs_review` outranks a clean pass and outranks warnings. Each lab pops `validation_evidence_correction`. |
| PR 12 | writer only (ASL auto-merged) | Currency section, pop `currency_correction`, and save the referential and currency reports when the currency check raises. |

After the twelve merges, integration commit `c8cbae73` joins the behaviors that only conflict at runtime. Owner follow-ups from live QA on 25 Nov 2026, merged in `7bc00794`:

- `0bcc6104` (MS-4019): the currency check treats a surface named by the syllabus the same as one named by the manual. Deprecated catalog names still block.
- `14b4ff2e` (MS-4018): an operating system offered on the same line as an alternative to the declared one (`Windows 10/11 o macOS`) is not a B5 contradiction. A different OS alone still is. Both `referent_check.py` copies stay identical.
- `311518e9` (COPCHAT_LD): removed the function-local `import os` inside `generate_complete_course`. That import made `os` local to the whole function, so `os.environ` raised `UnboundLocalError` and every PPT batch failed.

- `clasificar_hallazgos_de_plan` treats a lab-count gap as a low-confidence warning when the format budget merged labs (`ajustado`) or a selective update still carries `syllabus_items_combined` (`conteo_preservado`), the total does not exceed the course, and `sobran == 0`. An unexplained shortfall or `excede_total` stays high-confidence A3.
- Selective regeneration counts `extract_all_labs(..., modules_to_generate="all")`, not the filtered lab list, so regenerating one lab is not "extra labs".
- `NotifyFailure` goes to `RouteTerminalFailure`. If `$.audit_result.Payload.gate.bloquea` is true the execution fails with `LinkAuditFailed`; otherwise `FailWorkflow`. `CheckLinkAudit` still goes to `NotifyFailure` first, so the failure email is sent. `FailLabQualityGate` stays `LabQualityNeedsReview`.
- Visible status order: `needs_review`, then `link_audit_failed`, then generic `failed`, then `SUCCEEDED_WITH_WARNINGS` (no error), then `passed`.
- SAM env: `COPILOT_CATALOG_RETRIEVAL=0` and `CURRENCY_RETRY=1` on `StrandsLabWriter`, `VALIDATION_EVIDENCE_RETRY=1` on `StrandsLabWriter`, `LINK_AUDIT_GATE=1` on `PostGenerationAuditFunction`. No new IAM. The functions are not in a VPC; retrieval and link checks use the existing HTTPS egress.
- UI copy is Spanish unless the caller passes a language starting with `en`.

## State machine

`CourseGeneratorStateMachine` uses `CG-Backend/current_state_machine.json`.

1. Planner and master-plan results: `quality_status == needs_review` stamps the plan, notifies, and fails with `LabQualityNeedsReview`.
2. Writer batches: `CombineLabResults` → `EvaluateLabQualityGate` → `ValidateLabContent` → `CheckLabValidation`. A writer `needs_review` takes the same notify-and-fail path. Structural H1 or step failures still go to `NotifyFailure`. Shadow mode still bypasses to `InvokeLabGuideBuilder`.
3. After a successful course body, `InvokePostGenerationAudit` → `CheckLinkAudit`. `gate.bloquea == true` goes to `NotifyFailure` → `RouteTerminalFailure` → `FailLinkAudit` (`LinkAuditFailed`). Otherwise `InvokeDeckBuilder`.
4. The Setup Guide catch records `$.setup_guide_error` and continues to `InvokePostGenerationAudit`. A labs-only course whose PDF fails still has its links checked, then the decks, unless the link gate blocks. The execution can still reach `NotifyCompletion`, and `setup_guide_error` on a SUCCEEDED run is `SUCCEEDED_WITH_WARNINGS`. An audit Lambda crash and a deck-builder crash still go to `NotifyCompletion` (`audit_error`, `decks_error`). Theory-only (`CheckIfLabsNeeded` default) still skips the link audit.
5. A currency failure is a Lambda exception inside the lab-batch map (`LabBatchFailState`), not `LabQualityNeedsReview` and not `LinkAuditFailed`. The lab is not saved. The email dumps the catch payload when it reaches `NotifyFailure`.

ASL check (Python walker, not SAM): JSON parses; 57 top-level states, all reachable; map iterators `ProcessLabBatchesInParallelBoth` (3), `ProcessBatchesInParallel` (14), and `ProcessLabBatchesInParallel` (3), all reachable. `FailLinkAudit.Error` is `LinkAuditFailed`. `FailLabQualityGate.Error` is `LabQualityNeedsReview`.

## Interactions checked

**Practice cap versus the quality gate.** A full generation that merges extra labs (anchor `lab_id` kept, `syllabus_items_combined` set) no longer fails A3 only because the lab count is shorter than the syllabus activity count. `test_el_planner_reduce_las_11_practicas` expects `quality_status == passed` with low-confidence warnings. A plan that still exceeds the course duration, or a count gap the budget did not cause, is still `needs_review`.

**Selective regeneration (`lab_ids_to_regenerate`).** The planner calls `sin_ajuste(motivo=actualizacion_selectiva)` and does not merge. The gate still runs. The duration audit uses the full syllabus, not the one-lab subset. If the stored plan was already merged, `conteo_preservado` keeps the shorter count as a warning. If the stored plan is still over the course duration (the 11 × 30 minute conference in the test), the gate returns `needs_review` with an A3 duration finding. The writer does not skip those labs: the starter sets `update_mode`, which disables skip-if-exists. The state machine does not skip `CheckLabValidation`.

**Annex versus the gate.** An annexable high-confidence B1 (xlsx, docx, eml, csv, SharePoint `/sites/`) is inlined on the attempt that ships and then re-audited, so the gate can pass. B6, A5, C2, and A2e stay `needs_review`. Forward dependencies are not annexed.

**Frontend.** There is no in-app language switch. Helpers default to Spanish. English is the `lang` argument when it starts with `en`.

| Status or HTTP | Spanish (default) | English |
| --- | --- | --- |
| `needs_review` | NECESITA REVISIÓN. "El curso no se entregó: hay laboratorios con hallazgos de alta confianza que necesitan revisión." | NEEDS REVIEW |
| `SUCCEEDED_WITH_WARNINGS` | COMPLETADO CON ADVERTENCIAS, naming Setup Guide, Auditoría posterior, or Decks | COMPLETED WITH WARNINGS |
| `link_audit_failed` / `LinkAuditFailed` | ENLACES ROTOS. "El curso no se entregó: hay enlaces públicos muertos (404, 410 o DNS)." | BROKEN LINKS |
| PPT export 422 | "La presentación no se exportó. El deck no pasó el control de calidad." plus up to three issue messages | "The presentation was not exported. The deck did not pass the quality check." |

`InfographicViewer` throws that message instead of the API string `PPT quality validation failed`. `GeneradorContenido` treats `needs_review` and `link_audit_failed` as errors, and `SUCCEEDED_WITH_WARNINGS` as a success banner (tone warning), not a clean pass.

## Live QA fixes

Four gaps from the 25 Nov 2026 run on this head. None of them called a paid API, and nothing here was deployed.

1. **Reading budget.** Student-facing prose is capped at `LAB_READING_WORDS_PER_MINUTE` (default 60) times the declared duration. A student reads technical Spanish at about 200 words per minute (`LAB_READING_SPEED_WPM`), so 60 words per minute is 30% of the slot and leaves most of the time for doing the lab. A 12-minute lab may contain 720 words of prose (about 4 minutes of reading). A 55-minute lab may contain 3,300. The fictitious-data annex is counted apart, fences included, under `LAB_ANNEX_MAX_WORDS` (default 500). The writer prompt states the ceilings. After generation, while attempts remain and `READING_BUDGET_RETRY` is on, the writer is asked again with the measured counts. The last attempt records R1 at medium confidence and still ships the lab. The quality gate blocks only on high confidence, so this is a warning, not `needs_review`. A lab with no declared duration is told to stay under 1,200 words.
2. **Setup Guide PDF.** The lab cell is the lab id plus the title, truncated to about 60 characters. Every matrix cell is a reportlab Paragraph measured against an explicit column width (the eight widths sum to 420 pt, inside the A4 frame after padding). Estado inicial drops markdown table syntax. Evidencia is a short summary, not a pasted prompt. `render_pdf` raises on `LayoutError`, a pisa error, or a buffer that is not a PDF, so Step Functions keeps `setup_guide_error` and the client status is `SUCCEEDED_WITH_WARNINGS` when the rest of the run succeeds.
3. **Labs-only link audit.** The happy path already visited `InvokePostGenerationAudit`. The hole was the Setup Guide catch, which jumped to `NotifyCompletion` and skipped the audit. That catch now goes to the audit. `CheckLinkAudit` is unchanged. Every top-level state stays reachable. Theory-only still does not audit links.
4. **Dead-link repair.** Before the gate blocks, each 404/410/NXDOMAIN URL is replaced with the closest verified URL from the Copilot catalog (deprecated rows skipped), the manual, or the syllabus. An exact path, ignoring locale, outranks an alias. If nothing verified is close enough, the URL is removed and the anchor text stays. The labs are audited again. The gate blocks only when the second report still has dead links. `LINK_REPAIR=0` keeps the old block-on-first-report behavior. A repair exception keeps the first report, so the gate still runs. Offline tests inject `revisar_enlace` and do not call `urlopen`. `FailLinkAudit` and the failure email point at `labguide/enlaces.json`.

## Bigger gaps (not closed here)

- Item 10, the evaluation form, is still outside this repository.
- Item 11: the seven critical courses were not regenerated or re-scored. The manifest is still blind to lessons and the book.
- Measurable-evidence findings retry, and the last attempt still ships. They are not referential violations, so they do not enter the quality gate. `ContentValidator` still records them as WARNING. It also warns when a lab is under 1,000 words, so a 12-minute lab inside the 720-word reading budget can carry that warning. `CheckLabValidation` does not block on it.
- Currency failures are a generic batch task failure. They do not get their own Step Functions error name.
- A reading overrun that survives the last attempt ships as a medium R1 warning. It does not set `needs_review`.
- A Setup Guide PDF failure stays non-blocking (`SUCCEEDED_WITH_WARNINGS`). The link audit and the decks still run unless the link gate blocks.
- Theory-only courses still skip the link audit.
- Selective update does not re-apply the format cap, and it does not re-apply the reading budget to a lab that is not regenerated. A legacy over-budget plan cannot be patched one lab at a time until a full plan fits.
- `COPILOT_CATALOG_RETRIEVAL` is off. Link repair uses the checked-in catalog (`2026-11-25.1`) plus URLs already in the manual or the syllabus, and only keeps a replacement the injected checker calls alive. A dead link that has no close verified replacement is removed. The course still fails if a dead link remains after that one pass. 403/429/5xx stay unverifiable and do not block.
- The LPI-010 fixture is a structural stand-in in the writer prompt only. The planner prompt does not include it.
- `DELIVERABLES_RETRY` stays off. A high-confidence B3p still blocks through the quality gate; it just does not get an extra model retry unless the flag is turned on.
- April PPT leftovers outside the pagination and empty-table checks (typography, the GitHub Pages URL, `course_duration_hours` taken from the UI) were not re-verified on a generated deck.

## Environment variables and flags

| Name | Where | Default | Effect |
| --- | --- | --- | --- |
| `LINK_AUDIT_GATE` | `PostGenerationAuditFunction` | `1` | `0` keeps dead links in the report and sets `gate.bloquea` false. |
| `LINK_REPAIR` | `PostGenerationAuditFunction` | `1` | Before the gate blocks, replace a dead URL from the catalog, manual, or syllabus, or drop the URL and keep the text, then re-audit. `0` blocks on the first report. |
| `READING_BUDGET_RETRY` | `StrandsLabWriter` | `1` | Over-budget prose retries with the measured counts. `0` records a medium finding and ships. The last attempt never fails the lab for length. |
| `LAB_READING_WORDS_PER_MINUTE` | `StrandsLabWriter` | `60` | Student-facing words allowed per declared minute. 60 of a 200-word reading speed is 30% of the slot. |
| `LAB_READING_SPEED_WPM` | `StrandsLabWriter` | `200` | Reading speed used to explain the budget. It is not the budget. |
| `LAB_ANNEX_MAX_WORDS` | `StrandsLabWriter` | `500` | Cap for the fictitious-data annex. Counted apart from the body, fences included. |
| `COPILOT_CATALOG_RETRIEVAL` | `StrandsLabWriter` | `0` | `1` refreshes the catalog from Microsoft Learn before the currency check. |
| `CURRENCY_RETRY` | `StrandsLabWriter` | `1` | Blocking Copilot names retry. On the last attempt the lab is not saved and the batch fails. `0` records the finding and ships the lab. |
| `VALIDATION_EVIDENCE_RETRY` | `StrandsLabWriter` | `1` | Retries a lab whose validation steps are not measurable, until the last attempt, which still ships. |
| `DELIVERABLES_RETRY` | writer code, not in the template | `0` | Extra model retry for deliverable findings. Off. |
| `REQUIREMENTS_RETRY` | writer (pre-existing) | `1` | Unchanged. |
| `ENTORNO_RETRY` | writer (pre-existing) | `1` | Unchanged. |
| `LAB_SKIP_IF_EXISTS` | `StrandsLabWriter` | `true` | Unchanged. Disabled when `update_mode` or `force_regenerate` is set. |

The quality gate and the format budget have no off switch. Turning them off means redeploying the previous state machine and planner.

## Deployment checklist

Do not deploy this branch until it is reviewed. This run did not deploy.

From `CG-Backend`, on a machine with AWS credentials, SAM CLI, and the Netec profile used by `samconfig.toml`:

1. Confirm `samconfig.toml`: stack `crewai-course-generator-stack`, region `us-east-1`, `CAPABILITY_IAM`.
2. `powershell -ExecutionPolicy Bypass -File deploy.ps1` runs the PDF layer hash check, then `sam build`, then `sam deploy --no-confirm-changeset`. Use `-SkipDeploy` to rebuild the layer without deploying. Use `-ForceLayerRebuild` only if the PDF layer must be republished; `lambda-layers/pdf_layer/requirements.txt` did not change in this candidate.
3. `sam build` without Docker builds layers for x86_64. The PDF layer is the prebuilt aarch64 zip. Do not replace it with the `sam build` output.
4. The state machine definition is `current_state_machine.json` (`DefinitionUri`). A deploy updates `CourseGeneratorStateMachine` in place.
5. After deploy, confirm the flags in the table above on the live Lambdas before generating a client course. New on this pass: `READING_BUDGET_RETRY`, `LAB_READING_WORDS_PER_MINUTE`, `LAB_READING_SPEED_WPM`, `LAB_ANNEX_MAX_WORDS`, and `LINK_REPAIR`.
6. Generate one short non-client course and read `/exec-status`: a clean run is `passed`; a high-confidence lab finding is `needs_review` with error `LabQualityNeedsReview`; a dead link that repair cannot clear is `link_audit_failed` and the email points at `labguide/enlaces.json`; a Setup Guide or deck error on an otherwise successful run is `SUCCEEDED_WITH_WARNINGS`.
7. Export a deck that fails `ppt_quality` and confirm the UI shows the Spanish 422 text, not `PPT quality validation failed`.

### Rollback

Redeploy commit `dd032f6` (`thor-audit-base`) with the same `deploy.ps1`. That restores the previous template and the previous state machine. There is no flag that disables `LabQualityNeedsReview`.

To soften the new gates without a full rollback, set `LINK_AUDIT_GATE=0`, `CURRENCY_RETRY=0`, and `VALIDATION_EVIDENCE_RETRY=0`, and leave `COPILOT_CATALOG_RETRIEVAL=0`. The quality gate and the format budget stay on until the previous revision is deployed.

## Tests

Re-run on 2026-11-25 after the live-QA fixes, Python 3.12, Node 22. Credentials unset. `AWS_DEFAULT_REGION=us-east-1`, `AWS_EC2_METADATA_DISABLED=true`. Offline suite exit 0 for every file below. Frontend `npm ci` and `npm run build` exited 0.

Not run, because they call Lambda, Bedrock, Gemini, Imagen, or send mail: `test_bedrock_models.py`, `test_gemini_3.5.py`, `test_imagen_4.py`, `test_notification.py`, `test_notification_gmail.py`.

SAM CLI is not installed in this environment, so `sam validate` was not run. The ASL check above is the substitute.

| Suite | Result |
| --- | --- |
| `test_audience_adaptation.py` | 8/8 |
| `test_audit_diff.py` | 4/4 |
| `test_batch_expander.py` | 8/8 |
| `test_content_validator.py` | 17/17 |
| `test_copilot_currency.py` | 17/17 |
| `test_course_generation_status.py` | 3/3 |
| `test_deck_builder.py` | 4/4 |
| `test_demos_support.py` | pytest 11 passed |
| `test_format_budget.py` | 19/19 |
| `test_golden_lab_example.py` | 4/4 |
| `test_lab_heading_normalization.py` | pytest 2 passed |
| `test_list_projects.py` | 4/4 |
| `test_manual_context.py` | 19/19 |
| `test_measurable_evidence.py` | 6/6 |
| `test_no_import_shadowing.py` | 1/1 |
| `test_pixel_validation.py` | script OK |
| `test_post_generation_audit.py` | 18/18 |
| `test_ppt_quality.py` | 8/8 |
| `test_provider_lock.py` | pytest 16 passed |
| `test_quality_gate.py` | 10/10 |
| `test_reading_budget.py` | 6/6 |
| `test_referent_check.py` | 198/198 |
| `test_setup_guide_capabilities.py` | 6/6 |
| `test_setup_guide_pdf.py` | 3/3 |
| `test_starter_api_converter.py` | pytest 10 passed |
| `test_state_machine.py` | 14/14 |
| `test_visual_optimizer.py` | script OK |
| `src/utils/courseStatus.test.mjs`, `pptExportMessage.test.mjs` | node:test 8/8 |
| `npm run build` | exit 0 |

## Updated scorecard

Weights are unchanged (items 1–5 at 14, items 6–11 at 5). Points = percent × weight / 100. The October baseline is in parentheses.

| # | Item | Baseline | Estimate | Weight | Points | What is still open |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Syllabus anchor | 40% | 78% | 14 | 10.92 | A2e only locks labeled entities. No corpus re-score. Last-attempt evidence gaps still ship. |
| 2 | Time and format | 45% | 88% | 14 | 12.32 | Reading budget is 60 words per declared minute (30% of a 200 wpm read). The annex has its own 500-word cap. The last attempt still ships a medium R1. The step budget is unchanged. Selective update does not re-cap a legacy plan. |
| 3 | Self-contained labs | 35% | 82% | 14 | 11.48 | Annex covers xlsx, docx, eml, csv, and SharePoint. Forward dependencies are not annexed. |
| 4 | Setup Guide | 50% | 80% | 14 | 11.20 | The lab cell is the id plus a title of about 60 characters, and cells wrap inside the frame. A PDF layout failure is `SUCCEEDED_WITH_WARNINGS` and no longer skips the link audit. The failure stays non-blocking. B5 still compares the lab with the plan. |
| 5 | Verifiable validation | 30% | 68% | 14 | 9.52 | Retry is on. The last attempt does not fail the course. The validator stays WARNING. |
| 6 | Currency and links | 30% | 86% | 5 | 4.30 | Dead links are repaired from the catalog, manual, or syllabus, then re-audited. The gate blocks only if a dead link remains. Labs-only courses are audited even when the PDF fails. Theory-only still skips the audit. Retrieval stays off. Currency failure is a generic batch error. |
| 7 | Audience | 20% | 65% | 5 | 3.25 | Prompt and duration scales for Copilot and short courses. Not a structural rewrite of theory into demos. |
| 8 | PPT | 40% | 70% | 5 | 3.50 | Pagination, cap, empty and duplicate rejection, 422 in the UI. The `import os` crash is fixed. A deck-builder crash is still non-blocking. |
| 9 | LPI-010 | 0% | 50% | 5 | 2.50 | Writer few-shot only, on a stand-in fixture. Planner prompt unchanged. |
| 10 | Evaluation form | 0% | 0% | 5 | 0.00 | Out of repository. |
| 11 | Close the loop | 20% | 20% | 5 | 1.00 | No new runs of the seven courses. |

**Overall: 69.99 / 100 = 70.0%** (baseline 33.5%, previous candidate estimate 67.2%).

High-priority items 1–5: 55.44 / 70 = 79.2% (baseline 40%, previous estimate 76.0%).

Product items 1–9: 68.99 / 90 = 76.7% (baseline 36%, previous estimate 73.6%).

Items 2, 4, and 6 moved for the live-QA fixes above. This is still an estimate of wired checks, not a new instructor review.

## What blocks a production deploy

- This candidate is not deployed. Deploy only after review, with `CG-Backend/deploy.ps1` against `crewai-course-generator-stack`.
- `sam validate` and `sam build` were not run here. SAM CLI is not installed in the environment that built the branch.
- `LINK_AUDIT_GATE=1` still fails a course when a public 404/410/NXDOMAIN remains after one repair pass. `LINK_REPAIR=1` replaces that URL from the catalog, the manual, or the syllabus, or removes it. `CURRENCY_RETRY=1` still fails a lab whose Copilot surface is missing from the snapshot and not named by the manual or the syllabus.
- A selective content update of a plan that is still over the format budget now stops at `needs_review`. Those courses need a full regeneration so the planner can merge labs.
- The quality gate cannot be disabled with an environment variable. Rollback is a redeploy of `thor-audit-base`.
- Item 10 is still open, and item 11 has no new generated evidence. The 70.0% figure is the estimate in the table above.
- To soften the reading budget without a rollback, set `READING_BUDGET_RETRY=0` (the overrun is recorded and the lab still ships) or raise `LAB_READING_WORDS_PER_MINUTE`. To restore block-on-first-dead-link, set `LINK_REPAIR=0`.
- Live QA on 25 Nov 2026 is already on this head: the syllabus authorizes named Copilot surfaces (`0bcc6104`), an alternative OS on the same line is not a B5 block (`14b4ff2e`), and the `import os` that crashed every deck is gone (`311518e9`). Those three are not remaining blockers.
