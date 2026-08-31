/**
 * The shared contract every specialist writes against.
 *
 * ONE SHAPE, MIRRORING `brando.v1.BrandSpec`, and not a convenient
 * approximation of it. These schemas are used three ways — as tool
 * `inputSchema`/`outputSchema` so the model is forced into shape at every step,
 * as the final assembly validator, and as the API boundary parser — so a field
 * that drifts from the proto here drifts everywhere at once. The proto stays
 * the source; this is its zod twin, and `tests/contract.test.ts` holds the two
 * against each other rather than trusting that they agree.
 *
 * WHY NOT GENERATE IT. `protoc-gen-es` already produces types from the same
 * descriptor set, and those are what `agent/lib/brando/client.ts` speaks. They
 * are not what a MODEL should be handed: proto3 has no field presence for a
 * scalar, so every string is optional and every number defaults to zero, which
 * is precisely the shape a schema is supposed to prevent. This says which
 * fields are required, how long a story may be, and that a hex is a hex.
 */
import { z } from "zod";

/** `#RGB`, `#RRGGBB` or `#RRGGBBAA`. marklib's `palette.rgb` accepts all three. */
export const hexSchema = z
  .string()
  .regex(/^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/, "expected a hex colour like #1B7A55");

/** An arithmetic expression over a MarkProgram's own parameters. */
export const exprSchema = z.string().min(1);

export const modeSchema = z.enum(["light", "dark"]);

/**
 * The 14 roles `meridian.theme.v1.Palette` declares.
 *
 * Listed rather than left open so a typo is a validation error naming the roles
 * that exist. `warning` and `info` are here because they finally encode:
 * meridian's ValueTone had nowhere to resolve NEEDS-ATTENTION or INFORMATIONAL
 * and collapsed both to neutral on every surface until 0.24.0.
 */
export const paletteRoleSchema = z.enum([
  "bg", "surface", "fg", "muted", "border", "accent", "accent_strong",
  "on_accent", "danger", "success", "code_bg", "code_fg", "warning", "info",
]);

// ── identity ────────────────────────────────────────────────────────────────
export const identitySchema = z.object({
  legalName: z.string().min(1).optional(),
  /** One line. Appears in lockups and office templates. */
  tagline: z.string().min(1).max(120),
  positioning: z.string().min(1).max(600),
  story: z.string().min(1).max(1_200),
  /**
   * ONE RULE PER ENTRY, not a paragraph. leangres says why in its own spec: a
   * critique pass has to be able to cite the rule it thinks a draft broke,
   * rather than the whole paragraph.
   */
  voice: z.array(z.string().min(1).max(200)).min(2).max(5),
  /**
   * Constraints on USE rather than appearance — "the light-blue logo goes on
   * white only". These are the statements a contrast checker cannot derive and
   * a designer must not have to remember.
   */
  usageRules: z.array(z.string().min(1).max(240)).min(2).max(6),
});

// ── theme ───────────────────────────────────────────────────────────────────
export const paletteSchema = z.object({
  bg: hexSchema, surface: hexSchema, fg: hexSchema, muted: hexSchema,
  border: hexSchema, accent: hexSchema, accent_strong: hexSchema,
  on_accent: hexSchema, danger: hexSchema, success: hexSchema,
  code_bg: hexSchema, code_fg: hexSchema, warning: hexSchema, info: hexSchema,
});

export const fontSourceSchema = z.object({
  /** MUST match how the face is named in a typography stack: the join key. */
  family: z.string().min(1),
  srcUri: z.string().min(1),
  weight: z.string().min(1),
  style: z.enum(["normal", "italic"]).optional(),
  /**
   * A vendored binary with no sha256 and no licence is a question nobody can
   * answer six months on, so both are required here even though the proto
   * tolerates their absence.
   */
  sha256: z.string().regex(/^[0-9a-f]{64}$/).optional(),
  license: z.string().min(1),
  upstreamUri: z.string().min(1),
});

