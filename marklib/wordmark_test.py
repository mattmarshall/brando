"""Gate on wordmark placement, fitting and lockup composition.

These are the ~60 lines aion hand-rolled inside its 143. Each case pins a
convention that was implicit there — and implicit conventions are why two brands'
lockups cannot be compared today.
"""

import os
import tempfile
import unittest

from shapely.geometry import box

from marklib import wordmark as mw


def _sq(w=1.0, h=1.0):
    """A unit-ish glyph with its left edge at x=0 and baseline at y=0."""
    return box(0.0, 0.0, w, h)


class Place(unittest.TestCase):
    def test_glyphs_advance_left_to_right(self):
        geom, width = mw.place([(_sq(), 1.0), (_sq(), 1.0)], spacing=0.0)
        self.assertAlmostEqual(0.0, geom.bounds[0])
        self.assertAlmostEqual(2.0, geom.bounds[2])
        self.assertAlmostEqual(2.0, width)

    def test_spacing_goes_between_glyphs_not_after_the_last(self):
        """A trailing gap makes every lockup sit a letter-space too far left —
        invisible until two brands' lockups are compared side by side."""
        _, width = mw.place([(_sq(), 1.0), (_sq(), 1.0), (_sq(), 1.0)], spacing=0.5)
        self.assertAlmostEqual(4.0, width)  # 3 glyphs + 2 gaps, not 3

    def test_width_is_ink_width_for_a_single_glyph(self):
        _, width = mw.place([(_sq(), 1.0)], spacing=0.5)
        self.assertAlmostEqual(1.0, width)

    def test_advance_is_independent_of_the_drawn_extent(self):
        """A glyph may overhang its advance (an 'f', a serif) — placement must
        use the advance, not the bounds, or kerning silently changes."""
        wide_ink = box(0.0, 0.0, 2.0, 1.0)
        geom, width = mw.place([(wide_ink, 0.5), (_sq(), 1.0)], spacing=0.0)
        self.assertAlmostEqual(1.5, width)
        self.assertAlmostEqual(2.0, geom.bounds[2])

    def test_no_glyphs_fails_loudly(self):
        with self.assertRaises(ValueError):
            mw.place([], 0.0)


class FitBox(unittest.TestCase):
    def test_box_follows_the_words_own_aspect(self):
        """Unlike marklib.fit, a wordmark is not squeezed into a square."""
        tf, w, h = mw.fit_box((0.0, 0.0, 4.0, 1.0), ppu=100, pad=0.0)
        self.assertEqual((400, 100), (w, h))

    def test_padding_is_applied_on_both_sides(self):
        _, w, h = mw.fit_box((0.0, 0.0, 1.0, 1.0), ppu=100, pad=0.25)
        self.assertEqual((150, 150), (w, h))

    def test_y_is_flipped_to_pixel_space(self):
        tf, _, _ = mw.fit_box((0.0, 0.0, 1.0, 1.0), ppu=100, pad=0.0)
        self.assertLess(tf(0.0, 1.0)[1], tf(0.0, 0.0)[1])

    def test_floor_baseline_reserves_y_zero(self):
        """A word with no descender still reserves the baseline, so 'aion' and
        'gap' are centred the same way rather than by which letters they use."""
        _, _, with_floor = mw.fit_box((0.0, 0.5, 1.0, 1.0), ppu=100, pad=0.0)
        _, _, without = mw.fit_box((0.0, 0.5, 1.0, 1.0), ppu=100, pad=0.0,
                                   floor_baseline=False)
        self.assertEqual(100, with_floor)
        self.assertEqual(50, without)


class Lockup(unittest.TestCase):
    def test_word_is_scaled_relative_to_the_mark(self):
        """x_height is a FRACTION of the mark's diameter, so redrawing the mark
        does not silently change the pairing."""
        mark = box(-1.0, -1.0, 1.0, 1.0)
        _, placed = mw.lockup(mark, _sq(), x_height=0.5, gap=0.0)
        self.assertAlmostEqual(0.5, placed.bounds[3] - placed.bounds[1])

    def test_word_sits_to_the_right_of_the_mark(self):
        mark = box(-1.0, -1.0, 1.0, 1.0)
        _, placed = mw.lockup(mark, _sq(), x_height=0.5, gap=0.25)
        self.assertAlmostEqual(1.25, placed.bounds[0])

    def test_gap_is_measured_in_mark_radii(self):
        mark = box(-1.0, -1.0, 1.0, 1.0)
        _, a = mw.lockup(mark, _sq(), x_height=0.5, gap=0.0)
        _, b = mw.lockup(mark, _sq(), x_height=0.5, gap=0.5)
        self.assertAlmostEqual(0.5, b.bounds[0] - a.bounds[0])

    def test_mark_center_override_moves_the_baseline(self):
        """A mark whose optical centre is not its geometric one must say so."""
        mark = box(-1.0, -1.0, 1.0, 1.0)
        _, default = mw.lockup(mark, _sq(), x_height=0.5, gap=0.0)
        _, shifted = mw.lockup(mark, _sq(), x_height=0.5, gap=0.0, mark_center=0.5)
        self.assertAlmostEqual(0.5, shifted.bounds[1] - default.bounds[1])

    def test_combined_covers_both(self):
        mark = box(-1.0, -1.0, 1.0, 1.0)
        combined, placed = mw.lockup(mark, _sq(), x_height=0.5, gap=0.25)
        self.assertAlmostEqual(-1.0, combined.bounds[0])
        self.assertAlmostEqual(placed.bounds[2], combined.bounds[2])


class Emit(unittest.TestCase):
    def test_every_path_gets_evenodd(self):
        """These geometries are rings. Without evenodd every 'o' fills in solid."""
        tf, w, h = mw.fit_box((0.0, 0.0, 1.0, 1.0), ppu=100, pad=0.0)
        with tempfile.TemporaryDirectory() as d:
            path = mw.emit(os.path.join(d, "w.svg"), w, h, [(_sq(), "#000000")], tf)
            svg = open(path, encoding="utf-8").read()
        self.assertIn('fill-rule="evenodd"', svg)

    def test_layers_emit_in_order_with_their_own_fills(self):
        tf, w, h = mw.fit_box((0.0, 0.0, 2.0, 1.0), ppu=100, pad=0.0)
        with tempfile.TemporaryDirectory() as d:
            path = mw.emit(
                os.path.join(d, "w.svg"), w, h,
                [(_sq(), "#111111"), (box(1.0, 0.0, 2.0, 1.0), "url(#grad)")], tf,
            )
            svg = open(path, encoding="utf-8").read()
        self.assertIn('fill="#111111"', svg)
        self.assertIn('fill="url(#grad)"', svg)
        self.assertLess(svg.index("#111111"), svg.index("url(#grad)"))


if __name__ == "__main__":
    unittest.main()
