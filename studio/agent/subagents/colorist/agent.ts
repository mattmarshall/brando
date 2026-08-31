import { defineSpecialist } from "../../lib/subagent";
import { z } from "zod";
import { paletteSchema } from "../../lib/brand";

export default defineSpecialist(
  "Chooses both palettes, all 14 roles each, and does not stop until brando's contrast gate passes.",
  z.object({ light: paletteSchema, dark: paletteSchema }),
);
