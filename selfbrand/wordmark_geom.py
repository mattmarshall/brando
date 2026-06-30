#!/usr/bin/env python3
"""A tiny, self-contained serif wordmark builder for "brando".

To keep the self-brand fully HERMETIC (no system/bundled font files) while
staying in the marklib spirit (everything is shapely CSG), the "brando"
wordmark is drawn as parametric serif letterforms built from shapely
primitives — stems, elliptical bowls (rings), shoulders, and bracketed serif
slabs. It is intentionally compact: only b, r, a, n, d, o are needed.

CONVENTIONS (important): coordinates are in a left-to-right "em" space with y
DOWN (SVG/canvas style). The BASELINE is y = 0. The x-height band is therefore
y in [-X, 0]; ascenders (b, d) rise to y = -ASC (more negative). Each builder
returns ``(geom, advance)`` and lays its ink starting at x = x0.

``brando_word()`` unions the letters into one geometry; ``placed_word(cx, cy,
h)`` scales it to height ``h`` and centers it at ``(cx, cy)`` in a caller's
model space (also y DOWN), returning ``(geom, width)``.
"""
from __future__ import annotations

import math

from shapely.affinity import scale as _scale
from shapely.affinity import translate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

SEG = 96

# ---- design metrics (em-space, y DOWN; baseline at y=0) ----
X = 0.66          # x-height (top of x-height band at y = -X)
ASC = 1.02        # ascender top (y = -ASC) for b, d
STEM = 0.115      # stem half-width
SERIF_OUT = 0.085  # how far a serif extends beyond the stem on each side
SERIF_H = 0.060   # serif slab thickness
WALL = 0.110      # bowl / round-letter wall thickness
BOWL_RX = 0.260   # round-letter bowl outer x-radius


