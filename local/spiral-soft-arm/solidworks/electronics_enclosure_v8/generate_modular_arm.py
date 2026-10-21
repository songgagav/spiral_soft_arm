"""B32 joint-internal dovetails and compact wet-side motor/reel layout.

The central electronics envelope, wet motors, and tendons come from v5.  This
is a geometric review candidate, not a print or underwater release.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
V5_PATH = (HERE / CFG["reference_v5_script"]).resolve()
JOINT_PATH = (HERE / CFG["reference_joint_data"]).resolve()
spec = importlib.util.spec_from_file_location("b32_enclosure_v5_reference", V5_PATH)
v5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v5)

OUT_ASSEMBLY = HERE / "B32_三段机械臂_六边形包覆总装.step"
OUT_ARM = HERE / "B32_三段机械臂_燕尾榫装配.step"
OUT_PREVIEW = HERE / "B32_三段燕尾榫_六边形包覆预览.png"
OUT_DETAIL = HERE / "B32_燕尾榫接口与六边形顶盘细节.png"
OUT_DRIVE = HERE / "B32_电机线轮俯视布局.png"
OUT_SIDE = HERE / "B32_线轮到线孔直线路径侧视.png"
OUT_AUDIT = HERE / "分段与装配几何审计.json"
OUT_PRINT = HERE / "print_parts"


def hex_prism(radius: float, z0: float, z1: float) -> cq.Shape:
    xy = [(radius * math.cos(math.radians(-30 + 60 * i)),
           radius * math.sin(math.radians(-30 + 60 * i))) for i in range(6)]
    return cq.Workplane("XY").polyline(xy).close().extrude(z1 - z0).translate((0, 0, z0)).val()


def polygon_wire(radius: float, z: float) -> cq.Wire:
    vertices = [cq.Vector(radius * math.cos(math.radians(-30 + 60 * i)),
                          radius * math.sin(math.radians(-30 + 60 * i)), z)
                for i in range(6)]
    return cq.Wire.makePolygon(vertices + [vertices[0]])


def wedge(angle: float, z0: float, z1: float) -> cq.Shape:
    a0, a1 = math.radians(angle - 30), math.radians(angle + 30)
    return (cq.Workplane("XY").polyline([(0, 0),
            (300 * math.cos(a0), 300 * math.sin(a0)),
            (300 * math.cos(a1), 300 * math.sin(a1))])
            .close().extrude(z1 - z0).translate((0, 0, z0)).val())


def frame(angle: float) -> tuple[cq.Vector, cq.Vector]:
    t = math.radians(angle)
    return cq.Vector(math.cos(t), math.sin(t), 0), cq.Vector(-math.sin(t), math.cos(t), 0)


def tab_wire(angle: float, offset: float, r0: float, r1: float,
             half_width: float, z: float) -> cq.Wire:
    radial, tangent = frame(angle)
    vertices = [radial * r + tangent * u + cq.Vector(0, 0, z)
                for r, u in ((r0, offset-half_width), (r1, offset-half_width),
                             (r1, offset+half_width), (r0, offset+half_width))]
    return cq.Wire.makePolygon(vertices + [vertices[0]])


def radial_hole(angle: float, offset: float, z: float, diameter: float,
                r0: float, length: float) -> cq.Shape:
    radial, tangent = frame(angle)
    return cq.Solid.makeCylinder(diameter / 2, length,
                                  radial * r0 + tangent * offset + cq.Vector(0, 0, z), radial)


def make_fairing() -> dict[str, cq.Shape]:
    # V5 panel outline and open windows are retained.  The top attachment
    # holes move toward face corners to clear the tangential wet motors.
    outer = cq.Solid.makeLoft([polygon_wire(r, z) for z, r in
                              [(-8, 131.5), (-80, 141.5), (-236, 98)]], ruled=True)
    inner = cq.Solid.makeLoft([polygon_wire(r, z) for z, r in
                              [(-7, 126.5), (-8, 126.5), (-80, 136.5), (-236, 93), (-237, 93)]], ruled=True)
    shell = outer.cut(inner)
    for angle in (0, 120, 240):
        shell = shell.cut(v5.rotate(v5.box(65, 210, -36, 36, -132, -28), angle))
    for angle in (60, 180, 300):
        shell = shell.cut(v5.rotate(v5.box(65, 210, -30, 30, -188, -110), angle))
    shell = shell.cut(v5.rotate(v5.box(65, 210, -18, 18, -228, -206), 180))
    for angle in range(0, 360, 60):
        for z, offset in ((-12, 54), (-74, 50), (-88, 40), (-226, 36)):
            for sign in (-1, 1):
                shell = shell.cut(radial_hole(angle, sign*offset, z, 3.3, 80, 100))
    panels = {}
    for angle in range(0, 360, 60):
        sector = wedge(angle, -240, 5)
        panels[f"upper_panel_{angle:03d}"] = shell.intersect(sector).intersect(
            v5.box(-250, 250, -250, 250, -80, -8)).clean()
        panels[f"lower_panel_{angle:03d}"] = shell.intersect(sector).intersect(
            v5.box(-250, 250, -250, 250, -236, -80)).clean()
    return panels


def make_plate(mount: object) -> tuple[cq.Shape, list[cq.Shape]]:
    c = CFG["hex_plate"]
    plate = mount.plate.intersect(hex_prism(c["circumradius_mm"], -8, 0))
    # Preserve the v5 blind-post provision for the sealed electronics canister.
    for angle in (60, 180, 300):
        radial, _ = frame(angle)
        plate = plate.cut(v5.cyl(2.15, -8.2, .2, 47*radial.x, 47*radial.y))
    tabs = []
    for angle in c["face_angles_deg"]:
        for offset in c["upper_panel_tab_offsets_mm"]:
            # The outer face follows the sloped inside of the upper panel,
            # leaving a 0.25 mm geometric clearance at both tab ends.
            def panel_inner_face(z: float) -> float:
                radius = 126.5 + (-8-z) * 10 / 72
                return radius * math.cos(math.pi/6) - c["tab_gap_to_panel_mm"]
            tab = cq.Solid.makeLoft([
                tab_wire(angle, offset, 104, panel_inner_face(z),
                         c["tab_tangential_width_mm"]/2, z)
                for z in (-8, -18)], ruled=True)
            hole = radial_hole(angle, offset, c["tab_hole_z_mm"],
                               c["tab_hole_diameter_mm"], 100, 25)
            tab = tab.cut(hole)
            tabs.append(tab)
            plate = plate.fuse(tab)
    return plate.clean(), tabs


def make_root_guard(plate: cq.Shape) -> tuple[cq.Shape, dict[str, cq.Shape]]:
    c = CFG["root_guard"]
    z0, z1 = c["bottom_z_mm"], c["top_z_mm"]
    guard = hex_prism(c["outer_hex_circumradius_mm"], z0, z1).cut(
        hex_prism(c["inner_hex_circumradius_mm"], z0-1, z1+1))
    for angle in range(0, 360, 60):
        for offset in c["panel_hole_tangential_offsets_mm"]:
            guard = guard.cut(radial_hole(angle, offset, c["panel_hole_z_mm"],
                                          c["panel_hole_diameter_mm"], 35, 30))
        if angle in (60, 180, 300):
            guard = guard.cut(v5.rotate(v5.box(40, 80, -8, 8, 10, 17), angle))
    panels = {}
    for angle in range(0, 360, 60):
        panels[f"root_guard_{angle:03d}"] = guard.intersect(wedge(angle, -1, z1+1)).clean()

    # Small bosses on the disk, rather than a continuous collar, make the
    # guard removable and clear the existing split root retainer.
    for angle in range(0, 360, 60):
        for offset in c["panel_hole_tangential_offsets_mm"]:
            boss = cq.Solid.makeLoft([
                tab_wire(angle, offset, 40, 44.78, 5, 0),
                tab_wire(angle, offset, 40, 44.78, 5, 10)], ruled=True)
            boss = boss.cut(radial_hole(angle, offset, c["panel_hole_z_mm"],
                                        c["panel_hole_diameter_mm"], 35, 25))
            plate = plate.fuse(boss)
    return plate.clean(), panels


def make_panel_splices() -> dict[str, cq.Shape]:
    # Two short, removable inside straps on each face join the upper and
    # lower flat panels through their existing M3 holes at z=-74 and -88.
    def inner_face(z: float) -> float:
        radius = 126.5 + (-8-z)*10/72 if z >= -80 else 136.5 + (z+80)*43.5/156
        return radius*math.cos(math.pi/6)
    brackets = {}
    for angle in range(0, 360, 60):
        for sign in (-1, 1):
            profile = [(-70,53),(-74,50),(-80,45),(-88,40),(-92,37)]
            wires = [tab_wire(angle, sign*offset, inner_face(z)-5.3,
                              inner_face(z)-.3, 4.5, z)
                     for z,offset in profile]
            bracket = cq.Solid.makeLoft(wires, ruled=True)
            for z,offset in ((-74,50),(-88,40)):
                bracket = bracket.cut(radial_hole(angle, sign*offset, z, 3.3, 110, 25))
            brackets[f"panel_splice_{angle:03d}_{'p' if sign > 0 else 'm'}"] = bracket.clean()
    return brackets


def dovetail_prism(points: list[list[float]], z0: float, height: float) -> cq.Shape:
    return (cq.Workplane("XY").polyline([tuple(p) for p in points]).close()
            .extrude(height).translate((0, 0, z0)).val())


def straight_tendon_points(angle: float, hole_radius: float) -> np.ndarray:
    """Four collinear points from the reel exit slot to the disk hole mouth."""
    d = CFG["drive_layout"]
    radial, _ = frame(angle)
    start = np.array([radial.x*d["motor_center_radius_mm"],
                      radial.y*d["motor_center_radius_mm"],
                      d["spool_center_z_mm"]+d["spool_width_mm"]/2])
    end = np.array([radial.x*hole_radius, radial.y*hole_radius,
                    d["tendon_hole_entry_z_mm"]])
    return np.array([(1-u)*start+u*end for u in (0., 1/3, 2/3, 1.)])


def make_vertical_mount(config: dict, source_mount: object) -> object:
    """Three vertical wet motors, axial reels, and open two-ring supports."""
    from types import SimpleNamespace
    d = CFG["drive_layout"]
    z = d["motor_center_z_mm"]
    motor_radius = config["motor_reference"]["outer_diameter_mm"]/2
    length = d["motor_body_length_mm"]
    width = d["spool_width_mm"]
    flange_t = d["spool_flange_thickness_mm"]
    plate = v5.cyl(CFG["hex_plate"]["circumradius_mm"], -8, 0)
    for angle in (0, 120, 240):
        radial, _ = frame(angle)
        plate = plate.cut(v5.cyl(2.1, -8.2, .2,
                                radial.x*config["plate"]["tendon_hole_radius_mm"],
                                radial.y*config["plate"]["tendon_hole_radius_mm"]))
    for angle in range(30, 390, 60):
        radial, _ = frame(angle)
        plate = plate.cut(v5.cyl(2.25, -8.2, .2,
                                radial.x*v5.CFG["base_plate_fixture_radius_mm"],
                                radial.y*v5.CFG["base_plate_fixture_radius_mm"]))
    root_rims = source_mount.root_rims
    for angle in (45,135,225,315):
        radial, _ = frame(angle)
        plate = plate.cut(v5.cyl(1.7,-8.2,.2,
                                radial.x*config["plate"]["root_clamp_fastener_radius_mm"],
                                radial.y*config["plate"]["root_clamp_fastener_radius_mm"]))
    motors, reels, shafts, saddles, centers = [], [], [], [], []
    for angle in (0,120,240):
        radial, tangent = frame(angle)
        center = radial*d["motor_center_radius_mm"] + tangent*d["motor_tangential_offset_mm"]
        centers.append((center.x, center.y, z))
        motor = cq.Solid.makeCylinder(motor_radius, length,
                                      cq.Vector(center.x,center.y,z-length/2),cq.Vector(0,0,1))
        spool_bottom = d["spool_center_z_mm"]-width/2
        reel = v5.cyl(d["spool_core_radius_mm"],spool_bottom,spool_bottom+width,center.x,center.y)
        reel = reel.fuse(v5.cyl(d["spool_flange_radius_mm"],spool_bottom,
                                  spool_bottom+flange_t,center.x,center.y))
        reel = reel.fuse(v5.cyl(d["spool_flange_radius_mm"],spool_bottom+width-flange_t,
                                  spool_bottom+width,center.x,center.y))
        reel = reel.cut(v5.cyl(d["shaft_bore_diameter_mm"]/2,
                                 spool_bottom-.2,spool_bottom+width+.2,center.x,center.y))
        # An open exit slot in the upper flange, aligned with the straight
        # radial line.  The winding-to-slot transition remains a proxy.
        slot = v5.box(d["motor_center_radius_mm"]-9,
                      d["motor_center_radius_mm"]+2,-1.4,1.4,
                      spool_bottom+width-flange_t-.2,spool_bottom+width+.2)
        reel = reel.cut(v5.rotate(slot,angle)).clean()
        shaft = v5.cyl(2,z+length/2,spool_bottom+.2,center.x,center.y)
        rings = []
        for rz in d["saddle_ring_z_mm"]:
            rings.append(v5.cyl(24.5,rz-4,rz+4,center.x,center.y).cut(
                         v5.cyl(22,rz-4.2,rz+4.2,center.x,center.y)))
        saddle = rings[0].fuse(rings[1])
        for sign in (-1,1):
            foot_center = center+tangent*(sign*24.5)
            support = v5.cyl(2.5,-116,-8,foot_center.x,foot_center.y)
            pad = v5.cyl(5.5,-16,-8,foot_center.x,foot_center.y)
            saddle = saddle.fuse(support).fuse(pad)
            hole = v5.cyl(1.65,-18,.2,foot_center.x,foot_center.y)
            saddle = saddle.cut(hole)
            plate = plate.cut(hole)
        saddle = saddle.clean()
        if not all(s.isValid() and len(s.Solids())==1 for s in (motor,reel,shaft,saddle)):
            raise RuntimeError(f"Vertical drive solid invalid at {angle} degrees")
        motors.append(motor); reels.append(reel); shafts.append(shaft); saddles.append(saddle)
    return SimpleNamespace(arm=source_mount.arm, plate=plate.clean(),
                           root_rims=root_rims, saddles=saddles, motors=motors,
                           spools=reels, shafts=shafts, motor_centers=centers,
                           motor_angles=[0,120,240],source_audit=source_mount.source_audit,
                           tendon_hole_centers=source_mount.tendon_hole_centers)


def make_arm_sections(arm: cq.Shape) -> tuple[list[cq.Shape], list[cq.Shape], list[dict]]:
    source = json.loads(JOINT_PATH.read_text(encoding="utf-8"))
    positions = {entry["joint_id"]: entry["interface_position_from_base_m"]*1000
                 for entry in source["joint_stiffness_and_damping"]}
    # A seam belongs to the selected radial unit itself.  The recorded
    # joint position marks its tipward boundary, so use the midpoint between
    # that boundary and the previous one instead of the inter-unit interface.
    seams = []
    unit_spans = []
    for name in CFG["split_joint_ids"]:
        number = int(name.rsplit("_", 1)[1])
        lo = positions[f"joint_{number-1:02d}"]
        hi = positions[name]
        seam = (lo + hi) / 2
        if not lo + 1 < seam < hi - 1:
            raise RuntimeError(f"No internal cut plane within {name}")
        seams.append(seam)
        unit_spans.append((lo, hi))
    length = source["geometry"]["body_length_mm"]
    if abs(arm.BoundingBox().zlen-length) > .03 or seams != sorted(seams):
        raise RuntimeError("B32 arm length or split order differs from the frozen parameter record")
    cuts = [0, *seams, length]
    sections = []
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        part = arm.intersect(v5.box(-100, 100, -100, 100, lo, hi)).clean()
        if not part.isValid() or len(part.Solids()) != 1:
            raise RuntimeError(f"Arm slice {lo:.2f}..{hi:.2f} mm is not one valid solid")
        sections.append(part)
    d = CFG["dovetail"]
    pins, seam_records = [], []
    for index, seam in enumerate(seams):
        lower_hub = v5.cyl(d["hub_radius_mm"], seam-d["rootward_hub_depth_mm"], seam)
        upper_hub = v5.cyl(d["hub_radius_mm"], seam, seam+d["tipward_hub_depth_mm"])
        male = dovetail_prism(d["key_xy_polygon_mm"], seam, d["male_projection_mm"])
        female = dovetail_prism(d["socket_xy_polygon_mm"], seam-.2,
                                d["female_depth_mm"]+.2)
        pin_angle = math.radians(d["cross_pin_axis_deg"])
        pin_axis = cq.Vector(math.cos(pin_angle), math.sin(pin_angle), 0)
        bore_half = d["cross_pin_bore_half_lengths_mm"][index]
        pin_length = d["cross_pin_proxy_lengths_mm"][index]
        pin_hole = cq.Solid.makeCylinder(d["cross_pin_clearance_diameter_mm"]/2,
                    2*bore_half, -pin_axis*bore_half+cq.Vector(0,0,seam+4.5), pin_axis)
        pin_proxy = cq.Solid.makeCylinder(d["cross_pin_proxy_diameter_mm"]/2,
                    pin_length, -pin_axis*(pin_length/2)+cq.Vector(0,0,seam+4.5), pin_axis)
        sections[index] = sections[index].fuse(lower_hub).fuse(male).cut(pin_hole).clean()
        sections[index+1] = sections[index+1].fuse(upper_hub).cut(female).cut(pin_hole).clean()
        pins.append(pin_proxy)
        seam_records.append({"joint_id": CFG["split_joint_ids"][index],
                             "from_root_mm": round(seam, 4),
                             "joint_unit_span_from_root_mm": [round(v, 4) for v in unit_spans[index]],
                             "split_inside_joint_unit": True,
                             "male_projection_mm": d["male_projection_mm"],
                             "nominal_side_clearance_mm": d["side_clearance_mm"],
                             "cross_pin_clearance_diameter_mm": d["cross_pin_clearance_diameter_mm"],
                             "cross_pin_axis_deg": d["cross_pin_axis_deg"]})
    return sections, pins, seam_records


def tendon_channel_intrusion(sections: list[cq.Shape], pins: list[cq.Shape]) -> dict:
    paper_path = (V5_PATH.parent/"../paper_v1/generate_paper_step.py").resolve()
    paper_spec = importlib.util.spec_from_file_location("b32_paper_geometry_reference", paper_path)
    paper = importlib.util.module_from_spec(paper_spec)
    paper_spec.loader.exec_module(paper)
    params = json.loads(paper.PARAMS_PATH.read_text(encoding="utf-8-sig"))
    baseline = json.loads(JOINT_PATH.read_text(encoding="utf-8"))["geometry"]
    cutter = paper.build_three_cable_cutter(
        baseline["body_length_mm"], baseline["tip_diameter_actual_mm"],
        baseline["base_diameter_target_mm"], params)
    cutter = paper.transformed_to_z(cutter, baseline["body_length_mm"])
    section_hits = [round(part.intersect(cutter).Volume(), 5) for part in sections]
    pin_hits = [round(pin.intersect(cutter).Volume(), 5) for pin in pins]
    if max(section_hits+pin_hits) > .01:
        raise RuntimeError(f"Dovetail or lock pin enters original tendon passages: {section_hits}, {pin_hits}")
    return {"arm_section_overlap_mm3": section_hits,
            "installed_pin_overlap_mm3": pin_hits,
            "cutter_source": str(paper_path)}


def export_stl(shape: cq.Shape, path: Path) -> dict:
    cq.exporters.export(shape, str(path), exportType="STL", tolerance=.08, angularTolerance=.12)
    mesh = trimesh.load_mesh(str(path), process=True)
    bbox = mesh.bounds[1]-mesh.bounds[0]
    return {"file": str(path.relative_to(HERE)).replace("\\", "/"),
            "bbox_mm": [round(float(v), 2) for v in bbox],
            "valid_single_solid": shape.isValid() and len(shape.Solids()) == 1,
            "stl_watertight_after_vertex_welding": bool(mesh.is_watertight)}


def flatten_panel(shape: cq.Shape, angle: int, slope: float) -> cq.Shape:
    t = math.radians(angle)
    normal = cq.Vector(math.cos(t), math.sin(t), -slope).normalized()
    bed_normal = cq.Vector(0, 0, -1)
    axis = normal.cross(bed_normal).normalized()
    degrees = math.degrees(math.acos(max(-1, min(1, normal.dot(bed_normal)))))
    flat = shape.rotate((0, 0, 0), (axis.x, axis.y, axis.z), degrees)
    tangent = np.array([-math.sin(t), math.cos(t), 0])
    k = np.array([axis.x, axis.y, axis.z]); a = math.radians(degrees)
    turned = tangent*math.cos(a)+np.cross(k, tangent)*math.sin(a)+k*np.dot(k, tangent)*(1-math.cos(a))
    flat = flat.rotate((0, 0, 0), (0, 0, 1), -math.degrees(math.atan2(turned[1], turned[0])))
    bounds = flat.BoundingBox()
    return flat.translate(cq.Vector(-bounds.xmin, -bounds.ymin, -bounds.zmin))


def export_print_parts(sections: list[cq.Shape], plate: cq.Shape,
                       reels: list[cq.Shape], saddles: list[cq.Shape],
                       root_rims: list[cq.Shape],
                       fairing: dict[str, cq.Shape], guard: dict[str, cq.Shape],
                       splices: dict[str, cq.Shape]) -> dict:
    OUT_PRINT.mkdir(exist_ok=True)
    records = {}
    for i, shape in enumerate(sections, 1):
        records[f"arm_section_{i:02d}"] = export_stl(shape, OUT_PRINT/f"arm_section_{i:02d}.stl")
    records["hex_base_plate"] = export_stl(plate, OUT_PRINT/"hex_base_plate.stl")
    for i, shape in enumerate(reels, 1):
        records[f"cable_reel_{i:02d}"] = export_stl(shape, OUT_PRINT/f"cable_reel_{i:02d}.stl")
    for i, shape in enumerate(saddles, 1):
        records[f"wet_motor_saddle_{i:02d}"] = export_stl(shape, OUT_PRINT/f"wet_motor_saddle_{i:02d}.stl")
    for i, shape in enumerate(root_rims, 1):
        records[f"root_retainer_{i:02d}"] = export_stl(shape, OUT_PRINT/f"root_retainer_{i:02d}.stl")
    for name, shape in {**fairing, **guard}.items():
        angle = int(name.rsplit("_", 1)[1])
        if name.startswith("upper"):
            slope = (141.5-131.5)*math.cos(math.pi/6)/(-80+8)
        elif name.startswith("lower"):
            slope = (98-141.5)*math.cos(math.pi/6)/(-236+80)
        else:
            slope = 0
        records[name] = export_stl(flatten_panel(shape, angle, slope),
                                   OUT_PRINT/f"{name}_flat.stl")
    for name, shape in splices.items():
        records[name] = export_stl(shape, OUT_PRINT/f"{name}.stl")
    return records


def render_preview(sections: list[cq.Shape], pins: list[cq.Shape], plate: cq.Shape,
                   mount: object, shell: cq.Shape, lid: cq.Shape,
                   fairing: dict[str, cq.Shape], guard: dict[str, cq.Shape],
                   splices: dict[str, cq.Shape], seams: list[dict]) -> None:
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    from PIL import Image, ImageDraw, ImageFont
    window = vtk.vtkRenderWindow(); window.SetOffScreenRendering(1); window.SetSize(2000, 1040)
    def actor(shape: cq.Shape, rgb: tuple[float,float,float], opacity: float = 1) -> vtk.vtkActor:
        vertices, faces = shape.tessellate(1.1, .15)
        points = vtk.vtkPoints(); points.SetNumberOfPoints(len(vertices))
        for i, p in enumerate(vertices): points.SetPoint(i, p.x, p.y, p.z)
        polys = vtk.vtkCellArray()
        for face in faces:
            polys.InsertNextCell(3)
            for vertex in face: polys.InsertCellPoint(int(vertex))
        poly = vtk.vtkPolyData(); poly.SetPoints(points); poly.SetPolys(polys)
        mapper = vtk.vtkPolyDataMapper(); mapper.SetInputData(poly)
        item = vtk.vtkActor(); item.SetMapper(mapper)
        item.GetProperty().SetColor(*rgb); item.GetProperty().SetOpacity(opacity)
        return item
    for viewport, exploded in enumerate((False, True)):
        renderer = vtk.vtkRenderer(); renderer.SetViewport(viewport*.5, 0, (viewport+1)*.5, 1)
        renderer.SetBackground(.94, .96, .98); renderer.SetUseDepthPeeling(1)
        window.AddRenderer(renderer)
        for i, part in enumerate(sections):
            shift = cq.Vector(65*i, 0, 15*i) if exploded else cq.Vector(0, 0, 0)
            renderer.AddActor(actor(part.translate(shift), [(0.76,.37,.22),(.88,.50,.23),(.93,.65,.30)][i]))
        if not exploded:
            for pin in pins: renderer.AddActor(actor(pin, (.35,.38,.42)))
        renderer.AddActor(actor(plate, (.24,.38,.48)))
        renderer.AddActor(actor(shell, (.19,.28,.37)))
        renderer.AddActor(actor(lid, (.66,.48,.28)))
        for motor in mount.motors: renderer.AddActor(actor(motor, (.20,.59,.67)))
        for spool in mount.spools: renderer.AddActor(actor(spool, (.82,.62,.17)))
        for panel in fairing.values(): renderer.AddActor(actor(panel, (.73,.80,.84), .32))
        for panel in guard.values(): renderer.AddActor(actor(panel, (.58,.78,.84), .38))
        for bracket in splices.values(): renderer.AddActor(actor(bracket, (.68,.70,.72), .75))
        camera = renderer.GetActiveCamera(); camera.ParallelProjectionOn()
        camera.SetFocalPoint(30 if exploded else 0, 0, 160)
        camera.SetPosition(620, -530, 480); camera.SetViewUp(0, 0, 1)
        camera.SetParallelScale(490); renderer.ResetCameraClippingRange()
    window.SetAlphaBitPlanes(1); window.SetMultiSamples(0); window.Render()
    grab = vtk.vtkWindowToImageFilter(); grab.SetInput(window)
    grab.SetInputBufferTypeToRGB(); grab.Update()
    data = grab.GetOutput(); width, height, _ = data.GetDimensions()
    pixels = vtk_to_numpy(data.GetPointData().GetScalars()).reshape(height, width, 3)[::-1]
    image = Image.fromarray(pixels.copy()); draw = ImageDraw.Draw(image)
    title = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 32)
    note = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
    draw.text((55,25), "B32 竖向电机与线轮｜直线出线总装", font=title, fill=(30,47,61))
    draw.text((1060,25), "三段拆解｜半透明平板包覆", font=title, fill=(30,47,61))
    draw.text((55,972), "线轮出口至顶盘线孔为直线；顶盘 250 mm，关节切面位于第 6、13 单元内部。", font=note, fill=(55,70,80))
    image.save(OUT_PREVIEW)

    # Local views show the actual male and female connectors at each seam.
    detail = vtk.vtkRenderWindow(); detail.SetOffScreenRendering(1); detail.SetSize(2400, 820)
    for viewport in range(3):
        renderer = vtk.vtkRenderer(); renderer.SetViewport(viewport/3, 0, (viewport+1)/3, 1)
        renderer.SetBackground(.94, .96, .98); renderer.SetUseDepthPeeling(1)
        detail.AddRenderer(renderer)
        if viewport < 2:
            i = viewport
            if i == 0:
                renderer.AddActor(actor(sections[i], (.78,.38,.22)))
                renderer.AddActor(actor(sections[i+1].translate(cq.Vector(0,0,16)), (.91,.59,.27)))
            else:
                renderer.AddActor(actor(sections[i+1], (.91,.59,.27)))
            seam_z = seams[i]["from_root_mm"]
            camera = renderer.GetActiveCamera(); camera.ParallelProjectionOn()
            camera.SetFocalPoint(0,0,seam_z+6)
            camera.SetPosition(155,-190,seam_z+(95 if i == 0 else -90))
            camera.SetViewUp(0,0,1)
            camera.SetParallelScale(47 if i == 0 else 35)
        else:
            renderer.AddActor(actor(plate, (.24,.38,.48)))
            for panel in fairing.values():
                if panel.BoundingBox().zmax > -79:
                    renderer.AddActor(actor(panel, (.73,.80,.84), .28))
            for panel in guard.values(): renderer.AddActor(actor(panel, (.58,.78,.84), .43))
            camera = renderer.GetActiveCamera(); camera.ParallelProjectionOn()
            camera.SetFocalPoint(0,0,-5)
            camera.SetPosition(370,-310,230); camera.SetViewUp(0,0,1)
            camera.SetParallelScale(170)
        renderer.ResetCameraClippingRange()
    detail.SetAlphaBitPlanes(1); detail.SetMultiSamples(0); detail.Render()
    grab = vtk.vtkWindowToImageFilter(); grab.SetInput(detail)
    grab.SetInputBufferTypeToRGB(); grab.Update()
    data = grab.GetOutput(); width, height, _ = data.GetDimensions()
    pixels = vtk_to_numpy(data.GetPointData().GetScalars()).reshape(height, width, 3)[::-1]
    image = Image.fromarray(pixels.copy()); draw = ImageDraw.Draw(image)
    draw.rectangle((0,0,2400,72), fill=(239,244,248))
    draw.rectangle((0,742,2400,820), fill=(239,244,248))
    labels = ((35, "第 6 单元内部｜榫头与榫槽"), (835, "第 13 单元内部｜榫槽仰视"),
              (1635, "六边形盘｜根部固定护罩"))
    for x, label in labels: draw.text((x,24), label, font=title, fill=(30,47,61))
    draw.text((35,765), "左：接头向上分离 16 mm；中：从下方检查榫槽。横向锁止孔避开三条腱道。", font=note, fill=(55,70,80))
    image.save(OUT_DETAIL)


def render_drive_layout(mount: object, motor_cfg: dict) -> None:
    """Dimensioned top view using the same centers as the exported STEP."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon
    from matplotlib import font_manager
    font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
    plt.rcParams["font.family"] = font_manager.FontProperties(
        fname="C:/Windows/Fonts/msyh.ttc").get_name()
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(10, 9), dpi=180)
    plate_radius = CFG["hex_plate"]["circumradius_mm"]
    hex_xy = [(plate_radius*math.cos(math.radians(-30+60*i)),
               plate_radius*math.sin(math.radians(-30+60*i))) for i in range(6)]
    ax.add_patch(Polygon(hex_xy, closed=True, facecolor="#dce5ea", edgecolor="#426277",
                         linewidth=2, alpha=.6, label="250 mm 六边形顶盘"))
    ax.add_patch(Circle((0,0), v5.CFG["canister"]["outer_diameter_mm"]/2,
                        facecolor="#6e8290", edgecolor="#33495a", alpha=.28,
                        label="密封电子仓外径 136 mm"))
    motor_radius = motor_cfg["motor_reference"]["outer_diameter_mm"]/2
    for i, angle in enumerate(mount.motor_angles, 1):
        center = cq.Vector(*mount.motor_centers[i-1])
        ax.add_patch(Circle((center.x,center.y),motor_radius,
                            facecolor="#3695a3",edgecolor="#175c68",alpha=.7))
        ax.add_patch(Circle((center.x,center.y),CFG["drive_layout"]["spool_flange_radius_mm"],
                            facecolor="#e9b63c",edgecolor="#76520b",linewidth=1.3))
        p = straight_tendon_points(angle,motor_cfg["plate"]["tendon_hole_radius_mm"])
        ax.plot(p[:,0],p[:,1],color="#bd493f",linewidth=2)
        ax.scatter([p[-1,0]],[p[-1,1]],s=32,color="#a52d26")
        ax.annotate(f"电机/线轮{i}",(center.x,center.y),ha="center",va="center",fontsize=7,color="#fff")
    ax.set(xlim=(-140,140),ylim=(-140,140),xlabel="X / mm",ylabel="Y / mm")
    ax.set_aspect("equal"); ax.grid(alpha=.18); ax.legend(loc="upper left")
    ax.set_title("湿侧竖向电机与同轴线轮｜顶盘 250 mm\n红线：线轮出线槽到顶盘对应线孔的直线段",fontsize=14)
    fig.tight_layout(); fig.savefig(OUT_DRIVE); plt.close(fig)


