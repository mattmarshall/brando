import { defineSpecialist } from "../../lib/subagent";
import { catalogSchema } from "../../lib/brand";

export default defineSpecialist(
  "Declares the Catalog: which artifacts a complete build of this brand produces.",
  catalogSchema,
);
