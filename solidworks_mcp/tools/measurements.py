"""Read-only geometric and physical measurements."""

from ..comutil import com
from ..constants import SwErrors
from ..registry import tool


_LENGTH_FACTORS = {
    "m": 1.0,
    "cm": 100.0,
    "mm": 1000.0,
    "inch": 39.37007874015748,
}


@tool(
    name="get_mass_properties",
    description="Read volume, area, mass, density, and center of mass without modifying the active model.",
    schema={"type": "object", "properties": {
        "length_unit": {"type": "string", "enum": ["mm", "cm", "m", "inch"], "default": "mm"},
    }, "required": []},
)
def get_mass_properties(sw, length_unit: str = "mm") -> dict:
    """Return SI source values plus explicit display-unit conversions."""
    if length_unit not in _LENGTH_FACTORS:
        return sw._result(False, f"Unsupported length unit: {length_unit}", SwErrors.swInvalidInput)
    doc, err = sw.get_active_doc()
    if err:
        return err
    mass_property = com(com(doc, "Extension"), "CreateMassProperty")
    if mass_property is None:
        return sw._result(False, "SolidWorks could not calculate mass properties.",
                          SwErrors.swUnknownError)

    volume_m3 = float(com(mass_property, "Volume"))
    area_m2 = float(com(mass_property, "SurfaceArea"))
    mass_kg = float(com(mass_property, "Mass"))
    density_kg_m3 = float(com(mass_property, "Density"))
    center_m = [float(value) for value in com(mass_property, "CenterOfMass")]
    factor = _LENGTH_FACTORS[length_unit]
    data = {
        "si": {
            "volume_m3": volume_m3,
            "surface_area_m2": area_m2,
            "mass_kg": mass_kg,
            "center_of_mass_m": center_m,
        },
        "display": {
            "volume": volume_m3 * factor ** 3,
            "volume_unit": f"{length_unit}^3",
            "surface_area": area_m2 * factor ** 2,
            "surface_area_unit": f"{length_unit}^2",
            "center_of_mass": [value * factor for value in center_m],
            "center_of_mass_unit": length_unit,
        },
        "material_evidence": {
            "density_kg_m3": density_kg_m3,
            "source": "IMassProperty",
            "material_name": None,
            "material_name_status": "not_inspected",
        },
        "method": "SolidWorks IMassProperty",
    }
    return sw._result(True, f"Volume: {data['display']['volume']:.3f} {length_unit}^3",
                      data=data)
