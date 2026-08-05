#!/usr/bin/env python3
"""brando console — a browsable catalog of every brand in the fleet.

This is the Phase 4 seed, built against what exists today. The plan's console
reads `.brando` archives over a gRPC `BrandService`; neither exists yet, so this
reads the artifact that does: the `<brand>.json` each `brand_skin` already emits.
When the services land, the data source swaps and the page does not.

It dogfoods deliberately. The per-brand CSS comes from `marklib.tokens`, the same
projection that renders every brand's mdBook theme, and the contrast report comes
from `marklib.palette`, the same gate that runs in CI. If either is wrong, the
console is visibly wrong — which is the point of a tool looking at itself.

And the console WEARS the brand you select: picking a brand rewrites the page's
own custom properties from that skin. A brand tool whose chrome ignores the brands
it manages is not demonstrating much.

CLI: build_console.py --skin NAME=PATH [--skin ...] [--mark NAME=PATH] --out FILE
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marklib import palette as mpalette  # noqa: E402
from marklib import tokens as mtokens  # noqa: E402

ROLES = mpalette.CONTRAST_RULES


def _swatch(role: str, value: str) -> str:
    return (
        f'<div class="sw"><i style="background:{html.escape(value)}"></i>'
        f'<b>{html.escape(role)}</b><code>{html.escape(value)}</code></div>'
    )


def _palette_block(title: str, palette: dict) -> str:
    if not palette:
        return ""
    rows = "".join(_swatch(k, v) for k, v in palette.items())
    return f'<section><h4>{html.escape(title)}</h4><div class="sws">{rows}</div></section>'


def _contrast_block(theme: dict) -> str:
    found = mpalette.check_theme(theme)
    errs = [f for f in found if f.severity == "error"]
    warns = [f for f in found if f.severity != "error"]
    if not found:
        return '<p class="ok">No contrast failures.</p>'
    items = "".join(
        f'<li class="{f.severity}"><span>{html.escape(f.key)}</span> '
        f'{f.ratio:.2f}:1 <em>needs {f.minimum}</em> — {html.escape(f.what)}</li>'
        for f in errs + warns
    )
    return (
        f'<p class="{"bad" if errs else "warnish"}">{len(errs)} unreadable, '
        f"{len(warns)} to review.</p><ul class=\"contrast\">{items}</ul>"
    )


def _typography_block(theme: dict) -> str:
    typo = theme.get("typography") or {}
    metrics = theme.get("metrics") or {}
    if not typo and not metrics:
        return ""
    rows = []
    for key in ("sans", "display", "mono"):
        if typo.get(key):
            rows.append(
                f'<div class="type-row"><b>{key}</b>'
                f'<span style="font-family:{html.escape(typo[key])}">'
                f"The quick brown fox — 0123456789</span>"
                f"<code>{html.escape(typo[key])}</code></div>"
            )
    facts = []
    for key in ("base_size_px", "heading_weight", "body_weight", "heading_tracking"):
        if typo.get(key) not in (None, ""):
            facts.append(f"{key} {typo[key]}")
    for key in ("radius_px", "unit_px"):
        if metrics.get(key) not in (None, ""):
            facts.append(f"{key} {metrics[key]}")
    fonts = typo.get("fonts") or []
    if fonts:
        facts.append(f"{len(fonts)} declared font source(s)")
    else:
        facts.append("NO declared font sources — the stack is names only")
    return (
        "<section><h4>Typography &amp; metrics</h4>"
        + "".join(rows)
        + f'<p class="facts">{html.escape(" · ".join(facts))}</p></section>'
    )


def _brand_card(name: str, theme: dict, mark_svg: str | None) -> str:
    mark = f'<div class="mark">{mark_svg}</div>' if mark_svg else ""
    return f"""
<article class="brand" id="brand-{html.escape(name)}">
  <header>
    {mark}
    <div>
      <h3>{html.escape(theme.get("display_name") or name)}</h3>
      <code>{html.escape(theme.get("id") or name)}</code>
    </div>
    <button class="wear" data-brand="{html.escape(name)}">Wear this brand</button>
  </header>
  {_palette_block("Light", theme.get("light") or {})}
  {_palette_block("Dark", theme.get("dark") or {})}
  {_typography_block(theme)}
  <section><h4>Contrast</h4>{_contrast_block(theme)}</section>
