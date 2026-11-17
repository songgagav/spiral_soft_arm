# B32 Three-Channel M3508 Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a separate v22 B32 assembly that replaces all three v10 4092 drive proxies with M3508 modules, a common dry drive chamber, and wet-side cable reels.

**Architecture:** Reuse the v10 arm, hexagonal plate, tendons, electronics canister, fairing and dovetail geometry; instantiate v20 drive components three times at 120-degree intervals; substitute the CNC Rev A sleeve and 16×35×7 seal envelope; add a serviceable common dry chamber and three sealed horizontal reel-shaft exits. Preserve all source versions and the official motor STEP.

**Tech Stack:** Existing CadQuery/OCP generator workflow, Python 3.12 environment at `C:\Users\MOSS\.cache\codex-cadquery-py312\Scripts\python.exe`, STEP, PNG preview, JSON and Markdown.

**Spec:** `docs/superpowers/specs/2026-11-04-m3508-three-channel-arm-integration-design.md`

## Global Constraints

- Preserve v10 arm sections, the two internal dovetails, the 250 mm hexagonal plate, and the three tendon-hole centers.
- Use three M3508 modules spaced 120° apart; keep the reel axis perpendicular to its radial tendon direction and align the straight cable tangent to its matching plate hole.
- Use an 81.0 mm reel-center radius and the derived 98.1899 mm motor-center radius with the 55.5 mm motor/reel tangent offset; this 1.45 mm reel shift is a collision-driven fit adjustment and must remain recorded.
- Replace each v20 10×30×14 mm output bearing with two 10×22×6 mm single-row bearings per shaft: primary SKF 61900-2RS1 and alternate NTN 6900LLU; record the rough load screen and retain the selection as unvalidated pending combined bevel-gear load/life analysis.
- Keep all three M3508 bodies and right-angle transmissions in one common dry drive chamber; only the reels are wet-side.
- Use the Rev A Ø16×20 mm D-bore sleeve and model the motor-side 16×35×7 seal as a candidate; use each 10×22×7 output seal and labyrinth as the wet/dry interface.
- Put all outputs under `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/`; do not overwrite v10, v20, v21, or official source files.
- Do not claim gear mesh, pressure strength, print release, water tightness, or 5 m operation from CAD geometry.
- Do not stage, commit, or push changes.

## Review Focus

- **Module transform and channel pairing:** each reel's straight route must end at the matching v10 hole; record maximum lateral deviation and reel-axis/cable angle in the geometry report.
- **Threefold clearance:** no motor, transmission, seal carrier, screw proxy, reel, or dry-chamber solid may collide with another; compute pairwise solid intersections and minimum distances.
- **Shared dry chamber boundary:** chamber, service cover, wire pass-through proxies, three horizontal seals, and labyrinths must form a coherent nominal enclosure; report open or intersecting interfaces rather than hiding them.
- **Existing arm and enclosure fit:** motor chamber, reels, cover panels, top plate, electronics canister, root guard, and arm at rest must not overlap; record every exception.
- **Imported CNC sleeve:** preserve the Ø16×20 mm envelope, 12.3 mm motor D engagement, 7.7 mm extension socket and opposed M3 locations; align the D bore to the motor shaft and its seal land to the 16×35×7 envelope.

---

### Task 1: Create the isolated v22 generator and parameter set

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/generate_m3508_arm.py`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/parameters.json`

**Interfaces:**
- Consumes: v10 arm builder/assembly functions; v20 `build_parts()` and `P`; v21 sleeve STEP; v18 official motor STEP.
- Produces: versioned v22 parameters and reusable source loaders/build functions; no source-version edits.

- [x] Add a v22 loader/config wrapper around the unchanged v10/v20 generators and change outputs to v22 names.
- [x] Define channel angles `[0, 120, 240]`, plate-hole angles `[60, 180, 300]`, hole radius `30.6 mm`, the collision-driven reel/motor radii, `55.5 mm` module offset, and seal candidates `16×35×7` / `10×22×7 mm`.
- [x] Add source-file hash capture for the v10 generator/config, v20 generator/config, v21 sleeve STEP, and official M3508 STEP.

### Task 2: Build and position three M3508 drive modules

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/generate_m3508_arm.py`
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/parameters.json`

**Interfaces:**
- Consumes: Task 1 loaders/parameters and v20 part geometry.
- Produces: `build_three_drives() -> dict[str, cq.Shape]`, including named components per channel.

