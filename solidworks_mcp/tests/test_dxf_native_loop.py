import unittest
from types import SimpleNamespace
from solidworks_mcp.tools.export import _longest_edge_direction
from solidworks_mcp.tests.test_weldment_weld_bead import Edge

class CoEdge:
    calls=0
    _oleobj_=object()
    def GetEdge(self):return Edge((0,0,0),(.3,0,0))
    def GetNext(self):
        CoEdge.calls+=1
        return CoEdge()  # New Python wrapper, same native COM coedge.

class DxfLoopTests(unittest.TestCase):
    def test_stops_when_native_loop_closes_with_new_python_wrapper(self):
        CoEdge.calls=0
        face=SimpleNamespace(GetFirstLoop=SimpleNamespace(GetFirstCoEdge=CoEdge()))
        self.assertEqual(_longest_edge_direction(face),(1,0,0))
        self.assertEqual(CoEdge.calls,1)
