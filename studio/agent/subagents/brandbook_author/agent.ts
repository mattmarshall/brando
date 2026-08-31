import { defineSpecialist } from "../../lib/subagent";
import { copySchema } from "../../lib/brand";

export default defineSpecialist(
  "Writes the Copy the office templates and brandbook use, so they stop carrying hardcoded English.",
  copySchema,
);