def render_drive_side_profile(motor_cfg: dict) -> None:
    """Radial projection of one straight exit leg and the canister roof."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib import font_manager
    font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
    plt.rcParams["font.family"] = font_manager.FontProperties(
        fname="C:/Windows/Fonts/msyh.ttc").get_name()
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(10,6),dpi=180)
    d = CFG["drive_layout"]
    hole = motor_cfg["plate"]["tendon_hole_radius_mm"]
    face = CFG["hex_plate"]["circumradius_mm"]*math.cos(math.pi/6)
    ax.add_patch(Rectangle((0,-145),68,125,facecolor="#748895",alpha=.28,
                           edgecolor="#3e5664",label="密封电子仓投影"))
    ax.add_patch(Rectangle((0,-8),hole-2.1,8,facecolor="#294357",alpha=.75))
    ax.add_patch(Rectangle((hole+2.1,-8),face-hole-2.1,8,
                           facecolor="#294357",alpha=.75,label="六边形顶盘径向剖面"))
    ax.add_patch(Rectangle((d["motor_center_radius_mm"]-21,d["motor_center_z_mm"]-46),
                           42,92,facecolor="#3695a3",alpha=.65,edgecolor="#175c68",
                           label="竖向湿侧电机"))
    ax.add_patch(Rectangle((d["motor_center_radius_mm"]-10,
                            d["spool_center_z_mm"]-d["spool_width_mm"]/2),
                           20,d["spool_width_mm"],facecolor="#e9b63c",
                           edgecolor="#76520b",label="同轴线轮"))
    p = straight_tendon_points(0,hole)
    ax.plot(p[:,0],p[:,2],color="#bd493f",linewidth=3,label="线轮出口至线孔直线段")
    ax.scatter([p[0,0],p[-1,0]],[p[0,2],p[-1,2]],color="#a02d26",s=35,zorder=5)
    ax.annotate("出线槽",(p[0,0],p[0,2]),xytext=(109,-23),
                arrowprops={"arrowstyle":"->"},fontsize=10)
    ax.annotate("线孔下口",(p[-1,0],p[-1,2]),xytext=(11,10),
                arrowprops={"arrowstyle":"->"},fontsize=10)
    ax.axhline(-20,color="#465d6a",linestyle="--",linewidth=1)
    ax.set(xlim=(0,140),ylim=(-145,22),xlabel="沿第 1 条拉索的径向位置 / mm",
           ylabel="Z / mm")
    ax.grid(alpha=.15);ax.legend(loc="lower left",fontsize=9)
    ax.set_title("线轮出口 → 顶盘线孔：直线越过密封电子仓顶部\n线孔内部转向和卷绕到出线槽的细节仍待实物验证",fontsize=13)
    fig.tight_layout();fig.savefig(OUT_SIDE);plt.close(fig)


def write_manifest() -> None:
    paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p.name != "SHA256SUMS.csv")
    with (HERE/"SHA256SUMS.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["relative_path", "sha256"])
        for path in paths:
            writer.writerow([str(path.relative_to(HERE)).replace("\\", "/"),
                             hashlib.sha256(path.read_bytes()).hexdigest()])


def main() -> None:
    motor_config = v5.motor_module.load_config()
    drive = CFG["drive_layout"]
    # Build the frozen arm and root retainer through the reference builder;
    # replace only its wet motor group and plate with the vertical candidate.
    motor_config["layout"]["motor_center_radius_mm"] = 98.5
    motor_config["layout"]["spool_center_offset_from_motor_center_mm"] = 52.0
    motor_config["motor_saddles"]["foot_radial_offset_mm"] = 25.1
    motor_config["plate"]["diameter_mm"] = 2*CFG["hex_plate"]["circumradius_mm"]
    motor_config["plate"]["fixture_hole_radius_mm"] = v5.CFG["base_plate_fixture_radius_mm"]
    v5.CFG = {**v5.CFG, "motor_center_radius_mm": drive["motor_center_radius_mm"],
              "base_plate_diameter_mm": motor_config["plate"]["diameter_mm"]}
    v5.tendon_points = straight_tendon_points
    v5.minimum_bend_radius = lambda _points: 1e9  # A straight leg has no finite bend radius.
    source_mount = v5.motor_module.build_motor_mount(motor_config)
    mount = make_vertical_mount(motor_config, source_mount)
    sections, pins, seams = make_arm_sections(mount.arm)
    channel_audit = tendon_channel_intrusion(sections, pins)
    plate, top_tabs = make_plate(mount)
    plate, guard = make_root_guard(plate)
    if max(plate.BoundingBox().xlen, plate.BoundingBox().ylen) > 250.01:
        raise RuntimeError("The complete printable hex plate exceeds 250 mm in XY")
    mount.plate = plate
    shell, lid, gland = v5.make_shell()
    parts = {**v5.make_battery(), **v5.make_electronics()}
    wiring = v5.make_wire_proxies()
    for i, angle in enumerate(mount.motor_angles, 1):
        t = math.radians(angle)
        p = lambda r,z:(r*math.cos(t),r*math.sin(t),z)
        center = mount.motor_centers[i-1]
        wiring[f"motor_{i}_external_harness"] = v5.wire(
            [p(69,-76),p(79,-76),(center[0],center[1],-76)],1.5)
    tendons = {}
    for i, angle in enumerate(mount.motor_angles, 1):
        line = straight_tendon_points(angle,motor_config["plate"]["tendon_hole_radius_mm"])
        start, end = cq.Vector(*line[0]), cq.Vector(*line[-1])
        delta = end-start
        tendons[f"tendon_{i}_route_proxy"] = cq.Solid.makeCylinder(.65,delta.Length,start,delta.normalized())
    straightness = {}
    for angle in mount.motor_angles:
        points = straight_tendon_points(angle,motor_config["plate"]["tendon_hole_radius_mm"])
        direction = points[-1]-points[0]
        straightness[f"channel_{int(angle):03d}"] = round(float(max(
            np.linalg.norm(np.cross(point-points[0],direction))/np.linalg.norm(direction)
            for point in points)),7)
    if max(straightness.values()) > 1e-6:
        raise RuntimeError("A reel-to-hole cable leg is not straight")
    first_line = straight_tendon_points(0,motor_config["plate"]["tendon_hole_radius_mm"])
    r0, z0 = first_line[0,0], first_line[0,2]
    r1, z1 = first_line[-1,0], first_line[-1,2]
    roof_crossing_z = z0 + (68-r0)*(z1-z0)/(r1-r0)
    roof_clearance = roof_crossing_z-v5.CFG["canister"]["top_z_mm"]-.65
    if roof_clearance <= 0:
        raise RuntimeError("The straight cable does not clear the sealed canister roof")
    fairing = make_fairing()
    splices = make_panel_splices()
    existing_fit = v5.audit(mount, shell, lid, parts, wiring, tendons, motor_config, fairing)
    existing_fit["spool_positions"]["placement"] = "vertical coaxial reel above each wet motor"
    existing_fit["tendon_disk_holes"]["status"] = "straight cable proxy ends 0.8 mm below the underside opening; rounded entry and through-hole bend pending"
    existing_fit["tendon_route"] = "three straight segments from reel top-flange exit slots to matching disk hole undersides; hole transition not modeled"
    existing_fit["tendon_min_discrete_curvature_radius_mm"] = None
    if any(not (part.isValid() and len(part.Solids()) == 1) for part in sections):
        raise RuntimeError("One of the three dovetailed arm sections is invalid")
    if any(part.BoundingBox().zlen >= CFG["printer_effective_height_mm"] for part in sections):
        raise RuntimeError("A printed arm section exceeds the available build height")
    if any(sections[i].intersect(sections[i+1]).Volume() > .01 for i in range(2)):
        raise RuntimeError("Mated arm sections overlap in solid volume")
    if any(sum(panel.intersect(part).Volume() for panel in guard.values()) > .01
           for part in sections):
        raise RuntimeError("The fixed root guard intersects an arm section at rest")
    if any(sum(panel.intersect(motor).Volume() for panel in fairing.values()) > .01
           for motor in mount.motors):
        raise RuntimeError("The wet motor windows are obstructed")
    if any(sum(panel.intersect(saddle).Volume() for panel in fairing.values()) > .01
           for saddle in mount.saddles):
        raise RuntimeError("A vertical motor support intersects a fairing panel")
    if any(saddle.intersect(motor).Volume() > .01
           for saddle,motor in zip(mount.saddles,mount.motors)):
        raise RuntimeError("A vertical motor support intersects its motor envelope")
    if any(reel.intersect(motor).Volume() > .01 for reel in mount.spools for motor in mount.motors):
        raise RuntimeError("A cable reel overlaps a motor envelope")
    if any(reel.intersect(shell).Volume() > .01 or reel.intersect(plate).Volume() > .01
           for reel in mount.spools):
        raise RuntimeError("A cable reel overlaps the canister or plate")
    if any(route.intersect(reel).Volume() > .01
           for route,reel in zip(tendons.values(),mount.spools)):
        raise RuntimeError("A straight outgoing cable intersects its reel outside the exit slot")
    if any(plate.intersect(motor).Volume() > .01 for motor in mount.motors):
        raise RuntimeError("A new hex-plate attachment boss collides with a wet motor")
    if any(plate.intersect(rim).Volume() > .01 for rim in mount.root_rims):
        raise RuntimeError("A new hex-plate attachment boss collides with a root retainer")
    if any(sum(bracket.intersect(panel).Volume() for panel in fairing.values()) > .01
           or bracket.intersect(shell).Volume() > .01 for bracket in splices.values()):
        raise RuntimeError("A face splice clashes with its fairing panel or the dry canister")
    print_records = export_print_parts(sections, plate, mount.spools, mount.saddles,
                                       mount.root_rims, fairing, guard, splices)
    if not all(item["valid_single_solid"] and item["stl_watertight_after_vertex_welding"]
               for item in print_records.values()):
        raise RuntimeError("A print candidate failed CAD or STL topology inspection")
    arm_assembly = cq.Assembly(name="B32_three_sections_two_dovetails")
    for i, part in enumerate(sections, 1):
        arm_assembly.add(part, name=f"arm_section_{i:02d}", color=cq.Color(.77,.39,.22))
    for i, pin in enumerate(pins, 1):
        arm_assembly.add(pin, name=f"cross_pin_{i:02d}_proxy", color=cq.Color(.4,.42,.44))
    arm_assembly.export(str(OUT_ARM), exportType="STEP", unit="MM")
    assembly = cq.Assembly(name="B32_modular_arm_hex_plate_faceted_shrouds")
    for i, part in enumerate(sections, 1):
        assembly.add(part, name=f"arm_section_{i:02d}", color=cq.Color(.77,.39,.22))
    for i, pin in enumerate(pins, 1):
        assembly.add(pin, name=f"cross_pin_{i:02d}_proxy", color=cq.Color(.4,.42,.44))
    assembly.add(plate, name="hexagonal_base_plate_with_panel_tabs", color=cq.Color(.24,.38,.48))
    for i, shape in enumerate(mount.root_rims, 1): assembly.add(shape, name=f"root_retainer_{i}")
    for i, shape in enumerate(mount.saddles, 1): assembly.add(shape, name=f"wet_motor_saddle_{i}")
    for i, (motor, spool, shaft) in enumerate(zip(mount.motors, mount.spools, mount.shafts), 1):
        assembly.add(motor, name=f"wet_motor_{i}_envelope")
        assembly.add(spool, name=f"spool_{i}_proxy")
        assembly.add(shaft, name=f"shaft_{i}_proxy")
    assembly.add(shell, name="centerline_dry_canister")
    assembly.add(lid, name="removable_bottom_lid")
    assembly.add(gland, name="shore_tether_gland_proxy")
    for name, shape in {**fairing, **guard, **splices}.items(): assembly.add(shape, name=name)
    v5.add_parts(assembly, parts); v5.add_parts(assembly, wiring); v5.add_parts(assembly, tendons)
    assembly.export(str(OUT_ASSEMBLY), exportType="STEP", unit="MM")
    render_preview(sections, pins, plate, mount, shell, lid, fairing, guard, splices, seams)
    render_drive_layout(mount, motor_config)
    render_drive_side_profile(motor_config)
    report = {"candidate": CFG["model"], "release_status": CFG["status"],
              "source_arm_step_sha256": mount.source_audit["arm_step_sha256"],
              "joint_source": str(JOINT_PATH), "seams": seams,
              "arm_section_print_mesh_z_lengths_mm": [print_records[f"arm_section_{i:02d}"]["bbox_mm"][2] for i in range(1,4)],
              "arm_section_brep_conservative_z_lengths_mm": [round(part.BoundingBox().zlen, 3) for part in sections],
              "arm_section_max_below_build_height": True,
              "adjacent_section_solid_overlap_mm3": [round(sections[i].intersect(sections[i+1]).Volume(), 4) for i in range(2)],
              "tendon_channel_intrusion": channel_audit,
              "plate": {"shape": "six_sided", "vertex_radius_mm": CFG["hex_plate"]["circumradius_mm"],
                        "maximum_corner_to_corner_mm": 2*CFG["hex_plate"]["circumradius_mm"],
                        "upper_panel_boss_count": len(top_tabs), "root_guard_boss_count": 12,
                        "plate_bbox_mm": [round(v,2) for v in (plate.BoundingBox().xlen, plate.BoundingBox().ylen, plate.BoundingBox().zlen)]},
              "root_guard": {"panel_count": len(guard), "top_open": True,
                             "cover_height_mm": CFG["root_guard"]["top_z_mm"],
                             "arm_at_rest_overlap_mm3": 0},
              "wet_side_fairing": {"panel_count": len(fairing), "top_attachment_holes_per_panel": 2,
                                       "upper_lower_splice_brackets": len(splices),
                                       "observation_openings": 3, "motor_windows": 3, "pressure_boundary": False},
              "drive_layout": {"motor_axis": "vertical_Z",
                               "motor_centers_mm": mount.motor_centers,
                               "reel_centers_mm": [(x,y,drive["spool_center_z_mm"])
                                                    for x,y,_z in mount.motor_centers],
                               "straight_reel_exit_to_hole_deviation_mm": straightness,
                               "straight_segment_length_mm": round(float(np.linalg.norm(first_line[-1]-first_line[0])),3),
                               "canister_roof_clearance_along_first_cable_mm": round(roof_clearance,3),
                               "reel_exit_to_hole_route": "direct straight leg to underside of each plate hole; winding-to-exit-slot detail remains proxy",
                               "motor_to_canister_clearance_mm": round(min(shell.distance(m) for m in mount.motors),3),
                               "reel_to_motor_clearance_mm": round(min(r.distance(m) for r in mount.spools for m in mount.motors),3),
                               "reel_geometry_status": drive["geometry_status"]},
              "existing_enclosure_fit": existing_fit, "print_part_records": print_records,
              "step_readback": {"arm_valid": cq.importers.importStep(str(OUT_ARM)).val().isValid(),
                                "assembly_valid": cq.importers.importStep(str(OUT_ASSEMBLY)).val().isValid()},
              "unverified": ["dovetail fatigue, TPU creep and transverse pin retention",
                             "dynamic clearance and stiffness change at both arm seams",
                             "supplier motor output shaft interface and reel winding capacity",
                             "root guard clearance through the full tendon-driven motion",
                             "actual printer XY footprint, slicer paths, fastener seats and physical assembly",
                             "pressure/leak and freshwater/seawater runtime testing"]}
    with OUT_AUDIT.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2))
    write_manifest()
    print(json.dumps({"arm_sections_mm": report["arm_section_print_mesh_z_lengths_mm"],
                      "panel_count": len(fairing)+len(guard), "splice_bracket_count": len(splices),
                      "step_readback": report["step_readback"]}, ensure_ascii=False))


if __name__ == "__main__": main()
