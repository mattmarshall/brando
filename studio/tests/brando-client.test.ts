/**
 * The TypeScript client, against the real Python service.
 *
 * THIS IS THE ONE TEST THAT PROVES THE ARCHITECTURE. Everything the studio's
 * agents compute — contrast, stylesheets, marks — is a gRPC call into
 * `marklib`, which means TypeScript talking HTTP/2 to `grpcio`. That is an
 * assumption, not a fact, until something exercises it: the generated client
 * typechecks whether or not a byte ever reaches a server, and a mocked
 * transport would prove only that the mock works.
 *
 * So this test needs a live service. It FAILS rather than skips when there is
 * not one, because a skip that is always taken is a gate that silently checks
 * nothing — the same reasoning `//service:conformance_test` applies to its own
 * per-brand coverage guard.
 *
 *   bazel run //service:server -- --port 50051
 *   BRANDO_SERVICE_URL=http://localhost:50051 npm test
 */
import assert from "node:assert/strict";
import test from "node:test";

import { create } from "@bufbuild/protobuf";

import { brando, brandoTarget, resetBrandoClient } from "../agent/lib/brando/client";
import { ArtifactKind, BrandSpecSchema, ExprListSchema, ExprTableSchema, FitDefSchema, LayerDefSchema, MarkProgramSchema, ModalColorSchema, ParamSchema, RectSchema, ShapeSchema, ThemeColorSchema, VariantDefSchema } from "../agent/lib/brando/gen/brando/v1/brand_pb";
import { CheckCatalogRequestSchema, CheckContrastRequestSchema, CritiqueSpecRequestSchema, RenderMarkRequestSchema, RenderThemeRequestSchema } from "../agent/lib/brando/gen/brando/v1/brand_service_pb";
import { PaletteSchema, ThemeSchema } from "../agent/lib/brando/gen/proto/theme_pb";

/** A palette whose `accent` is deliberately unreadable on its own ground. */
function theme(accent = "#EEEEEE") {
  return create(ThemeSchema, {
    id: "t",
    light: create(PaletteSchema, {
      bg: "#FFFFFF", fg: "#111111", accent, onAccent: "#FFFFFF",
    }),
    dark: create(PaletteSchema, {
      bg: "#111111", fg: "#FFFFFF", accent: "#7FD9AF", onAccent: "#0B1F17",
    }),
  });
}

/** Two squares and a fit: a real program, short enough not to be the subject. */
function rect(x0: string, y0: string, x1: string, y1: string) {
  return create(ShapeSchema, {
    name: "body",
    form: { case: "rect", value: create(RectSchema, { x0, y0, x1, y1 }) },
  });
}

function markProgram() {
  return create(MarkProgramSchema, {
    canvas: 64,
    params: [create(ParamSchema, { name: "w", form: { case: "value", value: "10" } })],
    shapes: [rect("0", "0", "w", "w")],
    fit: create(FitDefSchema, {
      extent: { case: "boundsOf", value: "body" },
      pad: "0.1",
    }),
    layers: [create(LayerDefSchema, {
      name: "body",
      shape: "body",
      fill: create(ModalColorSchema, {
        light: {
          source: {
            case: "theme",
            value: create(ThemeColorSchema, { mode: "light", role: "fg" }),
          },
        },
      }),
    })],
    variants: [create(VariantDefSchema, { name: "flat", mode: "light" })],
  });
}

test("the target is stated, not guessed", () => {
  resetBrandoClient();
  assert.match(brandoTarget(), /^https?:\/\//);
});

test("contrast is arithmetic, and it comes from marklib", async () => {
  const { render } = brando();
  const response = await render.checkContrast(
    create(CheckContrastRequestSchema, { theme: theme() }),
  );
  // `on_accent` on a near-white `accent` is unreadable, and the gate says so
  // with severity ERROR because that pair's usage is unambiguous.
  const pairs = response.contrast.map((f) => `${f.foregroundRole}/${f.backgroundRole}`);
  assert.ok(pairs.includes("on_accent/accent"), `expected an on_accent finding, got ${pairs.join(", ")}`);
});

test("a stylesheet comes back with the contrast nobody asked for", async () => {
  const { render } = brando();
  const response = await render.renderTheme(
    create(RenderThemeRequestSchema, { theme: theme() }),
  );
  assert.match(response.css, /--brand-accent:/);
  assert.ok(response.contrast.length > 0, "a failing palette must report findings unasked");
});

test("a MarkProgram round-trips to layered SVG", async () => {
  const { render } = brando();
  const response = await render.renderMark(
    create(RenderMarkRequestSchema, { program: markProgram(), theme: theme() }),
  );
  const names = response.files.map((f) => f.name);
  assert.ok(names.includes("mark_flat.svg"), `got ${names.join(", ")}`);
  const composite = response.files.find((f) => f.name === "mark_flat.svg");
  assert.ok(composite);
  const svg = new TextDecoder().decode(composite.content);
  assert.match(svg, /<svg/);
  // The fill resolved from the theme, not from a hex in the program. This is
  // the property that makes a role reference worth having, and it is invisible
  // in any test that only checks the SVG parses.
  assert.match(svg, /#111111/);
});

test("a malformed program is the caller's error, and says which part", async () => {
  const { render } = brando();
  const program = markProgram();
  program.shapes[0] = rect("0", "0", "w + nope", "w");
  await assert.rejects(
    () => render.renderMark(create(RenderMarkRequestSchema, { program, theme: theme() })),
    (error: Error) => error.message.includes("nope"),
  );
});

test("a catalog reports only what is missing, because it is a floor", async () => {
  const { render } = brando();
  const spec = create(BrandSpecSchema, {
    id: "t",
    catalog: { kinds: [ArtifactKind.THEME_CSS, ArtifactKind.MARK_SVG] },
  });
  const response = await render.checkCatalog(
    create(CheckCatalogRequestSchema, {
      spec,
      present: [ArtifactKind.THEME_CSS, ArtifactKind.THEME_JSON],
    }),
  );
  assert.deepEqual(response.missing, [ArtifactKind.MARK_SVG]);
});

test("a draft can be critiqued without being saved first", async () => {
  const { studio } = brando();
  const response = await studio.critiqueSpec(
    create(CritiqueSpecRequestSchema, { spec: create(BrandSpecSchema, { id: "t" }) }),
  );
  assert.ok(response.critiques.length > 0, "an empty spec has plenty wrong with it");
  // Empty means the deterministic fallback answered. A reader should never have
  // to guess whether a critique came from a model.
  assert.equal(response.modelId, "");
});
