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

from typing import Optional

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


def paste_geom(img, size, tf, geom, fill_top, fill_bottom=None,
               gradient=False, opacity=255):
    """Paint ``geom`` onto ``img`` through its mask. With ``gradient`` and a
    ``fill_bottom``, paint a vertical gradient spanning the geometry's bbox;
    otherwise a solid ``fill_top``. ``opacity`` (0..255) scales the mask."""
    shape_polys = polys(geom)
    if not shape_polys:
        return
    m = mask(size, tf, shape_polys)
    if opacity != 255:
        m = m.point(lambda v: int(v * opacity / 255))
    if gradient and fill_bottom:
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
        grad = bool(layer.gradient)
        top = layer.gradient[0] if grad else layer.fill
        bot = layer.gradient[1] if grad else None
        paste_geom(img, big, canvas.tf, layer.geom, top, bot,
                   gradient=grad, opacity=int(layer.opacity * 255))
    if supersample > 1:
        out = big // supersample
        return img.resize((out, out), Image.LANCZOS)
    return img
