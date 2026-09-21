import tempfile
import unittest
import base64
import hashlib
from pathlib import Path
from unittest.mock import patch

from solidworks_mcp.core.contracts import DocumentRef
from solidworks_mcp.tools.views import _safe_filename_part, capture_view, set_view, zoom_fit
from solidworks_mcp.server import _content_for_result


class View:
    def __init__(self):
        self.Orientation3 = object()
        self.Translation3 = object()
        self.Scale2 = 2.5

    def GetViewHWnd(self):
        return 123


class Document:
    GetTitle = "Part1"

    def __init__(self):
        self.ActiveView = View()
        self.named_views = []
        self.zoom_count = 0
        self.redraw_count = 0

    def ShowNamedView2(self, name, view_id):
        self.named_views.append((name, view_id))

    def ViewZoomtofit2(self):
        self.zoom_count += 1

    def GraphicsRedraw2(self):
        self.redraw_count += 1


class Automation:
    def __init__(self):
        self.document = Document()
        self.app = type("App", (), {
            "ActivateDoc3": lambda _, title, use_preferences, option, errors: self.document,
        })()
        self.app.ActiveDoc = self.document
        self.target = DocumentRef("doc-1", None, "part", "Default", "mcp:4")

    def get_active_doc(self):
        return self.document, None

    def capture_active_document_ref(self):
        return self.target, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "error_code": int(error_code),
                "data": data or {}}


class ViewCaptureTests(unittest.TestCase):
    def test_revision_tokens_are_safe_in_windows_filenames(self):
        self.assertEqual("mcp_0", _safe_filename_part("mcp:0"))

    def test_set_view_and_zoom_fit_use_named_view_contract(self):
        automation = Automation()

        view_result = set_view(automation, "front")
        zoom_result = zoom_fit(automation)

        self.assertTrue(view_result["success"])
        self.assertTrue(zoom_result["success"])
        self.assertEqual([("*Front", 1)], automation.document.named_views)
        self.assertEqual(1, automation.document.zoom_count)

    def test_capture_restores_view_and_returns_revision_bound_artifact(self):
        automation = Automation()
        original_orientation = automation.document.ActiveView.Orientation3
        original_translation = automation.document.ActiveView.Translation3
        original_scale = automation.document.ActiveView.Scale2

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture.png"

            def fake_capture(hwnd, path, width, height, screen_box=None):
                Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfixture")
                return width, height

            with patch("solidworks_mcp.tools.views._capture_window_png", fake_capture):
                result = capture_view(
                    automation, orientation="isometric", width=640, height=480,
                    output_path=str(output),
                )

            self.assertTrue(result["success"], result["message"])
            artifact = result["data"]["artifact"]
            self.assertEqual("doc-1", artifact["document_id"])
            self.assertEqual("mcp:4", artifact["revision_token"])
            self.assertEqual("image/png", artifact["mime_type"])
            self.assertEqual([640, 480], artifact["pixel_size"])
            self.assertEqual(str(output.resolve()), artifact["path"])
            self.assertEqual([], result["data"]["restore_warnings"])
            self.assertEqual(2, automation.document.redraw_count)
            self.assertIs(original_orientation, automation.document.ActiveView.Orientation3)
            self.assertIs(original_translation, automation.document.ActiveView.Translation3)
            self.assertEqual(original_scale, automation.document.ActiveView.Scale2)

    def test_capture_rejects_invalid_dimensions_before_com(self):
        automation = Automation()

        result = capture_view(automation, width=0, height=480)

        self.assertFalse(result["success"])
        self.assertEqual([], automation.document.named_views)

    def test_mcp_content_includes_actual_image_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.png"
            payload = b"\x89PNG\r\n\x1a\nactual-image"
            path.write_bytes(payload)
            result = {
                "success": True,
                "message": "captured",
                "error_code": 0,
                "error_name": "swSuccess",
                "data": {"artifact": {"path": str(path), "mime_type": "image/png"}},
            }

            content = _content_for_result(result)

            self.assertEqual(2, len(content))
            self.assertEqual("image", content[1].type)
            self.assertEqual(base64.b64encode(payload).decode("ascii"), content[1].data)

    def test_mcp_content_rejects_image_whose_hash_no_longer_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.png"
            path.write_bytes(b"changed")
            result = {
                "success": True, "message": "captured", "error_code": 0,
                "error_name": "swSuccess",
                "data": {"artifact": {
                    "path": str(path), "mime_type": "image/png",
                    "sha256": hashlib.sha256(b"original").hexdigest(),
                }},
            }

            content = _content_for_result(result)

            self.assertEqual(1, len(content))
            self.assertIn("not attached", content[0].text)


if __name__ == "__main__":
    unittest.main()
