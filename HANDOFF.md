# SolidWorks MCP development handoff

Updated: 2026-09-22

## Resume point

- Repository: `C:\Users\Jan\Documents\Claude-Solidworks mcp`
- Branch: `additional-upgrades`
- Latest implementation commit: `7d5c181` (`feat: draw equation-driven curves and pin down their mixed units`)
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
| M1.1 | Sketch entities | done: 21 entity tools plus the equation-driven curve, all live-verified in one sequence |
| M1.2 | Sketch editing | slices 1–3 done: fillet, chamfer, offset, mirror, split, linear and circular patterns, scale, construction toggle, rotate |
| M1.3 | Sketch relations, dimensions and text | done (add/list/delete relations, status, driving dimension, sketch text) |
| M1.4 | Sketching on model geometry and 3D sketches | done (plane, 3D sketch, convert entities, 3D equation curve) |
| M2 | Part features, bodies, reference geometry, attributes | in progress from older work |
| M3 | Surface modeling | not started |
| M4 | Sheet metal, weldments, assembly, drawings, simulation | mixed |

## Latest completed slices: sketch editing (M1.2)

Implementation in `solidworks_mcp/tools/sketch_edit.py` (shared with trim and
extend):

- slice 1: `sketch_fillet`, `sketch_chamfer`, `offset_entities`,
  `sketch_mirror`, `split_entities`, `sketch_pattern_linear`,
  `sketch_pattern_circular`
- slice 2: `scale_entities`, `toggle_construction`, closed-entity splitting
  through `split_entities(x, y, x2, y2)`
- slice 3: `rotate_entities` (see below)

Contract:

- every tool reopens the named sketch, selects the entities by their exact
  sketch segment names, runs one `ISketchManager`/`IModelDoc2` call, closes the
  sketch and reports success **only when the sketch geometry changed**
  (`_edit_and_verify(..., require_change=True)`); the API return value is not
  trusted
- `_edit_and_verify` takes an `observe` hook for edits that do not change
  segment lengths: `toggle_construction` compares the
  `ConstructionGeometry` flags, `rotate_entities` compares
  `_sketch_state` = (segment lengths, `ISketch.ModelToSketchTransform.ArrayData`)
- **`SketchModifyRotate` rotates the sketch coordinate system, not the segment
  coordinates.** The segment getters keep returning the old coordinates even
  after a rebuild or after the sketch is closed and reopened, so a
  length-only observer reports a false failure. `rotate_entities` therefore
  treats a change in *either* half of `_sketch_state` as success. The edit is
  real and durable: front-view screenshots show the rotation, and extruding the
  rotated profile gives a body box with the axes swapped. See
  `docs/api-findings.md` section 25
- non-length COM arguments (chamfer type, `CapEnds` int, angles) bypass unit
  conversion; lengths go through `sw._units.to_meters`
- `sketch_mirror` selects the mirror axis last and rejects an axis that is one
  of the mirrored entities
- `sketch_pattern_circular` takes the pattern **centre** and derives the two
  arguments SolidWorks actually wants (`ArcRadius`, `ArcAngle`), reporting them
  back; see `docs/api-findings.md` section 23.4 for the verified formula
- `sketch_pattern_linear` defaults `angle_y_deg` to 90 so `count_y` produces a
  real grid; with both angles 0 every instance lands on one line
- `toggle_construction` writes `ISketchSegment.ConstructionGeometry` through
  `comutil.set_com`, because calling the member with an argument dispatches a
  property **get** and silently does nothing

Verification:

```powershell
.venv\Scripts\python.exe -m unittest solidworks_mcp.tests.test_sketch_edit_tools -v
$env:SW_MCP_LIVE_TESTS='1'
$env:SW_MCP_KEEP_REVIEW='1'
.venv\Scripts\python.exe -m unittest solidworks_mcp.tests.live.test_sketch_edit solidworks_mcp.tests.live.test_sketch_entities -v
```

Result: 51 unit tests in the edit module (323 in the full sweep); the live edit
sequence runs in about 107 s and leaves every scratch part unsaved.

## Live test strategy (changed 2026-09-22)

Do **not** create one scratch document per assertion. Both sketch live modules
now build their evidence as an explicit sequence of steps inside **one** scratch
part, via `solidworks_mcp/tests/live/_scratch.py`
(`ScratchPartTestCase`, `live_only`, `zone`):

- one step per tool, in build order, with a stated purpose
- each step owns its own zone of the sketch plane (`zone(column, row)`,
  90 mm pitch) and keeps its geometry inside that zone, so the accumulating
  part never overlaps itself
- several parameter sets of the same entity go into the same step
- every step takes a screenshot before the part is closed; screenshots land in
  `<first output root>/review` and are deleted again unless
  `SW_MCP_KEEP_REVIEW=1`