export const typographySchema = z.object({
  sans: z.string().min(1),
  mono: z.string().min(1),
  display: z.string().min(1).optional(),
  headingTracking: z.string().min(1),
  baseSizePx: z.number().int().min(12).max(24),
  headingWeight: z.number().int().min(100).max(900),
  bodyWeight: z.number().int().min(100).max(900),
  /**
   * A stack in `typography` is a list of NAMES. Without a source the browser
   * silently substitutes and the brand is quietly not applied — invisible in
   * review and in screenshots taken on a designer's machine.
   */
  fonts: z.array(fontSourceSchema).min(1),
});

export const metricsSchema = z.object({
  radiusPx: z.number().int().min(0).max(32),
  unitPx: z.number().int().min(1).max(32),
});

export const themeSchema = z.object({
  id: z.string().min(1),
  displayName: z.string().min(1),
  light: paletteSchema,
  dark: paletteSchema,
  typography: typographySchema,
  metrics: metricsSchema,
});

// ── the mark, as data ───────────────────────────────────────────────────────
export const pointSchema = z.object({ x: exprSchema, y: exprSchema });

/**
 * A colour a mark uses: stated, or resolved from the brand's own palette.
 *
 * A LITERAL IS THE DEFAULT. A mark's facet colours usually are not palette
 * roles, and tomato's skin says so as a decision rather than a concession —
 * binding a logo's red to `theme.accent` would make a palette change silently
 * redraw the mark. The reference exists for the colours that genuinely are
 * roles, which in practice are the ground it sits on and the ink it is drawn in.
 */
export const colorRefSchema = z.union([
  z.object({ literal: hexSchema }),
  z.object({ theme: z.object({ mode: modeSchema, role: paletteRoleSchema }) }),
]);

export const modalColorSchema = z.object({
  light: colorRefSchema,
  dark: colorRefSchema,
});

const rectSchema = z.object({ x0: exprSchema, y0: exprSchema, x1: exprSchema, y1: exprSchema });

/** The shape forms `marklib.program` can execute. Exactly one per shape. */
export const shapeFormSchema = z.union([
  z.object({ rect: rectSchema }),
  z.object({ poly: z.object({ points: z.array(pointSchema).min(3) }) }),
  z.object({
    ngon: z.object({
      cx: exprSchema, cy: exprSchema, rx: exprSchema,
      ry: exprSchema.optional(), sides: exprSchema, rotDeg: exprSchema.optional(),
    }),
  }),
  z.object({
    circle: z.object({
      cx: exprSchema, cy: exprSchema, r: exprSchema, segments: exprSchema.optional(),
    }),
  }),
  z.object({ roundedRect: rectSchema.extend({ radius: exprSchema, quadSegs: exprSchema.optional() }) }),
  z.object({
    polyline: z.object({
      points: z.array(pointSchema).min(2),
      halfWidth: exprSchema,
      taper: exprSchema.optional(),
    }),
  }),
  z.object({ unionOf: z.object({ shapes: z.array(z.string().min(1)).min(1) }) }),
  z.object({ intersectionOf: z.object({ shapes: z.array(z.string().min(1)).min(2) }) }),
  z.object({
    differenceOf: z.object({
      base: z.string().min(1),
      subtract: z.array(z.string().min(1)).min(1),
    }),
  }),
  z.object({
    buffer: z.object({
      shape: z.string().min(1),
      distance: exprSchema,
      quadSegs: exprSchema.optional(),
      joinStyle: exprSchema.optional(),
      capStyle: exprSchema.optional(),
      mitreLimit: exprSchema.optional(),
    }),
  }),
  z.object({
    rotate: z.object({
      shape: z.string().min(1), angleDeg: exprSchema, origin: pointSchema.optional(),
    }),
  }),
  z.object({
    translate: z.object({ shape: z.string().min(1), dx: exprSchema, dy: exprSchema }),
  }),
  z.object({
    scale: z.object({
      shape: z.string().min(1), sx: exprSchema,
      sy: exprSchema.optional(), origin: pointSchema.optional(),
    }),
  }),
]);

