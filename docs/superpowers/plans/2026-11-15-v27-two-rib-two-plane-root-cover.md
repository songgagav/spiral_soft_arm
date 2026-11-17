# V27 Two-Rib, Two-Plane Root Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the V27 root cover to use the approved lower-vertical/upper-tapered two-plane profile, two continuous external ribs, and four preserved fastener rows with inner support pads at the two middle rows.

**Architecture:** Keep fastener-row heights separate from raised-rib heights in the cover contract. Build only the bottom and top continuous ribs; build discrete inward-facing pads at the two middle M3 rows, then generate the same removable panels and service openings. Update the assembly audit and renderer to report and show the new geometry before regenerating the STEP, review images, JSON audits, and hash manifest.

**Tech Stack:** Python 3.12, CadQuery 2.8.0, `unittest`, V27 assembly/render scripts.

**Spec:** `docs/superpowers/specs/2026-11-14-v27-upper-small-lower-large-cover-design.md`

## Global Constraints

- Cover bounds stay at Z=-236…64 mm; panel split stays at Z=-80 mm.
- Main profile stations are `[-236,162]`, `[-80,162]`, `[37,162]`, `[56,133.148]`, and `[64,121]` (Z in mm, circumradius in mm). The lower wall stays vertical through Z=37; the single upper taper starts 1 mm above the drive pod maximum Z=36 and reaches the 250 mm top-plate outer radius at Z=64.
- Continuous raised ribs remain only at Z=-232 mm and Z=60 mm, each 8 mm high and 4 mm radial projection.
- Fastener rows remain at Z=[-232,-84,-76,60] mm, with 48 M3 Ø3.4 mm holes and tangent offsets ±35 mm.
- Middle rows use 24 local inner pads, nominally 12 mm tangential width × 8 mm height × 4 mm inward thickness; the 2.1 mm outer head recess must leave at least 4.3 mm nominal material through the supported pad region.
- Panel thickness remains 2.4 mm; six upper panels, six lower service panels, 4 mm panel edge gap, and existing windows remain.
- The top plate remains at the currently assumed Ø250 mm vertex-to-vertex outer diameter (circumradius 125 mm); verify overlap at the upper taper.
- Observation openings change from three 54×42 mm windows on lower faces 1/3/5 to two 110×80 mm windows on opposing lower faces normal=30°/210°, both centered at Z=-150 mm. Motor and M12 windows remain unchanged.
- Keep the existing 8 mm window-surround width, 2.5 mm proud height, 5 mm corner clip, and 1.5 mm reveal; the proposed large observation-window surround is about 129×99 mm.
- Printer build volume remains 350×350×320 mm. The flooded cover is not a pressure boundary.

## Review Focus

- A middle support pad fails to fuse to a panel or leaves insufficient material below the Ø8×2.1 mm head recess; test pad volume and residual wall thickness in `test_root_cover.py`.
- The two middle rows remain reachable by the 8 mm tool envelope; test access at all four rows in `test_root_cover.py` and the audit in `test_v27_integration.py`.
- A 12×8×4 mm inner pad intersects electronics, motors, or wiring; test forbidden assembly intersections in `test_v27_integration.py`.
- A 110×80 mm observation window leaves inadequate panel margins or conflicts with M3 rows, the M12 service window, or the motor windows; test opening placement and remaining panel material in `test_root_cover.py` and assembly collisions in `test_v27_integration.py`.
- The upper taper and top rib overlap or exceed the assumed Ø250 mm top plate interface; test the generated cover bounds and top interface in `test_v27_integration.py`.
- The taper intrudes into the M2006 bevel pods, bearings, wet spools or cartridge service paths; the initial steep taper from Z=-80 produced these collisions, so preserve a vertical wall through the full drive package and re-run complete collision and removal sweeps.
- Inner pads obstruct lower-panel extraction or the 280 mm drive-module removal path; test both service sweeps in `test_v27_integration.py`.

---

