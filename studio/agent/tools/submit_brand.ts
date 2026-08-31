import { defineTool } from "eve/tools";

import { brandSpecSchema } from "../lib/brand";

/**
 * The one submission.
 *
 * The app reads the finished brand out of THIS tool's output rather than out of
 * the director's prose — the same thing humblebrag's `submit_workit` does, and
 * for the same reason: a model asked to return JSON in a message will
 * eventually wrap it in a code fence, apologise for the delay, or summarise it.
 * A tool call is structured by construction.
 */
export default defineTool({
  description:
    "Validate and submit the finished brand. Call exactly once, after every specialist has " +
    "returned and the critic has signed off. Pass their results assembled and unchanged: do not " +
    "rewrite, summarise, or add commentary to what a specialist produced.",
  inputSchema: brandSpecSchema,
  outputSchema: brandSpecSchema,
  execute: (spec) => spec,
});
