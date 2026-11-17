# V27 Motor and Spool Orthogonal-Axis Correction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Correct V27 so the removable M2006 motors stay vertical, each wet spool rotates about a horizontal local-tangent axis, the motor and spool axes are perpendicular, and the actual cable tangent is collinear with the radial tendon path to its matching root inlet.

**Geometry:** For each channel define radial `R=(cosθ,sinθ,0)`, tangential `T=(-sinθ,cosθ,0)`, and vertical `Z=(0,0,1)`. Motor axes are `Z`; spool axes are `T`; therefore motor/spool axes are perpendicular and spool axis is perpendicular to radial tendon direction. Place the spool axis center at radial radius `r` and height `z_t - R_eff`; the cable contacts the upper cylindrical surface at `(r R, z_t)` and leaves along `R`. A fixed 90-degree bevel stage transfers rotation from the vertical motor-driven shaft to the horizontal spool shaft.

**Important interface consequence:** Horizontal spools straddle the existing top-plate plane. Model the needed spool pockets, transverse seal supports and bevel envelopes explicitly; audit plate ligaments, wet/dry separation and service clearances. Gear teeth and final gear SKU remain unselected, so gear solids are only labelled pitch/envelope proxies.

**Test method:** TDD. First add failing checks that distinguish the actual motor axis from the actual spool axis, derive the tangent contact from the spool surface, and reject the previous parallel-axis geometry. Only then change the CAD implementation.

---

### Task 1: Correct the regression tests

- [ ] Assert the installed M2006 geometry has vertical axes and the spool geometry has local-tangent horizontal axes.
- [ ] Assert the motor axis and spool axis dot product is zero for all three channels.
- [ ] Compute upper tangent point from actual spool center, effective radius, and spool axis; check the line to the root inlet is collinear with the radial tendon direction.
- [ ] Run the new tests against the current model and record the expected failures.

### Task 2: Rebuild the fixed drive geometry

- [ ] Separate `motor_axis`, `spool_axis`, motor center, spool center, contact point, and cable direction in `DriveAxis`.
- [ ] Keep M2006 motors and their removable plate vertical, retaining the existing fixed vertical input shaft/coupling interface.
- [ ] Add provisional miter/bevel gear envelope pairs at each channel to turn the fixed vertical input into a horizontal tangent-axis output.
- [ ] Orient each wet spool, output shaft, bearings, seal/labyrinth proxies and retainers along `T`; keep the spool fixed to the base module.
- [ ] Rework top-plate pockets/seal supports for the horizontal spools and check clearances and remaining ligaments.
- [ ] Ensure the spool's real upper cylindrical tangent is a straight radial path through the matching root inlet.

### Task 3: Verify, regenerate, document

- [ ] Run focused drive tests, then the full V27 test suite.
- [ ] Run collision, shaft-support, service-module, plate-ligament, spool-surface tangent and four-segment mesh audits.
- [ ] Regenerate STEP/STL and full-assembly, drive-module and exploded-module previews; visually inspect all three motor/spool orientations.
- [ ] Update README and audit records, regenerate the SHA256 manifest, and run `git diff --check`.
- [ ] Keep the result labelled as a static CAD candidate, not a print, strength, gear-mesh or underwater release.
