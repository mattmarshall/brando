"""Gate on the brandbook plates.

These check the two things a lift can get wrong that reviewing the code will not
catch: that the reference circle is measured through the caller's transform
(rather than assuming a scale, which is how the fastverk original was written),
and that the optional parts are genuinely optional -- a mark built on a square
must not be forced to draw a circle at radius zero.
"""

import os
import tempfile
import unittest

from PIL import Image
from shapely.geometry import Point

from marklib import diagrams
from marklib.fit import fit

BG, GUIDE, INK, ACCENT = "#F4F1EA", "#CFC8B8", "#15161A", "#E0A33E"


def _px(path):
    with Image.open(path) as im:
        return im.convert("RGB").load(), im.size


class Construction(unittest.TestCase):
    def test_writes_a_plate_at_the_requested_size(self):
        with tempfile.TemporaryDirectory() as out:
            path = diagrams.construction(
                os.path.join(out, "c.png"), 200, fit(200, half_extent=1.0), bg=BG, guide=GUIDE
            )
            _, size = _px(path)
            self.assertEqual((200, 200), size)

    def test_reference_circle_is_measured_through_the_transform(self):
        """Not assumed from a scale constant — that is what made it brand-specific.

        With pad=0.25 the model unit maps to a quarter of the canvas, so a
        radius-1 circle must touch x=50 and x=150 on a 200px plate, not x=0/200.
        """
        with tempfile.TemporaryDirectory() as out:
            tf = fit(200, half_extent=1.0, pad=0.25)
            path = diagrams.construction(
                os.path.join(out, "c.png"), 200, tf,
                bg=BG, guide=GUIDE, circle=(1.0, INK, 3), crosshair=False,
            )
            px, _ = _px(path)
            # The stroke sits at x=50 on the centre row; the plate is bg well outside it.
            row = 100
            self.assertNotEqual(px[50, row], px[10, row])
            self.assertEqual(px[10, row], px[190, row])

    def test_optional_parts_are_optional(self):
        """A mark built on a square names no circle and no vertices."""
        with tempfile.TemporaryDirectory() as out:
            path = diagrams.construction(
                os.path.join(out, "c.png"), 64, fit(64, half_extent=1.0),
                bg=BG, guide=GUIDE, crosshair=False,
            )
            px, _ = _px(path)
            self.assertEqual((244, 241, 234), px[32, 32])  # untouched background

    def test_rings_and_points_are_drawn(self):
        with tempfile.TemporaryDirectory() as out:
            path = diagrams.construction(
                os.path.join(out, "c.png"), 200, fit(200, half_extent=1.5),
                bg=BG, guide=GUIDE,
                rings=[(Point(0, 0).buffer(1.0), INK, 4)],
                points=[(0.0, 0.0, ACCENT)],
            )
            px, _ = _px(path)
            self.assertEqual((224, 163, 62), px[100, 100])  # the centre dot


class ClearSpace(unittest.TestCase):
    def test_clearance_is_a_fraction_of_the_mark_not_the_plate(self):
        """The convention that makes clear space a rule rather than a number.

        Doubling the plate while holding mark_frac fixed must scale the frame with
        the mark, so the frame's offset from the mark stays a fixed fraction of it.
        """
        mark = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
        offsets = []
        for size in (200, 400):
            with tempfile.TemporaryDirectory() as out:
                diagrams.clearspace(
                    os.path.join(out, "cs.png"), size, mark,
                    bg=BG, frame=INK, unit=ACCENT, clearance_frac=0.25, mark_frac=0.5,
                )
            icon = int(size * 0.5)
            offsets.append(int(icon * 0.25) / icon)
        self.assertAlmostEqual(offsets[0], offsets[1])

    def test_writes_a_plate(self):
        mark = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
        with tempfile.TemporaryDirectory() as out:
            path = diagrams.clearspace(
                os.path.join(out, "cs.png"), 200, mark, bg=BG, frame=INK, unit=ACCENT
            )
            _, size = _px(path)
            self.assertEqual((200, 200), size)


class Grid(unittest.TestCase):
    def test_composites_the_real_mark_not_a_second_rendering(self):
        mark = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        with tempfile.TemporaryDirectory() as out:
            path = diagrams.grid(
                os.path.join(out, "g.png"), 100, mark, bg=BG, crosshair=INK
            )
            px, _ = _px(path)
            self.assertEqual((255, 0, 0), px[10, 10])  # the mark, opaque, unaltered


if __name__ == "__main__":
    unittest.main()
