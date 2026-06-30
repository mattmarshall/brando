#!/usr/bin/env python3
"""brando self-brand mark v2 — the GODFATHER marionette, now WITH THE HAND.

v1 (gen_godfather.py) drew the puppeteer's CONTROL BAR + cross strut + four
strings ending in brand-artifact glyphs. It was missing the single most
recognizable Godfather element: the HAND gripping the control bar. v2 adds it.

The mark now reads unmistakably as The Godfather (a play on Marlon Brando): a
bold, confident CREAM HAND grips a horizontal marionette control bar from above
— the back/palm of the hand rests above the bar, four fingers curl DOWN over the
FRONT of the bar and hook back under it, and a thumb wraps the near (left) side.
A thin INK separation outline traces the hand where it crosses the bar so the
over/under "grip" reads at any size. Strings still descend from the bar to small
brand-artifact glyphs — "brando pulls all the strings of your brand":

  * a rounded-square app icon,
  * a filled color swatch (circle),
  * a type "mark" tile (a serif-ish "A" cut from a tile),
  * a document/page with a couple of text lines.

Like v1, ONE Spec drives everything; shapely is the exact CSG (bar, hand, halo,
strings, four artifact glyphs); emission is through ``@brando//marklib`` as
canonical LAYERS (bg / strings / bar / handhalo / hand / artifacts) plus a
composite. Construction is deterministic — reproducible output. The artifact
glyph builders are reused unchanged from gen_godfather (single source of truth).

Geometry lives in a square model space with y DOWN (so "top" is small y, like
SVG). ``_tf`` fits the union of bar+hand+strings+artifacts into ~``fit`` of the
square canvas, centered, with an optional optical nudge. Aesthetic: cream marks
on near-black ink (Godfather palette).

CLI: ``gen_godfather_v2.py <out-dir>`` emits every VARIANT's layered set.
"""
import math
import os
import sys
from dataclasses import dataclass, field

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from marklib import Canvas, geom_to_path

# Reuse v1's artifact-glyph CSG (icon / swatch / type / doc) verbatim so the two
# marks stay a single source of truth for the brand-artifact vocabulary.
from gen_godfather import Godfather as _GodfatherV1
from gen_godfather import Spec as _SpecV1


@dataclass
class Spec:
    # ---- model space ----
    # The mark is laid out around a [-1, 1] box, y DOWN (SVG-like): the hand grips
    # the control bar near the top (small y); the artifacts hang below.
    canvas: int = 1024

    # ---- control bar (the puppeteer's handle the hand grips) ----
    bar_y: float = -0.66          # vertical position of the horizontal bar
    bar_halfw: float = 0.80       # bar half-width
    bar_thick: float = 0.085      # bar half-thickness

    # ---- the HAND gripping the bar (the Godfather recognition cue) ----
    # Palm/back-of-hand block above the bar (a brushy polygon, not a plain rect).
    palm_round: float = 0.06      # palm silhouette softening (buffer out)
    palm_settle: float = 0.02     # ...then buffer back in (keeps it confident)
    finger_half: float = 0.068    # finger half-thickness (rounded capsules)
    finger_tip_taper: float = 0.80  # fingertip is a touch thinner than the knuckle
    knuckle_dy: float = -0.10     # knuckles ride this far above the bar (y-down)
    # Per-finger: (knuckle_x, reach below the bar front, horizontal hook-in at tip).
    # Middle two fingers reach lowest; tips hook back toward the palm = a grip.
    fingers: tuple = (
        (-0.255, 0.26, 0.10),     # index
        (-0.085, 0.34, 0.06),     # middle (longest)
        (0.090, 0.31, 0.02),      # ring
        (0.255, 0.23, -0.02),     # little
    )
    thumb_half: float = 0.082     # thumb half-thickness
    halo_w: float = 0.013         # ink separation outline thickness around the hand

    # ---- strings ----
    # Strings attach on the bar and drop to the artifacts. The outer two fall
    # cleanly from the bar ends; the inner two emerge from beneath the fingertips
    # (telling the "the hand pulls the strings" story).
    string_thick: float = 0.010   # string half-width (very thin)
    attach_xs: tuple = (-0.66, -0.30, 0.30, 0.66)
    glyph_xs: tuple = (-0.66, -0.24, 0.24, 0.66)
    glyph_y: float = 0.66         # vertical center of the artifact row
    string_top_gap: float = 0.02  # start strings just below the bar bottom edge

    # ---- artifact glyphs (reused from v1; sizes mirror v1 defaults) ----
    cell: float = 0.165
    icon_round: float = 0.052
    swatch_r: float = 0.150
    type_round: float = 0.040
    doc_w: float = 0.130
    doc_h: float = 0.165
    doc_fold: float = 0.072
    doc_lines: int = 3
    doc_line_thick: float = 0.013
    bead_r: float = 0.017

    # ---- colors (Godfather palette: cream on ink) ----
    cream: str = "#ECE7DA"
    cream2: str = "#D8D1BF"
    ink: str = "#15161A"          # near-black rounded-square bg (Godfather mood)
    bg_ink: str = "#15161A"

    # ---- toggles ----
    gradient: bool = False        # subtle vertical cream gradient on the marks
    background: str = "ink"       # ink | none (transparent)
    bg_round: float = 0.22        # rounded-square corner radius (frac of canvas)
    fit: float = 0.86             # fraction of the canvas the mark fills
    optical_dy: float = 0.0       # optical vertical nudge in model units


