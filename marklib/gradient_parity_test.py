"""SVG vs raster gradient parity — the one place a silent divergence can hide.

marklib 0.1.0 added N-stop, any-angle `linear_gradient` and shipped it TWICE: once
for SVG (`marklib.linear_gradient`, an `objectBoundingBox` vector on an svgwrite
gradient) and once for raster (`marklib.raster.lgrad`, a numpy projection in pixel
space). Two implementations of one visual result, and nothing compared them.

That is the worst shape a bug can take here. A divergence does not crash, does not
fail a build, and does not show up in a diff — the SVG hero and the PNG favicon
simply run their gradient different ways, and someone notices months later that
the app icon looks wrong next to the website. The gradient is also the single most
brand-defining thing marklib draws: aion's whole identity is the aeon spectrum
sweeping violet to cyan across the glyph.

So this pins the shared contract both implementations must honour: the vector runs
from (0.5 - dx/2, 0.5 - dy/2) to (0.5 + dx/2, 0.5 + dy/2) of the geometry's
bounding box, with dx = cos(angle), dy = sin(angle) and y increasing DOWNWARD in
both. Angle 0 is left-to-right; 90 is top-to-bottom.
"""

import math
import unittest

import svgwrite
from PIL import Image
from shapely.geometry import box

from marklib import linear_gradient
from marklib.fit import fit
from marklib.raster import lgrad

RED, BLUE = "#FF0000", "#0000FF"
GREEN = "#00FF00"


def _svg_vector(angle_deg):
    """The start/end the SVG implementation writes, read back off the element."""
    d = svgwrite.Drawing("x.svg", size=(10, 10))
    linear_gradient(d, "g", [RED, BLUE], angle_deg)
    grad = d.defs.elements[-1]
    return (
        (float(grad["x1"]), float(grad["y1"])),
        (float(grad["x2"]), float(grad["y2"])),
    )


def _raster_px(angle_deg, stops=(RED, BLUE), size=64):
    """The raster implementation's image over a full-canvas unit square."""
    tf = fit(size, half_extent=1.0, flip_y=False)
    geom = box(-1.0, -1.0, 1.0, 1.0)
    return lgrad(size, tf, geom, list(stops), angle_deg).convert("RGB").load()


class SharedVectorContract(unittest.TestCase):
    def test_svg_vector_matches_the_documented_construction(self):
        for angle in (0.0, 45.0, 90.0, 135.0):
            with self.subTest(angle=angle):
                a = math.radians(angle)
                dx, dy = math.cos(a), math.sin(a)
                start, end = _svg_vector(angle)
                self.assertAlmostEqual(0.5 - dx / 2, start[0], places=5)
                self.assertAlmostEqual(0.5 - dy / 2, start[1], places=5)
                self.assertAlmostEqual(0.5 + dx / 2, end[0], places=5)
                self.assertAlmostEqual(0.5 + dy / 2, end[1], places=5)


class RasterAgreesWithTheVector(unittest.TestCase):
    """Sample the raster where the SVG vector says each stop must land."""

    def _assert_endpoints(self, angle, size=64, tol=6):
        start, end = _svg_vector(angle)
        px = _raster_px(angle, size=size)
        # objectBoundingBox coords -> pixel coords on a full-canvas geometry.
        def at(uv):
            x = min(size - 1, max(0, round(uv[0] * (size - 1))))
            y = min(size - 1, max(0, round(uv[1] * (size - 1))))
            return px[x, y]

        r0, g0, b0 = at(start)
        r1, g1, b1 = at(end)
        self.assertGreater(r0, 255 - tol, f"angle {angle}: start should be red")
        self.assertLess(b0, tol, f"angle {angle}: start should be red")
        self.assertLess(r1, tol, f"angle {angle}: end should be blue")
        self.assertGreater(b1, 255 - tol, f"angle {angle}: end should be blue")

    def test_horizontal(self):
        self._assert_endpoints(0.0)

    def test_vertical_runs_top_to_bottom(self):
        """Both implementations take y as increasing DOWNWARD. If one flipped,
        every vertical gradient would be inverted between SVG and PNG."""
        self._assert_endpoints(90.0)

    def test_diagonals(self):
        self._assert_endpoints(45.0)
        self._assert_endpoints(135.0)

    def test_midpoint_of_a_three_stop_gradient_is_the_middle_stop(self):
        """N-stop, not just two — the aeon spectrum is three."""
        px = _raster_px(0.0, stops=(RED, GREEN, BLUE), size=64)
        r, g, b = px[32, 32]
        self.assertGreater(g, 200)
        self.assertLess(r, 60)
        self.assertLess(b, 60)

    def test_reversing_the_angle_reverses_the_sweep(self):
        fwd = _raster_px(0.0)
        rev = _raster_px(180.0)
        self.assertGreater(fwd[2, 32][0], 200)   # red at the left
        self.assertGreater(rev[2, 32][2], 200)   # blue at the left


if __name__ == "__main__":
    unittest.main()
