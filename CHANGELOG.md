# Changelog

## 0.4.0 — a brand should start complete, and be publishable

Additive. Every 0.3.0 rule keeps its behavior.

### Added

* **`brand_suite`** — a brand's whole catalog from one macro call. `fastverk`
  produced seventeen artifact types and `graph`/`savault` produced two, not
  because those brands wanted less but because each was wired by hand from the
  same rules and stopped wherever its author's patience did. A brand now opts OUT
  of what it does not want rather than opting in to each thing it does.
  `//examples/leangres` is a complete brand in a 26-line BUILD file.
* **`brand_css`** — Theme to CSS custom properties as a standalone artifact. The
  projection existed only *inside* `brand_mdbook_theme`, so the only way to get a
  brand's stylesheet was to also want an mdBook.
* **`brand_contrast_test`** — `marklib.palette` has had the WCAG checker and a
  waiver mechanism since 0.2.0 and nothing wrapped it, so no brand ran it in its
  own build. Every suite now does.
* **`brand_publish_plan` + `tools/publish_brando.sh`** — distribution. The plan
  half is hermetic (content-addressed key, URL, SRI `integrity`, a paste-ready
  MODULE.bazel snippet), so the pin is a build artifact a test checks rather than
  something the publisher derives by hand. `rules_brand.from_url` REQUIRES
  `integrity`, and computing an SRI hash manually is the step people skip — which
  matters, because an unpinned brand means a swapped CDN object restyles every
  consumer at once, silently. The upload half refuses a plan whose sha does not
  match its file.
* **`//examples/leangres` and `//examples/citizen_sh`** — the two brand exercises
  this work exists for, worked end to end. citizen-sh is the two-surface test:
  the LaTeX class for its governing document and the stylesheet plus favicon for
  its docs, from one package.
* **`//:version.bzl`** — one copy of the version. `MODULE.bazel` cannot `load()`,
  so a module cannot hand its own version to a BUILD file, which is why
  `brand_package`'s `brando_version` said `0.2.0` while `MODULE.bazel` said
  `0.3.0`. That field is stamped into every `.brando` as provenance; a stale one
  is worse than an absent one. `//:version_test` gates it.
* **CI**, which brando had none of: nineteen tests that only ever ran on one
  laptop, for a module six repos depend on.

### Fixed

* **`packed` is now passed to the rasterizer** as `--packed`. It was the last
  hand-sync hole in the icons path: `brand_icons` DECLARED `.icns`/`.ico` outputs
  and nothing told the generator to emit them, so the declared and produced sets
  could disagree — exactly the drift the `--variant`/`--layer` flags removed
  everywhere else.

## 0.3.0 — a brand becomes a package

Additive. Every 0.2.0 rule keeps its behavior; the new surface is `brand_package`
and the `brando.v1` protos it encodes.

### Added

* **`brand_package` — the `.brando` archive.** One file a consumer can take
  instead of a pipeline: a zip holding `brand.binpb` (a `brando.v1.BrandPackage`),
  `brand.json` (the same manifest, for Starlark) and every artifact under a
  content-addressed path. Identical bytes land once however many logical names
  point at them — a brand's flat and mono marks are routinely the same file — and
  a consumer asks for the name, never the hash. Byte-reproducible, with a test.

  It replaces two hand-assembled asset zips (`aion-brand-assets.zip`,
  `tbzl-brand-assets.zip`) with two different layouts, two naming conventions and
  no manifest in either. Four of the six brands had no bundle at all. A zip with
  no manifest is a bag of files: you can extract it, but you cannot ask it for
  "the favicon" without already knowing what this brand called that.

  The manifest is **protoc-validated, not merely produced** — `pack_brand.py` is
  stdlib and emits a textproto, and `protoc --encode` rejects anything that does
  not match `brando.v1`. That keeps the protobuf wheel out of a brand repo's
  graph, the property `skin_json` had to be rebuilt to preserve.

* **`brando.v1`** (`proto/brando/v1/brand.proto`), AIP-linted via `rules_aip`.
  `BrandSpec` is what a human or a model authors; `BrandPackage` is the manifest
  inside an archive. It **reuses `meridian.theme.v1.Theme`** rather than
  redeclaring the palette contract. `Catalog` and `ArtifactKind` are the
  formalization: "what does a complete brand include" stops being "whatever
  fastverk happened to wire up".