- trim and extend moved here out of `tests/live/test_documents.py`

Current shape: `test_sketch_entities.py` = 21 entity steps + the equation-driven
curve + sketch text + a plate profile + the extrusion + a sketch on the Right
Plane + converted model face and edge + a 3D sketch (28 screenshots);
`test_sketch_edit.py` = 26 edit, pattern, relation and dimension steps
(26 screenshots). The step that rotates a
profile and extrudes it is the rigorous one: it asserts the 40x20 profile
**swaps its axes** in `GetBodyBox`, which no length-based check can see.

When a step ends in a feature, prove success by **volume**, not by body count:
a single sketch with several closed loops extrudes all of them, but a body count
of 1 looks identical if only the first loop was used. See
`docs/api-findings.md` section 23.6.

The same consolidation should be applied to the part-feature live tests in
`tests/live/test_documents.py` (they still create one part per test) when M2
work next touches them.

Full regression command:

```powershell
.venv\Scripts\python.exe -m unittest discover -s solidworks_mcp\tests -v
```

Result: 320 tests run, 35 skipped, 0 failures before this test-only change;
the consolidation removes two live tests from `test_documents.py` and merges
eleven into two, so expect 318 declarations with a much smaller live runtime.

## Current capability register

Local generated reports (excluded by repository policy; regenerate with):

```powershell
.venv\Scripts\python.exe scripts\audit_capabilities.py --root . --requirements scripts\capability_requirements.json --output-json docs\upgrade\specs\capability-register.json --output-markdown docs\upgrade\specs\CAPABILITY-REGISTER.md
```

Status after M2.2 draft: 108 requirements —
93 registered, 4 internal_only, 9 absent, 1 superseded, 1 blocked
(68 verified live).

## Sketch relations (M1.3, slice 1)

Three tools in `solidworks_mcp/tools/sketch_edit.py` (they reuse the sketch
open/select/verify machinery): `add_sketch_relation`, `get_sketch_relations`
(read-only) and `delete_sketch_relations`. Details in `docs/api-findings.md`
section 27.

- Adding goes through the legacy `IModelDoc2.SketchAddConstraints("<sg name>")`
  with the entities selected; `ISketchRelationManager.AddRelation` throws
  `com_error` in this build and `GetAllowedRelations` returns `None` (B25).
- Verified strings: `sgHORIZONTAL`, `sgVERTICAL`, `sgTANGENT`, `sgPARALLEL`,
  `sgPERPENDICULAR`, `sgCOINCIDENT`, `sgCONCENTRIC`, `sgSYMMETRIC`,
  `sgSAMELENGTH`, `sgFIXED`, `sgCOLINEAR`. Equal length **and** equal radius are
  `sgSAMELENGTH`; `sgEQUAL` does not exist here; `sgCOLINEAR` has a single L.
  Midpoint (`sgMIDPOINT`, `sgATMIDDLE`) is ignored (B26).
- SolidWorks silently ignores a relation the geometry already satisfies, so the
  tool proves success with the **relation list**, never the return value, and
  reports `RELATION_NOT_ADDED` for a redundant request.
- `get_sketch_relations` reports `constrained_status` (swConstrainedStatus_e)
  and `fully_defined`. Measured: `sgFIXED` alone leaves a sketch at
  `under_constrained` (2) even after a rebuild; a driving dimension is what
  reaches 3 (fully). Do not claim "fixed means fully defined".
- `delete_sketch_relations` takes either one relation type or `all: true`;
  `DeleteRelation` and `DeleteAllRelations` both work.

## Equation-driven curve (M1.1, finished)

`draw_equation_curve` lives in `solidworks_mcp/tools/sketch_entities.py` and
wraps `ISketchManager.CreateEquationSpline` (the 2D `y = f(x)` form; the 3D
`CreateEquationSpline2` form is `draw_equation_curve_3d`, see below).

The trap is mixed units, measured live and recorded in `docs/api-findings.md`
section 26:

- `RangeStart` / `RangeEnd` and the expression are evaluated in the **document
  linear unit**, not in metres. Proven by the arc length: `sin(x)` over
  `0..2*pi` reports `7.640390 mm`, which is the analytic 7.6403956 in
  millimetres. A metre interpretation would report 7640 mm.
- `XOffset` / `YOffset` are **metres**, like every other length in the API.
- `RotationAngle` is radians, counter-clockwise about the sketch origin.
- The tool reads the document unit with `IModelDoc2.GetUnits()` (first element
  is `swLengthUnit_e`), converts the range into it and the offsets into metres,
  and returns `UNSUPPORTED_DOCUMENT_UNIT` rather than guessing for a unit it
  does not know.
