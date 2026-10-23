# B32 Shared Dry Motor Chamber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Place all three M2006 motors inside one connected dry chamber while leaving only reels wet and retaining straight tangent tendon routing.

**Architecture:** Create v12 from the v11 parametric model. Move reels inward and lower the central electronics chamber, then connect three sealed motor lobes to the central dry space with modeled dry ducts. Render wet/dry boundary and inspection views directly from v12 geometry.

**Tech Stack:** Python 3, CadQuery 2.8, VTK, matplotlib, STEP.

**Spec:** `docs/superpowers/specs/2026-10-23-b32-shared-dry-motor-chamber-design.md`

## Global Constraints

- 250 mm hex top disk; printer 350 × 350 × 320 mm; arm segments below 250 mm.
- Three horizontal M2006 motors share the dry chamber; only reels/tendon runs wet.
- Preserve v11 unchanged; publish v12 as a CAD candidate, not a pressure certified print release.

## Review Focus

- Water paths through wet reel wells into the common dry cavity.
- Static joints where motor lobes connect to the central chamber.
- Rotating shaft seal stack and motor shaft side load.
- Motor, reel, canister, and fairing intersections after moving the canister.
- Tendon route curvature and clearance at chamfered plate holes.

## Task 1: Reposition motors and reels

- [ ] Create `electronics_enclosure_v12/parameters.json` and generator without editing v11.
- [ ] Set reel radius 55 mm and axial motor offset 64 mm; recalculate pod envelope and fairing clearance.
- [ ] Keep the three tangent exit points on the same radial lines as plate and arm holes.

## Task 2: Build shared dry boundary

- [ ] Move the central electronics canister below the motor layer and move its contents with it.
- [ ] Create three motor lobes, a connected dry duct from each lobe to the main canister, and three open wet reel zones with bearing/shaft/seal layouts.
- [ ] Add an explicit removable service lid/closure interface and label all still schematic seals.

## Task 3: Generate review artifacts

- [ ] Export STEP assembly and a translucent overview that shows internal motors.
- [ ] Export top view and a single-axis section with dry/wet regions and seal points.
- [ ] Record geometric clearances, path lengths, assembly bounds, part print bounds, and limitations in the audit and README.

## Task 4: Publish candidate

- [ ] Refresh checksums and root README status; retain v11 history.
- [ ] Review the generated artifacts and Git diff for accidental edits.
- [ ] Commit and push v12 to current `main`, following the user's established Git instruction.
