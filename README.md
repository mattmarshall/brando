<p align="center">
  <img src="selfbrand/portrait/brando_card.svg" alt="brando" width="260">
</p>

<h1 align="center">brando</h1>

<p align="center"><em>The reusable brand pipeline — one source pulls all the strings.</em></p>

---

**brando** is a publishable Bazel module that holds the reusable brand machinery, so each
brand repo supplies only its own Spec / tokens / content and shares one hermetic pipeline.
Consumed today by `fastverk/brand` and `tomato-bazel/brand` (and, later, `meridian-ux/brand`).

## Use it

```starlark
# MODULE.bazel — resolves from the fastverk registry (registry.fastverk.com)
bazel_dep(name = "brando", version = "0.0.1")
```

```starlark
# BUILD.bazel
load("@brando//:defs.bzl", "brand_skin", "brand_svgs", "brand_icons", "brand_doc")
```

## What it provides

| rule | does |
|------|------|
| `brand_skin` | `meridian.theme.v1` textproto → `binpb` (schema-checked) + `json` |
| `brand_svgs` | run a brand's mark generator → layered SVGs |
| `brand_icons` | rasterize a mark → PNG / `.icns` / `.ico` |
| `brand_iconcomposer` | Icon Composer `.icon` bundles |
| `brand_wordmark` | wordmark / lockup generator |
| `brand_office_pptx` / `brand_office_docx` | branded deck / doc templates |
| `brand_mdbook_theme` | templated mdBook theme overlay |
| `brand_doc` / `brand_latex_class` | tectonic LaTeX → PDF + a templated brand class |
| `//marklib` | shapely CSG + layered-SVG emission + Pillow rasterizer (mark-authoring lib) |

A brand writes a small `gen_<mark>.py` against `@brando//marklib` and wires the rules above;
its geometry, palette, and copy stay in the brand repo.

## The name

A play on Marlon **Brando** → *The Godfather* → brand tooling that **pulls all the strings**:
one source generates every artifact (icon, wordmark, deck, doc, theme). brando's own mark is a
vectorized Brando portrait (`selfbrand/portrait/`); the marionette generators in `selfbrand/`
remain as the `marklib` pipeline dogfood.
