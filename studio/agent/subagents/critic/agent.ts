import { defineSpecialist } from "../../lib/subagent";
import { z } from "zod";

export default defineSpecialist(
  "Reviews the assembled brand and reports what contradicts what, keeping opinion separate from arithmetic.",
  z.object({ verdict: z.enum(["ship", "revise"]), findings: z.array(z.object({ subject: z.string().min(1), finding: z.string().min(1), suggestion: z.string().min(1), severity: z.enum(["note", "inconsistent", "blocking"]) })), contrastSummary: z.string().min(1) }),
);
