# Hardware End-to-End Simulation Design

**Status:** executed as a software scenario simulation on 2026-10-26  
**Basis:** `local/spiral-soft-arm/hardware/M3508_C620_供电拓扑重规划_2026-10-25.md` and the currently selected component candidates discussed with the user.

## Intent

Run a repeatable, no-hardware scenario simulation of shore power, USB-C PD, 4S battery charging and backup, UPS source selection, STM32/C620 CAN command and feedback, current limits, and fault shutdown. The goal is to expose interface and power-budget contradictions before physical wiring.

## Approaches

- A SPICE model would represent electrical transients more faithfully, but the exact UPS, charger-board, and PD-to-AUX converter schematics/models are not available.
- A MuJoCo model would test robot mechanics, not this electrical topology.
- **Selected: standard-library Python scenario model plus protocol tests.** It can exercise source priority, 30-minute power budgets, 15-minute backup energy, fault interlocks, and the published C620 CAN frame encoding with explicit assumptions.

## Scope and constraints

- Retain 3× DJI M3508 P19 and 3× C620, the 24 V isolated supply architecture, 4S1P 8 Ah battery, 24 V/15 A boost module, ≤10 A backup output, and ≤5 A single-axis emergency branch. The original 4 mm² tether is superseded only in the rated-run simulation.
- Replace the undersized LMF500-20B24 (24 V, 20.9 A) and 4 mm² / 15 A tether assumptions for the rated three-axis retest with MORNSUN LMF1000-20B24 (24 V, 42 A) and a 10 mm² copper power pair provisionally budgeted to 35 A.
- Keep the old 20.9 A / 4 mm² / 15 A configuration as a superseded comparison. The 35 A cable budget is a simulation limit, not a verified ampacity rating; validate the actual wire, connectors, and protection.
- Exercise the recommended 100 W Type-C PD source, 20 V PD sink, 16.8 V/5 A charger ceiling, 30 A BMS candidate, and 24→5 V controller supply as candidates, not confirmed installed parts.
- Model an illustrative 10 W control/AUX load, 90% conversion efficiencies, and 80% usable battery energy. Sweep or label these assumptions; they are not measurements.
- Encode C620 standard CAN command ID 0x200 and feedback IDs 0x201–0x203 at 1 Mbps, using the published ±20 A command scale. Treat host-to-STM32 application framing and actual firmware as out of scope.
- Model source handoff as ideal logic. Do not claim brownout-free physical transfer, thermal behavior, water-pressure resistance, regenerative braking absorption, or physical CAN signal integrity.
- Do not modify the CAD, hardware topology baseline, wiring, firmware, or selected motors.

## Success criteria

- The simulator emits a JSON report with assumptions, 30-minute shore scenarios, source-priority transitions, backup runtime, Type-C charging limit, C620 CAN frames, and fault responses.
- Unit tests pass for three-axis overload detection, a limited one-axis run, PD charge throttling, ≥15-minute estimated backup, C620 frame encode/decode, and fail-safe outputs on CAN/temperature faults.
- The report distinguishes model passes from physical validation still required.

## Replacement retest result

The replacement configuration supports the static budget for three axes at 10 A each with charging paused. Running that motor load while charging at 5 A is below the provisional 35 A cable limit, but has only about 0.65 A of modeled current headroom; charger throttling is required near that point. This does not include startup transients or cable temperature.
