#!/usr/bin/env python3
"""brando marklib raster — hermetic Pillow rasterization of mark layers.

The reusable Pillow plumbing shared by every brand's rasterizer: build an L mask
from shapely polygons (exterior filled, holes punched), paint a solid or a
vertical-gradient fill through that mask, and composite the standard
background / shape layers. A brand calls these helpers (or the high-level
``rasterize_canvas``) from its own ``raster_<mark>.py`` so it controls per-size
re-construction and supersampling.

No system rsvg/sips/iconutil — pure Pillow, so it is hermetic under Bazel.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PIL import Image, ImageColor, ImageDraw


def polys(geom):
    """shapely geometry -> [(exterior_pts, [hole_pts, ...]), ...]."""
    if geom is None or geom.is_empty:
        return []
    geoms = geom.geoms if geom.geom_type in ("MultiPolygon", "GeometryCollection") else [geom]
    return [(list(p.exterior.coords), [list(r.coords) for r in p.interiors])
            for p in geoms if p.geom_type == "Polygon"]


def mask(size, tf, shape_polys):
    """L mask at ``size`` px: exterior=255, holes=0, under transform ``tf``."""
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    for ext, holes in shape_polys:
        d.polygon([tf(x, y) for x, y in ext], fill=255)
        for h in holes:
            d.polygon([tf(x, y) for x, y in h], fill=0)
    return m


def vgrad(size, top, bottom, y0, y1):
    """A ``size``x``size`` RGBA vertical gradient image: ``top`` color at pixel
    row ``y0`` -> ``bottom`` color at pixel row ``y1`` (clamped outside)."""
    t, b = ImageColor.getrgb(top), ImageColor.getrgb(bottom)
    span = max(1.0, y1 - y0)
    col = Image.new("RGBA", (1, size))
    for y in range(size):
        f = min(1.0, max(0.0, (y - y0) / span))
        col.putpixel((0, y), tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(3)) + (255,))
    return col.resize((size, size))


def _rgb(c):
    return ImageColor.getrgb(c)


def _norm_stops(stops):
    """[(offset, rgb), ...] from a flat color list (even spacing) or pairs."""
    stops = list(stops)
    if stops and isinstance(stops[0], (tuple, list)) and len(stops[0]) == 2:
        return [(float(o), _rgb(c)) for o, c in stops]
    n = len(stops)
    return [(i / (n - 1) if n > 1 else 0.0, _rgb(c)) for i, c in enumerate(stops)]


def lgrad(size, tf, geom, stops, angle_deg):
    """A ``size``x``size`` RGBA image of an N-stop linear gradient at
    ``angle_deg``, laid over ``geom``'s bounding box exactly as the SVG's
    objectBoundingBox ``linear_gradient`` (y runs downward in pixel space)."""
    xs, ys, xe, ye = geom.bounds
    corners = [tf(xs, ys), tf(xe, ys), tf(xs, ye), tf(xe, ye)]
    minx = min(c[0] for c in corners); maxx = max(c[0] for c in corners)
    miny = min(c[1] for c in corners); maxy = max(c[1] for c in corners)
    bw, bh = maxx - minx, maxy - miny
    a = math.radians(angle_deg); dx, dy = math.cos(a), math.sin(a)
    sx, sy = minx + (0.5 - dx / 2) * bw, miny + (0.5 - dy / 2) * bh
    ex, ey = minx + (0.5 + dx / 2) * bw, miny + (0.5 + dy / 2) * bh
    grid = np.arange(size)
    X, Y = np.meshgrid(grid, grid)
    vx, vy = ex - sx, ey - sy
    t = np.clip(((X - sx) * vx + (Y - sy) * vy) / max(1e-6, vx * vx + vy * vy), 0.0, 1.0)
    norm = _norm_stops(stops)
    out = np.zeros((size, size, 3))
    for (o0, c0), (o1, c1) in zip(norm, norm[1:]):
        seg = (t >= o0) & (t <= o1) if o1 > o0 else (t == o0)
        span = max(1e-6, o1 - o0)
        f = np.clip((t[seg] - o0) / span, 0.0, 1.0)
        a0 = np.array(c0, float); a1 = np.array(c1, float)
        out[seg] = a0 * (1 - f)[:, None] + a1 * f[:, None]
    rgba = np.dstack([out.astype("uint8"), np.full((size, size), 255, "uint8")])
    return Image.fromarray(rgba, "RGBA")


def paste_geom(img, size, tf, geom, fill_top, fill_bottom=None,
               gradient=False, opacity=255, stops=None, angle_deg=90.0):
    """Paint ``geom`` onto ``img`` through its mask. With ``stops`` (a color list
    or ``(offset,color)`` pairs), paint an N-stop gradient at ``angle_deg`` over
    the geometry's bbox; else with ``gradient`` + ``fill_bottom``, a vertical
    2-stop gradient; else a solid ``fill_top``. ``opacity`` (0..255) scales the
    mask."""
    shape_polys = polys(geom)
    if not shape_polys:
        return
    m = mask(size, tf, shape_polys)
    if opacity != 255:
        m = m.point(lambda v: int(v * opacity / 255))
    if stops is not None:
        img.paste(lgrad(size, tf, geom, stops, angle_deg), (0, 0), m)
    elif gradient and fill_bottom:
        _, miny, _, maxy = geom.bounds
        # Orientation-independent: ``fill_top`` goes to the smaller pixel row
        # (visual top), ``fill_bottom`` to the larger one, regardless of whether
        # ``tf`` is y-up (mark) or y-down (e.g. an organic mark).
        py0, py1 = tf(0, miny)[1], tf(0, maxy)[1]
        top_px, bot_px = (py0, py1) if py0 <= py1 else (py1, py0)
        layer = vgrad(size, fill_top, fill_bottom, top_px, bot_px)
        img.paste(layer, (0, 0), m)
    else:
        img.paste(fill_top, (0, 0), m)


def background_rect(img, size, fill, round_frac):
    """Draw a rounded-square background filling the image."""
    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(round_frac * size), fill=fill)


def rasterize_canvas(canvas, supersample: int = 1):
    """Rasterize a marklib ``Canvas`` to an RGBA PIL image at ``canvas.size``.

    Renders the background (if any) then each shape layer back-to-front, honoring
    per-layer gradient/opacity. ``supersample`` renders at NxN and downsamples
    (LANCZOS) for antialiasing — Pillow's polygon fill is hard-edged.

    NOTE: ``canvas.tf`` must already map to the SUPERSAMPLED canvas size. Most
    brands instead rebuild their Spec at ``size*supersample`` and pass that
    Canvas in; this helper just composites whatever it is handed.
    """
    big = canvas.size
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    if canvas.bg is not None:
        background_rect(img, big, canvas.bg.fill, canvas.bg_round)
    for layer in canvas.layers:
        g = layer.gradient
        if isinstance(g, dict):       # N-stop, any angle
            paste_geom(img, big, canvas.tf, layer.geom, layer.fill,
                       stops=g["stops"], angle_deg=g.get("angle", 90.0),
                       opacity=int(layer.opacity * 255))
        else:                         # legacy (top, bottom) vertical, or solid
            top = g[0] if g else layer.fill
            bot = g[1] if g else None
            paste_geom(img, big, canvas.tf, layer.geom, top, bot,
                       gradient=bool(g), opacity=int(layer.opacity * 255))
    if supersample > 1:
        out = big // supersample
        return img.resize((out, out), Image.LANCZOS)
    return img
