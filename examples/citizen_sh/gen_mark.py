#!/usr/bin/env python3
"""citizen-sh mark — a portico, which is also the stack.

ONE FORM, TWO READINGS, and that is the whole idea. Seen as architecture it is a
portico: the colonnade of a public library or a courthouse, the most legible
shorthand there is for civic infrastructure held in common. Seen as a diagram it
is citizen-sh's own stack drawn honestly — a foundation course, load-bearing
columns rising from it, and an entablature resting on top. Hardware, seL4, the
userland above it. The columns carry the roof; nothing is decorative.

The gap between the middle columns is the door. A library you cannot walk into is
a warehouse.

WHY IT IS DRAWN AND NOT SET IN TYPE. citizen-sh's claim is that its core
assertions are machine-checked rather than asserted. A mark built from exact CSG
— every measurement derived from one Spec, no hand-nudged control points — is a
small version of the same promise: the drawing is reproducible, and two builds
cannot disagree.

Geometry is in a square model space with y UP — larger y is HIGHER, so the
entablature has the largest y and the stylobate the smallest. `fit()` flips to
pixel space. Getting this backwards is not a subtle bug but it is an invisible
one in code: the first render came out with the foundation resting on top of the
columns, which is structurally impossible and reads instantly wrong in the image
while looking perfectly reasonable in the source.

CLI: gen_mark.py <out-dir> [--variants ...] [--layers ...] [--sizes ...]
"""
import os
import sys
from dataclasses import dataclass

from shapely.geometry import box
from shapely.ops import unary_union

from marklib import Canvas, fit
from marklib import emit as emit_mod

# The palette this mark is drawn in. It mirrors citizen_sh.textpb, which is the
# source of truth for everything that RENDERS a brand; a generator draws shapes
# and needs the two or three colours it fills them with.
INK = "#14171A"
PAPER = "#FBFAF7"
VERDIGRIS = "#1F6F63"
PATINA = "#5FB8A6"


@dataclass(frozen=True)
class Spec:
    """Every measurement, in model units on a 100x100 square."""

    columns: int = 4
    column_w: float = 9.0
    column_h: float = 42.0
    span: float = 76.0          # outer width of the colonnade
    entablature_h: float = 11.0
    entablature_pad: float = 5.0  # the roof oversails the columns, per side
    stylobate_h: float = 8.0
    stylobate_pad: float = 8.0    # the base oversails further than the roof
    course_gap: float = 2.5       # the reveal between roof, columns and base
    door_extra: float = 14.0      # how much wider the central intercolumniation is
    fit: float = 0.80
    base_y: float = 26.0          # bottom of the stylobate, in model units


def _columns(s: Spec):
    """Columns spread across the span, with a wider gap at the centre: the door.

    Spacing is solved rather than tabulated, so changing `columns` or `door_extra`
    cannot leave the colonnade off-centre.
    """
    n = s.columns
    if n % 2:
        # With an odd count the centre of the colonnade falls ON a column, so
        # there is no middle gap to widen and the portico has no door.
        fail = "citizen-sh's portico needs an even column count; got %d" % n
        raise ValueError(fail)

    gaps = n - 1
    door = (gaps - 1) // 2  # the MIDDLE gap index: 1 for four columns
    base_gap = (s.span - n * s.column_w - s.door_extra) / gaps

    y0 = s.base_y + s.stylobate_h + s.course_gap
    out = []
    x = (100.0 - s.span) / 2.0
    for i in range(n):
        out.append(box(x, y0, x + s.column_w, y0 + s.column_h))
        if i < gaps:
            x += s.column_w + base_gap + (s.door_extra if i == door else 0.0)
    return out


def layers(s: Spec, mode: str):
    """The mark's layers, bottom to top."""
    fg = PAPER if mode == "dark" else INK
    accent = PATINA if mode == "dark" else VERDIGRIS

    cols = _columns(s)
    col_bottom = s.base_y + s.stylobate_h + s.course_gap
    col_top = col_bottom + s.column_h

    stylobate = box(
        (100.0 - s.span) / 2.0 - s.stylobate_pad, s.base_y,
        (100.0 + s.span) / 2.0 + s.stylobate_pad, s.base_y + s.stylobate_h,
    )
    entablature = box(
        (100.0 - s.span) / 2.0 - s.entablature_pad, col_top + s.course_gap,
        (100.0 + s.span) / 2.0 + s.entablature_pad,
        col_top + s.course_gap + s.entablature_h,
    )

    whole = unary_union([entablature, stylobate] + cols)
    tf = fit(1024, bounds=whole.bounds, pad=(1.0 - s.fit) / 2.0)

    return [
        # The foundation is the accent: it is the layer citizen-sh actually
        # builds first, and the one nobody else in the stack provides.
        ("base", stylobate, accent),
        ("columns", unary_union(cols), fg),
        ("roof", entablature, fg),
    ], tf


# variant -> (mode, background). `transparent` has no ground, which is why the
# `outs` for it legitimately omit bg.svg.
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
    e = emit_mod.parse_args(sys.argv[1:], prefix="citizen_sh", variants=list(VARIANTS))
    for name in e.variants:
        canvas_for(name).emit(os.path.join(e.out_dir, "%s_%s" % (e.prefix, name)))
