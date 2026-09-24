"""Unit tests for the SOLIDWORKS Simulation static-study tools.

The add-in objects are replaced by fakes that mirror the ``cosworks.tlb``
shapes: properties are plain attributes, methods take the ByRef variants the
real add-in expects and fill them through ``.value``.
"""

import unittest
from unittest.mock import patch

from solidworks_mcp.core.policy import OperationClass
from solidworks_mcp.registry import operation_class_for, registered_tools
from solidworks_mcp.tools.simulation import (
    apply_fixed_fixture, apply_force_load, create_static_study,
    get_stress_results, run_analysis,
)

FACE_LOOKUP = "solidworks_mcp.tools.simulation._get_planar_face_by_index"


class FakeStudy:
    def __init__(self, name, analysis_type=0, mesh_type=0):
        self.Name = name
        self.AnalysisType = analysis_type
        self._mesh_type = mesh_type
        self.BeamManager = FakeBeamManager(self)
        self.Mesh = FakeMesh()
        self.LoadsAndRestraintsManager = FakeLbcManager()
        self.Results = FakeResults()
        self.created_meshes = []
        self.run_calls = 0
        self.run_error = 0
        self.solution_time = 1.5

    @property
    def MeshType(self):
        return self._mesh_type

    def CreateMesh(self, units, element, tolerance):
        self.created_meshes.append((units, element, tolerance))
        return self.mesh_error

    mesh_error = 0

    def RunAnalysis(self):
        self.run_calls += 1
        return self.run_error

    def GetTotalSolutionTime(self):
        return self.solution_time


class FakeBeamManager:
    """A weldment study starts with beam bodies that cannot be meshed."""

    def __init__(self, study):
        self.study = study
        self.beams = []

    @property
    def BeamCount(self):
        return len(self.beams)

    def GetBeamBodyAt(self, index, errors):
        errors.value = 0
        return self.beams[index]


class FakeBeamBody:
    def __init__(self, study, manager, beam_type=0):
        self.study = study
        self.manager = manager
        self.BeamType = beam_type

    def ConvertToSolidBody(self):
        self.study._mesh_type = 0
        self.manager.beams.remove(self)


class FakeMesh:
    def __init__(self):
        self.Quality = 0
        self.NodeCount = 1234
        self.ElementCount = 567
        self.failed = 0
        self.element_size = 4.0
        self.tolerance = 0.2

    def GetDefaultElementSizeAndTolerance(self, units, element, tolerance):
        element.value = self.element_size
        tolerance.value = self.tolerance

    def GetNoOfFailedComponents(self):
        return self.failed


class FakeLbcManager:
    def __init__(self):
        self._items = []
        self.restraint_error = 0
        self.force_error = 0
        self.force_value = None
        self.force_edit_error = 0

    @property
    def Count(self):
        return len(self._items)

    def AddRestraint(self, restraint_type, entities, reference, errors):
        errors.value = self.restraint_error
        if self.restraint_error:
            return None
        restraint = FakeRestraint(restraint_type)
        self._items.append(restraint)
        return restraint

    def AddForce2(self, force_type, selection_type, entities, reference, errors):
        errors.value = self.force_error
        if self.force_error:
            return None
        force = FakeForce(self.force_value)
        force.force_edit_error = self.force_edit_error
        force.ForceType = force_type
        self._items.append(force)
        return force


class FakeRestraint:
    def __init__(self, restraint_type):
        self.RestraintType = restraint_type


class FakeForce:
    """``stored`` models the add-in ignoring the value we set."""

    def __init__(self, stored=None):
        self._stored = stored
        self._value = stored if stored is not None else 0.0
        self.ForceType = 1
        self.force_edit_error = 0

    @property
    def NormalForceOrTorqueValue(self):
        return self._value

    @NormalForceOrTorqueValue.setter
    def NormalForceOrTorqueValue(self, value):
        if self._stored is None:
            self._value = value

    def ForceBeginEdit(self):
        return None

    def ForceEndEdit(self):
        return self.force_edit_error


class FakeResults:
    def __init__(self):
        self.available_steps = 1
        self.values = [7, -1.25, 91, 33.5]
        self.error = 0
        self.calls = []

    def GetMaximumAvailableSteps(self):
        return self.available_steps

    def GetMinMaxStress(self, component, element, step, plane, units, errors):
        self.calls.append((component, element, step, plane, units))
        errors.value = self.error
        return type(self.values)(self.values)


