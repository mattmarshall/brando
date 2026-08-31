import { defineSpecialist } from "../../lib/subagent";
import { identitySchema } from "../../lib/brand";

export default defineSpecialist(
  "Writes the brand's Identity: tagline, positioning, story, voice rules and usage rules.",
  identitySchema,
);
