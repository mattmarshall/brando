"""Gate on the rasterizer driver — the loop four brands each copied.

Two of the cases here are the reason the lift is a correctness fix rather than
tidying:

  * `test_supersampling_antialiases` pins the quality property that fastverk and
    meridian silently lacked. Their rasterizers were copied from a version without
    it, so their small icons have hard diagonals — nobody decided that.
  * `test_packed_without_the_source_size_fails_loudly` pins the failure mode of
    asking for an .icns built from a size that was never rendered. Pillow's own
    error for that is unhelpful, and this is a config mistake a brand will make.
"""

import dataclasses
import os
import tempfile
import unittest

from shapely.geometry import Point

from marklib import raster
from marklib.fit import fit


@dataclasses.dataclass
class Spec:
    canvas: int = 64
    fill: str = "#3B6FF0"


def _paint_disc(img, px, spec):
    """A brand's per-mark callback: one filled disc, inset so edges are visible."""
    tf = fit(px, half_extent=1.0, pad=0.05)
    raster.paste_geom(img, px, tf, Point(0, 0).buffer(1.0, quad_segs=64), spec.fill)


class RenderSet(unittest.TestCase):
    def test_writes_one_png_per_size(self):
        with tempfile.TemporaryDirectory() as out:
            written = raster.render_set(out, "t", Spec(), _paint_disc, sizes=(16, 32), ss=1)
            self.assertEqual(
                [os.path.join(out, "t_16.png"), os.path.join(out, "t_32.png")], written
            )
            for path in written:
                self.assertTrue(os.path.exists(path))

    def test_returns_the_paths_it_wrote(self):
        """brand_icons computes `outs` from the same policy; this is the contract."""
        with tempfile.TemporaryDirectory() as out:
            written = raster.render_set(
                out, "t", Spec(), _paint_disc, sizes=(256, 1024), ss=1, packed=True
            )
            self.assertEqual(
                {"t_256.png", "t_1024.png", "t.icns", "t.ico"},
                {os.path.basename(p) for p in written},
            )

    def test_rendered_image_is_the_requested_size_not_the_supersampled_one(self):
        with tempfile.TemporaryDirectory() as out:
            raster.render_set(out, "t", Spec(), _paint_disc, sizes=(32,), ss=4)
            from PIL import Image

            with Image.open(os.path.join(out, "t_32.png")) as im:
                self.assertEqual((32, 32), im.size)

    def test_supersampling_antialiases(self):
        """The property fastverk and meridian lost by copying the wrong file.

        Pillow's polygon fill is hard-edged, so without supersampling a curve's
        alpha channel is binary: every pixel is 0 or 255. Downsampling from a
        larger render produces intermediate alpha. Counting partially-transparent
        pixels distinguishes the two without depending on exact geometry.
        """
        from PIL import Image

        def partial_alpha(ss):
            with tempfile.TemporaryDirectory() as out:
                raster.render_set(out, "t", Spec(), _paint_disc, sizes=(64,), ss=ss)
                with Image.open(os.path.join(out, "t_64.png")) as im:
                    alpha = im.convert("RGBA").getchannel("A")
                    return sum(1 for v in alpha.getdata() if 0 < v < 255)

        self.assertEqual(0, partial_alpha(1))
        self.assertGreater(partial_alpha(4), 0)

    def test_packed_without_the_source_size_fails_loudly(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(ValueError) as ctx:
                raster.render_set(out, "t", Spec(), _paint_disc, sizes=(16,), packed=True)
            self.assertIn("not in sizes", str(ctx.exception))

    def test_is_byte_identical_to_the_hand_rolled_loop_it_replaces(self):
        """The acceptance test for the lift: adoption must not move a pixel.

        This reproduces the loop verbatim as the brands wrote it -- rebuild the
        spec at size*SS, make a transparent RGBA image, paint, LANCZOS down -- and
        asserts render_set produces the same bytes. Without this, "we lifted the
        rasterizer" is a claim; with it, a brand can migrate and know the only
        thing that changed is the amount of code it owns.

        Deliberately run at ss=2 (aion's and tomato's setting) rather than ss=1,
        so the supersample path itself is what is being compared.
        """
        from PIL import Image

        from marklib.fit import spec_at

        spec, size, ss = Spec(), 64, 2

        # --- the loop as every brand wrote it, inlined ---
        big = size * ss
        s = spec_at(spec, big)
        legacy = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        _paint_disc(legacy, big, s)
        legacy = legacy.resize((size, size), Image.LANCZOS)

        with tempfile.TemporaryDirectory() as out:
            legacy_path = os.path.join(out, "legacy.png")
            legacy.save(legacy_path)
            raster.render_set(out, "lifted", spec, _paint_disc, sizes=(size,), ss=ss)
            with open(legacy_path, "rb") as a, open(os.path.join(out, f"lifted_{size}.png"), "rb") as b:
                self.assertEqual(a.read(), b.read())

    def test_paint_receives_the_supersampled_size_and_a_rebuilt_spec(self):
        """The brand never does `size * ss` itself — that was the old sharp edge."""
        seen = []

        def paint(img, px, spec):
            seen.append((px, spec.canvas))

        with tempfile.TemporaryDirectory() as out:
            raster.render_set(out, "t", Spec(canvas=1), paint, sizes=(32,), ss=2)
        self.assertEqual([(64, 64)], seen)


if __name__ == "__main__":
    unittest.main()
