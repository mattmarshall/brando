import { localDev, vercelOidc, type AuthFn } from "eve/channels/auth";
import { eveChannel } from "eve/channels/eve";

import { sessionFor } from "@/lib/auth";

/**
 * The studio's session, as the agent's caller.
 *
 * This is the whole of the browser-facing auth: the cookie Better Auth set is
 * already on the request, because `withEve` mounts the channel on this origin.
 */
const studioSession: AuthFn<Request> = async (request) => {
  const session = await sessionFor(request.headers);
  if (!session) return null;

  const attributes: Record<string, string> = {
    email: session.user.email,
    name: session.user.name,
  };
  if (session.user.image) attributes.picture = session.user.image;

  return {
    attributes,
    authenticator: "better-auth:github",
    principalId: session.user.id,
    principalType: "user",
  };
};

/**
 * ORDER IS THE POLICY, and `none()` is gone rather than demoted.
 *
 * `routeAuth` walks this list and the first function to return a context wins —
 * so `none()` anywhere in it would halt the walk unconditionally and make
 * everything after it decoration. It used to be the only entry here, which was
 * fine while nothing was deployed and is not fine now: this endpoint spends
 * model tokens.
 *
 * The signed-in human first, then `vercelOidc()` so internal callers and
 * `eve dev <url>` still work, then `localDev()`, which only ever returns a
 * context on a development server and cannot be reached by any header.
 */
export default eveChannel({
  auth: [studioSession, vercelOidc(), localDev()],
});
