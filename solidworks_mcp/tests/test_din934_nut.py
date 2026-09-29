"""The nut adapter checks real solids and never exposes an unverified copy."""

import tempfile
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from solidworks_mcp.core.policy import PathPolicy
from solidworks_mcp.tools import standard_parts as sp


ROW = {
    "standard": "DIN", "category": "nuts", "source": "browser",
    "standard_folder": "DIN", "type": "hex nut style 1 gradeab",
    "file": sp.DIN934_MASTER,
    "rel": "nuts/hex nuts/" + sp.DIN934_MASTER,
}
WASHER_ROW = {
    "standard": "DIN", "category": "washers", "source": "browser",
    "standard_folder": "DIN", "type": "plain washer grade a",
    "file": sp.DIN125A_MASTER,
    "rel": "washers/plain washers/" + sp.DIN125A_MASTER,
}
SCREW_ROW = {
    "standard": "ISO", "category": "bolts and screws", "source": "browser",
    "standard_folder": "ISO", "type": "socket head cap screw",
    "file": sp.ISO4762_MASTER,
    "rel": "bolts and screws/hexagon socket head screws/" + sp.ISO4762_MASTER,
}


class Object:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)


def good_document(bore=8.5, error=0):
    size = "DIN 934 M10"
    dims = dict(zip(("Thread_major@ThreadCosmetic", "Width_flats@BaseNutSke",
                     "Thickness@BaseNut", "Tap_drill@BaseNutSke"),
                    (10, 17, 8, 8.5)))
    cylinder = Object(IsCylinder=lambda: True,
                      CylinderParams=lambda: [0, 0, -0.008, 0, 0, 1, bore / 2000])
    body = Object(GetBodyBox=lambda: [-0.0085, -0.0098149546, -0.008,
                                       0.0085, 0.0098149546, 0],
                  GetFaces=lambda: [Object(GetSurface=lambda: cylinder)])
    feature = Object(GetErrorCode=lambda: error, GetNextFeature=lambda: None)
    return Object(ConfigurationManager=Object(ActiveConfiguration=Object(Name=size)),
                  Parameter=lambda key: Object(SystemValue=dims[key] / 1000),
                  FirstFeature=lambda: feature, GetBodies2=lambda *_: [body])


