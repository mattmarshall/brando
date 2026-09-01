/**
 * What the agency is doing, read off the message stream.
 *
 * NOTHING HERE IS EXTRA PLUMBING, and that is the point. eve surfaces a
 * delegation as an ordinary tool call named `eve:subagent:<id>`, with the same
 * lifecycle every other tool has, so "which specialist is live" is already in
 * the stream the chat renders. A parallel progress channel — a status field the
 * director had to remember to update — would be a second account of the run,
 * and the second account is the one that goes stale.
 *
 * The same reasoning gives the finished brand: it is the OUTPUT of the
 * `submit_brand` tool, not a JSON block in the director's prose. A model asked
 * to return JSON in a message eventually fences it, apologises, or summarises
 * it; a tool call is structured by construction.
 */
import type { EveMessage, EveMessagePart } from "eve/react";

import { brandSpecSchema, type BrandSpec } from "@/agent/lib/brand";
import { ROSTER, specialistFor, type Specialist } from "./roster";

export type SpecialistState = "idle" | "working" | "done" | "failed";

export type SpecialistStatus = {
  readonly specialist: Specialist;
  readonly state: SpecialistState;
  /** The specialist's own answer, once it has one. Rendered as a summary only. */
  readonly output?: unknown;
};

/**
 * A call to brando's service, as one line.
 *
 * These are the only things in the run that are FACTS rather than opinions —
 * a contrast ratio, a stylesheet, a rendered mark — so they get their own
 * ledger instead of being buried in a specialist's transcript.
 */
export type Fact = {
  readonly id: string;
  readonly tool: string;
  readonly summary: string;
  readonly failed: boolean;
};

export type RunState = {
  readonly statuses: readonly SpecialistStatus[];
  readonly facts: readonly Fact[];
  readonly spec?: BrandSpec;
  /** Present when `submit_brand` ran but its output is not a legal BrandSpec. */
  readonly specError?: string;
  readonly started: boolean;
};

/** Tools that call the deterministic tier. Composition tools are not facts. */
const DETERMINISTIC = new Set(["check_contrast", "render_theme_css", "render_mark", "check_catalog", "critique_spec"]);

function toolParts(messages: readonly EveMessage[]) {
  const parts: EveMessagePart[] = [];
  for (const message of messages) parts.push(...message.parts);
  return parts.filter((part) => part.type === "dynamic-tool");
}

export function readRun(messages: readonly EveMessage[]): RunState {
  const parts = toolParts(messages);

  const states = new Map<string, SpecialistState>();
  const outputs = new Map<string, unknown>();
  const facts: Fact[] = [];
  let spec: BrandSpec | undefined;
  let specError: string | undefined;

  for (const part of parts) {
    const specialist = specialistFor(part.toolName);
    if (specialist) {
      states.set(specialist.id, toState(part.state));
      if (part.state === "output-available") outputs.set(specialist.id, part.output);
      continue;
    }

    if (DETERMINISTIC.has(part.toolName) && (part.state === "output-available" || part.state === "output-error")) {
      facts.push({
        id: part.toolCallId,
        tool: part.toolName,
        summary: part.state === "output-error" ? part.errorText : summarise(part.toolName, part.output),
        failed: part.state === "output-error",
      });
      continue;
    }

    if (part.toolName === "submit_brand" && part.state === "output-available") {
      const parsed = brandSpecSchema.safeParse(part.output);
      if (parsed.success) {
        spec = parsed.data;
        specError = undefined;
      } else {
        // Worth saying rather than rendering nothing: the director submitted,
        // so the run believes it finished, and an empty page would read as a
        // studio that silently did nothing.
        specError = parsed.error.issues
          .slice(0, 3)
          .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
          .join("; ");
      }
    }
  }

  return {
    facts,
    spec,
    specError,
    started: parts.length > 0,
    statuses: ROSTER.map((specialist) => ({
      output: outputs.get(specialist.id),
      specialist,
      state: states.get(specialist.id) ?? "idle",
    })),
  };
}

function toState(state: string): SpecialistState {
  switch (state) {
    case "output-available":
      return "done";
    case "output-error":
    case "output-denied":
      return "failed";
    default:
      return "working";
  }
}

/**
 * One line per fact, in the vocabulary of the thing measured.
 *
 * Each branch matches a tool's declared `outputSchema` in
 * `agent/lib/brand-tools.ts`, and an unrecognised shape says so rather than
 * guessing — so a tool whose output changes shows up as "no summary" instead of
 * as a confident sentence about a field that no longer exists.
 */
function summarise(tool: string, output: unknown): string {
  if (output === null || typeof output !== "object") return String(output ?? "");
  const value = output as Record<string, unknown>;

  // Two tools already write their own one-liner, for the model. It is the same
  // sentence a reader wants, so it is not written twice.
  if (typeof value.summary === "string") return value.summary;

  if (tool === "critique_spec") {
    const critiques = Array.isArray(value.critiques) ? value.critiques.length : 0;
    const contrast = Array.isArray(value.contrast) ? value.contrast.length : 0;
    // An empty modelId means brando's deterministic fallback answered rather
    // than a model. A reader should never have to guess which.
    const source = value.modelId ? String(value.modelId) : "deterministic";
    return `${critiques} critique${critiques === 1 ? "" : "s"}, ${contrast} contrast finding${contrast === 1 ? "" : "s"} (${source})`;
  }

  if (tool === "check_catalog" && Array.isArray(value.missing)) {
    return value.missing.length === 0
      ? "every declared kind has a producer"
      : `declared but unbuildable: ${value.missing.join(", ")}`;
  }

  if (tool === "render_theme_css" && Array.isArray(value.variables)) {
    return `${value.variables.length} custom properties`;
  }

  return "no summary";
}
