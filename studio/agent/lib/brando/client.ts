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
import { createConnectTransport, createGrpcTransport } from "@connectrpc/connect-node";

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
  const explicit = process.env.BRANDO_SERVICE_URL?.trim();
  if (explicit) return explicit;

  // THERE IS NO VERCEL_URL FALLBACK, and its absence is the point.
  //
  // Deployed, `BRANDO_SERVICE_URL` is injected by a service BINDING, and a
  // binding is declared by the CALLER — so it exists in a service only if that
  // service's entry in `vercel.json` asks for it. This code runs in two of them:
  // the Next app (for `/api/marks`) and the eve agent (for every tool). Falling
  // back to the deployment's own origin turned a missing binding into a request
  // that goes out to the public internet, gets held by Deployment Protection,
  // and — if it got through — would be handed by the catch-all rewrite to
  // Next.js, which serves no `/brando.v1.*` path. A 404 from the wrong server,
  // where the honest answer is "this service has no binding".
  throw new Error(
    "BRANDO_SERVICE_URL is not set. Deployed, it comes from the `brando` " +
      "service binding, which every calling service must declare in vercel.json — " +
      "if this is a deployment, the service you are running in is missing its " +
      "`bindings` entry. Locally, run the Connect door " +
      "(`python -m service.connect_app --port 8787`) with " +
      "BRANDO_SERVICE_URL=http://localhost:8787, or the gRPC server " +
      "(`bazel run //service:server -- --port 50051`) with " +
      "BRANDO_SERVICE_URL=http://localhost:50051 and BRANDO_TRANSPORT=grpc.",
  );
}

/**
 * Which wire to use.
 *
 * TWO TRANSPORTS, ONE SERVICE, AND THE CLIENTS DO NOT KNOW THE DIFFERENCE. That
 * is the property Connect-ES buys: `agent/lib/brand-tools.ts` and every test
 * above it are written against generated clients, so which of these is in play
 * is a deployment fact rather than an application one.
 *
 * Connect is the default because it is what ships: a stateless function needs no
 * process with a lifetime, and gRPC needs HTTP/2 to something long-running. gRPC
 * stays reachable because it is what `bazel run //service:server` speaks, and
 * what `//service:conformance_test` holds the whole service to.
 */
export function brandoTransportKind(): "connect" | "grpc" {
  return process.env.BRANDO_TRANSPORT?.trim() === "grpc" ? "grpc" : "connect";
}

function transport() {
  const baseUrl = brandoTarget();
  // Every call this client makes is one of the five stateless methods, and those
  // are milliseconds of CSG and string building. A minute is already absurdly
  // generous.
  //
  // It used to be five minutes, which is exactly a serverless platform's own
  // request ceiling — so the platform would have returned a gateway timeout
  // first and the client's error would have blamed the wrong thing. A timeout
  // that fires after the host gives up tells you nothing.
  const defaultTimeoutMs = 60 * 1000;

  if (brandoTransportKind() === "grpc") {
    return createGrpcTransport({ baseUrl, defaultTimeoutMs });
  }
  return createConnectTransport({
    baseUrl,
    // HTTP/1.1 on purpose. The Connect door is an ordinary serverless function,
    // and requiring HTTP/2 of it would put back the constraint this transport
    // exists to remove.
    httpVersion: "1.1",
    defaultTimeoutMs,
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
