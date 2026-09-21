import os
import unittest
from pathlib import Path
from uuid import uuid4

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.comutil import com
from solidworks_mcp.constants import SwDocumentTypes
from solidworks_mcp.core.session import TargetMismatchError
from solidworks_mcp.tools.assembly import list_mates
from solidworks_mcp.tools.inspection import inspect_document
from solidworks_mcp.tools.export import export_step, export_stl
from solidworks_mcp.tools.history import redo, undo
from solidworks_mcp.tools.inspection import list_planes
from solidworks_mcp.tools.reference_geometry import create_reference_plane
from solidworks_mcp.tools.views import capture_view


@unittest.skipUnless(
    os.environ.get("SW_MCP_LIVE_TESTS") == "1",
    "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.",
)
class LiveDocumentTargetTests(unittest.TestCase):
    def setUp(self):
        self.automation = SolidWorksAutomation()
        result = self.automation.connect()
        if not result["success"]:
            self.skipTest(result["message"])
        self.created_titles = []
        self.created_artifacts = []

    def tearDown(self):
        for path in self.created_artifacts:
            Path(path).unlink(missing_ok=True)
        for title in reversed(self.created_titles):
            try:
                self.automation.app.CloseDoc(title)
            except Exception:
                pass
        self.automation.disconnect()

    def _new_part(self):
        result = self.automation.create_new_part()
        self.assertTrue(result["success"], result["message"])
        title = result["data"]["name"]
        self.created_titles.append(title)
        return title

    def _top_level_feature_types(self):
        document, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        types = []
        feature = com(document, "FirstFeature")
        retained = []
        while feature is not None:
            retained.append(feature)
            types.append(com(feature, "GetTypeName2"))
            feature = com(feature, "GetNextFeature")
        return types

    def test_focus_change_rejects_old_target_until_explicit_rebind(self):
        first_title = self._new_part()
        first = self.automation.bind_active_document()
        second_title = self._new_part()

        with self.assertRaises(TargetMismatchError) as raised:
            self.automation.require_bound_active_document()

        self.assertEqual("WRONG_DOCUMENT", raised.exception.operation_error.code)
        second = self.automation.bind_active_document()
        current = self.automation.require_bound_active_document()
        self.assertEqual(second.document_id, current.document_id)
        self.assertNotEqual(first.document_id, second.document_id)
        self.assertNotEqual(first_title, second_title)
        self.assertIsNone(first.path)
        self.assertIsNone(second.path)

    def test_two_connections_remain_on_the_same_com_owner_thread(self):
        owner = self.automation._com_owner_thread_id

        result = self.automation.connect()

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(owner, self.automation._com_owner_thread_id)

    def test_inspect_unsaved_part_returns_versioned_summary_without_saving(self):
        self._new_part()

        result = inspect_document(self.automation, sections=["summary"])

        self.assertTrue(result["success"], result["message"])
        snapshot = result["data"]["snapshot"]
        self.assertEqual("part", snapshot["documents"][0]["document_type"])
        self.assertIsNone(snapshot["documents"][0]["path"])
        self.assertEqual("known", snapshot["observations"][0]["state"])

    def test_inspect_scratch_extrusion_preserves_live_feature_tree(self):
        self._new_part()
        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        rectangle = self.automation.draw_rectangle(-20, -10, 20, 10, "mm")
        self.assertTrue(rectangle["success"], rectangle["message"])
        extrusion = self.automation.extrude_sketch(8, False, "mm")
        self.assertTrue(extrusion["success"], extrusion["message"])

        result = inspect_document(
            self.automation, sections=["features", "parameters"], depth=6
        )

        self.assertTrue(result["success"], result["message"])
        observations = result["data"]["snapshot"]["observations"]
        feature_types = [item["type"] for item in observations[0]["value"]]
        self.assertIn("Extrusion", feature_types)

    def test_inspect_unsaved_part_dependencies_uses_compatibility_fallback(self):
        self._new_part()

        result = inspect_document(self.automation, sections=["dependencies"])

        self.assertTrue(result["success"], result["message"])
        snapshot = result["data"]["snapshot"]
        self.assertEqual([], snapshot["dependency_edges"])
        self.assertEqual(
            "IModelDoc2.GetDependencies2",
            snapshot["observations"][0]["source"],
            snapshot["observations"][0],
        )
        self.assertIn(
            "fallback",
            snapshot["observations"][0]["value"]["evidence"][0].lower(),
        )

    def test_capture_scratch_part_returns_real_png_without_saving_model(self):
        self._new_part()
        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        rectangle = self.automation.draw_rectangle(-20, -10, 20, 10, "mm")
        self.assertTrue(rectangle["success"], rectangle["message"])
        extrusion = self.automation.extrude_sketch(8, False, "mm")
        self.assertTrue(extrusion["success"], extrusion["message"])

        document, document_error = self.automation.get_active_doc()
        self.assertIsNone(document_error)
        feature = com(document, "FirstFeature")
        sketch_segment_count = None
        retained = []
        while feature is not None:
            retained.append(feature)
            if com(feature, "GetTypeName2") == "ProfileFeature":
                sketch = com(feature, "GetSpecificFeature2")
                sketch_segment_count = len(com(sketch, "GetSketchSegments") or [])
            feature = com(feature, "GetNextFeature")
        self.assertEqual(4, sketch_segment_count)
        com(document, "ClearSelection2", True)

        result = capture_view(
            self.automation, orientation="isometric", width=640, height=480
        )

        self.assertTrue(result["success"], result["message"])
        artifact = result["data"]["artifact"]
        if os.environ.get("SW_MCP_KEEP_CAPTURE") == "1":
            print(f"CAPTURE_PATH={artifact['path']}")
        else:
            self.created_artifacts.append(artifact["path"])
        self.assertEqual(b"\x89PNG\r\n\x1a\n", Path(artifact["path"]).read_bytes()[:8])
        self.assertEqual([640, 480], artifact["pixel_size"])
        self.assertEqual([], result["data"]["restore_warnings"])
        active, error = self.automation.capture_active_document_ref()
        self.assertIsNone(error)
        self.assertIsNone(active.path)

    def test_export_scratch_part_to_step_and_stl_without_saving_native_model(self):
        self._new_part()
        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        rectangle = self.automation.draw_rectangle(-20, -10, 20, 10, "mm")
        self.assertTrue(rectangle["success"], rectangle["message"])
        extrusion = self.automation.extrude_sketch(8, False, "mm")
        self.assertTrue(extrusion["success"], extrusion["message"])
        output_root = self.automation._path_policy.output_roots[0] / "exports"
        stem = f"scratch-{uuid4().hex}"
        step_path = output_root / f"{stem}.step"
        stl_path = output_root / f"{stem}.stl"
        self.created_artifacts.extend((str(step_path), str(stl_path)))

        step_result = export_step(self.automation, str(step_path))
        stl_result = export_stl(self.automation, str(stl_path))

        self.assertTrue(step_result["success"], step_result["message"])
        self.assertTrue(stl_result["success"], stl_result["message"])
        self.assertGreater(step_path.stat().st_size, 0)
        self.assertGreater(stl_path.stat().st_size, 0)
        active, error = self.automation.capture_active_document_ref()
        self.assertIsNone(error)
        self.assertIsNone(active.path)

    def test_undo_and_redo_restore_a_scratch_extrusion_without_saving(self):
        self._new_part()
        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        rectangle = self.automation.draw_rectangle(-20, -10, 20, 10, "mm")
        self.assertTrue(rectangle["success"], rectangle["message"])
        extrusion = self.automation.extrude_sketch(8, False, "mm")
        self.assertTrue(extrusion["success"], extrusion["message"])
        self.assertIn("Extrusion", self._top_level_feature_types())

        undo_result = undo(self.automation)
        self.assertTrue(undo_result["success"], undo_result["message"])
        self.assertNotIn("Extrusion", self._top_level_feature_types())

        redo_result = redo(self.automation)
        self.assertTrue(redo_result["success"], redo_result["message"])
        self.assertIn("Extrusion", self._top_level_feature_types())
        active, error = self.automation.capture_active_document_ref()
        self.assertIsNone(error)
        self.assertIsNone(active.path)

    def test_create_offset_reference_plane_on_scratch_part_without_saving(self):
        self._new_part()
        before = list_planes(self.automation)
        self.assertTrue(before["success"], before["message"])

        result = create_reference_plane(
            self.automation, "Front Plane", 25, "mm"
        )

        self.assertTrue(result["success"], result["message"])
        after = list_planes(self.automation)
        self.assertTrue(after["success"], after["message"])
        self.assertEqual(
            len(before["data"]["planes"]) + 1,
            len(after["data"]["planes"]),
        )
        self.assertEqual("reference", after["data"]["planes"][-1]["kind"])
        active, error = self.automation.capture_active_document_ref()
        self.assertIsNone(error)
        self.assertIsNone(active.path)


@unittest.skipUnless(
    os.environ.get("SW_MCP_LIVE_TESTS") == "1",
    "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.",
)
class LiveAssemblyInspectionTests(unittest.TestCase):
    def setUp(self):
        self.automation = SolidWorksAutomation()
        result = self.automation.connect()
        if not result["success"]:
            self.skipTest(result["message"])

    def tearDown(self):
        self.automation.disconnect()

    def test_active_user_assembly_mates_are_read_without_saving(self):
        document, error = self.automation.get_active_doc()
        if error or com(document, "GetType") != SwDocumentTypes.swDocASSEMBLY:
            self.skipTest("No active assembly is available for read-only mate inspection.")

        result = list_mates(self.automation)

        self.assertTrue(result["success"], result["message"])
        for mate in result["data"]["mates"]:
            self.assertIn("entities", mate)
            self.assertIn("solver_status", mate)
            self.assertIn("feature_id", mate)


if __name__ == "__main__":
    unittest.main()
