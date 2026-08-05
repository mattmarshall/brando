#!/usr/bin/env python3
"""resumarsh mark — the line that carries the story.

Four stacked bars, the way a resume looks from across the room: ruled lines of
unequal length, which is what any document reduces to at a glance. One of them —
the second, where a career's turn usually is rather than at the top or the
bottom — runs longer than the rest and carries the accent.

That is the whole argument. resumarsh's claim is that a resume is structured data
and the structure is a NARRATIVE: the interesting thing is not that there are
five roles, it is which one is the story. A mark that highlighted every line
would say the opposite, which is also the brand's usage rule.

WHAT IS DELIBERATELY NOT HERE. No document outline with a folded corner, no
person silhouette, no upward arrow. The first says "file", the second says
"profile", and the third says "we score you" — which the voice rules forbid,
because the product structures a story and does not rank people.

Geometry is in a square model space with y UP — larger y is higher, matching
`fit()`'s flip. Bars are listed top-down and their y is computed from the index,
so reordering them is a data change rather than an arithmetic one.

CLI: gen_mark.py <out-dir> [--variants ...] [--layers ...]
"""
import os
import sys
from dataclasses import dataclass, field
from typing import Tuple

from shapely.geometry import box
from shapely.ops import unary_union

from marklib import Canvas, fit
from marklib import emit as emit_mod

INK = "#1A1618"
PAPER = "#FCFBFA"
PLUM = "#7A2E52"        # light-mode accent
PLUM_LIFT = "#D98BAF"   # dark-mode accent


@dataclass(frozen=True)
class Spec:
    """Every measurement, in model units on a 100x100 square."""

    # Relative bar lengths, top to bottom. The second is the story: it is the
    # longest, and it is the one the accent lands on.
    lengths: Tuple[float, ...] = (0.72, 1.00, 0.56, 0.84)
    story: int = 1
    span: float = 68.0      # the length a 1.00 bar occupies
    bar_h: float = 13.0
    gap: float = 8.0
    left: float = 16.0
    radius: float = 0.0     # square ends; a rounded bar reads as a pill/tag
    fit: float = 0.84

    @property
    def total_h(self) -> float:
        n = len(self.lengths)
        return n * self.bar_h + (n - 1) * self.gap


def bars(s: Spec):
    """(index, geometry) top to bottom. y is computed from the index, so the
    order is data rather than four hand-written offsets."""
    top = 50.0 + s.total_h / 2.0
    out = []
    for i, frac in enumerate(s.lengths):
        y1 = top - i * (s.bar_h + s.gap)
        out.append((i, box(s.left, y1 - s.bar_h, s.left + s.span * frac, y1)))
    return out


def layers(s: Spec, mode: str):
    """The mark's layers, back to front."""
    fg = PAPER if mode == "dark" else INK
    accent = PLUM_LIFT if mode == "dark" else PLUM

    placed = bars(s)
    rest = unary_union([g for i, g in placed if i != s.story])
    story = [g for i, g in placed if i == s.story][0]

    whole = unary_union([rest, story])
    tf = fit(1024, bounds=whole.bounds, pad=(1.0 - s.fit) / 2.0)

    return [
        ("lines", rest, fg),
        ("story", story, accent),
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
    e = emit_mod.parse_args(sys.argv[1:], prefix="resumarsh", variants=list(VARIANTS))
    for name in e.variants:
        canvas_for(name).emit(os.path.join(e.out_dir, "%s_%s" % (e.prefix, name)))
