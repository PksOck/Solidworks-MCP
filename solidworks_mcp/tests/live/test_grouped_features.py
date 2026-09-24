"""Sequential live checks sharing a single solid body and saved part.

The numbered tests intentionally share model state. Run the whole class, not
individual methods: each operation has its own reported test and checkpoint.
"""

import math
import os
import unittest
from pathlib import Path
from uuid import uuid4

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.comutil import com
from solidworks_mcp.tools.advanced_features import hole_wizard
from solidworks_mcp.tools.appearance import set_appearance
from solidworks_mcp.tools.body_features import delete_body, move_copy_body, scale_body
from solidworks_mcp.tools.configurations import create_configuration
from solidworks_mcp.tools.equations import add_equation
from solidworks_mcp.tools.export import list_planar_faces
from solidworks_mcp.tools.properties import set_custom_property
from solidworks_mcp.tools.reference_geometry import create_reference_axis
from solidworks_mcp.tools.saving import save_document


@unittest.skipUnless(os.environ.get("SW_MCP_LIVE_TESTS") == "1",
                     "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.")
class LiveGroupedSingleBodyTests(unittest.TestCase):
    """One part, initially a 100 x 100 x 40 mm body, then controlled copies."""

    @classmethod
    def setUpClass(cls):
        cls.automation = SolidWorksAutomation()
        cls.title = None
        cls.stage = 0
        cls.path = None
        result = cls.automation.connect()
        if not result["success"]:
            raise unittest.SkipTest(result["message"])
        try:
            result = cls.automation.create_new_part()
            if not result["success"]:
                raise AssertionError(result["message"])
            cls.title = result["data"]["name"]
            for result in (cls.automation.create_sketch("Front", exact_geometry=True),
                           cls.automation.draw_rectangle(-50, -50, 50, 50, "mm"),
                           cls.automation.extrude_sketch(40, False, "mm")):
                if not result["success"]:
                    raise AssertionError(result["message"])
            root = Path(cls.automation._path_policy.output_roots[0]) / "saved"
            cls.path = root / f"mcp_live_grouped_edges_hole_{uuid4().hex}.SLDPRT"
        except BaseException:
            cls._close_and_disconnect()
            raise

    @classmethod
    def _close_and_disconnect(cls):
        try:
            if cls.title is not None:
                cls.automation.app.CloseDoc(cls.title)
        finally:
            cls.automation.disconnect()

    @classmethod
    def tearDownClass(cls):
        try:
            # Preserve the diagnostic model even when an earlier stage fails.
            if cls.title is not None and cls.path is not None:
                saved = save_document(cls.automation, path=str(cls.path))
                if not saved["success"]:
                    raise AssertionError(saved["message"])
                if cls.path.stat().st_size == 0:
                    raise AssertionError("Shared part was saved empty.")
        finally:
            cls._close_and_disconnect()

    def _volume(self):
        part, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        bodies = com(part, "GetBodies2", 0, True) or []
        self.assertEqual(1, len(bodies))
        return com(bodies[0], "GetMassProperties", 0.0)[3] * 1e9

    def _bodies(self):
        part, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        return com(part, "GetBodies2", 0, True) or []

    def _total_volume(self):
        return sum(com(body, "GetMassProperties", 0.0)[3] * 1e9
                   for body in self._bodies())

    def _require_stage(self, stage):
        if type(self).stage != stage:
            self.skipTest(f"Earlier operation did not reach checkpoint {stage}.")

    def test_01_fillet_removes_expected_volume(self):
        before = self._volume()
        self.assertAlmostEqual(400000, before, delta=0.1)
        result = self.automation.fillet_edges(5, "mm", edge_points=[[20, 50, 50]])
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(before - self._volume(),
                               (25 - math.pi * 25 / 4) * 40, delta=0.05)
        type(self).stage = 1

    def test_02_chamfer_removes_expected_volume(self):
        self._require_stage(1)
        before = self._volume()
        result = self.automation.chamfer_edges(5, 45, "mm",
                                               edge_points=[[20, 50, -50]])
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(before - self._volume(), 5 * 5 / 2 * 40, delta=0.05)
        type(self).stage = 2

    def test_03_hole_wizard_removes_volume(self):
        self._require_stage(2)
        before = self._volume()
        faces = list_planar_faces(self.automation)
        self.assertTrue(faces["success"], faces["message"])
        cap = next((face for face in faces["data"]["faces"]
                    if face["normal"][0] > 0.9
                    and abs(face["point_mm"][0] - 40) < 0.1
                    and face["area_mm2"] > 9000), None)
        self.assertIsNotNone(cap, "Extrusion cap not found after edge treatments.")
        result = hole_wizard(self.automation, cap["index"], [40, 0, 0], 6, 8)
        self.assertTrue(result["success"], result["message"])
        self.assertLess(self._volume(), before - 10)
        type(self).stage = 3

    def test_04_reference_axis_does_not_change_volume(self):
        self._require_stage(3)
        before = self._volume()
        result = create_reference_axis(self.automation, "Front Plane", "Top Plane")
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(before, self._volume(), delta=0.01)
        type(self).stage = 4

    def test_05_custom_properties_in_both_scopes(self):
        self._require_stage(4)
        before = self._volume()
        part, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        config = str(com(com(part, "ConfigurationManager"), "ActiveConfiguration").Name)
        first = set_custom_property(self.automation, "MCP_Document", "DOCUMENT_42")
        self.assertTrue(first["success"], first["message"])
        second = set_custom_property(self.automation, "MCP_Config", "CONFIG_19",
                                     configuration=config)
        self.assertTrue(second["success"], second["message"])
        self.assertEqual("DOCUMENT_42", first["data"]["read_back"])
        self.assertEqual("CONFIG_19", second["data"]["read_back"])
        self.assertAlmostEqual(before, self._volume(), delta=0.01)
        type(self).stage = 5

    def test_06_configuration_keeps_body_geometry(self):
        self._require_stage(5)
        before = self._volume()
        part, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        first_config = str(com(com(part, "ConfigurationManager"), "ActiveConfiguration").Name)
        result = create_configuration(self.automation, "MCP_TEST_VARIANT",
                                      comment="MCP live", description="test configuration",
                                      activate=True)
        self.assertTrue(result["success"], result["message"])
        self.assertEqual("MCP_TEST_VARIANT", result["data"]["read_back"]["name"])
        self.assertTrue(result["data"]["active"])
        self.assertAlmostEqual(before, self._volume(), delta=0.01)
        duplicate = create_configuration(self.automation, "MCP_TEST_VARIANT")
        self.assertFalse(duplicate["success"])
        self.assertEqual("CONFIGURATION_EXISTS", duplicate["data"]["code"])
        self.assertIsNotNone(com(part, "GetConfigurationByName", first_config))
        type(self).stage = 6

    def test_07_equation_round_trips_without_volume_change(self):
        self._require_stage(6)
        before = self._volume()
        result = add_equation(self.automation, "MCP_Width", 20)
        self.assertTrue(result["success"], result["message"])
        self.assertEqual("verified", result["data"]["status"])
        part, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        manager = com(part, "GetEquationMgr")
        self.assertTrue(com(manager, "GlobalVariable", result["data"]["index"]))
        self.assertIn('"MCP_Width"', com(manager, "Equation", result["data"]["index"]))
        self.assertAlmostEqual(before, self._volume(), delta=0.01)
        type(self).stage = 7

    def test_08_appearance_preserves_geometry(self):
        self._require_stage(7)
        before = self._volume()
        result = set_appearance(self.automation, 0.2, 0.5, 0.8)
        self.assertTrue(result["success"], result["message"])
        self.assertTrue(all(abs(actual - value) < 1 / 255 + 1e-6
                            for actual, value in zip(result["data"]["rgb"], (0.2, 0.5, 0.8))))
        self.assertAlmostEqual(before, self._volume(), delta=0.01)
        type(self).stage = 8

    def test_09_move_body_preserves_volume(self):
        self._require_stage(8)
        before = self._volume()
        result = move_copy_body(self.automation, 0, 0, 150, 0)
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(result["data"]["box_after_m"][1] -
                               result["data"]["box_before_m"][1], .15, delta=1e-4)
        self.assertAlmostEqual(before, self._volume(), delta=1)
        type(self).stage = 9

    def test_10_copy_body_adds_one_body(self):
        self._require_stage(9)
        before = self._volume()
        result = move_copy_body(self.automation, 0, 0, 150, 0, copy=True)
        self.assertTrue(result["success"], result["message"])
        self.assertEqual(2, len(self._bodies()))
        self.assertAlmostEqual(before * 2, self._total_volume(), delta=1)
        self.assertAlmostEqual(result["data"]["box_after_m"][1] -
                               result["data"]["box_before_m"][1], .15, delta=1e-4)
        type(self).stage = 10

    def test_11_scale_one_body_octuples_its_volume(self):
        self._require_stage(10)
        bodies = self._bodies()
        before = [com(body, "GetMassProperties", 0.0)[3] * 1e9 for body in bodies]
        # Choose the body at y=150 mm, not the copied one at y=300 mm.
        index = min(range(len(bodies)), key=lambda i: com(bodies[i], "GetBodyBox")[1])
        box = com(bodies[index], "GetBodyBox")
        result = scale_body(self.automation, index, 2, origin="centroid")
        self.assertTrue(result["success"], result["message"])
        after = [com(body, "GetMassProperties", 0.0)[3] * 1e9 for body in self._bodies()]
        self.assertEqual(2, len(after))
        self.assertAlmostEqual(sum(after), sum(before) + before[index] * 7, delta=1)
        scaled = next(body for body in self._bodies()
                      if abs(com(body, "GetMassProperties", 0.0)[3] * 1e9 - before[index] * 8) < 1)
        scaled_box = com(scaled, "GetBodyBox")
        for axis in range(3):
            self.assertAlmostEqual(scaled_box[axis + 3] - scaled_box[axis],
                                   2 * (box[axis + 3] - box[axis]), delta=1e-4)
        type(self).stage = 11

    def test_12_delete_only_selected_body(self):
        self._require_stage(11)
        bodies = self._bodies()
        before = self._total_volume()
        index = max(range(len(bodies)), key=lambda i: com(bodies[i], "GetMassProperties", 0.0)[3])
        removed = com(bodies[index], "GetMassProperties", 0.0)[3] * 1e9
        result = delete_body(self.automation, index)
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(self._volume(), before - removed, delta=1)
        type(self).stage = 12

    def test_13_keep_only_selected_body(self):
        self._require_stage(12)
        result = move_copy_body(self.automation, 0, 0, 150, 0, copy=True)
        self.assertTrue(result["success"], result["message"])
        bodies = self._bodies()
        self.assertEqual(2, len(bodies))
        before = self._total_volume()
        index = max(range(len(bodies)), key=lambda i: com(bodies[i], "GetBodyBox")[1])
        kept = com(bodies[index], "GetMassProperties", 0.0)[3] * 1e9
        result = delete_body(self.automation, index, keep_only=True)
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(self._volume(), kept, delta=1)
        self.assertAlmostEqual(before, kept * 2, delta=1)
        type(self).stage = 13

    def test_14_scale_body_about_origin_octuples_volume(self):
        self._require_stage(13)
        body = self._bodies()[0]
        before_box = com(body, "GetBodyBox")
        before = self._volume()
        result = scale_body(self.automation, 0, 2, origin="origin")
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(self._volume(), before * 8, delta=1)
        after_box = com(self._bodies()[0], "GetBodyBox")
        for axis in range(3):
            self.assertAlmostEqual(after_box[axis + 3] - after_box[axis],
                                   2 * (before_box[axis + 3] - before_box[axis]), delta=1e-4)
        type(self).stage = 14

    def test_15_save_and_close_shared_part(self):
        self._require_stage(14)
        saved = save_document(self.automation, path=str(self.path))
        self.assertTrue(saved["success"], saved["message"])
        self.assertGreater(self.path.stat().st_size, 0)
        part, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        self.assertTrue(all(abs(com(part, "MaterialPropertyValues")[i] - value) < 1 / 255 + 1e-6
                            for i, value in enumerate((0.2, 0.5, 0.8))))
        title = str(com(part, "GetTitle"))
        self.automation.app.CloseDoc(title)
        type(self).title = None
        documents = self.automation.list_open_documents()
        self.assertTrue(documents["success"], documents["message"])
        self.assertNotIn(title, [d["title"] for d in documents["data"]["documents"]])
