# V27 Verification and Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add traceable analytical and CAD-proxy checks for V27 serviceability, wiring access and outstanding physical measurements before cover optimization.

**Architecture:** Keep geometry collision and removal sweeps in `generate_v27_assembly.py`; place calculation assumptions and unmeasured-input tracking in `engineering_audit.py`. The generated JSON becomes the single audit handoff, while the review document explains the limits and the bench-test data still required.

**Tech Stack:** Python 3.12, CadQuery 2.8, unittest, STEP/STL exports.

**Spec:** `docs/superpowers/specs/2026-11-11-v27-verification-accessibility.md`

## Global Constraints

- V27 remains a CAD candidate, not print or underwater release.
- Existing module boundaries, 250 mm top plate and tendon paths stay fixed.
- No fabricated physical measurements; missing inputs remain explicitly unqualified.
- Work in the existing linked worktree on `feat/v27-modular-m2006`.

## Review Focus

- A proxy cable route must reject collisions with every non-endpoint component, not only controller backing plates.
- Maintenance routes must name every required removed component so a passing sweep cannot hide a disassembly prerequisite.
- Missing mass, buoyancy, efficiency, seal drag, friction, current and spool-turn measurements must never turn the engineering report qualified.
- Connector service envelopes must keep their existing collision protections after any route audit is added.
- Documentation must distinguish a CAD path from a physical bench or water test.

### Task 1: Traceable engineering-input audit

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/engineering_audit.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_engineering_audit.py`

**Interfaces:**
- Produces: `measurement_plan` mapping in `generate_v27_engineering_audit(contract)`.

- [ ] Write failing tests for named bench tests and unqualified missing-value status.
- [ ] Run the focused test and verify it fails because `measurement_plan` is absent.
- [ ] Add `measurement_plan` with inputs, bench method, acceptance evidence and status `pending_physical_measurement`; preserve `qualified: false`.
- [ ] Run focused engineering tests and verify they pass.

### Task 2: Wiring and service-route CAD audit

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/generate_v27_assembly.py`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/test_v27_integration.py`

**Interfaces:**
- Consumes: Task 1's audit status conventions.
- Produces: `service.wiring_accessibility` mapping in `audit_v27_assembly(result)`.

- [ ] Write failing tests requiring three named motor harness routes, non-endpoint obstacle checks, and explicit external connector service status.
- [ ] Run the focused integration test and verify it fails because `wiring_accessibility` is absent.
- [ ] Implement route probes and collision checks against all non-endpoint solids; record route names, checked obstacles, collisions and physical limitations.
- [ ] Run focused integration tests and verify they pass.

### Task 3: Generated audit, documentation and delivery integrity

**Files:**
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/README.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/preprint_review/V27打印前审查.md`
- Modify: `local/spiral-soft-arm/solidworks/integrated_assembly_v27_1m_modular_m2006/来源与SHA256.csv`

**Interfaces:**
- Consumes: Task 1 `measurement_plan` and Task 2 `wiring_accessibility`.
- Produces: generated `V27工程审计.json` and `V27装配审查.json` with current results.

- [ ] Write failing delivery tests requiring both audit sections and physical-test wording.
- [ ] Run the focused delivery tests and verify they fail before documentation is updated.
- [ ] Update documents, regenerate both JSON audits and refresh the manifest.
- [ ] Run all unit tests, manifest verification and `git diff --check`.

## Self-review

- Physical quantities remain unmeasured and unqualified; the plan records an actionable bench method instead of an invented result.
- Service routes cover motor controls, external power access and both modular removal sequences.
- Cover changes are deliberately deferred until the new audit identifies no geometric defect.