class FakeStudyManager:
    def __init__(self):
        self.studies = []
        self.error = 0
        self.beam_mesh = False

    @property
    def StudyCount(self):
        return len(self.studies)

    def GetStudy(self, index):
        return self.studies[index]

    def CreateNewStudy3(self, name, analysis_type, sub_option, errors):
        errors.value = self.error
        if self.error:
            return None
        study = FakeStudy(name, analysis_type, 4 if self.beam_mesh else 0)
        if self.beam_mesh:
            study.BeamManager.beams.append(
                FakeBeamBody(study, study.BeamManager))
        self.studies.append(study)
        return study


class FakeSimModel:
    def __init__(self):
        self.StudyManager = FakeStudyManager()


class FakeCallback:
    def __init__(self, model):
        self.COSMOSWORKS = type("FakeCosmos", (), {
            "ActiveDoc": lambda self_: model})()


class FakeExtension:
    def __init__(self, selection_manager, selects=True):
        self._selection_manager = selection_manager
        self._selects = selects
        self.calls = []

    def SelectByID2(self, name, kind, x, y, z, append, mark, data, option):
        self.calls.append((name, kind))
        return self._selects


class FakeSelectionManager:
    def __init__(self, selected=None):
        self.selected = selected
        self.cleared = []

    def ClearSelection2(self, clear_all):
        self.cleared.append(clear_all)
        return True

    def GetSelectedObject6(self, index, mark):
        return self.selected


class FakePlane:
    pass


class FakeFeature:
    def __init__(self, name, type_name):
        self.Name = name
        self.type_name = type_name

    def GetTypeName2(self):
        return self.type_name

    def GetSpecificFeature2(self):
        return FakePlane()


class FakeDocument:
    def __init__(self, doc_type=1, has_plane=True, plane_name="Front Plane",
                 axis_name="Axis1"):
        self.doc_type = doc_type
        self.SelectionManager = FakeSelectionManager()
        self.Extension = FakeExtension(self.SelectionManager)
        self.clear_calls = []
        self.reference_lookups = []
        self._features = {}
        if has_plane:
            self._features[plane_name] = FakeFeature(plane_name, "RefPlane")
        if axis_name is not None:
            self._features[axis_name] = FakeFeature(axis_name, "RefAxis")

    def GetType(self):
        return self.doc_type

    def ClearSelection2(self, clear_all):
        self.clear_calls.append(clear_all)
        return True

    def FeatureByName(self, name):
        self.reference_lookups.append(name)
        return self._features.get(name)


class FakeApp:
    def __init__(self, callback):
        self._callback = callback
        self.queries = []

    def GetAddInObject(self, progid):
        self.queries.append(progid)
        return self._callback


class SimulationAutomation:
    def __init__(self, document=None, callback="auto"):
        self.document = document or FakeDocument()
        self.model = FakeSimModel()
        self.app = FakeApp(FakeCallback(self.model) if callback == "auto" else callback)
        self.active_doc_calls = 0

    def get_active_doc(self):
        self.active_doc_calls += 1
        return self.document, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message,
                "error_code": int(error_code), "data": data or {}}


class SimulationRegistrationTests(unittest.TestCase):
    def test_static_workflow_tools_are_registered_with_expected_semantics(self):
        names = {item.name for item in registered_tools()}
        for name in ("create_static_study", "apply_fixed_fixture",
                     "apply_force_load", "run_analysis", "get_stress_results"):
            self.assertIn(name, names)
        for name in ("create_static_study", "apply_fixed_fixture",
                     "apply_force_load", "run_analysis"):
            self.assertIs(OperationClass.MUTATE, operation_class_for(name))
        self.assertIs(OperationClass.READ, operation_class_for("get_stress_results"))

    def test_force_schema_requires_a_positive_magnitude(self):
        tools = {item.name: item for item in registered_tools()}
        schema = tools["apply_force_load"].inputSchema
        self.assertEqual(["face_indices", "magnitude"], schema["required"])
        self.assertEqual(0, schema["properties"]["magnitude"]["exclusiveMinimum"])
        self.assertEqual(["kg", "kgf", "kgf*m", "kn", "kn*m", "n", "n*m", "n*mm", "t"],
                         schema["properties"]["unit"]["enum"])
        self.assertEqual(["force", "torque"], schema["properties"]["load_type"]["enum"])