class Din934Tests(unittest.TestCase):
    def test_catalog_distinguishes_preparable_from_materialized_and_routes_m10(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.json").write_text(json.dumps([ROW]), encoding="utf-8")
            (root / "sizes.json").write_text(json.dumps({ROW["rel"]: ["existing cfg"]}), encoding="utf-8")
            class Automation:
                def _result(self, success, message, error_code=0, data=None):
                    return {"success": success, "message": message, "data": data or {}}
            sw = Automation()
            prepared = root / "verified.sldprt"
            with patch.dict(sp.os.environ, {sp.LIBRARY_ENV_VAR: str(root)}), \
                    patch.object(sp, "_prepare_din934_nut", return_value=str(prepared)) as nut, \
                    patch.object(sp, "insert_component", return_value={
                        "success": True, "data": {"name": "nut"}}) as insert:
                part = sp.get_standard_part_sizes(sw, "DIN")["data"]["parts"][0]
                self.assertEqual(["existing cfg"], part["sizes"])
                self.assertEqual(list(sp.DIN934_NUTS), part["preparable_sizes"])
                result = sp.insert_standard_part(sw, "DIN", size="DIN 934 M10")
                self.assertTrue(result["success"])
                nut.assert_called_once()
                self.assertEqual(str(prepared), insert.call_args.kwargs["filepath"])
                self.assertFalse(sp.insert_standard_part(sw, "DIN", size="DIN 934 M11")["success"])
            with patch.dict(sp.os.environ, {sp.LIBRARY_ENV_VAR: str(root)}), \
                    patch.object(sp, "_prepare_din934_nut", return_value=None), \
                    patch.object(sp, "insert_component") as insert:
                self.assertEqual("SIZE_PREPARATION_FAILED", sp.insert_standard_part(
                    sw, "DIN", size="DIN 934 M10")["data"]["code"])
                insert.assert_not_called()

    def test_geometry_requires_actual_bore_and_no_feature_errors(self):
        dimensions = sp.DIN934_NUTS["DIN 934 M10"]
        def fake_com(obj, name, *args):
            value = getattr(obj, name)
            return value(*args) if callable(value) else value
        with patch.object(sp, "com", side_effect=fake_com):
            self.assertTrue(sp._nut_valid(good_document(), "DIN 934 M10", dimensions))
            self.assertFalse(sp._nut_valid(good_document(bore=10), "DIN 934 M10", dimensions))
            self.assertFalse(sp._nut_valid(good_document(error=1), "DIN 934 M10", dimensions))

    def test_only_exact_master_is_eligible(self):
        self.assertTrue(sp._din934_nut(ROW))
        self.assertFalse(sp._din934_nut({**ROW, "file": "another nut_din.sldprt"}))
        self.assertEqual(17, len(sp.DIN934_NUTS))
        self.assertEqual((3, .5, 5.5, 2.4, 2.5), sp.DIN934_NUTS["DIN 934 M3"])
        self.assertEqual((30, 3.5, 46, 24, 26.5), sp.DIN934_NUTS["DIN 934 M30"])

    def test_denied_policy_cannot_copy_or_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / sp.DIN934_MASTER
            source.write_bytes(b"master")
            sw = SimpleNamespace(app=object(), _path_policy=PathPolicy([root / "elsewhere"]))
            with patch.object(sp, "_master_file", return_value=str(source)):
                self.assertIsNone(sp._prepare_din934_nut(sw, root, ROW, "DIN 934 M10"))
            self.assertFalse((root / "sized").exists())
            self.assertEqual(b"master", source.read_bytes())

    def test_publishes_only_after_validating_reopened_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / sp.DIN934_MASTER
            source.write_bytes(b"unchanged master")
            state = {"opens": 0, "saved": False, "bad_reopen": False, "drivers": {}}
            def fake_com(obj, name, *args):
                value = getattr(obj, name)
                return value(*args) if callable(value) else value
            def open_doc(*_args):
                state["opens"] += 1
                doc = good_document(bore=10 if state["bad_reopen"] and state["opens"] == 2 else 8.5)
                config = doc.ConfigurationManager
                config.ActiveConfiguration.Name = "Default" if state["opens"] == 1 else "DIN 934 M10"
                config.AddConfiguration = lambda name, *_: Object(Name=name)
                doc.GetConfigurationByName = lambda *_: None
                doc.ShowConfiguration2 = lambda name: setattr(config.ActiveConfiguration, "Name", name) or False
                doc.Parameter = lambda key: Object(
                    SystemValue=state["drivers"].get(key, {
                        "Tap_drill@BaseNutSke": .0085, "Thread_major@ThreadCosmetic": .01,
                        "Width_flats@BaseNutSke": .017, "Thickness@BaseNut": .008,
                    }[key]),
                    SetSystemValue3=lambda value, *_: state["drivers"].__setitem__(key, value))
                doc.GetEquationMgr = lambda: Object(EvaluateAll=lambda: -1)
                doc.EditRebuild3 = lambda: True
                doc.ForceRebuild3 = lambda *_: True
                doc.Save3 = lambda *_: state.__setitem__("saved", True) or True
                doc.GetTitle = lambda: "staging"
                return doc
            app = Object(OpenDoc6=open_doc, CloseDoc=lambda *_: None)
            sw = SimpleNamespace(app=app, _path_policy=PathPolicy([root]))
            pythoncom = types.ModuleType("pythoncom")
            pythoncom.VT_BYREF, pythoncom.VT_I4, pythoncom.VT_EMPTY = 0, 1, 2
            client = types.ModuleType("win32com.client")
            client.VARIANT = lambda *_: Object(value=0)
            win32com = types.ModuleType("win32com")
            win32com.client = client
            modules = {"pythoncom": pythoncom, "win32com": win32com,
                       "win32com.client": client}
            with patch.dict(sys.modules, modules), patch.object(sp, "com", side_effect=fake_com), \
                    patch.object(sp, "_master_file", return_value=str(source)):
                state["bad_reopen"] = True
                self.assertIsNone(sp._prepare_din934_nut(sw, root, ROW, "DIN 934 M10"))
                self.assertTrue(state["saved"])
                target = sp._sized_cache_path(root, ROW, "DIN 934 M10")
                self.assertFalse(target.exists())
                state.update(opens=0, bad_reopen=False)
                self.assertEqual(str(target), sp._prepare_din934_nut(
                    sw, root, ROW, "DIN 934 M10"))
                self.assertEqual(2, state["opens"])
                self.assertEqual(str(target), sp._prepare_din934_nut(
                    sw, root, ROW, "DIN 934 M10"))
                self.assertEqual(3, state["opens"])  # cache is reopened, not trusted by name
            self.assertEqual(b"unchanged master", source.read_bytes())


class Din125aTests(unittest.TestCase):
    def test_washer_catalog_and_insertion_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.json").write_text(json.dumps([WASHER_ROW]), encoding="utf-8")
            (root / "sizes.json").write_text("{}", encoding="utf-8")
            class Automation:
                def _result(self, success, message, error_code=0, data=None):
                    return {"success": success, "data": data or {}}
            with patch.dict(sp.os.environ, {sp.LIBRARY_ENV_VAR: str(root)}), \
                    patch.object(sp, "_prepare_din125a_washer", return_value=str(root / "ready.sldprt")) as prep, \
                    patch.object(sp, "insert_component", return_value={"success": True, "data": {}}):
                part = sp.get_standard_part_sizes(Automation(), "DIN")["data"]["parts"][0]
                self.assertEqual(list(sp.DIN125A_WASHERS), part["preparable_sizes"])
                self.assertTrue(sp.insert_standard_part(Automation(), "DIN", size="DIN 125A M10")["success"])
                prep.assert_called_once()

    def test_washer_requires_correct_solid_bore_and_feature_state(self):
        def fake_com(obj, name, *args):
            value = getattr(obj, name)
            return value(*args) if callable(value) else value
        def doc(bore=10.5, error=0):
            cylinder = Object(IsCylinder=lambda: True,
                              CylinderParams=lambda: [-.034925, 0, 0, -1, 0, 0, bore / 2000])
            body = Object(GetBodyBox=lambda: [-.002, -.01, -.01, 0, .01, .01],
                          GetFaces=lambda: [Object(GetSurface=lambda: cylinder)])
            dims = {"Inside_dia@Sketch1": .0105, "Outside_dia@Sketch1": .020,
                    "Thickness@Sketch1": .002}
            return Object(ConfigurationManager=Object(ActiveConfiguration=Object(Name="DIN 125A M10")),
                          Parameter=lambda key: Object(SystemValue=dims[key]),
                          FirstFeature=lambda: Object(GetErrorCode=lambda: error,
                                                      GetNextFeature=lambda: None),
                          GetBodies2=lambda *_: [body])
        with patch.object(sp, "com", side_effect=fake_com):
            self.assertTrue(sp._din125a_washer(WASHER_ROW))
            self.assertTrue(sp._washer_valid(doc(), "DIN 125A M10", sp.DIN125A_WASHERS["DIN 125A M10"]))
            self.assertFalse(sp._washer_valid(doc(bore=8), "DIN 125A M10", sp.DIN125A_WASHERS["DIN 125A M10"]))
            self.assertFalse(sp._washer_valid(doc(error=1), "DIN 125A M10", sp.DIN125A_WASHERS["DIN 125A M10"]))


class Iso4762Tests(unittest.TestCase):
    def test_screw_lists_length_and_routes_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.json").write_text(json.dumps([SCREW_ROW]), encoding="utf-8")
            (root / "sizes.json").write_text(json.dumps({SCREW_ROW["rel"]: [sp.ISO4762_BASE]}), encoding="utf-8")
            class Automation:
                def _result(self, success, message, error_code=0, data=None):
                    return {"success": success, "data": data or {}}
            with patch.dict(sp.os.environ, {sp.LIBRARY_ENV_VAR: str(root)}), \
                    patch.object(sp, "_prepare_iso4762_screw", return_value=str(root / "ready.sldprt")) as prep, \
                    patch.object(sp, "insert_component", return_value={"success": True, "data": {}}):
                part = sp.get_standard_part_sizes(Automation(), "ISO")["data"]["parts"][0]
                self.assertEqual(["ISO 4762 M10 x 25"], part["preparable_sizes"])
                self.assertIn(sp.ISO4762_BASE, part["sizes"])
                self.assertTrue(sp.insert_standard_part(Automation(), "ISO", size="ISO 4762 M10 x 25")["success"])
                prep.assert_called_once()

    def test_geometry_checks_shank_and_overall_length(self):
        def fake_com(obj, name, *args):
            value = getattr(obj, name)
            return value(*args) if callable(value) else value
        def doc(shank=10, xsize=.035):
            cylinder = Object(IsCylinder=lambda: True,
                              CylinderParams=lambda: [.01, 0, 0, 1, 0, 0, shank / 2000])
            body = Object(GetBodyBox=lambda: [0, -.008, -.008, xsize, .008, .008],
                          GetFaces=lambda: [Object(GetSurface=lambda: cylinder)])
            return Object(ConfigurationManager=Object(ActiveConfiguration=Object(Name="ISO 4762 M10 x 25")),
                          Parameter=lambda _: Object(SystemValue=.025),
                          FirstFeature=lambda: Object(GetErrorCode=lambda: 0, GetNextFeature=lambda: None),
                          GetBodies2=lambda *_: [body])
        with patch.object(sp, "com", side_effect=fake_com):
            self.assertTrue(sp._iso4762_screw(SCREW_ROW))
            dimensions = sp.ISO4762_SCREWS["ISO 4762 M10 x 25"]
            self.assertTrue(sp._iso4762_valid(doc(), "ISO 4762 M10 x 25", dimensions))
            self.assertFalse(sp._iso4762_valid(doc(shank=9), "ISO 4762 M10 x 25", dimensions))
            self.assertFalse(sp._iso4762_valid(doc(xsize=.026), "ISO 4762 M10 x 25", dimensions))


if __name__ == "__main__":
    unittest.main()
