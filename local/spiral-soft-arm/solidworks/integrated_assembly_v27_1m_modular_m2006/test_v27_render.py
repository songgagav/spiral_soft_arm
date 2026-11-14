from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

import render_v27


class V27CoverComparisonRenderTests(unittest.TestCase):
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
                pixels = image.convert("RGB").crop((220, 180, 1040, 820)).getdata()
                outline_pixels = sum(1 for pixel in pixels if max(pixel) < 170)
                self.assertGreater(
                    outline_pixels,
                    20,
                    "opaque cover preview needs dark component outlines for edge contrast",
                )


if __name__ == "__main__":
    unittest.main()