class CreateStaticStudyTests(unittest.TestCase):
    def test_creates_and_verifies_study_through_the_manager(self):
        automation = SimulationAutomation()

        result = create_static_study(automation, "MCP Static")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(1, result["data"]["study_count_after"])
        self.assertEqual(0, result["data"]["analysis_type"])
        self.assertEqual(0, result["data"]["mesh_type"])
        self.assertEqual(0, result["data"]["beam_bodies_converted"])
        self.assertEqual("MCP Static", automation.model.StudyManager.studies[0].Name)

    def test_beam_bodies_are_converted_so_a_weldment_study_meshes_as_solid(self):
        automation = SimulationAutomation()
        automation.model.StudyManager.beam_mesh = True

        result = create_static_study(automation, "MCP Beam")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(1, result["data"]["beam_bodies_converted"])
        self.assertEqual(0, result["data"]["mesh_type"])
        self.assertEqual(0, automation.model.StudyManager.studies[0].BeamManager.BeamCount)

    def test_beam_mesh_type_is_left_alone_when_requested(self):
        automation = SimulationAutomation()
        automation.model.StudyManager.beam_mesh = True

        result = create_static_study(automation, "MCP Beam", mesh_type="beam")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(4, result["data"]["mesh_type"])
        self.assertEqual(0, result["data"]["beam_bodies_converted"])

    def test_invalid_mesh_type_is_rejected_before_com(self):
        automation = SimulationAutomation()

        result = create_static_study(automation, "S1", mesh_type="shell")

        self.assertFalse(result["success"])
        self.assertEqual(0, automation.active_doc_calls)

    def test_duplicate_name_reports_the_simulation_error_code(self):
        automation = SimulationAutomation()
        automation.model.StudyManager.error = 2

        result = create_static_study(automation, "MCP Static")

        self.assertFalse(result["success"])
        self.assertEqual("STUDY_NOT_CREATED", result["data"]["code"])
        self.assertEqual(2, result["data"]["simulation_error_code"])

    def test_missing_add_in_is_reported_not_raised(self):
        automation = SimulationAutomation(callback=None)

        result = create_static_study(automation, "MCP Static")

        self.assertFalse(result["success"])
        self.assertEqual("SIMULATION_UNAVAILABLE", result["data"]["code"])

    def test_requires_an_active_part(self):
        automation = SimulationAutomation(document=FakeDocument(doc_type=2))

        result = create_static_study(automation, "MCP Static")

        self.assertFalse(result["success"])
        self.assertEqual("SIMULATION_REQUIRES_PART", result["data"]["code"])

    def test_invalid_name_is_rejected_before_com(self):
        automation = SimulationAutomation()

        result = create_static_study(automation, "   ")

        self.assertFalse(result["success"])
        self.assertEqual(0, automation.active_doc_calls)


class FixedFixtureTests(unittest.TestCase):
    @patch(FACE_LOOKUP, side_effect=lambda document, index: f"face-{index}")
    def test_adds_fixed_restraint_and_verifies_type(self, _lookup):
        automation = SimulationAutomation()
        study = create_static_study(automation, "S1")
        self.assertTrue(study["success"])

        result = apply_fixed_fixture(automation, [3, 4])

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(0, result["data"]["restraint_type"])
        self.assertEqual(1, result["data"]["count_after"])
        self.assertEqual(2, result["data"]["face_count"])
        self.assertEqual("S1", result["data"]["study"])

    @patch(FACE_LOOKUP, return_value=None)
    def test_non_planar_face_is_reported(self, _lookup):
        automation = SimulationAutomation()

        result = apply_fixed_fixture(automation, [99])

        self.assertFalse(result["success"])
        self.assertEqual("SIMULATION_FACE_NOT_FOUND", result["data"]["code"])

    def test_empty_face_list_is_rejected(self):
        automation = SimulationAutomation()

        result = apply_fixed_fixture(automation, [])

        self.assertFalse(result["success"])
        self.assertEqual(0, automation.active_doc_calls)


