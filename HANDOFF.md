# SolidWorks MCP development handoff

Updated: 2026-09-21

## Resume point

- Repository: `C:\Users\Jan\Documents\Claude-Solidworks mcp`
- Branch: `additional-upgrades`
- Latest implementation commit: `d4a084b` (`feat: add tangent arc and arc slot sketch entities`)
- Do not push to a remote unless the user explicitly asks.
- SolidWorks 2025 SP1.1 must be running for the opt-in live COM tests.

## User intent and operating rules

The user extended the goal: cover everything SolidWorks offers, progressively,
starting with parts — **all sketch capabilities first, then all part features,
then surfaces, then assembly/drawings/simulation**.

- Never save scratch native SolidWorks models used for testing.
- Do not modify or save the user's manually opened SolidWorks examples.
- Scratch tests may create a new document and must close it without saving.
- SolidWorks may need to remain at least partly visible and not minimized for
  viewport capture.
- Preserve the existing explicit DXF tools. The user explicitly rejected a
  generic DXF router as unnecessary complexity:
  - `export_face_to_dxf` for a selected planar face
  - `export_flat_pattern` for sheet metal
- Use `comutil.com()` for SolidWorks members because SW COM inconsistently
  exposes properties and methods.
- Read exact signatures from `sldworks.tlb` / `swconst.tlb`; never guess
  (see `docs/api-findings.md` section 0).
- Never run two scripts driving SolidWorks at the same time.
- Use TDD: add a failing focused test, implement the minimum behavior, run the
  focused test, run a scratch COM test where applicable, then the whole suite.

## Coverage plan (new)

`docs/upgrade/PARTS-COVERAGE-PLAN.md` (local only; `docs/` is gitignored) is the
ordered backlog:

| Milestone | Content | Status |
|---|---|---|
| M1.1 | Sketch entities | partial: 13 of ~22 tools done |
| M1.2 | Sketch editing (fillet, chamfer, offset, convert, split, mirror, sketch patterns) | not started |
| M1.3 | Sketch relations and dimensions | not started |
| M1.4 | Sketch on reference plane / 3D sketch | not started |
| M2 | Part features, bodies, reference geometry, attributes | in progress from older work |
| M3 | Surface modeling | not started |
| M4 | Sheet metal, weldments, assembly, drawings, simulation | mixed |

## Latest completed slice: sketch entities (M1.1)

Implementation:

- `solidworks_mcp/tools/sketch_entities.py` (new module, 10 tools)
- registration import in `solidworks_mcp/tools/__init__.py`
- unit tests in `solidworks_mcp/tests/test_sketch_entities.py`
- live test in `solidworks_mcp/tests/live/test_sketch_entities.py`
- live evidence in `scripts/capability_requirements.json`
- findings in `docs/api-findings.md` section 22

Tools: `draw_centerline`, `draw_point`, `draw_circle_radius`,
`draw_center_rectangle`, `draw_rectangle_3point_corner`,
`draw_rectangle_3point_center`, `draw_parallelogram`, `draw_ellipse`,
`draw_elliptical_arc`, `draw_parabola`, `draw_tangent_arc`, `draw_arc_slot`,
`draw_arc_slot_3point`.

Contract:

- all coordinates are converted with the explicit `unit` argument; positive
  radii/widths are validated before any COM access
- non-coordinate COM arguments (the elliptical arc `Direction` int16, the slot
  creation and length types, the tangent arc `ArcType`) are passed outside unit
  conversion, otherwise `1` becomes `0.001` and the call fails; `_create_entity`
  therefore takes separate `leading` and `trailing` argument lists
- success requires a non-`None` sketch entity from `ISketchManager`
- `draw_tangent_arc` fixes `ArcType` at 0: a live probe showed 0-3 all produce
  an identical arc, so the flag is not exposed

Verification:

```powershell
$env:SW_MCP_LIVE_TESTS='1'
.venv\Scripts\python.exe -m unittest solidworks_mcp.tests.live.test_sketch_entities -v
```

