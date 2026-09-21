# SolidWorks MCP development handoff

Updated: 2026-09-21

## Resume point

- Repository: `C:\Users\Jan\Documents\Claude-Solidworks mcp`
- Branch: `additional-upgrades`
- Latest implementation commit: `5343a3730a5059de1d4f2a012d9487a78b98d63c` (`feat: add verified shell feature`)
- Work continued from the user-specified commit `2a6d5aca7562d6403239fcbf35dd96dae282ba10`.
- Do not push to a remote unless the user explicitly asks.
- The user asked to stop after completing `shell_feature`; no later roadmap item has been started.

## User intent and operating rules

The priority is broad SolidWorks functionality coverage before heavy planning or reasoning logic. Keep the MCP lightweight and expose small explicit tools. Develop each tool with unit tests and an opt-in live COM test where safe.

- Never save scratch native SolidWorks models used for testing.
- Do not modify or save the user's manually opened SolidWorks examples.
- Scratch tests may create a new document and must close it without saving.
- SolidWorks may need to remain at least partly visible and not minimized for viewport capture.
- COM testing is available. Native Computer Use inventory was empty in this session, so do not claim direct UI control.
- Preserve the existing explicit DXF tools. The user explicitly rejected a generic DXF router as unnecessary complexity:
  - `export_face_to_dxf` for a selected planar face
  - `export_flat_pattern` for sheet metal
- Use `comutil.com()` for SolidWorks members because SW COM inconsistently exposes properties and methods.
- Use TDD: add a failing focused test, implement the minimum behavior, run the focused test, run a scratch COM test where applicable, then run the whole suite.

## Files owned by the user: do not stage or overwrite

At handoff these pre-existing changes remain intentionally untouched:

```text
 M DEVELOPMENT_ROADMAP.md
 M solidworks_mcp/config.json
?? UGOTOVITVE_TEST.md
?? scripts/build_gear.py
```

Always use explicit `git add -- <files>` rather than `git add .`.

## Latest completed function: shell_feature

Implementation:

- `solidworks_mcp/tools/advanced_features.py`
- registration import in `solidworks_mcp/tools/__init__.py`
- unit tests in `solidworks_mcp/tests/test_advanced_features.py`
- live test in `solidworks_mcp/tests/live/test_documents.py`
- live evidence in `scripts/capability_requirements.json`

Contract:

- positive finite `thickness` with explicit unit conversion
- optional distinct non-negative `remove_face_indices` from the current `list_planar_faces` result
- optional `outward` direction
- removable faces selected with SolidWorks selection mark 1
- uses the documented `IModelDoc2.InsertFeatureShell(thickness_m, outward)` API
- because the API returns void, success is reported only when a new top-level feature whose type contains `Shell` appears
- selections are cleared before and after the operation

Verification performed:

```powershell
$env:SW_MCP_LIVE_TESTS='1'
.venv\Scripts\python.exe -m unittest solidworks_mcp.tests.live.test_documents.LiveDocumentTargetTests.test_shell_scratch_extrusion_removes_one_planar_face_without_saving -v
```

Result: 1 passed. SW 2025 created a 2 mm Shell on a scratch 40 x 20 x 20 mm extrusion after removing one planar face. The native part remained unsaved and teardown closed it.

Full regression command:

```powershell
.venv\Scripts\python.exe -m unittest discover -s solidworks_mcp\tests -v
```

Result: 163 tests run, 12 skipped, 0 failures. The skips are opt-in live COM tests plus the Windows symlink-privilege test.

## Current capability register

The local generated reports are:

- `docs/upgrade/specs/capability-register.json`
- `docs/upgrade/specs/CAPABILITY-REGISTER.md`

They are excluded locally by repository policy; regenerate with:

```powershell
.venv\Scripts\python.exe scripts\audit_capabilities.py --root . --requirements scripts\capability_requirements.json --output-json docs\upgrade\specs\capability-register.json --output-markdown docs\upgrade\specs\CAPABILITY-REGISTER.md
```

Status after `shell_feature`:

- registered: 46
- internal_only: 4
- absent: 13
- superseded: 1
- blocked: 1

The ignored execution ledger is `.superpowers/sdd/H-plan-nadaljnji-razvoj/progress.md` and contains the detailed R0-R8 evidence/rulings through the shell feature.

## Remaining absent roadmap capabilities

No work has started on these after the handoff request:

| ID | Capability | Tool | Phase |
|---|---|---|---|
| 3.1 | Sweep profile along path | `sweep_sketch` | R6-F |
| 3.2 | Loft ordered profiles | `loft_sketches` | R6-F |
| 3.5 | Mirror feature | `mirror_feature` | R6-F |
| 4.8 | Add drawing dimension | `add_drawing_dimension` | R5 |
| 5.1 | Create static study | `create_static_study` | R8 |
| 5.2 | Apply material | `apply_material` | R8 |
| 5.3 | Apply fixed fixture | `apply_fixed_fixture` | R8 |
| 5.4 | Apply force load | `apply_force_load` | R8 |
| 5.5 | Run analysis | `run_analysis` | R8 |
| 5.6 | Read stress results | `get_stress_results` | R8 |
| 6.3 | Bounded traversal/performance work | internal | R7 |
| 2.summary.trim | Trim referenced sketch entities | `trim_entities` | R6-S |
| D1 | Workshop balloons and marked dimensions | `insert_marked_dimensions` | R5 |

Recommended next small coverage item is `mirror_feature`, but confirm current SolidWorks selection/API behavior and follow TDD before implementation. Do not revive generic DXF work.

## Recent local commits

```text
5343a37 feat: add verified shell feature
7009a53 feat: create offset reference planes
1f112de chore: keep explicit dxf export workflows
72d00e1 feat: add guarded undo and redo tools
cf10870 feat: export verified STEP and STL artifacts
4b6164d feat: capture revision-bound model views
d821e17 feat: inspect assembly mate health
c04711b feat: inspect document dependencies
2c3271c feat: inspect feature trees and parameters
4c662d5 feat: add pageable project inspection snapshots
```

## First checks for the next model

```powershell
git branch --show-current
git status --short
git log -5 --oneline
.venv\Scripts\python.exe -m unittest discover -s solidworks_mcp\tests -v
```

Expected branch is `additional-upgrades`. Confirm that only the four protected user files above are dirty before beginning another roadmap item.
