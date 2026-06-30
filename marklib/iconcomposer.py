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
            entry["fill"] = {
                "linear-gradient": [ext_srgb(layer.gradient[0]), ext_srgb(layer.gradient[1])],
                "orientation": grad_axis,
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
