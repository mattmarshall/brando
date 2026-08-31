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
import json
import os
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


def _fill_critiques(target, critiques: List[dict]) -> None:
    for c in critiques:
        target.add(
            subject=c.get("subject", ""),
            finding=c.get("finding", ""),
            suggestion=c.get("suggestion", ""),
            severity=pb.Critique.Severity.Value(
                c.get("severity", "SEVERITY_UNSPECIFIED")),
        )


def _fill_contrast(target, findings: List[dict]) -> None:
    """Copy `render_core.contrast` findings into a repeated ContrastFinding.

    ONE PROJECTION, four call sites. Contrast now travels back from a proposal,
    a critique, a rendered theme and a bare check, and a second copy of this
    loop is a second place to quietly drop `severity` — which is the field that
    decides whether a build fails.
    """
    for finding in findings:
        target.add(
            mode=finding["mode"],
            foreground_role=finding["foreground_role"],
            background_role=finding["background_role"],
            ratio=finding["ratio"],
            minimum=finding["minimum"],
            severity=data.ContrastFinding.Severity.Value(
                "SEVERITY_ERROR" if finding["severity"] == "error" else "SEVERITY_WARN"),
        )


def _brand_id(name: str) -> str:
    """`brands/{brand}` -> `{brand}`, rejecting anything else."""
    parts = name.split("/")
    if len(parts) != 2 or parts[0] != "brands" or not parts[1]:
        raise ValueError("expected brands/{brand}, got %r" % name)
    return parts[1]


def _log_unhandled(fn):
    """grpc turns any unhandled servicer exception into a bare UNKNOWN with no
    detail, which is the least debuggable outcome available. Log it, then let it
    become UNKNOWN -- the point is that the traceback exists somewhere.

    A DELIBERATE `context.abort()` IS NOT AN UNHANDLED EXCEPTION, and it took
    until 0.6.0 for that to matter. `abort()` unwinds by raising a bare
    `Exception` as a sentinel -- not an `RpcError`, so the original guard here
    never caught it -- and every refusal therefore printed a full traceback that
    looked exactly like a crash. With one abort in the service that was a wart;
    with nine it is a log nobody reads, which is worse than no log. `code()` is
    set on the context by `abort()` and by nothing else, so it distinguishes the
    two without reaching into grpc's internals."""
    import functools
    import traceback

    @functools.wraps(fn)
    def wrapped(self, request, context):
        try:
            return fn(self, request, context)
        except Exception:
            deliberate = isinstance(sys.exc_info()[1], grpc.RpcError)
            if not deliberate:
                try:
                    deliberate = context.code() is not None
                except Exception:
                    deliberate = False
            if not deliberate:
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
        _fill_critiques(response.critiques, out["critiques"])
        # The contrast findings used to be dropped here. `Studio.critique`
        # computes them, `CritiqueBrandResponse.contrast` has always had a field
        # for them, and nothing carried them across -- so the half of the answer
        # that is arithmetic rather than opinion never reached a caller, which is
        # exactly the distinction the two fields exist to draw.
        _fill_contrast(response.contrast, out["contrast"])
        return self._done(
            "operations/critique-%s" % brand.name, response,
            pb.StudioMetadata(model_id=out["model_id"], cached=out["cached"]))

    @_log_unhandled
    def CritiqueSpec(self, request, context):
        """The same review, on a draft nobody has saved.

        Unary, unlike its sibling: a critique of an unsaved spec is a dict walk
        with no model configured and one call with one, and requiring a save
        first would make every rejected draft a permanent revision.
        """
        out = self._studio.critique(json_format.MessageToDict(
            request.spec, preserving_proto_field_name=True))
        response = pb.CritiqueSpecResponse(model_id=out["model_id"])
        _fill_critiques(response.critiques, out["critiques"])
        _fill_contrast(response.contrast, out["contrast"])
        return response

    def DraftCopy(self, request, context):
        """Write the prose a brand's Identity is missing.

        DECLARED IN THE PROTO SINCE 0.3.0 AND ABSENT FROM THIS CLASS. Both
        `Engine.draft_copy` and `Studio.draft_copy` existed and were reachable
        from nothing, so the method returned UNIMPLEMENTED while the service
        advertised it. Either serve it or delete it; it is three lines to serve.
        """
        brand = self._store.get(_brand_id(request.name))
        if brand is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such brand")
        out = self._studio.draft_copy(
            json_format.MessageToDict(brand.spec, preserving_proto_field_name=True),
            list(request.fields))
        response = pb.DraftCopyResponse()
        json_format.ParseDict(out["identity"], response.identity,
                              ignore_unknown_fields=True)
        return self._done(
            "operations/draft-copy-%s" % brand.name, response,
            pb.StudioMetadata(model_id=out["model_id"], cached=out["cached"]))


