/**
 * Every tool the agency has, as factories.
 *
 * WHY FACTORIES AND NOT TOOLS. An eve subagent inherits nothing from its
 * parent: discovery treats `agent/subagents/<id>/` as its own agent root, and a
 * tool is visible to an agent only if a file exists under THAT agent's
 * `tools/`. Eight specialists that each need `check_contrast` would naively
 * mean eight implementations. humblebrag solved this and the solution is why
 * its two writer packages are byte-identical but for one string per file: all
 * logic lives in `lib/`, and every per-subagent tool file is a three-line shim.
 *
 * The `agent` parameter is not decoration. It interpolates into the tool's
 * description, so the model reads "…for the palette you are composing" rather
 * than a generic sentence, which is the same thing humblebrag's `network`
 * parameter does.
 *
 * TWO KINDS OF TOOL HERE, and the difference is the whole design:
 *
 *   COMPOSITION tools validate and return their input unchanged. They exist to
 *   force a specialist's output into shape at the point it is produced, so a
 *   malformed palette is a retry rather than a parse failure six steps later.
 *
 *   DETERMINISTIC tools call brando's gRPC service. They are the only things
 *   here that produce a fact. Nothing in this file computes a contrast ratio,
 *   projects a stylesheet or draws a shape, because all three already exist in
 *   `marklib` and a second implementation is what this architecture is built to
 *   avoid.
 */
import { create } from "@bufbuild/protobuf";
import { defineTool } from "eve/tools";
import { z } from "zod";

import {
  brandSpecSchema,
  catalogSchema,
  copySchema,
  identitySchema,
  markProgramSchema,
  metricsSchema,
  paletteSchema,
  themeSchema,
  typographySchema,
  wordmarkSchema,
} from "./brand";
import { brando } from "./brando/client";
import { ArtifactKind } from "./brando/gen/brando/v1/brand_pb";
import {
  CheckCatalogRequestSchema,
  CheckContrastRequestSchema,
  CritiqueSpecRequestSchema,
  RenderMarkRequestSchema,
  RenderThemeRequestSchema,
} from "./brando/gen/brando/v1/brand_service_pb";
import { toBrandSpecMessage, toMarkProgramMessage } from "./proto-json";
import { toThemeMessage } from "./theme-message";

// ── the contrast gate ───────────────────────────────────────────────────────
const contrastFindingSchema = z.object({
  mode: z.string(),
  foregroundRole: z.string(),
  backgroundRole: z.string(),
  ratio: z.number(),
  minimum: z.number(),
  severity: z.enum(["error", "warn"]),
  what: z.string(),
});

const contrastResultSchema = z.object({
  passes: z.boolean(),
  errors: z.array(contrastFindingSchema),
  warnings: z.array(contrastFindingSchema),
  summary: z.string(),
});

/**
 * WCAG, computed by `marklib.palette` — never by the model.
 *
 * This is the rule brando states and this app has to enforce at the point a
 * palette is authored rather than at build time: a model can produce a
 * plausible palette that fails WCAG, and asking it to check its own arithmetic
 * is the wrong tool for the job.
 *
 * The response splits errors from warnings because the gate does, and the split
 * is load-bearing. Holding every pair to AA once flagged 35 failures across six
 * skins including `border on bg` in every one — six out of six failing one rule
 * is a bad rule, not six bad palettes, and a gate that fails everything is a
 * gate someone disables. So: `error` pairs are unambiguously text and must be
 * fixed; `warn` pairs are "look at these".
 */
export function checkContrastTool(agent: string) {
  return defineTool({
    description:
      `Compute WCAG contrast for the palette ${agent} is working on, using brando's own ` +
      "gate. Call it after every change and do not return a palette with any error-severity " +
      "finding. Never estimate a ratio yourself; this is arithmetic and the answer is here.",
    inputSchema: z.object({ theme: themeSchema }),
    outputSchema: contrastResultSchema,
    async execute({ theme }) {
      const { render } = brando();
      const response = await render.checkContrast(
        create(CheckContrastRequestSchema, { theme: toThemeMessage(theme) }),
      );
      const findings = response.contrast.map((f) => ({
        mode: f.mode,
        foregroundRole: f.foregroundRole,
        backgroundRole: f.backgroundRole,
        ratio: Number(f.ratio.toFixed(2)),
        minimum: f.minimum,
        // The proto enum is SEVERITY_ERROR / SEVERITY_WARN; the model reads the
        // bare word, and the mapping lives here rather than in a prompt.
        severity: (f.severity === 1 ? "error" : "warn") as "error" | "warn",
        what: `${f.foregroundRole} on ${f.backgroundRole} in ${f.mode}`,
      }));
      const errors = findings.filter((f) => f.severity === "error");
      const warnings = findings.filter((f) => f.severity === "warn");
      return {
        passes: errors.length === 0,
        errors,
        warnings,
        summary: errors.length
          ? `${errors.length} unreadable pair(s): ` +
            errors.map((e) => `${e.what} at ${e.ratio}:1, needs ${e.minimum}`).join("; ")
          : `No unreadable pairs. ${warnings.length} warning(s) to look at.`,
      };
    },
  });
}