class GodfatherV2:
    """Deterministic shapely construction + marklib emission of the hand-gripping
    marionette. The hand is the headline; bar + strings + artifacts carry the
    brando twist."""

    SEG = 96  # polygon segments per circle (smooth at 1024px)

    def __init__(self, s: Spec):
        self.s = s
        self.bar_geom = self._bar()
        self.hand_geom = self._hand()
        # the ink separation outline traces the hand but is masked to the bar
        # region (we only need the over/under read where the hand meets the bar).
        self.halo_geom = self._halo()
        self.glyphs = self._glyphs()                 # list of (kind, geom)
        self.artifacts_geom = unary_union([g for _, g in self.glyphs])
        self.strings_geom = self._strings()          # strings + beads

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
        r = max(0.0, min(r, hw, hh))
        if r <= 0:
            return box(cx - hw, cy - hh, cx + hw, cy + hh)
        core = box(cx - hw + r, cy - hh + r, cx + hw - r, cy + hh - r)
        return core.buffer(r, join_style=1, quad_segs=24)

    @staticmethod
    def _capsule(pts, half, taper=1.0):
        """A thin rounded poly-capsule through ``pts`` (rounded caps + joins)."""
        return LineString(pts).buffer(half * taper, cap_style=1, join_style=1,
                                      quad_segs=18)

    # ---- the control bar ----
    def _bar(self):
        s = self.s
        return self._rounded_rect(0.0, s.bar_y, s.bar_halfw, s.bar_thick,
                                  s.bar_thick)

    # ---- the hand: palm above the bar, fingers curling over the front, thumb ----
    def _finger(self, base_x, knuckle_y, reach, curl_in):
        """One finger: from the knuckle (above the bar) down over the bar FRONT,
        hooking back inward beneath it (``curl_in``) — a clear gripping curl."""
        s = self.s
        half = s.finger_half
        bar_front = s.bar_y + s.bar_thick
        p0 = (base_x, knuckle_y)
        p1 = (base_x + curl_in * 0.10, bar_front - 0.02)          # crossing the bar
        p2 = (base_x + curl_in * 0.45, bar_front + reach * 0.55)  # below the bar
        p3 = (base_x + curl_in, bar_front + reach)                # hooked tip
        body = self._capsule([p0, p1, p2], half)
        tip = self._capsule([p1, p2, p3], half, taper=s.finger_tip_taper)
        knuckle = self._circle(base_x, knuckle_y, half * 1.04)
        return unary_union([knuckle, body, tip])

    def _hand(self):
        s = self.s
        by = s.bar_y
        parts = []
        # palm / back of the hand: a confident, slightly angular block above the
        # bar (brushy polygon, then softened) — not a sterile rounded rectangle.
        palm_pts = [
            (-0.40, by - 0.02),     # lower-left (meets bar, near the thumb)
            (-0.44, by - 0.30),     # left side rising
            (-0.30, by - 0.50),     # upper-left shoulder
            (0.10, by - 0.54),      # top ridge
            (0.40, by - 0.44),      # upper-right (toward the little finger)
            (0.46, by - 0.16),      # right side down to the first knuckle
            (0.40, by + 0.02),      # lower-right (over the bar)
        ]
        palm = (Polygon(palm_pts)
                .buffer(s.palm_round, join_style=1)
                .buffer(-s.palm_settle, join_style=1))
        parts.append(palm)
        # four fingers curling down over the FRONT of the bar
        knuckle_y = by + s.knuckle_dy
        for base_x, reach, curl in s.fingers:
            parts.append(self._finger(base_x, knuckle_y, reach, curl))
        # thumb: near (left/front) side, a thick digit angling down across the
        # left end of the bar with a rounded tip — the near-side grip.
        bar_front = by + s.bar_thick
        thumb = unary_union([
            self._capsule([(-0.30, by - 0.16),
                           (-0.47, by - 0.02),
                           (-0.54, bar_front + 0.06)], s.thumb_half),
            self._circle(-0.54, bar_front + 0.06, s.thumb_half * 0.98),
        ])
        parts.append(thumb)
        return unary_union(parts).buffer(0)

    def _halo(self):
        """A thin ink ring around the hand, clipped to a band spanning the bar, so
        the grip's over/under reads where the fingers cross the bar (and nowhere
        the hand simply sits on the ink background)."""
        s = self.s
        ring = self.hand_geom.buffer(s.halo_w).difference(self.hand_geom)
        # only keep the part of the ring near the bar (a generous vertical band).
        band = box(-s.bar_halfw - 0.1, s.bar_y - s.bar_thick - 0.02,
                   s.bar_halfw + 0.1, s.bar_y + s.bar_thick + 0.22)
        return ring.intersection(band).buffer(0)

    # ---- the hanging strings + the bead where each meets its glyph ----
    def _strings(self):
        s = self.s
        bar_bottom = s.bar_y + s.bar_thick
        parts = []
        for ax, gx in zip(s.attach_xs, s.glyph_xs):
            y_top = bar_bottom + s.string_top_gap
            y_bot = s.glyph_y - s.cell - s.bead_r * 0.4
            parts.append(self._capsule([(ax, y_top), (gx, y_bot)], s.string_thick))
            parts.append(self._circle(gx, y_bot, s.bead_r))
        return unary_union(parts).buffer(0)

    # ---- the artifact glyphs (reuse v1 builders for a single source of truth) ----
    def _glyphs(self):
        s = self.s
        # build a v1 Godfather with our glyph placement/sizes, then borrow its
        # per-glyph CSG (icon / swatch / type / doc) directly.
        v1 = _GodfatherV1(_SpecV1(
            glyph_xs=s.glyph_xs, glyph_y=s.glyph_y, cell=s.cell,
            icon_round=s.icon_round, swatch_r=s.swatch_r, type_round=s.type_round,
            doc_w=s.doc_w, doc_h=s.doc_h, doc_fold=s.doc_fold,
            doc_lines=s.doc_lines, doc_line_thick=s.doc_line_thick,
        ))
        return v1.glyphs

    # ---- transform model -> canvas (square, y-down already; small nudge) ----
    def _full_bounds(self):
        u = unary_union([self.bar_geom, self.hand_geom, self.strings_geom,
                         self.artifacts_geom])
        return u.bounds

    def _tf(self):
        s = self.s
        S = s.canvas
        minx, miny, maxx, maxy = self._full_bounds()
        span = max(maxx - minx, maxy - miny)
        scale_f = s.fit * S / span
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0 + s.optical_dy
        return lambda x, y: (S / 2 + (x - cx) * scale_f, S / 2 + (y - cy) * scale_f)

    def _d(self, g):
        return geom_to_path(g, self._tf())

    # ---- emission (via brando marklib) ----
    def _bg_fill(self):
        if self.s.background == "none":
            return None
        return self.s.bg_ink

    def _canvas(self):
        s = self.s
        c = Canvas(size=s.canvas, tf=self._tf(), bg_round=s.bg_round)
        bg = self._bg_fill()
        if bg is not None:
            c.add_background(bg)
        grad = (s.cream, s.cream2) if s.gradient else None
        # back-to-front: strings (behind), bar, the ink hand-halo, the cream hand,
        # then the artifacts. The halo is a composite-only separation outline; on
        # a transparent background it is filled with the ink so the grip still
        # reads when the mark is placed on a dark surface.
        c.add_layer("strings", self.strings_geom, s.cream, gradient=grad)
        c.add_layer("bar", self.bar_geom, s.cream, gradient=grad)
        c.add_layer("handhalo", self.halo_geom, s.bg_ink, emit_file=False)
        c.add_layer("hand", self.hand_geom, s.cream, gradient=grad)
        c.add_layer("artifacts", self.artifacts_geom, s.cream, gradient=grad)
        return c

    def canvas(self):
        return self._canvas()

    def render(self, path):
        self._canvas().render(path)

    def emit(self, base):
        self._canvas().emit(base)


# The candidate family (mirrors v1): variants differ in background + flat vs.
# gradient so a human can pick. Flat cream on ink is the classic Godfather read.
VARIANTS = {
    "inkbg":       Spec(background="ink", gradient=False),
    "inkbg_grad":  Spec(background="ink", gradient=True),
    "transparent": Spec(background="none", gradient=False),
}

# Every file-backed layer emit() can produce (for Bazel `outs` declaration). The
# composite-only handhalo is intentionally absent (emit_file=False).
LAYERS = ["svg", "bg.svg", "strings.svg", "bar.svg", "hand.svg", "artifacts.svg"]


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, spec in VARIANTS.items():
        GodfatherV2(spec).emit(os.path.join(out_dir, f"brando_v2_{name}"))
        print(f"emit brando_v2_{name} -> {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
