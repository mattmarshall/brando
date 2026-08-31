<p align="center">
  <img src="selfbrand/portrait/brando_card.svg" alt="brando" width="260">
</p>

<h1 align="center">brando</h1>

<p align="center"><em>The reusable brand pipeline — one source pulls all the strings.</em></p>

---

**brando** is a publishable Bazel module that holds the reusable brand machinery, so each
brand repo supplies only its own Spec / tokens / content and shares one hermetic pipeline.
Consumed by `savvifi/aion//brand`, `fastverk/brand`, `tomato-bazel/brand`,
`meridian-ux/brand` and `savvifi/graph//brand`.

**[The brand catalog](https://mattmarshall.github.io/brando/)** — every brand brando builds, rendered from the same `<brand>.json` each `brand_skin` emits,
with its contrast report. One self-contained page; no external requests.

## Use it

```starlark
# MODULE.bazel — resolves from registry.tbzl.dev
bazel_dep(name = "brando", version = "0.2.0")
```

```starlark
# BUILD.bazel
load("@brando//:defs.bzl", "brand_skin", "brand_svgs", "brand_icons", "brand_doc")
```

## What it provides

| rule | does |
|------|------|
| `brand_skin` | `meridian.theme.v1` textproto → `binpb` (schema-checked) + `json` |
| `brand_svgs` | run a brand's mark generator → layered SVGs (`variants`/`layers` own the `outs`) |
| `brand_icons` | rasterize a mark → PNG / `.icns` / `.ico` |
| `brand_iconcomposer` | Icon Composer `.icon` bundles |
| `brand_wordmark` | wordmark / lockup generator (typeface) |
| `brand_wordmark_glyphs` | ditto, for CONSTRUCTED letterforms — see `//marklib:wordmark` |
| `brand_office_pptx` / `brand_office_docx` | branded deck / doc templates |
| `brand_mdbook_theme` | templated mdBook theme overlay |
| `brand_doc` / `brand_latex_class` | tectonic LaTeX → PDF + a templated brand class |
| `//marklib` | shapely CSG + layered-SVG emission + Pillow rasterizer (mark-authoring lib) |
| `//marklib:tokens` | Theme → CSS custom properties |
| `//marklib:palette` | colour arithmetic + the WCAG contrast gate |
| `//marklib:diagrams` | brandbook construction / grid / clearspace plates |
| `//fonts:space_grotesk` | the shared OFL face (was vendored three times) |

A brand writes a small `gen_<mark>.py` against `@brando//marklib` and wires the rules above;
its geometry, palette, and copy stay in the brand repo.

## The name

A play on Marlon **Brando** → *The Godfather* → brand tooling that **pulls all the strings**:
one source generates every artifact (icon, wordmark, deck, doc, theme). brando's own mark is a
vectorized Brando portrait (`selfbrand/portrait/`); the marionette generators in `selfbrand/`
remain as the `marklib` pipeline dogfood.

## The studio

`studio/` is a Next.js + [eve](https://eve.dev) app: a brand agency of nine
agents, over the deterministic tier below it.

**Why an agency rather than a prompt.** `StudioService` is one `Engine` with
three methods, so one model call produces a whole brand — story, palette,
typography, catalog — in a single pass. Nobody staffs an agency with one
generalist. Here a creative director routes to eight specialists, each owning
one part of the brand and nothing else: `strategist`, `colorist`,
`typographer`, `mark_designer`, `wordmark_designer`, `platform_producer`,
`brandbook_author`, `critic`. The director writes no brand content of its own —
the moment it starts choosing hex codes it has bypassed the contrast loop and
the schema that forces it.

**Nothing here computes anything.** Every fact the agents produce — a contrast
ratio, a stylesheet, a rendered mark — is a gRPC call into the same `marklib`
the Bazel rules run. There is no TypeScript contrast gate, and there will not
be one: a second implementation is what this repo spent three releases removing.

**The colorist has a loop it cannot skip.** `check_contrast` runs the real WCAG
gate, and the instructions forbid returning a palette with any error-severity
finding. That is the rule stated below — contrast is computed, never asked for —
made enforceable at the point the palette is authored rather than at build time.

```sh
bazel run //service:server -- --port 50051      # the deterministic tier
cd studio && npm install && npm run dev          # the agency
```

`studio/` is excluded from `bazel build //...` and has its own gate
(`.github/workflows/studio.yml`): typecheck, tests against a real service, an
`eve build`, and a regenerate-and-diff of the gRPC client, because a generated
client nobody compares is the same unchecked declaration `//tools:catalog_check`
exists to catch.

## The service

`bazel run //service:server -- --port 50051` serves five AIP-linted gRPC
services: brands and their revisions, content-addressed assets, `RenderBrand`,
and a model-assisted `StudioService`.

**One library, two drivers.** The service imports the same `marklib` the Bazel
rules run — not a reimplementation, and not Bazel shelled out to.
`//service:conformance_test` compares the two byte for byte across every brand
in the repo, which is what keeps that from being a comment.

**What it renders, and what it does not.** This used to say the service could
not draw a mark at all, because a spec *named* a generator and executing a
caller-supplied generator is remote code execution rather than a feature. That
refusal still stands for a `MarkSpec.generator`. What changed in 0.6.0 is that a
spec can now *carry* its drawing: a `brando.v1.MarkProgram` is primitives,
boolean operations and arithmetic over named parameters, with no assignment, no
recursion and no unbounded loop, so executing one is evaluation and it
terminates. `//examples:citizen_sh_program_parity` asserts a transcribed program
emits bytes identical to the hand-written generator it replaces.

A construction that is genuinely a program — one whose shape *count* is not known
until the CSG runs — is still not data, and `generator` remains the supported
path for it.

**The model never draws.** `ProposeSpec` returns a `BrandSpec` — numbers and hex
codes — and the deterministic pipeline executes them. Contrast is always
computed, never asked for: a model can produce a plausible palette that fails
WCAG, and asking it to check its own arithmetic is the wrong tool.

With `BRANDO_MODEL_ID` unset the engine is a deterministic mock, so nothing
reaches Bedrock by accident. Storage is in-memory: nothing here deploys anywhere
yet, and choosing a database before choosing a host would answer the harder
question by accident.
