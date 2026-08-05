#!/usr/bin/env python3
"""brando template renderer — resolve @TOKEN@ from a skin, not from re-typed hex.

WHAT THIS REPLACES.

brando templated its LaTeX class and mdBook theme with `sed`, driven by colour
arguments the BUILD file passed in by hand. So a brand's palette was authored
once as the canonical `<brand>.textpb` and then AGAIN as `brand_mdbook_theme`
attributes, AGAIN as `brand_latex_class` attributes (in a different notation --
6-hex WITHOUT the leading `#`), and again in the office JSON configs. fastverk's
amber exists five times; the office copy has already drifted to the light-mode
value while the others carry dark.

Colours re-typed in five places are colours that will disagree in five places,
so this reads them from the skin the brand already authored. The `--set` escape
hatch remains for tokens that genuinely are not palette -- a class name, a font
filename -- and for a brand mid-migration.

TOKEN VOCABULARY. Palette roles are addressed by mode, `@DARK_ACCENT@` /
`@LIGHT_BG@`, rather than by a house nickname like `@INK@` or `@CREAM@`. That is
deliberate: `ink` and `cream` are fastverk's words for its own colours, and a
template written in them cannot describe a brand whose background is not ink. The
roles are the contract; the nicknames were the leak.

CLI: render_template.py --template T --out O [--theme_json J] [--mode M]
                        [--set KEY=VALUE]...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Dict, Optional

# Palette roles get `@<MODE>_<ROLE>@`; typography and metrics are mode-independent.
_PALETTE_ROLES = (
    "bg", "surface", "fg", "muted", "border", "accent", "accent_strong",
    "on_accent", "danger", "success", "code_bg", "code_fg", "warning", "info",
)
_TYPOGRAPHY = ("sans", "mono", "display", "heading_tracking")
_TYPOGRAPHY_NUM = ("base_size_px", "heading_weight", "body_weight")
_METRICS = ("radius_px", "unit_px")

_TOKEN_RE = re.compile(r"@([A-Z][A-Z0-9_]*)@")


def tokens_from_theme(
    theme: dict, *, strip_hash: bool = False, mode: Optional[str] = None
) -> Dict[str, str]:
    """Every @TOKEN@ a skin can supply.

    `strip_hash` emits `E0A33E` instead of `#E0A33E`, which is what LaTeX's
    xcolor wants. Carrying that as a flag rather than as a second set of authored
    values is the whole point -- the notation differing is not a reason for the
    palette to be typed twice.

    `mode` additionally exposes that mode's roles UNPREFIXED, so `@BG@` means "the
    background of the mode this artifact is rendered for". A print artifact has
    exactly one mode and reads better for saying `@BG@`; a stylesheet carries both
    and must say `@DARK_BG@` / `@LIGHT_BG@`.
    """
    out: Dict[str, str] = {}

    def put(key: str, value) -> None:
        if value is None or value == "":
            return
        text = str(value)
        if strip_hash and text.startswith("#"):
            text = text[1:]
        out[key] = text

    # NB: `each` rather than `mode` — shadowing the parameter here would leave it
    # bound to "dark" below, so every artifact would silently render dark
    # regardless of what the caller asked for.
    for each in ("light", "dark"):
        palette = theme.get(each) or {}
        for role in _PALETTE_ROLES:
            put("%s_%s" % (each.upper(), role.upper()), palette.get(role))

    typo = theme.get("typography") or {}
    for field in _TYPOGRAPHY:
        put(field.upper(), typo.get(field))
    for field in _TYPOGRAPHY_NUM:
        put(field.upper(), typo.get(field))
    for field in _METRICS:
        put(field.upper(), (theme.get("metrics") or {}).get(field))

    if mode:
        palette = theme.get(mode) or {}
        for role in _PALETTE_ROLES:
            put(role.upper(), palette.get(role))

    put("ID", theme.get("id"))
    put("NAME", theme.get("display_name") or theme.get("id"))
    return out


def render(template: str, tokens: Dict[str, str], *, strict: bool = True) -> str:
    """Substitute @TOKEN@. Unresolved tokens are an error, not a silent passthrough.

    Leaving `@ACCENT@` in a shipped stylesheet is the failure mode `sed` had: it
    substitutes what it matches and says nothing about what it did not, so a
    renamed token surfaces as a literal `@ACCENT@` in the browser rather than as a
    build failure.
    """
    missing = sorted({
        m.group(1) for m in _TOKEN_RE.finditer(template) if m.group(1) not in tokens
    })
    if missing and strict:
        raise SystemExit(
            "render_template: no value for %s.\n"
            "  Supply it from the skin (a palette role, e.g. DARK_ACCENT) or with "
            "--set NAME=VALUE." % ", ".join("@%s@" % m for m in missing)
        )
    return _TOKEN_RE.sub(lambda m: tokens.get(m.group(1), m.group(0)), template)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--theme_json", help="a brand_skin <name>.json")
    ap.add_argument(
        "--mode",
        choices=("light", "dark"),
        help="also expose this mode's roles unprefixed, so @BG@ works in a "
             "single-mode artifact such as a LaTeX class",
    )
    ap.add_argument(
        "--strip_hash",
        action="store_true",
        help="emit colours as bare 6-hex (LaTeX xcolor wants no leading '#')",
    )
    ap.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="a non-palette token, or an override while migrating off explicit colours",
    )
    args = ap.parse_args(argv)

    tokens: Dict[str, str] = {}
    if args.theme_json:
        with open(args.theme_json, encoding="utf-8") as fh:
            tokens.update(tokens_from_theme(
                json.load(fh), strip_hash=args.strip_hash, mode=args.mode
            ))

    # A --set VALUE may itself reference theme tokens, so a caller can say
    # `--set DARK_SIDEBAR=@DARK_BG@` and have it mean "same as the background"
    # without Starlark needing to read the JSON (it cannot). Resolved against the
    # theme tokens only, so one --set cannot depend on another and there is no
    # ordering or cycle to reason about.
    theme_tokens = dict(tokens)
    for pair in args.set:
        if "=" not in pair:
            raise SystemExit(f"render_template: --set wants KEY=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        tokens[key] = render(value, theme_tokens) if "@" in value else value

    with open(args.template, encoding="utf-8") as fh:
        template = fh.read()
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render(template, tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main())
