/**
 * Sign in with GitHub.
 *
 * WHY BETTER AUTH AND NOT eve's `oidc()`. GitHub speaks OAuth2, not OIDC: there
 * is no `id_token` to verify, so none of eve's shipped verifiers apply. The
 * alternative to a library here is hand-writing the authorize redirect, the
 * callback, state and PKCE, the token exchange, a `GET /user` call, a signed
 * cookie, and then a verifier for it — a couple of hundred lines to own forever,
 * for something an auth library exists to do.
 *
 * eve's own web template uses this exact shape with Vercel as the provider; the
 * only change here is which provider.
 *
 * COOKIE, NOT BEARER, and that is the part that pays. `withEve` mounts the agent
 * at `/eve/v1/*` on this same origin, so the browser sends this session cookie on
 * every agent request including the NDJSON stream — `useEveAgent()` needs no
 * `auth` option at all. A bearer scheme would mean putting a real token in
 * client-side JavaScript and refreshing it there.
 */
import { betterAuth } from "better-auth";

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (value) return value;
  // Development gets a placeholder rather than a crash, the way eve's own
  // template does: `next dev` should start without a GitHub OAuth app, and the
  // sign-in button is the thing that fails, visibly, when you press it.
  if (process.env.NODE_ENV === "development") return `development-${name}`;
  throw new Error(
    `${name} is not set. The studio will not start without it: it is a public ` +
      "endpoint that spends model tokens, so there is no sensible unauthenticated " +
      "default to fall back to.",
  );
}

/**
 * Every host this deployment answers on.
 *
 * Preview URLs are per-deployment and per-branch, so a hardcoded base URL is
 * wrong on every preview — which is exactly where you most want to sign in and
 * try something.
 */
function allowedHosts(): string[] {
  if (process.env.NODE_ENV === "development") return ["localhost:*", "127.0.0.1:*"];
  const hosts = [
    process.env.VERCEL_PROJECT_PRODUCTION_URL,
    process.env.VERCEL_BRANCH_URL,
    process.env.VERCEL_URL,
  ].filter((host): host is string => Boolean(host));
  if (hosts.length === 0) {
    // Better Auth would otherwise trust the Host header, which is what makes a
    // callback redirect forgeable. Failing here is the correct outcome: it means
    // this is neither a dev server nor a Vercel deployment, and nothing has said
    // what host it is.
    throw new Error("No trusted deployment hosts are configured");
  }
  return [...new Set(hosts)];
}

/**
 * Built on first use, not on import.
 *
 * WHY LAZY. Every value above is a deployment fact — the secret, the OAuth
 * credentials, the hosts this deployment answers on — and none of them exists
 * while the app is being BUILT. `eve build` evaluates `agent/channels/eve.ts`,
 * which reaches this module, and `next build` imports every route handler to
 * collect its config; constructing at import time made both of those fail with
 * "No trusted deployment hosts are configured", which is a true statement about
 * a build machine and a useless one.
 *
 * So the checks still happen, and still fail loudly — on the first request that
 * needs auth, where the answer ("set GITHUB_CLIENT_SECRET") is actionable.
 */
/**
 * Who may sign in.
 *
 * AUTHENTICATION WITHOUT AUTHORIZATION IS NOT A GATE. Everything else in this
 * file exists because "this endpoint spends model tokens" — and until this
 * function existed, the answer to "whose tokens, spent by whom" was: anyone on
 * GitHub. Proving you have a GitHub account is not a reason to be given a brand
 * agency.
 *
 * Keyed on the GitHub LOGIN rather than the email, because the login is the
 * identifier GitHub guarantees and the one you would type if asked who should
 * have access. An unverified or changed email is not an argument here.
 */
function allowedLogins(): Set<string> {
  const configured = process.env.STUDIO_ALLOWED_LOGINS?.trim();
  const raw = configured && configured.length > 0 ? configured : DEFAULT_ALLOWED_LOGIN;
  return new Set(raw.split(/[,\s]+/).filter(Boolean).map((login) => login.toLowerCase()));
}

/**
 * The repo's owner, as the floor.
 *
 * A default of "nobody" would make a missing variable look like a broken
 * deployment; a default of "everybody" is the hole this closes. The owner is
 * the one answer that is right when nothing has been configured.
 */
const DEFAULT_ALLOWED_LOGIN = "mattmarshall";

function build() {
  return betterAuth({
    baseURL: {
      allowedHosts: allowedHosts(),
      protocol: process.env.NODE_ENV === "development" ? "auto" : "https",
    },
    secret: required("BETTER_AUTH_SECRET"),
    session: {
      expiresIn: 8 * 60 * 60,
      disableSessionRefresh: true,
      cookieCache: { enabled: true, maxAge: 8 * 60 * 60, refreshCache: false, strategy: "jwe" },
    },
    socialProviders: {
      github: {
        clientId: required("GITHUB_CLIENT_ID"),
        clientSecret: required("GITHUB_CLIENT_SECRET"),
        /**
         * The gate, on the one hook that runs every time.
         *
         * `mapProfileToUser` is called from the provider's `getUserInfo`, which
         * is part of the OAuth CALLBACK — so it runs on every sign-in, not only
         * on the first. A `databaseHooks.user.create.before` would not: this
         * deployment has no database, so the user table is per-instance and
         * "create" fires on a schedule nobody controls. Throwing here fails the
         * callback before a session cookie is ever minted.
         */
        mapProfileToUser: (profile: { login?: string }) => {
          const login = profile.login?.toLowerCase();
          if (!login || !allowedLogins().has(login)) {
            throw new Error(
              `${profile.login ?? "that account"} is not on this studio's allowlist. ` +
                "Set STUDIO_ALLOWED_LOGINS to a comma-separated list of GitHub logins.",
            );
          }
          return {};
        },
      },
    },
  });
}

// Typed from `build` rather than from `betterAuth`: the options object is a
// type argument, so `ReturnType<typeof betterAuth>` is a DIFFERENT, wider type
// that this instance is not assignable to.
let instance: ReturnType<typeof build> | undefined;

export function getAuth(): ReturnType<typeof build> {
  instance ??= build();
  return instance;
}

/** The session behind a request, or `null`. The one thing every caller wants. */
export async function sessionFor(headers: Headers) {
  return getAuth().api.getSession({ headers });
}

/**
 * The gate every API route uses.
 *
 * Development is open, matching the pages, so `next dev` works with no GitHub
 * OAuth app. Deployed there is no bypass — `/api/marks` and `/api/contrast`
 * run CSG and a WCAG sweep on caller-supplied input, which is not expensive but
 * is not free either, and an open endpoint is an open endpoint.
 */
export async function signedIn(headers: Headers): Promise<boolean> {
  if (process.env.NODE_ENV === "development") return true;
  return Boolean(await sessionFor(headers));
}