class RenderServicer(pb_grpc.RenderServiceServicer):
    def __init__(self, store: Store):
        self._store = store

    @_log_unhandled
    def RenderBrand(self, request, context):
        brand = self._store.get(_brand_id(request.name))
        if brand is None:
            context.abort(grpc.StatusCode.NOT_FOUND, "no such brand")

        spec_json = json_format.MessageToDict(
            brand.spec, preserving_proto_field_name=True)

        # An empty `kinds` means the brand's declared Catalog, which is what the
        # proto has always said and what this method used not to do -- it fell
        # back to DERIVABLE_KINDS and never read `spec.catalog` at all. So a
        # brand declaring a Catalog got whatever the service happened to make,
        # and the declaration it was measured against everywhere else was
        # ignored here.
        requested = [data.ArtifactKind.Name(k) for k in request.kinds]
        if not requested:
            requested = list((spec_json.get("catalog") or {}).get("kinds", []))
        if not requested:
            requested = list(render_core.renderable_kinds(spec_json))

        missing = render_core.unrenderable(requested, spec_json)
        if missing:
            # Told, not silently short. A caller asking for something this
            # service cannot draw gets an error naming it, rather than a package
            # quietly missing it.
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "this brand cannot produce %s here. %s" % (
                    ", ".join(missing),
                    "Its mark names a generator rather than carrying a "
                    "MarkProgram, and running a caller-supplied generator is "
                    "remote code execution, not a feature."
                    if not render_core.has_program(spec_json)
                    else "This service renders only spec-derivable artifacts."))

        theme = spec_json.get("theme") or {}
        artifacts = render_core.render(theme, kinds=requested)
        if any(k in render_core.PROGRAM_KINDS for k in requested):
            artifacts.update(render_core.render_mark(spec_json))

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
            spec_json,
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


    # ── the deterministic surface ────────────────────────────────────────────
    # Unary, all four. `RenderBrand` is an LRO because it runs rasterization at
    # every icon size and a LaTeX pass; these are microseconds to milliseconds,
    # and wrapping them in an Operation would be ceremony a caller has to unwrap
    # for nothing.

    @_log_unhandled
    def CheckContrast(self, request, context):
        theme = json_format.MessageToDict(
            request.theme, preserving_proto_field_name=True)
        response = pb.CheckContrastResponse()
        _fill_contrast(response.contrast, render_core.contrast(theme))
        return response

    @_log_unhandled
    def RenderTheme(self, request, context):
        theme = json_format.MessageToDict(
            request.theme, preserving_proto_field_name=True)
        response = pb.RenderThemeResponse(
            css=render_core.theme_css(
                theme,
                prefix=request.prefix or "brand",
                selector=request.selector or ":root"))
        # Returned whether or not it is clean. A caller who has to ask separately
        # is a caller who will forget to.
        _fill_contrast(response.contrast, render_core.contrast(theme))
        return response

    @_log_unhandled
    def RenderMark(self, request, context):
        # Assembled as a spec fragment because `render_core.render_mark` takes a
        # spec: one code path executes a program, whether it arrived inside a
        # stored brand or on its own, so the two cannot drift.
        spec = {
            "mark": {"program": json_format.MessageToDict(
                request.program, preserving_proto_field_name=True)},
        }
        if request.HasField("theme"):
            spec["theme"] = json_format.MessageToDict(
                request.theme, preserving_proto_field_name=True)
        try:
            files = render_core.render_mark(
                spec, variants=list(request.variants) or None,
                canvas=request.canvas or None)
        except ValueError as cause:
            # A malformed program is the CALLER's error, and saying which part
            # of it is wrong is the whole value of having a schema. Flattening
            # it to INTERNAL would leave an author with "something went wrong"
            # and a program they cannot debug.
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(cause))

        response = pb.RenderMarkResponse()
        for name, content in sorted(files.items()):
            response.files.add(
                name=name, media_type="image/svg+xml", content=content)
        return response

    @_log_unhandled
    def CheckCatalog(self, request, context):
        declared = [data.ArtifactKind.Name(k) for k in request.spec.catalog.kinds]
        present = {data.ArtifactKind.Name(k) for k in request.present}
        response = pb.CheckCatalogResponse()
        # Declared-minus-present only. A Catalog is the FLOOR, not the ceiling:
        # shipping more than declared is legal, and `//tools:catalog_check` says
        # so in the same words.
        for kind in declared:
            if kind not in present:
                response.missing.append(data.ArtifactKind.Value(kind))
        return response


