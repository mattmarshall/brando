/**
 * Which hosts may mint a session.
 *
 * Better Auth derives `redirect_uri` per request from the Host header and
 * validates it against this list, so the list is the whole of the answer to
 * "who can complete a sign-in on this deployment". Both failure directions are
 * invisible from the outside until someone hits them: a host missing from the
 * list fails sign-in on the published URL, and a list that is too permissive is
 * a redirect somebody else can claim.
 *
 * The case that prompted this file: `brando.marsh.build`. The `VERCEL_*`
 * variables carry a custom domain only when it is the PRODUCTION domain, so a
 * domain attached to a preview branch is in none of them.
 */
import assert from "node:assert/strict";
import test, { afterEach } from "node:test";

import { allowedHosts } from "../lib/auth";

const KEYS = [
  "NODE_ENV",
  "STUDIO_PUBLIC_HOST",
  "VERCEL_PROJECT_PRODUCTION_URL",
  "VERCEL_BRANCH_URL",
  "VERCEL_URL",
] as const;

const saved = new Map(KEYS.map((key) => [key, process.env[key]]));

/**
 * `@types/node` types `NODE_ENV` as read-only, which is a useful rule for app
 * code and the wrong one for a test whose whole subject is how this function
 * behaves per environment. The cast is here, once, rather than at each site.
 */
const env = process.env as Record<string, string | undefined>;

function setEnv(key: string, value: string | undefined) {
  if (value === undefined) delete env[key];
  else env[key] = value;
}

afterEach(() => {
  for (const [key, value] of saved) setEnv(key, value);
});

/** A deployment, as Vercel describes one. */
function deployed(extra: Record<string, string | undefined> = {}) {
  setEnv("NODE_ENV", "production");
  setEnv("STUDIO_PUBLIC_HOST", undefined);
  setEnv("VERCEL_PROJECT_PRODUCTION_URL", "brando-studio.vercel.app");
  setEnv("VERCEL_BRANCH_URL", "brando-studio-git-branch.vercel.app");
  setEnv("VERCEL_URL", "brando-studio-abc123.vercel.app");
  for (const [key, value] of Object.entries(extra)) setEnv(key, value);
}

test("without STUDIO_PUBLIC_HOST the list is exactly what it always was", () => {
  // The change has to be inert when unset: every existing deployment reaches
  // this path, and none of them should notice.
  deployed();
  assert.deepEqual(allowedHosts(), [
    "brando-studio.vercel.app",
    "brando-studio-git-branch.vercel.app",
    "brando-studio-abc123.vercel.app",
  ]);
});

test("a custom domain attached to a preview branch is trusted once named", () => {
  // The failure this exists for: VERCEL_PROJECT_PRODUCTION_URL is still the
  // .vercel.app host, so the domain appears in none of the three.
  deployed({ STUDIO_PUBLIC_HOST: "brando.marsh.build" });
  assert.ok(allowedHosts().includes("brando.marsh.build"));
});

test("a pasted URL is accepted as the host it names", () => {
  // Nobody reads a host out of a URL bar without the scheme coming with it, and
  // `https://brando.marsh.build/` would never match a Host header.
  for (const pasted of [
    "https://brando.marsh.build",
    "https://brando.marsh.build/",
    "http://brando.marsh.build/some/path",
    "  brando.marsh.build  ",
  ]) {
    deployed({ STUDIO_PUBLIC_HOST: pasted });
    assert.ok(
      allowedHosts().includes("brando.marsh.build"),
      `${JSON.stringify(pasted)} should resolve to the bare host`,
    );
  }
});

test("more than one public host can be named", () => {
  deployed({ STUDIO_PUBLIC_HOST: "brando.marsh.build, studio.marsh.build" });
  const hosts = allowedHosts();
  assert.ok(hosts.includes("brando.marsh.build"));
  assert.ok(hosts.includes("studio.marsh.build"));
});

test("naming a host does not drop the deployment's own", () => {
  // The Vercel URLs have to survive: the branch URL is how a preview is opened
  // before any domain points anywhere.
  deployed({ STUDIO_PUBLIC_HOST: "brando.marsh.build" });
  assert.ok(allowedHosts().includes("brando-studio-git-branch.vercel.app"));
});

test("a deployment that is not a deployment is refused, not defaulted", () => {
  // Better Auth would otherwise trust the Host header outright.
  deployed({
    STUDIO_PUBLIC_HOST: undefined,
    VERCEL_PROJECT_PRODUCTION_URL: undefined,
    VERCEL_BRANCH_URL: undefined,
    VERCEL_URL: undefined,
  });
  assert.throws(() => allowedHosts(), /No trusted deployment hosts/);
});

test("STUDIO_PUBLIC_HOST alone is enough to be a configured deployment", () => {
  // Self-hosting outside Vercel: no VERCEL_* at all, one named host.
  deployed({
    STUDIO_PUBLIC_HOST: "brando.marsh.build",
    VERCEL_PROJECT_PRODUCTION_URL: undefined,
    VERCEL_BRANCH_URL: undefined,
    VERCEL_URL: undefined,
  });
  assert.deepEqual(allowedHosts(), ["brando.marsh.build"]);
});

test("development trusts localhost and nothing else", () => {
  deployed({ STUDIO_PUBLIC_HOST: "brando.marsh.build" });
  setEnv("NODE_ENV", "development");
  assert.deepEqual(allowedHosts(), ["localhost:*", "127.0.0.1:*"]);
});
