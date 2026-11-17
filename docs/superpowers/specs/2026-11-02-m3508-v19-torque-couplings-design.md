# M3508 v19 Gear and Reel Torque Couplings

## Intent

Revise the v18 one-channel M3508 drive model so both the miter-gear shafts and the wet cable reel have explicit, serviceable torque-locking interfaces. Keep v18 unchanged and generate a separately named v19 candidate.

## Goals

- Represent the selected KHK MMSA1.5-20R/L stock miter-gear pair and its native M4 screw interface.
- Add shaft flats aligned with the stock gear screws so the screws bear on flats rather than smooth round shafts.
- Change the reel bore from a loose round hole to a D bore matching the 10 mm output shaft.
- Add an axial retainer plate/washer and screw to keep the reel from sliding off the shaft while the D faces transmit torque.
- Preserve the existing motor position, 1:1 right-angle drive, reel position, straight tangent cable path, chamfered guide port, and dry/wet boundary unless a verified physical collision requires a local clearance correction.
- Export an editable script, STEP assembly, preview images, and a review report under a new v19 directory.

## Non-goals and anti-goals

- Do not overwrite v18 or alter the official DJI motor STEP source.
- Do not cut or reshape the stock KHK gears; fit and align the shafts to their factory bore and screws.
- Do not present envelope-only gear teeth as a functioning mesh.
- Do not claim validated torque capacity, pressure sealing, print strength, or print readiness from CAD alone.

## Constraints

- KHK catalog data for MMSA1.5-20R/L: 1:1 ratio, module 1.5, 20 teeth, 10 mm finished bore with tapped holes, 25 mm hub diameter, 30 mm pitch diameter, 31.9 mm outside diameter, 28 mm mounting distance, 18.48 mm overall length, 10.5 mm hub width, and 16.5 mm bore length. The table specifies 2-M4 set screws; its `L=6 mm` dimension locates the screw center axially from the gear back face and is not the screw length. KHK says a set screw is included for tapped-hole products. Catalog allowable torque values are reference figures, not a system-level proof.
- Model M4×8 mm set-screw proxies only to show the contact geometry from the Ø25 mm hub to the chosen shaft flats. The purchased screw length and exact angular spacing must be confirmed against the actual gears. Model the two screw axes 90° apart as an adjustable layout assumption, not a confirmed catalog dimension.
- Use stock screw positions and dimensions from KHK product data/CAD where available. If native tooth geometry cannot be retrieved, keep a clearly labeled catalog-dimension gear envelope and report that tooth contact remains unverified.
- Model the 10 mm shaft flats and reel D-bore with explicit preliminary assembly clearance. Record the chosen dimensions in `parameters.json`; treat them as fit prototypes pending a printed coupon and measurement.
- Make the axial retainer accessible from the reel's free end without intersecting the cable envelope, guide port, bearing, seal, or housing.
- Keep the current one-channel v18 coordinate frame and report any changed envelope dimensions.

## Approaches considered

1. **Stock KHK screws on shaft flats; D-bore reel with axial retainer (selected).** Preserves factory gears, gives the reel a positive torque face, and keeps the interfaces serviceable with few parts.
2. **Keyed shafts and keyed reel.** Provides positive torque transfer but requires more machining and changes the factory gear interface.
3. **Stock gear screws plus split-clamp reel hub.** Avoids a D-bore fit but adds radial bulk and fasteners close to the cable path.

The user selected approach 1. The model author will determine minor fit dimensions from the stock CAD and existing shaft envelope, and label print-fit values as preliminary.

## Verification boundary

The v19 review checks model validity, gear and shaft clearances, screw/flat contact placement, D-bore fit, retainer access, reel/cable clearance, and the preserved straight cable route. It does not establish gear tooth meshing unless actual manufacturer tooth CAD is present, shaft fatigue capacity, screw preload, seal performance at 5 m, or print-release status.

## Local correction found during implementation

The inherited v18 stack had an actual CAD overlap between the fixed labyrinth envelope, seal support, and bulkhead, and the bulkhead opening was too small for the support sleeve. The v19 implementation moves the labyrinth ring to the wet-side bulkhead face, enlarges the bulkhead opening to Ø24.1 mm for the Ø24 mm seal-support envelope, and represents the oil-seal and bearing seats as two separate support rings. A second measured overlap between the labyrinth and outer reel flange required moving the reel and guide-port plane 1.5 mm wetward together; the radial tangent route and line length remain unchanged. Their housing connection and retention remain unresolved and are explicitly recorded in the geometry review.

## Sources

- KHK, *Miter Gears*, MMSA1.5-20R/L catalog table: https://khkgears.net/pdf/2025/miter-gears.pdf
- KHK, *Miter Gears*, product precautions and included set-screw note: https://khkgears.net/pdf/2025/miter-gears.pdf
- KHK, *Gear Drawings*: https://khkgears.net/korea/gear_drawing.html