* **brando has a skin** (`//skins:brando`). It shipped a mark, a wordmark and an
  entire brand pipeline for three releases with no skin of its own, which is a
  poor advertisement for a tool whose argument is that one source drives
  everything. Cream on ink; `accent` is a value step rather than a hue, because
  the identity is monochrome on purpose. Zero unreadable pairs under the gate.

* **`//console`** — a browsable catalog rendering every brand from the
  `<brand>.json` each `brand_skin` already emits, dogfooding `marklib.tokens` for
  the CSS and `marklib.palette` for the contrast report. Each card wears its own
  skin via scoped custom properties, so the brands read as different brands
  rather than six identically-styled swatch grids.

* **Fixtures for `brand_doc` and `brand_latex_class`.** Neither had an in-repo
  caller — the same condition that let `brand_skin` mis-resolve its schema and
  `brand_iconcomposer` ship a `KeyError` for two releases. There is now one
  fixture **per emitted file**: the article class and the beamer theme, because
  0.2.0's rename broke a call site the single article fixture never touched.

### Fixed

* **`skin_json` did not implement string concatenation.** Adjacent string
  literals join, as in C — how every textproto wraps prose. Neither this parser
  nor the tokenizer it replaced handled it, and nothing noticed, because no
  *skin* has a field long enough to wrap. A `BrandSpec` does. The failure is
  badly localized: the second literal reads as a scalar with no field name, so
  the error names a position several lines past the real one.
* **Enums could not be parsed.** A textproto writes an enum as a bare identifier,
  which lexes exactly like a field name; only the schema can distinguish them.
* **int64 is now its own schema kind.** It is the one type whose two encodings
  genuinely disagree: bare in a textproto, a **string** in proto3-JSON, because
  JSON numbers cannot carry the full int64 range. `theme.proto` has no 64-bit
  field, so this could not surface before `size_bytes`.
* **`marklib` imported eagerly**, so `import marklib.tokens` pulled `svgwrite`
  despite `tokens` and `palette` being stdlib-only by design. The tests never
  caught it — they run under Bazel, where every wheel is present. Now lazy
  (PEP 562), asserted in a subprocess.

### Changed

* **`meridian_schemas` 0.17.0 → 0.24.0.** `Palette.warning` and `Palette.info`
  now **encode for the first time in the fleet**. Zero of six skins set them, and
  that was not neglect: no skin *could*. The fields arrive in 0.20.0, and
  0.20.0–0.24.0 were tagged upstream but never published — `rels` derived the
  registry directory from the repo basename rather than the module's declared
  name, so five releases wrote to a path Bazel never reads.

## 0.2.0 — the consolidation release

Breaking for `brand_mdbook_theme` and `brand_latex_class`; every other rule keeps
a working legacy path so a brand can adopt 0.2.0 in one commit and migrate its
generators in another.

### Fixed — bugs that were shipping

* **`brand_skin` resolved its own schema by accident.** It emitted
  `"@meridian//proto:theme.proto"` as a plain string into `native.genrule(srcs=)`,
  and bzlmod resolves a plain-string label in a legacy macro with the **calling**
  package's repo mapping. Which schema validated a skin was therefore an accident
  of the consumer's dependency graph. brando pinned the retired `meridian` 0.2.3,
  whose 69-line `theme.proto` has no `Typography.display` (7) and no
  `repeated FontSource fonts` (8) — so a consumer without a `meridian` alias
  failed the `--encode` gate on exactly the fields a brand needs to ship its own
  faces. aion had forked these genrules into its own BUILD file to work around it.
  Fixed in both halves: depend on `meridian_schemas`, and emit every external
  label via `Label()`. Verified with a consumer declaring only `bazel_dep(brando)`.
* **`marklib.iconcomposer` crashed** (`KeyError: 0`) on the dict-form gradients
  0.1.0 introduced. `brand_iconcomposer` has no caller anywhere in the fleet,
  which is why it shipped broken for two releases. The gradient **angle** is now
  honoured rather than dropped, using the same vector construction as
  `linear_gradient`, so an `.icon` and its SVG cannot disagree about direction.
