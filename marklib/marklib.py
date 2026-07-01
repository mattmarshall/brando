#!/usr/bin/env python3
"""brando marklib — the reusable mark-authoring library.

A brand's own ``gen_<mark>.py`` builds its geometry with shapely (exact CSG) and
emits it through THIS library, so every brando brand shares one emission
convention: canonical LAYERS (a rounded-square background + one transparent-bg
SVG per shape) plus a composite, which is exactly what Icon Composer and the
rasterizer consume.

What's reusable (here) vs brand-specific (in the brand's gen_<mark>.py):

  * REUSABLE (here): the shapely-geometry -> SVG path serialization, the
    rounded-square background, the per-layer SVG writer, the vertical
    linear-gradient helper, and the ``Canvas``/``Layer`` model that ties a
    transform + a set of layers into the standard ``emit()`` outputs.
  * BRAND-SPECIFIC (the brand's file): the Spec dataclass, the CSG that builds
    the shapes, the palette, and the model->canvas transform.

Nothing here is fastverk- or tomato-specific; it is pure plumbing on top of
shapely + svgwrite.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

import svgwrite

# A model->canvas transform: (model_x, model_y) -> (px_x, px_y).
Transform = Callable[[float, float], tuple]


def geom_to_path(geom, tf: Transform) -> str:
    """Serialize a shapely geometry to an SVG path ``d`` string under ``tf``.

    Handles Polygon / MultiPolygon / GeometryCollection; emits the exterior and
    every interior ring as closed subpaths (use with ``fill-rule="evenodd"`` so
    holes punch through). Coordinates are formatted to 2 decimals.
    """
    if geom is None or geom.is_empty:
        return ""
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        polys = [g for g in geom.geoms if g.geom_type == "Polygon"]
    else:
        polys = [geom]
    out = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            out.append(
                "M " + " L ".join(
                    f"{a:.2f},{b:.2f}" for a, b in (tf(x, y) for x, y in ring.coords)
                ) + " Z"
            )
    return " ".join(out)


def vertical_gradient(d: "svgwrite.Drawing", gid: str, top: str, bottom: str,
                      y0: float = 0.0, y1: float = 1.0) -> str:
    """Define a vertical linear gradient (objectBoundingBox by default) and
    return a ``url(#gid)`` fill reference. ``y0``/``y1`` are gradient-vector
    endpoints in the drawing's gradient coordinate space (0..1 by default)."""
    g = d.linearGradient(start=(0, y0), end=(0, y1), id=gid)
    g.add_stop_color(0, top)
    g.add_stop_color(1, bottom)
    d.defs.add(g)
    return f"url(#{gid})"


def _norm_stops(stops) -> "list":
    """Normalize ``stops`` to ``[(offset, color), ...]``. Accepts a flat list of
    color strings (spaced evenly across 0..1) or a list of ``(offset, color)``."""
    stops = list(stops)
    if stops and isinstance(stops[0], (tuple, list)):
        return [(float(o), c) for o, c in stops]
    n = len(stops)
    return [(i / (n - 1) if n > 1 else 0.0, c) for i, c in enumerate(stops)]


def linear_gradient(d: "svgwrite.Drawing", gid: str, stops,
                    angle_deg: float = 90.0) -> str:
    """Define an N-stop linear gradient at ``angle_deg`` (objectBoundingBox) and
    return a ``url(#gid)`` fill reference.

    ``stops`` is a flat list of colors (even spacing) or ``(offset, color)``
    pairs. ``angle_deg`` is the gradient-vector direction in the SVG frame (x
    right, y down): ``90`` = top->bottom (matches ``vertical_gradient``), ``0`` =
    left->right, ``55`` = a top-left->bottom-right diagonal. The vector is
    centered on the bounding box, so any angle stays within 0..1 bbox space."""
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    g = d.linearGradient(start=(0.5 - dx / 2, 0.5 - dy / 2),
                         end=(0.5 + dx / 2, 0.5 + dy / 2), id=gid)
    for off, col in _norm_stops(stops):
        g.add_stop_color(off, col)
    d.defs.add(g)
    return f"url(#{gid})"


def rounded_square(d: "svgwrite.Drawing", size: int, fill: str, radius_frac: float):
    """Add a full-canvas rounded-square rect (the standard brand background)."""
    r = radius_frac * size
    d.add(d.rect(insert=(0, 0), size=(size, size), rx=r, ry=r, fill=fill))


@dataclass
class Layer:
    """One named, transparent-background shape layer.

    ``geom`` is a shapely geometry; ``fill`` is the solid color used for the flat
    per-layer SVG and as the default fill in a composite. ``gradient`` optionally
    renders the shape as a gradient in the composite (and the rasterizer): either
    a legacy ``(top, bottom)`` 2-tuple (vertical), or a dict
    ``{"stops": [...], "angle": deg}`` for an N-stop gradient at any angle (see
    ``linear_gradient``). ``blend`` / ``name`` carry through to the Icon Composer
    manifest. ``opacity`` (0..1) is used for soft overlays such as a specular
    highlight.
    """
    name: str
    geom: object
    fill: str
    # (top, bottom) vertical 2-stop, or {"stops": [...], "angle": deg}, or None
    gradient: Optional[object] = None
    blend: str = "normal"
    opacity: float = 1.0
    # If True, this layer is the background rounded-square (rendered as a rect,
    # not a shape path) and is excluded from the foreground/Icon-Composer layers.
    is_background: bool = False
    # If False, the layer is composite-only (drawn in render(), but NOT written as
    # its own <base>.<name>.svg by emit(), nor exposed as an Icon Composer layer).
    # Use for overlays like a specular highlight that have no standalone asset.
    emit_file: bool = True


@dataclass
class Canvas:
    """A square canvas + a model->canvas transform + ordered layers.

    A brand builds one ``Canvas`` per variant: it adds an optional background
    layer (``add_background``) and then its shape layers BACK-TO-FRONT, then
    calls ``emit(base)`` / ``render(path)``. The transform maps the brand's model
    space to pixels.
    """
    size: int
    tf: Transform
    bg: Optional[Layer] = None
    layers: list = field(default_factory=list)
    bg_round: float = 0.20

    # ---- assembly ----
    def add_background(self, fill: str, round_frac: Optional[float] = None) -> "Canvas":
        self.bg = Layer(name="bg", geom=None, fill=fill, is_background=True)
        if round_frac is not None:
            self.bg_round = round_frac
        return self

    def add_layer(self, name: str, geom, fill: str, gradient: Optional[tuple] = None,
                  blend: str = "normal", opacity: float = 1.0,
                  emit_file: bool = True) -> "Canvas":
        if geom is not None and not geom.is_empty:
            self.layers.append(Layer(name=name, geom=geom, fill=fill,
                                     gradient=gradient, blend=blend, opacity=opacity,
                                     emit_file=emit_file))
        return self

    # ---- emission ----
    def _drawing(self, path: str) -> "svgwrite.Drawing":
        S = self.size
        return svgwrite.Drawing(path, size=(S, S), viewBox=f"0 0 {S} {S}")

    def _add_shape(self, d, layer: Layer):
        fill = layer.fill
        if layer.gradient:
            g = layer.gradient
            if isinstance(g, dict):   # N-stop, any angle
                fill = linear_gradient(d, f"{layer.name}grad", g["stops"],
                                       g.get("angle", 90.0))
            else:                     # legacy (top, bottom) vertical 2-stop
                fill = vertical_gradient(d, f"{layer.name}grad", g[0], g[1])
        path = d.add(d.path(d=geom_to_path(layer.geom, self.tf), fill=fill))
        path.update({"fill-rule": "evenodd"})
        if layer.opacity != 1.0:
            path.update({"opacity": layer.opacity})

    def render(self, path: str):
        """Write the composite SVG: background, then layers back-to-front."""
        d = self._drawing(path)
        if self.bg is not None:
            rounded_square(d, self.size, self.bg.fill, self.bg_round)
        for layer in self.layers:
            self._add_shape(d, layer)
        d.save()

    def write_layer(self, path: str, layer: Layer):
        """Write one transparent-background single-shape SVG (flat fill)."""
        d = self._drawing(path)
        self._add_shape(d, Layer(name=layer.name, geom=layer.geom, fill=layer.fill))
        d.save()

    def write_background(self, path: str):
        d = self._drawing(path)
        rounded_square(d, self.size, self.bg.fill, self.bg_round)
        d.save()

    def emit(self, base: str):
        """Canonical layered output: ``<base>.bg.svg`` (if any), one
        ``<base>.<name>.svg`` per file-backed shape layer, and the composite
        ``<base>.svg`` — exactly the set Icon Composer and the rasterizer expect.
        Composite-only layers (``emit_file=False``, e.g. a highlight) are drawn in
        the composite but get no standalone file."""
        if self.bg is not None:
            self.write_background(base + ".bg.svg")
        for layer in self.layers:
            if layer.emit_file:
                self.write_layer(f"{base}.{layer.name}.svg", layer)
        self.render(base + ".svg")

    # ---- foreground (non-background) layers with standalone assets, back-to-front ----
    def foreground_layers(self) -> list:
        return [layer for layer in self.layers if layer.emit_file]
