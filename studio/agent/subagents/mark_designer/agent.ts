import { defineSpecialist } from "../../lib/subagent";
import { z } from "zod";
import { markProgramSchema } from "../../lib/brand";

export default defineSpecialist(
  "Designs the logo as a MarkProgram: parametric geometry that brando executes deterministically.",
  z.object({ program: markProgramSchema, variants: z.array(z.string().min(1)).min(1), layers: z.array(z.string().min(1)).min(1), sizes: z.array(z.number().int()).min(1), packed: z.array(z.string().min(1)).optional() }),
);
