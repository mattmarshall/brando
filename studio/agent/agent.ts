import { defineAgent } from "eve";

import { contextWindowTokens, directorModel } from "./lib/model";

/**
 * The creative director.
 *
 * A ROUTER, DELIBERATELY, like humblebrag's root agent. It reads the brief,
 * delegates to the studio, assembles what comes back and submits it once. It
 * writes no brand content of its own — the moment a director starts choosing
 * hex codes, the colorist's contrast loop and the schema that forces it are
 * both bypassed, and the brand is whatever one model felt like in one pass.
 * That is precisely the `StudioService.ProposeSpec` this app replaces.
 *
 * `experimental.tasks` is on because `build_package` is a background tool: a
 * full catalog render runs CSG, rasterization at every icon size and a LaTeX
 * pass, and eve's durable task machinery is the right home for that rather than
 * the webhook-and-cron protocol humblebrag had to hand-roll around an external
 * GPU service.
 */
export default defineAgent({
  model: directorModel,
  modelContextWindowTokens: contextWindowTokens,
  experimental: { tasks: true },
});
