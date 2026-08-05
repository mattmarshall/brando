#!/usr/bin/env python3
"""brando marklib wordmark — letter placement, fitting and lockup composition.

brando shipped a wordmark generator that assumes a TTF: it outlines glyphs with
fontTools and lays them out by the font's own advance widths. That is the right
tool for a brand whose wordmark is set in a typeface, which is most of them.

It is the wrong tool for a brand whose wordmark IS the mark. aion's letterforms
are constructed from the same circle and stroke module as its logo — the `o` is
the mark's ring, the `a` is that ring plus the stem, `n` is the ring with its
sides straightened — so "aion" and the logomark are one geometric system rather
than a drawing next to some type. There is no font to outline.

Having no way to say that, aion hand-rolled 143 lines, and about 60 of them are
not aion's: placing glyphs left to right by advance, fitting a bounds to a padded
box, flipping y, composing the mark and the word into a lockup at a stated
x-height and gap, and emitting the dark/light pair. Those are the same operations
brando's TTF path performs; only the source of the outlines differs.

So this module owns the operations and neither owns the letterforms. A typeface
brand keeps using `wordmark.py`; a CSG brand supplies its own glyphs and gets the
layout, the lockup spacing and the emission from here.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from shapely.affinity import scale, translate
from shapely.ops import unary_union

Transform = Callable[[float, float], Tuple[float, float]]


def place(glyphs: Sequence[Tuple[object, float]], spacing: float = 0.0):
    """Lay glyphs out left to right. Returns `(geometry, total_width)`.

    Each entry is `(geometry, advance)` with the glyph's left edge at x=0. The
    advance is the glyph's own width; `spacing` is the gap added between glyphs
    and — importantly — NOT after the last one, so the returned width is the ink
    width rather than the ink width plus a trailing gap. Getting that wrong makes
    every lockup sit a letter-space too far left, which is invisible until two
    brands' lockups are put side by side.
    """
    parts: List[object] = []
    x = 0.0
    for geom, advance in glyphs:
        parts.append(translate(geom, xoff=x))
        x += advance + spacing
    if not parts:
        raise ValueError("place(): no glyphs")
    return unary_union(parts), x - spacing


def fit_box(bounds, *, ppu: float, pad: float, floor_baseline: bool = True):
    """Fit a bounds to a padded pixel box. Returns `(tf, width, height)`.

    Unlike `marklib.fit`, which fits a mark into a SQUARE canvas, a wordmark's box
    follows its own aspect: the width is whatever the word came out as.

    `floor_baseline` extends the box down to y=0 when the geometry sits above it,
    so a word with no descender still reserves the baseline. Without it, "aion"
    and "gap" would be vertically centred differently and a lockup would shift
    depending on which letters the brand happens to use.
    """
    minx, miny, maxx, maxy = bounds
    if floor_baseline:
        miny = min(miny, 0.0)
    width = round((maxx - minx + 2 * pad) * ppu)
    height = round((maxy - miny + 2 * pad) * ppu)

    def tf(x, y):
        return ((x - minx + pad) * ppu, (maxy - y + pad) * ppu)

    return tf, width, height


def lockup(
    mark,
    word,
    *,
    x_height: float,
    gap: float,
    mark_center: Optional[float] = None,
):
    """Place `word` to the right of `mark`. Returns `(combined, placed_word)`.

    `x_height` scales the word so its x-height is that fraction of the mark's
    diameter — the wordmark is sized RELATIVE to the mark rather than in absolute
    units, which is what keeps the pairing stable when the mark is redrawn.
    `gap` is the mark-to-word distance in mark radii, for the same reason.

    `mark_center` overrides the vertical centre the word aligns to; it defaults to
    the mark's bounds centre. A mark whose optical centre is not its geometric one
    — most marks with a descender-like element — needs to say so.
    """
    if mark_center is None:
        mark_center = (mark.bounds[1] + mark.bounds[3]) / 2.0

    placed = scale(word, xfact=x_height, yfact=x_height, origin=(0, 0))
    placed = translate(placed, xoff=(1.0 + gap), yoff=(mark_center - x_height))
    return unary_union([mark, placed]), placed


def emit(path: str, width: int, height: int, layers: Iterable[Tuple[object, str]], tf: Transform):
    """Write an SVG of `(geometry, fill)` layers.

    `fill` is any svgwrite fill — a hex string or a `url(#id)` from
    `marklib.linear_gradient`, so a gradient mark and a flat wordmark compose in
    one call. Every path gets `fill-rule: evenodd`, which is not a detail: these
    geometries are rings, and without it every `o` fills in solid.
    """
    import svgwrite

    from .marklib import geom_to_path

    drawing = svgwrite.Drawing(path, size=(width, height), viewBox="0 0 %d %d" % (width, height))
    for geom, fill in layers:
        node = drawing.add(drawing.path(d=geom_to_path(geom, tf), fill=fill))
        node.update({"fill-rule": "evenodd"})
    drawing.save()
    return path
