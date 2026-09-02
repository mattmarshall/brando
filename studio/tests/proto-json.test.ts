/**
 * The conversion the agents actually use, against the real service.
 *
 * THIS IS THE GATE THAT WAS MISSING. `tests/brando-client.test.ts` proves the
 * transport and the interpreter, but it builds its messages with `create()` and
 * tagged oneofs — the protobuf-es object form. The agents do not have that: a
 * specialist produces the zod shape, which is proto3 JSON, where a oneof is a
 * plain field. Nothing compared the two, so `create(MarkProgramSchema, program)`
 * with a cast typechecked, shipped, and sent every `Param` with no member set.
 *
 * So these tests start from a value `markProgramSchema` parsed — exactly what a
 * tool's `execute` receives — and end at rendered SVG.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { markProgramSchema, type MarkProgram } from "../agent/lib/brand";
import { toBrandSpecMessage, toMarkProgramMessage } from "../agent/lib/proto-json";

/** A program in the shape a specialist writes it: flat oneof members. */
function authoredProgram(): MarkProgram {
  return markProgramSchema.parse({
    canvas: 64,
    params: [
      { name: "w", value: "10" },
      { name: "corners", table: { rows: [{ values: ["0", "0"] }, { values: ["1", "1"] }] } },
    ],
    shapes: [
      { name: "body", rect: { x0: "0", y0: "0", x1: "w", y1: "w" } },
      { name: "hole", circle: { cx: "w / 2", cy: "w / 2", r: "w / 4" } },
      { name: "ring", difference: { base: "body", subtract: ["hole"] } },
    ],
    fit: { bounds: "ring", pad: "0.1" },
    layers: [
      {
        name: "ring",
        shape: "ring",
        fill: {
          light: { theme: { mode: "light", role: "fg" } },
          dark: { literal: "#7FD9AF" },
        },
      },
    ],
    variants: [{ name: "flat", mode: "light" }],
  });
}

test("a oneof authored as a plain field survives the conversion", () => {
  const message = toMarkProgramMessage(authoredProgram());

  // The failure this replaces: `form.case` was undefined, and the service said
  // "parameter 'w' sets none of value/list/table".
  assert.equal(message.params[0]?.form.case, "value");
  assert.equal(message.params[0]?.form.case === "value" ? message.params[0].form.value : undefined, "10");
  assert.equal(message.params[1]?.form.case, "table");

  assert.equal(message.shapes[0]?.form.case, "rect");
  assert.equal(message.shapes[2]?.form.case, "difference");
  assert.equal(message.fit?.extent.case, "bounds");
});

test("a colour reference and a literal are different members, not the same one", () => {
  const message = toMarkProgramMessage(authoredProgram());
  const fill = message.layers[0]?.fill;
  assert.equal(fill?.light?.source.case, "theme");
  assert.equal(fill?.dark?.source.case, "literal");
  // The whole point of the role reference: the light fill names a role rather
  // than a colour, so the palette decides it.
  assert.equal(fill?.light?.source.case === "theme" ? fill.light.source.value.role : undefined, "fg");
});

test("an artifact kind converts by name, not by a hand-written table", () => {
  const message = toBrandSpecMessage({
    catalog: { kinds: ["ARTIFACT_KIND_THEME_CSS", "ARTIFACT_KIND_MARK_SVG"] },
  });
  assert.deepEqual(message.catalog?.kinds.length, 2);
});

test("a field the proto does not have is refused rather than dropped", () => {
  // The property that makes this a gate: a zod schema that drifts from the
  // proto fails here, loudly, instead of arriving as a quietly emptier message.
  assert.throws(() => toBrandSpecMessage({ nonsense: true } as never), /nonsense/);
});

test("an authored program renders, end to end", async () => {
  // The conversion unit-tested above, followed by the service that rejected the
  // old one. Requires a live tier, like `brando-client.test.ts` — a skip here
  // would be a gate that silently checks nothing.
  const { create } = await import("@bufbuild/protobuf");
  const { brando, resetBrandoClient } = await import("../agent/lib/brando/client");
  const { RenderMarkRequestSchema } = await import(
    "../agent/lib/brando/gen/brando/v1/brand_service_pb"
  );
  const { PaletteSchema, ThemeSchema } = await import("../agent/lib/brando/gen/proto/theme_pb");

  resetBrandoClient();
  const response = await brando().render.renderMark(
    create(RenderMarkRequestSchema, {
      program: toMarkProgramMessage(authoredProgram()),
      theme: create(ThemeSchema, {
        id: "t",
        light: create(PaletteSchema, { bg: "#FFFFFF", fg: "#111111" }),
        dark: create(PaletteSchema, { bg: "#111111", fg: "#FFFFFF" }),
      }),
      variants: ["flat"],
    }),
  );

  const composite = response.files.find((file) => file.name === "mark_flat.svg");
  assert.ok(composite, `no composite among ${response.files.map((f) => f.name).join(", ")}`);
  const svg = new TextDecoder().decode(composite.content);
  assert.match(svg, /#111111/, "the light fill named the `fg` role; the palette should decide it");
});
