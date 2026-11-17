# V27 Hidden Cover Mounting Ears Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Connect three V27 upper cover panels to the existing fixed top plate with internal M3 mounting ears while preserving the approved outside contour and service openings.

**Architecture:** Integrate one horizontal radial ear into each of upper panels 01, 03, and 05, aligned with the existing plate holes at radius 100 mm and face normals 30°, 150°, and 270°. Keep each ear fused into its panel and seated on the plate at Z=0. Extend the assembly audit with hole alignment, contact, fastener access, underside receiver clearance, and upper-panel removal checks.

**Tech Stack:** Python 3.12, CadQuery 2.8.0, unittest, V27 assembly/render/audit scripts.

**Spec:** docs/superpowers/specs/2026-11-15-v27-hidden-cover-mounting-ears-design.md

## Global Constraints

- Fixed top plate stays a Ø250 mm vertex-to-vertex hexagon spanning Z=-8…0 mm.
- The exterior cover profile, two raised ribs, four panel-fastener rows, two 110×80 mm observation openings, motor windows, M12 window, arm, drive and electronics stay unchanged.
- Add ears only to the upper panels whose normals are 30°, 150°, and 270°; each ear has an 18 mm tangential width and an 8 mm vertical height from Z=0 to Z=8.
- Each ear reaches inward to radius 92 mm, keeps at least the nominal 2 mm radial gap from the Ø180 mm root-flange envelope, and carries an Ø3.4 mm through-hole at radius 100 mm.
- Use the three existing Ø3.2 mm top-plate through-holes at radius 100 mm and matching normals. CAD must verify coaxial alignment and face contact at Z=0.
- Treat M3 through-bolts and underside nuts as geometry envelopes only. Do not claim a qualified fastener joint, print strength, slicing success, water sealing, or pressure performance.
- An upper panel with an ear can be removed only after its plate-retention bolt is released; verify its radial pull-out path.

## Review Focus

- A normal-to-panel index error puts an ear behind a motor-window panel; assert the three exact host panels and keep all other panels ear-free.
- A radial-length or overlap error leaves an ear detached from its panel or intruding beyond the radial limit; assert one-solid fusion, the target radius and the ear's nominal section.
- A Z offset leaves a gap to the top plate or overlaps it; assert ear bottom Z=0 and top-plate top Z=0, with contact but no volumetric collision.
- A hole-position error prevents an M3 bolt from crossing both parts; assert all three ear-hole centers match the existing plate holes and a through-probe clears both solids.
- A receiver or driver collides with the root flange, motor, electronics or cover; test an Ø8 mm top-side tool corridor, a 6.5×2.4 mm underside nut envelope and each upper-panel radial removal sweep.

---

### Task 1: Build and test the three integrated mounting ears

**Files:**
- Modify: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json
- Modify: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py
- Test: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py

**Interfaces:**
- Consumes: contract.integration["root_cover"], existing six upper-panel normals, and the ear dimensions from the spec.
- Produces: RootCoverResult.top_plate_attachment_panel_names listing the three upper host panels; each host panel remains a valid single solid with its ear integrated.

- [x] **Step 1: Write failing cover-geometry tests**

Add tests for three and only three ears on upper panels 01/03/05; 18 mm tangential width, 8 mm Z height, inner radial limit 92 mm, and one Ø3.4 mm hole per ear at R=100 mm on normals 30°/150°/270°. Probe the material around each hole to confirm the ear exists, the through-hole remains open, and the ear is fused to its host panel as one solid. Assert upper panels 02/04/06 remain unchanged by ear geometry.

- [x] **Step 2: Run the new tests against the current model**

Run from the assembly directory:

~~~powershell
$py = 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe'
& $py -X utf8 -m unittest test_root_cover.V27RootCoverTests.test_three_hidden_top_plate_ears_are_integrated_on_non_motor_upper_panels -v
~~~

Expected: FAIL because the three mounting ears and their vertical holes do not exist yet.

- [x] **Step 3: Add the parameter contract and integrate ear solids**

