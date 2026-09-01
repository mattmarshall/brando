/**
 * Better Auth's own routes: the GitHub redirect, the callback, sign-out.
 *
 * The handler is built per request rather than at module scope, because
 * `toNextJsHandler(auth)` would otherwise construct the auth instance while
 * Next is collecting page data at BUILD time — where none of the deployment
 * environment it needs exists yet.
 */
import { toNextJsHandler } from "better-auth/next-js";

import { getAuth } from "@/lib/auth";

export const runtime = "nodejs";

export function GET(request: Request) {
  return toNextJsHandler(getAuth()).GET(request);
}

export function POST(request: Request) {
  return toNextJsHandler(getAuth()).POST(request);
}
