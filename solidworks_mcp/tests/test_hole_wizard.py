"""Focused contract for a straight ANSI metric Hole Wizard hole."""

import unittest
from unittest.mock import patch

from solidworks_mcp.core.policy import OperationClass
from solidworks_mcp.registry import operation_class_for
from solidworks_mcp.tests.test_advanced_features import Automation, Document
from solidworks_mcp.tools.advanced_features import hole_wizard


class HoleFeature:
    Name = "Hole1"

    def GetErrorCode(self):
        return 0


class HoleManager:
    def __init__(self):
        self.args = None

    def HoleWizard5(self, *args):
        self.args = args
        return HoleFeature()


class HoleExtension:
    def __init__(self):
        self.ray = None

    def SelectByRay(self, *args):
        self.ray = args
        return True


class HoleDocument(Document):
    def __init__(self):
        super().__init__()
        self.FeatureManager = HoleManager()
        self.Extension = HoleExtension()


class HoleFace:
    class Surface:
        PlaneParams = (0, 0, 0.01, 0, 0, 1)

    def GetSurface(self):
        return self.Surface()


class HoleWizardTests(unittest.TestCase):
    @patch("solidworks_mcp.tools.advanced_features._get_planar_face_by_index", return_value=HoleFace())
    def test_straight_hole_selects_location_and_converts_dimensions(self, face_lookup):
        document = HoleDocument()
        automation = Automation(document)
        with patch("solidworks_mcp.tools.advanced_features._solid_volume_mm3", side_effect=[10000, 9700]):
            result = hole_wizard(automation, 0, [5, 6, 10], 6, 15)
        self.assertTrue(result["success"], result["message"])
        self.assertEqual(OperationClass.MUTATE, operation_class_for("hole_wizard"))
        expected = (0.005, 0.006, 0.011, 0, 0, -1, 0.0001, 2, False, 0, 0)
        for actual, wanted in zip(document.Extension.ray, expected):
            if isinstance(wanted, float):
                self.assertAlmostEqual(wanted, actual)
            else:
                self.assertEqual(wanted, actual)
        args = document.FeatureManager.args
        self.assertEqual((2, 1, 39, "Ø6.0", 0), args[:5])
        self.assertAlmostEqual(0.006, args[5])
        self.assertAlmostEqual(0.015, args[6])
        self.assertEqual((-1.0,) * 12, args[8:20])

    def test_invalid_input_does_not_touch_com(self):
        for position, diameter, depth in (([1, 2], 6, 10), ([1, 2, 3], 0, 10),
                                           ([1, 2, 3], 6, float("nan")),
                                           ([1, 2, 3], 5.25, 10)):
            automation = Automation(HoleDocument())
            result = hole_wizard(automation, 0, position, diameter, depth)
            self.assertFalse(result["success"])
            self.assertEqual(0, automation.active_doc_calls)
