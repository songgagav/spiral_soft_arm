# V27 Dry-Side Shaft and Wet-Side Spool Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace each separate dry-side coupling sleeve with one stepped M2006 input shaft and add a positive, serviceable retainer while keeping each wet-side spool independently replaceable.

**Architecture:** Build the motor D6 socket, cross-pin collar, vertical input shaft, and 8 mm bevel-gear journal as one fixed-base solid. Keep the wet spool independently replaceable with a circular clearance bore and removable radial drive pin; capture it between a small integral shaft shoulder and a removable stainless retaining-ring envelope. The fixed output support land remains installed with a Ø26.8 mm axial through-bore; its outboard bearing/seal cartridge is separately removable with two M2.5 screws before the spool slides through the land.

**Tech Stack:** Python 3.12.2, CadQuery 2.8.0, `unittest`, STEP export, Pillow/Matplotlib render generation.

**Spec:** `docs/superpowers/specs/2026-11-12-v27-simplified-shaft-spool-design.md`

## Global Constraints

- Work only in `E:\Spiral_Robots\.worktrees\spiral-soft-arm-v27` on `feat/v27-modular-m2006`.
- Preserve the 1 m/42-unit arm, 250 mm top plate, three M2006 drive axes, bevel-gear centers and ratio, Ø10 seal journals, Ø8 gear journals, and existing straight tendon tangent.
- Each dry-side motor input shaft is one 316L candidate part with a 15 mm local D6 socket collar, Ø6.2 mm × 13 mm D-shaped motor socket, a 2.6 mm flat offset matched to the official STEP's 2.5 mm motor-shaft flat, and Ø3.2 mm cross-pin hole; retain the removable Ø2.8 mm motor pin.
- End the Ø15 mm collar 0.2 mm before the first input bearing; continue the Ø10 mm shaft through the bearing stations. This is nominal CAD face clearance only.
- Remove the separate coupling sleeve and its ineffective M3 screw geometry; do not add a coupling fastener.
- Keep the spool a separate replaceable part with a Ø10.1 mm circular clearance bore and removable Ø2.5 mm radial drive pin. Use a nominal Ø10.8 mm integral shoulder, a 10 mm-shaft retaining-ring envelope (Ø9.6 mm groove, 1.0 mm axial width, Ø16 mm outer envelope), and 0.2 mm nominal spool-side clearances. These are CAD candidates, not supplier-approved tolerances.
- Keep the seal journal Ø10 mm. For the retention layout, place the two 10×22×7 mm seal envelopes at `[-12,-5]` and `[5,12]` mm, and the two labyrinth envelopes at `[-13.1,-12.1]` and `[12.1,13.1]` mm along the output-shaft axis. Preserve the existing output-bearing stations.
- Keep the fixed output support land and give it a Ø26.8 mm through-bore; use a separate OD Ø26.4/ID Ø22.02 mm cartridge with two M2.5 fasteners and 5 mm nominal thread engagement. Integrate the Ø23/Ø20.5 × 1.5 mm outboard seal-retaining shoulder into that cartridge. Treat these as machinable CAD candidates only.
- Keep the V26 snapshot and unrelated untracked files unchanged. Update generated V27 outputs only through the V27 generator.
- CAD-only evidence must remain separate from CNC fit, strength, corrosion, sealing, and underwater validation.
- Run PowerShell commands from the V27 model directory after setting `$py = 'C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe'`.

## Review Focus

- D6 socket profile/depth, 0.1 mm nominal flat fit, collar wall, and cross-pin alignment: `test_integrated_input_shaft_preserves_motor_socket_and_pin_interface`.
- One-piece validity and removal of the obsolete coupling/screw components: `test_input_shaft_is_single_fixed_part_without_loose_coupler`.
- Gear journal, bearing stations, and input/output axes must stay at the approved geometry: `test_input_shaft_change_preserves_drive_datums`.
- Shoulder, groove, retaining-ring fit, drive-pin fit, spool endplay, seals, and labyrinths must not overlap: `test_spool_retainer_and_seal_stack_have_clearance`.
- The outboard support cartridge and wet spool must each have a clear, collision-checked 32 mm extraction: `test_output_support_cartridge_removal_path_is_clear` and `test_wet_spool_service_sweep_is_clear_after_release_sequence`.

---

### Task 1: Integrate the M2006 coupling into the fixed input shaft

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/model_contract.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_parameters.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_drive_and_base.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- Consumes: `V27Contract.integration` dimensions, `DriveAxis`, and the existing fixed/removable component dictionaries.
- Produces: `fixed_shaft_01..03`, each one valid solid that includes the motor socket/collar through the bevel-gear journal; the drive module still owns exactly three removable cross-pins. No `fixed_coupling_sleeve_*` or `fixed_coupling_lock_screw_*` keys remain.

