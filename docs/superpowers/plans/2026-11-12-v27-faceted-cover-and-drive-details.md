# V27 Faceted Cover and Drive Detail Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the V27 planar cover into a six-sided stepped armor style and deliver CAD-derived motor, coupling, shaft, seal, and spool detail views.

**Architecture:** Keep the existing twelve panel solids and all mechanism placement fixed. Add four shallow exterior hex bands and clipped-corner surrounds fused to cover panels. Extend the current CadQuery/matplotlib renderer with a labelled, three-view drive detail sheet. Regenerate STEP, PNG, README, and the SHA-256 manifest from the current V27 generator.

**Tech Stack:** Python 3.12, CadQuery 2.8.0, matplotlib, unittest.

**Spec:** `docs/superpowers/specs/2026-11-12-v27-faceted-cover-and-drive-details-design.md`

## Global Constraints

- Work in `feat/v27-modular-m2006` and preserve its current uncommitted single-piece root-guard changes.
- Keep 12 flat cover panels, 2.4 mm panel thickness, Z split at -80 mm, and existing aperture clear dimensions.
- Keep 332 mm maximum cover diameter, within the 350×350 mm print platform.
- Added band and window-surround geometry must project outward from the current panel surface.
- Preserve all motor, shaft, gear, bearing, seal, spool, tendon, electronics, root-interface, and module-removal geometry.
- Keep the cover floodable; it is not a pressure boundary.
- Do not edit the existing untracked `.tmp_v27_docx_preview/` directory.

## Review Focus

- Exterior bands must meet the panel surfaces and retain the original panel fastener axes.
- Window surrounds must not narrow the three motor, three inspection, or Type-C apertures.
- The 332 mm cover envelope must fit the 350 mm printer bed.
- Motor and spool detail views must depict the current CAD component ownership and shaft directions accurately.
- Labels must identify gear teeth, seal performance, and the official M2006 solid model as unverified proxies where applicable.

---

### Task 1: Six-sided cover styling

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`

**Interfaces:**
- Consumes: current V27 `root_cover` dimensions and `fixed_root_guard_hex` implementation.
- Produces: four visible exterior polygon bands plus clipped-corner surrounds integrated into the existing service panels.

- [x] **Step 1: Add failing assertions**

Test that the cover still contains 12 panels, that four external band shapes are present and valid, that the largest band diameter is 332 mm, and that the motor/inspection/Type-C aperture probes remain open after adding surrounds.

- [x] **Step 2: Run the focused cover tests and confirm the new assertions fail**

Run: `& 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe' -X utf8 -m unittest test_root_cover.V27RootCoverTests -v`

Expected: FAIL because the armor bands and surrounds are not yet implemented.

- [x] **Step 3: Implement bands and surrounds**

Set the frame outer circumradii to `[102, 166, 166, 166]` mm with 4 mm radial thickness, preserving the current inner mating radii. Add an 8 mm-wide, 2.5 mm-proud clipped-corner surround to each of the seven openings, fused to its existing panel without shrinking the current opening.

- [x] **Step 4: Run the focused cover tests**

Run: `& 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe' -X utf8 -m unittest test_root_cover.V27RootCoverTests -v`

Expected: PASS; panel count, opening clearances, and bed envelope remain within the specified values.

### Task 2: Mechanical detail-sheet rendering and release artifacts

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27传动轴套轴封齿轮与包覆复核.md`
- Regenerate: V27 cover/full-assembly STEP and PNG review images plus `来源与SHA256.csv` in the same directory.

**Interfaces:**
- Consumes: completed cover solids from Task 1 and current drive component names from `V27AssemblyResult`.
- Produces: `V27_传动系统细节图.png` with three CAD views: M2006/D6 sleeve and removable pin; 90-degree gear pair and D8/D10 shaft; paired 6900 bearings, twin seal/labyrinth boundaries, wet spool, and straight tangent tendon.

- [x] **Step 1: Add an integration assertion for the new detail image**

Assert `render_v27()` returns the named detail image, the image is at least 1600×900 pixels, and its visible labels plus README retain the gear-tooth and seal verification limits.

- [x] **Step 2: Run the focused integration test and confirm it fails**

Run: `& 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe' -X utf8 -m unittest test_v27_integration.V27IntegrationTests.test_review_images_are_nonempty -v`

Expected: FAIL because the detail-sheet key is not yet returned.

- [x] **Step 3: Render, document, and regenerate**

Add the three-view detail sheet using the current component solids and actual contract values. Label M2006 body geometry, KHK gears, and rotary seals as envelope/candidate representations where appropriate. Update README cover description and detail-image links. Run the V27 assembly generator to refresh STEP, audit, and images, then refresh `来源与SHA256.csv`.

- [x] **Step 4: Run the complete V27 suite**

Run: `& 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe' -X utf8 -m unittest discover -s . -p 'test_*.py' -v`

Expected: PASS, including no forbidden collisions, all tendon routes, and both module extraction paths.

- [x] **Step 5: Commit the scoped result**

```powershell
git add docs/superpowers/specs/2026-11-12-v27-faceted-cover-and-drive-details-design.md docs/superpowers/plans/2026-11-12-v27-faceted-cover-and-drive-details.md local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006
git commit -m "feat(v27): refine cover and render drive details"
```

### Task 3: Independent geometry review corrections and clone-complete package

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: the V27 cover/integration tests, README, review note, generated STEP/PNG/audit/hash manifest.

- [x] Replace the constant-radius lower band with a profile-following loft and notch its Type-C side under the tall service surround.
- [x] Increase radial window reveal from 0.5 mm to 1.5 mm per side while preserving the 8 mm border; test a 30 mm deep near-full gauge.
- [x] Regenerate CAD and imagery, run the complete V27 test suite (98/98 PASS), reconcile every hash-manifest path with Git (111/111 tracked), and obtain a fresh independent review (no material geometry issue found).
- [x] Commit the corrected geometry and force-add only the 16 V27 manifest-listed paths hidden by the repository `local/` ignore rule; do not add unrelated local files.
