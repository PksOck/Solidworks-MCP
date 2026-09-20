import unittest

from solidworks_mcp.automation.sketches import SketchOperations


class Extension:
    def SelectByID2(self, *args):
        return True


class SketchManager:
    def __init__(self):
        self.AddToDB = False


class Document:
    def __init__(self):
        self.Extension = Extension()
        self.SketchManager = SketchManager()
        self.insert_calls = 0

    def InsertSketch2(self, update):
        self.insert_calls += 1

    def ClearSelection2(self, clear_all):
        return True


class Automation(SketchOperations):
    def __init__(self):
        self.document = Document()

    def get_active_doc(self):
        return self.document, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "data": data or {}}


class ExactSketchModeTests(unittest.TestCase):
    def test_create_sketch_enables_exact_geometry_only_when_requested(self):
        automation = Automation()

        result = automation.create_sketch("Front", exact_geometry=True)

        self.assertTrue(result["success"])
        self.assertTrue(automation.document.SketchManager.AddToDB)
        self.assertTrue(result["data"]["exact_geometry"])

    def test_exit_sketch_always_restores_normal_inference_mode(self):
        automation = Automation()
        automation.document.SketchManager.AddToDB = True

        result = automation.exit_sketch()

        self.assertTrue(result["success"])
        self.assertFalse(automation.document.SketchManager.AddToDB)


if __name__ == "__main__":
    unittest.main()
