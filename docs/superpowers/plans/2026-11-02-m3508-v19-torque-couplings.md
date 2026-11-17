# M3508 v19 Torque Couplings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate v19 M3508 drive candidate with stock KHK gear screws bearing on shaft flats and a D-bore cable reel retained by an axial plate and screw.

**Architecture:** Copy the v18 generator and parameters into a sibling v19 directory, keep the official motor STEP as a read-only reference, and update only the v19 geometry and report. Prefer manufacturer KHK CAD; when unavailable, use catalog-dimension gear envelopes and explicitly report that the tooth mesh is not modeled.

**Tech Stack:** CadQuery, Python 3.12 environment at `C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe`, STEP export, JSON and Markdown reports, Matplotlib preview images.

**Spec:** `docs/superpowers/specs/2026-11-02-m3508-v19-torque-couplings-design.md`

## Global Constraints

- Keep all v18 files unchanged.
- Use the 10 mm bore KHK MMSA1.5-20R/L pair and its native 2-M4 tapped-hole/set-screw interface; catalog `L=6 mm` is the axial hole position from the back face, not screw length.
- Fit stock gear screws to modeled shaft flats; do not modify the stock gear body.
- Use a preliminary-clearance D bore on the 10 mm output shaft and an axial retainer plate/screw.
- Preserve the v18 radial cable tangent, guide-port chamfers, motor position, and gear centers. A measured labyrinth/outer-flange collision justifies shifting the reel and guide-port plane together 1.5 mm wetward along the output axis; preserve the straight radial cable path and recalculate the dry/wet interfaces.
- Mark gear tooth mesh, print fit, torque strength, seal pressure, and print release as unverified unless directly evidenced.
- Do not commit or push as part of this plan.

## Review Focus

- **Gear screw to shaft flat orientation:** report the adjustable 90° angular layout assumption and axial hole location; check that each M4×8 mm proxy reaches its flat without entering the gear tooth envelope, and mark actual included screw length for physical confirmation.
- **D-bore fit:** report shaft diameter, shaft across-flat size, bore round clearance, and flat clearance; keep these values labeled preliminary.
- **Axial retention:** confirm the screw and plate engage the shaft end and clear the cable and guide path.
- **Stack clearance:** check the updated gear/shaft interfaces against bearings, seal, labyrinth, bulkhead, drive pod, and wet reel after the local axial shift.
- **Cable route:** confirm reel envelopes do not intersect the straight tangent cable or the chamfered guide plate.

---

### Task 1: Create the isolated v19 candidate package

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/generate_shaft_sleeve_reel.py`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/parameters.json`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/README_轴套与线轮驱动模组.md`

**Interfaces:**
- Consumes: v18 `generate_shaft_sleeve_reel.py`, `parameters.json`, and the official DJI STEP at `local/spiral-soft-arm/solidworks/electronics_enclosure_v18/references/official/DJI_M3508_P19_official.stp`.
- Produces: a v19 generator and parameter set with versioned output names and a relative reference to the unchanged official motor STEP.

- [x] Copy the v18 generator and parameter file into the sibling v19 directory; update model/version/output names and source file path without editing v18.
- [x] Write a v19 README stating scope, inherited geometry, source provenance, and validation limits.
- [x] Compare every v18 baseline hash and confirm no v18 file changed.

### Task 2: Model stock gear screw and shaft-flat interfaces

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/generate_shaft_sleeve_reel.py`

**Interfaces:**
- Consumes: v19 part builders and KHK MMSA1.5-20R/L catalog values.
- Produces: gear parts with labeled stock screw holes/screw proxies, input/output shafts with aligned flats, and report fields for screw/flat alignment.

- [x] Check the official KHK catalog/CAD source; native tooth CAD was not obtainable, so retain the catalog envelope and label tooth meshing as unverified.
- [x] Replace the v18 full-length frusta with the catalog-dimension body envelope and add two M4 screw proxies at `L=6 mm`, using the documented 90° layout assumption.
- [x] Use M4×8 mm smooth fastener proxies to meet the shaft flats; document the unknown purchased screw length.
- [x] Cut the input/output shaft flats for screw contact; record diameter, depth, orientation, and axial span.
- [x] Add geometry checks for valid solids, screw-to-flat contact, and clearances from bearings, seals, pod, and gear envelopes.

### Task 3: Add the reel D-bore and axial retainer

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/parameters.json`
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/generate_shaft_sleeve_reel.py`

**Interfaces:**
- Consumes: v19 output shaft and reel envelope parameters.
- Produces: inner flange/core/outer flange with a common D-bore, plus a distinct axial retainer plate/washer and screw.

- [x] Replace each reel's Ø10.1 round bore with one dimensioned D-bore that matches the modeled 10 mm output-shaft flat and declared preliminary clearance.
- [x] Extend or rework only the free shaft end as needed for the axial retainer; model the screw passage/thread proxy and plate/washer separately.
- [x] Check retainer engagement, reel axial position, cable clearance, and unchanged straight tangent-to-port route; include measured values in the report.

### Task 4: Regenerate and review the v19 deliverables

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/B32_v19_M3508_轴套线轮传动模组.step`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/B32_v19_M3508_轴套线轮效果图.png`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/B32_v19_线轮切线近景.png`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/B32_v19_D形线轮与压片剖视.png`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/装配审查.json`
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v19/README_轴套与线轮驱动模组.md`

**Interfaces:**
- Consumes: all v19 geometry and report calculations from Tasks 1–3.
- Produces: a regenerated STEP, review images, JSON physical-geometry audit, and user-facing README.

- [x] Run the v19 generator with the bundled CadQuery Python environment and inspect part validity, clearances, and the preserved radial tangent length.
- [x] Re-import the STEP and verify valid solids, overall bounds, and unchanged official motor SHA-256.
- [x] Inspect the assembly preview, close-up, and D-bore section image; correct the verified seal-stack and reel/labyrinth interferences.
- [x] Update the README and geometry report with measured results, remaining unverified conditions, output paths, and the KHK source link.
- [x] Confirm `git status` leaves existing unrelated untracked documents untouched; `local/` is ignored by repository rules, so this candidate remains local and was not staged, committed, or pushed.
