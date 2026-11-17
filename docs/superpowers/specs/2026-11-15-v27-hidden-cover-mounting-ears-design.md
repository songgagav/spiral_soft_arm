# V27 Root Cover Hidden Mounting Ears

## Intent

Connect the six-panel V27 root cover to the fixed hexagonal top plate without changing the approved exterior: the lower vertical wall, single upper taper, two raised ribs, four fastener rows, and two large observation openings stay as designed. The connection must use accessible M3 hardware, avoid the motor windows, and release when an upper cover panel is removed.

The model currently has a 64 mm axial separation between the fixed top plate top face at Z=0 and the cover's top edge at Z=64. The selected design connects the cover at the plate's Z=0 face with hidden internal mounting ears; it does not try to move the top edge down to the plate.

## Current Geometry

- The fixed top plate is a regular hexagonal prism with a 250 mm vertex-to-vertex diameter, spanning Z=-8…0 mm.
- The plate already has six Ø3.2 mm through holes on a 100 mm radius at 30° increments.
- Upper cover face normals are 30°, 90°, 150°, 210°, 270°, and 330°. Motor windows occupy 90°, 210°, and 330°.
- The three remaining faces at 30°, 150°, and 270° have no upper motor windows. Their top-plate holes are available for cover retention.

## Approaches

1. **Three hidden ears integrated with upper panels — selected by the user.** Add one radial shelf to each upper panel at normals 30°, 150°, and 270°; each shelf carries an M3 vertical fastener aligned to the existing top-plate hole at radius 100 mm. This uses the fewest separate parts and preserves the external outline. To remove one of these panels, first release its M3 plate fastener, then pull the panel radially outward.
2. **Three separate L brackets.** These can print as flat, replaceable parts but add bracket-to-panel fasteners and extra service steps.
3. **A continuous inner hexagonal collar.** This distributes retention around all faces, but uses the most material and can obstruct the motor and service envelope.

## Proposed CAD Contract

- Add three ears only to upper panels 01, 03, and 05 (face normals 30°, 150°, and 270°); do not add them to the three motor-window panels.
- Keep each ear internal and fuse it into its upper panel as one valid solid. The initial nominal section is 18 mm tangential width × 8 mm vertical height. Its bottom face rests on the plate top face at Z=0; it extends to Z=8 mm.
- Extend the ear radially from the panel's inner face to radius 92 mm. The upper panel wall at Z=0 has inner apothem equal to R-at-Z0 times cos(30°) minus panel thickness; derive the exact ear length from the existing profile and include a small fusion overlap into the panel. Radius 92 mm leaves nominal 2 mm clearance outside the Ø180 mm root-flange envelope.
- Put a Ø3.4 mm vertical clearance hole at radius 100 mm on the existing face normal. The hole must be coaxial with the matching Ø3.2 mm plate hole. The through-bolt receiver and exact bolt length are not frozen; for geometry review, use an M3 through-bolt and underside nut envelope unless that envelope collides with existing parts.
- Do not change the exterior cover profile, windows, M3 panel rows, two external ribs, top-plate shape, arm, drive, or electronics.

## Verification

- Unit tests check the exact three host panels, one ear per panel, one-solid fusion, the 18 × 8 mm nominal section, clearance to the Ø180 mm root-flange envelope, and hole centers at the existing plate interfaces.
- Assembly audit checks zero forbidden intersections, ear-to-plate seating at Z=0, through-hole alignment, top-side driver access, underside receiver clearance, and upper-panel radial removal after the M3 connector fasteners are released.
- Regenerate assembly STEP, transparent and opaque cover previews, the audit JSON, README/preprint text, and delivery hashes only after these checks pass.
- CAD evidence does not prove print strength, fastener preload, material creep, slicer success, waterproofing, or underwater pressure performance.

## Open Boundary

The M3 through-bolt receiver and purchased hardware dimensions remain a preprint confirmation item. The design must keep this uncertainty visible in the audit and documentation rather than treating nominal CAD contact as a tested joint.

## Service-Path Interaction Found During Integration

The ear-bearing panels intersect the existing 32 mm output-support cartridge extraction sweeps while those panels remain installed. The CAD audit found about 393 mm³ of swept overlap per corresponding route. The three upper panels themselves can be pulled radially outward 120 mm with no sampled collisions after releasing their four panel fasteners and one new plate-retention bolt. Therefore each paired upper panel is a required service prerequisite before withdrawing its output-support cartridge. The audit and instructions must show that sequence explicitly. This adds a cover-removal step; it does not qualify hardware access or structural strength in a printed part.
