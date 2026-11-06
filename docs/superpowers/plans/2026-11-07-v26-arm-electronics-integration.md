# B32 V26 Arm and Electronics Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an independent V26 static assembly candidate that explicitly integrates the original B32 arm, three M3508 tendon drives, and the verified V25 electronics chamber.

**Architecture:** Add a thin V26 integration layer that imports V25 component construction without altering V23 or V25 sources. V26 validates source identities and coordinate interfaces, exports a separate physical assembly, reimports it, and renders whole-arm and root-interface review images.

**Tech Stack:** Python 3.12, CadQuery 2.8, VTK, STEP, JSON, unittest, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-07-v26-arm-electronics-integration-design.md`

## Global Constraints

- Preserve all V23 and V25 source files and artifacts.
- Preserve the original B32 arm component name, five-solid structure, dimensions, and `Z=0 mm` root plane.
- Reuse the V25 component builder; do not copy or independently recreate its hardware geometry.
- Exclude observation-only service-clearance volumes from the physical STEP.
- Keep geometry, printing, movement, sealing, electrical, and pressure evidence explicitly separate.

## Review Focus

- A source change that silently removes or transforms the original arm must fail the V26 contract test.
- Observation/service envelopes must not be exported as physical parts.
- The whole-arm preview must show both the 550 mm arm and the lower electronics chamber at a useful scale.
- Root-interface review must retain the three existing cable-entry directions without introducing guide geometry.
- STEP reimport and static overlap checks must not be reported as print or underwater release.

---

### Task 1: V26 source contract and integration tests

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v26_arm_and_v25_electronics/parameters.json`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v26_arm_and_v25_electronics/test_v26_integration.py`

**Interfaces:**
- Consumes: V25 `build_v25_components() -> tuple[dict[str, cq.Shape], list[str]]`.
- Produces: parameter contract and failing expectations for `build_v26_components()` and `audit_v26_integration()`.

- [ ] Create the V26 parameter record with V25 source path, required component names, original arm solid count, expected arm bounds, root plane, and excluded service envelope names.
- [ ] Write tests requiring the original arm, V25 canister, root plate, three drive prefixes, M28 interface, and controller buck.
- [ ] Write tests requiring five original arm solids, `Z=0 mm` root, approximately `550.014 mm` height, and an unchanged arm bounding box.
- [ ] Write tests requiring the physical export set to omit `v25_M28_service_clearance`.
- [ ] Run `python -m unittest test_v26_integration.py -v`; expect failure because the V26 generator does not exist.

### Task 2: Integrated component builder and interface audit

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v26_arm_and_v25_electronics/generate_integrated_assembly.py`

**Interfaces:**
- Consumes: V26 parameters and V25 component builder.
- Produces: `build_v26_components()`, `physical_v26_components()`, and `audit_v26_integration()`.

- [ ] Implement dynamic loading of the frozen V25 source path and return its components without geometric reconstruction.
- [ ] Implement the physical-component filter that excludes only declared observation envelopes.
- [ ] Implement arm identity and bounding-box checks, required-component checks, drive-channel presence checks, and electronics-above-arm-space checks.
- [ ] Record the arm, root plate, canister, M28, component-count, and unverified-evidence boundaries in the audit result.
- [ ] Run the V26 contract tests; expect all builder and audit tests to pass.

### Task 3: STEP export, whole-arm rendering, and documentation

**Files:**
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v26_arm_and_v25_electronics/render_integrated_assembly.py`
- Create: `local/spiral-soft-arm/solidworks/integrated_assembly_v26_arm_and_v25_electronics/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v26_arm_and_v25_electronics/test_v26_integration.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `physical_v26_components()` and `audit_v26_integration()`.
- Produces: V26 STEP, two PNG review images, and `整机整合审查.json`.

- [ ] Add a failing integration test requiring V26 STEP reimport, whole-arm preview, root-interface preview, and audit JSON.
- [ ] Export `B32_v26_原机械臂与V25电子仓整合总装.step` and reimport it as valid BREP with recorded solid count and bounds.
- [ ] Render `B32_v26_整机半透明预览.png` with the entire 550 mm arm and lower chamber visible.
- [ ] Render `B32_v26_根部与电子仓接口近景.png` showing the arm root, plate, three drive directions, canister, and M28 location.
- [ ] Document inherited hardware, coordinate assumptions, completed static checks, and all remaining physical validation gates.
- [ ] Update the root README with V26 status and links while leaving V23/V25 descriptions intact.
- [ ] Run the full V26 suite, `git diff --check`, inspect both images, and commit only the V26/spec/plan/root-README changes.

### Task 4: Final review and Git synchronization

**Files:**
- Review: all files changed since the V26 design base.

**Interfaces:**
- Consumes: completed V26 artifacts and test evidence.
- Produces: reviewed commits and a push attempt to `origin/main`.

- [ ] Review plan alignment, source preservation, physical-export filtering, visual usability, audit claim boundaries, and binary size.
- [ ] Fix every critical or important finding with a failing regression test first.
- [ ] Run the complete V26 suite again on the final tree and verify the generated STEP and JSON timestamps are current.
- [ ] Commit the reviewed result on the current `main` branch, preserving unrelated untracked files.
- [ ] Push `main`; if GitHub transport remains unavailable, report the exact local commit and remote divergence without rewriting history.
