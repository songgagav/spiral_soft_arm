# Hardware End-to-End Simulation Plan

> **For agentic workers:** Use the inline execution workflow. Steps use checkbox syntax for tracking.

**Goal:** Run a reproducible software simulation of the selected M3508/C620 power, charging, backup, CAN, and fault topology.

**Architecture:** A dependency-free Python model computes current, power, battery reserve, source priority, and safety interlocks. A JSON CLI report and `unittest` suite provide auditable results.

**Tech Stack:** Python standard library (`dataclasses`, `json`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-10-26-hardware-e2e-simulation-design.md`

## Global Constraints

- Use the revised rated-run baseline: MORNSUN LMF1000-20B24, 24 V/42 A, and a 5 m one-way 10 mm² copper power pair provisionally limited to 35 A. Retain the old 24 V/20.9 A, 4 mm², 15 A case only as superseded comparison.
- Preserve the 4S1P 8 Ah pack, ≤10 A backup output, and ≤5 A emergency-axis branch.
- Keep motor and ESC selection unchanged.
- Treat unmeasured efficiencies and control/AUX load as labeled assumptions.
- Do not call the simulation physical hardware validation.
- Leave CAD, wiring diagrams, firmware, and Git history untouched; do not commit or push.

## Review Focus

- Three motors at the documented nominal 10 A each exceed the selected shore source and tether limit.
- Type-C auxiliary load must reduce battery charging current below the charger’s 5 A maximum.
- Battery-to-24 V backup current and 15-minute reserve depend on usable energy and converter efficiency assumptions.
- C620 signed current encoding, command/feedback IDs, standard-frame length, and 1 Mbps setting must match the manufacturer protocol.
- CAN loss, temperature fault, and emergency stop must drop K1/K2 while preserving controller power when an UPS source remains.

---

### Task 1: Implement and run the scenario simulator

**Files:**
- Create: `local/spiral-soft-arm/hardware/simulation/test_hardware_e2e.py`
- Create: `local/spiral-soft-arm/hardware/simulation/hardware_e2e_sim.py`
- Create: `local/spiral-soft-arm/hardware/simulation/hardware_e2e_sim_results.json`
- Create: `local/spiral-soft-arm/hardware/simulation/hardware_e2e_sim_report.md`

**Interfaces:**
- CLI: `python hardware_e2e_sim.py --json` writes one JSON report to stdout.
- Report fields include `shore_scenarios`, `pd_budget`, `backup`, `source_transitions`, `can_protocol`, `faults`, `assumptions`, and `physical_gates`.

- [x] **Step 1: Write and run failing tests.** The initial availability test failed because the simulator CLI did not exist yet; behavioral assertions cover one-axis shore operation, three-axis overload, PD charge throttling, backup energy, C620 frames, source priority, and fault shutdown.
- [x] **Step 2: Implement the minimal model.** Added configuration dataclasses, source-selection logic, current and energy calculations, C620 frame encode/decode, fault-state resolution, and JSON CLI output.
- [x] **Step 3: Re-run the tests.** `py -3 -m unittest discover -s local/spiral-soft-arm/hardware/simulation -p test_hardware_e2e.py -v` passed all 11 tests.
- [x] **Step 4: Generate the report and review its classifications.** Generated the JSON result and Chinese Markdown report. Model-level outcomes are separated from physical validation gates.

### Task 2: Replace the undersized shore supply and tether, then retest

**Files:**
- Modify: `local/spiral-soft-arm/hardware/simulation/hardware_e2e_sim.py`
- Modify: `local/spiral-soft-arm/hardware/simulation/test_hardware_e2e.py`
- Regenerate: `local/spiral-soft-arm/hardware/simulation/hardware_e2e_sim_results.json`
- Regenerate: `local/spiral-soft-arm/hardware/simulation/hardware_e2e_sim_report.md`

- [x] **Step 1: Add red tests for the replacement configuration.** Require 24 V/42 A, 10 mm² copper, 35 A provisional cable limit, and a three-axis 10 A run to fit the static budget.
- [x] **Step 2: Update the model to MORNSUN LMF1000-20B24 and the 10 mm² tether.** Preserve the previous configuration as a superseded comparison in the report.
- [x] **Step 3: Retest power cases.** Confirm three axes at 10 A with charging paused, and flag simultaneous 5 A charging as low margin.
- [x] **Step 4: Re-run all regression tests and regenerate the report.** All 14 tests passed; results remain scenario estimates, not physical validation.