- Reading a curve back: `ISketchSpline.GetPoints2()` returns two
  `ISketchPoint`s (start and end, in metres) and `GetPointCount()` returns 2;
  `GetStartPoint`/`GetEndPoint` do not exist on a spline even though
  `GetLength` does.

The live step draws `8*sin(x)` and compares the reported length with a
20000-step arc-length integral (0.5 % tolerance), so a unit mistake cannot pass.

## Remaining absent capabilities

| ID | Capability | Tool | Note |
|---|---|---|---|
| 4.8 | Add drawing dimension | `add_drawing_dimension` | programmatic `AddDimension2` returns None in SW 2025 |
| 5.1–5.6 | Simulation block | `create_static_study`, `apply_material`, `apply_fixed_fixture`, `apply_force_load`, `run_analysis`, `get_stress_results` | needs a Simulation licence |
| 6.3 | Bounded traversal / performance | internal | R7 |
| M1.1-k | Perimeter (3-point) circle | — | SW 2025 exposes neither `CreatePerimeterCircle` nor `Create3PointCircle` |

Blocked on the SolidWorks API (see `docs/upgrade/odlocitve-in-backlog.md`
section 2.4):

- `SketchModifyTranslate` (move entities) — five argument shapes tried with and
  without the sketch origin in the selection, both sketch-closing modes and an
  explicit rebuild: the geometry and the sketch frame stay unchanged. The UI
  command works, this member does not (B21).
- `SketchModifyFlip` — changes only the sketch normal; the model geometry is
  identical (measured with `GetBodyBox` for flags 1–3), so it is not exposed.
- `repair_sketch` (no `Repair` member exists for sketches in SW 2025, B22).

`SketchModifyRotate` **does** work and is now exposed as `rotate_entities`;
`SketchModifyScale` works as `scale_entities`. Both change the sketch frame
rather than the segment coordinates — verify with `ISketch.ModelToSketchTransform`,
never with segment lengths alone.

Recommended next items, in the plan's order:

1. M2.2 features (rib, dome, hole wizard, ...; draft is done as `draft_faces`). M2.1 is done except
   thicken, which needs a surface body (FeatureBossThicken selects a surface
   with mark 1), so it moves after M3 `planar_surface`.
2. Rest of M2 part features, in the plan's order. Research each API on
   help.solidworks.com first (the site needs a real browser — use Playwright).

## Known traps (do not relearn)

- `list_planar_faces` reports `ISurface.PlaneParams` normals, which can point
  against the outward face normal (`IFace2.Normal` is correct) — backlog B25.
  Pick faces by area/point, not by normal sign. In the default part template
  here the Front Plane lies in YZ (a Front sketch extrudes along X).

- `InsertNetBlend` (boundary boss/cut) returns `None` even when it succeeds;
  read the new feature with `FeatureByPositionReverse(0)` and check its type
  (`NetBlend` / `NetBlendCut`).

- `draw_center_rectangle` passed two corners until 2026-09-23 (the API takes
  centre + corner) — every such rectangle was twice as large. Its construction
  diagonals also make a revolve axis ambiguous; use `draw_rectangle` in
  revolve profiles.

- `CreateEquationSpline2` (3D equation curve) returns `None` for any
  non-integer range on a decimal-comma Windows locale; integer ranges and
  decimals inside the expressions work. `draw_equation_curve_3d` always sends
  0..1 and remaps `t` in the expressions (`docs/api-findings.md` section 30).

- `IModelDoc2.EditSketch` is void and returns `None` on success.
- `SketchTrim` returns `False` for `swSketchTrimClosest` even when it trims;
  prove success by observed geometry change.
- `SketchMirror()`, `SketchModifyTranslate`, `SketchModifyRotate` and
  `SketchModifyFlip` all return `None` on success; `SketchModifyScale` returns
  `True`. Never judge these calls by their return value.
- A circular sketch pattern's centre is derived by SolidWorks as
  `seed + ArcRadius * (cos ArcAngle, sin ArcAngle)`; `PatternSpacing` is an
  angle in radians, and a positive spacing steps clockwise. Do not guess it —
  see `docs/api-findings.md` section 23.4.
- `ISketchSegment.GetCenterPoint`/`GetStartPoint`/`GetEndPoint` return
  **sketch** coordinates, not model coordinates.
- An extrusion consumes the closed loops of the **selected sketch only**; the
  proof that every loop was used is the volume, not the body count. A plate
  profile plus five holes gives one body either way.
- With `angle_y_deg = 0` a linear sketch pattern folds the second row onto the
  first line instead of stacking perpendicular to it.
