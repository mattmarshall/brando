#!/usr/bin/env python3
"""brando's own wordmark + lockup — the dogfood for the CONSTRUCTED-glyph path.

brando's serif "brando" is built from shapely primitives in wordmark_geom.py, not
set in a typeface, so it cannot go through `brand_wordmark`'s fontTools path. That
is exactly aion's situation, and aion's answer was 143 hand-rolled lines.

This is what that becomes once the shared parts live in `@brando//marklib:wordmark`:
the letterforms stay in wordmark_geom.py, and placement, box fitting, lockup
spacing and emission come from brando. Roughly 30 lines instead of 143, and the
30 are all brand content.

It exists to keep the path honest as much as to produce the assets. brand_skin,
brand_iconcomposer and brand_latex_class all shipped broken while having no
in-repo caller; a rule nothing exercises is a rule nobody notices breaking.

CLI: gen_wordmark.py <out-dir>
"""
import os
import sys

from shapely.ops import unary_union

from gen_godfather import Godfather, Spec
from marklib import linear_gradient, wordmark as mwordmark
from wordmark_geom import brando_word

# Ink for the wordmark on each ground — the Godfather palette's cream and ink.
INK_DARK = "#ECE7DA"   # on a dark ground
INK_LIGHT = "#0E0E0E"  # on a light ground

PPU = 200      # px per model unit
PAD = 0.10     # padding, model units
X_HEIGHT = 0.42  # wordmark x-height as a fraction of the mark's diameter
GAP = 0.30     # mark -> wordmark gap, in mark radii


def _mark_geom(spec):
    """The marionette's ink: the control bar, its strings, and the artifacts."""
    g = Godfather(spec)
    return unary_union([g.bar_geom, g.strings_geom, g.artifacts_geom]).buffer(0)


def emit_wordmark(out_dir):
    word, _ = brando_word()
    tf, w, h = mwordmark.fit_box(word.bounds, ppu=PPU, pad=PAD)
    for tag, ink in (("dark", INK_DARK), ("light", INK_LIGHT)):
        mwordmark.emit(
            os.path.join(out_dir, f"brando_wordmark_{tag}.svg"), w, h, [(word, ink)], tf
        )
    print(f"wordmark {w}x{h}")


def emit_lockup(out_dir):
    spec = Spec()
    mark = _mark_geom(spec)
    word, _ = brando_word()
    combined, placed = mwordmark.lockup(mark, word, x_height=X_HEIGHT, gap=GAP)
    tf, w, h = mwordmark.fit_box(combined.bounds, ppu=PPU, pad=PAD, floor_baseline=False)
    for tag, ink in (("dark", INK_DARK), ("light", INK_LIGHT)):
        # Mark AND wordmark take the ground's ink. Filling the mark with the
        # palette's cream regardless would paint a cream marionette onto the light
        # lockup's light ground — invisible, and invisible in a way that only
        # shows up when someone actually places the light variant.
        mwordmark.emit(
            os.path.join(out_dir, f"brando_lockup_{tag}.svg"),
            w, h,
            [(mark, ink), (placed, ink)],
            tf,
        )
    print(f"lockup {w}x{h}")


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    emit_wordmark(out_dir)
    emit_lockup(out_dir)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
