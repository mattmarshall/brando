#!/usr/bin/env python3
"""leangres mark — the turnstile, closing.

leangres proves SQL correct before it runs, and mathematics already has the two
symbols for that. The turnstile ⊢ opens a claim -- a stem for the theory, a bar
for what follows from it. The halmos ∎ closes one: the filled square that ends a
proof. Together they read "⊢ … ∎", which is the entire product in two glyphs.

A first attempt put a Postgres elephant-ear ring at the end of the bar. It was a
better IDEA and a worse MARK: at 200px, an avatar's actual size, the ring read as
a blob with a bite taken out of it. The halmos is flat geometry that survives any
scale, and it is the more precise claim anyway -- an elephant says which database,
the halmos says what leangres does to it.

WHAT IS DELIBERATELY NOT HERE. No database cylinder, no shield, no checkmark. A
checkmark says "we tested it", which is precisely the distinction leangres exists
to draw and its own voice rules forbid blurring: proved is not tested.

Geometry is in a square model space with y UP — larger y is higher, matching
`fit()`'s flip. citizen-sh's mark was drawn with the opposite assumption and came
out upside down, which is worth stating once per generator rather than
rediscovering.

CLI: gen_mark.py <out-dir> [--variants ...] [--layers ...]
"""
import os
import sys
from dataclasses import dataclass

from shapely.geometry import box
from shapely.ops import unary_union

from marklib import Canvas, fit
from marklib import emit as emit_mod

INK = "#12161A"
PAPER = "#FBFCFC"
VERIFIED = "#4FC08D"   # the dark-mode green; the accent that marks verification
DEEP = "#1B7A55"       # the light-mode green


@dataclass(frozen=True)
class Spec:
    """Every measurement, in model units on a 100x100 square."""

    stem_w: float = 13.0
    stem_h: float = 62.0
    stem_x: float = 20.0
    bar_h: float = 13.0
    bar_len: float = 26.0
    qed: float = 24.0          # the halmos, a square, centred on the bar
    qed_gap: float = 9.0       # the reveal between the bar and the halmos
    base_y: float = 19.0
    fit: float = 0.82


def _turnstile(s: Spec):
    """The ⊢ itself: a stem, and a bar at its vertical midpoint."""
    stem = box(s.stem_x, s.base_y, s.stem_x + s.stem_w, s.base_y + s.stem_h)
    mid = s.base_y + s.stem_h / 2.0
    bar = box(
        s.stem_x + s.stem_w, mid - s.bar_h / 2.0,
        s.stem_x + s.stem_w + s.bar_len, mid + s.bar_h / 2.0,
    )
    return unary_union([stem, bar]), mid


def _halmos(s: Spec, mid: float):
    """∎ — the filled square that ends a proof. Flat geometry, no curve to lose."""
    x = s.stem_x + s.stem_w + s.bar_len + s.qed_gap
    return box(x, mid - s.qed / 2.0, x + s.qed, mid + s.qed / 2.0)


def layers(s: Spec, mode: str):
    """The mark's layers, back to front."""
    fg = PAPER if mode == "dark" else INK
    accent = VERIFIED if mode == "dark" else DEEP

    turnstile, mid = _turnstile(s)
    halmos = _halmos(s, mid)

    whole = unary_union([turnstile, halmos])
    tf = fit(1024, bounds=whole.bounds, pad=(1.0 - s.fit) / 2.0)

    return [
        # The turnstile opens the claim; the halmos closes it, so the halmos
        # carries the accent. Green marks verification and nothing else.
        ("turnstile", turnstile, fg),
        ("halmos", halmos, accent),
    ], tf


VARIANTS = {
    "flat": ("light", PAPER),
    "inkbg": ("dark", INK),
    "transparent": ("light", None),
}


def canvas_for(variant: str, s: Spec = Spec()) -> Canvas:
    mode, ground = VARIANTS[variant]
    parts, tf = layers(s, mode)
    c = Canvas(size=1024, tf=tf)
    if ground is not None:
        c.add_background(ground)
    for name, geom, fill in parts:
        c.add_layer(name, geom, fill)
    return c


if __name__ == "__main__":
    e = emit_mod.parse_args(sys.argv[1:], prefix="leangres", variants=list(VARIANTS))
    for name in e.variants:
        canvas_for(name).emit(os.path.join(e.out_dir, "%s_%s" % (e.prefix, name)))
