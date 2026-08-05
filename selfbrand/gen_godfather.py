#!/usr/bin/env python3
"""brando self-brand mark — the GODFATHER marionette.

brando is brand tooling; brando's first client is ITSELF. The mark dogfoods
brando's own pipeline: it is built with shapely CSG and emitted through
``@brando//marklib`` (the same convention tomato-bazel uses), so generating it
proves brando's public mark-authoring API end-to-end.

The concept (a play on The Godfather / Marlon Brando): the iconic mark is the
puppeteer's CONTROL BAR with hanging strings. For brando the metaphor is
literal — brand tooling *pulls all the strings*: one source generates every
brand artifact. So the mark is a marionette control CROSS near the top, with
several thin STRINGS descending, each ending in a small brand-artifact glyph:

  * a rounded-square app icon,
  * a filled color swatch (circle),
  * a type "mark" tile (an "A" serif-ish glyph cut from a tile),
  * a document/page with a couple of text lines.

ONE Spec drives everything, mirroring gen_tomato.py: shapely is the exact CSG
(the control bar, the cross strut, the strings, the four artifact glyphs);
emission is svgwrite, as canonical LAYERS (bg / bar / strings / artifacts) plus
a composite. Construction is deterministic — no randomness — so output is
reproducible.

Geometry lives in a square model space with y DOWN (so "top" is small y, like
SVG). ``_tf`` maps the model into ~84% of the square canvas, centered, with a
small optical nudge. Aesthetic: cream marks on near-black ink (Godfather
palette).

CLI: ``gen_godfather.py <out-dir>`` emits every VARIANT's layered set.
"""
import math
import os
import sys
from dataclasses import dataclass

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from marklib import emit
from marklib import Canvas, geom_to_path


@dataclass
class Spec:
    # ---- model space ----
    # The mark is laid out in a [-1, 1] x [-1, 1] box, y DOWN (SVG-like): the
    # control cross sits near the top (small y), the artifacts hang below.
    canvas: int = 1024

    # ---- control bar / cross (the puppeteer's handle) ----
    bar_y: float = -0.74          # vertical position of the main horizontal bar
    bar_halfw: float = 0.74       # bar half-width
    bar_thick: float = 0.085      # bar half-thickness
    bar_round: float = 0.085      # bar end rounding (model units)
    strut_halfw: float = 0.30     # the crossed second (shorter) bar's half-width
    strut_y: float = -0.66        # the cross strut hangs slightly below the bar...
    strut_thick: float = 0.062    # ...and is a touch thinner
    show_strut: bool = True       # subtle crossed second bar (the marionette cross)

    # ---- strings ----
    # Each artifact hangs from an attachment point on the bar by a thin string.
    string_thick: float = 0.011   # string half-width (very thin)
    # x positions on the bar where strings attach (4 strings), and the x of the
    # glyph each one drops to (a gentle splay).
    attach_xs: tuple = (-0.52, -0.18, 0.18, 0.52)
    glyph_xs: tuple = (-0.62, -0.21, 0.21, 0.62)
    glyph_y: float = 0.50         # vertical center of the artifact row
    string_top_gap: float = 0.02  # start strings just below the bar bottom edge

    # ---- artifact glyphs (all roughly fit a ~0.30 model-unit cell) ----
    cell: float = 0.165           # glyph half-extent (most glyphs ~ this size)
    icon_round: float = 0.052     # rounded-square app-icon corner radius (model units)
    swatch_r: float = 0.150       # color-swatch circle radius
    type_round: float = 0.040     # type-tile corner radius
    doc_w: float = 0.130          # document half-width
    doc_h: float = 0.165          # document half-height
    doc_fold: float = 0.072       # dog-eared corner fold size
    doc_lines: int = 3            # number of text lines on the document
    doc_line_thick: float = 0.013 # half-thickness of a doc text line

    # ---- attachment "beads" where each string meets its glyph ----
    bead_r: float = 0.018

    # ---- colors (Godfather palette: cream on ink) ----
    cream: str = "#ECE7DA"        # marks / strings / glyphs
    cream2: str = "#D8D1BF"       # deeper cream gradient end (bottom)
    ink: str = "#0E0E0E"          # near-black rounded-square bg
    bg_ink: str = "#0E0E0E"

    # ---- toggles ----
    gradient: bool = False        # subtle vertical cream gradient on the marks
    background: str = "ink"       # ink | none (transparent)
    bg_round: float = 0.22        # rounded-square corner radius (frac of canvas)
    fit: float = 0.86             # fraction of the canvas the mark fills
    optical_dy: float = 0.0       # optical vertical nudge in model units


