# V27 Faceted Cover Redesign and Drive Detail Views

## Intent

Give the V27 base cover a more deliberate, finished six-sided appearance and provide clear CAD-derived views of the existing M2006-to-spool drivetrain. Preserve the working mechanism, service access, cable route, and modular removal paths.

## Current geometry and fixed interfaces

- V27 uses twelve flat printed cover panels, in upper/lower halves, with a nominal 324 mm maximum outer diameter, 300 mm height, and a split at Z=-80 mm.
- The cover has three motor service openings, three inspection openings, and a Type-C access opening. The cover is floodable and is not a pressure boundary.
- Three M2006 motors remain vertical and removable as one plate. Each drives a fixed one-piece D6 socket input shaft with a removable cross pin, then a 90-degree 1:1 bevel pair. The horizontal Ø10 mm shaft has an Ø8 mm D-flat gear journal, paired 6900 supports, two 10×22×7 mm seal candidates with external labyrinths, and an independently replaceable round-bore wet spool with radial drive pin and a positive retaining ring. The tendon leaves the spool tangent in a straight radial path to the arm-root hole.
- The motor, coupling, shafts, bearing/seal layout, spool centers, tendon paths, electronics envelope, and arm/drive extraction paths are fixed interfaces for this scope.

## Approaches considered

1. **Faceted stepped armor, selected and approved by the user:** retain the twelve flat print panels, emphasize the shoulder and lower taper with four shallow hexagonal exterior bands, and add clipped-corner service-window surrounds that stand outward from the panel faces. This improves visual hierarchy while preserving the planar print strategy and internal space.
2. **Exposed rib cage:** emphasize a sparse frame around recessed panels. This improves visibility but leaves more electronics and transmission exposed and increases the number of visually dominant frame members.
3. **Narrow tapered shell:** reduce the apparent bulk with a stronger inward taper. This is less suitable because it competes with the installed Ø324 mm assembly envelope, device clearance, and existing access openings.

## Goals and constraints

- Keep all printed cover panels planar and individually removable.
- Keep the existing panel profile stations, Z split, and service-window clear dimensions; use profile-following hexagonal armor bands with 4 mm radial thickness. The three straight-wall bands have 166 mm outer circumradius. The base band follows the sloped panel from 102 mm at Z=-236 mm to 106.063 mm at Z=-228 mm, with a local Type-C clearance notch.
- Keep the largest outside diameter at 332 mm, leaving 18 mm total nominal XY platform margin on the 350 mm printer.
- Make window surrounds 8 mm wide and 2.5 mm proud, with clipped outer corners and 1.5 mm per-side reveal; expand the outer profile to retain the full 8 mm border, preserve aperture dimensions, and keep added geometry outside the panel face.
- Keep the current panel count, split location, inspection/service openings, and cover mounting interfaces unless local exterior geometry alone can change them safely.
- Add visual structure only outward of the current panel surfaces; do not intrude into the verified component envelope.
- Keep the maximum printed footprint within the 350×350 mm printer platform.
- Preserve the single-piece hexagonal root guard with its three M3 fasteners and two locator ears from the current V27 worktree.
- Add CAD-derived detail views: a three-quarter installed overall render; an opened/exploded cover view; a single-drive isometric showing motor, sleeve, shaft, bevel gears, supports, seals, labyrinth, spool and straight tendon; and a coupling/spool interface close-up showing the D interfaces and cross-pin retention.
- Do not use illustrative geometry as evidence of actual gear-tooth engagement, seal performance, or material strength. Existing parts remain dimensioned proxies where the repository labels them as such.

## Independent review corrections

- The first fixed-radius base band overlapped the tapered lower panels. Replace it with a loft that follows the panel profile while maintaining the 4 mm external offset. The Type-C outer surround overlaps this band in Z, so provide a local through-clearance notch beneath it and preserve the two side flanks and radial fastener axes. If the notch is incorrectly sized, the local border may be obstructed or weakened.
- The original 0.5 mm surround reveal obstructed a 30 mm deep near-full radial gauge by 21.27 mm³. Use 1.5 mm per-side reveal and preserve the full 8 mm surround width by expanding the surround outward.
- The repository-wide `local/` ignore rule hides the V27 source, review assets, and coupon files from Git. Force-add only the files listed in the V27 source/hash manifest so a clean clone contains the referenced deliverables without exposing unrelated local artifacts.

## Out of scope

- Relocating or resizing motors, shafts, spools, bearings, gears, seals, electronics, top plate, arm root, or cable entry.
- Turning the floodable cover into a pressure vessel or sealing the inspection openings.
- Revising the selected one-piece root guard attachment.

## Acceptance evidence

- Updated STEP for the cover and updated full assembly use the revised exterior geometry.
- Views clearly show the cover styling and the requested motor/sleeve/shaft/spool details.
- Boolean checks show no volume intersection between the profile-following base band and any lower panel, and a 30 mm deep near-full gauge passes through the lower inspection and Type-C windows.
- Every V27 source-manifest path exists in the commit, including the local CAD generator, review assets, and coupon files.
- Existing CAD clearance and service-path checks continue to pass; report nominal CAD evidence separately from physical print, load, and underwater qualification.
