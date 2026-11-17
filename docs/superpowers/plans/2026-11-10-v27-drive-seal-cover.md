# V27 Drive, Seal, and Cover Implementation Plan

> Status: this draft's SM3-20 gear and 320 mm cover proposals were superseded by later catalog review and assembly preflight. The current candidate uses SM1.25-25H and the [2026-11-11 compact-layout plan](2026-11-11-v27-compact-layout.md) for its 324 mm stepped-shoulder cover; use the V27 README and drive/seal review for final current values.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revalidate the V27 coupling sleeve, shaft seals, and right-angle gears, then add a removable flat-panel fairing and short root guard to the assembly.

**Architecture:** Keep gear selection evidence separate from assembly geometry. Correct seal seat and retention geometry independently; add cover geometry in a focused `root_cover.py` module and integrate its component names into the existing export and review renderer.

**Tech Stack:** Python 3.12, CadQuery 2.8, unittest, STEP export, Matplotlib preview.

**Spec:** `docs/superpowers/specs/2026-11-10-v27-drive-seal-cover.md`

## Global Constraints

- Preserve V27's 250 mm top plate and motor-board removal direction.
- Preserve vertical motor axes, horizontal tangential spool axes, and straight tangent-to-inlet cable routing.
- Treat the exterior cover as floodable and vented, never as a pressure vessel.
- Do not claim print, water-seal, or gear-train release from catalog arithmetic or proxy CAD.
- Do not commit or push.

## Review Focus

- Seal housing bore and shaft journal must follow the seal manufacturer's H8/h11 dimensions; test the modeled seat radius.
- TRP seals need axial retention; test that the retainer is modeled and remains serviceable.
- Standard miter gear envelopes may collide with the arm flange or plate; report this as a hold instead of silently shrinking the gear.
- Panel windows, frame, electronics connectors, root guard, and motor-module service sweep must remain clear; test the candidate assembly.
- Cover height and side-panel layout must stay inside the user's printer envelope; assert the saved dimensions.

---

### Task 1: Correct and test the seal-seat interface

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/drive_and_base.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_drive_and_base.py`

- [ ] Add assertions for Ø22 H8 nominal seal seats and positive axial-retainer components.
- [ ] Run targeted tests and confirm they fail on the current Ø22.2 through-bores/no-retainer geometry.
- [ ] Model Ø22.0 nominal seal seats and a separate dry-side retaining ring at each seal; preserve Ø10 shaft journal and noncontact simplified seal-lip proxy.
- [ ] Run targeted tests and confirm the interface checks pass.

### Task 2: Add the detachable cover accessory

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/root_cover.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/render_v27.py`
- Test: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_root_cover.py`

- [ ] Test the 320 mm six-sided outer envelope, 300 mm printable panel height, M12 service opening, open top/bottom, and 20 mm root guard.
- [ ] Build six removable flat panels, three hexagonal support frames, plate anchors, access/pressure-equalization openings, and the short root guard.
- [ ] Integrate cover parts as detachable fixed-base components and add them to the assembly exports/previews.
- [ ] Run the cover tests and existing assembly preflight; assert no cover interference with the existing V27 geometry and downward motor-board service sweep.

### Task 3: Record interface and gear-selection review

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27传动密封与包覆复核.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/V27打印前审查.md`

- [ ] Record the verified M2006-to-coupler dimensions, TRP H8/h11 and media limits, seal-retainer requirement, 6900 support interface, and KHK SM3-20 candidate dimensions/torque.
- [ ] Record the catalog-sized gear-envelope intersection against the current top plate/root flange; keep the gear marked not integrated if the geometry conflicts.
- [ ] Generate STEP and the semi-transparent cover preview; inspect the final preview and exported bounding boxes.
- [ ] Run the complete V27 unittest suite and export/preflight checks; report unresolved physical gates explicitly.
