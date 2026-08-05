#!/usr/bin/env python3
"""The render core — what `RenderService` runs, and what the Bazel rules run.

ONE LIBRARY, TWO DRIVERS. This is the seam that claim rests on. Every function
here is a thin arrangement over `marklib`, and the Bazel rules call the same
`marklib` entry points with the same arguments. `//service:conformance_test`
compares the two outputs byte for byte, which is what keeps the claim honest —
without it, "the service runs the same code" is a comment.

WHAT A SERVICE CAN RENDER, AND WHAT IT CANNOT. This is the scoping decision of
the whole phase and it is worth stating plainly rather than discovering later.

A brand's MARK is brand-specific geometry: `gen_mark.py` is Python that draws a
portico, or a turnstile, or a marionette. A service handed an arbitrary BrandSpec
cannot produce one, because the spec does not contain the drawing — it names a
generator that lives in a repo. Executing a caller-supplied generator is not a
scoping problem, it is remote code execution.

So `RenderService` renders exactly what is DERIVABLE FROM THE SPEC:

    theme.json / theme.binpb   the Theme, in both wire forms
    theme.css                  custom properties, via marklib.tokens
    the contrast report        via marklib.palette
    the templated surfaces     mdBook theme, LaTeX class

and marks arrive as INPUTS, produced by whoever owns the geometry. That is not a
lesser service: the derivable set is what changes when a palette changes, which
is what a hosted renderer is for. A mark changes when someone edits geometry, and
that already has a home — a build.
"""
from __future__ import annotations

import json
from typing import Dict, List

from marklib import palette as _palette
from marklib import tokens as _tokens

# The artifact kinds this core can produce from a spec alone. Named here rather
# than inferred so a caller can be told what it will get BEFORE a render, and so
# that adding a kind is a deliberate edit.
DERIVABLE_KINDS = (
    "ARTIFACT_KIND_THEME_JSON",
    "ARTIFACT_KIND_THEME_CSS",
    "ARTIFACT_KIND_CONTRAST_MATRIX",
)


def theme_css(theme: dict, *, prefix: str = "brand", selector: str = ":root") -> str:
    """The brand's stylesheet.

    Delegates rather than reimplements, and the delegation IS the contract:
    `brand_css` shells out to `marklib/tokens.py` as a binary, this calls the
    same function in-process, and the conformance test asserts the two produce
    identical bytes. A second projection here — even a correct one — would make
    that test pass by coincidence rather than by construction.
    """
    return _tokens.to_css_vars(theme, prefix=prefix, selector=selector)


def contrast(theme: dict) -> List[dict]:
    """WCAG findings, as plain dicts ready for `ContrastFinding`.

    `marklib.palette` returns its own `Failure` objects; converting here keeps
    the proto shape out of marklib, which is stdlib-only by design and must stay
    importable in a build with no protobuf runtime.
    """
    return [
        {
            "key": f.key,
            "mode": f.mode,
            "foreground_role": f.fg_role,
            "background_role": f.bg_role,
            "foreground": f.fg,
            "background": f.bg,
            "ratio": round(f.ratio, 2),
            "minimum": f.minimum,
            "severity": f.severity,
            # `what` is marklib's plain-language reason -- "border as an operable
            # boundary (WCAG 1.4.11)" -- and it is the field a human reads. It
            # travels with the finding rather than being re-derived from the role
            # names, which is how two surfaces end up explaining one number
            # differently.
            "what": f.what,
        }
        for f in _palette.check_theme(theme)
    ]


def render(theme: dict, *, kinds=None) -> Dict[str, bytes]:
    """Produce every requested derivable artifact.

    Returns logical name -> bytes, the same shape `brand_package` assembles, so
    a rendered result and a built one can be compared directly.
    """
    wanted = set(kinds or DERIVABLE_KINDS)
    out: Dict[str, bytes] = {}

    if "ARTIFACT_KIND_THEME_JSON" in wanted:
        # sort_keys=False: the Theme's field order is the proto's, and reordering
        # it would make a diff between two renders unreadable for no gain.
        out["theme.json"] = (json.dumps(theme, indent=2) + "\n").encode("utf-8")

    if "ARTIFACT_KIND_THEME_CSS" in wanted:
        out["theme.css"] = theme_css(theme).encode("utf-8")

    if "ARTIFACT_KIND_CONTRAST_MATRIX" in wanted:
        findings = contrast(theme)
        out["contrast.json"] = (
            json.dumps({"findings": findings}, indent=2) + "\n"
        ).encode("utf-8")

    return out


def unrenderable(kinds) -> List[str]:
    """Which requested kinds this core cannot produce.

    A caller asking for a mark should be TOLD, not quietly handed a package
    missing it — that is the same silent-shortfall the Catalog gate exists to
    prevent, arriving through a different door.
    """
    return [k for k in kinds if k not in DERIVABLE_KINDS]
