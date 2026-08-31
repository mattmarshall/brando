/**
 * Which model each tier of the studio runs on.
 *
 * THE AI GATEWAY, NOT BEDROCK, and the difference from humblebrag is not
 * arbitrary. That app reaches Bedrock through Vercel OIDC because it needs
 * Bedrock's IMAGE models — an avatar and a scene have to come from somewhere.
 * This studio needs no image model at all: every pixel it produces is drawn
 * deterministically by `marklib` from numbers the agents chose. Inheriting the
 * AWS coupling would buy nothing and cost a role, a region and a credential
 * path.
 *
 * TWO TIERS, as humblebrag splits `fallbackTextModelId` from `textModelId`. The
 * creative director routes and assembles; it writes no brand content and does
 * not need the better model. The specialists own the creative voice and do.
 */
export const directorModel =
  process.env.BRANDO_DIRECTOR_MODEL?.trim() || "anthropic/claude-haiku-4.5";

export const specialistModel =
  process.env.BRANDO_SPECIALIST_MODEL?.trim() || "anthropic/claude-opus-4.5";

/** Every agent here shares one window; stated once so the tiers cannot drift. */
export const contextWindowTokens = 200_000;