export type ShapeForm = z.infer<typeof shapeFormSchema>;

/**
 * A shape node. `repeat` is declared separately because its body is a shape,
 * and zod cannot express that recursion inside a union without a lazy schema.
 */
export type MarkShape = { name: string } & (
  | ShapeForm
  | {
      repeat: {
        count?: string;
        over?: string;
        indexVar?: string;
        separate?: boolean;
        body: Omit<MarkShape, "name"> & { name?: string };
      };
    }
);

export const markShapeSchema: z.ZodType<MarkShape> = z.lazy(() =>
  z.intersection(
    z.object({ name: z.string().min(1) }),
    z.union([
      shapeFormSchema,
      z.object({
        repeat: z.object({
          count: exprSchema.optional(),
          /** A table parameter to walk, instead of a counter. */
          over: z.string().min(1).optional(),
          indexVar: z.string().min(1).optional(),
          separate: z.boolean().optional(),
          body: markShapeSchema.or(shapeFormSchema),
        }),
      }),
    ]),
  ),
) as z.ZodType<MarkShape>;

export const paramSchema = z.object({ name: z.string().min(1) }).and(
  z.union([
    z.object({ value: exprSchema }),
    z.object({ list: z.object({ values: z.array(exprSchema).min(1) }) }),
    z.object({
      table: z.object({ rows: z.array(z.object({ values: z.array(exprSchema).min(1) })).min(1) }),
    }),
  ]),
);

export const layerDefSchema = z.object({
  name: z.string().min(1),
  shape: z.string().min(1),
  fill: modalColorSchema,
  gradient: z
    .object({
      stops: z.array(z.object({ offset: exprSchema.optional(), color: modalColorSchema })).min(2),
      angleDeg: exprSchema.optional(),
    })
    .optional(),
  blend: z.string().min(1).optional(),
  opacity: exprSchema.optional(),
  /** Drawn in the composite, written to no file of its own. */
  compositeOnly: z.boolean().optional(),
});

export const variantDefSchema = z.object({
  name: z.string().min(1),
  mode: modeSchema,
  /** Absent means transparent. */
  ground: modalColorSchema.optional(),
  paramOverrides: z.array(paramSchema).optional(),
});

export const markProgramSchema = z.object({
  params: z.array(paramSchema).min(1),
  shapes: z.array(markShapeSchema).min(1),
  layers: z.array(layerDefSchema).min(1),
  /**
   * The three every brand in this repo ships. `transparent` is named exactly
   * that because `brand_suite` keys its background handling off the literal
   * name — a variant called `clear` would silently acquire a ground.
   */
  variants: z.array(variantDefSchema).min(1),
  fit: z
    .object({
      boundsOf: z.string().min(1).optional(),
      halfExtent: exprSchema.optional(),
      scale: exprSchema.optional(),
      pad: exprSchema.optional(),
      center: pointSchema.optional(),
      noFlipY: z.boolean().optional(),
    })
    .refine(
      (fit) => [fit.boundsOf, fit.halfExtent, fit.scale].filter(Boolean).length === 1,
      "give exactly one of boundsOf / halfExtent / scale, as marklib.fit requires",
    ),
  canvas: z.number().int().min(64).max(4096).optional(),
  bgRound: exprSchema.optional(),
});

/**
 * The wordmark, as a configuration rather than as geometry.
 *
 * DELIBERATELY NOT A MarkProgram. brando has two wordmark paths and neither is
 * the mark pipeline: `brand_wordmark` outlines glyphs from a real typeface with
 * fontTools, and `brand_wordmark_glyphs` runs a generator for letterforms that
 * are CONSTRUCTED. Letterforms are a typeface problem — brando's own serif
 * "brando" is six hand-authored letter builders keyed by character — and a
 * geometry DSL that tried to absorb them would be inventing a font format. So
 * this states what `wordmark/wordmark.py` actually reads: the word, the
 * tagline, the face, and how the lockup places the mark against it.
 */