// ── the mark ────────────────────────────────────────────────────────────────
/**
 * Execute a MarkProgram, and report what came out.
 *
 * THE POINT IS THAT IT RUNS, not that the model sees the SVG. Returning a few
 * kilobytes of path data would fill the context with coordinates the model
 * cannot check and did not choose — it chose parameters and relations, and the
 * interpreter computed the coordinates. What it needs back is whether the
 * program parsed, which layers and variants it produced, and which colours the
 * fills resolved to, because those are the things it can be wrong about.
 */
export function renderMarkTool(agent: string) {
  return defineTool({
    description:
      `Execute the MarkProgram ${agent} is designing against brando's interpreter and report ` +
      "what it produced. Call it before returning: a program that does not render is not a mark, " +
      "and the error names the part that is wrong.",
    inputSchema: z.object({ program: markProgramSchema, theme: themeSchema }),
    outputSchema: z.object({
      rendered: z.boolean(),
      files: z.array(z.object({ name: z.string(), bytes: z.number().int() })),
      colours: z.array(z.string()),
      summary: z.string(),
    }),
    async execute({ program, theme }) {
      const { render } = brando();
      const response = await render.renderMark(
        create(RenderMarkRequestSchema, {
          program: toMarkProgramMessage(program),
          theme: toThemeMessage(theme),
        }),
      );
      const files = response.files.map((f) => ({ name: f.name, bytes: f.content.length }));
      const decoder = new TextDecoder();
      const colours = [
        ...new Set(
          response.files.flatMap((f) =>
            [...decoder.decode(f.content).matchAll(/fill="(#[0-9A-Fa-f]{3,8})"/g)].map((m) => m[1]),
          ),
        ),
      ].sort();
      return {
        rendered: true,
        files,
        colours,
        summary:
          `${files.length} file(s) across ${new Set(files.map((f) => f.name.split(".")[0])).size} ` +
          `variant(s); fills resolved to ${colours.join(", ")}.`,
      };
    },
  });
}

// ── the catalog ─────────────────────────────────────────────────────────────
export function checkCatalogTool(agent: string) {
  return defineTool({
    description:
      `Check the Catalog ${agent} declared against the artifact kinds a build would actually ` +
      "produce. A Catalog is a floor, not a ceiling: shipping more than declared is fine, " +
      "declaring more than is produced fails the package.",
    inputSchema: z.object({
      catalog: catalogSchema,
      present: z.array(z.string().min(1)),
    }),
    outputSchema: z.object({ conformant: z.boolean(), missing: z.array(z.string()) }),
    async execute({ catalog, present }) {
      const { render } = brando();
      const kindOf = (name: string) =>
        ArtifactKind[name.replace("ARTIFACT_KIND_", "") as keyof typeof ArtifactKind];
      const response = await render.checkCatalog(
        create(CheckCatalogRequestSchema, {
          // The declared kinds go through proto3 JSON, which reads an enum by
          // name — so `ARTIFACT_KIND_MARK_SVG` is the wire value, not something
          // this file has to map. `present` is a bare repeated enum on the
          // request rather than a field of a message, so it still does.
          spec: toBrandSpecMessage({ catalog: { kinds: catalog.kinds, custom: catalog.custom ?? [] } }),
          present: present.map(kindOf).filter((k) => k !== undefined),
        }),
      );
      const missing = response.missing.map((k) => `ARTIFACT_KIND_${ArtifactKind[k]}`);
      return { conformant: missing.length === 0, missing };
    },
  });
}