### Task 1: Separate raised ribs from fastener support geometry

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`

**Interfaces:**
- Consumes: `contract.integration["root_cover"]`.
- Produces: `RootCoverResult.raised_rib_centers_mm` with `(-232.0, 60.0)` and `RootCoverResult.fastener_row_centers_mm` with `(-232.0, -84.0, -76.0, 60.0)`.

- [x] **Step 1: Add failing tests for the new cover contract**

Add tests asserting the exact profile stations, two continuous rib centers, four fastener-row centers, 24 middle inner pads, 48 fastener holes, two 110×80 mm observation openings on opposing lower panels, and valid single-solid removable panels. Assert that a section probe finds continuous external rib material only at Z=-232 and Z=60, and finds inner-pad support material at Z=-84 and Z=-76. Assert that observation-window outer surrounds remain within the lower-panel face and clear the M12 window and fastening rows.

- [x] **Step 2: Run the focused cover tests and confirm the new assertions fail**

Run from the assembly directory:

```powershell
$py = 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe'
& $py -X utf8 -m unittest test_root_cover -v
```

Expected: the new raised-rib/pad assertions fail against the four-rib baseline.

- [x] **Step 3: Update the cover contract and `build_root_cover`**

Replace the coupled `frame_z_centers_mm` field with `fastener_row_z_centers_mm=[-232,-84,-76,60]` and `raised_rib_z_centers_mm=[-232,60]`; set the profile stations to the spec values. Generate the two continuous face ribs only at the raised-rib centers. At the two middle rows, add 24 discrete inner pads, each nominally 12 mm tangential width, 8 mm high, and 4 mm thick toward the enclosure interior. Keep the existing Ø8 mm head-seat recess, 2.1 mm depth, all 48 through-holes, and tool paths. Preserve the 2 mm recessed center seam without cutting away the inner pads.

- [x] **Step 4: Run focused cover tests and confirm the new geometry passes**

Run: `& $py -X utf8 -m unittest test_root_cover -v`

Expected: all cover tests pass; only two raised-rib bands are detected, four fastener rows remain, and each inner pad retains at least 4.3 mm nominal material beneath its head recess.

### Task 2: Update assembly audit, service checks, and review images

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- Consumes: `RootCoverResult.raised_rib_centers_mm` and `RootCoverResult.fastener_row_centers_mm` from Task 1.
- Produces: `audit["cover_layout"]` reports two visible bands, four support rows, 24 inner pads, their bounds, the preserved 48-hole M3 pattern, and the actual cover envelope.

- [x] **Step 1: Add failing integration assertions**

Update the integration tests to expect `visible_band_count == 2`, raised-rib centers `[-232,60]`, four support-row centers, 24 inner pads, 48 fastener holes, two large observation openings, no forbidden collisions, unchanged 12-panel counts, and clear lower-panel/drive-module extraction sweeps.

- [x] **Step 2: Run the focused integration tests and confirm the new assertions fail**

Run: `& $py -X utf8 -m unittest test_v27_integration -v`

Expected: the new audit and service assertions fail against the four-rib baseline.

- [x] **Step 3: Update audit and renderer consumers**

Make `generate_v27_assembly.py` calculate continuous-band envelopes only from the two raised-rib centers and pad envelopes from the two middle support rows. Keep screw and tool-clearance sweeps over all four rows. Update `render_v27.py` to show two continuous ribs, discrete middle fastener positions, and two large opposing observation openings; retain the existing motor and M12 window views and all module-extraction views.

- [x] **Step 4: Run focused integration tests and confirm the two-rib assembly passes**

Run: `& $py -X utf8 -m unittest test_v27_integration -v`

Expected: all integration checks pass, with no collisions and all service paths clear.

### Task 3: Regenerate deliverables and update project records

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27打印前审查.md`
- Regenerate: cover/assembly STEP files, review PNGs, `V27装配审查.json`, `V27工程审计.json`, and `来源与SHA256.csv` in the same directory.

**Interfaces:**
- Consumes: the passing Task 1 cover and Task 2 assembly/audit/render results.
- Produces: a self-consistent V27 model package with the approved two-plane/two-rib cover and regenerated evidence files.

- [x] **Step 1: Update documentation to describe two external ribs and four retained fastener rows**

Replace four-visible-band claims with two continuous external ribs, four retained M3 rows, 24 internal middle-row pads, and two 110×80 mm opposing observation openings. Keep the stated boundary that geometry checks do not prove slicer success, print strength, or underwater performance.

- [x] **Step 2: Run the engineering audit and regenerate all model artifacts**

Run:

```powershell
& $py -X utf8 .\engineering_audit.py
& $py -X utf8 .\generate_v27_assembly.py
```

Expected: cover STEP, full assembly STEP, review renders, audit JSON files, and SHA-256 manifest are refreshed from the same parameter set.

- [x] **Step 3: Run the complete regression suite**

Run: `& $py -X utf8 -m unittest discover -s . -p 'test_*.py' -v`

Expected: all tests pass, including geometry, collision, printer-envelope, tool-access, service-path, export-readback, and manifest checks.

- [x] **Step 4: Verify the regenerated outputs and report the evidence boundary**

Read back the cover and assembly STEP files. Confirm the cover has two raised ribs, four fastener rows, 12 removable panels, the expected profile and dimensions, no forbidden collisions, 24 unobstructed inner pads, and clear service sweeps. Verify every SHA-256 manifest entry. Report slicing and physical strength/sealing as unverified.