class Godfather:
    """Deterministic shapely construction + marklib emission of the marionette."""

    SEG = 96  # polygon segments per circle (smooth at 1024px)

    def __init__(self, s: Spec):
        self.s = s
        self.bar_geom = self._bar()
        self.glyphs = self._glyphs()             # list of (kind, geom)
        self.artifacts_geom = unary_union([g for _, g in self.glyphs])
        self.strings_geom = self._strings()      # strings + beads

    # ---- primitives ----
    @staticmethod
    def _circle(cx, cy, r, n=SEG):
        return Polygon([
            (cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ])

    @staticmethod
    def _rounded_rect(cx, cy, hw, hh, r):
        """A rounded rectangle centered at (cx, cy) with half-extents hw/hh and
        corner radius r, via shapely buffer (dilate a shrunken core)."""
        r = max(0.0, min(r, hw, hh))
        if r <= 0:
            return box(cx - hw, cy - hh, cx + hw, cy + hh)
        core = box(cx - hw + r, cy - hh + r, cx + hw - r, cy + hh - r)
        return core.buffer(r, join_style=1, quad_segs=24)

    @staticmethod
    def _seg(x0, y0, x1, y1, half):
        """A thin rounded segment (string) from (x0,y0) to (x1,y1)."""
        return LineString([(x0, y0), (x1, y1)]).buffer(half, cap_style=1, quad_segs=12)

    # ---- the control bar + crossed strut ----
    def _bar(self):
        s = self.s
        parts = [self._rounded_rect(0.0, s.bar_y, s.bar_halfw, s.bar_thick, s.bar_round)]
        if s.show_strut:
            # the crossed second bar: a shorter horizontal piece hung just below,
            # giving the unmistakable marionette "cross" read.
            parts.append(
                self._rounded_rect(0.0, s.strut_y, s.strut_halfw, s.strut_thick,
                                   s.strut_thick))
            # a short vertical connector fusing bar + strut into one rigid cross
            parts.append(
                self._rounded_rect(0.0, (s.bar_y + s.strut_y) / 2.0,
                                   s.strut_thick * 0.9,
                                   abs(s.strut_y - s.bar_y) / 2.0 + s.bar_thick,
                                   s.strut_thick * 0.9))
        return unary_union(parts).buffer(0)

    # ---- the four hanging strings + the bead where each meets its glyph ----
    def _strings(self):
        s = self.s
        bar_bottom = s.bar_y + s.bar_thick  # y of the bar's lower edge (y-down)
        parts = []
        for ax, gx in zip(s.attach_xs, s.glyph_xs):
            y_top = bar_bottom + s.string_top_gap
            y_bot = s.glyph_y - s.cell - s.bead_r * 0.4
            parts.append(self._seg(ax, y_top, gx, y_bot, s.string_thick))
            parts.append(self._circle(gx, y_bot, s.bead_r))
        return unary_union(parts).buffer(0)

    # ---- the artifact glyphs ----
    def _glyph_icon(self, cx, cy):
        """A rounded-square app icon with a punched-out smaller rounded square
        (a hollow 'app tile' reads cleanly at small sizes)."""
        s = self.s
        outer = self._rounded_rect(cx, cy, s.cell, s.cell, s.icon_round)
        inner = self._rounded_rect(cx, cy, s.cell * 0.52, s.cell * 0.52,
                                   s.icon_round * 0.55)
        return outer.difference(inner).buffer(0)

    def _glyph_swatch(self, cx, cy):
        """A filled color-swatch circle with a small notch removed at top-right
        (so it reads as a 'swatch', not just a dot)."""
        s = self.s
        disc = self._circle(cx, cy, s.swatch_r)
        # a thin crescent cut to give it a swatch/chip feel
        cut = self._circle(cx + s.swatch_r * 0.62, cy - s.swatch_r * 0.62,
                           s.swatch_r * 0.55)
        return disc.difference(cut).buffer(0)

    def _glyph_type(self, cx, cy):
        """A type 'mark' tile: a rounded tile with a serif 'A' cut out of it."""
        s = self.s
        tile = self._rounded_rect(cx, cy, s.cell, s.cell, s.type_round)
        a = self._letter_A(cx, cy, s.cell * 1.36, s.cell * 1.62)
        return tile.difference(a).buffer(0)

    def _letter_A(self, cx, cy, h, w):
        """A chunky serif-ish capital 'A' polygon centered at (cx, cy)."""
        hh, hw = h / 2.0, w / 2.0
        # outer triangle of the A (apex up = small y), with serif feet
        apex = (cx, cy - hh)
        foot_l = (cx - hw, cy + hh)
        foot_r = (cx + hw, cy + hh)
        outer = Polygon([apex, foot_r, foot_l]).buffer(0)
        # serif feet (small rectangles at the base of each leg)
        serif_h = h * 0.14
        serif_w = w * 0.20
        feet = unary_union([
            box(cx - hw - serif_w * 0.3, cy + hh - serif_h,
                cx - hw + serif_w, cy + hh + serif_h * 0.2),
            box(cx + hw - serif_w, cy + hh - serif_h,
                cx + hw + serif_w * 0.3, cy + hh + serif_h * 0.2),
        ])
        body = unary_union([outer, feet]).buffer(0)
        # inner triangular counter (the hole) and the crossbar gap
        inset = w * 0.30
        counter_apex = (cx, cy - hh + h * 0.30)
        counter_l = (cx - hw + inset, cy + hh - h * 0.06)
        counter_r = (cx + hw - inset, cy + hh - h * 0.06)
        counter = Polygon([counter_apex, counter_r, counter_l]).buffer(0)
        # crossbar: keep a horizontal band of the counter filled
        crossbar = box(cx - hw, cy + h * 0.10, cx + hw, cy + h * 0.10 + h * 0.13)
        counter = counter.difference(crossbar).buffer(0)
        return body.difference(counter).buffer(0)

    def _glyph_doc(self, cx, cy):
        """A document/page with a dog-eared corner and a few text lines."""
        s = self.s
        w, h, f = s.doc_w, s.doc_h, s.doc_fold
        # page outline with a folded top-right corner
        page = Polygon([
            (cx - w, cy - h),
            (cx + w - f, cy - h),
            (cx + w, cy - h + f),
            (cx + w, cy + h),
            (cx - w, cy + h),
        ]).buffer(0)
        page = page.buffer(s.type_round * 0.4, join_style=1).buffer(
            -s.type_round * 0.4, join_style=1)
        # text lines (subtracted so they read as light gaps on the cream page)
        lines = []
        n = s.doc_lines
        # lay lines in the lower ~60% of the page; shorten the last line
        top = cy - h + f + h * 0.18
        step = (cy + h - top - h * 0.18) / max(1, n)
        for i in range(n):
            ly = top + step * (i + 0.5)
            lw = w * (0.62 if i == n - 1 else 0.74)
            lines.append(box(cx - lw, ly - s.doc_line_thick,
                             cx + lw, ly + s.doc_line_thick))
        return page.difference(unary_union(lines)).buffer(0)

    def _glyphs(self):
        s = self.s
        gx = s.glyph_xs
        gy = s.glyph_y
        return [
            ("icon", self._glyph_icon(gx[0], gy)),
            ("swatch", self._glyph_swatch(gx[1], gy)),
            ("type", self._glyph_type(gx[2], gy)),
            ("doc", self._glyph_doc(gx[3], gy)),
        ]

    # ---- transform model -> canvas (square, y-down already; small nudge) ----
    def _full_bounds(self):
        u = unary_union([self.bar_geom, self.strings_geom, self.artifacts_geom])
        return u.bounds

    def _tf(self):
        s = self.s
        S = s.canvas
        minx, miny, maxx, maxy = self._full_bounds()
        span = max(maxx - minx, maxy - miny)
        scale_f = s.fit * S / span
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0 + s.optical_dy
        # model y is already DOWN, so no flip — match SVG/canvas orientation.
        return lambda x, y: (S / 2 + (x - cx) * scale_f, S / 2 + (y - cy) * scale_f)

    def _d(self, g):                                # geometry -> SVG path (marklib)
        return geom_to_path(g, self._tf())

    # ---- emission (via brando marklib) ----
    def _bg_fill(self):
        if self.s.background == "none":
            return None
        return self.s.bg_ink

    def _canvas(self):                              # assemble the marklib Canvas
        s = self.s
        c = Canvas(size=s.canvas, tf=self._tf(), bg_round=s.bg_round)
        bg = self._bg_fill()
        if bg is not None:
            c.add_background(bg)
        grad = (s.cream, s.cream2) if s.gradient else None
        # back-to-front: strings (behind), then the bar, then the artifacts.
        c.add_layer("strings", self.strings_geom, s.cream, gradient=grad)
        c.add_layer("bar", self.bar_geom, s.cream, gradient=grad)
        c.add_layer("artifacts", self.artifacts_geom, s.cream, gradient=grad)
        return c

    def canvas(self):
        return self._canvas()

    def render(self, path):
        self._canvas().render(path)

    def emit(self, base):
        self._canvas().emit(base)                   # bg/strings/bar/artifacts + composite


# The candidate family. Variants differ in background + flat-vs-gradient, so a
# human can pick (flat cream on ink is the classic Godfather read; the gradient
# adds a touch of depth; transparent is for placing on any surface).
VARIANTS = {
    # primary: flat cream marionette on the near-black ink rounded-square
    "inkbg":        Spec(background="ink", gradient=False),
    # subtle cream gradient on ink — a touch of depth
    "inkbg_grad":   Spec(background="ink", gradient=True),
    # transparent (no background) flat cream mark — for placing on any surface
    "transparent":  Spec(background="none", gradient=False),
}

# NOTE: there is no LAYERS constant here any more. There used to be one, annotated
# "for Bazel `outs` declaration" — which is the whole story: it existed only so a
# human could copy it into BUILD.bazel, where a second copy then had to be kept in
# step by hand. The layer list now lives in the brand_svgs call and nowhere else,
# so the two cannot disagree. `emit()` writes whatever layers the Canvas holds.


def main(argv=None):
    e = emit.parse_args(argv, prefix="brando", variants=list(VARIANTS))
    os.makedirs(e.out_dir, exist_ok=True)
    for name in e.variants:
        Godfather(VARIANTS[name]).emit(os.path.join(e.out_dir, f"{e.prefix}_{name}"))
        print(f"emit {e.prefix}_{name} -> {e.out_dir}")


if __name__ == "__main__":
    main()
