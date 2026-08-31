import { defineSpecialist } from "../../lib/subagent";
import { z } from "zod";
import { metricsSchema, typographySchema } from "../../lib/brand";

export default defineSpecialist(
  "Chooses the typography stacks, the font sources that back them, and the brand's metrics.",
  z.object({ typography: typographySchema, metrics: metricsSchema }),
);
