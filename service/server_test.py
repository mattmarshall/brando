"""Round-trip the real server over a real socket.

The unit tests below this cover the renderer and the engine. This covers the part
they cannot: that the protos, the stubs and the servicers actually fit together.
A servicer with a typo'd method name, a field renamed on one side of the wire, a
status code that should be NOT_FOUND and is UNKNOWN — none of those show up in a
function-level test, and all of them are the first thing a client hits.

It starts a server on an ephemeral port rather than mocking the channel, because
mocking the channel would test the mock.
"""

import unittest
from concurrent import futures

import grpc

# Two modules, because the DATA and the SURFACE are two files: BrandSpec and
# ArtifactKind are brand.proto's, everything request-shaped is
# brand_service.proto's. That split is deliberate -- see brand_service.proto.
from brando.v1 import brand_pb2 as data
from brando.v1 import brand_service_pb2 as pb
from brando.v1 import brand_service_pb2_grpc as pb_grpc
from service import server as srv


def _spec(brand_id="t", accent="#1B7A55"):
    spec = data.BrandSpec(id=brand_id, display_name=brand_id)
    spec.theme.light.bg = "#FFFFFF"
    spec.theme.light.fg = "#111111"
    spec.theme.light.accent = accent
    spec.theme.light.on_accent = "#FFFFFF"
    spec.theme.dark.bg = "#111111"
    spec.theme.dark.fg = "#FFFFFF"
    spec.theme.dark.accent = "#7FD9AF"
    spec.theme.dark.on_accent = "#0B1F17"
    return spec