- [x] **Step 1: Write failing geometry and ownership tests**

Update `test_modular_interface_contract` and add `test_integrated_motor_input_shaft_and_seal_fits_are_explicitly_reviewed` in `test_parameters.py`; add the three geometry tests named in Review Focus to `test_drive_and_base.py`; add `test_input_shaft_audit_reports_integrated_socket_and_no_loose_sleeves` to `test_v27_integration.py`. Replace component assertions that require `fixed_coupling_sleeve_*` and `fixed_coupling_lock_screw_*`. Assert the Ø15 collar, its 0.2 mm nominal axial clearance to the first bearing, Ø6.2×13 socket, Ø3.2 cross-hole at the published 9 mm-from-tip station, at least 4.4 mm nominal socket wall away from the cross-hole, one-solid shaft, and unchanged gear/bearing datums.

- [x] **Step 2: Run the new focused tests and observe the expected failure**

Run the named parameter tests, the three named drive/base tests, and the integration audit test individually with the `& $py -X utf8 <test-file> <TestClass>.<test_name> -v` form.

Expected: the tests fail because the current model contains a separate sleeve and screw rather than a one-piece input shaft.

- [x] **Step 3: Build the one-piece input shaft**

In `build_fixed_base`, fuse the 15 mm collar envelope to the existing stepped input shaft before cutting the Ø6.2 mm motor socket and cross-pin hole. End the collar 0.2 mm before the first input bearing while the Ø10 mm shaft continues through the bearing stations. Preserve the vertical D10 geometry and D8 bevel-gear journal. Rename the retained dimensions to `m2006_input_shaft_collar_diameter_mm`, `m2006_input_shaft_socket_diameter_mm`, `m2006_input_shaft_socket_depth_mm`, `m2006_input_shaft_cross_pin_diameter_mm`, `m2006_input_shaft_cross_pin_hole_diameter_mm`, and `m2006_input_shaft_cross_pin_length_mm`; remove the unused coupling-sleeve and set-screw keys.

- [x] **Step 4: Update the input-interface audit and component assertions**

Keep the audit object `m2006_coupling_interface` for compatibility, but report `integrated_input_shaft: true`, the socket/collar dimensions, `loose_coupling_sleeve_count: 0`, `coupling_set_screw_count: 0`, and `removable_cross_pin_count: 3`. Keep the shaft in `fixed_component_names`.

- [x] **Step 5: Run drive and integration tests**

Run: `& $py -X utf8 test_drive_and_base.py -v`, `& $py -X utf8 test_v27_integration.py -v`, then `& $py -X utf8 -m unittest discover -s . -p 'test_*.py' -v`.

Expected: focused tests pass, followed by the complete repository suite; motor-module negative-Z removal sweep remains clear; forbidden collisions remain empty; V26 snapshot hashes are unchanged.

- [x] **Step 6: Commit the integrated input-shaft change**

Stage only `parameters.json`, `model_contract.py`, `drive_and_base.py`, `generate_v27_assembly.py`, `test_parameters.py`, `test_drive_and_base.py`, and `test_v27_integration.py`; run `git diff --cached --check`, then commit as `refactor(v27): integrate M2006 input shaft`.

### Task 2: Add spool axial capture, removal-path audit, and updated deliverables

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_drive_and_base.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `README.md`
- Regenerate: V27 STEP exports, `V27_装配审查.json`, drive-detail PNGs, and `来源与SHA256.csv`.

**Interfaces:**
- Consumes: the three separate wet-spool shapes and output-shaft axes from Task 1's fixed-base builder.
- Produces: three independent spools, integral inboard stops, three `fixed_spool_retainer_01..03` retaining-ring envelopes, separately named drive-side/outboard seal and labyrinth components, and `service.spool_removal` records with collision-checked axial extraction sweeps.

- [x] **Step 1: Write failing retainer and service-path tests**

Add `test_spool_retainer_and_seal_stack_have_clearance` to `test_drive_and_base.py` and service-path tests to `test_v27_integration.py`. Require the ring/shaft groove match, positive shoulder overlap beyond the circular bore, removable drive-pin fit, 0.2 mm spool-side clearances, the stated seal/labyrinth ranges, separate spool solids, a 32 mm positive-axis extraction, and no sweep collision after removing the outboard cartridge, its two screws, `fixed_bearing_outer_*`, `fixed_oil_seal_outboard_*`, `fixed_labyrinth_outboard_*`, `fixed_spool_retainer_*`, and `fixed_spool_drive_pin_*`. Retain the fixed support land and validate cartridge removal independently. The cable must be detached and unwrapped before service.

