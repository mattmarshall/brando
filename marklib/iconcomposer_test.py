"""Regression gate on the Icon Composer writer.

`brand_iconcomposer` has no caller anywhere in the fleet, and that is exactly why
`emit_icon_bundle` shipped a crash for two releases: marklib 0.1.0 introduced the
dict gradient form and this writer still indexed it as a tuple, so
`layer.gradient[0]` raised `KeyError: 0`. An unexercised rule is an untested rule.

So the first case here is that crash, and the rest pin the manifest shape a brand
would otherwise have to discover by opening Icon Composer.
"""

import json
import os
import tempfile
import unittest

from shapely.geometry import Point

from marklib import Canvas, iconcomposer
from marklib.fit import fit


def _canvas():
    c = Canvas(size=64, tf=fit(64, half_extent=1.0))
    c.add_background("#0B1020")
    return c


def _manifest(canvas):
    with tempfile.TemporaryDirectory() as out:
        iconcomposer.emit_icon_bundle(out, "t", canvas)
        with open(os.path.join(out, "t.icon", "icon.json"), encoding="utf-8") as fh:
            return json.load(fh)


class DictGradient(unittest.TestCase):
    def test_dict_gradient_does_not_raise(self):
        """The KeyError: 0 regression — a 0.1.0-style N-stop layer."""
        c = _canvas()
        c.add_layer(
            "glyph",
            Point(0, 0).buffer(1.0),
            "#3B6FF0",
            gradient={"stops": ["#7C3AED", "#3B6FF0", "#22D3EE"], "angle": 55.0},
        )
        entry = _manifest(c)["groups"][0]["layers"][0]
        self.assertEqual(3, len(entry["fill"]["linear-gradient"]))

    def test_angle_is_honoured_not_dropped(self):
        """An .icon whose gradient runs a different way than the SVG is a silent bug."""
        c = _canvas()
        c.add_layer("glyph", Point(0, 0).buffer(1.0), "#fff",
                    gradient={"stops": ["#000000", "#ffffff"], "angle": 0.0})
        axis = _manifest(c)["groups"][0]["layers"][0]["fill"]["orientation"]
        # angle 0 => horizontal: x sweeps 0->1, y stays centred.
        self.assertAlmostEqual(0.0, axis["start"]["x"])
        self.assertAlmostEqual(1.0, axis["stop"]["x"])
        self.assertAlmostEqual(0.5, axis["start"]["y"])

    def test_dict_without_angle_keeps_the_default_axis(self):
        c = _canvas()
        c.add_layer("glyph", Point(0, 0).buffer(1.0), "#fff",
                    gradient={"stops": ["#000000", "#ffffff"]})
        axis = _manifest(c)["groups"][0]["layers"][0]["fill"]["orientation"]
        self.assertEqual(iconcomposer.GRAD_AXIS, axis)

    def test_tuple_gradient_still_works(self):
        """The original 2-tuple form must keep working — brands still use it."""
        c = _canvas()
        c.add_layer("glyph", Point(0, 0).buffer(1.0), "#fff", gradient=("#000000", "#ffffff"))
        entry = _manifest(c)["groups"][0]["layers"][0]
        self.assertEqual(2, len(entry["fill"]["linear-gradient"]))
        self.assertEqual(iconcomposer.GRAD_AXIS, entry["fill"]["orientation"])

    def test_a_one_stop_gradient_fails_loudly(self):
        c = _canvas()
        c.add_layer("glyph", Point(0, 0).buffer(1.0), "#fff", gradient={"stops": ["#000000"]})
        with self.assertRaises(ValueError):
            _manifest(c)


class ManifestShape(unittest.TestCase):
    def test_layers_are_front_first(self):
        """Canvas holds back-to-front; Icon Composer lists front first."""
        c = _canvas()
        c.add_layer("back", Point(0, 0).buffer(1.0), "#111111")
        c.add_layer("front", Point(0, 0).buffer(0.5), "#222222")
        names = [l["name"] for l in _manifest(c)["groups"][0]["layers"]]
        self.assertEqual(["front", "back"], names)

    def test_composite_only_layers_are_excluded(self):
        """emit_file=False layers exist for the composite, not as assets."""
        c = _canvas()
        c.add_layer("real", Point(0, 0).buffer(1.0), "#111111")
        c.add_layer("halo", Point(0, 0).buffer(1.2), "#222222", emit_file=False)
        names = [l["name"] for l in _manifest(c)["groups"][0]["layers"]]
        self.assertEqual(["real"], names)


if __name__ == "__main__":
    unittest.main()