def _spec_with_program(brand_id="p"):
    """A spec whose mark is DATA rather than a label naming code.

    Two squares and a union: enough to be a real program and short enough that
    what is being tested is the refusal boundary rather than the geometry, which
    `//examples:*_program_parity` covers against real brands.
    """
    spec = _spec(brand_id)
    program = spec.mark.program
    program.canvas = 64
    program.params.add(name="w", value="10")
    shape = program.shapes.add(name="body")
    shape.rect.x0 = "0"
    shape.rect.y0 = "0"
    shape.rect.x1 = "w"
    shape.rect.y1 = "w"
    program.fit.bounds_of = "body"
    program.fit.pad = "0.1"
    layer = program.layers.add(name="body", shape="body")
    layer.fill.light.theme.mode = "light"
    layer.fill.light.theme.role = "fg"
    program.variants.add(name="flat", mode="light")
    return spec


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.store = srv.Store()
        self.server = srv.serve(0, store=self.store)
        # add_insecure_port(0) picks a port; ask the server which one rather than
        # guessing one and racing whatever else on the machine wants it.
        self.port = self.server.add_insecure_port("[::]:0")
        self.server.start()
        self.channel = grpc.insecure_channel("localhost:%d" % self.port)
        self.brands = pb_grpc.BrandServiceStub(self.channel)
        self.revisions = pb_grpc.RevisionServiceStub(self.channel)
        self.render = pb_grpc.RenderServiceStub(self.channel)
        self.studio = pb_grpc.StudioServiceStub(self.channel)
        self.assets = pb_grpc.AssetServiceStub(self.channel)

    def tearDown(self):
        self.channel.close()
        self.server.stop(grace=0)

    def _create(self, brand_id="t", accent="#1B7A55"):
        brand = pb.Brand()
        brand.spec.CopyFrom(_spec(brand_id, accent))
        return self.brands.CreateBrand(
            pb.CreateBrandRequest(brand_id=brand_id, brand=brand))

    def test_create_then_get(self):
        created = self._create()
        self.assertEqual("brands/t", created.name)
        got = self.brands.GetBrand(pb.GetBrandRequest(name="brands/t"))
        self.assertEqual("#1B7A55", got.spec.theme.light.accent)

    def test_a_missing_brand_is_NOT_FOUND(self):
        """Not UNKNOWN. A client cannot retry sensibly on a status the server
        chose by accident."""
        with self.assertRaises(grpc.RpcError) as ctx:
            self.brands.GetBrand(pb.GetBrandRequest(name="brands/nope"))
        self.assertEqual(grpc.StatusCode.NOT_FOUND, ctx.exception.code())

    def test_a_malformed_resource_name_is_INVALID_ARGUMENT(self):
        with self.assertRaises(grpc.RpcError) as ctx:
            self.brands.GetBrand(pb.GetBrandRequest(name="not-a-resource-name"))
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctx.exception.code())

    def test_creating_twice_is_ALREADY_EXISTS(self):
        self._create()
        with self.assertRaises(grpc.RpcError) as ctx:
            self._create()
        self.assertEqual(grpc.StatusCode.ALREADY_EXISTS, ctx.exception.code())

    def test_update_advances_the_revision_and_keeps_the_old_one(self):
        first = self._create()
        updated = pb.Brand()
        updated.CopyFrom(first)
        updated.spec.theme.light.accent = "#7A2E52"
        self.brands.UpdateBrand(pb.UpdateBrandRequest(brand=updated))

        revisions = self.revisions.ListBrandRevisions(
            pb.ListBrandRevisionsRequest(parent="brands/t")).brand_revisions
        self.assertEqual(2, len(revisions))
        # The point of keeping history: the old palette is still answerable.
        self.assertEqual("#1B7A55", revisions[0].spec.theme.light.accent)
        self.assertEqual("#7A2E52", revisions[1].spec.theme.light.accent)

    def test_a_stale_etag_is_ABORTED(self):
        """Two editors and one palette is the ordinary case for a brand, and
        last-write-wins loses somebody's work with no signal."""
        first = self._create()
        stale = pb.Brand()
        stale.CopyFrom(first)
        stale.spec.theme.light.accent = "#000000"
        self.brands.UpdateBrand(pb.UpdateBrandRequest(brand=stale))

        second = pb.Brand()
        second.CopyFrom(first)  # still carries the ORIGINAL etag
        second.spec.theme.light.accent = "#FFFFFF"
        with self.assertRaises(grpc.RpcError) as ctx:
            self.brands.UpdateBrand(pb.UpdateBrandRequest(brand=second))
        self.assertEqual(grpc.StatusCode.ABORTED, ctx.exception.code())

    def test_rollback_creates_a_new_revision_rather_than_truncating(self):
        first = self._create()
        changed = pb.Brand()
        changed.CopyFrom(first)
        changed.spec.theme.light.accent = "#7A2E52"
        self.brands.UpdateBrand(pb.UpdateBrandRequest(brand=changed))

        rolled = self.revisions.RollbackBrand(
            pb.RollbackBrandRequest(name="brands/t", revision_id="r1"))
        self.assertEqual("#1B7A55", rolled.spec.theme.light.accent)

        revisions = self.revisions.ListBrandRevisions(
            pb.ListBrandRevisionsRequest(parent="brands/t")).brand_revisions
        self.assertEqual(3, len(revisions), "the rollback should be recorded, not hidden")

    def test_deleting_a_brand_with_revisions_needs_force(self):
        self._create()
        with self.assertRaises(grpc.RpcError) as ctx:
            self.brands.DeleteBrand(pb.DeleteBrandRequest(name="brands/t"))
        self.assertEqual(grpc.StatusCode.FAILED_PRECONDITION, ctx.exception.code())
        self.brands.DeleteBrand(pb.DeleteBrandRequest(name="brands/t", force=True))

    def test_render_returns_the_derivable_artifacts(self):
        self._create()
        op = self.render.RenderBrand(pb.RenderBrandRequest(name="brands/t"))
        self.assertTrue(op.done)
        response = pb.RenderBrandResponse()
        op.response.Unpack(response)
        names = {a.name for a in response.brand_package.assets}
        self.assertIn("theme.css", names)
        self.assertIn("theme.json", names)

    def test_a_generator_mark_is_still_refused_with_a_reason(self):
        """The refusal that made this service honest, narrowed rather than lifted.

        A `MarkSpec.generator` is a Bazel label naming code in a repo, and
        running caller-supplied code is remote code execution -- so this must
        still SAY it cannot draw one, rather than returning a package quietly
        missing it. What changed in 0.6.0 is only which marks fall under it: the
        test below is the other half, and the two together are the whole
        invariant.
        """
        self._create()
        with self.assertRaises(grpc.RpcError) as ctx:
            self.render.RenderBrand(pb.RenderBrandRequest(
                name="brands/t", kinds=[data.ARTIFACT_KIND_MARK_SVG]))
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctx.exception.code())
        self.assertIn("remote code execution", ctx.exception.details())

    def test_a_program_mark_is_rendered(self):
        """The other half: a spec that CONTAINS its drawing gets one.

        Executing a MarkProgram is evaluation over a closed vocabulary with no
        assignment, no recursion and no unbounded loop, which is why it does not
        reopen the argument above.
        """
        brand = pb.Brand()
        brand.spec.CopyFrom(_spec_with_program("p"))
        self.brands.CreateBrand(pb.CreateBrandRequest(brand_id="p", brand=brand))
        op = self.render.RenderBrand(pb.RenderBrandRequest(
            name="brands/p", kinds=[data.ARTIFACT_KIND_MARK_SVG]))
        response = pb.RenderBrandResponse()
        op.response.Unpack(response)
        names = {a.name for a in response.brand_package.assets}
        self.assertIn("mark_flat.svg", names)
        self.assertIn("mark_flat.body.svg", names)

    def test_render_mark_executes_a_program_that_was_never_stored(self):
        """An author iterating on geometry has no brand to name yet."""
        spec = _spec_with_program()
        response = self.render.RenderMark(pb.RenderMarkRequest(
            program=spec.mark.program, theme=spec.theme))
        names = {f.name for f in response.files}
        self.assertIn("mark_flat.svg", names)
        self.assertTrue(all(f.content.startswith(b"<?xml") or
                            f.content.startswith(b"<svg") for f in response.files))

    def test_a_malformed_program_is_the_callers_error(self):
        """Naming which part is wrong is the whole value of having a schema.

        Flattening it to INTERNAL would leave an author with 'something went
        wrong' and a program they cannot debug.
        """
        spec = _spec_with_program()
        spec.mark.program.shapes[0].rect.x1 = "w + nope"
        with self.assertRaises(grpc.RpcError) as ctx:
            self.render.RenderMark(pb.RenderMarkRequest(
                program=spec.mark.program, theme=spec.theme))
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctx.exception.code())
        self.assertIn("nope", ctx.exception.details())

    def test_render_brand_renders_the_declared_catalog(self):
        """An empty `kinds` means the brand's Catalog, which is what the proto
        says and what this method used not to do -- it ignored `spec.catalog`
        entirely and fell back to whatever the service could derive."""
        brand = pb.Brand()
        brand.spec.CopyFrom(_spec("c"))
        brand.spec.catalog.kinds.append(data.ARTIFACT_KIND_THEME_CSS)
        self.brands.CreateBrand(pb.CreateBrandRequest(brand_id="c", brand=brand))
        op = self.render.RenderBrand(pb.RenderBrandRequest(name="brands/c"))
        response = pb.RenderBrandResponse()
        op.response.Unpack(response)
        names = {a.name for a in response.brand_package.assets}
        self.assertEqual({"theme.css"}, names)

    def test_check_contrast_is_arithmetic_and_needs_no_brand(self):
        spec = _spec(accent="#EEEEEE")  # unreadable on white, on purpose
        response = self.render.CheckContrast(pb.CheckContrastRequest(theme=spec.theme))
        pairs = {(f.foreground_role, f.background_role) for f in response.contrast}
        self.assertIn(("on_accent", "accent"), pairs)

    def test_render_theme_returns_the_contrast_it_was_not_asked_for(self):
        """A caller who has to request the check separately is a caller who will
        forget to."""
        spec = _spec(accent="#EEEEEE")
        response = self.render.RenderTheme(pb.RenderThemeRequest(theme=spec.theme))
        self.assertIn("--brand-accent", response.css)
        self.assertTrue(response.contrast)

    def test_check_catalog_reports_only_what_is_missing(self):
        """A Catalog is the FLOOR: shipping more than declared stays legal."""
        spec = _spec()
        spec.catalog.kinds.append(data.ARTIFACT_KIND_THEME_CSS)
        spec.catalog.kinds.append(data.ARTIFACT_KIND_MARK_SVG)
        response = self.render.CheckCatalog(pb.CheckCatalogRequest(
            spec=spec, present=[data.ARTIFACT_KIND_THEME_CSS,
                                data.ARTIFACT_KIND_THEME_JSON]))
        self.assertEqual([data.ARTIFACT_KIND_MARK_SVG], list(response.missing))

    def test_critique_spec_needs_no_saved_brand(self):
        """Requiring a save first would make every rejected draft a permanent
        revision, which is the opposite of what a history is for."""
        response = self.studio.CritiqueSpec(pb.CritiqueSpecRequest(spec=_spec()))
        self.assertTrue(response.critiques)
        self.assertEqual("", response.model_id)

    def test_a_critique_carries_the_contrast_it_computed(self):
        """`Studio.critique` has always computed these and the response has
        always had a field for them; nothing carried them across, so the half of
        the answer that is arithmetic never reached a caller."""
        self._create(brand_id="u", accent="#EEEEEE")
        op = self.studio.CritiqueBrand(pb.CritiqueBrandRequest(name="brands/u"))
        response = pb.CritiqueBrandResponse()
        op.response.Unpack(response)
        self.assertTrue(response.contrast)

    def test_draft_copy_is_served_rather_than_unimplemented(self):
        """Declared in the proto since 0.3.0 and absent from the servicer, so it
        returned UNIMPLEMENTED while the service advertised it."""
        self._create()
        op = self.studio.DraftCopy(pb.DraftCopyRequest(name="brands/t"))
        self.assertTrue(op.done)

    def test_asset_service_is_registered(self):
        """Four of five services were wired. Every method here returned
        UNIMPLEMENTED while the proto declared them."""
        self._create()
        self.render.RenderBrand(pb.RenderBrandRequest(name="brands/t"))
        response = self.assets.ListBrandAssets(
            pb.ListBrandAssetsRequest(parent="brands/t"))
        ids = {a.logical_id for a in response.brand_assets}
        self.assertIn("theme.css", ids)
        one = self.assets.GetBrandAsset(pb.GetBrandAssetRequest(
            name="brands/t/assets/theme.css"))
        self.assertEqual("text/css", one.media_type)
        self.assertTrue(one.sha256)

    def test_resolving_an_asset_uri_refuses_to_invent_one(self):
        """Returning a plausible URL would be the worst outcome available: a
        caller fetches it, gets nothing, and cannot tell a broken asset from a
        service that was never hosting one."""
        self._create()
        self.render.RenderBrand(pb.RenderBrandRequest(name="brands/t"))
        with self.assertRaises(grpc.RpcError) as ctx:
            self.assets.ResolveBrandAssetUri(pb.ResolveBrandAssetUriRequest(
                name="brands/t/assets/theme.css"))
        self.assertEqual(grpc.StatusCode.FAILED_PRECONDITION, ctx.exception.code())

    def test_critique_reports_no_model_when_none_is_configured(self):
        """The empty model_id is how a caller tells a placeholder from a model's
        opinion. With no BRANDO_MODEL_ID set -- which is the test environment and
        should be -- it must be empty."""
        self._create()
        op = self.studio.CritiqueBrand(pb.CritiqueBrandRequest(name="brands/t"))
        meta = pb.StudioMetadata()
        op.metadata.Unpack(meta)
        self.assertEqual("", meta.model_id)


