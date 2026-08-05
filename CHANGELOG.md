# Changelog

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
