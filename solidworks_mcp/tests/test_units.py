import unittest

from solidworks_mcp.utils.units import UnitConverter


class UnitConverterContractTests(unittest.TestCase):
    def test_25_4_millimeters_equals_one_inch(self):
        converter = UnitConverter("mm")

        self.assertAlmostEqual(1.0, converter.convert(25.4, "mm", "inch"), places=12)


if __name__ == "__main__":
    unittest.main()