Add explicit configuration keys for host face normals, inner radial limit, tangential width, Z bounds, hole radius and hole diameter. In build_root_cover, derive the wall's inner apothem at Z=0 from the existing profile; create one inward shelf per selected upper panel with a small overlap into the panel; fuse and validate each host panel; then cut the vertical Ø3.4 mm hole at its aligned R=100 mm center. Populate RootCoverResult.top_plate_attachment_panel_names.

- [x] **Step 4: Run cover geometry tests**

Run: & $py -X utf8 -m unittest test_root_cover -v

Expected: all root-cover tests pass, with exactly three hidden ears and no change to the outer envelope or existing openings.

### Task 2: Audit the top-plate joint and upper-panel service path

**Files:**
- Modify: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py
- Test: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py

**Interfaces:**
- Consumes: RootCoverResult.top_plate_attachment_panel_names from Task 1 and fixed_top_plate.
- Produces: audit["service"]["top_plate_cover_attachment"] with per-panel hole centers, contact result, tool and nut-envelope clearances, and radial removal results.

- [x] **Step 1: Add failing integration assertions**

Add tests that check each ear hole is coaxial with an existing Ø3.2 mm top-plate hole; all three ears seat at Z=0 without volume overlap; the M3 bolt probe clears ear and plate; the Ø8 mm driver path and 6.5×2.4 mm underside receiver envelope clear surrounding hardware; and the three upper panels can translate radially outward 120 mm after the attachment bolt is released.

- [x] **Step 2: Run the focused integration test and confirm it fails**

Run: & $py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests.test_top_plate_cover_ear_fasteners_clear_and_align -v

Expected: FAIL because the audit does not yet include ear alignment or upper-panel release paths.

- [x] **Step 3: Extend assembly service audit and render the joint**

In generate_v27_assembly.py, report the three attachment positions, nominal ear dimensions, Z=0 mating plane, through-hole alignment, driver corridor, underside nut-envelope checks and per-panel removal sweep. Keep contact at the plate face as a permitted zero-distance interface, not a forbidden volume collision. Add a separate magnified joint view in render_v27.py without changing the existing cover previews. A matching upper panel must be released and pulled out before its output-support cartridge; the paired cartridge sweep must record this prerequisite.

- [x] **Step 4: Run focused cover integration tests**

Run: & $py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests.test_top_plate_cover_ear_fasteners_clear_and_align -v

Expected: all three joints align and seat, zero forbidden intersections remain, and all upper-panel service paths pass after bolt release.

### Task 3: Regenerate and document the connected cover candidate

**Files:**
- Modify: root README.md
- Modify: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md
- Modify: local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27打印前审查.md
- Regenerate: fixed-base/full-assembly/cover STEP files, review PNGs, V27装配审查.json, V27工程审计.json, and 来源与SHA256.csv.

**Interfaces:**
- Consumes: passing cover and assembly audit results from Tasks 1–2.
- Produces: internally consistent V27 geometry, review images, audit records and delivery hashes. The M3 hardware remains a nominal receiver envelope until its exact purchased parts are selected.

- [x] **Step 1: Update documentation to describe the hidden connection**

Describe the three internal ears, host faces, existing R=100 mm plate holes, Z=0 mating face, M3 release-before-panel-removal sequence, and the remaining fastener-receiver/strength confirmation. Preserve the boundary that the CAD joint is not load-qualified.

- [x] **Step 2: Regenerate model exports and audit records**

Run:

~~~powershell
& $py -X utf8 .\engineering_audit.py
& $py -X utf8 .\generate_v27_assembly.py
~~~

Expected: updated STEP read-backs, joint detail and existing review renders, assembly/engineering audits, and manifest all come from the same parameter set.

- [x] **Step 3: Run the complete regression suite**

Run: & $py -X utf8 -m unittest discover -s . -p 'test_*.py' -v

Expected: all tests pass, including cover geometry, forbidden collisions, hole/tool alignment, top-plate fit, panel extraction, STEP read-back and delivery-manifest checks.

- [x] **Step 4: Verify package consistency and evidence limits**

Read back the full-assembly and cover STEP files. Confirm three attached ears, three aligned M3 holes, unchanged two-plane/two-rib exterior and observation-window dimensions, zero forbidden collisions, and passing upper-panel release sweeps. Recompute and test every SHA-256 entry. Report slicer, printed strength, actual fastener preload and underwater performance as unverified.
