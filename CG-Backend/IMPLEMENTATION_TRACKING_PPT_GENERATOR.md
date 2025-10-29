# PPT Generator — Implementation Tracker

This document records progress, goals, verification steps, and a clear roadmap to complete the PPT generator improvements.

## Objectives (what we must achieve)
1. Titles centered consistently across slide types (title, content, image, summary) with professional typography and spacing.
2. Images must never overwhelm or overlap text — the generator must resize/crop images and choose adaptive layouts so text remains readable.
3. Robust image handling: support S3 and HTTP sources, in-memory caching, retries, and graceful fallback to a professional placeholder when the image is unavailable.
4. Adaptive layouts: automatically choose text-only, image-only, split-top, or split-right layout based on text length and image aspect ratio/size.
5. Professional, consistent style: fonts, color palette, bullet limits, spacing, and hierarchy tuned for corporate training (three style presets: professional, educational, modern).
6. Test coverage and automation: unit tests for image manager and layout decisions, and a CI smoke test that generates a PPTX artifact.
7. Easy QA & observability: deterministic placeholder tagging and logging so test tooling and operators can detect placeholders and image failures.

## Success criteria (measurable)
- Title centering: 100% of generated title elements across sample slides must have centered paragraphs/shape alignment.
- No overlap: Generated slides should have zero overlapping bounding boxes between text and images in >95% of automated checks across sample inputs.
- Placeholder fallback: When an image fails to download, generator inserts either a placeholder picture or a clearly tagged placeholder shape; test harness must detect this reliably.
- Adaptive layout: For a set of 10 representative lessons (short/medium/long text + wide/tall images) the layout decision must produce readable slides with correct layout in at least 90% of cases.
- Tests: Unit tests for `image_manager` (download/resize/placeholder) and layout decision logic must pass in CI.

## Work completed (summary)
- Center titles and subtitles across slide types via `center_shape_horizontally` in `strands_ppt_generator.py`.
- Implemented `image_manager.py` with:
  - S3/HTTP fetch (`fetch_image_bytes`), image size probe (`get_image_size_from_bytes`), resize (`resize_image_bytes`) and placeholder PNG generation (`create_placeholder_image`).
- Integrated in-memory `image_cache` to avoid redundant downloads during a run.
- Added unit tests for `image_manager` and validated locally (tests passing).
- Added adaptive layout heuristics (word-count thresholds, aspect-ratio rules) and integrated into slide rendering.

## Verification performed
- Ran `CG-Backend/test_ppt_layout.py` — produced `CG-Backend/test_layouts.pptx` for visual checks.
- Executed harnesses to generate `CG-Backend/test_mixed_images.pptx` and `CG-Backend/test_s3_images.pptx`.
  - Confirmed S3 images from `crewai-course-artifacts/251026-Cisco-03/images/` download and are inserted.
  - Confirmed missing S3 keys fall back to placeholder shapes.
- Ran pytest on `CG-Backend/lambda/strands_ppt_generator/tests/test_image_manager.py` — passing locally.

## Files added/changed (most important)
- Modified: `CG-Backend/lambda/strands_ppt_generator/strands_ppt_generator.py` — generator, layout rules, centering helper, image insertion flow.
- Added: `CG-Backend/lambda/strands_ppt_generator/image_manager.py` — robust image helpers and placeholder generation.
- Added tests: `CG-Backend/lambda/strands_ppt_generator/tests/test_image_manager.py`.
- Added harness scripts: `CG-Backend/test_ppt_mixed_images.py`.

## Current constraints / observations
- Outbound HTTP may be restricted in some environments; S3 retrieval worked in this environment when credentials allowed it.
- Placeholder fallback is currently implemented as either a generated PNG (inserted as a picture when possible) or a drawn rectangle/text shape as a final fallback.
- Placeholder detection in tests was enhanced by both checking picture average color and auto-shapes with placeholder-like fills/text; this was necessary because placeholders can be shapes or images depending on path taken.

## Prioritized next steps (I will implement in this order)
1. Deterministic placeholder tagging (quick, high impact)
   - When creating a placeholder (picture or shape) tag it with `shape.name = 'aurora_placeholder'` and add a note or append ` [PLACEHOLDER]` to the text. This makes detection exact for QA and CI.
   - ETA: 0.5–1 hour.

2. Prefer placeholder-as-picture for visual consistency (small code change)
   - Use `image_manager.create_placeholder_image()` to generate PNG bytes and insert via `add_picture()` rather than drawing a rectangle. Keeps placeholders consistent with images and simplifies layout handling.
   - ETA: 1–2 hours.

3. Add deterministic tests & CI smoke job (medium)
   - Unit tests for layout decision (word counts, aspect ratios) and integration test that produces a PPTX containing at least one real image and one placeholder.
   - Add a CI job (GitHub Actions) that runs tests and produces the PPTX artifact (optional upload to workflow artifacts).
   - ETA: 3–6 hours.

4. Overlap detection and text reflow (medium)
   - Implement a function to detect bounding-box overlaps after placing shapes. If overlap detected, shrink text area font size or move to a new slide.
   - ETA: 4–8 hours.

5. Finish Layout Decision Engine & Text Analyzer (medium)
   - Improve heuristics and add simple summary/split logic (word-count based) or call a light text-summarization routine to keep bullet counts within limits.
   - ETA: 6–12 hours.

6. Aesthetic polish & configuration (low)
   - Centralize theme (fonts/colors), finalize bullet styles, and create an easy style switcher.
   - ETA: 4–8 hours.

## Quick reproducible commands (from repo root)
```bash
# optional: create venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r CG-Backend/requirements.txt

# run image manager tests
pytest -q CG-Backend/lambda/strands_ppt_generator/tests/test_image_manager.py

# generate sample PPTX using S3 images (requires AWS credentials with read access to the bucket)
python3 - <<'PY'
from importlib import util
spec = util.spec_from_file_location('spg', 'CG-Backend/lambda/strands_ppt_generator/strands_ppt_generator.py')
spg = util.module_from_spec(spec)
spec.loader.exec_module(spg)
presentation_structure = {
  'presentation_title':'S3 Images Test','style':'professional','slides':[
    {'slide_type':'title','title':'S3 Images Test','subtitle':'Using S3 images'},
    {'slide_type':'image','title':'S3 Image 1','image_url':'s3://crewai-course-artifacts/251026-Cisco-03/images/01-01-0001.png','caption':'S3 image 01-01-0001.png'},
  ]
}
open('CG-Backend/test_run.pptx','wb').write(spg.generate_pptx_file(presentation_structure, {}))
PY
```

## Acceptance checklist (trackable)
- [x] Center titles across slide types
- [x] Implement image_manager with fetch/resize/placeholder
- [x] In-memory per-run image cache
- [x] Unit tests for image_manager (local)
- [ ] Deterministic placeholder tagging (next)
- [ ] Placeholder-as-picture option (next)
- [ ] Layout decision tuning and overlap detection
- [ ] CI job and integration test

---

Tell me which of the prioritized next steps you want me to implement first (I recommend deterministic placeholder tagging -> placeholder-as-picture -> CI/test), and I will update this tracker and implement it.

