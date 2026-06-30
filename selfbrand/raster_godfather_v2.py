#!/usr/bin/env python3
"""Rasterize brando's GODFATHER marionette v2 (now WITH THE HAND) — hermetic.

Mirrors raster_godfather.py but composites the v2 layer stack: strings, bar, the
ink hand-halo (the over/under separation outline where the hand grips the bar),
the cream hand, then the artifact glyphs. Cream marks render as vertical
gradients when the spec sets gradient=True. Antialiasing is 4x supersample +
LANCZOS downsample (Pillow's polygon fill is hard-edged).

Two flavors are produced:

  * the plain MARK variants (mark-only, per gen_godfather_v2.VARIANTS), and
  * a WORDMARK lockup: the v2 mark above the cream serif "brando" wordmark
    (drawn from wordmark_geom — no external font, fully hermetic), on the ink
    rounded-square and transparent.

brando CONTENT: the palette + the avatar sizes + the lockup composition. The
Pillow plumbing lives in @brando//marklib:raster.

CLI: raster_godfather_v2.py <out-dir>
"""
import os
import sys

from PIL import Image
from shapely.ops import unary_union

from gen_godfather_v2 import Spec, GodfatherV2, VARIANTS
from marklib import raster as mraster
from wordmark_geom import placed_word

PNG_SIZES = [512, 1024]
SS = 4  # supersample factor for antialiasing


def _paint_mark(img, big, tf, g, spec):
    """Composite a v2 Godfather hand-marionette mark (no background) onto ``img``
    at the supersampled size under transform ``tf``, honoring the spec gradient."""
    top, bot, grad = spec.cream, spec.cream2, spec.gradient
    mraster.paste_geom(img, big, tf, g.strings_geom, top, bot, gradient=grad)
    mraster.paste_geom(img, big, tf, g.bar_geom, top, bot, gradient=grad)
    # the ink separation halo is ALWAYS solid ink (even on transparent), so the
    # grip's over/under reads on any dark surface.
    mraster.paste_geom(img, big, tf, g.halo_geom, spec.bg_ink)
    mraster.paste_geom(img, big, tf, g.hand_geom, top, bot, gradient=grad)
    mraster.paste_geom(img, big, tf, g.artifacts_geom, top, bot, gradient=grad)


def raster_mark(spec, size):
    """A mark-only variant (matches gen_godfather_v2 VARIANTS)."""
    big = size * SS
    s = Spec(**{**spec.__dict__, "canvas": big})
    g = GodfatherV2(s)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    if s.background != "none":
        mraster.background_rect(img, big, s.bg_ink, s.bg_round)
    _paint_mark(img, big, g._tf(), g, s)
    return img.resize((size, size), Image.LANCZOS)


def raster_wordmark(background, size):
    """The v2 mark + cream serif "brando" wordmark lockup.

    The mark is rendered into the UPPER portion of the canvas and the serif
    wordmark sits below it, Godfather-style. Everything is drawn through marklib
    raster helpers so it stays hermetic.
    """
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))

    s = Spec(background=background, gradient=False, canvas=big)
    if s.background != "none":
        mraster.background_rect(img, big, s.bg_ink, s.bg_round)

    g = GodfatherV2(s)
    mark = [g.strings_geom, g.bar_geom, g.hand_geom, g.artifacts_geom]
    mark_minx, mark_miny, mark_maxx, mark_maxy = g._full_bounds()

    mark_cx = (mark_minx + mark_maxx) / 2.0
    word_h = 0.30                                   # wordmark height in model units
    gap = 0.20                                       # gap below the mark
    word_cy = mark_maxy + gap + word_h / 2.0
    word, _ = placed_word(mark_cx, word_cy, word_h)

    union = unary_union(mark + [word])
    minx, miny, maxx, maxy = union.bounds
    span = max(maxx - minx, maxy - miny)
    scale_f = 0.84 * big / span
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    tf = lambda x, y: (big / 2 + (x - cx) * scale_f, big / 2 + (y - cy) * scale_f)

    mraster.paste_geom(img, big, tf, g.strings_geom, s.cream)
    mraster.paste_geom(img, big, tf, g.bar_geom, s.cream)
    mraster.paste_geom(img, big, tf, g.halo_geom, s.bg_ink)
    mraster.paste_geom(img, big, tf, g.hand_geom, s.cream)
    mraster.paste_geom(img, big, tf, g.artifacts_geom, s.cream)
    mraster.paste_geom(img, big, tf, word, s.cream)

    return img.resize((size, size), Image.LANCZOS)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for variant, spec in VARIANTS.items():
        for sz in PNG_SIZES:
            raster_mark(spec, sz).save(
                os.path.join(out_dir, f"brando_v2_{variant}_{sz}.png"))
        print(f"icons brando_v2_{variant}")
    for bgname, bg in (("wordmark", "ink"), ("wordmark_transparent", "none")):
        for sz in PNG_SIZES:
            raster_wordmark(bg, sz).save(
                os.path.join(out_dir, f"brando_v2_{bgname}_{sz}.png"))
        print(f"icons brando_v2_{bgname}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
