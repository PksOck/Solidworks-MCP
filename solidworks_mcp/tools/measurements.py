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
    name="get_body_bounding_box",
    description="Read approximate per-body and combined bounding boxes for the active part.",
    schema={"type": "object", "properties": {
        "length_unit": {"type": "string", "enum": ["mm", "cm", "m", "inch"], "default": "mm"},
        "visible_only": {"type": "boolean", "default": True},
    }, "required": []},
)
def get_body_bounding_box(sw, length_unit: str = "mm", visible_only: bool = True) -> dict:
    """Return approximate boxes; callers must not treat them as tolerance measurements."""
    if length_unit not in _LENGTH_FACTORS:
        return sw._result(False, f"Unsupported length unit: {length_unit}", SwErrors.swInvalidInput)
    doc, err = sw.get_active_doc()
    if err:
        return err
    bodies = com(doc, "GetBodies2", 0, visible_only) or []
    if not bodies:
        return sw._result(False, "No solid bodies found.", SwErrors.swUnknownError)

    factor = _LENGTH_FACTORS[length_unit]
    entries = []
    boxes = []
    for index, body in enumerate(bodies):
        box = [float(value) for value in com(body, "GetBodyBox")]
        boxes.append(box)
        try:
            name = com(body, "Name")
        except Exception:
            name = f"Body{index + 1}"
        entries.append({
            "name": name,
            "min": {"x": box[0] * factor, "y": box[1] * factor, "z": box[2] * factor},
            "max": {"x": box[3] * factor, "y": box[4] * factor, "z": box[5] * factor},
            "size": {"x": (box[3] - box[0]) * factor,
                     "y": (box[4] - box[1]) * factor,
                     "z": (box[5] - box[2]) * factor},
        })
    combined = [min(box[i] for box in boxes) for i in range(3)] + [
        max(box[i] for box in boxes) for i in range(3, 6)]
    data = {
        "unit": length_unit,
        "accuracy": "approximate",
        "method": "IBody2.GetBodyBox",
        "visible_only": visible_only,
        "bodies": entries,
        "combined": {
            "min": {"x": combined[0] * factor, "y": combined[1] * factor, "z": combined[2] * factor},
            "max": {"x": combined[3] * factor, "y": combined[4] * factor, "z": combined[5] * factor},
            "size": {"x": (combined[3] - combined[0]) * factor,
                     "y": (combined[4] - combined[1]) * factor,
                     "z": (combined[5] - combined[2]) * factor},
        },
    }
    return sw._result(True, f"Approximate bounding box for {len(entries)} body/bodies.", data=data)


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
