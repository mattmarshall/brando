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

    def test_asking_for_a_mark_is_refused_with_a_reason(self):
        """The service must SAY it cannot draw a mark, not return a package
        quietly missing one -- the same silent shortfall the Catalog gate exists
        to prevent, arriving through a different door."""
        self._create()
        with self.assertRaises(grpc.RpcError) as ctx:
            self.render.RenderBrand(pb.RenderBrandRequest(
                name="brands/t", kinds=[data.ARTIFACT_KIND_MARK_SVG]))
        self.assertEqual(grpc.StatusCode.INVALID_ARGUMENT, ctx.exception.code())
        self.assertIn("brand-specific geometry", ctx.exception.details())

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