Result: 3 passed. Every entity was drawn in its own scratch sketch on a scratch
part and verified by `ISketch` counts (`GetSketchSegments`, `GetEllipseCount`,
`GetParabolaCount`, `GetUserPointsCount`, `GetSketchSlotCount`); the part stayed
unsaved.

Full regression command:

```powershell
.venv\Scripts\python.exe -m unittest discover -s solidworks_mcp\tests -v
```

Result: 275 tests run, 27 skipped, 0 failures.

## Current capability register

Local generated reports (excluded by repository policy; regenerate with):

```powershell
.venv\Scripts\python.exe scripts\audit_capabilities.py --root . --requirements scripts\capability_requirements.json --output-json docs\upgrade\specs\capability-register.json --output-markdown docs\upgrade\specs\CAPABILITY-REGISTER.md
```

Status after this slice: 80 requirements —
65 registered, 4 internal_only, 9 absent, 1 superseded, 1 blocked
(40 verified live).

## Remaining absent capabilities

| ID | Capability | Tool | Note |
|---|---|---|---|
| 4.8 | Add drawing dimension | `add_drawing_dimension` | programmatic `AddDimension2` returns None in SW 2025 |
| 5.1–5.6 | Simulation block | `create_static_study`, `apply_material`, `apply_fixed_fixture`, `apply_force_load`, `run_analysis`, `get_stress_results` | needs a Simulation licence |
| 6.3 | Bounded traversal / performance | internal | R7 |
| M1.1-k | Perimeter (3-point) circle | — | SW 2025 exposes neither `CreatePerimeterCircle` nor `Create3PointCircle` |

Recommended next items, in the plan's order:

1. `draw_equation_curve` — confirm `CreateEquationSpline`/`CreateEquationSpline2`
   parameter semantics live before exposing them
2. M1.2 sketch editing: `CreateFillet`, `CreateChamfer`, `SketchOffset2`,
   `SketchUseEdge3`, `SketchMirror`, `SplitOpenSegment`,
   `CreateLinearSketchStepAndRepeat`, `CreateCircularSketchStepAndRepeat`
   (signature list already in `docs/api-findings.md` section 13)

## Known traps (do not relearn)

- `IModelDoc2.EditSketch` is void and returns `None` on success.
- `SketchTrim` returns `False` for `swSketchTrimClosest` even when it trims;
  prove success by observed geometry change.
- Leaveover unsaved `Part*` scratch documents wedge `create_sketch`/`draw_line`.
- Non-coordinate COM arguments must not pass through unit conversion.
- `capture_view` refuses to overwrite an existing file.

## Files owned by the user: do not stage or overwrite

```text
 M .gitignore
 M DEVELOPMENT_ROADMAP.md
 M solidworks_mcp/config.json
?? UGOTOVITVE_TEST.md
?? output/
?? scripts/build_gear.py
```

Always use explicit `git add -- <files>` rather than `git add .`.

## Recent local commits

```text
d4a084b feat: add tangent arc and arc slot sketch entities
b62204c docs: refresh handoff with the sketch entity slice and coverage plan
fca4676 feat: add ten verified sketch entity tools
557788a Fix three assembly defects found while building the gearbox test
08d9865 feat: add neutral CAD import tool with 3D Interconnect handling
f4e6660 test: live-verify assembly components and three mate types
c7ec993 test: verify sheet metal flat pattern without a bend; record edge flange block
b8befce test: live-verify sheet metal flat pattern flatten and export
83ad42a feat: create sheet metal base flange and fix flat pattern export guard
7666e36 test: live-verify weldment structural member creation
ac99344 feat: expose guarded save_document tool and register all tool modules
bd45d0d feat: add drawing marked dimensions and auto balloon
f002312 feat: add verified sketch trim and extend
639e870 feat: add verified sweep and loft features
3b912fe feat: add verified mirror feature
```

## First checks for the next model

```powershell
git branch --show-current
git status --short
git log -5 --oneline
.venv\Scripts\python.exe -m unittest discover -s solidworks_mcp\tests -v
```

Expected branch is `additional-upgrades`. Confirm that only the user-owned files
listed above are dirty before beginning another roadmap item.
