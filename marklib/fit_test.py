"""Gate on marklib.fit — the transform four brands each re-derived.

The value of this test is not that the arithmetic is hard; it is that the four
hand-written versions disagreed about things nobody had written down. So these
cases pin the CONTRACT: where the origin lands, which way y runs, and what `pad`
means. If someone later "simplifies" pad from a fraction of the half-canvas into a
fraction of the canvas, every mark in the fleet silently changes size, and only a
test that states the convention catches it.
"""

import unittest

from marklib.fit import fit, spec_at


class Fit(unittest.TestCase):
    def test_origin_lands_at_the_canvas_centre(self):
        tf = fit(100, half_extent=1.0)
        self.assertEqual((50.0, 50.0), tf(0.0, 0.0))

    def test_y_runs_downward_in_pixel_space(self):
        """Model space is y-up, pixels are y-down. Getting this wrong flips marks."""
        tf = fit(100, half_extent=1.0)
        self.assertLess(tf(0.0, 1.0)[1], tf(0.0, -1.0)[1])

    def test_flip_y_false_for_y_down_model_spaces(self):
        tf = fit(100, half_extent=1.0, flip_y=False)
        self.assertGreater(tf(0.0, 1.0)[1], tf(0.0, -1.0)[1])

    def test_half_extent_fills_the_canvas_without_padding(self):
        tf = fit(100, half_extent=2.0)
        self.assertAlmostEqual(100.0, tf(2.0, 0.0)[0])
        self.assertAlmostEqual(0.0, tf(-2.0, 0.0)[0])

    def test_pad_is_a_fraction_of_the_full_canvas_per_side(self):
        """pad=0.10 on a 100px canvas leaves 10px of air on EACH side.

        This convention is worth pinning precisely because it is the one the four
        hand-written transforms disagreed about. `pad` is not half-canvas-relative
        and it is not a total: it is per-side, against the full canvas.
        """
        tf = fit(100, half_extent=1.0, pad=0.10)
        self.assertAlmostEqual(90.0, tf(1.0, 0.0)[0])
        self.assertAlmostEqual(10.0, tf(-1.0, 0.0)[0])

    def test_pad_matches_aions_existing_formula_exactly(self):
        """Adoption must not move an existing mark by a pixel.

        aion's _tf() is (S/2) * (1 - 2*0.06) / half_extent. If `fit` ever drifts
        from that, aion's mark silently resizes on the next build.
        """
        S, half_extent, aion_pad = 512.0, 1.37, 0.06
        expected_scale = (S / 2) * (1 - 2 * aion_pad) / half_extent
        tf = fit(S, half_extent=half_extent, pad=aion_pad)
        got_scale = tf(1.0, 0.0)[0] - tf(0.0, 0.0)[0]
        self.assertAlmostEqual(expected_scale, got_scale)

    def test_center_moves_the_optical_origin(self):
        """The centring knob: a mark whose visual centre is not its origin."""
        tf = fit(100, half_extent=1.0, center=(0.0, 0.5))
        self.assertEqual((50.0, 50.0), tf(0.0, 0.5))

    def test_bounds_fits_the_longer_axis_and_centres_the_bbox(self):
        # A wide, off-origin box: 4 across, 2 tall, centred on (3, 1).
        tf = fit(100, bounds=(1.0, 0.0, 5.0, 2.0))
        self.assertEqual((50.0, 50.0), tf(3.0, 1.0))
        self.assertAlmostEqual(100.0, tf(5.0, 1.0)[0])
        self.assertAlmostEqual(0.0, tf(1.0, 1.0)[0])
        # The short axis is NOT stretched — aspect ratio is preserved.
        self.assertAlmostEqual(25.0, tf(3.0, 2.0)[1])

    def test_explicit_scale_shares_centring_without_rederiving(self):
        tf = fit(100, scale=10.0)
        self.assertEqual((60.0, 50.0), tf(1.0, 0.0))

    def test_exactly_one_sizing_mode_is_required(self):
        """Two modes silently disagreeing is precisely the bug being retired."""
        with self.assertRaises(ValueError):
            fit(100)
        with self.assertRaises(ValueError):
            fit(100, half_extent=1.0, scale=10.0)

    def test_zero_extent_fails_loudly(self):
        with self.assertRaises(ValueError):
            fit(100, bounds=(1.0, 1.0, 1.0, 1.0))


class SpecAt(unittest.TestCase):
    def test_dataclass_spec(self):
        import dataclasses

        @dataclasses.dataclass
        class S:
            canvas: int
            accent: str

        self.assertEqual(S(512, "#fff"), spec_at(S(64, "#fff"), 512))

    def test_plain_object_spec(self):
        class S:
            def __init__(self, canvas, accent):
                self.canvas = canvas
                self.accent = accent

        got = spec_at(S(64, "#fff"), 512)
        self.assertEqual(512, got.canvas)
        self.assertEqual("#fff", got.accent)

    def test_alternate_field_name(self):
        import dataclasses

        @dataclasses.dataclass
        class S:
            size: int

        self.assertEqual(1024, spec_at(S(64), 1024, field="size").size)


if __name__ == "__main__":
    unittest.main()
