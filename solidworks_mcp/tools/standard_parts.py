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

Because the path policy forbids MCP writes outside approved output roots, the
fill itself stays a CLI script; the LLM-facing `standard_library_status` tool
reports state and the exact command to run.
"""

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool
from .assembly import insert_component

logger = logging.getLogger("SolidWorksMCP")

LIBRARY_ENV_VAR = "SW_MCP_STANDARD_LIBRARY"
DEFAULT_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "standard_library"
INDEX_FILE = "index.json"
SIZES_FILE = "sizes.json"

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


def _prepare_sized_copy(sw, lib: Path, row: dict, size: str):
    """JIT: turn one Toolbox size into a real part file.

    Verified live (2026-09-23): AddComponent5 with a configuration *name* on a
    Toolbox part silently inserts the part's active configuration instead of
    the requested one. The working recipe is to prep a writable copy whose
    active configuration is the requested size -- ShowConfiguration2, rebuild,
    save -- then insert that copy. Returns the prepared path, or None.
    """
    target = _sized_cache_path(lib, row, size)
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
        "never configured have none."
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
        })
    total = sum(len(e["sizes"]) for e in entries)
    return sw._result(
        True, f"{total} materialised size(s) for {len(entries)} part(s).",
        data={"parts": entries})


@tool(
    name="insert_standard_part",
    description=(
        "Insert a standard part (e.g. ISO 4017 M10 x 40) into the active "
        "assembly at x,y,z. Resolves the part from the synced library and "
        "delegates to insert_component. Pass size= (a string like 'ISO 4762 "
        "M10 x 16 - 16N') to insert that exact Toolbox size: the part is "
        "JIT-prepared (a writable copy is switched to the size configuration, "
        "rebuilt and saved, then inserted). Without size the part's default "
        "configuration is inserted."
    ),
    schema={
        "type": "object",
        "properties": {
            "standard": {"type": "string", "description": "Standard id or folder, e.g. ISO, DIN."},
            "type": {"type": "string", "description": "Substring of the part type, e.g. 'hex screw'."},
            "file": {"type": "string", "description": "Exact master file name, to disambiguate."},
            "size": {"type": "string", "description": "Materialised configuration, e.g. 'ISO 4762 M10 x 16 - 16N'."},
            "x": {"type": "number", "description": "Position in meters. Default 0."},
            "y": {"type": "number", "description": "Position in meters. Default 0."},
            "z": {"type": "number", "description": "Position in meters. Default 0."},
            "place": {"type": "string", "enum": ["center", "origin"],
                      "description": "Same semantics as insert_component."},
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

    if size:
        # verified live: a Toolbox part ignores the configuration name passed
        # to AddComponent5; the requested size must be materialised first
        part_sizes = sizes.get(row["rel"], [])
        wanted = size.strip().casefold()
        exact = next((s for s in part_sizes if s.casefold() == wanted), None)
        if exact is None:
            return sw._result(
                False,
                f"Size {size!r} is not materialised for this part.",
                SwErrors.swInvalidInput,
                {"code": "SIZE_NOT_AVAILABLE",
                 "available": part_sizes[:50],
                 "available_count": len(part_sizes)})
        filepath = _prepare_sized_copy(sw, lib, row, exact)
        if filepath is None:
            return sw._result(
                False,
                f"Could not prepare size {exact!r} (toolbox part must be "
                f"rebuilt with that configuration).",
                SwErrors.swFeatureError,
                {"code": "SIZE_PREPARATION_FAILED",
                 "size": exact, "rel": row["rel"]})
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