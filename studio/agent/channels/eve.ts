import { none } from "eve/channels/auth";
import { eveChannel } from "eve/channels/eve";

/**
 * Unauthenticated, as humblebrag's is, and for the same reason: the studio is
 * a public demonstration of a pipeline, not a store of anyone's data. What it
 * costs is bounded by the rate limit on the persistence route rather than by a
 * credential.
 */
export default eveChannel({ auth: none() });