def _ellipse(cx, cy, rx, ry, n=SEG):
    return Polygon([
        (cx + rx * math.cos(2 * math.pi * i / n),
         cy + ry * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ])


def _ring(cx, cy, rx, ry, wall):
    """An elliptical ring centered at (cx, cy): outer minus a wall-thick inner."""
    return _ellipse(cx, cy, rx, ry).difference(
        _ellipse(cx, cy, rx - wall, ry - wall))


def _serif(cx, baseline_y):
    """A bracketed serif slab sitting ON a baseline_y (slab spans the line)."""
    return box(cx - (STEM + SERIF_OUT), baseline_y - SERIF_H / 2.0,
               cx + (STEM + SERIF_OUT), baseline_y + SERIF_H / 2.0)


def _stem(cx, y_top, y_bot, top_serif=True, bot_serif=True):
    """A vertical stem from y_top (smaller/higher) to y_bot (baseline-ish)."""
    parts = [box(cx - STEM, y_top, cx + STEM, y_bot)]
    if top_serif:
        parts.append(_serif(cx, y_top))
    if bot_serif:
        parts.append(_serif(cx, y_bot))
    return unary_union(parts)


# ---- letters: each returns (geom, advance) and starts ink at x0 ----

def _letter_o(x0):
    cx = x0 + BOWL_RX
    cy = -X / 2.0
    return _ring(cx, cy, BOWL_RX, X / 2.0, WALL), 2 * BOWL_RX + 0.06


def _letter_b(x0):
    # ascender stem on the LEFT, bowl on the RIGHT, in the x-height band.
    stem_x = x0 + STEM
    stem = _stem(stem_x, -ASC, 0.0, top_serif=True, bot_serif=False)
    bcx = stem_x + (BOWL_RX - WALL * 0.4)
    bcy = -X / 2.0
    bowl = _ring(bcx, bcy, BOWL_RX, X / 2.0, WALL)
    # fuse: drop the bowl's left half-wall into the stem
    bowl = bowl.difference(box(x0 - 0.4, -X - 0.4, stem_x, 0.4))
    return unary_union([stem, bowl]).buffer(0), (bcx + BOWL_RX) - x0 + 0.06


def _letter_d(x0):
    # bowl on the LEFT, ascender stem on the RIGHT (mirror of b).
    bcx = x0 + BOWL_RX
    bcy = -X / 2.0
    bowl = _ring(bcx, bcy, BOWL_RX, X / 2.0, WALL)
    stem_x = bcx + (BOWL_RX - WALL * 0.4)
    stem = _stem(stem_x, -ASC, 0.0, top_serif=True, bot_serif=True)
    bowl = bowl.difference(box(stem_x, -ASC - 0.4, x0 + 2 * BOWL_RX + 0.4, 0.4))
    return unary_union([stem, bowl]).buffer(0), (stem_x + STEM + SERIF_OUT) - x0 + 0.05


def _letter_n(x0):
    left_x = x0 + STEM
    width = 2 * BOWL_RX - 0.04
    right_x = left_x + width
    left = _stem(left_x, -X, 0.0, top_serif=True, bot_serif=True)
    right = _stem(right_x, -X, 0.0, top_serif=False, bot_serif=True)
    # shoulder: top half of a ring arching from the left stem to the right stem.
    acx = (left_x + right_x) / 2.0
    arch_ry = X * 0.66
    arch = _ring(acx, -X + arch_ry, (right_x - left_x) / 2.0 + STEM, arch_ry, WALL)
    # keep only the UPPER half of the ring (y above its center = smaller y).
    arch = arch.intersection(box(x0 - 0.4, -X - 0.4, right_x + 0.4, -X + arch_ry))
    return unary_union([left, right, arch]).buffer(0), (right_x + STEM + SERIF_OUT) - x0 + 0.05


def _letter_r(x0):
    stem_x = x0 + STEM
    stem = _stem(stem_x, -X, 0.0, top_serif=True, bot_serif=True)
    # a short arm/shoulder curving up-right out of the stem top.
    acx = stem_x + 0.10
    arch_ry = X * 0.60
    arch = _ring(acx, -X + arch_ry, 0.20, arch_ry, WALL)
    arch = arch.intersection(box(stem_x, -X - 0.4, acx + 0.30, -X + arch_ry))
    return unary_union([stem, arch]).buffer(0), 0.34


def _letter_a(x0):
    # a two-story serif 'a': a lower bowl + a right stem + a small top arch.
    rx = BOWL_RX * 0.96
    bcx = x0 + rx
    bowl_cy = -X * 0.30
    bowl = _ring(bcx, bowl_cy, rx, X * 0.30, WALL)
    stem_x = x0 + 2 * rx - STEM
    stem = _stem(stem_x, -X, 0.0, top_serif=False, bot_serif=True)
    # top arch from stem over the bowl
    arch_ry = X * 0.44
    arch = _ring(bcx, -X + arch_ry, rx, arch_ry, WALL)
    arch = arch.intersection(box(x0 - 0.4, -X - 0.4, stem_x + STEM, -X + arch_ry))
    return unary_union([bowl, stem, arch]).buffer(0), (stem_x + STEM + SERIF_OUT) - x0 + 0.05


_BUILDERS = {
    "b": _letter_b,
    "r": _letter_r,
    "a": _letter_a,
    "n": _letter_n,
    "d": _letter_d,
    "o": _letter_o,
}


def brando_word(tracking: float = 0.050):
    """Union the "brando" letters in em-space. Returns ``(geom, width)``."""
    parts = []
    x = 0.0
    for ch in "brando":
        g, adv = _BUILDERS[ch](x)
        parts.append(g)
        x += adv + tracking
    word = unary_union(parts).buffer(0.003).buffer(-0.003)
    minx, _, maxx, _ = word.bounds
    return word, maxx - minx


def placed_word(cx, cy, target_h):
    """Scale the wordmark to ``target_h`` tall and center it at (cx, cy) in the
    caller's model space (y DOWN). Returns ``(geom, width)``."""
    word, _ = brando_word()
    minx, miny, maxx, maxy = word.bounds
    s = target_h / (maxy - miny)
    word = _scale(word, xfact=s, yfact=s, origin=(0, 0))
    minx, miny, maxx, maxy = word.bounds
    word = translate(word, xoff=cx - (minx + maxx) / 2.0,
                     yoff=cy - (miny + maxy) / 2.0)
    return word, (maxx - minx) * s
