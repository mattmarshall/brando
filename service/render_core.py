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

    theme.json                 the Theme, as proto3-JSON
    theme.css                  custom properties, via marklib.tokens
    contrast.json              the contrast report, via marklib.palette

That list is shorter than an earlier version of this docstring claimed. It named
`theme.binpb` and the templated mdBook and LaTeX surfaces as well, and
`DERIVABLE_KINDS` never included any of them — a comment describing a service
that did not exist, which is worse than no comment at all.

AND, SINCE 0.6.0, THE MARK — when the spec carries one. The reasoning above is
unchanged and the refusal still stands for a `MarkSpec` that names a
`generator`: running caller-supplied code is not a scoping problem. What changed
is that a `MarkSpec` can now carry a `MarkProgram` instead, which is a closed
vocabulary of primitives, boolean operations and arithmetic over named
parameters — no assignment, no recursion, no unbounded loop. Executing one is
evaluation and it terminates, so the spec finally CONTAINS the drawing rather
than naming it. `unrenderable()` is therefore a question about a spec rather
than a constant lookup.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

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

# Kinds this core can produce ONLY when the spec carries a `MarkProgram`. They
# are listed separately rather than folded into `DERIVABLE_KINDS` because
# whether they are renderable is a property of the SPEC, not of the service: a
# `MarkSpec` that names a generator is still a mark this service cannot draw,
# and saying so remains the right answer.
PROGRAM_KINDS = (
    "ARTIFACT_KIND_MARK_SVG",
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


def has_program(spec: dict) -> bool:
    """Whether this spec carries a mark this service may execute.

    The distinction the whole refusal turns on. A `MarkSpec.generator` is a Bazel
    label naming code in a repo; a `MarkSpec.program` is a closed vocabulary of
    primitives and arithmetic with no assignment, no recursion and no unbounded
    loop. The first is remote code execution and stays refused. The second
    terminates.
    """
    return bool((spec.get("mark") or {}).get("program"))


def render_mark(spec: dict, *, variants=None, canvas: Optional[int] = None,
                prefix: str = "mark") -> Dict[str, bytes]:
    """Execute the spec's MarkProgram into `filename -> bytes`.

    IMPORTED LAZILY, and that is not an optimisation. `marklib.program` needs
    shapely; `theme_css` and `contrast` need nothing but the standard library,
    and they are the paths a caller checking a palette takes. Keeping the
    geometry stack off that path is the same property `marklib/__init__.py`
    defends with PEP 562, for the same reason — it was silently false once, and
    the console found it rather than the tests.
    """
    from marklib import program as _program

    mark = spec.get("mark") or {}
    node = mark.get("program")
    if not node:
        raise ValueError(
            "this spec's mark names a generator rather than carrying a program, "
            "so there is nothing here to execute")
    return _program.emit_bytes(
        node, prefix, variants or _program.variant_names(node),
        theme=spec.get("theme"), canvas=canvas)


def package(spec_json: dict, artifacts: Dict[str, bytes], *,
            brando_version: str = "", spec_binpb: bytes = b"",
            manifest_binpb: bytes = b"") -> bytes:
    """Assemble a real `.brando` from rendered artifacts.

    THE ARCHIVE THE SERVICE WRITES IS THE ARCHIVE THE BUILD WRITES. Blob paths
    come from `tools.pack_brand._blob_path` -- imported, not reimplemented --
    because a second definition of "where does this blob live" is precisely how
    the manifest and the archive end up disagreeing about where an asset is,
    which no consumer could then diagnose. `pack_brand`'s own docstring makes
    that point about its two modes; the same argument applies across drivers.

    Deterministic in the same way too: fixed mtimes and sorted entries, so a
    render of an unchanged brand produces identical bytes and every downstream
    pin stays put.
    """
    import zipfile
    from io import BytesIO

    from tools.pack_brand import _blob_path

    blobs = {_blob_path(b): b for b in artifacts.values()}

    assets = []
    for logical, blob in sorted(artifacts.items()):
        path = _blob_path(blob)
        assets.append({
            "name": logical,
            "path": path,
            "media_type": _MEDIA.get(logical.rsplit(".", 1)[-1], "application/octet-stream"),
            "size_bytes": str(len(blob)),
            "sha256": path.split("/", 1)[1],
        })

    manifest = {
        "spec": spec_json,
        "assets": assets,
        "provenance": {
            "brando_version": brando_version or "service",
            "spec_digest": hashlib.sha256(
                json.dumps(spec_json, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
    }

    buf = BytesIO()
    fixed = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name: str, payload: bytes):
            info = zipfile.ZipInfo(name, fixed)
            info.external_attr = 0o644 << 16
            z.writestr(info, payload)

        # Both encodings, exactly as brand_package writes them: the binpb for
        # anything with a proto runtime, the JSON for rules_brand's repo rule,
        # which runs during loading and has neither.
        if manifest_binpb:
            add("brand.binpb", manifest_binpb)
        add("brand.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
        for name in sorted(blobs):
            add(name, blobs[name])

    return buf.getvalue()


_MEDIA = {
    "css": "text/css",
    "json": "application/json",
    "svg": "image/svg+xml",
    "png": "image/png",
    "binpb": "application/octet-stream",
}


def renderable_kinds(spec: Optional[dict] = None) -> tuple:
    """Everything this core can produce for `spec`.

    Spec-dependent since 0.6.0. It used to be a constant, because a mark was
    never renderable; now it is renderable exactly when the spec carries a
    program, and a constant could not say that.
    """
    if spec is not None and has_program(spec):
        return DERIVABLE_KINDS + PROGRAM_KINDS
    return DERIVABLE_KINDS


def unrenderable(kinds, spec: Optional[dict] = None) -> List[str]:
    """Which requested kinds this core cannot produce for this spec.

    A caller asking for a mark should be TOLD, not quietly handed a package
    missing it — that is the same silent-shortfall the Catalog gate exists to
    prevent, arriving through a different door.

    `spec` is optional so the question "what can you make from a bare Theme"
    still has an answer, and defaults to the strictest one: with no spec in hand
    there is no program, so a mark is unrenderable. Refusing by default is the
    behaviour this function shipped with, and it is the safe direction to be
    wrong in.
    """
    allowed = renderable_kinds(spec)
    return [k for k in kinds if k not in allowed]