</article>"""


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>brando — brand catalog</title>
<style>
:root {{ color-scheme: dark; }}
{default_vars}
{scoped_vars}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 2rem clamp(1rem, 4vw, 3rem);
  background: var(--brand-bg, #111); color: var(--brand-fg, #eee);
  font-family: var(--brand-sans, ui-sans-serif, system-ui, sans-serif);
  font-size: var(--brand-base-size, 16px);
  transition: background .2s, color .2s;
}}
h1 {{ font-family: var(--brand-display, inherit); letter-spacing: -0.02em; margin: 0 0 .25rem; }}
.sub {{ color: var(--brand-muted, #999); margin: 0 0 2rem; max-width: 62ch; }}
/* Each card wears its OWN skin — see the scoped block emitted below. So the
   chrome here reads every role from the brand, not just the swatches: its
   background, its typeface, its corner radius, its heading weight. Six cards
   rendered in one brand's blue would tell you nothing about six brands. */
.brand {{
  border: 1px solid var(--brand-border, #333);
  border-radius: calc(var(--brand-radius, 8px) * 1.5);
  background: var(--brand-bg, #1a1a1a); color: var(--brand-fg, #eee);
  font-family: var(--brand-sans, ui-sans-serif, system-ui, sans-serif);
  font-size: var(--brand-base-size, 16px);
  padding: 1.5rem; margin: 0 0 1.5rem;
}}
/* Sections sit on the brand's SURFACE, so bg-vs-surface is visible — two roles
   that look near-identical as swatches and matter a lot in a real UI. */
.brand section {{
  background: var(--brand-surface, transparent);
  border-radius: var(--brand-radius, 8px);
  padding: .75rem 1rem; margin: .85rem 0;
}}
.brand > header {{ display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }}
.brand h3 {{
  margin: 0; font-size: 1.6rem;
  font-family: var(--brand-display, var(--brand-sans, inherit));
  font-weight: var(--brand-heading-weight, 600);
  letter-spacing: var(--brand-heading-tracking, -0.01em);
}}
.brand header code {{ color: var(--brand-muted, #999); font-size: .85em; }}
.mark {{ width: 60px; height: 60px; flex: 0 0 60px; }}
.mark svg {{ width: 100%; height: 100%; }}
.wear {{
  margin-left: auto; cursor: pointer; padding: .55rem 1rem;
  border-radius: var(--brand-radius, 6px);
  border: 1px solid var(--brand-accent, #555);
  background: var(--brand-accent, #333); color: var(--brand-on-accent, #fff);
  font-family: inherit; font-size: .85em; font-weight: 600;
}}
h4 {{ margin: 1.25rem 0 .5rem; font-size: .75rem; letter-spacing: .08em;
     text-transform: uppercase; color: var(--brand-muted, #999); }}
.sws {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: .5rem; }}
.sw {{ display: flex; align-items: center; gap: .5rem; font-size: .8rem; }}
.sw i {{ width: 26px; height: 26px; border-radius: 5px; flex: 0 0 26px;
        border: 1px solid rgba(128,128,128,.4); }}
.sw b {{ font-weight: 600; }}
.sw code {{ margin-left: auto; color: var(--brand-muted, #999); }}
.type-row {{ display: grid; grid-template-columns: 7rem 1fr; gap: .5rem 1rem;
            align-items: baseline; margin: .35rem 0; font-size: .95rem; }}
.type-row code {{ grid-column: 2; color: var(--brand-muted, #999); font-size: .72rem; }}
.facts {{ color: var(--brand-muted, #999); font-size: .8rem; }}
.contrast {{ list-style: none; padding: 0; margin: .5rem 0 0; font-size: .82rem; }}
.contrast li {{ padding: .3rem 0; border-top: 1px solid var(--brand-border, #333); }}
.contrast li span {{ font-weight: 600; }}
.contrast li.error span {{ color: var(--brand-danger, #f66); }}
.contrast li.warn span {{ color: var(--brand-warning, #d9a441); }}
.contrast em {{ color: var(--brand-muted, #999); font-style: normal; }}
.ok {{ color: var(--brand-success, #4c9); }}
.bad {{ color: var(--brand-danger, #f66); }}
.warnish {{ color: var(--brand-warning, #d9a441); }}
code {{ font-family: var(--brand-mono, ui-monospace, monospace); }}
</style>
<h1>brando</h1>
<p class="sub">Every brand in the fleet, from the <code>&lt;brand&gt;.json</code> each
<code>brand_skin</code> emits. The palettes below are rendered through
<code>marklib.tokens</code> and the contrast report through
<code>marklib.palette</code> — the same projection and the same gate the build
uses, so a bug in either is visible here. Pick a brand and the page wears it.</p>
{cards}
<script>
const SKINS = {skins_json};
function wear(name) {{
  const css = SKINS[name];
  let el = document.getElementById('worn');
  if (!el) {{ el = document.createElement('style'); el.id = 'worn'; document.head.append(el); }}
  el.textContent = css;
  document.documentElement.dataset.brand = name;
  history.replaceState(null, '', '#brand-' + name);
}}
document.querySelectorAll('.wear').forEach(b =>
  b.addEventListener('click', () => wear(b.dataset.brand)));
</script>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skin", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--mark", action="append", default=[], metavar="NAME=PATH")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    marks = {}
    for pair in args.mark:
        name, path = pair.split("=", 1)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                marks[name] = fh.read()

    cards, css, themes = [], {}, {}
    for pair in args.skin:
        name, path = pair.split("=", 1)
        with open(path, encoding="utf-8") as fh:
            theme = json.load(fh)
        themes[name] = theme
        cards.append(_brand_card(name, theme, marks.get(name)))
        css[name] = mtokens.to_css_vars(theme, prefix="brand")

    if not cards:
        raise SystemExit("build_console: no --skin given")

    # EVERY CARD WEARS ITS OWN SKIN. `to_css_vars` already takes a selector, so
    # this is the same projection the mdBook themes use, pointed at a card instead
    # of :root — the brand's typeface, radius and surface come along, not just its
    # swatches.
    scoped = "\n".join(
        mtokens.to_css_vars(theme, prefix="brand", selector="#brand-%s" % name)
        for name, theme in themes.items()
    )
    # The page CHROME defaults to the first brand and follows "Wear this brand";
    # the cards never change, so they stay comparable against each other.
    default_vars = next(iter(css.values()))

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(PAGE.format(
            default_vars=default_vars,
            scoped_vars=scoped,
            cards="\n".join(cards),
            skins_json=json.dumps(css),
        ))
    print(f"console: {len(cards)} brand(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
