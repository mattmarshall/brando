import { headers } from "next/headers";

import { sessionFor } from "@/lib/auth";
import { AccountControl, SignIn } from "./studio-auth";
import { Studio } from "./studio";

/**
 * The gate.
 *
 * DEVELOPMENT SKIPS IT, the way eve's template does: a local server has no
 * GitHub OAuth app and requiring one to run `next dev` would mean the first
 * thing anyone does with this repo is configure a third party. Deployed, there
 * is no bypass — this endpoint spends model tokens.
 */
export async function AuthenticatedStudio({ sessionId }: { readonly sessionId?: string }) {
  if (process.env.NODE_ENV === "development") return <Studio sessionId={sessionId} />;

  const session = await sessionFor(await headers());
  if (!session) return <SignIn />;

  return (
    <Studio
      account={
        <AccountControl
          email={session.user.email}
          image={session.user.image}
          name={session.user.name}
        />
      }
      sessionId={sessionId}
    />
  );
}