export const wordmarkSchema = z.object({
  word: z.string().min(1).max(32),
  tagline: z.string().min(1).max(120).optional(),
  /** Must name a family the typographer supplied a source for. */
  family: z.string().min(1),
  /** Letterspacing, in ems. Negative tightens. */
  tracking: z.number().min(-0.1).max(0.3),
  /**
   * The word's x-height as a fraction of the MARK's diameter, and the gap
   * between them in mark radii. Both relative on purpose: `marklib.wordmark`
   * sizes this way so the pairing stays stable when the mark is redrawn.
   */
  xHeight: z.number().min(0.2).max(0.8),
  gap: z.number().min(0.05).max(1.0),
});

export type Wordmark = z.infer<typeof wordmarkSchema>;

// ── catalog and copy ────────────────────────────────────────────────────────
/**
 * The kinds a brand may declare. Restricted to what `brand_suite` can actually
 * produce today: a Catalog naming a kind with no producer fails
 * `//tools:catalog_check` at package time, and a specialist should not be able
 * to write a brand that cannot be built.
 */
export const artifactKindSchema = z.enum([
  "ARTIFACT_KIND_THEME_BINPB",
  "ARTIFACT_KIND_THEME_JSON",
  "ARTIFACT_KIND_THEME_CSS",
  "ARTIFACT_KIND_MARK_SVG",
  "ARTIFACT_KIND_MARK_PNG",
  "ARTIFACT_KIND_ICON_PACKED",
  "ARTIFACT_KIND_FAVICON",
  "ARTIFACT_KIND_MDBOOK_THEME",
  "ARTIFACT_KIND_LATEX_CLASS",
  "ARTIFACT_KIND_CONTRAST_MATRIX",
  "ARTIFACT_KIND_FONTS",
]);

export const catalogSchema = z.object({
  kinds: z.array(artifactKindSchema).min(2),
  custom: z.array(z.string().min(1)).optional(),
});

/**
 * Prose the office and brandbook templates use instead of hardcoded English.
 * `pptx_gen.py` still ships "The mark" and "Light & dark" as literals; this is
 * the field that retires them.
 */
export const copySchema = z.object({
  deckTitle: z.string().min(1).max(80),
  deckSubtitle: z.string().min(1).max(160),
  markSectionTitle: z.string().min(1).max(60),
  colorSectionTitle: z.string().min(1).max(60),
  typeSectionTitle: z.string().min(1).max(60),
  closing: z.string().min(1).max(160),
});

// ── the whole brand ─────────────────────────────────────────────────────────
export const brandSpecSchema = z.object({
  id: z.string().regex(/^[a-z][a-z0-9_]*$/, "lowercase, the archive's basename"),
  displayName: z.string().min(1),
  identity: identitySchema,
  theme: themeSchema,
  mark: z.object({
    program: markProgramSchema,
    variants: z.array(z.string().min(1)).min(1),
    layers: z.array(z.string().min(1)).min(1),
    sizes: z.array(z.number().int()).min(1),
    packed: z.array(z.string().min(1)).optional(),
  }),
  catalog: catalogSchema,
  copy: copySchema,
});

export type BrandSpec = z.infer<typeof brandSpecSchema>;
export type Identity = z.infer<typeof identitySchema>;
export type Theme = z.infer<typeof themeSchema>;
export type MarkProgram = z.infer<typeof markProgramSchema>;
export type Catalog = z.infer<typeof catalogSchema>;
export type Copy = z.infer<typeof copySchema>;

/** The brief a client walks in with. */
export const briefSchema = z.object({
  brandId: z.string().regex(/^[a-z][a-z0-9_]*$/),
  displayName: z.string().min(1),
  /** What the brand is for, in the client's own words. */
  brief: z.string().min(1).max(4_000),
  /**
   * Colours, faces or metrics already decided. A rebrand usually is not
   * starting from nothing, and silently overriding a decided colour is the
   * worst thing an agency can do.
   */
  constraints: z.string().max(2_000).optional(),
});

export type Brief = z.infer<typeof briefSchema>;
