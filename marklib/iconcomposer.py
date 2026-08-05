#!/usr/bin/env python3
"""brando marklib iconcomposer — emit Icon Composer ``.icon`` bundles.

Icon Composer (macOS 26, Liquid Glass) writes a directory ``<name>.icon`` with an
``icon.json`` manifest + an ``Assets/`` dir of per-layer SVGs. This module emits
that bundle from a marklib ``Canvas``: each foreground layer becomes an
Assets/<name>.svg + a manifest entry, with the standard Liquid Glass material on
the group. Per-layer fills (incl. a vertical linear-gradient) are passed through.

The schema is brand-neutral; the brand supplies the Canvas (its layers + colors).
"""
from __future__ import annotations

import json
import math
import os
from typing import Optional, Sequence

# The Liquid Glass material (Icon Composer's group-level defaults).
GLASS = {
    "specular": True,
    "shadow": {"kind": "neutral", "opacity": 0.5},
    "translucency": {"enabled": True, "value": 0.5},
}

# Default gradient axis (vertical, top-weighted) for a gradient layer.
GRAD_AXIS = {"start": {"x": 0.5, "y": 0}, "stop": {"x": 0.5, "y": 0.7}}


def ext_srgb(hexstr: str) -> str:
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return "extended-srgb:%.5f,%.5f,%.5f,1.00000" % (r, g, b)


def _bg_fill(bg_hex: str, mode: str) -> dict:
    return {"automatic-gradient": ext_srgb(bg_hex)} if mode == "auto" else {"solid": ext_srgb(bg_hex)}


def _gradient_fill(gradient, default_axis: dict):
    """Colors + orientation for a manifest fill, from EITHER gradient form.

    ``Layer.gradient`` has two shapes: the original ``(top, bottom)`` 2-tuple, and
    the ``{"stops": [...], "angle": deg}`` dict that marklib 0.1.0 added for
    N-stop gradients at any angle. This writer only ever handled the tuple, so a
    0.1.0-style layer raised ``KeyError: 0`` on ``gradient[0]``.

    It went unnoticed for two releases because ``brand_iconcomposer`` has no
    caller anywhere in the fleet -- the one rule nothing exercises is the one rule
    that broke. The angle is honoured rather than dropped, using the same vector
    construction as ``marklib.linear_gradient``, so the .icon bundle and the SVG
    do not disagree about which way the gradient runs.
    """
    if not isinstance(gradient, (dict,)):
        return list(gradient), default_axis

    stops = list(gradient.get("stops") or ())
    colors = [s[1] if isinstance(s, (tuple, list)) else s for s in stops]
    if len(colors) < 2:
        raise ValueError(
            f"iconcomposer: a gradient fill needs at least 2 stops, got {colors!r}"
        )

    if "angle" not in gradient:
        return colors, default_axis
    a = math.radians(float(gradient["angle"]))
    dx, dy = math.cos(a), math.sin(a)
    axis = {
        "start": {"x": 0.5 - dx / 2, "y": 0.5 - dy / 2},
        "stop": {"x": 0.5 + dx / 2, "y": 0.5 + dy / 2},
    }
    return colors, axis


def emit_icon_bundle(out_dir: str, name: str, canvas, *,
                     fill: str = "auto", glass: bool = True,
                     blend_modes: Optional[dict] = None,
                     grad_axis: dict = GRAD_AXIS) -> str:
    """Emit ``<out_dir>/<name>.icon`` from a marklib ``Canvas``.

    Layers are ordered front-to-back in the manifest (Icon Composer's order), so
    we reverse the Canvas's back-to-front layer list. A layer whose ``gradient``
    is set gets a linear-gradient fill on the manifest entry. ``blend_modes`` maps
    layer name -> blend mode (default "normal"). ``fill`` is "auto" (automatic
    gradient bg) or "solid".
    """
    blend_modes = blend_modes or {}
    icon = os.path.join(out_dir, "%s.icon" % name)
    assets = os.path.join(icon, "Assets")
    os.makedirs(assets, exist_ok=True)

    layers = []
    # Icon Composer lists front layer first; Canvas holds back-to-front.
    for layer in reversed(canvas.foreground_layers()):
        img_name = "%s.svg" % layer.name
        canvas.write_layer(os.path.join(assets, img_name), layer)
        entry = {
            "blend-mode": blend_modes.get(layer.name, "normal"),
            "image-name": img_name,
            "name": layer.name,
        }
        if layer.gradient:
            colors, axis = _gradient_fill(layer.gradient, grad_axis)
            entry["fill"] = {
                "linear-gradient": [ext_srgb(c) for c in colors],
                "orientation": axis,
            }
        layers.append(entry)

    group = {"layers": layers}
    if glass:
        group.update(GLASS)
    bg_hex = canvas.bg.fill if canvas.bg is not None else "#000000"
    manifest = {
        "fill": _bg_fill(bg_hex, fill),
        "groups": [group],
        "supported-platforms": {"circles": ["watchOS"], "squares": "shared"},
    }
    with open(os.path.join(icon, "icon.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("icon %s.icon" % name)
    return icon
