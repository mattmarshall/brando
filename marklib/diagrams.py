#!/usr/bin/env python3
"""brando marklib diagrams — the brandbook guideline plates.

Only fastverk has a brandbook, so only fastverk has construction / grid /
clearspace figures. But nothing about those plates is fastverk's: a construction
diagram is a crosshair, a reference circle, the geometry outlined, and a dot at
each defining vertex; a clear-space plate is a dashed frame at a stated clearance
with one corner marked to show the unit. What was fastverk's is five hex values
and which shapes to outline.

Lifting the layout means the other five brands get brandbook figures for the cost
of naming their own geometry -- which is the difference between "fastverk produces
17 artifact types and graph produces 2" being a fact about tooling and being a
fact about how much someone had time to hand-build.

Colours are parameters with no defaults on the palette-bearing arguments: a
diagram that silently drew itself in fastverk's amber would be exactly the leak
this module exists to remove.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

Point = Tuple[float, float]


def _outline(draw, tf, ring, color, width):
    draw.line([tf(x, y) for x, y in ring.exterior.coords],
              fill=color, width=width, joint="curve")


def construction(
    path: str,
    size: int,
    tf,
    *,
    bg: str,
    guide: str,
    rings: Sequence[Tuple[object, str, int]] = (),
    points: Sequence[Tuple[float, float, str]] = (),
    circle: Optional[Tuple[float, str, int]] = None,
    crosshair: bool = True,
    dot_r: int = 7,
    margin: int = 30,
):
    """The construction plate: reference geometry with its defining points.

    `rings` are `(shapely polygon, colour, stroke width)`; `points` are
    `(model x, model y, colour)` dots marking the vertices the construction is
    derived from; `circle` is `(model radius, colour, width)` for the reference
    circle a mark is built on. All optional -- a mark built on a square names no
    circle, and saying so is better than drawing one at radius 0.
    """
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    cx, cy = tf(0, 0)

    if crosshair:
        d.line([(cx, margin), (cx, size - margin)], fill=guide, width=1)
        d.line([(margin, cy), (size - margin, cy)], fill=guide, width=1)

    if circle is not None:
        r_model, color, width = circle
        # Radius in pixels, measured through the transform rather than assumed,
        # so this stays correct for any scale or padding the brand chose.
        r = abs(tf(r_model, 0)[0] - cx)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)

    for ring, color, width in rings:
        _outline(d, tf, ring, color, width)

    for x, y, color in points:
        px, py = tf(x, y)
        d.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=color)

    img.save(path)
    return path


def grid(path: str, size: int, mark: Image.Image, *, bg: str, crosshair: str,
         major_width: int = 3, minor_width: int = 2):
    """The mark under an optical-centre crosshair.

    `mark` is an already-rendered RGBA image at `size` -- pass whatever
    `raster.render` produced, so the plate shows the real artifact rather than a
    second rendering that could drift from it.
    """
    base = Image.new("RGBA", (size, size), bg)
    base.alpha_composite(mark.convert("RGBA"))
    d = ImageDraw.Draw(base)
    d.line([(0, size // 2), (size, size // 2)], fill=crosshair, width=major_width)
    d.line([(size // 2, 0), (size // 2, size)], fill=crosshair, width=minor_width)
    base.convert("RGB").save(path)
    return path


def clearspace(path: str, size: int, mark: Image.Image, *, bg: str, frame: str,
               unit: str, clearance_frac: float = 0.20, mark_frac: float = 0.58,
               dash: int = 14, width: int = 3):
    """The mark inside a dashed clear-space frame, with the unit called out.

    `clearance_frac` is a fraction of the MARK's size, not the plate's -- the
    convention worth stating, because clear space that scales with the plate is
    meaningless as a rule. It defaults to 0.20 to match the rounded-square corner
    radius, which is the standard way to make the clearance a visible property of
    the mark rather than an arbitrary number.
    """
    icon = int(size * mark_frac)
    off = (size - icon) // 2
    clr = int(icon * clearance_frac)

    img = Image.new("RGBA", (size, size), bg)
    img.alpha_composite(mark.convert("RGBA").resize((icon, icon), Image.LANCZOS), (off, off))
    d = ImageDraw.Draw(img)

    x0, y0, x1, y1 = off - clr, off - clr, off + icon + clr, off + icon + clr
    for x in range(x0, x1, dash * 2):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=frame, width=width)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=frame, width=width)
    for y in range(y0, y1, dash * 2):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=frame, width=width)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=frame, width=width)

    # One corner square showing that the clearance IS the stated unit.
    d.rectangle([off - clr, off - clr, off, off], outline=unit, width=width)
    img.convert("RGB").save(path)
    return path
