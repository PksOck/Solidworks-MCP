"""
Standard parts tools (part E, Toolbox milestone).

Design: the MCP **never reads the SOLIDWORKS Toolbox directly**; it reads its
own generated library (solidworks_mcp/standard_library/, overridable with the
SW_MCP_STANDARD_LIBRARY env var). The library is filled by
scripts/sync_standard_library.py (see docs/upgrade/STANDARD-LIBRARY-FLOW.md).

- index.json : catalog rows {standard, category, subcategory, type, file,
                               rel, source, path}
- sizes.json : {rel: [materialised configuration names, e.g. "ISO 4762 M10 x
                              16 - 16N"]}

The library directory must be explicitly approved as an output root for JIT
copies. Catalog synchronization remains a separate CLI operation.
"""

import hashlib
import json
import logging
import math
import os
import shutil
import uuid
from pathlib import Path

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass, WriteDeniedError
from ..registry import tool
from .assembly import insert_component

logger = logging.getLogger("SolidWorksMCP")

LIBRARY_ENV_VAR = "SW_MCP_STANDARD_LIBRARY"
DEFAULT_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "standard_library"
INDEX_FILE = "index.json"
SIZES_FILE = "sizes.json"

# DIN 934 (1987), style 1, coarse thread; (major, pitch, s, m, tap drill), mm.
# Nominal s and m from:
# https://boltingspecialist.com/dimensions/din-934-hex-nuts/
# Coarse pitch and recommended tapping drill from:
# https://fullerfasteners.com/tech/recommended-tapping-drill-size/
# Tap drill is the modeled bore, NOT the nominal thread ID. Four driving
# dimension names were verified on a Toolbox copy (nut_true_drivers_probe.py).
# Each row must still pass live rebuild and saved-copy checks before publication.
DIN934_NUTS = {
    "DIN 934 M3": (3, 0.5, 5.5, 2.4, 2.5),
    "DIN 934 M3.5": (3.5, 0.6, 6, 2.8, 2.9),
    "DIN 934 M4": (4, 0.7, 7, 3.2, 3.3),
    "DIN 934 M5": (5, 0.8, 8, 4, 4.2),
    "DIN 934 M6": (6, 1, 10, 5, 5),
    "DIN 934 M7": (7, 1, 11, 5.5, 6),
    "DIN 934 M8": (8, 1.25, 13, 6.5, 6.75),
    "DIN 934 M10": (10, 1.5, 17, 8, 8.5),
    "DIN 934 M12": (12, 1.75, 19, 10, 10.2),
    "DIN 934 M14": (14, 2, 22, 11, 12),
    "DIN 934 M16": (16, 2, 24, 13, 14),
    "DIN 934 M18": (18, 2.5, 27, 15, 15.5),
    "DIN 934 M20": (20, 2.5, 30, 16, 17.5),
    "DIN 934 M22": (22, 2.5, 32, 18, 19.5),
    "DIN 934 M24": (24, 3, 36, 19, 21),
    "DIN 934 M27": (27, 3, 41, 22, 24),
    "DIN 934 M30": (30, 3.5, 46, 24, 26.5),
}
DIN934_MASTER = "hex nut style 1 gradeab_din.sldprt"

# DIN 125 A / ISO 7089 normal series: (bore, OD, thickness), nominal mm.
# Source table identifies DIN 125 A as equivalent and gives d1 min, d2 max,
# and nominal midpoint of the h tolerance band:
# https://www.fasteners.eu/standards/iso/7089/
DIN125A_WASHERS = {
    "DIN 125A M3": (3.2, 7, 0.5),
    "DIN 125A M3.5": (3.7, 8, 0.5),
    "DIN 125A M4": (4.3, 9, 0.8),
    "DIN 125A M5": (5.3, 10, 1),
    "DIN 125A M6": (6.4, 12, 1.6),
    "DIN 125A M7": (7.4, 14, 1.6),
    "DIN 125A M8": (8.4, 16, 1.6),
    "DIN 125A M10": (10.5, 20, 2),
    "DIN 125A M12": (13, 24, 2.5),
    "DIN 125A M14": (15, 28, 2.5),
    "DIN 125A M16": (17, 30, 3),
    "DIN 125A M18": (19, 34, 3),
    "DIN 125A M20": (21, 37, 3),
    "DIN 125A M22": (23, 39, 3),
    "DIN 125A M24": (25, 44, 4),
    "DIN 125A M27": (28, 50, 4),
    "DIN 125A M30": (31, 56, 4),
}
DIN125A_MASTER = "plain washer grade a_din.sldprt"

