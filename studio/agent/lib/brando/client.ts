/**
 * The studio's one connection to brando's deterministic tier.
 *
 * WHY THERE IS NO TYPESCRIPT MARKLIB. Every number this app produces — a
 * contrast ratio, a stylesheet, a rendered mark — comes back over gRPC from the
 * same `marklib` the Bazel rules run. A TypeScript port would be faster to call
 * and would immediately become a second implementation of a contrast gate, and
 * brando's whole history is the cost of second implementations: a palette
 * authored two to five times per brand and already drifted, four incompatible
 * fit formulas, a gradient that ran the other way in the app icon than on the
 * website. `//service:conformance_test` keeps the two existing drivers honest by
 * comparing bytes; a third driver written in another language could not be held
 * to that, so there is not one.
 *
 * The client is generated from the descriptor set `aip_proto_lint` checked, and
 * `npm run proto:check` regenerates and diffs it, so it cannot quietly disagree
 * with the server.
 */
import { createClient, type Client } from "@connectrpc/connect";
import { createGrpcTransport } from "@connectrpc/connect-node";

import { AssetService, BrandService, RenderService, RevisionService, StudioService } from "./gen/brando/v1/brand_service_pb";

/**
 * Where the service is.
 *
 * Read at call time rather than at module load, so a missing variable is an
 * error on the request that needed it and names what to set — not a crash while
 * the app is starting, which is where an environment problem is hardest to
 * attribute.
 */
export function brandoTarget(): string {
  const target = process.env.BRANDO_SERVICE_URL?.trim();
  if (!target) {
    throw new Error(
      "BRANDO_SERVICE_URL is not set. The studio has no deterministic tier " +
        "without it: contrast, stylesheets and marks all come from brando's " +
        "gRPC service. Run it locally with " +
        "`bazel run //service:server -- --port 50051` and set " +
        "BRANDO_SERVICE_URL=http://localhost:50051.",
    );
  }
  return target;
}

/**
 * gRPC over HTTP/2, against the existing `grpcio` server.
 *
 * NOT the Connect protocol, which the Python server does not speak. Connect-ES
 * clients are transport-agnostic, so if outbound HTTP/2 ever turns out to be a
 * problem where this runs, the fix is to put a proxy in front and swap this one
 * function for `createConnectTransport({ httpVersion: "1.1" })` — the generated
 * clients and every tool above them are unchanged.
 */
function transport() {
  return createGrpcTransport({
    baseUrl: brandoTarget(),
    // A brand's full catalog render runs CSG, rasterization at every icon size
    // and a LaTeX pass. The unary calls the agents make are milliseconds; this
    // ceiling is for RenderBrand, which is the one that earns it.
    defaultTimeoutMs: 5 * 60 * 1000,
  });
}

let cached: {
  brands: Client<typeof BrandService>;
  revisions: Client<typeof RevisionService>;
  assets: Client<typeof AssetService>;
  render: Client<typeof RenderService>;
  studio: Client<typeof StudioService>;
} | null = null;

/**
 * The five services, over one transport.
 *
 * Memoised because a serverless invocation may make several calls and there is
 * no reason to dial five times; not memoised across a target change, because
 * nothing changes `BRANDO_SERVICE_URL` mid-process and pretending otherwise
 * would mean carrying a cache key nobody reads.
 */
export function brando() {
  if (cached) return cached;
  const t = transport();
  cached = {
    brands: createClient(BrandService, t),
    revisions: createClient(RevisionService, t),
    assets: createClient(AssetService, t),
    render: createClient(RenderService, t),
    studio: createClient(StudioService, t),
  };
  return cached;
}

/** For tests, which start a server on a fresh port per case. */
export function resetBrandoClient(): void {
  cached = null;
}
