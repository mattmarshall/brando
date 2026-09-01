#!/usr/bin/env python3
"""A Connect door onto the same servicers gRPC serves. The third driver that isn't one.

WHY THIS EXISTS. The studio's agents need contrast, stylesheets and marks, and all
of it lives in `marklib`. Reaching it means a network call to this service, and a
gRPC server is a process with a lifetime — a container, a host, a thing to keep
running. The RPCs the agency actually calls need none of that: `CheckContrast`,
`RenderTheme`, `RenderMark`, `CheckCatalog` and `CritiqueSpec` are pure functions
of their request, touching no `Store`. A process with a lifetime is the wrong shape
for work that has none.

Connect's unary protocol is `POST /<package>.<Service>/<Method>` with the message
as a JSON body and no envelope, which is to say: an ordinary HTTP request that any
serverless function can answer. So this is the same service, reachable without a
server.

THE THING THIS MUST NOT BECOME IS A SECOND IMPLEMENTATION. brando has spent three
releases removing those — a palette authored five times, four incompatible fit
formulas, a gradient running one way in the icon and the other on the site. So
this module contains no logic. It routes a path to a method on the SAME
`RenderServicer` and `StudioServicer` instances `serve()` registers, converts
through `json_format` in both directions, and translates a gRPC status into a
Connect one. Every answer it gives was computed by the code the Bazel rules run.

`json_format` rather than hand-written dict shuffling is deliberate. proto3-JSON is
camelCase and this repo's wire format is snake_case; the one time that was handled
by hand, `spec.display_name` silently vanished from a rendered package and every
structure test passed because they checked paths rather than field naming.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional, Tuple

import grpc
from google.protobuf import json_format

from brando.v1 import brand_service_pb2 as pb


class _Aborted(Exception):
    """A deliberate refusal, carrying the status the servicer chose."""

    def __init__(self, code: grpc.StatusCode, details: str):
        super().__init__(details)
        self.code = code
        self.details = details


class _Context:
    """Enough of `grpc.ServicerContext` for a servicer that only ever aborts.

    THE SERVICERS ARE UNCHANGED, so this has to satisfy what they actually use.
    Across all 24 abort sites that is `abort()` and nothing else — plus `code()`,
    which `_log_unhandled` reads to tell a deliberate refusal from a crash. Both
    are here; anything else a servicer might reach for is absent on purpose, so a
    method that grows a dependency on the real context fails loudly here rather
    than behaving differently over one transport than the other.
    """

    def __init__(self):
        self._code: Optional[grpc.StatusCode] = None

    def abort(self, code: grpc.StatusCode, details: str):
        self._code = code
        raise _Aborted(code, details)

    def code(self):
        return self._code


# gRPC status -> (Connect error code, HTTP status). From the Connect protocol's
# own mapping table; the HTTP status is what a client without Connect support
# sees, so it is worth being right rather than uniformly 500.
_STATUS = {
    grpc.StatusCode.INVALID_ARGUMENT: ("invalid_argument", 400),
    grpc.StatusCode.NOT_FOUND: ("not_found", 404),
    grpc.StatusCode.ALREADY_EXISTS: ("already_exists", 409),
    grpc.StatusCode.PERMISSION_DENIED: ("permission_denied", 403),
    grpc.StatusCode.FAILED_PRECONDITION: ("failed_precondition", 412),
    grpc.StatusCode.ABORTED: ("aborted", 409),
    grpc.StatusCode.UNIMPLEMENTED: ("unimplemented", 501),
    grpc.StatusCode.UNAVAILABLE: ("unavailable", 503),
    grpc.StatusCode.INTERNAL: ("internal", 500),
}

# What this door serves, and nothing else.
#
# EVERY ENTRY IS STATELESS. That is the property that lets the whole service
# answer from a function with no process behind it, and it is a property of these
# five methods rather than of the service — so the set is written down rather
# than inferred, and asking for anything outside it gets a reason instead of a
# confusing failure against an empty in-memory Store.
_STATELESS = {
    "brando.v1.RenderService/CheckContrast": ("render", "CheckContrast", pb.CheckContrastRequest),
    "brando.v1.RenderService/RenderTheme": ("render", "RenderTheme", pb.RenderThemeRequest),
    "brando.v1.RenderService/RenderMark": ("render", "RenderMark", pb.RenderMarkRequest),
    "brando.v1.RenderService/CheckCatalog": ("render", "CheckCatalog", pb.CheckCatalogRequest),
    "brando.v1.StudioService/CritiqueSpec": ("studio", "CritiqueSpec", pb.CritiqueSpecRequest),
}

# Declared by the protos and deliberately not served here, with the reason. A
# caller that reaches one should be told which door to use, not handed an empty
# answer from a Store that is discarded when the function returns.
_STATEFUL_REASON = (
    "%s needs stored brand state, and this deployment answers from a stateless "
    "function with no Store behind it. Use the gRPC service "
    "(`bazel run //service:server`) for the resource-oriented surface."
)


def _servicers():
    """The same servicers `serve()` registers, built once per process.

    Imported inside the function because `service.server` pulls the whole gRPC
    stack, and the module docstring's claim — that nothing here computes anything
    — only holds if this file stays a router.
    """
    from service import server as srv

    store = srv.Store()
    return {
        "render": srv.RenderServicer(store),
        "studio": srv.StudioServicer(store, srv.Studio()),
    }


_CACHED: Dict[str, object] = {}


# Connect's two unary encodings. The generated TypeScript client defaults to
# BINARY, so a door that only spoke JSON would answer every request with an empty
# message and a 200 — which is exactly how this first behaved, and is worse than
# an error because it looks like the service simply found nothing.
_JSON = "application/json"
_PROTO = "application/proto"


def handle(method: str, path: str, body: bytes,
           content_type: str = _PROTO) -> Tuple[int, Dict[str, str], bytes]:
    """One Connect request. Returns `(status, headers, body)`.

    Transport-shaped rather than framework-shaped so the WSGI adapter below and
    the tests call exactly the same thing — a handler only reachable through a
    web server is a handler nobody tests.

    The response is encoded the way the request was. JSON stays supported even
    though nothing defaults to it, because a service you cannot `curl` is a
    service you cannot diagnose from a deployment log.
    """
    if method != "POST":
        # Connect supports GET for side-effect-free methods; nothing here is
        # marked idempotent, so POST is the whole protocol surface.
        return _error("unimplemented", "Connect unary requires POST", 405)

    route = path.strip("/")
    if route.startswith("api/brando/"):
        route = route[len("api/brando/"):]

    entry = _STATELESS.get(route)
    if entry is None:
        known = ", ".join(sorted(_STATELESS))
        if "/" in route:
            return _error("unimplemented", _STATEFUL_REASON % route + " Served here: " + known, 501)
        return _error("not_found", "no such method %r. Served here: %s" % (route, known), 404)

    kind, method_name, request_class = entry
    if not _CACHED:
        _CACHED.update(_servicers())

    as_json = _JSON in (content_type or "")
    try:
        request = request_class()
        if body:
            if as_json:
                json_format.Parse(body.decode("utf-8"), request)
            else:
                request.ParseFromString(body)
    except (json_format.ParseError, UnicodeDecodeError) as cause:
        # The caller's error, and naming the field is the whole value of having a
        # schema. A malformed MarkProgram should say which part is wrong.
        return _error("invalid_argument", str(cause), 400)
    except Exception as cause:  # a truncated or non-protobuf body
        return _error("invalid_argument", "could not decode the request: %s" % cause, 400)

    context = _Context()
    try:
        response = getattr(_CACHED[kind], method_name)(request, context)
    except _Aborted as aborted:
        code, status = _STATUS.get(aborted.code, ("internal", 500))
        return _error(code, aborted.details, status)

    if as_json:
        # camelCase, because that is what proto3-JSON is and what a generated
        # client expects. The snake_case convention this repo holds elsewhere is
        # about the .brando manifest, which Starlark reads; it is not the wire
        # format between two generated clients.
        payload = json_format.MessageToJson(
            response, preserving_proto_field_name=False, indent=None).encode("utf-8")
        return 200, {"content-type": _JSON}, payload
    return 200, {"content-type": _PROTO}, response.SerializeToString()


def _error(code: str, message: str, status: int):
    body = json.dumps({"code": code, "message": message}).encode("utf-8")
    return status, {"content-type": "application/json"}, body


def _read_body(environ) -> bytes:
    """The request body, with or without a Content-Length.

    THE CLIENT SENDS CHUNKED. `@connectrpc/connect-node` streams the request, so
    there is no `Content-Length` and a reader that trusts one reads zero bytes —
    which parses as an empty message, renders nothing, and returns 200. That is
    the worst failure available here: it looks exactly like a service that
    correctly found no contrast problems.
    """
    length = environ.get("CONTENT_LENGTH")
    stream = environ["wsgi.input"]
    if length:
        try:
            return stream.read(int(length))
        except ValueError:
            pass
    # No length: read to EOF. A conforming host has already dechunked by here.
    return stream.read()


def app(environ, start_response):
    """WSGI, so this runs under any Python host without an adapter.

    WSGI rather than a framework: the whole surface is one POST with a proto or
    JSON body, and a dependency that exists to parse that would be a dependency
    to keep current for no gain.
    """
    body = _read_body(environ)

    status, headers, payload = handle(
        environ.get("REQUEST_METHOD", "GET"),
        environ.get("PATH_INFO", "/"),
        body,
        environ.get("CONTENT_TYPE", _PROTO),
    )
    reason = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
              409: "Conflict", 412: "Precondition Failed", 501: "Not Implemented",
              503: "Service Unavailable"}.get(status, "Internal Server Error")
    start_response("%d %s" % (status, reason),
                   list(headers.items()) + [("content-length", str(len(payload)))])
    return [payload]


class _Handler(BaseHTTPRequestHandler):
    """A local Connect server that dechunks, because the real client chunks.

    NOT `wsgiref`, which is what this used first. `wsgiref.simple_server` does
    not implement chunked request bodies at all — it hands the raw framing to the
    application, or nothing — so proving the door against it would have proved
    the door against a client nobody uses. A local server that accepts a
    different wire format from the deployed one is a local server that lies.
    """

    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = self.headers.get("Content-Length")
        if length:
            body = self.rfile.read(int(length))
        elif (self.headers.get("Transfer-Encoding") or "").lower() == "chunked":
            body = self._read_chunked()
        else:
            body = b""

        status, headers, payload = handle(
            "POST", self.path, body, self.headers.get("Content-Type", _PROTO))
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_chunked(self) -> bytes:
        chunks = []
        while True:
            line = self.rfile.readline().strip()
            size = int(line.split(b";")[0] or b"0", 16)
            if size == 0:
                self.rfile.readline()  # the trailing CRLF
                break
            chunks.append(self.rfile.read(size))
            self.rfile.readline()
        return b"".join(chunks)

    def log_message(self, fmt, *args):
        # One line per call, without the date noise BaseHTTPRequestHandler adds.
        print("connect: " + fmt % args, flush=True)


def serve_http(port: int):
    """A local Connect server, for proving the door without deploying it."""
    return ThreadingHTTPServer(("", port), _Handler)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    server = serve_http(args.port)
    print("brando: Connect on :%d (stateless methods only)" % args.port, flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