class AssetServicer(pb_grpc.AssetServiceServicer):
    """A built brand's artifacts, as addressable resources.

    DECLARED SINCE 0.3.0 AND NEVER REGISTERED. `serve()` wired four of the five
    services, so every method here returned UNIMPLEMENTED -- a declaration
    nothing backed, which is the condition `//tools:catalog_check` exists to
    catch one directory over.

    The assets come from the stored package's manifest rather than a second
    index, so what this lists is exactly what the archive contains.
    """

    def __init__(self, store: Store):
        self._store = store

    def _manifest(self, brand_id: str, context):
        stored = self._store.get_package(brand_id)
        if stored is None:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                "brand %r has no built package; call RenderBrand first" % brand_id)
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(stored[1])) as archive:
            return json.loads(archive.read("brand.json"))

    def _assets(self, brand_id: str, context):
        out = []
        for asset in self._manifest(brand_id, context).get("assets", []):
            out.append(pb.BrandAsset(
                name="brands/%s/assets/%s" % (brand_id, asset["name"]),
                logical_id=asset["name"],
                media_type=asset.get("media_type", ""),
                size_bytes=int(asset.get("size_bytes", 0)),
                sha256=asset.get("sha256", ""),
            ))
        return out

    @_log_unhandled
    def ListBrandAssets(self, request, context):
        response = pb.ListBrandAssetsResponse()
        response.brand_assets.extend(self._assets(_brand_id(request.parent), context))
        return response

    @_log_unhandled
    def GetBrandAsset(self, request, context):
        parts = request.name.split("/assets/", 1)
        if len(parts) != 2:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "expected brands/{brand}/assets/{asset}")
        for asset in self._assets(_brand_id(parts[0]), context):
            if asset.logical_id == parts[1]:
                return asset
        context.abort(grpc.StatusCode.NOT_FOUND, "no such asset")

    @_log_unhandled
    def ResolveBrandAssetUri(self, request, context):
        """Where the bytes are -- when there is anywhere for them to be.

        The control plane is gRPC and the data plane is an ordinary URL, which
        is right and is what the proto says. It also means this method cannot
        invent an answer: storage here is in-memory and nothing is deployed, so
        with no base URL configured there is no URL. Returning a plausible one
        would be the worst outcome available -- a caller would fetch it, get
        nothing, and have no way to tell a broken asset from a service that was
        never hosting one.
        """
        base = os.environ.get("BRANDO_ASSET_BASE_URL", "").strip()
        if not base:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "this service has no asset base URL configured "
                "(BRANDO_ASSET_BASE_URL), and its storage is in-memory, so "
                "there is no URL to give you. The asset's metadata is "
                "available from GetBrandAsset.")
        parts = request.name.split("/assets/", 1)
        if len(parts) != 2:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "expected brands/{brand}/assets/{asset}")
        for asset in self._assets(_brand_id(parts[0]), context):
            if asset.logical_id == parts[1]:
                # Content-addressed, so the URL cannot change meaning.
                return pb.ResolveBrandAssetUriResponse(
                    uri="%s/assets/%s" % (base.rstrip("/"), asset.sha256))
        context.abort(grpc.StatusCode.NOT_FOUND, "no such asset")


def serve(port: int, store: Optional[Store] = None) -> grpc.Server:
    store = store or Store()
    studio = Studio()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pb_grpc.add_BrandServiceServicer_to_server(BrandServicer(store), server)
    pb_grpc.add_RevisionServiceServicer_to_server(RevisionServicer(store), server)
    pb_grpc.add_StudioServiceServicer_to_server(StudioServicer(store, studio), server)
    pb_grpc.add_RenderServiceServicer_to_server(RenderServicer(store), server)
    pb_grpc.add_AssetServiceServicer_to_server(AssetServicer(store), server)
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