// ── the critic's deterministic half ─────────────────────────────────────────
export function critiqueSpecTool(agent: string) {
  return defineTool({
    description:
      `Ask brando what is structurally absent from the spec ${agent} is reviewing, and get the ` +
      "contrast report with it. The critiques are opinion; the contrast is arithmetic. Keep them " +
      "apart in what you report, because only one of them is negotiable.",
    inputSchema: z.object({ spec: brandSpecSchema.partial() }),
    outputSchema: z.object({
      critiques: z.array(z.object({
        subject: z.string(), finding: z.string(),
        suggestion: z.string(), severity: z.string(),
      })),
      contrast: z.array(contrastFindingSchema),
      modelId: z.string(),
    }),
    async execute({ spec }) {
      const { studio } = brando();
      const response = await studio.critiqueSpec(
        create(CritiqueSpecRequestSchema, { spec: toBrandSpecMessage(spec) }),
      );
      return {
        critiques: response.critiques.map((c) => ({
          subject: c.subject, finding: c.finding,
          suggestion: c.suggestion, severity: String(c.severity),
        })),
        contrast: response.contrast.map((f) => ({
          mode: f.mode, foregroundRole: f.foregroundRole, backgroundRole: f.backgroundRole,
          ratio: Number(f.ratio.toFixed(2)), minimum: f.minimum,
          severity: (f.severity === 1 ? "error" : "warn") as "error" | "warn",
          what: `${f.foregroundRole} on ${f.backgroundRole} in ${f.mode}`,
        })),
        // Empty means the deterministic fallback answered. A reader should never
        // have to guess whether a critique came from a model.
        modelId: response.modelId,
      };
    },
  });
}

export function renderThemeCssTool(agent: string) {
  return defineTool({
    description:
      `Project the theme ${agent} is working on into CSS custom properties, exactly as a build ` +
      "would. Use it to see what a consumer actually gets.",
    inputSchema: z.object({ theme: themeSchema }),
    outputSchema: z.object({ css: z.string(), variables: z.array(z.string()) }),
    async execute({ theme }) {
      const { render } = brando();
      const response = await render.renderTheme(
        create(RenderThemeRequestSchema, { theme: toThemeMessage(theme) }),
      );
      return {
        css: response.css,
        variables: [...response.css.matchAll(/(--brand-[a-z-]+):/g)].map((m) => m[1]),
      };
    },
  });
}

// ── composition: validate, and hand back unchanged ──────────────────────────
/**
 * A schema-checked pass-through.
 *
 * The value is entirely in the check happening at the moment the specialist
 * produces the thing. A malformed palette becomes a retry inside the colorist,
 * where the model still has the reasoning that produced it, rather than a parse
 * failure in the director six steps later with nothing left to fix it from.
 */
function passthrough<T extends z.ZodTypeAny>(description: string, schema: T) {
  return defineTool({
    description,
    inputSchema: schema,
    outputSchema: schema,
    execute: (value: z.infer<T>) => value,
  });
}

export const composeIdentityTool = (agent: string) =>
  passthrough(
    `Record the Identity ${agent} wrote: tagline, positioning, story, voice rules and usage ` +
      "rules. Write each voice and usage rule as its own entry rather than a paragraph, so a " +
      "critique can cite the one rule it thinks a draft broke. Call exactly once.",
    identitySchema,
  );

export const composePaletteTool = (agent: string) =>
  passthrough(
    `Record the palettes ${agent} chose, all 14 roles in each. Call this only after ` +
      "check_contrast reports no error-severity findings. Call exactly once.",
    z.object({ light: paletteSchema, dark: paletteSchema }),
  );

export const composeTypographyTool = (agent: string) =>
  passthrough(
    `Record the typography ${agent} chose, its font sources with provenance, and the metrics. ` +
      "Every family named first in a stack needs a source: a stack is a list of NAMES, and " +
      "without a file the browser substitutes silently and the brand is quietly not applied. " +
      "Call exactly once.",
    z.object({ typography: typographySchema, metrics: metricsSchema }),
  );

export const composeMarkTool = (agent: string) =>
  passthrough(
    `Record the MarkProgram ${agent} designed, plus the variants, layers and sizes a build ` +
      "should produce from it. Call this only after render_mark has executed the program " +
      "successfully. Call exactly once.",
    z.object({
      program: markProgramSchema,
      variants: z.array(z.string().min(1)).min(1),
      layers: z.array(z.string().min(1)).min(1),
      sizes: z.array(z.number().int()).min(1),
      packed: z.array(z.string().min(1)).optional(),
    }),
  );

export const composeWordmarkTool = (agent: string) =>
  passthrough(
    `Record the wordmark ${agent} specified and the lockup that pairs it with the mark. The ` +
      "family must be one the typographer supplied a source for. Call exactly once.",
    wordmarkSchema,
  );

export const composeCatalogTool = (agent: string) =>
  passthrough(
    `Record which artifact kinds ${agent} declared a complete build of this brand produces. ` +
      "Declare only kinds the pipeline can actually make: a Catalog is checked, and declaring " +
      "one nothing produces fails the package. Call exactly once.",
    catalogSchema,
  );

export const composeCopyTool = (agent: string) =>
  passthrough(
    `Record the prose ${agent} wrote for the office and brandbook templates, so they stop ` +
      "carrying hardcoded English. Call exactly once.",
    copySchema,
  );