# ISO 4762 / DIN 912; M10x25 is an enumerated preferred length:
# https://www.fasteners.eu/standards/ISO/4762/
# This copy inherits the verified M10x16 materialized Toolbox configuration;
# only length is changed. Other diameters need separately verified drivers.
ISO4762_SCREWS = {"ISO 4762 M10 x 25": (10, 25, 16, 10)}  # shank, L, head OD, head height
ISO4762_MASTER = "socket head cap screw_iso.sldprt"
ISO4762_BASE = "ISO 4762 M10 x 16 - 16N"

SYNC_HINT = (
    "Run: .venv\\Scripts\\python.exe scripts\\sync_standard_library.py "
    "--out solidworks_mcp\\standard_library"
)


def library_dir() -> Path:
    override = os.environ.get(LIBRARY_ENV_VAR)
    return Path(override) if override else DEFAULT_LIBRARY_DIR


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as error:
        logger.warning("could not read %s: %s", path, error)
        return None


def _matches(rows, standard=None, type_=None, file_=None):
    std = standard.strip().casefold() if standard else ""
    typ = type_.strip().casefold() if type_ else ""
    fil = file_.strip().casefold() if file_ else ""
    for row in rows:
        if std and not (row["standard"].casefold() == std
                        or row["standard_folder"].casefold() == std):
            continue
        if typ and typ not in row["type"].casefold():
            continue
        if fil and row["file"].casefold() != fil:
            continue
        yield row


def _is_fastener(row: dict) -> bool:
    category = str(row.get("category") or "").casefold()
    return category in {"bolts and screws", "nuts", "washers"}


