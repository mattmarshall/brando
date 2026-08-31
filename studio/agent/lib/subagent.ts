/**
 * The shape every specialist shares, so eight `agent.ts` files stay three lines.
 *
 * `outputSchema` applies in TASK MODE, which is exactly how a subagent runs, so
 * declaring it here means the framework enforces each specialist's contract
 * rather than the director noticing afterwards that a palette came back as
 * prose. The `compose_*` tools stay regardless: they check each STEP, and a
 * schema on the final answer cannot tell you that the contrast gate was
 * consulted before the palette was written down.
 */
import { defineAgent } from "eve";
import { z } from "zod";

/**
 * eve's `JsonObject` is deeply readonly, and `z.toJSONSchema` returns a mutable
 * one. The values are identical; only the modifier differs, and asserting that
 * once here is better than eight call sites each doing it differently.
 */
type JsonSchema = { readonly [key: string]: unknown };

import { contextWindowTokens, specialistModel } from "./model";

export function defineSpecialist(description: string, output: z.ZodTypeAny) {
  return defineAgent({
    description,
    model: specialistModel,
    modelContextWindowTokens: contextWindowTokens,
    // Zod 4 emits JSON Schema directly; eve takes a plain JSON Schema object.
    // Converting here rather than at each call site means one place knows how.
    outputSchema: z.toJSONSchema(output, { io: "output" }) as unknown as JsonSchema & Parameters<typeof defineAgent>[0]["outputSchema"],
  });
}
