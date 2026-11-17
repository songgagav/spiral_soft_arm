# V27 Single-piece Root Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V27 root guard a keyed, single removable hexagonal part with three M3 fastening clearances.

**Architecture:** Parameters define the fastening and alignment geometry. `root_cover.py` creates the keyed guard; `drive_and_base.py` cuts matching receiver slots in the fixed top plate. Existing full-assembly generation remains the single source for STEP, audit, and removal-sweep outputs.

**Tech Stack:** Python, CadQuery, unittest, STEP export.

**Spec:** `docs/superpowers/specs/2026-11-12-v27-single-piece-root-guard-design.md`

## Global Constraints

- Work only in the existing `feat/v27-modular-m2006` linked worktree.
- Preserve the 250 mm top plate and all 12 planar cover panels.
- Treat CAD clearance as nominal only; do not claim print or underwater release.
- Do not modify the pre-existing untracked `.tmp_v27_docx_preview/` directory.

## Review Focus

- Guard must remain one component rather than accidentally becoming split bodies.
- Three M3 clearance holes must not be removed by tendon access windows.
- Two tabs must have matching top-plate slots and retain nominal clearance.
- Existing arm-module Z extraction must still remove the guard first and remain collision-free.
- Generated STEP/audit outputs must reflect the altered geometry, not only source parameters.

### Task 1: Parameterized keyed guard geometry

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`

**Interfaces:**
- Consumes: `integration.root_cover` dimensions from `parameters.json`.
- Produces: valid `fixed_root_guard_hex` with holes/tabs and a keyed `fixed_top_plate`.

- [ ] **Step 1: Write a failing root-cover test**

Assert the new parameter values, guard single-solid validity, three clearance-hole probes, and tab/slot clearance probes.

- [ ] **Step 2: Run the root-cover test to verify it fails**

Run: `py -X utf8 -m unittest test_root_cover.V27RootCoverTests -v`

Expected: FAIL because the current contract has no keyed-guard parameters.

- [ ] **Step 3: Implement keyed guard parameters and geometry**

Add M3.4 clearance holes at 60°, 180°, 300°; add two 4×8 mm tabs and matching slots with 0.3 mm side clearance. Retain the guard name and all existing cover geometry.

- [ ] **Step 4: Run the root-cover test to verify it passes**

Run: `py -X utf8 -m unittest test_root_cover.V27RootCoverTests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add parameters.json root_cover.py drive_and_base.py test_root_cover.py
git commit -m "feat(v27): key single-piece root guard"
```

### Task 2: Regenerate integration artefacts and maintenance record

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: generated `SpiRobs_v27_*.step`, `V27装配审查.json`, `V27工程审计.json`, and V27 preview PNGs in the same directory.
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- Consumes: keyed guard and top-plate slots from Task 1.
- Produces: regenerated audit/STEP/image evidence and explicit keyed-guard maintenance instructions.

- [ ] **Step 1: Write a failing integration assertion**

Assert the audit contains the selected single-piece keyed-guard metadata and the arm removal sequence still starts by removing it.

- [ ] **Step 2: Run the integration test to verify it fails**

Run: `py -X utf8 -m unittest test_v27_integration.V27CoverIntegrationTests -v`

Expected: FAIL because the audit does not yet expose the selected fastening/keying metadata.

- [ ] **Step 3: Regenerate and document**

Update audit metadata and README maintenance language, run `generate_v27_assembly.py`, then render the refreshed cover review PNG.

- [ ] **Step 4: Run focused and full verification**

Run: `py -X utf8 -m unittest discover -s . -p 'test_*.py' -v`

Expected: PASS with no failures.

- [ ] **Step 5: Commit**

```bash
git add README.md test_v27_integration.py SpiRobs_v27_*.step V27装配审查.json V27工程审计.json V27_*.png
git commit -m "docs(v27): record keyed root guard service design"
```
