# B32 v25 Power Input and M28 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a v25 B32 electronics chamber with the confirmed 42×24×5 mm STM32 buck module and the user-supplied M28 rear-panel connector geometry.

**Architecture:** Fork the parameterized v24 candidate into a new v25 directory, preserving the v23 mechanical assembly and all v24 hardware. Replace the M28 proxy and lid bore with the approved 5 mm local recessed mount, add connector/plug service envelopes and the buck module, then regenerate STEP, previews and audits.

**Tech Stack:** CadQuery 2.8, Python 3.12, VTK, Matplotlib, STEP, JSON, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-06-v25-power-input-and-m28-design.md`

## Global Constraints

- Preserve v23 and v24 artifacts; create `electronics_enclosure_v25_power_input_and_m28`.
- M28 panel opening is 26.2×28 mm, nominal mounting cylinder Ø27.8 mm, flange Ø36 mm and effective panel thickness 5 mm.
- M28 plug service envelope is Ø33×71.5 mm.
- Buck module envelope is 42×24×5 mm with the recorded 5–35 V, 20 A user specification.
- Keep all unknown seal grooves, terminal tails and PCB mounting holes explicitly unverified.

## Review Focus

- The 5 mm recessed M28 land must remain one valid lid solid with a surrounding load ring.
- The asymmetric M28 opening must retain its 26.2 mm flat-to-flat width after STEP export.
- The external plug envelope must clear the lid fasteners and fairing service space.
- The buck module and mounting shelf must clear the STM32, UPS, regulator and wiring bays.
- The generated audit must not convert dimensional envelopes into waterproof or thermal claims.

---

### Task 1: Versioned parameters and geometry checks

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v25_power_input_and_m28/parameters.json`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v25_power_input_and_m28/test_v25_interfaces.py`

**Interfaces:**
- Consumes: v24 parameter values and the approved design spec.
- Produces: exact `hardware.buck_5v` and `hardware.m28_power` records consumed by the generator.

- [ ] Copy the v24 parameters into a v25 schema and add the confirmed buck and M28 values.
- [ ] Add tests asserting 42×24×5 mm, 26.2×28 mm, Ø27.8/Ø36 mm, 5 mm land and Ø33×71.5 mm plug values.
- [ ] Run `python -m unittest test_v25_interfaces.py -v`; expect all parameter tests to pass.

### Task 2: M28 recessed lid and buck-module layout

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v25_power_input_and_m28/generate_power_input.py`

**Interfaces:**
- Consumes: v25 parameters and `v24.generate_selected_hardware` assembly functions.
- Produces: `build_v25_components() -> tuple[dict[str, cq.Shape], list[str]]` and named M28/buck components.

- [ ] Implement the 26.2×28 mm M28 opening as the intersection of the Ø28 cutter and the 26.2 mm width limiter.
- [ ] Cut an inner recess that leaves a 5 mm mounting land and fuse a surrounding annular load ring without covering the connector opening.
- [ ] Add the Ø27.8 socket body, Ø36 flange, Ø33×71.5 plug envelope and a service clearance volume.
- [ ] Add the 42×24×5 mm buck envelope and removable shelf beside the STM32/UPS lane.
- [ ] Run the v25 interface tests and a generator dry run; expect valid solids and no hardware envelope overlap.

### Task 3: Export, audit and review images

**Files:**
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v25_power_input_and_m28/render_layout.py`
- Create: `local/spiral-soft-arm/solidworks/electronics_enclosure_v25_power_input_and_m28/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `build_v25_components()`.
- Produces: electronics STEP, full-assembly STEP, translucent preview, M28 detail view, layered layout and JSON audit.

- [ ] Export and reimport both STEP files; require valid BREP and record solid counts.
- [ ] Audit hardware-to-hardware, hardware-to-shell and buck-to-existing-board intersections; require no unexpected positive-volume overlaps.
- [ ] Render a translucent chamber preview, an M28 recessed-lid detail and an updated layered layout.
- [ ] Document the confirmed power behavior separately from unverified sealing, thermal and terminal dimensions.
- [ ] Run `git diff --check`, inspect both previews, and commit only v25, the design/plan and README changes.
