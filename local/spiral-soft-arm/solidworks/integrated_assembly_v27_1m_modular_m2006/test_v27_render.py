from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from PIL import Image

import render_v27


class V27CoverComparisonRenderTests(unittest.TestCase):
    def test_top_plate_cover_joint_review_renders_three_serviceable_connections(self) -> None:
        self.assertTrue(
            hasattr(render_v27, "_top_plate_cover_joint_review"),
            "render_v27 must provide a magnified fixed-ear connection review",
        )
        cq = render_v27.cq
        plate = cq.Solid.makeBox(250.0, 250.0, 8.0, cq.Vector(-125.0, -125.0, -8.0))
        components = {"fixed_top_plate": plate}
        for normal_deg in (30.0, 150.0, 270.0):
            angle = math.radians(normal_deg)
            x_mm, y_mm = 100.0 * math.cos(angle), 100.0 * math.sin(angle)
            components[f"fixed_cover_upper_panel_{(int(normal_deg - 30) // 60) + 1:02d}"] = (
                cq.Solid.makeBox(30.0, 24.0, 8.0, cq.Vector(x_mm - 15.0, y_mm - 12.0, 0.0))
            )
        result = SimpleNamespace(
            components=components,
            contract=SimpleNamespace(
                integration={
                    "root_cover": {
                        "top_plate_attachment_normals_deg": [30.0, 150.0, 270.0],
                        "top_plate_attachment_hole_radius_mm": 100.0,
                        "top_plate_attachment_z_bounds_mm": [0.0, 8.0],
                    }
                }
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "cover-ear-joints.png"
            render_v27._top_plate_cover_joint_review(result, output_path)
            self.assertTrue(output_path.is_file())
            with Image.open(output_path) as image:
                self.assertGreaterEqual(image.width, 1200)
                self.assertGreaterEqual(image.height, 800)
                pixels = image.convert("RGB").get_flattened_data()
                gold_axis_pixels = sum(
                    1
                    for red, green, blue in pixels
                    if red > 160 and 100 < green < 195 and blue < 140 and red > green * 1.12
                )
                self.assertGreater(
                    gold_axis_pixels,
                    20,
                    "the M3 nominal fastener axis must be visibly highlighted in the connection detail",
                )

    def test_cover_comparison_preserves_equal_scale_before_and_after_views(self) -> None:
        self.assertTrue(
            hasattr(render_v27, "_cover_comparison"),
            "render_v27 must provide a before/after cover comparison renderer",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            before_path = directory / "before.png"
            after_path = directory / "after.png"
            output_path = directory / "comparison.png"
            Image.new("RGB", (64, 48), "#87a9bb").save(before_path)
            Image.new("RGB", (64, 48), "#d2b16d").save(after_path)

            render_v27._cover_comparison(before_path, after_path, output_path)

            self.assertTrue(output_path.is_file())
            with Image.open(output_path) as image:
                self.assertGreaterEqual(image.width, 128)
                self.assertGreaterEqual(image.height, 48)

    def test_opaque_cover_view_renders_a_printable_cover_component(self) -> None:
        self.assertTrue(
            hasattr(render_v27, "_cover_opaque_view"),
            "render_v27 must provide an opaque cover inspection view",
        )
        shape = render_v27.cq.Solid.makeBox(12.0, 12.0, 8.0)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "opaque-cover.png"
            render_v27._cover_opaque_view(
                [("fixed_cover_lower_panel_01", shape)], output_path
            )
            self.assertTrue(output_path.is_file())
            with Image.open(output_path) as image:
                self.assertGreaterEqual(image.width, 1200)
                self.assertGreaterEqual(image.height, 800)
                pixels = image.convert("RGB").crop((220, 180, 1040, 820)).get_flattened_data()
                outline_pixels = sum(1 for pixel in pixels if max(pixel) < 170)
                self.assertGreater(
                    outline_pixels,
                    20,
                    "opaque cover preview needs dark component outlines for edge contrast",
                )


if __name__ == "__main__":
    unittest.main()
