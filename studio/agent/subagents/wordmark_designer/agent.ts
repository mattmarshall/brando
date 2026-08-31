import { defineSpecialist } from "../../lib/subagent";
import { wordmarkSchema } from "../../lib/brand";

export default defineSpecialist(
  "Specifies the wordmark and the lockup that pairs it with the mark.",
  wordmarkSchema,
);