- [x] Implement the transform mapping for each channel so local module +X maps opposite the cable tangent and local +Y maps radially outward; preserve the v10 reel-center radius and existing hole centers.
- [x] Import the v21 sleeve and place it at the v20 motor D shaft; keep the shaft extension, M5 retainer, gears, horizontal output shaft, reel and retainer components while replacing the output bearing.
- [x] Replace each v20 10×30×14 output bearing with two 10×22×6 SKF 61900-2RS1 envelopes; record NTN 6900LLU as dimensionally equivalent alternate and update both support seats.
- [x] Replace each motor-side 16×22×7 envelope with a 16×35×7 envelope and resize its carrier seat; retain the 10×22×7 horizontal output seal and labyrinth.
- [x] Remove v20's one-channel local guide-plate and cable-route proxies; create three cable proxies from actual reel tangency points to the three v10 plate holes.
- [x] Record per-channel motor, reel, shaft, seal, gear and cable bounds/poses in the v22 audit data.

**Task 2 geometry gate (superseded by Tasks 3–5):** The initial v22 placement produced six M3508-to-v10-lower-fairing intersections, which led to the user-authorized lower-chamber redesign. The final integrated chassis and full named-component review are recorded in `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/README_三路M3508共用干仓.md` and `装配审查.json`.

### Task 3: Add the shared dry drive chamber

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/generate_m3508_arm.py`
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/parameters.json`

**Interfaces:**
- Consumes: Task 2 module placements and v10 root/enclosure geometry.
- Produces: `build_shared_drive_chamber(drives, parameters) -> dict[str, cq.Shape]` with chamber shell, removable service cover, nominal gasket interface, and three horizontal shaft-seal interfaces.

**Decision gate cleared by user (2026-11-04):** Keep linewheels close to the tendon holes, use a compact output-bearing pair, and redesign the lower dry chamber. Keep the 250 mm top-plate profile and B32 arm geometry; the final model integrates the plate and chamber as one printed base because the existing plate tabs intersect the chamber rim. The final support-to-shell, tendon, and reel clearances are in the v22 JSON audit.

- [x] Build one faceted common dry enclosure around the three motors and right-angle transmissions, retaining bottom service access and the v10 central electronics canister as a separate compartment.
- [x] Add three horizontal output-shaft seal seats and wet-side labyrinth proxies; place reels outside the dry boundary.
- [x] Add cable pass-through proxies between the electronics and motor chambers without assigning an unconfirmed connector or pressure rating.
- [x] Replace the lower motor-height fairing with the authorized faceted drive-chamber shell; preserve the v10 external top-plate profile and arm, fuse the plate/chamber joint, and record root/fairing clearances.

### Task 4: Build the full B32 v22 assembly and preview

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/generate_m3508_arm.py`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/B32_v22_M3508三路共用干仓总装.step`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/B32_v22_M3508三路总装预览.png`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/B32_v22_驱动与干仓剖视.png`

**Interfaces:**
- Consumes: v10 arm, top plate, electronics, root guard and fairing; Tasks 2–3 drive/chamber shapes.
- Produces: named STEP assembly, exterior preview, and section preview.

- [x] Assemble the unchanged arm/tendon geometry with the three drive modules, common chamber, existing 250 mm plate profile, electronics compartment, root guard and faceted cover.
- [x] Export a named STEP assembly in millimetres and render an exterior view plus a section showing motor locations, chamber boundary, output seals and wet reels.

### Task 5: Write the assembly audit and user handoff

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/装配审查.json`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/README_三路M3508共用干仓.md`
- Modify: `local/spiral-soft-arm/solidworks/electronics_enclosure_v22_m3508_three_channel/generate_m3508_arm.py`

**Interfaces:**
- Consumes: complete v22 named assembly and channel geometry.
- Produces: geometry review measurements, provenance, limits, and usage notes.

- [x] Check every generated solid for validity, preserve named components, re-import the exported STEP, and record solid count and assembly bounds.
- [x] Check all component pairs for volume overlap and the assembly's nearest exact clear contact, plus per-module and critical interface distances; classify inherited v10 overlaps separately from intended v22 contacts.
- [x] Check cable-line deviation, reel-axis angle, hole-center alignment and per-channel clearances; record seal-seat compression and the oblique cable transition through the original vertical top-plate hole as unverified.
- [x] Document remaining limits: inherited v10 electronics overlaps, unmodeled gear teeth, motor/shaft tolerances, seal approval, material, fastener access, dry-chamber pressure strength, cable feedthroughs, print fit, and physical water testing.

**Completion boundary:** Geometry gate passed and STEP round-trip succeeded. The final pair sweep reports 52 inherited v10 overlap pairs and six intentional v22 screw/cable continuity contacts; no unexplained new v22 solid-volume overlaps remain. The cable line reaches the original hole center, but its oblique transition through the vertical plate bore is not modeled. The assembly remains a geometric candidate, not a print, pressure, or underwater release.
