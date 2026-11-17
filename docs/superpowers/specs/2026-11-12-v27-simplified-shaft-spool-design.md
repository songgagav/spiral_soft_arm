# V27 Dry-Side Input Shaft and Wet-Side Spool Simplification

## Intent

Reduce the number of drive parts and motor-change steps without sacrificing a positive torque path, a replaceable wet-side line spool, or access to service components.

## Current arrangement and findings

- The M2006 D6 output shaft engages a separate dry-side coupling sleeve. A Ø2.8 mm cross-pin passes through the motor's transverse hole.
- The coupling sleeve also has a D10 bore for the vertical input shaft and a modeled M3 set screw. The set-screw station is currently Z=-42 mm, while the vertical D10 shaft begins at Z=-37.2 mm; the current CAD reports a 3.4 mm gap from screw to shaft, so this screw does not retain the shaft.
- The wet-side line spool is already a single part with a D-bore. It is separate from the Ø10 mm horizontal output shaft and sits between the shaft seals and labyrinth features. The present CAD has no positive spool axial keeper.
- The cable tangent, 90-degree bevel-gear handoff, horizontal shaft, bearings, seal journals, and wet/dry boundary are fixed interfaces for this change.

## Approaches considered

1. **Selected: one-piece dry-side coupling collar and vertical input shaft; separate wet-side spool.** Machine the D6 motor socket and the vertical shaft as one stepped 316L candidate part. Keep the existing removable motor cross-pin. Keep the spool a separate replaceable part with circular clearance bore, removable drive pin, and positive axial retainer. This removes the loose dry-side coupling interface and its ineffective set screw while preserving spool replacement. It makes the vertical shaft a custom CNC part.
2. **Keep the sleeve separate and correct its engagement.** Move the M3 retention feature onto the D10 engagement and revisit the 2.2 mm current overlap. This keeps each part replaceable but retains a fastener and an additional motor-service step.
3. **Integrate the wet spool and horizontal output shaft.** This removes the drive-pin joint and a separate spool retainer, but service requires removing the shaft, bearings, and seals together. The Ø24 mm spool flange cannot pass through the present Ø22 mm seal/bearing seat openings, so this route would need a redesigned service path.

Approach 1 is selected because it removes a dry-side interface while leaving the wet spool independently replaceable. It does not claim that the spool can be extracted with all shaft supports installed.

## Selected design constraints

- Preserve the motor's D6 shaft and transverse-pin interface: nominal Ø6.2 mm socket, 13 mm engagement, and a removable Ø2.8 mm pin aligned to the motor cross-hole. Model the D profile, not a round hole: the official STEP cross-section measures the shaft flat at 2.5 mm from axis; use a 2.6 mm socket flat, aligned so its normal is the radial cross-pin axis. This leaves 0.1 mm nominal radial/flat clearance, subject to physical fit validation. Keep the current Ø15 mm local collar envelope around the socket to preserve a substantial socket wall.
- Continue the collar into the existing Ø10 mm vertical input shaft and the existing Ø8 mm D-flat bevel-gear journal. Preserve the gear center, shaft axis, support positions, motor module boundary, and tendon tangent geometry.
- End the Ø15 mm collar 0.2 mm before the first input bearing while the Ø10 mm shaft continues through both bearing stations. This is nominal CAD clearance only, not a manufacturing tolerance.
- Remove the separate `fixed_coupling_sleeve` and ineffective `fixed_coupling_lock_screw` geometry. The motor cross-pin remains the motor retention feature.
- Keep the wet spool a separate single-piece component with a Ø10.1 mm circular clearance bore. A removable Ø2.5 mm radial drive pin through the spool hub and output shaft transmits torque and is withdrawn before axial extraction.
- Add one positive, tool-serviceable axial keeper for the wet spool. It must not use friction alone for axial retention, rub the rotating seal/labyrinth surfaces, or interrupt the polished Ø10 mm seal journals. The CAD pass must determine a keeper and labyrinth arrangement that fits the actual shaft section.
- Document the spool service sequence. Because the spool is wider than the current seal/bearing through-openings, the service path may require releasing one removable support/seal carrier before the spool can slide off the shaft.

## Goals and non-goals

Goals: lower the part/fastener count at the motor coupling, simplify motor disconnection, keep the existing right-angle transmission and line route, and make spool axial retention explicit and serviceable.

Non-goals: changing the M2006 motor, gear ratio, spool radius/cable tangent, electronic package, arm geometry, or pressure-boundary concept. The cover remains floodable and the electronic bay remains the pressure boundary.

## Acceptance checks

- The integrated input shaft has a valid solid and sufficient wall around the complementary D6 socket and cross-pin hole; the motor proxy has the matching D6 external profile, and the socket seats on it with the documented nominal clearance.
- The motor can be removed by removing the existing cross-pin and sliding it off the integrated shaft; no hidden coupling screw is required.
- The bevel-gear journal, both input supports, and all existing seal/shaft alignments remain unchanged.
- The spool has a modeled positive axial stop and a clear documented removal path. The keeper and drive pin clear the labyrinths and seals; after the pin is removed, the circular bore slides over the round Ø10 mm seal journal.
- The tendon leaves the spool tangentially on the existing straight path to the root cable entry.
- Update the drive detail sheet, assembly/service audit, README, STEP exports, and SHA-256 delivery manifest. Record remaining manufacturing and physical-validation limits separately.

## Verification boundary

CAD checks can establish nominal geometry, collision clearances, and the modeled service path. They do not establish CNC tolerances, cross-pin shear strength, shaft fatigue, corrosion resistance, seal life, or underwater performance. Actual motor and shaft measurements, a machined fit check, and wet testing remain separate gates.

## Implementation ruling

- The first 32 mm spool sweep failed because a D-bore spool cannot pass over the round Ø10 mm seal journal. To preserve round seal surfaces and the replaceable-spool path, the spool uses a Ø10.1 mm circular clearance bore plus one removable Ø2.5 mm radial drive pin through the hub and shaft. The cable must be detached and unwrapped and the pin withdrawn before axial extraction. This adds one removable pin per spool and requires torque/shear, corrosion, and retention validation.
- Final review found the first M2006 socket cut was circular although the approved interface called for D6. The official STEP cross-section gives a 2.5 mm flat offset; the motor proxy now has that D6 profile and the one-piece shaft socket has a matching 2.6 mm flat offset, aligned to the radial cross-pin axis. The 0.1 mm nominal fit still needs a CNC coupon check.
- The Ø10.1 printed spool bore over a Ø10 mm shaft has only 0.05 mm nominal radial clearance. CAD sweep clearance is not print-fit evidence; require a spool/shaft coupon and ream or post-process as needed before a full spool print.
