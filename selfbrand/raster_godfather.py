#!/usr/bin/env python3
"""Rasterize brando's GODFATHER marionette — hermetic, via marklib raster.

Mirrors gen/raster_tomato.py: draws the shapely polygons directly (exterior
filled, holes punched), composites bg / strings / bar / artifacts, and renders
the cream marks as vertical gradients when the spec sets gradient=True.
Antialiasing is done by rendering at 4x and downsampling (Pillow's polygon fill
is hard-edged).

Two flavors are produced:

  * the plain MARK variants (mark-only, per gen_godfather.VARIANTS), and
  * a WORDMARK lockup: the marionette mark above a cream serif "brando"
    wordmark (drawn from wordmark_geom — no external font, fully hermetic), on
    the ink rounded-square and transparent.

brando CONTENT: the palette + the avatar sizes + the lockup composition. The
Pillow plumbing lives in @brando//marklib:raster.

CLI: raster_godfather.py <out-dir>
"""
import os
import sys

from PIL import Image
from shapely.ops import unary_union

from gen_godfather import Spec, Godfather, VARIANTS
from marklib import raster as mraster
from wordmark_geom import placed_word

PNG_SIZES = [512, 1024]
SS = 4  # supersample factor for antialiasing


def _paint_mark(img, big, spec):
    """Composite a Godfather marionette mark (no background) onto ``img`` at the
    supersampled size, honoring the spec's gradient."""
    s = Spec(**{**spec.__dict__, "canvas": big})
    g = Godfather(s)
    tf = g._tf()
    top, bot, grad = s.cream, s.cream2, s.gradient
    mraster.paste_geom(img, big, tf, g.strings_geom, top, bot, gradient=grad)
    mraster.paste_geom(img, big, tf, g.bar_geom, top, bot, gradient=grad)
    mraster.paste_geom(img, big, tf, g.artifacts_geom, top, bot, gradient=grad)


def raster_mark(spec, size):
    """A mark-only variant (matches gen_godfather VARIANTS)."""
    big = size * SS
    s = Spec(**{**spec.__dict__, "canvas": big})
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    if s.background != "none":
        mraster.background_rect(img, big, s.bg_ink, s.bg_round)
    _paint_mark(img, big, spec)
    return img.resize((size, size), Image.LANCZOS)


def raster_wordmark(background, size):
    """The mark + cream serif "brando" wordmark lockup.

    The mark is rendered into the UPPER portion of the canvas (smaller + lifted)
    and the serif wordmark sits below it, Godfather-style. Everything is drawn
    through marklib raster helpers so it stays hermetic.
    """
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))

    s = Spec(background=background, gradient=False, canvas=big)
    if s.background != "none":
        mraster.background_rect(img, big, s.bg_ink, s.bg_round)

    # --- build mark + wordmark geometry together, then ONE joint transform ---
    g = Godfather(s)
    mark = [g.strings_geom, g.bar_geom, g.artifacts_geom]
    mark_minx, mark_miny, mark_maxx, mark_maxy = g._full_bounds()

    # Place the serif "brando" wordmark centered under the mark, with a gap. Size
    # it to a comfortable fraction of the mark's width so it reads at avatar size.
    mark_w = mark_maxx - mark_minx
    mark_cx = (mark_minx + mark_maxx) / 2.0
    word_h = 0.30                                   # wordmark height in model units
    gap = 0.20                                       # gap below the mark
    word_cy = mark_maxy + gap + word_h / 2.0
    word, _ = placed_word(mark_cx, word_cy, word_h)

    # Joint bounds (mark + word), one transform fitting both into the canvas with
    # generous margins, horizontally + vertically centered.
    union = unary_union(mark + [word])
    minx, miny, maxx, maxy = union.bounds
    span = max(maxx - minx, maxy - miny)
    scale_f = 0.84 * big / span
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    tf = lambda x, y: (big / 2 + (x - cx) * scale_f, big / 2 + (y - cy) * scale_f)

    mraster.paste_geom(img, big, tf, g.strings_geom, s.cream)
    mraster.paste_geom(img, big, tf, g.bar_geom, s.cream)
    mraster.paste_geom(img, big, tf, g.artifacts_geom, s.cream)
    mraster.paste_geom(img, big, tf, word, s.cream)

    return img.resize((size, size), Image.LANCZOS)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # mark-only variants
    for variant, spec in VARIANTS.items():
        for sz in PNG_SIZES:
            raster_mark(spec, sz).save(
                os.path.join(out_dir, f"brando_{variant}_{sz}.png"))
        print(f"icons brando_{variant}")
    # wordmark lockups (ink + transparent)
    for bgname, bg in (("wordmark", "ink"), ("wordmark_transparent", "none")):
        for sz in PNG_SIZES:
            raster_wordmark(bg, sz).save(
                os.path.join(out_dir, f"brando_{bgname}_{sz}.png"))
        print(f"icons brando_{bgname}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
