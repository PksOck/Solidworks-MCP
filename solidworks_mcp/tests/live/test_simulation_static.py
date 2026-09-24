"""Live Simulation workflow on a scratch structural-member beam.

The beam is a real library profile (DIN IPE) extruded 600 mm along a sketch
line, so the model is large enough for the mesh counts to be meaningful.  A
weldment part is a beam study by default, which cannot be meshed before beam
joints exist; ``create_static_study`` converts the beam bodies to solid bodies
so the standard solid mesh workflow applies.

Each test builds its own single-member part and closes it again; the part is
saved into the approved output root only where the test proves persistence.
"""

import os
import unittest
from pathlib import Path
from uuid import uuid4

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.comutil import com
from solidworks_mcp.tools.export import list_planar_faces
from solidworks_mcp.tools.material import apply_material
from solidworks_mcp.tools.saving import save_document
from solidworks_mcp.tools.simulation import (
    apply_fixed_fixture, apply_force_load, create_static_study,
    get_stress_results, run_analysis)
from solidworks_mcp.tools.weldments import (
    create_structural_member, list_weldment_profiles)

BEAM_LENGTH_MM = 600
LOAD_NEWTONS = 2000.0
MATERIAL_DB = (r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\english"
               r"\sldmaterials\solidworks materials.sldmat")
MATERIAL_NAME = "Plain Carbon Steel"


@unittest.skipUnless(os.environ.get("SW_MCP_LIVE_TESTS") == "1",
                     "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.")