def _select_row(sw, rows, standard, type_, file_):
    matched = list(_matches(rows, standard, type_, file_))
    if not matched:
        return None, sw._result(
            False,
            f"Standard part not found (standard={standard!r}, type={type_!r}, "
            f"file={file_!r}).",
            SwErrors.swInvalidInput, {"code": "STANDARD_PART_NOT_FOUND"})
    # the same logical part is usually present twice: once from browser, once
    # from the custom Toolbox tree; browser rows come first, so keep the first
    # occurrence of each (file, standard) pair
    unique: list = []
    seen: set = set()
    for row in matched:
        key = (row["file"].casefold(), row["standard"].casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    matched = unique
    if len(matched) > 1 and not file_:
        candidates = [{"standard": r["standard"], "type": r["type"],
                       "rel": r["rel"]} for r in matched[:20]]
        return None, sw._result(
            False,
            f"{len(matched)} parts match; pass file= to disambiguate.",
            SwErrors.swInvalidInput,
            {"code": "AMBIGUOUS_STANDARD_PART", "candidates": candidates})
    return matched[0], None


def _source_copy(lib: Path, row: dict) -> Path:
    """Portable copy of a sized part, if it was copied with --copy-sized."""
    rel = row["rel"]
    if row.get("source") == "custom" and "/" in rel:
        rel = rel.split("/", 1)[1]
    return lib / "source" / row["standard"] / rel


def _master_file(lib: Path, row: dict) -> str:
    """Master file for a row: the portable source copy when present, else the
    original Toolbox path recorded at sync time."""
    copy = _source_copy(lib, row)
    if copy.is_file():
        return str(copy)
    return row.get("path") or ""


def _sized_cache_path(lib: Path, row: dict, size: str) -> Path:
    """Prepared-copy path for one (part, size) under lib/sized/ (gitignored)."""
    rel = row["rel"]
    if row.get("source") == "custom" and "/" in rel:
        rel = rel.split("/", 1)[1]
    safe_size = "".join(c if c not in '<>:"/\\|?*' else "_" for c in size)
    digest = hashlib.md5(f"{row['rel']}|{size}".encode("utf-8", "surrogatepass")).hexdigest()[:10]
    stem = Path(rel).stem
    return lib / "sized" / row["standard"] / f"{stem}__{digest}__{safe_size}.sldprt"


def _din934_nut(row: dict) -> bool:
    return (row.get("standard") == "DIN" and row.get("category") == "nuts"
            and row.get("file", "").casefold() == DIN934_MASTER
            and row.get("rel", "").replace("\\", "/").casefold().endswith(
                "nuts/hex nuts/" + DIN934_MASTER))


def _din125a_washer(row: dict) -> bool:
    return (row.get("standard") == "DIN" and row.get("category") == "washers"
            and row.get("file", "").casefold() == DIN125A_MASTER
            and row.get("rel", "").replace("\\", "/").casefold().endswith(
                "washers/plain washers/" + DIN125A_MASTER))


def _iso4762_screw(row: dict) -> bool:
    return (row.get("standard") == "ISO" and row.get("category") == "bolts and screws"
            and row.get("file", "").casefold() == ISO4762_MASTER
            and row.get("rel", "").replace("\\", "/").casefold().endswith(
                "bolts and screws/hexagon socket head screws/" + ISO4762_MASTER))


def _features_clear(doc):
    feature = com(doc, "FirstFeature")
    while feature is not None:
        if com(feature, "GetErrorCode") != 0:
            return False
        feature = com(feature, "GetNextFeature")
    return True


def _nut_geometry(doc, dimensions):
    """Check actual solid, not equation-driven sketch dimensions or cosmetics."""
    major, _pitch, flats, thickness, bore = dimensions
    bodies = com(doc, "GetBodies2", 0, False) or ()
    if len(bodies) != 1:
        return False
    body = bodies[0]
    box = com(body, "GetBodyBox")
    if not box or len(box) != 6:
        return False
    close = lambda actual, expected: math.isclose(actual, expected / 1000, abs_tol=0.00005)
    if not (close(box[3] - box[0], flats)
            and close(box[4] - box[1], 2 * flats / math.sqrt(3))
            and close(box[5] - box[2], thickness)):
        return False
    bore_found = False
    for face in com(body, "GetFaces") or ():
        surface = com(face, "GetSurface")
        if com(surface, "IsCylinder"):
            cylinder = com(surface, "CylinderParams")
            # This model also has a cosmetic thread cylinder beyond the body.
            if (cylinder and len(cylinder) >= 7 and
                    close(2 * cylinder[6], bore) and
                    abs(cylinder[0]) < 0.00005 and abs(cylinder[1]) < 0.00005 and
                    abs(cylinder[2] - box[2]) < 0.00005):
                bore_found = True
    return bore_found


def _nut_valid(doc, size, dimensions):
    active = com(com(com(doc, "ConfigurationManager"), "ActiveConfiguration"), "Name")
    if active != size:
        return False
    for key, mm in zip(("Thread_major@ThreadCosmetic", "Width_flats@BaseNutSke",
                        "Thickness@BaseNut", "Tap_drill@BaseNutSke"),
                       (dimensions[0], dimensions[2], dimensions[3], dimensions[4])):
        dim = com(doc, "Parameter", key)
        if dim is None or not math.isclose(com(dim, "SystemValue"), mm / 1000, abs_tol=0.000001):
            return False
    return _features_clear(doc) and _nut_geometry(doc, dimensions)


def _washer_valid(doc, size, dimensions):
    bore, outer, thickness = dimensions
    active = com(com(com(doc, "ConfigurationManager"), "ActiveConfiguration"), "Name")
    if active != size:
        return False
    for key, mm in (("Inside_dia@Sketch1", bore), ("Outside_dia@Sketch1", outer),
                    ("Thickness@Sketch1", thickness)):
        dim = com(doc, "Parameter", key)
        if dim is None or not math.isclose(com(dim, "SystemValue"), mm / 1000, abs_tol=0.000001):
            return False
    bodies = com(doc, "GetBodies2", 0, False) or ()
    if len(bodies) != 1 or not _features_clear(doc):
        return False
    body = bodies[0]
    box = com(body, "GetBodyBox")
    if not box or len(box) != 6:
        return False
    close = lambda actual, expected: math.isclose(actual, expected / 1000, abs_tol=0.00005)
    if not (close(box[3] - box[0], thickness)
            and close(box[4] - box[1], outer)
            and close(box[5] - box[2], outer)):
        return False
    for face in com(body, "GetFaces") or ():
        surface = com(face, "GetSurface")
        if com(surface, "IsCylinder"):
            cylinder = com(surface, "CylinderParams")
            if (cylinder and len(cylinder) >= 7
                    and close(2 * cylinder[6], bore)
                    and abs(abs(cylinder[3]) - 1) < 0.00001
                    and abs(cylinder[4]) < 0.00001
                    and abs(cylinder[5]) < 0.00001):
                return True
    return False


def _iso4762_valid(doc, size, dimensions):
    shank, length, head_od, head_height = dimensions
    active = com(com(com(doc, "ConfigurationManager"), "ActiveConfiguration"), "Name")
    if active != size:
        return False
    dim = com(doc, "Parameter", "Length@BodySke")
    if dim is None or not math.isclose(com(dim, "SystemValue"), length / 1000, abs_tol=0.000001):
        return False
    bodies = com(doc, "GetBodies2", 0, False) or ()
    if len(bodies) != 1 or not _features_clear(doc):
        return False
    body = bodies[0]
    box = com(body, "GetBodyBox")
    if not box or len(box) != 6:
        return False
    close = lambda actual, expected: math.isclose(actual, expected / 1000, abs_tol=0.00005)
    if not (close(box[3] - box[0], length + head_height)
            and close(box[4] - box[1], head_od)
            and close(box[5] - box[2], head_od)):
        return False
    for face in com(body, "GetFaces") or ():
        surface = com(face, "GetSurface")
        if com(surface, "IsCylinder"):
            cylinder = com(surface, "CylinderParams")
            if (cylinder and len(cylinder) >= 7 and close(2 * cylinder[6], shank)
                    and abs(abs(cylinder[3]) - 1) < 0.00001):
                return True
    return False


def _prepare_verified_copy(sw, lib: Path, row: dict, size: str, drivers, valid,
                           base_configuration: str | None = None):
    """Publish one prepared copy only after rebuild, save and reopen checks."""
    policy = getattr(sw, "_path_policy", None)
    target = _sized_cache_path(lib, row, size)
    if policy is None:
        return None
    try:
        policy.require_write(target, OperationClass.MUTATE)
    except WriteDeniedError:
        return None
    master = _master_file(lib, row)
    if not master or not os.path.isfile(master) or sw.app is None:
        return None
    app = sw.app
    if hasattr(app, "_oleobj_"):
        import win32com.client
        app = win32com.client.dynamic.Dispatch(app)
    import pythoncom
    import win32com.client as wc
    def open_copy(path):
        errors = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        doc = com(app, "OpenDoc6", str(path), 1, 1, "", errors, warnings)
        return doc, errors, warnings
    def close_copy(doc):
        if doc is not None:
            com(app, "CloseDoc", com(doc, "GetTitle"))
    doc = None
    try:
        if target.is_file():
            # Do not close an assembly's already-open instance of this part.
            if hasattr(app, "GetOpenDocumentByName") and com(app, "GetOpenDocumentByName", str(target)) is not None:
                return None
            doc, _, _ = open_copy(target)
            return str(target) if doc is not None and valid(doc) else None
        staging = target.with_name(target.stem + ".pending-" + uuid.uuid4().hex + ".sldprt")
        policy.require_write(staging, OperationClass.MUTATE)
        staging.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(master, staging)
        os.chmod(staging, 0o666)
        doc, errors, warnings = open_copy(staging)
        if doc is None:
            return None
        manager = com(doc, "ConfigurationManager")
        if base_configuration:
            if com(doc, "GetConfigurationByName", base_configuration) is None:
                return None
            com(doc, "ShowConfiguration2", base_configuration)
            if com(com(manager, "ActiveConfiguration"), "Name") != base_configuration:
                return None
        if com(doc, "GetConfigurationByName", size) is None:
            if com(manager, "AddConfiguration", size, "", "", 0, "", "") is None:
                return None
        com(doc, "ShowConfiguration2", size)  # may return False even when activated
        active = com(com(manager, "ActiveConfiguration"), "Name")
        if active != size:
            return None
        null = wc.VARIANT(pythoncom.VT_EMPTY, None)
        for key, mm in drivers:
            dim = com(doc, "Parameter", key)
            if dim is None:
                return None
            com(dim, "SetSystemValue3", mm / 1000, 1, null)
            if not math.isclose(com(dim, "SystemValue"), mm / 1000, abs_tol=0.000001):
                return None
        com(com(doc, "GetEquationMgr"), "EvaluateAll")
        if not com(doc, "EditRebuild3") or not com(doc, "ForceRebuild3", False):
            return None
        if not com(doc, "EditRebuild3") or not valid(doc):
            return None
        errors.value = 0
        if not com(doc, "Save3", 0, errors, warnings) or errors.value:
            return None
        close_copy(doc)
        doc = None
        doc, _, _ = open_copy(staging)
        if doc is None or not com(doc, "EditRebuild3") or not valid(doc):
            return None
        close_copy(doc)
        doc = None
        # Do not overwrite an existing cache, including one from another writer.
        if target.exists():
            return None
        os.rename(staging, target)
        return str(target)
    except Exception as error:
        logger.warning("standard part preparation failed for %s: %s", size, error)
        return None
    finally:
        if doc is not None:
            try:
                close_copy(doc)
            except Exception:
                pass


def _prepare_din934_nut(sw, lib: Path, row: dict, size: str):
    dimensions = DIN934_NUTS[size]
    return _prepare_verified_copy(sw, lib, row, size,
        (("Tap_drill@BaseNutSke", dimensions[4]),
         ("Thread_major@ThreadCosmetic", dimensions[0]),
         ("Width_flats@BaseNutSke", dimensions[2]),
         ("Thickness@BaseNut", dimensions[3])),
        lambda doc: _nut_valid(doc, size, dimensions))


def _prepare_din125a_washer(sw, lib: Path, row: dict, size: str):
    dimensions = DIN125A_WASHERS[size]
    return _prepare_verified_copy(sw, lib, row, size,
        (("Inside_dia@Sketch1", dimensions[0]),
         ("Outside_dia@Sketch1", dimensions[1]),
         ("Thickness@Sketch1", dimensions[2])),
        lambda doc: _washer_valid(doc, size, dimensions))


def _prepare_iso4762_screw(sw, lib: Path, row: dict, size: str):
    dimensions = ISO4762_SCREWS[size]
    return _prepare_verified_copy(sw, lib, row, size,
        (("Length@BodySke", dimensions[1]),),
        lambda doc: _iso4762_valid(doc, size, dimensions), ISO4762_BASE)


def _prepare_sized_copy(sw, lib: Path, row: dict, size: str):
    """JIT: turn one Toolbox size into a real part file.

    Verified live (2026-09-23): AddComponent5 with a configuration *name* on a
    Toolbox part silently inserts the part's active configuration instead of
    the requested one. The working recipe is to prep a writable copy whose
    active configuration is the requested size -- ShowConfiguration2, rebuild,
    save -- then insert that copy. Returns the prepared path, or None.
    """
    target = _sized_cache_path(lib, row, size)
    policy = getattr(sw, "_path_policy", None)
    if policy is not None:
        try:
            policy.require_write(target, OperationClass.MUTATE)
        except WriteDeniedError as error:
            logger.warning("sized prep: write denied: %s", error)
            return None
    if os.path.isfile(target):
        return str(target)
    master = _master_file(lib, row)
    if not master or not os.path.isfile(master):
        logger.warning("sized prep: master missing for %s", row["rel"])
        return None

    app = getattr(sw, "app", None)
    if app is None:
        logger.warning("sized prep: no app connection")
        return None
    if hasattr(app, "_oleobj_"):
        import win32com.client
        app = win32com.client.dynamic.Dispatch(app)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(master, target)
        os.chmod(target, 0o666)
    except OSError as error:
        logger.warning("sized prep: copy failed: %s", error)
        return None

    import pythoncom
    import win32com.client as wc
    doc = None
    try:
        errors = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        # swOpenDocOptions_Silent (1) + writable
        doc = com(app, "OpenDoc6", str(target), 1, 1, "", errors, warnings)
        if doc is None:
            logger.warning("sized prep: could not open %s", target)
            return None
        cfg = com(doc, "GetConfigurationByName", size)
        if cfg is None:
            logger.warning("sized prep: config %r not found in %s", size, row["rel"])
            return None
        if not com(doc, "ShowConfiguration2", size):  # activates the size
            logger.warning("sized prep: ShowConfiguration2 failed for %r", size)
            return None
        if not com(doc, "EditRebuild3"):
            logger.warning("sized prep: rebuild failed for %r", size)
            return None
        if not com(doc, "Save3", 0, errors, warnings):
            logger.warning("sized prep: save failed for %r", size)
            return None
        return str(target)
    except Exception as error:
        logger.warning("sized prep failed for %s %r: %s", row["rel"], size, error)
        return None
    finally:
        if doc is not None:
            try:
                com(app, "CloseDoc", com(doc, "GetTitle"))
            except Exception:
                pass


@tool(
    name="list_standard_parts",
    description=(
        "List standard parts from the synced library: per-standard counts, or "
        "the full parts list for one standard. Data comes from the generated "
        "index.json; no SolidWorks calls are made."
    ),
    schema={
        "type": "object",
        "properties": {
            "standard": {"type": "string",
                         "description": "Standard id or folder, e.g. ISO, DIN, ANSI_Metric, SKF."},
        },
        "required": [],
    },
    operation_class=OperationClass.READ,
)
def list_standard_parts(sw, standard: str | None = None) -> dict:
    """Catalog of standard parts from the synced library (no COM)."""
    lib = library_dir()
    index = _load_json(lib / INDEX_FILE)
    if not isinstance(index, list) or not index:
        return sw._result(
            False,
            "Standard library not found. " + SYNC_HINT,
            SwErrors.swFileNotFoundError, {"code": "STANDARD_LIBRARY_NOT_FOUND",
                                           "library": str(lib)})

    if standard:
        rows = list(_matches(index, standard=standard))
        if not rows:
            return sw._result(False, f"No parts for standard: {standard}.",
                              SwErrors.swInvalidInput,
                              {"code": "STANDARD_NOT_FOUND"})
        parts = [{"standard": r["standard"], "type": r["type"],
                  "subcategory": r["subcategory"], "file": r["file"],
                  "rel": r["rel"], "source": r["source"]} for r in rows]
        return sw._result(True, f"{len(parts)} parts for {standard}.",
                          data={"standard": standard, "parts": parts})

    by_standard: dict[str, dict] = {}
    for row in index:
        entry = by_standard.setdefault(
            row["standard"], {"part_count": 0, "categories": set()})
        entry["part_count"] += 1
        entry["categories"].add(row["category"] or row["subcategory"] or row["type"])
    summary = {std: {"part_count": e["part_count"],
                     "categories": sorted(c for c in e["categories"] if c)}
               for std, e in sorted(by_standard.items())}
    return sw._result(True, f"{len(index)} parts across {len(summary)} standards.",
                      data={"standards": summary})


@tool(
    name="get_standard_part_sizes",
    description=(
        "Return the materialised sizes of a standard part, e.g. the Toolbox "
        "configurations 'ISO 4762 M10 x 16 - 16N'. Pass the same filters as "
        "list_standard_parts. Sizes come from sizes.json; parts SolidWorks has "
        "never configured have none. Verified DIN 934 / DIN 125A M3-M30 and "
        "ISO 4762 M10x25 are separately offered under preparable_sizes and inserted "
        "only after geometry and save/reopen verification."
    ),
    schema={
        "type": "object",
        "properties": {
            "standard": {"type": "string", "description": "Standard id or folder, e.g. ISO."},
            "type": {"type": "string", "description": "Substring of the part type, e.g. 'socket head cap'."},
            "file": {"type": "string", "description": "Exact master file name, to disambiguate."},
        },
        "required": ["standard"],
    },
    operation_class=OperationClass.READ,
)
def get_standard_part_sizes(sw, standard: str, type: str = "",
                            file: str = "") -> dict:
    """Materialised sizes of one standard part type."""
    lib = library_dir()
    index = _load_json(lib / INDEX_FILE)
    sizes = _load_json(lib / SIZES_FILE) or {}
    if not isinstance(index, list):
        return sw._result(
            False, "Standard library not found. " + SYNC_HINT,
            SwErrors.swFileNotFoundError,
            {"code": "STANDARD_LIBRARY_NOT_FOUND", "library": str(lib)})

    matched = list(_matches(index, standard=standard, type_=type, file_=file))
    if not matched:
        return sw._result(False, f"Standard part not found: {standard}"
                          f"{'/' + type_ if type_ else ''}{'/' + file_ if file_ else ''}.",
                          SwErrors.swInvalidInput,
                          {"code": "STANDARD_PART_NOT_FOUND"})
    entries = []
    for row in matched:
        part_sizes = sizes.get(row["rel"], [])
        entries.append({
            "standard": row["standard"], "type": row["type"],
            "file": row["file"], "rel": row["rel"], "source": row["source"],
            "sizes": part_sizes, "size_count": len(part_sizes),
            "preparable_sizes": [s for s in (
                DIN934_NUTS if _din934_nut(row) else
                DIN125A_WASHERS if _din125a_washer(row) else
                ISO4762_SCREWS if _iso4762_screw(row) else ()) if s not in part_sizes],
        })
    total = sum(len(e["sizes"]) for e in entries)
    return sw._result(
        True, f"{total} materialised size(s) for {len(entries)} part(s).",
        data={"parts": entries})


@tool(
    name="insert_standard_part",
    description=(
        "Insert a standard part (e.g. ISO 4017 M10 x 40) into the active assembly at x,y,z via insert_component. Fasteners require size= (e.g. 'ISO 4762 M10 x 16 - 16N'), which prepares that Toolbox size."
    ),
    schema={
        "type": "object",
        "properties": {
            "standard": {"type": "string", "description": "Standard id or folder, e.g. ISO, DIN"},
            "type": {"type": "string", "description": "Part type substring, e.g. 'hex screw'"},
            "file": {"type": "string", "description": "Exact master file name"},
            "size": {"type": "string", "description": "Configuration, e.g. 'ISO 4762 M10 x 16 - 16N'"},
            "x": {"type": "number", "description": "Meters, default 0"},
            "y": {"type": "number", "description": "Meters, default 0"},
            "z": {"type": "number", "description": "Meters, default 0"},
            "place": {"type": "string", "enum": ["center", "origin"],
                      "description": "As in insert_component"},
        },
        "required": ["standard"],
    },
    operation_class=OperationClass.MUTATE,
)
def insert_standard_part(sw, standard: str, type: str = "", file: str = "",
                         size: str = "", x: float = 0.0, y: float = 0.0,
                         z: float = 0.0, place: str = "center") -> dict:
    """Insert a standard part into the active assembly."""
    lib = library_dir()
    index = _load_json(lib / INDEX_FILE)
    sizes = _load_json(lib / SIZES_FILE) or {}
    if not isinstance(index, list):
        return sw._result(
            False, "Standard library not found. " + SYNC_HINT,
            SwErrors.swFileNotFoundError,
            {"code": "STANDARD_LIBRARY_NOT_FOUND", "library": str(lib)})

    row, err = _select_row(sw, index, standard, type, file)
    if err:
        return err

    if not size and _is_fastener(row):
        return sw._result(
            False, "Fasteners require a verified size; the master preview may have "
            "incorrect geometry. Call get_standard_part_sizes for sizes or preparable_sizes.",
            SwErrors.swInvalidInput,
            {"code": "SIZE_REQUIRED", "rel": row["rel"]})

    if size:
        # verified live: a Toolbox part ignores the configuration name passed
        # to AddComponent5; the requested size must be materialised first
        part_sizes = sizes.get(row["rel"], [])
        wanted = size.strip().casefold()
        exact = next((s for s in part_sizes if s.casefold() == wanted), None)
        generated = next((s for s in DIN934_NUTS if s.casefold() == wanted), None) if _din934_nut(row) else None
        washer = next((s for s in DIN125A_WASHERS if s.casefold() == wanted), None) if _din125a_washer(row) else None
        screw = next((s for s in ISO4762_SCREWS if s.casefold() == wanted), None) if _iso4762_screw(row) else None
        if exact is None and generated is None and washer is None and screw is None:
            return sw._result(
                False,
                f"Size {size!r} is not materialised for this part.",
                SwErrors.swInvalidInput,
                {"code": "SIZE_NOT_AVAILABLE",
                 "available": part_sizes[:50],
                 "available_count": len(part_sizes)})
        # A scanned configuration is still a legitimate size; the opt-in
        # generated name always uses the geometry-validated preparation path.
        filepath = (_prepare_din934_nut(sw, lib, row, generated) if generated is not None
                    else _prepare_din125a_washer(sw, lib, row, washer) if washer is not None
                    else _prepare_iso4762_screw(sw, lib, row, screw) if screw is not None
                    else _prepare_sized_copy(sw, lib, row, exact))
        if filepath is None:
            return sw._result(
                False,
                f"Could not prepare size {exact or generated or washer or screw!r} (toolbox part must be "
                f"rebuilt with that configuration).",
                SwErrors.swFeatureError,
                {"code": "SIZE_PREPARATION_FAILED",
                 "size": exact or generated or washer or screw, "rel": row["rel"]})
        configuration = ""
    else:
        filepath = _master_file(lib, row)
        configuration = ""
        if not filepath or not os.path.isfile(filepath):
            return sw._result(
                False,
                f"Part file missing: {filepath}. " + SYNC_HINT,
                SwErrors.swFileNotFoundError,
                {"code": "STANDARD_PART_FILE_MISSING"})

    result = insert_component(sw, filepath=filepath, x=x, y=y, z=z,
                              place=place, configuration=configuration)
    if result.get("success"):
        result["data"] = {
            **(result.get("data") or {}),
            "standard": row["standard"], "type": row["type"],
            "file": row["file"],
            "requested_size": size or None,
            "configuration": configuration or None,
            "library_source": row["source"],
        }
    return result


@tool(
    name="standard_library_status",
    description=(
        "Report the state of the standard-parts library (path, catalog and "
        "size counts, last sync) and print the exact CLI command to rebuild it."
    ),
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
)
def standard_library_status(sw) -> dict:
    """Library state and the rebuild command. The fill itself is a CLI."""
    lib = library_dir()
    index = _load_json(lib / INDEX_FILE)
    sizes = _load_json(lib / SIZES_FILE) or {}
    report_path = lib / "report.json"
    last_sync = None
    if report_path.is_file():
        last_sync = _load_json(report_path)

    state = {
        "library": str(lib),
        "index_present": isinstance(index, list) and bool(index),
        "index_count": len(index) if isinstance(index, list) else 0,
        "sizes_present": bool(sizes),
        "parts_with_sizes": sum(1 for v in sizes.values() if v),
        "last_sync": last_sync,
        "rebuild_command": SYNC_HINT + " --scan-sizes",
        "env_override": LIBRARY_ENV_VAR,
    }
    ok = state["index_present"]
    return sw._result(
        ok,
        "Standard library ready." if ok else "Standard library missing.",
        int(SwErrors.swFileNotFoundError) if not ok else 0,
        data=state)
