#!/usr/bin/env python3
"""The brando gRPC server.

TRANSPORT ONLY. Every decision that matters is already made below this file:
`render_core` holds the renderer the Bazel rules share, `studio` holds the
engine, its cache and its fail-open behaviour. This translates protos to those
calls and back. Keeping it that thin is what lets the conformance and rails tests
be unit tests over functions rather than integration tests over a socket.

STORAGE IS IN-MEMORY, AND THAT IS A STATEMENT RATHER THAN A TODO. brando is a
personal project, nothing here deploys anywhere yet, and picking a database
before deciding whose infrastructure this runs on would be choosing the answer to
the harder question by accident. `Store` is the seam a real backend replaces --
five methods, no SQL, no ORM.

RUN IT: bazel run //service:server -- --port 50051
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent import futures
from typing import Dict, List, Optional

import grpc
from google.protobuf import empty_pb2, json_format

from brando.v1 import brand_pb2 as data
from brando.v1 import brand_service_pb2 as pb
from brando.v1 import brand_service_pb2_grpc as pb_grpc
from service import render_core
from service.studio import Studio


class Store:
    """In-memory brands and their revisions.

    The seam a real backend replaces. Deliberately small: a brand is a spec and a
    history, and anything more elaborate here would be inventing requirements for
    a service that has not chosen a host.
    """

    def __init__(self):
        self._brands: Dict[str, pb.Brand] = {}
        self._revisions: Dict[str, List[pb.BrandRevision]] = {}
        self._packages: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    def get(self, brand_id: str) -> Optional[pb.Brand]:
        with self._lock:
            return self._brands.get(brand_id)

    def list(self) -> List[pb.Brand]:
        with self._lock:
            # Sorted, so pagination is stable. An unordered list plus a page
            # token is a way to show a caller the same brand twice and skip
            # another, which reads as data loss.
            return [self._brands[k] for k in sorted(self._brands)]

    def put(self, brand_id: str, brand: pb.Brand, description: str = "") -> pb.Brand:
        with self._lock:
            history = self._revisions.setdefault(brand_id, [])
            rev_id = "r%d" % (len(history) + 1)

            stored = pb.Brand()
            stored.CopyFrom(brand)
            stored.name = "brands/%s" % brand_id
            stored.current_revision = rev_id
            # The etag is over the SPEC, not the wrapper: two writes that leave
            # the brand identical should not conflict with each other.
            stored.etag = _spec_etag(brand.spec)

            revision = pb.BrandRevision(
                name="brands/%s/revisions/%s" % (brand_id, rev_id),
                description=description,
            )
            revision.spec.CopyFrom(brand.spec)
            history.append(revision)

            self._brands[brand_id] = stored
            return stored

    def put_package(self, brand_id: str, archive: bytes) -> str:
        """Store a rendered `.brando` and return its digest.

        Content-addressed, so re-rendering an unchanged brand overwrites nothing
        and a URL for a package never changes meaning -- the same property the
        published packages have, kept here so the service does not become the one
        place where a brand's bytes are mutable.
        """
        import hashlib
        digest = hashlib.sha256(archive).hexdigest()
        with self._lock:
            self._packages[brand_id] = (digest, archive)
        return digest

    def get_package(self, brand_id: str):
        with self._lock:
            return self._packages.get(brand_id)

    def revisions(self, brand_id: str) -> List[pb.BrandRevision]:
        with self._lock:
            return list(self._revisions.get(brand_id, []))

    def delete(self, brand_id: str, force: bool) -> None:
        with self._lock:
            if self._revisions.get(brand_id) and not force:
                raise ValueError(
                    "brands/%s has revisions; pass force to delete them with it"
                    % brand_id
                )
            self._brands.pop(brand_id, None)
            self._revisions.pop(brand_id, None)


def _spec_etag(spec) -> str:
    from service.studio import spec_digest
    return spec_digest(json_format.MessageToDict(spec))[:16]


def _brand_id(name: str) -> str:
    """`brands/{brand}` -> `{brand}`, rejecting anything else."""
    parts = name.split("/")
    if len(parts) != 2 or parts[0] != "brands" or not parts[1]:
        raise ValueError("expected brands/{brand}, got %r" % name)
    return parts[1]


def _log_unhandled(fn):
    """grpc turns any unhandled servicer exception into a bare UNKNOWN with no
    detail, which is the least debuggable outcome available. Log it, then let it
    become UNKNOWN -- the point is that the traceback exists somewhere."""
    import functools
    import traceback

    @functools.wraps(fn)
    def wrapped(self, request, context):
        try:
            return fn(self, request, context)
        except Exception:
            if not isinstance(sys.exc_info()[1], grpc.RpcError):
                traceback.print_exc(file=sys.stderr)
            raise

    return wrapped


class BrandServicer(pb_grpc.BrandServiceServicer):
    def __init__(self, store: Store):
        self._store = store

    def GetBrand(self, request, context):
        try:
            brand = self._store.get(_brand_id(request.name))
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        if brand is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such brand: %s" % request.name)
        return brand

    def ListBrands(self, request, context):
        return pb.ListBrandsResponse(brands=self._store.list())

    def CreateBrand(self, request, context):
        if not request.brand_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "brand_id is required")
        if self._store.get(request.brand_id) is not None:
            context.abort(grpc.StatusCode.ALREADY_EXISTS,
                          "brands/%s already exists" % request.brand_id)
        return self._store.put(request.brand_id, request.brand, "created")

    def UpdateBrand(self, request, context):
        try:
            brand_id = _brand_id(request.brand.name)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        current = self._store.get(brand_id)
        if current is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such brand")
        # Optimistic concurrency. Two editors and one palette is the ordinary
        # case for a brand, and last-write-wins loses somebody's work silently.
        if request.brand.etag and request.brand.etag != current.etag:
            context.abort(grpc.StatusCode.ABORTED,
                          "etag mismatch: the brand changed since you read it")
        return self._store.put(brand_id, request.brand, "updated")

    def DeleteBrand(self, request, context):
        try:
            self._store.delete(_brand_id(request.name), request.force)
        except ValueError as exc:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        return empty_pb2.Empty()


class RevisionServicer(pb_grpc.RevisionServiceServicer):
    def __init__(self, store: Store):
        self._store = store

    def ListBrandRevisions(self, request, context):
        try:
            brand_id = _brand_id(request.parent)
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return pb.ListBrandRevisionsResponse(
            brand_revisions=self._store.revisions(brand_id))

    def GetBrandRevision(self, request, context):
        parts = request.name.split("/")
        if len(parts) != 4:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "expected brands/{brand}/revisions/{revision}")
        for revision in self._store.revisions(parts[1]):
            if revision.name == request.name:
                return revision
        context.abort(grpc.StatusCode.NOT_FOUND, "no such revision")

    def RollbackBrand(self, request, context):
        brand_id = _brand_id(request.name)
        target = "brands/%s/revisions/%s" % (brand_id, request.revision_id)
        for revision in self._store.revisions(brand_id):
            if revision.name == target:
                brand = pb.Brand()
                brand.spec.CopyFrom(revision.spec)
                # A rollback creates a NEW revision rather than truncating
                # history: it is an event worth keeping, and rewriting the past
                # makes "why does this look different" unanswerable.
                return self._store.put(
                    brand_id, brand,
                    "rolled back to %s" % request.revision_id)
        context.abort(grpc.StatusCode.NOT_FOUND, "no such revision: %s" % target)


class StudioServicer(pb_grpc.StudioServiceServicer):
    """The model surface.

    These are declared as LROs in the proto and answered INLINE here, because the
    mock engine returns immediately and a queue for work that takes microseconds
    would be theatre. The proto shape is what matters: it is already an
    Operation, so putting a real queue behind a real model is a server change and
    not an API break.
    """

    def __init__(self, store: Store, studio: Studio):
        self._store = store
        self._studio = studio

    def _done(self, name: str, response, metadata):
        from google.longrunning import operations_pb2
        from google.protobuf import any_pb2

        packed = any_pb2.Any()
        packed.Pack(response)
        meta = any_pb2.Any()
        meta.Pack(metadata)
        return operations_pb2.Operation(
            name=name, done=True, response=packed, metadata=meta)

    def ProposeSpec(self, request, context):
        out = self._studio.propose_spec(
            request.brief, request.brand_id,
            json_format.MessageToDict(request.constraints))
        response = pb.ProposeSpecResponse()
        json_format.ParseDict(out["spec"], response.spec, ignore_unknown_fields=True)
        response.rationale = "" if out["model_id"] else \
            "No model configured; this is a deterministic placeholder."
        return self._done(
            "operations/propose-%s" % request.brand_id, response,
            pb.StudioMetadata(model_id=out["model_id"], cached=out["cached"]))

    def CritiqueBrand(self, request, context):
        brand = self._store.get(_brand_id(request.name))
        if brand is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such brand")
        out = self._studio.critique(json_format.MessageToDict(brand.spec))

        response = pb.CritiqueBrandResponse()
        for c in out["critiques"]:
            response.critiques.add(
                subject=c.get("subject", ""),
                finding=c.get("finding", ""),
                suggestion=c.get("suggestion", ""),
                severity=pb.Critique.Severity.Value(
                    c.get("severity", "SEVERITY_UNSPECIFIED")),
            )
        return self._done(
            "operations/critique-%s" % brand.name, response,
            pb.StudioMetadata(model_id=out["model_id"], cached=out["cached"]))


class RenderServicer(pb_grpc.RenderServiceServicer):
    def __init__(self, store: Store):
        self._store = store

    @_log_unhandled
    def RenderBrand(self, request, context):
        brand = self._store.get(_brand_id(request.name))
        if brand is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such brand")

        requested = [data.ArtifactKind.Name(k) for k in request.kinds] or None
        missing = render_core.unrenderable(requested or [])
        if missing:
            # Told, not silently short. A caller asking for a mark gets an error
            # naming what this service cannot draw, rather than a package quietly
            # missing it.
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "this service renders only spec-derivable artifacts; it cannot "
                "produce %s (a mark is brand-specific geometry that lives in a "
                "repo, not in the spec)" % ", ".join(missing))

        theme = json_format.MessageToDict(
            brand.spec.theme, preserving_proto_field_name=True)
        artifacts = render_core.render(theme, kinds=requested)

        # The manifest, as a real BrandPackage. The service HAS a proto runtime,
        # unlike the stdlib-only build path that has to shell out to
        # `protoc --encode`, so it serializes directly.
        manifest = data.BrandPackage()
        manifest.spec.CopyFrom(brand.spec)

        response = pb.RenderBrandResponse()
        # `blob`, not `data`: `data` is the brand_pb2 module imported at the top,
        # and a loop variable of that name makes every earlier reference to it in
        # this function an UnboundLocalError -- which grpc then flattens to a
        # bare UNKNOWN with no detail. Exactly the shadowing that made
        # render_template emit every artifact in dark mode.
        import hashlib
        for logical, blob in sorted(artifacts.items()):
            response.brand_package.assets.add(
                name=logical, size_bytes=len(blob),
                sha256=hashlib.sha256(blob).hexdigest())
        response.brand_package.spec.CopyFrom(brand.spec)
        manifest.CopyFrom(response.brand_package)

        # A REAL archive, in the same format brand_package writes -- so what the
        # service produces is what rules_brand consumes, with no second reader.
        archive = render_core.package(
            # preserving_proto_field_name, because the .brando manifest uses
            # PROTO field names -- `display_name`, `accent_strong` -- and
            # MessageToDict emits camelCase by default. rules_brand reads
            # `spec.display_name`, so without this the service produces an
            # archive that unpacks, generates every target, and quietly has no
            # brand name. Found by feeding a service-rendered package to
            # rules_brand; every structure test passed, because they checked
            # paths rather than field naming.
            json_format.MessageToDict(brand.spec, preserving_proto_field_name=True),
            artifacts,
            brando_version="service",
            manifest_binpb=manifest.SerializeToString(),
        )
        digest = self._store.put_package(_brand_id(request.name), archive)
        response.package_uri = "brands/%s/assets/%s" % (
            _brand_id(request.name), digest[:16])
        response.package_integrity = "sha256-" + __import__("base64").b64encode(
            bytes.fromhex(digest)).decode("ascii")

        from google.longrunning import operations_pb2
        from google.protobuf import any_pb2
        packed = any_pb2.Any()
        packed.Pack(response)
        return operations_pb2.Operation(
            name="operations/render-%s" % brand.name, done=True, response=packed)


def serve(port: int, store: Optional[Store] = None) -> grpc.Server:
    store = store or Store()
    studio = Studio()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pb_grpc.add_BrandServiceServicer_to_server(BrandServicer(store), server)
    pb_grpc.add_RevisionServiceServicer_to_server(RevisionServicer(store), server)
    pb_grpc.add_StudioServiceServicer_to_server(StudioServicer(store, studio), server)
    pb_grpc.add_RenderServiceServicer_to_server(RenderServicer(store), server)
    server.add_insecure_port("[::]:%d" % port)
    return server


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=50051)
    args = ap.parse_args(argv)

    server = serve(args.port)
    server.start()
    print("brando: serving on :%d (storage is in-memory)" % args.port, flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(grace=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
