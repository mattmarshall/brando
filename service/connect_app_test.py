#!/usr/bin/env python3
"""Tests for the Connect door.

THE BUG THIS FILE EXISTS FOR was silent. The generated TypeScript client sends
`Content-Type: application/proto` with a CHUNKED body and no `Content-Length`.
A door that read only JSON, or that trusted `Content-Length`, parsed an empty
message, computed an honest answer about nothing, and returned it with a 200.
Every request "succeeded"; every response was empty. That is worse than an error,
because it reads as a service that correctly found no problems.

So the cases below are mostly about the wire, not the logic — the logic is
`marklib`'s and is tested where it lives. What is new here is a transport, and a
transport is exactly the kind of thing that fails by returning something
plausible.
"""
import json
import unittest

from google.protobuf import json_format

from brando.v1 import brand_service_pb2 as pb
from service import connect_app

_THEME = {
    "light": {"bg": "#FFFFFF", "fg": "#111111", "accent": "#EEEEEE", "onAccent": "#FFFFFF"},
    "dark": {"bg": "#111111", "fg": "#FFFFFF", "accent": "#7FD9AF", "onAccent": "#0B1F17"},
}

_PROGRAM = {
    "canvas": 64,
    "params": [{"name": "w", "value": "10"}],
    "shapes": [{"name": "body", "rect": {"x0": "0", "y0": "0", "x1": "w", "y1": "w"}}],
    "fit": {"boundsOf": "body", "pad": "0.1"},
    "layers": [{"name": "body", "shape": "body",
                "fill": {"light": {"theme": {"mode": "light", "role": "fg"}}}}],
    "variants": [{"name": "flat", "mode": "light"}],
}


def _json_call(route, payload):
    status, headers, body = connect_app.handle(
        "POST", route, json.dumps(payload).encode("utf-8"), "application/json")
    return status, json.loads(body or b"{}")


def _binary_call(route, message, response_class):
    """The encoding the real client actually uses."""
    status, headers, body = connect_app.handle(
        "POST", route, message.SerializeToString(), "application/proto")
    if status != 200:
        return status, json.loads(body)
    out = response_class()
    out.ParseFromString(body)
    return status, out


class Routing(unittest.TestCase):
    def test_the_five_stateless_methods_are_served(self):
        """Named rather than inferred, so adding a stateful one is deliberate."""
        self.assertEqual(
            sorted([
                "brando.v1.RenderService/CheckCatalog",
                "brando.v1.RenderService/CheckContrast",
                "brando.v1.RenderService/RenderMark",
                "brando.v1.RenderService/RenderTheme",
                "brando.v1.StudioService/CritiqueSpec",
            ]),
            sorted(connect_app._STATELESS),
        )

    def test_a_stateful_method_is_refused_with_the_reason(self):
        """An empty Store would answer `GetBrand` with NOT_FOUND, which is a lie:
        the brand may well exist, in a process this deployment does not have."""
        status, body = _json_call("/brando.v1.BrandService/GetBrand", {"name": "brands/t"})
        self.assertEqual(501, status)
        self.assertEqual("unimplemented", body["code"])
        self.assertIn("stateless function", body["message"])

    def test_an_unknown_method_lists_what_is_served(self):
        status, body = _json_call("/nope", {})
        self.assertEqual(404, status)
        self.assertIn("CheckContrast", body["message"])

    def test_the_mount_prefix_is_stripped(self):
        """Deployed, the door sits under a path. Connect's own route is the
        fully-qualified method, so the prefix has to come off before dispatch."""
        for route in ("/brando.v1.RenderService/CheckContrast",
                      "/api/brando/brando.v1.RenderService/CheckContrast"):
            with self.subTest(route=route):
                status, _ = _json_call(route, {"theme": _THEME})
                self.assertEqual(200, status)

    def test_get_is_refused(self):
        status, headers, body = connect_app.handle("GET", "/brando.v1.RenderService/CheckContrast", b"")
        self.assertEqual(405, status)