class LiveSimulationStaticTests(unittest.TestCase):
    def setUp(self):
        self.automation = SolidWorksAutomation()
        result = self.automation.connect()
        if not result["success"]:
            self.skipTest(result["message"])
        self.created_titles = []
        self.output_root = Path(self.automation._path_policy.output_roots[0])

    def tearDown(self):
        for title in reversed(self.created_titles):
            try:
                self.automation.app.CloseDoc(title)
            except Exception:
                pass
        self.automation.disconnect()

    # -- scratch beam -------------------------------------------------------
    def _new_part(self):
        result = self.automation.create_new_part()
        self.assertTrue(result["success"], result["message"])
        title = result["data"]["name"]
        self.created_titles.append(title)
        return title

    def _document(self):
        document, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        return document

    def _sketch_name(self, document):
        name = None
        feature = com(document, "FirstFeature")
        while feature is not None:
            if com(feature, "GetTypeName2") == "ProfileFeature":
                name = str(com(feature, "Name"))
            feature = com(feature, "GetNextFeature")
        return name

    def _profile(self):
        profiles = list_weldment_profiles(self.automation, filter="ipe")
        self.assertTrue(profiles["success"], profiles["message"])
        items = profiles["data"]["profiles"]
        self.assertTrue(items, "No IPE weldment profile is installed.")
        chosen = next((item for item in items
                       if item["folder"].casefold() == "din"
                       and item["name"].casefold() == "ipe.sldlfp"), None)
        return chosen or items[0]

    def _beam(self):
        """A 600 mm single-member beam built from a real library profile."""
        self._new_part()
        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        line = self.automation.draw_line(0, 0, BEAM_LENGTH_MM, 0, "mm")
        self.assertTrue(line["success"], line["message"])
        self.assertTrue(self.automation.exit_sketch()["success"])

        document = self._document()
        profile = self._profile()
        member = create_structural_member(self.automation,
                                          self._sketch_name(document),
                                          profile["path"])
        self.assertTrue(member["success"], member["message"])
        material = apply_material(self.automation, MATERIAL_NAME, MATERIAL_DB)
        self.assertTrue(material["success"], material["message"])
        self.assertGreater(self._volume_mm3(), 0)
        return document, member["data"]["feature"], profile

    def _volume_mm3(self):
        return sum(com(body, "GetMassProperties", 0.0)[3] * 1e9
                   for body in com(self._document(), "GetBodies2", 0, True) or [])

    def _end_faces(self):
        """The two end caps of the beam, as planar-face indices."""
        listed = list_planar_faces(self.automation)
        self.assertTrue(listed["success"], listed["message"])
        faces = listed["data"]["faces"]
        points = [item["point_mm"] for item in faces]
        spreads = [max(p[axis] for p in points) - min(p[axis] for p in points)
                   for axis in range(3)]
        axis = spreads.index(max(spreads))
        ends = sorted((item for item in faces if abs(item["normal"][axis]) > 0.9),
                      key=lambda item: item["point_mm"][axis])
        self.assertGreaterEqual(len(ends), 2, "The beam has no two end faces.")
        self.assertGreater(ends[-1]["point_mm"][axis] - ends[0]["point_mm"][axis], 0)
        return ends[0]["index"], ends[-1]["index"]

    def _study_with_loads(self, name):
        self.assertTrue(create_static_study(self.automation, name)["success"])
        fixed, loaded = self._end_faces()
        fixture = apply_fixed_fixture(self.automation, [fixed], study=name)
        self.assertTrue(fixture["success"], fixture["message"])
        force = apply_force_load(self.automation, [loaded], LOAD_NEWTONS, study=name)
        self.assertTrue(force["success"], force["message"])
        return fixed, loaded

    def _save(self, path):
        """Save As renames the document, so the open title follows the path."""
        saved = save_document(self.automation, path=str(path))
        self.assertTrue(saved["success"], saved["message"])
        self.created_titles[-1] = path.stem

    # -- 5.1 ----------------------------------------------------------------
    def test_create_static_study_converts_beam_bodies_and_verifies_the_study(self):
        document, feature, profile = self._beam()
        self.assertIn("WeldMemberFeat", self._feature_types(document))
        self.assertTrue(feature)

        result = create_static_study(self.automation, "MCP Beam Static")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(1, result["data"]["study_count_after"])
        self.assertEqual(0, result["data"]["analysis_type"])
        self.assertEqual(0, result["data"]["mesh_type"])
        self.assertGreaterEqual(result["data"]["beam_bodies_converted"], 1,
                                "The weldment study was not converted to solid bodies.")

        path = self.output_root / "saved" / f"mcp_live_sim_beam_{uuid4().hex}.SLDPRT"
        self._save(path)
        self.assertGreater(path.stat().st_size, 0)

    def _feature_types(self, document):
        types = []
        feature = com(document, "FirstFeature")
        while feature is not None:
            types.append(str(com(feature, "GetTypeName2")))
            feature = com(feature, "GetNextFeature")
        return types

    # -- 5.3 ----------------------------------------------------------------
    def test_apply_fixed_fixture_adds_one_fixed_restraint(self):
        self._beam()
        fixed, _loaded = self._end_faces()
        self.assertTrue(create_static_study(self.automation, "MCP Fixed")["success"])

        result = apply_fixed_fixture(self.automation, [fixed], study="MCP Fixed")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(0, result["data"]["restraint_type"])
        self.assertEqual(1, result["data"]["face_count"])
        self.assertEqual(0, result["data"]["count_before"])
        self.assertEqual(1, result["data"]["count_after"])

    # -- 5.4 ----------------------------------------------------------------
    def test_apply_force_load_converts_units_and_reads_the_magnitude_back(self):
        self._beam()
        _fixed, loaded = self._end_faces()
        self.assertTrue(create_static_study(self.automation, "MCP Force")["success"])

        # A force unit: 2 kN must be stored as 2000 N.
        kilonewtons = apply_force_load(self.automation, [loaded], LOAD_NEWTONS / 1000.0,
                                       unit="kN", study="MCP Force")
        self.assertTrue(kilonewtons["success"], kilonewtons["message"])
        self.assertEqual(1000.0, kilonewtons["data"]["conversion_factor"])
        self.assertAlmostEqual(LOAD_NEWTONS, kilonewtons["data"]["force_newtons"],
                               places=6)
        self.assertAlmostEqual(LOAD_NEWTONS, kilonewtons["data"]["read_back_newtons"],
                               places=6)
        self.assertEqual(1, kilonewtons["data"]["force_type"])
        self.assertEqual(1, kilonewtons["data"]["count_after"])

        # A mass unit: 200 kg becomes 200 * 9.80665 N in the study.
        kilograms = apply_force_load(self.automation, [loaded], 200.0, unit="kg",
                                     study="MCP Force")
        self.assertTrue(kilograms["success"], kilograms["message"])
        expected = 200.0 * 9.80665
        self.assertAlmostEqual(expected, kilograms["data"]["force_newtons"], places=6)
        self.assertAlmostEqual(expected, kilograms["data"]["read_back_newtons"],
                               places=6)
        self.assertEqual(2, kilograms["data"]["count_after"])

    # -- 5.5 ----------------------------------------------------------------
    def test_run_analysis_meshes_the_beam_and_solves(self):
        document, _feature, _profile = self._beam()
        self._study_with_loads("MCP Solve")

        result = run_analysis(self.automation, study="MCP Solve")

        if not result["success"]:
            self.assertEqual("ANALYSIS_AUTHORIZATION_FAILED", result["data"].get("code"),
                             result["message"])
            self.skipTest("Simulation license does not authorize a static solve.")
        self.assertGreater(result["data"]["node_count"], 1000)
        self.assertGreater(result["data"]["element_count"], 500)
        self.assertEqual(0, result["data"]["mesh_error"])
        self.assertEqual(0, result["data"]["run_error"])
        # The mesh is a real discretisation of the beam, not a stub.
        self.assertGreater(self._volume_mm3(), 0)

    # -- 5.6 ----------------------------------------------------------------
    def test_get_stress_results_returns_a_finite_positive_maximum(self):
        document, _feature, _profile = self._beam()
        self._study_with_loads("MCP Stress")
        analysis = run_analysis(self.automation, study="MCP Stress")
        if not analysis["success"]:
            self.assertEqual("ANALYSIS_AUTHORIZATION_FAILED",
                             analysis["data"].get("code"), analysis["message"])
            self.skipTest("Simulation license does not authorize a static solve.")

        result = get_stress_results(self.automation, study="MCP Stress")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(9, result["data"]["component"])
        self.assertGreaterEqual(result["data"]["available_steps"], 1)
        self.assertGreater(result["data"]["stress_max_mpa"], 0)
        self.assertGreaterEqual(result["data"]["stress_min_mpa"], 0)
        self.assertLessEqual(result["data"]["stress_min_mpa"],
                             result["data"]["stress_max_mpa"])
        self.assertGreaterEqual(result["data"]["node_max"], 0)
        # The solved beam mesh must have the node the maximum refers to.
        self.assertLess(result["data"]["node_max"], analysis["data"]["node_count"])


if __name__ == "__main__":
    unittest.main()
