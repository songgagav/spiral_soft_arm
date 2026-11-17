# V27 Paper-Derived Spiral and 5 m Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recalculate the 1 m, 42-unit V27 spiral from the paper equations, write a Chinese derivation report for the 5 m environment, and regenerate the arm and integrated assembly exports.

**Architecture:** Add one pure-math module that solves the paper length equation, produces interval lengths and a deterministic parameter JSON, and is consumed by `arm_module.py`. Rebuild the existing V27 assembly with its current modules and export per-segment STL, arm STEP, integrated assembly STEP, and refreshed render/manifest artifacts. The report is generated from the same formula results and clearly separates geometry from water-pressure qualification.

**Tech Stack:** Python 3.12, CadQuery 2.8.0, python-docx, bundled DOCX renderer, Markdown/JSON.

**Spec:** `docs/superpowers/specs/2026-11-08-v27-paper-spiral-depth-integration.md`

## Global Constraints

- Keep the 1,000 mm centerline length, 42 paper units, 5/120 mm tip/root sizes, 3 tendons and 4 print segments.
- Treat one paper quadrilateral unit as one angular interval, so `DeltaTheta = theta0 / 42`.
- Keep the four segments within the existing 300 mm nominal print-height limit.
- Preserve the V27 module boundaries and do not modify V26 outputs.
- Do not treat 5 m pressure calculations or CAD exports as physical, print, or waterproof validation.
- Do not add or run a test suite in this task; use only the export pipeline's required preflight/readback and artifact QA.

## Review Focus

- **Unit versus interval count:** confirm the 42 quadrilaterals span 42 angular increments and scale by `beta = exp(b*DeltaTheta)`.
- **Length definition:** report 1,000 mm as paper-equation centerline arc length; do not conflate it with external end-to-end projection.
- **Water depth:** compute 5 m gauge pressure separately from geometry; do not alter `b` or claim a depth-rated arm.
- **Segment interfaces:** retain unit-boundary cuts and existing four-segment mechanical assembly interfaces.
- **Version boundary:** write only under V27 and leave V26 snapshots unchanged.

---

### Task 1: Implement the paper-derived spiral parameter source

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/spiral_parameters.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/arm_module.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`

**Steps:**

- [ ] Implement a stable positive-root bisection for paper Eq. (5) after substituting the tip/root ratio.
- [ ] Derive `a`, `a1`, `theta0`, `DeltaTheta`, `beta`, taper angle, central-curve scale, exact per-interval arc lengths, and the 5 m freshwater/seawater pressure context.
- [ ] Change `compute_unit_planes` to sum the 42 exact centerline arc-length intervals tip-to-root, reversed into the existing root-to-tip Z convention.
- [ ] Change `_paper_profile_polygons` to use computed `b`, `a`, `a1`, and `DeltaTheta` instead of a hard-coded 30-degree interval and prior ratio approximation.
- [ ] Add the discretization convention to the parameter contract and emit `V27螺旋参数.json` from the same calculation source.

**Expected:** computed values identify `b≈0.140222015932`, `a≈3.537542594481 mm`, `a1≈6.037542594481 mm`, `theta0≈22.664442592811 rad`, `DeltaTheta≈30.918497752014 degrees`, and `beta≈1.078604362321`; the 42 interval lengths sum to 1,000 mm.

### Task 2: Rebuild and export the integrated V27 CAD model

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Refresh: V27 STEP, STL, PNG, JSON, CSV outputs in the V27 directory.

**Steps:**

- [ ] Add derived spiral parameters to the assembly audit record.
- [ ] Extend the current export function with four individual print-segment STLs while preserving the existing arm, drive, base, and whole-assembly STEP files.
- [ ] Run the existing V27 generation/export path; it must complete its assembly preflight and re-import each emitted STEP successfully.
- [ ] Render the integrated/exploded/detail reviews and regenerate the provenance/hash CSV.
- [ ] Update README output list and formula/discretization summary without changing V26.

**Expected:** one current parameter JSON, four per-segment STL files, updated arm-module STEP, unchanged drive/base module interfaces, and an integrated whole-project STEP from the same in-memory V27 assembly.

### Task 3: Write the Chinese derivation paper and visually verify it

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/V27_5m水深_1m三缆臂螺旋函数推导.md`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/V27_5m水深_1m三缆臂螺旋函数推导.docx`
- Create: one derivation/profile figure for the report.

**Steps:**

- [ ] Explain the source paper equations and derive the endpoint ratio, reduced length equation, numerical solution, and all geometric functions.
- [ ] Show the 42-interval discretization and exact interval-arc-length summation.
- [ ] State the 5 m hydrostatic pressure assumptions and the boundary between geometry calculation and underwater/pressure validation.
- [ ] Generate the DOCX with the bundled document runtime and render it to PNG pages.
- [ ] Inspect every rendered page and correct layout or formula-glyph problems before delivery.

**Expected:** Markdown and DOCX report values agree with `V27螺旋参数.json`; every DOCX page renders legibly, and the report does not call the model print-ready or depth-qualified.