class Encoding(unittest.TestCase):
    def test_binary_in_binary_out(self):
        """The client's default, and the one that failed silently."""
        request = pb.CheckContrastRequest()
        json_format.ParseDict({"theme": _THEME}, request)
        status, response = _binary_call(
            "/brando.v1.RenderService/CheckContrast", request, pb.CheckContrastResponse)
        self.assertEqual(200, status)
        pairs = {(f.foreground_role, f.background_role) for f in response.contrast}
        self.assertIn(("on_accent", "accent"), pairs,
                      "a near-white accent is unreadable; the gate must say so")

    def test_json_in_json_out(self):
        """Kept working so the deployed service can be diagnosed with curl."""
        status, body = _json_call("/brando.v1.RenderService/CheckContrast", {"theme": _THEME})
        self.assertEqual(200, status)
        self.assertTrue(body["contrast"])

    def test_the_response_encoding_matches_the_request(self):
        _, headers, _ = connect_app.handle(
            "POST", "/brando.v1.RenderService/CheckContrast",
            json.dumps({"theme": _THEME}).encode(), "application/json")
        self.assertEqual("application/json", headers["content-type"])

        request = pb.CheckContrastRequest()
        json_format.ParseDict({"theme": _THEME}, request)
        _, headers, _ = connect_app.handle(
            "POST", "/brando.v1.RenderService/CheckContrast",
            request.SerializeToString(), "application/proto")
        self.assertEqual("application/proto", headers["content-type"])

    def test_an_empty_body_is_not_mistaken_for_an_empty_message(self):
        """A request that arrives with no body at all still parses to an empty
        message — that part is correct. What must NOT happen is the same outcome
        for a body the reader failed to collect, which is the chunked bug."""
        status, body = _json_call("/brando.v1.RenderService/CheckContrast", {})
        self.assertEqual(200, status)
        self.assertEqual({}, body, "an empty theme has no roles to check")

    def test_a_non_protobuf_body_is_the_callers_error(self):
        status, headers, body = connect_app.handle(
            "POST", "/brando.v1.RenderService/CheckContrast", b"{not json", "application/json")
        self.assertEqual(400, status)
        self.assertEqual("invalid_argument", json.loads(body)["code"])


class Dispatch(unittest.TestCase):
    """The door returns what the servicers return, and refuses what they refuse."""

    def test_a_mark_program_renders(self):
        status, body = _json_call(
            "/brando.v1.RenderService/RenderMark", {"program": _PROGRAM, "theme": _THEME})
        self.assertEqual(200, status)
        names = {f["name"] for f in body["files"]}
        self.assertIn("mark_flat.svg", names)

    def test_a_theme_role_resolves_through_the_door(self):
        """The fill came from the palette, not from a hex in the program. This is
        the property the whole role-reference design exists for, and it is
        invisible in any test that only checks the SVG parses."""
        status, body = _json_call(
            "/brando.v1.RenderService/RenderMark", {"program": _PROGRAM, "theme": _THEME})
        import base64
        svg = base64.b64decode(
            next(f["content"] for f in body["files"] if f["name"] == "mark_flat.svg")).decode()
        self.assertIn("#111111", svg)

    def test_a_malformed_program_keeps_the_servicers_status(self):
        """INVALID_ARGUMENT, not a 500 — and the message names the bad part."""
        broken = json.loads(json.dumps(_PROGRAM))
        broken["shapes"][0]["rect"]["x1"] = "w + nope"
        status, body = _json_call(
            "/brando.v1.RenderService/RenderMark", {"program": broken, "theme": _THEME})
        self.assertEqual(400, status)
        self.assertEqual("invalid_argument", body["code"])
        self.assertIn("nope", body["message"])

    def test_a_catalog_reports_only_what_is_missing(self):
        status, body = _json_call("/brando.v1.RenderService/CheckCatalog", {
            "spec": {"catalog": {"kinds": ["ARTIFACT_KIND_THEME_CSS", "ARTIFACT_KIND_MARK_SVG"]}},
            "present": ["ARTIFACT_KIND_THEME_CSS"],
        })
        self.assertEqual(200, status)
        self.assertEqual(["ARTIFACT_KIND_MARK_SVG"], body["missing"])


class WsgiBody(unittest.TestCase):
    """The adapter, at the seam where the silent failure lived."""

    def _environ(self, body: bytes, *, length: bool):
        import io

        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/brando.v1.RenderService/CheckContrast",
            "CONTENT_TYPE": "application/json",
            "wsgi.input": io.BytesIO(body),
        }
        if length:
            environ["CONTENT_LENGTH"] = str(len(body))
        return environ

    def _run(self, environ):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status

        payload = b"".join(connect_app.app(environ, start_response))
        return captured["status"], json.loads(payload or b"{}")

    def test_a_body_with_a_content_length_is_read(self):
        body = json.dumps({"theme": _THEME}).encode()
        status, out = self._run(self._environ(body, length=True))
        self.assertTrue(status.startswith("200"))
        self.assertTrue(out["contrast"])

    def test_a_body_WITHOUT_a_content_length_is_still_read(self):
        """The regression that returned 200-and-nothing for every call.

        The client streams, so there is no Content-Length. Reading to EOF is what
        makes the deployed door see the same request the local one does.
        """
        body = json.dumps({"theme": _THEME}).encode()
        status, out = self._run(self._environ(body, length=False))
        self.assertTrue(status.startswith("200"))
        self.assertTrue(out["contrast"], "the body was dropped; every answer would be empty")


if __name__ == "__main__":
    unittest.main()