class ForceLoadTests(unittest.TestCase):
    @patch(FACE_LOOKUP, side_effect=lambda document, index: f"face-{index}")
    def test_adds_normal_force_and_reads_the_magnitude_back(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")

        result = apply_force_load(automation, [2], 1000.0)

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(1000.0, result["data"]["magnitude"])
        self.assertEqual("n", result["data"]["unit"])
        self.assertEqual("force", result["data"]["load_type"])
        self.assertEqual(1.0, result["data"]["conversion_factor"])
        self.assertEqual(1000.0, result["data"]["force_newtons"])
        self.assertEqual(1000.0, result["data"]["read_back_newtons"])
        self.assertEqual(1, result["data"]["force_type"])
        self.assertEqual(1, result["data"]["face_count"])
        self.assertEqual(1, result["data"]["count_after"])

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_mass_units_are_converted_to_newtons(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")

        cases = (
            ("kg", 200.0, 200.0 * 9.80665),
            ("KG", 1.0, 9.80665),
            ("t", 2.0, 2.0 * 9806.65),
            ("kgf", 10.0, 10.0 * 9.80665),
            ("kN", 1.5, 1500.0),
        )
        for unit, amount, expected in cases:
            with self.subTest(unit=unit):
                result = apply_force_load(automation, [2], amount, unit=unit)
                self.assertTrue(result["success"], result["message"])
                self.assertAlmostEqual(expected, result["data"]["force_newtons"],
                                       places=6)
                # What we set is what the add-in stores and reads back.
                self.assertAlmostEqual(expected, result["data"]["read_back_newtons"],
                                       places=6)

    def test_unknown_unit_is_rejected_before_com(self):
        automation = SimulationAutomation()

        result = apply_force_load(automation, [2], 10.0, unit="psi")

        self.assertFalse(result["success"])
        self.assertEqual("VALIDATION_FAILED", result["data"]["code"])
        self.assertEqual(0, automation.active_doc_calls)

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_read_back_mismatch_is_a_failure(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        study = automation.model.StudyManager.studies[0]
        # The add-in accepted the call but stored a different magnitude.
        study.LoadsAndRestraintsManager.force_value = 5.0

        result = apply_force_load(automation, [2], 1000.0)

        self.assertFalse(result["success"])
        self.assertEqual("FORCE_NOT_VERIFIED", result["data"]["code"])
        self.assertEqual(5.0, result["data"]["read_back"])

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_simulation_error_code_is_mapped(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        automation.model.StudyManager.studies[0].LoadsAndRestraintsManager.force_error = 2

        result = apply_force_load(automation, [2], 1000.0)

        self.assertFalse(result["success"])
        self.assertEqual("FORCE_NOT_CREATED", result["data"]["code"])
        self.assertEqual(2, result["data"]["simulation_error_code"])

    def test_non_positive_magnitude_is_rejected_before_com(self):
        automation = SimulationAutomation()

        for magnitude in (0.0, -1.0):
            with self.subTest(magnitude=magnitude):
                result = apply_force_load(automation, [2], magnitude)
                self.assertFalse(result["success"])
        self.assertEqual(0, automation.active_doc_calls)


class TorqueLoadTests(unittest.TestCase):
    @patch(FACE_LOOKUP, side_effect=lambda document, index: f"face-{index}")
    def test_adds_torque_about_a_reference_axis(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "Zasuk")

        result = apply_force_load(automation, [2], 500.0, unit="N*m",
                                  load_type="torque", reference="Axis1")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual("torque", result["data"]["load_type"])
        self.assertEqual(500.0, result["data"]["torque_nm"])
        self.assertEqual(500.0, result["data"]["read_back_nm"])
        self.assertEqual(2, result["data"]["force_type"])
        self.assertEqual("Axis1", result["data"]["reference"])
        self.assertEqual(1, result["data"]["count_after"])
        self.assertEqual(["Axis1"], automation.document.reference_lookups)

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_torque_units_are_converted_to_newton_metres(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "Zasuk")

        for unit, amount, expected in (("N*mm", 500000.0, 500.0),
                                       ("kN*m", 0.5, 500.0),
                                       ("kgf*m", 100.0, 980.665)):
            with self.subTest(unit=unit):
                result = apply_force_load(automation, [2], amount, unit=unit,
                                          load_type="torque", reference="Axis1")
                self.assertTrue(result["success"], result["message"])
                self.assertAlmostEqual(expected, result["data"]["torque_nm"], places=6)
                self.assertAlmostEqual(expected, result["data"]["read_back_nm"],
                                       places=6)

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_read_back_mismatch_is_a_failure(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "Zasuk")
        automation.model.StudyManager.studies[0].LoadsAndRestraintsManager.force_value = 7.0

        result = apply_force_load(automation, [2], 500.0, unit="N*m",
                                  load_type="torque", reference="Axis1")

        self.assertFalse(result["success"])
        self.assertEqual("FORCE_NOT_VERIFIED", result["data"]["code"])
        self.assertEqual(7.0, result["data"]["read_back"])

    def test_torque_without_a_reference_is_rejected_before_com(self):
        automation = SimulationAutomation()

        result = apply_force_load(automation, [2], 500.0, load_type="torque")

        self.assertFalse(result["success"])
        self.assertEqual("VALIDATION_FAILED", result["data"]["code"])
        self.assertEqual(0, automation.active_doc_calls)

    def test_force_unit_is_rejected_for_a_torque_before_com(self):
        automation = SimulationAutomation()

        result = apply_force_load(automation, [2], 500.0, unit="kg",
                                  load_type="torque", reference="Axis1")

        self.assertFalse(result["success"])
        self.assertEqual("VALIDATION_FAILED", result["data"]["code"])
        self.assertEqual(0, automation.active_doc_calls)

    def test_unknown_load_type_is_rejected_before_com(self):
        automation = SimulationAutomation()

        result = apply_force_load(automation, [2], 500.0, load_type="pressure")

        self.assertFalse(result["success"])
        self.assertEqual(0, automation.active_doc_calls)

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_unknown_reference_axis_is_reported(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "Zasuk")

        result = apply_force_load(automation, [2], 500.0, unit="N*m",
                                  load_type="torque", reference="Axis9")

        self.assertFalse(result["success"])
        self.assertEqual("SIMULATION_REFERENCE_NOT_FOUND", result["data"]["code"])

    @patch(FACE_LOOKUP, side_effect=lambda document, index: "face")
    def test_a_non_axis_feature_is_rejected_as_a_torque_reference(self, _lookup):
        automation = SimulationAutomation()
        create_static_study(automation, "Zasuk")

        result = apply_force_load(automation, [2], 500.0, unit="N*m",
                                  load_type="torque", reference="Front Plane")

        self.assertFalse(result["success"])
        self.assertEqual("SIMULATION_REFERENCE_NOT_FOUND", result["data"]["code"])


class RunAnalysisTests(unittest.TestCase):
    def test_meshes_and_runs_and_reports_counts(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")

        result = run_analysis(automation, quality=1)

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(1234, result["data"]["node_count"])
        self.assertEqual(567, result["data"]["element_count"])
        self.assertEqual(1.5, result["data"]["solution_time_seconds"])
        study = automation.model.StudyManager.studies[0]
        self.assertEqual(1, study.run_calls)
        self.assertEqual(1, study.Mesh.Quality)
        self.assertEqual([(0, 4.0, 0.2)], study.created_meshes)

    def test_mesh_error_code_is_mapped(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        automation.model.StudyManager.studies[0].mesh_error = 4

        result = run_analysis(automation)

        self.assertFalse(result["success"])
        self.assertEqual("MESH_FAILED", result["data"]["code"])
        self.assertEqual(4, result["data"]["simulation_error_code"])

    def test_authorization_failure_is_reported_specifically(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        automation.model.StudyManager.studies[0].run_error = 22

        result = run_analysis(automation)

        self.assertFalse(result["success"])
        self.assertEqual("ANALYSIS_AUTHORIZATION_FAILED", result["data"]["code"])

    def test_failed_mesh_components_are_a_failure(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        automation.model.StudyManager.studies[0].Mesh.failed = 2

        result = run_analysis(automation)

        self.assertFalse(result["success"])
        self.assertEqual("MESH_INVALID", result["data"]["code"])


class StressResultTests(unittest.TestCase):
    def test_reads_von_mises_min_and_max(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")

        result = get_stress_results(automation)

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(9, result["data"]["component"])
        self.assertEqual(33.5, result["data"]["stress_max_mpa"])
        self.assertEqual(-1.25, result["data"]["stress_min_mpa"])
        self.assertEqual(91, result["data"]["node_max"])
        study = automation.model.StudyManager.studies[0]
        call = study.Results.calls[0]
        self.assertEqual((9, 0, 1, 3), (call[0], call[1], call[2], call[4]))

    def test_unavailable_step_is_reported(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        automation.model.StudyManager.studies[0].Results.available_steps = 1

        result = get_stress_results(automation, step=3)

        self.assertFalse(result["success"])
        self.assertEqual("RESULTS_STEP_UNAVAILABLE", result["data"]["code"])

    def test_negative_maximum_stress_is_rejected(self):
        automation = SimulationAutomation()
        create_static_study(automation, "S1")
        automation.model.StudyManager.studies[0].Results.values = [0, 0.0, 0, -5.0]

        result = get_stress_results(automation)

        self.assertFalse(result["success"])
        self.assertEqual("RESULTS_NOT_VALID", result["data"]["code"])

    def test_missing_study_is_reported(self):
        automation = SimulationAutomation()

        result = get_stress_results(automation, study="nope")

        self.assertFalse(result["success"])
        self.assertEqual("SIMULATION_NO_STUDY", result["data"]["code"])


if __name__ == "__main__":
    unittest.main()
