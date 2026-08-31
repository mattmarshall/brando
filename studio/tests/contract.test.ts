/**
 * The zod contract, held against the proto it claims to mirror.
 *
 * `agent/lib/brand.ts` says it is `brando.v1.BrandSpec`'s twin. That is exactly
 * the kind of claim this repo has learned to distrust: a Catalog declared kinds
 * nothing checked and was already false; a `# keep in sync` comment appeared in
 * six BUILD files across four repos, which is a fair measure of how well it
 * worked. A twin nothing compares is a comment that looks like a type.
 *
 * So this walks the generated descriptors and asserts that every field name and
 * every enum member the agents are allowed to produce exists on the other side.
 * It cannot check semantics — that a `story` is a story — but it catches the
 * failure that actually happens: a proto field renamed, and a schema that goes
 * on cheerfully producing the old name until something downstream silently
 * drops it.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { z } from "zod";

import {
  artifactKindSchema,
  catalogSchema,
  copySchema,
  identitySchema,
  paletteRoleSchema,
  paletteSchema,
  typographySchema,
} from "../agent/lib/brand";
import { ArtifactKind, CatalogSchema, CopySchema, IdentitySchema } from "../agent/lib/brando/gen/brando/v1/brand_pb";
import { PaletteSchema, TypographySchema } from "../agent/lib/brando/gen/proto/theme_pb";

/** Proto field names, as protobuf-es reports them (camelCase). */
function protoFields(desc: { fields: readonly { name: string; localName: string }[] }) {
  return new Set(desc.fields.map((f) => f.localName));
}

/** Proto field names in their WIRE spelling (snake_case), for role vocabularies. */
function protoWireNames(desc: { fields: readonly { name: string }[] }) {
  return new Set(desc.fields.map((f) => f.name));
}

function zodKeys(schema: z.ZodObject<z.ZodRawShape>) {
  return new Set(Object.keys(schema.shape));
}

test("every Identity field the strategist writes exists on the proto", () => {
  const proto = protoFields(IdentitySchema);
  for (const key of zodKeys(identitySchema)) {
    assert.ok(proto.has(key), `Identity.${key} is not a brando.v1.Identity field`);
  }
});

test("the palette role vocabulary is exactly meridian's", () => {
  // Both directions. A missing role means a brand cannot set something the
  // renderer will look for and fall back on; an EXTRA one means a specialist
  // can write a role that is silently dropped on encode, which is worse
  // because nothing fails.
  const proto = protoWireNames(PaletteSchema);
  const ours = zodKeys(paletteSchema);
  assert.deepEqual([...ours].sort(), [...proto].sort());
  // And the enum a MarkProgram's ThemeColor may name is the same set again.
  assert.deepEqual([...paletteRoleSchema.options].sort(), [...proto].sort());
});

test("every Typography field exists on the proto", () => {
  const proto = protoFields(TypographySchema);
  for (const key of zodKeys(typographySchema)) {
    assert.ok(proto.has(key), `Typography.${key} is not a meridian.theme.v1.Typography field`);
  }
});

test("every Copy field the brandbook author writes exists on the proto", () => {
  const proto = protoFields(CopySchema);
  for (const key of zodKeys(copySchema)) {
    assert.ok(proto.has(key), `Copy.${key} is not a brando.v1.Copy field`);
  }
});

test("every artifact kind a specialist may declare is a real ArtifactKind", () => {
  for (const name of artifactKindSchema.options) {
    const bare = name.replace("ARTIFACT_KIND_", "");
    assert.ok(
      bare in ArtifactKind,
      `${name} is not in brando.v1.ArtifactKind; a Catalog naming it would fail to encode`,
    );
  }
});

test("the catalog schema is a floor: it does not forbid shipping more", () => {
  // A Catalog that rejected an unknown kind would turn "shipping more than
  // declared" — which is explicitly legal — into a validation error.
  const parsed = catalogSchema.safeParse({
    kinds: ["ARTIFACT_KIND_THEME_JSON", "ARTIFACT_KIND_THEME_CSS"],
    custom: ["something-this-brand-invented"],
  });
  assert.ok(parsed.success, parsed.success ? "" : JSON.stringify(parsed.error.issues));
});

test("a palette missing a role is rejected rather than half-parsed", () => {
  const { light, ...rest } = { light: { bg: "#FFFFFF" }, dark: {} };
  void rest;
  assert.equal(paletteSchema.safeParse(light).success, false);
});

test("a colour that is not a hex is rejected", () => {
  const full = Object.fromEntries(
    [...zodKeys(paletteSchema)].map((role) => [role, "#123456"]),
  );
  assert.equal(paletteSchema.safeParse(full).success, true);
  assert.equal(paletteSchema.safeParse({ ...full, accent: "rebeccapurple" }).success, false);
  // Three-digit and eight-digit forms are legal: marklib's `rgb()` takes both.
  assert.equal(paletteSchema.safeParse({ ...full, accent: "#abc" }).success, true);
  assert.equal(paletteSchema.safeParse({ ...full, accent: "#12345678" }).success, true);
});