- [x] **Step 2: Run the new tests and observe the expected failure**

Run: `& $py -X utf8 test_drive_and_base.py V27DriveAndBaseTests.test_spool_retainer_and_seal_stack_have_clearance -v` and `& $py -X utf8 test_v27_integration.py V27ZZDeliveryTests.test_wet_spool_service_sweep_is_clear_after_release_sequence -v`.

Expected: they fail because the current assembly has neither a positive spool keeper nor a service-path audit.

- [x] **Step 3: Model the shoulder, groove, retaining-ring envelope, and seal stack**

Add the Ø10.8×0.8 mm inboard shoulder to the output shaft over `[-4.5,-3.7]` mm; cut the Ø9.6×1.0 mm outboard ring groove at `[3.7,4.7]` mm and add an independently removable Ø16×1.0 mm retaining-ring envelope as `fixed_spool_retainer_NN`. Split each seal and labyrinth compound into `fixed_oil_seal_drive_side_NN`, `fixed_oil_seal_outboard_NN`, `fixed_labyrinth_drive_side_NN`, and `fixed_labyrinth_outboard_NN`. Move those envelopes to the ranges in Global Constraints.

- [x] **Step 4: Implement and test the spool extraction sweep**

Translate each spool 32 mm along its own positive tangent axis after removing only the documented outboard service components, including the removable drive pin. Separately sweep the outboard cartridge 32 mm after removing its two screws, bearing, oil seal and labyrinth. Record obstacle names, release sequence, clearances and collisions for each path in `audit_v27_assembly`; make `preflight_v27` reject any failed spool or cartridge extraction path.

- [x] **Step 5: Update drawing and service documentation**

Revise the drive details sheet to show the integrated dry-side shaft, cross-pin, separate wet spool, shoulder, retaining-ring envelope, fixed support land, removable cartridge and its screws, and relocated seal/labyrinth stack. Update the V27 README with both service sequences, nominal clearances, and the warning that ring/groove and cartridge dimensions need supplier/CNC confirmation.

- [x] **Step 6: Regenerate V27 deliverables and run verification**

Run: `& $py -X utf8 generate_v27_assembly.py`, then `& $py -X utf8 -m unittest discover -s . -p 'test_*.py' -v` from the V27 directory.

Expected: export/preflight succeeds; all tests pass; STEP parts re-import as valid; the detail render and audit describe the new geometry; manifest hashes match; V26 snapshots remain unchanged. The audit remains a static CAD candidate, not a manufacturing or underwater release.

- [x] **Step 7: Commit the completed change**

Stage only this plan, its spec, the V27 source/docs/tests, and regenerated deliverables; run `git diff --cached --check`, then commit as `feat(v27): simplify shaft and retain wet spools`.

## Implementation ruling

- The first 32 mm spool sweep failed because a D-bore spool cannot pass over the round Ø10 mm seal journal. To preserve round seal surfaces and the replaceable-spool path, use a Ø10.1 mm circular clearance bore and one removable Ø2.5 mm radial pin through the spool hub and output shaft; withdraw the pin and unload/unwrap the cable before axial extraction. This adds one service pin per spool and requires torque/shear, corrosion, and retention validation. The pin sits below the cable winding surface.
- Final review found the original socket cut was round despite the approved D6 interface. The official STEP section has a 2.5 mm flat offset; model the matching motor proxy and cut a 2.6 mm D socket flat aligned to the radial cross-pin axis. The nominal 0.1 mm fit requires a CNC coupon check. Keep the printed spool's 0.05 mm radial hole/shaft clearance explicitly gated by a fit coupon and post-processing as needed.
- Task 1 and Task 2 are committed together in one atomic change because the input-shaft geometry, spool service path, audit schema, tests, and generated STEP outputs share the same V27 source and final regeneration. This keeps the published candidate internally consistent; the tradeoff is that Git history has no intermediate shaft-only checkpoint.

## Post-review correction pass

- [x] Open the spool radial-pin channel through both faces and verify the removable cartridge is a single connected solid with its lugs joined to the sleeve.
- [x] Keep the fixed support land installed, add its Ø26.8 mm through-bore and the OD Ø26.4/ID Ø22 mm removable cartridge with two M2.5 fasteners, and collision-check both 32 mm extraction paths.
- [x] Extend the tendon-transition coupon's radial entry and axial exit channels through the host faces.
- [x] Make V27 preflight reject cartridge-removal collisions, update documentation/renders, regenerate outputs and rerun the full suite before commit.