if __name__ == "__main__":
    unittest.main()


class PackageTest(ServerTest):
    """The archive a render produces must be the archive rules_brand consumes.

    A service that emitted a *nearly* correct archive would fail in the consumer,
    inside a repository rule, during loading -- about the worst place a format
    error can surface, because the error names a checksum or a missing file
    rather than the producer.
    """

    def _render(self):
        op = self.render.RenderBrand(pb.RenderBrandRequest(name="brands/t"))
        response = pb.RenderBrandResponse()
        op.response.Unpack(response)
        return response

    def test_a_render_produces_a_real_archive(self):
        import io
        import zipfile

        self._create()
        self._render()
        _digest, archive = self.store.get_package("t")
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            names = set(z.namelist())
        # Exactly what rules_brand's repo rule opens: the JSON manifest it can
        # actually parse (Starlark has json.decode and no proto runtime), the
        # binpb for anything that does, and content-addressed blobs.
        self.assertIn("brand.json", names)
        self.assertIn("brand.binpb", names)
        self.assertTrue([n for n in names if n.startswith("assets/")])

    def test_the_manifest_and_the_archive_agree_about_every_blob(self):
        """The disagreement no consumer could diagnose: a manifest naming a path
        the archive does not contain. `_blob_path` is imported from pack_brand
        rather than reimplemented precisely to make this impossible."""
        import io
        import json as _json
        import zipfile

        self._create()
        self._render()
        _digest, archive = self.store.get_package("t")
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            manifest = _json.loads(z.read("brand.json"))
            names = set(z.namelist())
        self.assertTrue(manifest["assets"], "the manifest lists no assets")
        for asset in manifest["assets"]:
            self.assertIn(asset["path"], names,
                          "%s points at a blob the archive lacks" % asset["name"])

    def test_the_response_pin_matches_the_stored_bytes(self):
        """The integrity a caller would paste has to describe what was stored.
        A mismatch resolves and then fails the consumer's fetch with what reads
        as a corrupted download."""
        import base64
        import hashlib

        self._create()
        response = self._render()
        _digest, archive = self.store.get_package("t")
        expected = "sha256-" + base64.b64encode(
            hashlib.sha256(archive).digest()).decode("ascii")
        self.assertEqual(expected, response.package_integrity)

    def test_rendering_twice_produces_identical_bytes(self):
        """Deterministic, like the build path: an unchanged brand must not churn
        every downstream pin for nothing."""
        self._create()
        self._render()
        first = self.store.get_package("t")[1]
        self._render()
        self.assertEqual(first, self.store.get_package("t")[1])

    def test_the_manifest_uses_PROTO_field_names_not_camelCase(self):
        """The bug the structure tests could not see.

        MessageToDict emits camelCase by default; the .brando manifest uses proto
        field names, and rules_brand reads `spec.display_name`. Without
        preserving_proto_field_name the archive unpacks, generates every target,
        and quietly has no brand name -- found only by feeding a service-rendered
        package to rules_brand and noticing an empty DISPLAY_NAME.
        """
        import io
        import json as _json
        import zipfile

        self._create()
        self._render()
        _digest, archive = self.store.get_package("t")
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            manifest = _json.loads(z.read("brand.json"))
        self.assertIn("display_name", manifest["spec"],
                      "the manifest is camelCase; rules_brand reads snake_case")
        self.assertNotIn("displayName", manifest["spec"])
        self.assertEqual("t", manifest["spec"]["display_name"])
