# V27 Electronics Enclosure and Dovetail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the selected V25 electronics bay into V27 and make the four printed arm sections mate through three serviceable dovetails cut inside existing joint units.

**Architecture:** Keep V27 as the assembly authority and load hashed, frozen V25-derived electronic STEP components so clean builds do not depend on the older generator chain. Parameterize internal-unit split planes and one axial dovetail plus transverse lock pin per interface; generate fresh STEP/STL exports and review images from the same assembly result.

**Tech Stack:** Python 3.12, CadQuery 2.8, STEP/STL exporters, JSON contracts, matplotlib review renders.

**Spec:** `docs/superpowers/specs/2026-11-08-v27-electronics-and-dovetails-design.md`

## Global Constraints

- Preserve V26 and V25 geometry; update the V27 candidate, project README, plan/spec, and the repository-root frozen electronics snapshot required for reproducible builds.
- Keep the 1,000 mm arm, 42 spiral units, three 0.5 mm tendon routes, four print segments, and M2006 drive module.
- Put each dovetail inside units 5, 10, and 18; use measured profile cuts at Z=249.780, 501.635, and 744.343 mm. Unit 18 is shifted 6 mm rootward from its midpoint to keep the terminal segment connected.
- Use a 14 ×8 mm trapezoid, 12 mm engagement, 0.30 mm per-side fit clearance, and Ø3 mm removable lock pin with a Ø3.3 mm passage at 30°.
- Preserve the 136/126 mm electronics canister, four 21700 cells, 100 ×80 ×39 mm battery-side regulator, 100 ×50 ×15 mm UPS, STM32F407 board, PD1002, ideal diode, BMS, 42 ×24 ×5 mm buck, M28 and M12 interfaces.
- Keep the release label as a static CAD/engineering candidate; do not claim pressure, strength, thermal, or print qualification.
- Do not commit or push as part of this task.

## Review Focus

- Dovetail cuts through the existing profile units without opening gaps between the original joint interfaces.
- Female sockets and male projections overlap by 12 mm after assembly and remain separate valid solids before assembly.
- The locking-pin bore remains clear of all three tendon channels at all connector planes.
- All finished print pieces remain below the 300 mm V27 contract limit, including the male projection.
- Electronics support structures, interfaces, and hardware fit the dry-cavity boundary without retaining an obsolete controller or omitting the confirmed regulator.

## File Map

- `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`: connector parameters and fixed unit indices.
- `.../model_contract.py`: typed contract for new connector parameters and validation.
- `.../arm_module.py`: profile clipping, dovetail/lock geometry, clearances, and segment metadata.
- `.../generate_v27_assembly.py`: hashed STEP snapshot loading, collision/clearance audit, exports and review renders.
- `.../render_v27.py`: full V27, electronics-bay and dovetail close-up previews.
- `.../README.md`, generated JSON/STEP/STL/PNG and `来源与SHA256.csv`: refreshed candidate record.

## Tasks

### Task 1: Rebuild four arm sections around internal dovetail cuts

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/model_contract.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/arm_module.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`

**Interfaces:** `build_arm_module(contract) -> ArmBuildResult` continues to return four named print solids; `segment_boundary_z_mm` records the new profile-midpoint cuts; each dovetail records the unit number, insertion depth and fit clearance; each lock feature records the 30° pin direction and local length.

- [x] Add the approved split-unit and connector dimensions to the V27 JSON contract and validate exactly three connector locations.
- [x] Clip the paper-profile solid at Z=249.780, 501.635, and 744.343 mm (unit 18 shifted 6 mm rootward), then add 12 mm male extensions and 12.3 mm female sockets with the 14 ×8 mm, 8° rotated trapezoid.
- [x] Add aligned Ø3.3 mm radial passages and Ø3 mm pin proxies centered 6 mm into each joint, oriented at 30° and cut clear of tendon bores.
- [x] Update segment export metadata to report exact cut heights, joint-unit identifiers, assembled engagement and finished print heights.
- [x] Build `ArmBuildResult` directly and inspect its geometry values: four print sections, cuts inside the selected units, positive tendon clearances and finished print heights below 300 mm.

### Task 2: Integrate the named V25 electronics assembly

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Modify if needed: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`

**Interfaces:** the electronics selector returns the named V24/V25 enclosure, support, connector and hardware shapes in V27 coordinates, plus the three V27 C610 controller envelopes. V25 cell carriers, board backings, rails, shelves and the confirmed regulator remain included; obsolete V24 C620 envelopes are excluded.

- [x] Freeze the V25-derived V27 layout as individually hashed component STEP files; reload and validate all 31 components plus the M28 service envelope without importing the upstream generator chain.
- [x] Select the electronics canister, M28-recess lid, M28 and M12 parts, carrier/shelf/backing components and current hardware envelopes; exclude V24 C620 hardware and retain V27 C610 envelopes.
- [x] Preserve the source V25 cavity/hardware fit audit in the electronic snapshot and resolve the canister boss/ring, cell/support, M12/drive-plate, bracket and board-orientation conflicts in V27 without editing V25/V26.
- [x] Call `_select_v25_electronics(contract)`; result contains three C610 envelopes/backings, M28 service envelope and zero source V25 fit-audit overlaps.

### Task 3: Refresh V27 documentation and exported review package

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Regenerate: V27 assembly and four section STEP/STL, assembly audits, renders, source manifest.

- [x] Document the integrated component list, exact split locations, dovetail fit and pin route, service-fit corrections, and remaining hardware/material qualification boundaries.
- [x] Run `C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe -X utf8 generate_v27_assembly.py` from the V27 directory.
- [x] Inspect the regenerated full assembly and joint close-up renders: electronics bay, three internal dovetail joints, M2006/fixed-base assembly, and four print sections below 300 mm.
- [x] Confirm STEP re-import reports valid geometry, audit all four STL meshes for zero-area facets/closed edge incidence, and refresh SHA-256 records for the generated V27 package and reusable electronic STEP snapshot.

## Execution Notes

No new test files or test-suite runs are included. The requested CAD generation and its built-in geometry preflight/STEP re-import are the verification path for this modeling task. Existing unrelated uncommitted V27 work must remain intact.
