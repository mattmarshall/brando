import { defineTool } from "eve/tools";

import { briefSchema } from "../lib/brand";

export default defineTool({
  description:
    "Parse and validate the brand id, display name, brief and any already-decided constraints " +
    "before delegating. Call exactly once at the start of every engagement.",
  inputSchema: briefSchema,
  outputSchema: briefSchema,
  execute: (brief) => brief,
});