- `SketchModifyRotate` and `SketchModifyScale` work but change the **sketch
  coordinate system**, not the segment coordinates: after the call every
  segment getter still reports the old values, through a rebuild and a
  close/reopen. Verify with `ISketch.ModelToSketchTransform.ArrayData` (and, for
  a durable proof, `GetBodyBox` after extruding the rotated profile).
  `SketchModifyTranslate` does nothing at all; `SketchModifyFlip` only flips the
  sketch normal. A "no change" read from segment coordinates is therefore not
  evidence that these calls failed — look at the screen too (this exact trap
  cost a long detour; the user spotted the rotation on screen).
- `ISketchSpline.GetPoints2()` returns two `ISketchPoint`s (curve start and end,
  in metres); `GetStartPoint`/`GetEndPoint` do not exist on a spline even
  though `GetLength` does.
- `CreateEquationSpline` takes the range **and** evaluates the expression in the
  document linear unit, but takes `XOffset`/`YOffset` in **metres**. Mixing
  these up shows as a factor-of-1000 curve, not as an error.
- `IModelDoc2.AddDimension2` opens the dimension-value prompt when the global
  user preference `swInputDimValOnCreate` (10) is true. `EditRebuild3` is **not**
  the fix: it can make `GetRunningCommandInfo` report idle while the user still
  has to confirm. The verified no-dialog recipe is: save the preference, set it
  false, call `AddDimension2`, and restore it in `finally`; then use
  `IDimension.SetSystemValue2(value_m, 0)` and rebuild. Official API Help says
  to use this preference specifically to suppress the input dialog.
- `ISketchRelationManager.AddRelation` throws `com_error` in SW 2025 and
  `GetAllowedRelations` returns `None`; add relations with
  `IModelDoc2.SketchAddConstraints("sg...")` instead.
- The relation strings are `sgSAMELENGTH` (equal length *and* equal radius) and
  `sgCOLINEAR` with one L. `sgEQUAL`, `sgSAMERADIUS`, `sgCOLLINEAR`,
  `sgMIDPOINT` and `sgATMIDDLE` are silently ignored.
- SolidWorks silently ignores a relation the geometry already satisfies; prove
  relations through the relation list, never the return value.
- `sgFIXED` does not make a sketch fully defined: the status stays
  `under_constrained` (2) even after a rebuild. A driving dimension reaches 3.
- A sketch that is created and exited **without geometry is deleted again**.
- A 3D sketch is a `3DProfileFeature`, not a `ProfileFeature`, so any helper
  that looks for `ProfileFeature` misses it. `ISketch.Is3D` is the check.
- `Insert3DSketch2(True)` and `InsertSketch2(True)` both return `None`; verify
  through `GetActiveSketch2()` and `Is3D()`, never through the return value.
- Convert Entities (`SketchUseEdge2(Chain)`) **silently rejects** a selection it
  cannot convert: it returns `True`, converts nothing and clears the selection.
  One face (its loop) or a few coherent edges convert fine; all 12 edges of a
  body at once convert nothing. Prove it by the sketch segment count growing.
- Points exactly on a body **corner** are ambiguous for `SelectByID2`; use the
  middle of a face or of an edge.
  Read the sketch name right after `create_sketch`, never after exiting it.
- Setting a COM property needs a plain attribute assignment (`comutil.set_com`);
  `com(obj, "Member", value)` dispatches a property *get* with an argument and
  is silently ignored, which is how the construction flag refused to clear.
- `IMathUtility.CreatePoint` + `IMathPoint.MultiplyTransform` is broken in this
  build (returns the translation alone).
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
7d5c181 feat: draw equation-driven curves and pin down their mixed units
c05aadd feat: rotate sketch entities and verify sketch-frame edits
3f8787e feat: scale, construction toggle and closed-entity split for sketches
d1819f4 test: run the sketch live tests as one sliced sequence per part
29d9b8e feat: add seven verified sketch editing tools
ed41f5f docs: record the tangent arc and arc slot slice in the handoff
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
```

Expected branch is `additional-upgrades`. Confirm that only the user-owned files
listed above are dirty before beginning another roadmap item.

Test economy: run only the focused module(s) for the slice being changed
(`python -m unittest solidworks_mcp.tests.<module> -v`) while iterating. Run the
whole `discover` sweep once before committing, and do not enable
`SW_MCP_LIVE_TESTS` for a broad sweep unless it is needed — some pre-existing
live tests save documents and prompt the user. The two consolidated sketch
modules are the safe live pair:

```powershell
$env:SW_MCP_LIVE_TESTS='1'
$env:SW_MCP_KEEP_REVIEW='1'   # optional: keep the per-step screenshots
.venv\Scripts\python.exe -m unittest solidworks_mcp.tests.live.test_sketch_entities solidworks_mcp.tests.live.test_sketch_edit -v
```

Screenshots are written to `C:\Users\Jan\Documents\SolidWorks MCP Output\review`
and are meant to be looked at before the scratch part is discarded.