* **`fvslate` and `fvtertiary` were the same token under two names** — the LaTeX
  class called it tertiary, the beamer theme called it slate. Unified.

### Changed

* **Palettes come from the skin.** `brand_mdbook_theme(skin=)` and
  `brand_latex_class(skin=)` read the brand's own `<name>.json` instead of taking
  re-typed colour attributes. A palette was previously authored two to five times
  per brand, and had already drifted: fastverk's LaTeX accent said `E0A33E` where
  its skin said `F2C46A`.
* **`brand_svgs` / `brand_icons` own their `outs`.** They take `variants`,
  `layers`, `sizes` and `prefix`, compute the outputs, and pass the same lists to
  the generator. Bazel checks declared ⊆ produced but not the reverse, so a layer
  added to a generator and not to the BUILD list was written and silently dropped.
  The comment `# keep in sync with gen_mark.py's VARIANTS/LAYERS` appeared in six
  BUILD files across four repos; it is gone, along with the second list.
* **No more `fv`.** `fvbg`/`fvfg`/`fvaccent` → `brand*`; `--fv-*` → `--brand-*`;
  `.fv-cta` → `.brand-cta`. Template tokens moved from `@INK@`/`@CREAM@`/
  `@TERTIARY@` to the schema's role names, and the CSS variables with them.
* **`brand_mdbook_theme` is multi-instantiable** via `theme_dir`; its six output
  paths were hardcoded, which quietly limited a package to one theme.
* **`skin_json` replaces `textpb_to_json`.** Same stdlib-only property — that is a
  hard requirement, since it runs in the consumer's build and a brand repo need
  not have `rules_python` at all — but the arity and numeric facts now come from
  `theme_schema.json`, derived from `theme.proto` and diffed by
  `//skins:theme_schema_test`, rather than from two hand-written sets. Output is
  byte-identical to the tokenizer it replaces.

### Added

* `//marklib:fit` — one model→pixel transform. Four brands had four incompatible
  formulas; `pad` is now documented (a fraction of the full canvas, per side) and
  a test pins that it reproduces aion's existing values exactly.
* `//marklib:raster.render_set` — the rasterizer driver, ~280 lines of near-identical
  copy across five repos. `ss=2` by default, so fastverk and meridian pick up the
  antialiasing they silently lacked. A test asserts it is **byte-identical** to
  the hand-rolled loop.
* `//marklib:tokens` — Theme → CSS custom properties, previously implemented three
  times with three fallback tables.
* `//marklib:palette` — WCAG contrast, with severity tiers. Run flat it flagged all
  six skins on `border`, which is a bad rule rather than six bad palettes; only
  pairs whose usage is unambiguous fail a build.
* `//marklib:diagrams` — brandbook construction / grid / clearspace, lifted from
  fastverk. The reference circle is measured through the caller's transform rather
  than an assumed scale, which is what made the original brand-specific.
* `//marklib:wordmark` — placement, box fitting and lockup composition, plus
  `brand_wordmark_glyphs`, for a brand whose letterforms are constructed rather
  than set in a typeface. aion hand-rolled 143 lines for want of this.
* `//tools:render_template` — one templating path, replacing a `_sed_cmd` that
  existed verbatim in two files. An unresolved token now **fails the build**;
  `sed` shipped it to the browser as a literal `@ACCENT@`.
* `//fonts:space_grotesk` — one copy of a face that was md5-identical in three
  repos, with `SOURCES.json` provenance and the OFL inside the filegroup.

### Tests

**1 → 14.** brando previously tested only its textproto converter. Notably
`//marklib:gradient_parity_test`: `linear_gradient` ships twice, once for SVG and
once for raster, and nothing compared them — a divergence there does not crash or
fail a build, the app icon's gradient simply runs the other way from the website's.
`//skins:fixture` makes brando dogfood `brand_skin`, and `//doc:fixture_class` /
`//mdbook:fixture_theme` do the same for the rules that had no in-repo caller —
the condition under which all three of the bugs above shipped.

## 0.1.1

* `skins: textpb_to_json` dropped all but the last of a repeated field.

## 0.1.0

* `marklib`: reusable N-stop / any-angle `linear_gradient` (SVG + raster).

## 0.0.1

* Initial release — the reusable brand pipeline as a Bazel module.
