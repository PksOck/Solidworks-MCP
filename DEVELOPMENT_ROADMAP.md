# 🚀 SolidWorks MCP Development Roadmap
## Building the Most Robust SolidWorks MCP Server

- **Project:** SolidWorks MCP Server
- **Original author:** Samsaam Ali Baig
- **Additional development and 2026 progress updates:** PksOck
- **Start Date:** January 2026
- **Target:** Production-Ready v3.0

The original roadmap and its code examples are Samsaam Ali Baig's work.
PksOck is developing the additional tools and tests on `additional-upgrades`.
The updates recorded here describe work in that branch; they are not yet part
of the original author's project. The changes will be cleaned up into one PR
for the original author's review.

---

# 📋 TABLE OF CONTENTS

1. [Project Vision](#1-project-vision)
2. [Current State Analysis](#2-current-state-analysis)
3. [Development Phases](#3-development-phases)
4. [Phase 1: Foundation Improvements](#4-phase-1-foundation-improvements)
5. [Phase 2: Core Feature Expansion](#5-phase-2-core-feature-expansion)
6. [Phase 3: Advanced Features](#6-phase-3-advanced-features)
7. [Phase 4: Assembly & Drawing Support](#7-phase-4-assembly--drawing-support)
8. [Phase 5: Simulation & Analysis](#8-phase-5-simulation--analysis)
9. [Phase 6: Production Hardening](#9-phase-6-production-hardening)
10. [Testing Strategy](#10-testing-strategy)
11. [Documentation Plan](#11-documentation-plan)
12. [Progress Tracking](#12-progress-tracking)

---

# 1. PROJECT VISION

## 1.1 Mission Statement
Create the most comprehensive, reliable, and user-friendly MCP server for SolidWorks automation that enables AI assistants to perform complex CAD operations through natural language commands.

## 1.2 Success Criteria
- [x] 50+ automation tools (145 in the live MCP catalog on 2026-09-24;
  unfinished operation families remain in the Parts coverage plan)
- [ ] 99% connection reliability
- [x] Support for Parts, Assemblies, and Drawings (see §12.1 for remaining gaps)
- [ ] Simulation integration
- [ ] Unit-agnostic input (mm, inch, meter)
- [ ] Comprehensive error recovery
- [ ] Full documentation and examples

## 1.3 Target Users
- Engineers using AI assistants for CAD automation
- Educators teaching CAD through conversational interfaces
- Rapid prototyping teams
- Design automation pipelines

---

# 2. CURRENT STATE ANALYSIS

## 2.1 Version 2.3 Inventory

> **Historical baseline (as of January 2026).** This section describes the
> original v2.3 server and is kept as the starting point for the roadmap — it is
> not the current state. For the live, generated capability state as of
> 24 September 2026 see §12 (Progress Tracking) and
> `docs/upgrade/specs/CAPABILITY-REGISTER.md`. The code examples throughout
> §4–§11 are the original design drafts and are not rewritten here.

### Current Tools (11)
| # | Tool | Category | Status |
|---|------|----------|--------|
| 1 | connect_solidworks | Connection | ✅ Working |
| 2 | create_new_part | Document | ✅ Working |
| 3 | create_sketch | Sketch | ✅ Working |
| 4 | draw_circle | 2D Geometry | ✅ Working |
| 5 | draw_rectangle | 2D Geometry | ✅ Working |
| 6 | draw_line | 2D Geometry | ✅ Working |
| 7 | extrude_sketch | 3D Feature | ✅ Working |
| 8 | save_document | File I/O | ✅ Working |
| 9 | close_document | Document | ✅ Working |
| 10 | execute_python | Advanced | ✅ Working |
| 11 | get_document_info | Information | ✅ Working |

### Current Capabilities
```
✅ Connect to SolidWorks (with auto-launch)
✅ Create part documents
✅ Basic 2D sketching (circle, rectangle, line)
✅ Boss extrusion
✅ Save/Close documents
✅ Custom Python execution
✅ Error handling with codes
✅ Logging system
```

### Current Limitations
```
❌ No assembly support
❌ No drawing support
❌ No cut operations
❌ No fillets/chamfers
❌ No revolve/sweep/loft
❌ No patterns
❌ No sketch constraints
❌ No measurements
❌ No export formats (STEP, STL, etc.)
❌ No simulation
❌ Hardcoded units (meters only)
❌ Hardcoded SolidWorks path
```

## 2.2 Code Metrics
- Total Lines: ~623
- Classes: 3 (SwErrors, SwPlanes, SolidWorksAutomation)
- Methods: 16
- Tools: 11
- Test Coverage: 0%

---

# 3. DEVELOPMENT PHASES

## 3.1 Phase Overview

The week-by-week diagram below is the original January 2026 schedule;
current progress and priorities are in §12.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT TIMELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PHASE 1: Foundation     ████████░░░░░░░░░░░░  Week 1-2         │
│  PHASE 2: Core Features  ░░░░░░░░████████░░░░  Week 3-4         │
│  PHASE 3: Advanced       ░░░░░░░░░░░░░░░█████  Week 5-6         │
│  PHASE 4: Assembly/Draw  ░░░░░░░░░░░░░░░░░░██  Week 7-8         │
│  PHASE 5: Simulation     ░░░░░░░░░░░░░░░░░░░█  Week 9-10        │
│  PHASE 6: Production     ░░░░░░░░░░░░░░░░░░░░  Week 11-12       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 3.2 Tool Count Targets

| Phase | New Tools | Total Tools | Coverage |
|-------|-----------|-------------|----------|
| Current | - | 11 | Basic |
| Phase 1 | +5 | 16 | Foundation |
| Phase 2 | +12 | 28 | Core |
| Phase 3 | +10 | 38 | Advanced |
| Phase 4 | +8 | 46 | Full CAD |
| Phase 5 | +6 | 52 | Simulation |
| Phase 6 | +3 | 55 | Production |

> These are the original January 2026 targets, not the current tool inventory.
> Before the next M2/M3 additions on 24 September 2026, the live MCP catalog
> contained 144 tools. See §12 for the verified capability register and
> `docs/upgrade/PARTS-COVERAGE-PLAN.md` for unfinished M2/M3 commands.

---

# 4. PHASE 1: FOUNDATION IMPROVEMENTS
## Week 1-2 | Priority: CRITICAL

### 4.1 Goals
- [ ] Modular code architecture
- [ ] Configuration system
- [ ] Unit conversion system
- [ ] Auto-detect SolidWorks installation
- [ ] Improved connection reliability

### 4.2 Tasks

#### Task 1.1: Create Project Structure
```
solidworks_mcp/
├── __init__.py
├── server.py                 # MCP entry point
├── config.py                 # Configuration management
├── constants.py              # All constants
├── automation/
│   ├── __init__.py
│   ├── base.py              # Base automation class
│   ├── connection.py        # Connection management
│   ├── documents.py         # Document operations
│   ├── sketches.py          # Sketch operations
│   ├── features.py          # Feature operations
│   └── geometry.py          # Geometry helpers
├── utils/
│   ├── __init__.py
│   ├── units.py             # Unit conversion
│   ├── validation.py        # Input validation
│   └── sw_finder.py         # SolidWorks detection
├── tools/
│   ├── __init__.py
│   ├── connection_tools.py
│   ├── document_tools.py
│   ├── sketch_tools.py
│   └── feature_tools.py
└── tests/
    ├── __init__.py
    ├── test_connection.py
    ├── test_sketches.py
    └── test_features.py
```
**Status:** [ ] Not Started
**Estimated Time:** 4 hours

---

#### Task 1.2: Configuration System
**File:** `config.py`
```python
"""
Configuration management for SolidWorks MCP
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class SolidWorksConfig:
    """SolidWorks MCP Configuration"""
    
    # SolidWorks settings
    exe_path: str = "auto"  # "auto" or explicit path
    startup_timeout: int = 120  # seconds
    connection_retry_interval: int = 5  # seconds
    
    # Default units
    default_unit: str = "mm"  # mm, inch, meter
    
    # Templates
    part_template: str = "auto"
    assembly_template: str = "auto"
    drawing_template: str = "auto"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "solidworks_mcp.log"
    
    # Feature defaults
    default_extrude_depth: float = 10.0  # in default_unit
    default_fillet_radius: float = 2.0   # in default_unit
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'SolidWorksConfig':
        """Load configuration from file"""
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        
        if Path(config_path).exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
            return cls(**data)
        return cls()
    
    def save(self, config_path: Optional[str] = None):
        """Save configuration to file"""
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        
        with open(config_path, 'w') as f:
            json.dump(self.__dict__, f, indent=2)

# Global config instance
config = SolidWorksConfig.load()
```
**Status:** [ ] Not Started
**Estimated Time:** 2 hours

---

#### Task 1.3: Unit Conversion System
**File:** `utils/units.py`
```python
"""
Unit conversion utilities for SolidWorks MCP
SolidWorks API uses meters internally
"""
from enum import Enum
from typing import Union

class Unit(Enum):
    METER = "m"
    MILLIMETER = "mm"
    CENTIMETER = "cm"
    INCH = "inch"
    FOOT = "ft"

# Conversion factors TO meters
TO_METERS = {
    Unit.METER: 1.0,
    Unit.MILLIMETER: 0.001,
    Unit.CENTIMETER: 0.01,
    Unit.INCH: 0.0254,
    Unit.FOOT: 0.3048,
}

# Conversion factors FROM meters
FROM_METERS = {unit: 1.0 / factor for unit, factor in TO_METERS.items()}

class UnitConverter:
    """Handle unit conversions for SolidWorks API"""
    
    def __init__(self, default_unit: str = "mm"):
        self.default_unit = self._parse_unit(default_unit)
    
    def _parse_unit(self, unit: str) -> Unit:
        """Parse unit string to Unit enum"""
        unit_map = {
            "m": Unit.METER, "meter": Unit.METER, "meters": Unit.METER,
            "mm": Unit.MILLIMETER, "millimeter": Unit.MILLIMETER,
            "cm": Unit.CENTIMETER, "centimeter": Unit.CENTIMETER,
            "inch": Unit.INCH, "in": Unit.INCH, "inches": Unit.INCH,
            "ft": Unit.FOOT, "foot": Unit.FOOT, "feet": Unit.FOOT,
        }
        return unit_map.get(unit.lower(), Unit.MILLIMETER)
    
    def to_meters(self, value: float, unit: str = None) -> float:
        """Convert value to meters for SolidWorks API"""
        if unit is None:
            unit = self.default_unit
        else:
            unit = self._parse_unit(unit)
        return value * TO_METERS[unit]
    
    def from_meters(self, value: float, unit: str = None) -> float:
        """Convert value from meters to display unit"""
        if unit is None:
            unit = self.default_unit
        else:
            unit = self._parse_unit(unit)
        return value * FROM_METERS[unit]
    
    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert between any two units"""
        meters = self.to_meters(value, from_unit)
        return self.from_meters(meters, to_unit)

# Global converter instance
converter = UnitConverter()

# Convenience functions
def mm(value: float) -> float:
    """Convert mm to meters"""
    return value * 0.001

def inch(value: float) -> float:
    """Convert inches to meters"""
    return value * 0.0254

def cm(value: float) -> float:
    """Convert cm to meters"""
    return value * 0.01
```
**Status:** [ ] Not Started
**Estimated Time:** 2 hours

---

#### Task 1.4: SolidWorks Auto-Detection
**File:** `utils/sw_finder.py`
```python
"""
Auto-detect SolidWorks installation
"""
import os
import winreg
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class SolidWorksFinder:
    """Find SolidWorks installation on the system"""
    
    REGISTRY_PATHS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks\SOLIDWORKS"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\SolidWorks\SOLIDWORKS"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\SolidWorks\SOLIDWORKS"),
    ]
    
    COMMON_PATHS = [
        r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe",
        r"C:\Program Files\SolidWorks Corp\SolidWorks\SLDWORKS.exe",
        r"D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe",
        r"D:\SolidWorks\SLDWORKS.exe",
    ]
    
    @classmethod
    def find(cls) -> Optional[str]:
        """Find SolidWorks executable"""
        # Try registry first
        path = cls._find_from_registry()
        if path:
            return path
        
        # Try common paths
        path = cls._find_from_common_paths()
        if path:
            return path
        
        # Search Program Files
        path = cls._search_program_files()
        if path:
            return path
        
        logger.error("SolidWorks installation not found")
        return None
    
    @classmethod
    def _find_from_registry(cls) -> Optional[str]:
        """Search Windows registry for SolidWorks"""
        for hkey, reg_path in cls.REGISTRY_PATHS:
            try:
                with winreg.OpenKey(hkey, reg_path) as key:
                    versions = cls._get_subkeys(key)
                    versions.sort(reverse=True)  # Latest first
                    
                    for version in versions:
                        try:
                            with winreg.OpenKey(key, version) as ver_key:
                                sw_path, _ = winreg.QueryValueEx(ver_key, "SolidWorks Exe")
                                if os.path.exists(sw_path):
                                    logger.info(f"Found SolidWorks {version} at: {sw_path}")
                                    return sw_path
                        except WindowsError:
                            continue
            except WindowsError:
                continue
        return None
    
    @classmethod
    def _get_subkeys(cls, key) -> List[str]:
        """Get all subkeys of a registry key"""
        subkeys = []
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
                i += 1
            except WindowsError:
                break
        return subkeys
    
    @classmethod
    def _find_from_common_paths(cls) -> Optional[str]:
        """Check common installation paths"""
        # Add versioned paths
        all_paths = list(cls.COMMON_PATHS)
        for year in range(2030, 2015, -1):
            all_paths.extend([
                rf"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS {year}\SLDWORKS.exe",
                rf"D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS {year}\SLDWORKS.exe",
            ])
        
        for path in all_paths:
            if os.path.exists(path):
                logger.info(f"Found SolidWorks at: {path}")
                return path
        return None
    
    @classmethod
    def _search_program_files(cls) -> Optional[str]:
        """Search Program Files directories"""
        search_roots = [
            r"C:\Program Files",
            r"D:\Program Files",
            r"C:\Program Files (x86)",
        ]
        
        for root in search_roots:
            if not os.path.exists(root):
                continue
            
            for folder in os.listdir(root):
                if "solidworks" in folder.lower():
                    sw_folder = os.path.join(root, folder)
                    for dirpath, _, files in os.walk(sw_folder):
                        if "SLDWORKS.exe" in files:
                            path = os.path.join(dirpath, "SLDWORKS.exe")
                            logger.info(f"Found SolidWorks at: {path}")
                            return path
        return None
    
    @classmethod
    def get_version(cls, exe_path: str) -> Optional[str]:
        """Get SolidWorks version from executable"""
        try:
            import win32api
            info = win32api.GetFileVersionInfo(exe_path, "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
        except:
            return None
```
**Status:** [ ] Not Started
**Estimated Time:** 2 hours

---

#### Task 1.5: New Tools for Phase 1

| Tool | Description | Priority |
|------|-------------|----------|
| `get_solidworks_info` | Get SW version, path, status | HIGH |
| `set_units` | Change default units | HIGH |
| `open_document` | Open existing file | HIGH |
| `list_features` | List all features in model | MEDIUM |
| `list_planes` | List all planes | MEDIUM |

**Status:** [ ] Not Started
**Estimated Time:** 4 hours

---

### 4.3 Phase 1 Deliverables
- [ ] Modular project structure
- [ ] Configuration file support
- [ ] Unit conversion (mm, inch, meter)
- [ ] Auto-detect SolidWorks
- [ ] 5 new tools (16 total)
- [ ] Unit tests for core functions

---


# 5. PHASE 2: CORE FEATURE EXPANSION
## Week 3-4 | Priority: HIGH

### 5.1 Goals
- [ ] Complete 2D sketch tools
- [ ] Add cut operations
- [ ] Add fillet/chamfer
- [ ] Add revolve feature
- [ ] Add sketch constraints
- [ ] Add measurement tools

### 5.2 New Sketch Tools

#### Task 2.1: Arc Drawing Tools
```python
def draw_arc_center(self, cx, cy, radius, start_angle, end_angle, unit="mm") -> Dict:
    """
    Draw arc by center point and angles
    
    Args:
        cx, cy: Center point
        radius: Arc radius
        start_angle: Start angle in degrees
        end_angle: End angle in degrees
        unit: Unit for dimensions
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    radius_m = self.units.to_meters(radius, unit)
    cx_m = self.units.to_meters(cx, unit)
    cy_m = self.units.to_meters(cy, unit)
    
    import math
    start_rad = math.radians(start_angle)
    end_rad = math.radians(end_angle)
    
    # Calculate start and end points
    x1 = cx_m + radius_m * math.cos(start_rad)
    y1 = cy_m + radius_m * math.sin(start_rad)
    x2 = cx_m + radius_m * math.cos(end_rad)
    y2 = cy_m + radius_m * math.sin(end_rad)
    
    arc = doc.SketchManager.CreateArc(cx_m, cy_m, 0, x1, y1, 0, x2, y2, 0, 1)
    
    if arc is None:
        return self._result(False, "Failed to create arc", SwErrors.swSketchError)
    
    return self._result(True, f"Arc created: r={radius}{unit}", SwErrors.swSuccess)

def draw_arc_3point(self, x1, y1, x2, y2, x3, y3, unit="mm") -> Dict:
    """
    Draw arc through 3 points
    
    Args:
        x1, y1: Start point
        x2, y2: Mid point (on arc)
        x3, y3: End point
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Convert units
    points = [(x1, y1), (x2, y2), (x3, y3)]
    points_m = [(self.units.to_meters(x, unit), self.units.to_meters(y, unit)) 
                for x, y in points]
    
    arc = doc.SketchManager.Create3PointArc(
        points_m[0][0], points_m[0][1], 0,
        points_m[2][0], points_m[2][1], 0,
        points_m[1][0], points_m[1][1], 0
    )
    
    return self._result(True, "3-point arc created", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 2.2: Spline Tool
```python
def draw_spline(self, points: list, unit="mm") -> Dict:
    """
    Draw spline through points
    
    Args:
        points: List of (x, y) tuples
        unit: Unit for coordinates
    
    Example:
        draw_spline([(0, 0), (10, 5), (20, 0), (30, -5)], unit="mm")
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if len(points) < 2:
        return self._result(False, "Spline needs at least 2 points", SwErrors.swSketchError)
    
    # Convert to meters and create point array
    import array
    point_array = array.array('d')
    
    for x, y in points:
        point_array.append(self.units.to_meters(x, unit))
        point_array.append(self.units.to_meters(y, unit))
        point_array.append(0)  # Z coordinate
    
    spline = doc.SketchManager.CreateSpline2(point_array, True)
    
    if spline is None:
        return self._result(False, "Failed to create spline", SwErrors.swSketchError)
    
    return self._result(True, f"Spline with {len(points)} points created", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 2.3: Polygon Tool
```python
def draw_polygon(self, cx, cy, radius, sides=6, unit="mm") -> Dict:
    """
    Draw regular polygon
    
    Args:
        cx, cy: Center point
        radius: Circumscribed radius
        sides: Number of sides (3-100)
        unit: Unit for dimensions
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if sides < 3 or sides > 100:
        return self._result(False, "Sides must be 3-100", SwErrors.swSketchError)
    
    cx_m = self.units.to_meters(cx, unit)
    cy_m = self.units.to_meters(cy, unit)
    radius_m = self.units.to_meters(radius, unit)
    
    # CreatePolygon: Cx, Cy, Cz, Vx, Vy, Vz, NumSides, Inscribed
    polygon = doc.SketchManager.CreatePolygon(
        cx_m, cy_m, 0,           # Center
        cx_m + radius_m, cy_m, 0, # Vertex
        sides,                    # Number of sides
        False                     # Inscribed (False = circumscribed)
    )
    
    return self._result(True, f"{sides}-sided polygon created", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 2.4: Slot Tool
```python
def draw_slot(self, x1, y1, x2, y2, width, unit="mm") -> Dict:
    """
    Draw straight slot
    
    Args:
        x1, y1: Start center point
        x2, y2: End center point
        width: Slot width (diameter of end caps)
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    x1_m = self.units.to_meters(x1, unit)
    y1_m = self.units.to_meters(y1, unit)
    x2_m = self.units.to_meters(x2, unit)
    y2_m = self.units.to_meters(y2, unit)
    width_m = self.units.to_meters(width, unit)
    
    # CreateSketchSlot: Type, X1, Y1, Z1, X2, Y2, Z2, Width, CenterArc, AddDimension, Value
    slot = doc.SketchManager.CreateSketchSlot(
        0,  # swSketchSlotLongCenter
        x1_m, y1_m, 0,
        x2_m, y2_m, 0,
        width_m,
        0,     # Center arc type
        False  # Add dimension
    )
    
    return self._result(True, f"Slot created: width={width}{unit}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 5.3 Cut & Feature Tools

#### Task 2.5: Cut Extrude
```python
def cut_extrude(self, depth, through_all=False, both_directions=False, unit="mm") -> Dict:
    """
    Cut extrude (remove material)
    
    Args:
        depth: Cut depth (ignored if through_all=True)
        through_all: Cut through entire model
        both_directions: Cut in both directions
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Exit sketch
    doc.InsertSketch2(True)
    
    depth_m = self.units.to_meters(depth, unit)
    
    if through_all:
        if both_directions:
            end_cond = 2  # swEndCondThroughAllBoth
        else:
            end_cond = 1  # swEndCondThroughAll
        depth_m = 0
    else:
        end_cond = 6 if both_directions else 0  # MidPlane or Blind
    
    # FeatureCut4 for cut operations
    feat = doc.FeatureManager.FeatureCut4(
        True,           # Sd
        False,          # Flip
        False,          # Dir
        end_cond,       # T1
        0,              # T2
        depth_m,        # D1
        depth_m,        # D2
        False, False,   # Dchk1, Dchk2
        False, False,   # Ddir1, Ddir2
        0.0, 0.0,       # Draft angles
        False, False,   # OffsetReverse
        False, False,   # TranslateSurface, NormalCut
        False,          # FlipSide
        True, True,     # AssemblyFeatureScope, AutoSelect
        True,           # FeatureScope
        0,              # T0
        0.0, False      # StartOffset, FlipStartOffset
    )
    
    if feat is None:
        return self._result(False, "Cut failed", SwErrors.swFeatureError)
    
    cut_type = "through all" if through_all else f"{depth}{unit} deep"
    return self._result(True, f"Cut extrude: {cut_type}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 2.6: Fillet Tool
```python
def fillet_edges(self, radius, edge_indices=None, all_edges=False, unit="mm") -> Dict:
    """
    Add fillet to edges
    
    Args:
        radius: Fillet radius
        edge_indices: List of edge indices to fillet (optional)
        all_edges: Fillet all edges
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    radius_m = self.units.to_meters(radius, unit)
    
    if all_edges:
        # Select all edges
        doc.Extension.SelectAll()
    elif edge_indices:
        # Select specific edges
        doc.ClearSelection2(True)
        for idx in edge_indices:
            doc.Extension.SelectByID2(f"Edge<{idx}>", "EDGE", 0, 0, 0, True, 0, None, 0)
    
    # Simple constant radius fillet
    feat = doc.FeatureManager.FeatureFillet3(
        195,        # Options: swFeatureFilletKeepFeatures | swFeatureFilletPropagate
        radius_m,   # Radius
        0,          # Fillet type (0 = symmetric)
        0,          # Overflow type
        0, 0,       # Radius type, Profile type
        0, 0, 0,    # Additional parameters
        0, 0, 0,
        0, 0, 0
    )
    
    if feat is None:
        return self._result(False, "Fillet failed - select edges first", SwErrors.swFeatureError)
    
    return self._result(True, f"Fillet r={radius}{unit}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 2.7: Chamfer Tool
```python
def chamfer_edges(self, distance, angle=45, edge_indices=None, unit="mm") -> Dict:
    """
    Add chamfer to edges
    
    Args:
        distance: Chamfer distance
        angle: Chamfer angle (default 45°)
        edge_indices: List of edge indices
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    import math
    dist_m = self.units.to_meters(distance, unit)
    angle_rad = math.radians(angle)
    
    if edge_indices:
        doc.ClearSelection2(True)
        for idx in edge_indices:
            doc.Extension.SelectByID2(f"Edge<{idx}>", "EDGE", 0, 0, 0, True, 0, None, 0)
    
    # FeatureChamfer: Type, Width, Angle, OtherDist, FlipFlag, Tangent, FaceEdge
    feat = doc.FeatureManager.FeatureChamfer(
        1,          # Type (1 = Distance-Angle)
        dist_m,     # Distance
        angle_rad,  # Angle
        dist_m,     # Other distance
        0,          # Flip flag
        False,      # Tangent propagation
        False       # Face-edge chamfer
    )
    
    if feat is None:
        return self._result(False, "Chamfer failed", SwErrors.swFeatureError)
    
    return self._result(True, f"Chamfer {distance}{unit} x {angle}°", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 2.8: Revolve Feature
```python
def revolve_sketch(self, angle=360, axis="centerline", unit="deg") -> Dict:
    """
    Revolve sketch around axis
    
    Args:
        angle: Revolution angle (default 360 for full)
        axis: "centerline", "x", "y", or axis name
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    import math
    angle_rad = math.radians(angle)
    
    # Exit sketch
    doc.InsertSketch2(True)
    
    # Select axis if specified
    if axis.lower() == "x":
        doc.Extension.SelectByID2("", "AXIS", 1, 0, 0, False, 0, None, 0)
    elif axis.lower() == "y":
        doc.Extension.SelectByID2("", "AXIS", 0, 1, 0, False, 0, None, 0)
    
    # FeatureRevolve2: Sd, Flip, Dir, T1, T2, D1, D2, Dchk1, Dchk2, MergeResult, UseFeatScope
    feat = doc.FeatureManager.FeatureRevolve2(
        True,       # Sd (single direction)
        False,      # Flip
        False,      # Dir
        0,          # T1 (Blind)
        0,          # T2
        angle_rad,  # D1 (angle)
        0,          # D2
        False,      # Dchk1
        False,      # Dchk2
        True,       # MergeResult
        True,       # UseFeatScope
        True        # UseAutoSelect
    )
    
    if feat is None:
        return self._result(False, "Revolve failed - need axis", SwErrors.swFeatureError)
    
    return self._result(True, f"Revolved {angle}°", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 5.4 Measurement Tools

#### Task 2.9: Measure Distance
```python
def measure_distance(self, entity1_type, entity1_name, entity2_type, entity2_name) -> Dict:
    """
    Measure distance between two entities
    
    Args:
        entity1_type: "FACE", "EDGE", "VERTEX", "PLANE"
        entity1_name: Entity name or index
        entity2_type: Second entity type
        entity2_name: Second entity name
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    measure = doc.Extension.CreateMeasure()
    
    # Select first entity
    doc.Extension.SelectByID2(str(entity1_name), entity1_type, 0, 0, 0, False, 0, None, 0)
    
    # Select second entity
    doc.Extension.SelectByID2(str(entity2_name), entity2_type, 0, 0, 0, True, 0, None, 0)
    
    # Calculate
    status = measure.Calculate(None)
    
    if status:
        distance_m = measure.Distance
        distance_mm = distance_m * 1000
        
        return self._result(True, f"Distance: {distance_mm:.3f}mm", SwErrors.swSuccess,
                          {"distance_m": distance_m, "distance_mm": distance_mm})
    
    return self._result(False, "Measurement failed", SwErrors.swUnknownError)

def get_mass_properties(self, unit="mm") -> Dict:
    """
    Get mass properties of the model
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    props = doc.Extension.CreateMassProperty()
    
    if props is None:
        return self._result(False, "Failed to get mass properties", SwErrors.swUnknownError)
    
    # Get values
    volume = props.Volume  # m³
    surface_area = props.SurfaceArea  # m²
    mass = props.Mass  # kg
    cog = props.CenterOfMass  # (x, y, z) in meters
    
    # Convert based on unit
    if unit == "mm":
        volume_display = volume * 1e9  # mm³
        area_display = surface_area * 1e6  # mm²
        volume_unit = "mm³"
        area_unit = "mm²"
    else:
        volume_display = volume
        area_display = surface_area
        volume_unit = "m³"
        area_unit = "m²"
    
    return self._result(True, f"Volume: {volume_display:.2f}{volume_unit}", SwErrors.swSuccess, {
        "volume": volume_display,
        "volume_unit": volume_unit,
        "surface_area": area_display,
        "surface_area_unit": area_unit,
        "mass_kg": mass,
        "center_of_mass": list(cog)
    })
```
**Status:** [ ] Not Started

---

### 5.5 Phase 2 Tool Summary

| # | Tool | Category | Priority |
|---|------|----------|----------|
| 1 | draw_arc_center | 2D Sketch | HIGH |
| 2 | draw_arc_3point | 2D Sketch | MEDIUM |
| 3 | draw_spline | 2D Sketch | MEDIUM |
| 4 | draw_polygon | 2D Sketch | HIGH |
| 5 | draw_slot | 2D Sketch | MEDIUM |
| 6 | cut_extrude | 3D Feature | HIGH |
| 7 | fillet_edges | 3D Feature | HIGH |
| 8 | chamfer_edges | 3D Feature | HIGH |
| 9 | revolve_sketch | 3D Feature | HIGH |
| 10 | measure_distance | Measurement | MEDIUM |
| 11 | get_mass_properties | Measurement | MEDIUM |
| 12 | trim_entities | 2D Sketch | MEDIUM |

### 5.6 Phase 2 Deliverables
- [ ] 12 new tools (28 total)
- [ ] Complete 2D sketch capability
- [ ] Cut operations
- [ ] Fillet & Chamfer
- [ ] Revolve feature
- [ ] Basic measurements
- [ ] All tools use unit conversion

---


# 6. PHASE 3: ADVANCED FEATURES
## Week 5-6 | Priority: MEDIUM-HIGH

### 6.1 Goals
- [ ] Sweep and Loft features
- [ ] Pattern features (linear, circular, mirror)
- [ ] Shell feature
- [ ] Reference geometry (planes, axes)
- [ ] Export formats (STEP, STL, DXF)

### 6.2 Advanced Feature Tools

#### Task 3.1: Sweep Feature
```python
def sweep_sketch(self, profile_sketch, path_sketch) -> Dict:
    """
    Sweep a profile along a path
    
    Args:
        profile_sketch: Name of profile sketch
        path_sketch: Name of path sketch
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Select profile
    doc.Extension.SelectByID2(profile_sketch, "SKETCH", 0, 0, 0, False, 1, None, 0)
    
    # Select path
    doc.Extension.SelectByID2(path_sketch, "SKETCH", 0, 0, 0, True, 4, None, 0)
    
    # InsertSweep2: Propagate, Alignment, TwistType, TwistAngle, etc.
    feat = doc.FeatureManager.InsertSweep2(
        False,      # Propagate
        True,       # Alignment type
        0,          # Twist type (none)
        0,          # Twist angle
        False,      # Keep tangency
        False,      # BSpline
        0, 0,       # Start/End scale
        True,       # Thin feature
        0.001,      # Thin wall thickness
        0,          # Thin wall type
        True,       # Merge
        True,       # Auto select
        True        # Feature scope
    )
    
    if feat is None:
        return self._result(False, "Sweep failed", SwErrors.swFeatureError)
    
    return self._result(True, "Sweep feature created", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 3.2: Loft Feature
```python
def loft_sketches(self, sketch_names: list) -> Dict:
    """
    Create loft between multiple sketches
    
    Args:
        sketch_names: List of sketch names in order
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if len(sketch_names) < 2:
        return self._result(False, "Loft needs at least 2 profiles", SwErrors.swFeatureError)
    
    # Select sketches as profiles
    for i, name in enumerate(sketch_names):
        append = (i > 0)
        doc.Extension.SelectByID2(name, "SKETCH", 0, 0, 0, append, 1, None, 0)
    
    # InsertLoftRefSurface: Closed, SmType, NoTwist, Guide, Close, etc.
    feat = doc.FeatureManager.InsertProtrusionLoft2(
        False,      # Closed
        True,       # SmType
        False,      # NoTwist
        True,       # Guide influence
        0,          # Start constraint (natural)
        0,          # End constraint (natural)
        0.0, 0.0,   # Start/End tangent length
        True,       # Maintain tangency
        True,       # MergeResult
        True,       # UseFeatScope
        True        # UseAutoSelect
    )
    
    if feat is None:
        return self._result(False, "Loft failed", SwErrors.swFeatureError)
    
    return self._result(True, f"Loft through {len(sketch_names)} profiles", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 3.3: Linear Pattern
```python
def pattern_linear(self, feature_name, direction="x", count=3, spacing=10, 
                   count2=1, spacing2=0, unit="mm") -> Dict:
    """
    Create linear pattern of a feature
    
    Args:
        feature_name: Feature to pattern
        direction: "x", "y", or edge name
        count: Number in first direction
        spacing: Spacing in first direction
        count2: Number in second direction
        spacing2: Spacing in second direction
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    spacing_m = self.units.to_meters(spacing, unit)
    spacing2_m = self.units.to_meters(spacing2, unit)
    
    # Select feature
    doc.Extension.SelectByID2(feature_name, "BODYFEATURE", 0, 0, 0, False, 4, None, 0)
    
    # Select direction
    if direction.lower() == "x":
        doc.Extension.SelectByID2("", "EDGE", 1, 0, 0, True, 1, None, 0)
    elif direction.lower() == "y":
        doc.Extension.SelectByID2("", "EDGE", 0, 1, 0, True, 1, None, 0)
    
    feat = doc.FeatureManager.FeatureLinearPattern4(
        count, spacing_m,           # D1 count and spacing
        count2, spacing2_m,         # D2 count and spacing
        True, False,                # D1Reverse, D2Reverse
        "", "",                     # D1PatternSeed, D2PatternSeed
        False,                      # GeomPattern
        True, True                  # FeatureScope, AutoSelect
    )
    
    if feat is None:
        return self._result(False, "Linear pattern failed", SwErrors.swFeatureError)
    
    total = count * (count2 if count2 > 0 else 1)
    return self._result(True, f"Linear pattern: {total} instances", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 3.4: Circular Pattern
```python
def pattern_circular(self, feature_name, axis="z", count=6, angle=360, unit="deg") -> Dict:
    """
    Create circular pattern
    
    Args:
        feature_name: Feature to pattern
        axis: "x", "y", "z", or axis name
        count: Number of instances
        angle: Total angle span
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    import math
    angle_rad = math.radians(angle)
    
    # Select feature
    doc.Extension.SelectByID2(feature_name, "BODYFEATURE", 0, 0, 0, False, 4, None, 0)
    
    # Select axis
    if axis.lower() == "z":
        doc.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, True, 1, None, 0)
    
    feat = doc.FeatureManager.FeatureCircularPattern4(
        count,              # Number
        angle_rad,          # Angle span
        False,              # Reverse
        "",                 # PatternSeed
        False,              # GeomPattern
        True,               # EqualSpacing
        True, True          # FeatureScope, AutoSelect
    )
    
    if feat is None:
        return self._result(False, "Circular pattern failed", SwErrors.swFeatureError)
    
    return self._result(True, f"Circular pattern: {count} instances", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 3.5: Mirror Feature
```python
def mirror_feature(self, feature_name, plane="Right") -> Dict:
    """
    Mirror a feature about a plane
    
    Args:
        feature_name: Feature to mirror
        plane: "Front", "Top", "Right" or plane name
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    plane_map = {"Front": "Front Plane", "Top": "Top Plane", "Right": "Right Plane"}
    plane_name = plane_map.get(plane, plane)
    
    # Select feature
    doc.Extension.SelectByID2(feature_name, "BODYFEATURE", 0, 0, 0, False, 4, None, 0)
    
    # Select plane
    doc.Extension.SelectByID2(plane_name, "PLANE", 0, 0, 0, True, 1, None, 0)
    
    feat = doc.FeatureManager.FeatureMirror2(
        True,   # FeatureScope
        True,   # AutoSelect
        False,  # GeomPattern
        True    # Propagate visual properties
    )
    
    if feat is None:
        return self._result(False, "Mirror failed", SwErrors.swFeatureError)
    
    return self._result(True, f"Mirrored about {plane_name}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 3.6: Shell Feature
```python
def shell_body(self, thickness, faces_to_remove=None, unit="mm") -> Dict:
    """
    Shell a solid body
    
    Args:
        thickness: Wall thickness
        faces_to_remove: List of face indices to remove (optional)
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    thickness_m = self.units.to_meters(thickness, unit)
    
    if faces_to_remove:
        # Select faces to remove
        doc.ClearSelection2(True)
        for face_idx in faces_to_remove:
            doc.Extension.SelectByID2(f"Face<{face_idx}>", "FACE", 0, 0, 0, True, 0, None, 0)
    
    feat = doc.FeatureManager.InsertFeatureShell2(
        thickness_m,    # Thickness
        False,          # Shell outward
        True            # Show preview
    )
    
    if feat is None:
        return self._result(False, "Shell failed", SwErrors.swFeatureError)
    
    return self._result(True, f"Shell: {thickness}{unit} wall", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 6.3 Export Tools

#### Task 3.7: Export to STEP
```python
def export_step(self, filepath) -> Dict:
    """
    Export model to STEP format
    
    Args:
        filepath: Output file path (e.g., "C:/export/part.step")
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Ensure .step extension
    if not filepath.lower().endswith(('.step', '.stp')):
        filepath += '.step'
    
    # Create directory if needed
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # SaveAs with STEP format
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    
    # Save as STEP (format constant: swFileType_e.swSTEP_FILE = 4)
    result = doc.Extension.SaveAs(filepath, 0, 0, None, errors, warnings)
    
    if not result or errors.value != 0:
        return self._result(False, f"Export failed (code {errors.value})", SwErrors.swFileSaveError)
    
    return self._result(True, f"Exported to: {filepath}", SwErrors.swSuccess, {"path": filepath})
```
**Status:** [ ] Not Started

---

#### Task 3.8: Export to STL
```python
def export_stl(self, filepath, quality="fine", binary=True) -> Dict:
    """
    Export model to STL format for 3D printing
    
    Args:
        filepath: Output file path
        quality: "coarse", "medium", "fine", "custom"
        binary: True for binary STL, False for ASCII
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Ensure .stl extension
    if not filepath.lower().endswith('.stl'):
        filepath += '.stl'
    
    # Create directory
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # Set STL quality options
    quality_map = {
        "coarse": (0.1, 30),    # Deviation, Angle
        "medium": (0.05, 15),
        "fine": (0.01, 5),
    }
    deviation, angle = quality_map.get(quality, quality_map["fine"])
    
    # Export
    result = doc.SaveAs4(
        filepath,
        0,      # Save as type
        1 if binary else 0,  # Options
        0,      # Ref configuration
        0       # Alternate geometry
    )
    
    if not result:
        return self._result(False, "STL export failed", SwErrors.swFileSaveError)
    
    return self._result(True, f"STL exported: {filepath}", SwErrors.swSuccess, {
        "path": filepath,
        "quality": quality,
        "binary": binary
    })
```
**Status:** [ ] Not Started

---

#### Task 3.9: Export to DXF
```python
def export_dxf(self, filepath, sheet_name=None) -> Dict:
    """
    Export drawing or flat pattern to DXF
    
    Args:
        filepath: Output file path
        sheet_name: Sheet name for drawings (optional)
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if not filepath.lower().endswith('.dxf'):
        filepath += '.dxf'
    
    # SaveAs with DXF format
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    
    result = doc.Extension.SaveAs(filepath, 0, 0, None, errors, warnings)
    
    if not result:
        return self._result(False, "DXF export failed", SwErrors.swFileSaveError)
    
    return self._result(True, f"DXF exported: {filepath}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 6.4 Reference Geometry Tools

#### Task 3.10: Create Reference Plane
```python
def create_plane(self, offset=0, reference="Front", unit="mm") -> Dict:
    """
    Create a reference plane
    
    Args:
        offset: Offset distance from reference
        reference: "Front", "Top", "Right", or face name
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    offset_m = self.units.to_meters(offset, unit)
    
    ref_map = {"Front": "Front Plane", "Top": "Top Plane", "Right": "Right Plane"}
    ref_name = ref_map.get(reference, reference)
    
    # Select reference
    doc.Extension.SelectByID2(ref_name, "PLANE", 0, 0, 0, False, 0, None, 0)
    
    # Create offset plane
    feat = doc.FeatureManager.InsertRefPlane(
        1 | 4,      # Type: parallel at distance (swRefPlaneReferenceConstraint_Parallel | Distance)
        offset_m,   # D1 (offset)
        0,          # D2
        0,          # D3
        0,          # D4
        0           # D5
    )
    
    if feat is None:
        return self._result(False, "Failed to create plane", SwErrors.swFeatureError)
    
    return self._result(True, f"Plane created {offset}{unit} from {reference}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 6.5 Phase 3 Tool Summary

| # | Tool | Category | Priority |
|---|------|----------|----------|
| 1 | sweep_sketch | 3D Feature | HIGH |
| 2 | loft_sketches | 3D Feature | HIGH |
| 3 | pattern_linear | Pattern | HIGH |
| 4 | pattern_circular | Pattern | HIGH |
| 5 | mirror_feature | Pattern | HIGH |
| 6 | shell_body | 3D Feature | MEDIUM |
| 7 | export_step | Export | HIGH |
| 8 | export_stl | Export | HIGH |
| 9 | export_dxf | Export | MEDIUM |
| 10 | create_plane | Reference | MEDIUM |

### 6.6 Phase 3 Deliverables
- [ ] 10 new tools (38 total)
- [ ] Sweep and Loft features
- [ ] Pattern features
- [ ] Shell feature
- [ ] Export to STEP, STL, DXF
- [ ] Reference plane creation

---


# 7. PHASE 4: ASSEMBLY & DRAWING SUPPORT
## Week 7-8 | Priority: HIGH

### 7.1 Goals
- [ ] Create assemblies
- [ ] Insert components
- [ ] Add mates/constraints
- [ ] Create drawings
- [ ] Add drawing views
- [ ] Add dimensions to drawings

> **Status as of 2026-09-24:** assembly creation, component insertion and the
> three mates (`4.1`–`4.5`), the drawing view tool `4.7`
> (`add_standard_3_view`), the drawing dimension tool `4.8`
> (`add_drawing_dimension`) and the cut-list table `F` are live-verified in
> `scripts/capability_requirements.json`. No original numbered Phase 4
> requirement is absent any more, and the `D1` marked-vs-unmarked dimension
> filter is proven live (`insert_marked_dimensions` now uses
> `InsertModelAnnotations4`; see `docs/api-findings.md` §58).

### 7.2 Assembly Tools

#### Task 4.1: Create Assembly
```python
def create_assembly(self) -> Dict:
    """Create a new assembly document"""
    try:
        if not self.is_connected:
            r = self.connect()
            if not r["success"]: return r
        
        # Search for assembly template
        template = None
        sw_dir = os.path.dirname(SOLIDWORKS_EXE)
        
        search_paths = [
            os.path.join(sw_dir, "data", "templates", "Assembly.asmdot"),
            os.path.join(sw_dir, "lang", "english", "Tutorial", "Assembly.asmdot"),
            r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\Assembly.asmdot",
        ]
        
        for t in search_paths:
            if os.path.exists(t):
                template = t
                break
        
        if not template:
            template = ""  # Use SolidWorks default
        
        doc = self._sw_app.NewDocument(template, 0, 0, 0)
        
        if doc is None:
            return self._result(False, "Failed to create assembly", SwErrors.swFileLoadError)
        
        # Set isometric view
        doc.ShowNamedView2("*Isometric", 7)
        doc.ViewZoomtofit2()
        
        title = doc.GetTitle() if hasattr(doc, 'GetTitle') else "Assembly1"
        if callable(title): title = title()
        
        return self._result(True, f"Created assembly: {title}", SwErrors.swSuccess, 
                          {"name": title, "type": "Assembly"})
    except Exception as e:
        return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
```
**Status:** [ ] Not Started

---

#### Task 4.2: Insert Component
```python
def insert_component(self, filepath, x=0, y=0, z=0, unit="mm") -> Dict:
    """
    Insert a component into the assembly
    
    Args:
        filepath: Path to part or assembly file
        x, y, z: Position coordinates
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Check if this is an assembly
    if doc.GetType() != 2:  # swDocASSEMBLY = 2
        return self._result(False, "Active document is not an assembly", SwErrors.swUnknownError)
    
    if not os.path.exists(filepath):
        return self._result(False, f"File not found: {filepath}", SwErrors.swFileNotFoundError)
    
    x_m = self.units.to_meters(x, unit)
    y_m = self.units.to_meters(y, unit)
    z_m = self.units.to_meters(z, unit)
    
    # AddComponent5: PathName, ConfigName, X, Y, Z, AddConstraints
    component = doc.AddComponent5(
        filepath,
        0,          # swAddComponentConfigOptions_CurrentSelectedConfig
        "",         # Configuration name (empty = active)
        False,      # Use lightweight
        "",         # Ref configuration
        x_m, y_m, z_m  # Position
    )
    
    if component is None:
        return self._result(False, "Failed to insert component", SwErrors.swFileLoadError)
    
    component_name = os.path.basename(filepath)
    return self._result(True, f"Inserted: {component_name}", SwErrors.swSuccess, {
        "component": component_name,
        "position": {"x": x, "y": y, "z": z, "unit": unit}
    })
```
**Status:** [ ] Not Started

---

#### Task 4.3: Add Mate (Coincident)
```python
def mate_coincident(self, entity1, entity2, flip=False) -> Dict:
    """
    Add coincident mate between two entities
    
    Args:
        entity1: First entity (e.g., "Face<1>@Part1-1")
        entity2: Second entity
        flip: Flip alignment direction
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if doc.GetType() != 2:
        return self._result(False, "Not an assembly", SwErrors.swUnknownError)
    
    # Clear selection
    doc.ClearSelection2(True)
    
    # Select entities
    doc.Extension.SelectByID2(entity1, "FACE", 0, 0, 0, False, 1, None, 0)
    doc.Extension.SelectByID2(entity2, "FACE", 0, 0, 0, True, 1, None, 0)
    
    # AddMate5: swMateType, swMateAlign, Flip, Distance, DistanceAbsUpperLimit, etc.
    # swMateCOINCIDENT = 0
    mate = doc.AddMate5(
        0,          # Mate type (Coincident)
        1 if flip else 0,  # Alignment
        False,      # Flip
        0, 0, 0,    # Distance limits
        0, 0, 0,    # Angle limits
        0, 0, 0, 0, # Additional params
        False,      # Locked rotation
        True        # Preview
    )
    
    if mate is None:
        return self._result(False, "Failed to add coincident mate", SwErrors.swFeatureError)
    
    return self._result(True, "Coincident mate added", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 4.4: Add Mate (Concentric)
```python
def mate_concentric(self, entity1, entity2) -> Dict:
    """
    Add concentric mate between cylindrical faces
    
    Args:
        entity1: First cylindrical face
        entity2: Second cylindrical face
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if doc.GetType() != 2:
        return self._result(False, "Not an assembly", SwErrors.swUnknownError)
    
    doc.ClearSelection2(True)
    doc.Extension.SelectByID2(entity1, "FACE", 0, 0, 0, False, 1, None, 0)
    doc.Extension.SelectByID2(entity2, "FACE", 0, 0, 0, True, 1, None, 0)
    
    # swMateCONCENTRIC = 1
    mate = doc.AddMate5(1, 0, False, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, True)
    
    if mate is None:
        return self._result(False, "Failed to add concentric mate", SwErrors.swFeatureError)
    
    return self._result(True, "Concentric mate added", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 4.5: Add Distance Mate
```python
def mate_distance(self, entity1, entity2, distance, unit="mm") -> Dict:
    """
    Add distance mate between two entities
    
    Args:
        entity1: First entity
        entity2: Second entity
        distance: Distance value
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if doc.GetType() != 2:
        return self._result(False, "Not an assembly", SwErrors.swUnknownError)
    
    dist_m = self.units.to_meters(distance, unit)
    
    doc.ClearSelection2(True)
    doc.Extension.SelectByID2(entity1, "FACE", 0, 0, 0, False, 1, None, 0)
    doc.Extension.SelectByID2(entity2, "FACE", 0, 0, 0, True, 1, None, 0)
    
    # swMateDISTANCE = 5
    mate = doc.AddMate5(5, 0, False, dist_m, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, True)
    
    if mate is None:
        return self._result(False, "Failed to add distance mate", SwErrors.swFeatureError)
    
    return self._result(True, f"Distance mate: {distance}{unit}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 7.3 Drawing Tools

#### Task 4.6: Create Drawing
```python
def create_drawing(self, paper_size="A4", orientation="landscape") -> Dict:
    """
    Create a new drawing document
    
    Args:
        paper_size: "A4", "A3", "A2", "A1", "A0", "Letter", "Legal"
        orientation: "landscape" or "portrait"
    """
    try:
        if not self.is_connected:
            r = self.connect()
            if not r["success"]: return r
        
        # Search for drawing template
        template = None
        sw_dir = os.path.dirname(SOLIDWORKS_EXE)
        
        search_paths = [
            os.path.join(sw_dir, "data", "templates", "Drawing.drwdot"),
            os.path.join(sw_dir, "lang", "english", "Tutorial", "Drawing.drwdot"),
        ]
        
        for t in search_paths:
            if os.path.exists(t):
                template = t
                break
        
        doc = self._sw_app.NewDocument(template or "", 0, 0, 0)
        
        if doc is None:
            return self._result(False, "Failed to create drawing", SwErrors.swFileLoadError)
        
        # Set paper size
        paper_sizes = {
            "A4": (0.210, 0.297),
            "A3": (0.297, 0.420),
            "A2": (0.420, 0.594),
            "A1": (0.594, 0.841),
            "A0": (0.841, 1.189),
            "Letter": (0.2159, 0.2794),
            "Legal": (0.2159, 0.3556),
        }
        
        width, height = paper_sizes.get(paper_size, paper_sizes["A4"])
        if orientation == "landscape":
            width, height = height, width
        
        # Get active sheet and set size
        sheet = doc.GetCurrentSheet()
        if sheet:
            sheet.SetSize(99, width, height)  # 99 = custom size
        
        return self._result(True, f"Created {paper_size} {orientation} drawing", SwErrors.swSuccess)
    except Exception as e:
        return self._result(False, f"Error: {e}", SwErrors.swFileLoadError)
```
**Status:** [ ] Not Started

---

#### Task 4.7: Add Drawing View
```python
def add_drawing_view(self, model_path, view_type="front", scale=1.0, x=0.1, y=0.1) -> Dict:
    """
    Add a view to the drawing
    
    Args:
        model_path: Path to part/assembly file
        view_type: "front", "back", "left", "right", "top", "bottom", "isometric"
        scale: View scale (1.0 = 1:1, 0.5 = 1:2)
        x, y: Position on sheet (meters from bottom-left)
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if doc.GetType() != 3:  # swDocDRAWING = 3
        return self._result(False, "Not a drawing document", SwErrors.swUnknownError)
    
    view_types = {
        "front": 1, "back": 2, "left": 3, "right": 4,
        "top": 5, "bottom": 6, "isometric": 7
    }
    view_code = view_types.get(view_type.lower(), 1)
    
    # Create model view
    # CreateDrawViewFromModelView3: ModelName, ViewName, X, Y, Z
    view = doc.CreateDrawViewFromModelView3(
        model_path,
        "*" + view_type.capitalize(),  # View name
        x, y, 0
    )
    
    if view is None:
        return self._result(False, "Failed to add view", SwErrors.swFeatureError)
    
    # Set scale
    view.SetScale2(scale, 1)
    
    return self._result(True, f"Added {view_type} view at {scale}:1", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

#### Task 4.8: Add Dimension to Drawing
```python
def add_drawing_dimension(self, entity1, entity2=None, x=0, y=0) -> Dict:
    """
    Add dimension to drawing view
    
    Args:
        entity1: First entity to dimension
        entity2: Second entity (optional, for distance dimensions)
        x, y: Dimension text position
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    if doc.GetType() != 3:
        return self._result(False, "Not a drawing", SwErrors.swUnknownError)
    
    # Select entities
    doc.ClearSelection2(True)
    doc.Extension.SelectByID2(entity1, "EDGE", 0, 0, 0, False, 0, None, 0)
    if entity2:
        doc.Extension.SelectByID2(entity2, "EDGE", 0, 0, 0, True, 0, None, 0)
    
    # Add dimension
    dim = doc.AddDimension2(x, y, 0)
    
    if dim is None:
        return self._result(False, "Failed to add dimension", SwErrors.swFeatureError)
    
    return self._result(True, "Dimension added", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 7.4 Phase 4 Tool Summary

| # | Tool | Category | Priority |
|---|------|----------|----------|
| 1 | create_assembly | Assembly | HIGH |
| 2 | insert_component | Assembly | HIGH |
| 3 | mate_coincident | Assembly | HIGH |
| 4 | mate_concentric | Assembly | HIGH |
| 5 | mate_distance | Assembly | MEDIUM |
| 6 | create_drawing | Drawing | HIGH |
| 7 | add_drawing_view | Drawing | HIGH |
| 8 | add_drawing_dimension | Drawing | MEDIUM |

Status as of 2026-09-24: rows 1–5, 7 and 8 are live-verified (the implemented
names are `create_new_assembly`, `insert_component`, `mate_coincident`,
`mate_concentric`, `mate_distance`, `add_standard_3_view` and
`add_drawing_dimension`); row 6 is automation-only (`4.6`, internal_only).

### 7.5 Phase 4 Deliverables
- [x] Assembly tools — `create_new_assembly`, `insert_component` live-verified
- [x] Basic mate types — `mate_coincident`, `mate_concentric`, `mate_distance` live-verified
- [x] Drawing creation — `create_new_drawing` (automation, internal_only)
- [x] Drawing views — `add_standard_3_view`, `list_drawing_views` live-verified
- [x] Basic dimensioning — `add_drawing_dimension` (`4.8`) live-verified

---

# 8. PHASE 5: SIMULATION & ANALYSIS
## Week 9-10 | Priority: MEDIUM

### 8.1 Goals
- [ ] Static stress analysis
- [ ] Modal analysis setup
- [ ] Results extraction
- [ ] Design table support
- [ ] Configuration management

### 8.2 Simulation Tools

#### Task 5.1: Create Static Study
```python
def create_static_study(self, study_name="Static Study") -> Dict:
    """
    Create a new static stress analysis study
    
    Args:
        study_name: Name for the study
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Get SOLIDWORKS Simulation add-in
    try:
        cosworks = self._sw_app.GetAddInObject("SldWorks.Simulation")
        if cosworks is None:
            return self._result(False, "SOLIDWORKS Simulation not available", SwErrors.swUnknownError)
        
        # Get active document's simulation interface
        cwdoc = cosworks.ActiveDoc
        if cwdoc is None:
            return self._result(False, "Cannot access simulation for this document", SwErrors.swUnknownError)
        
        # Create study (Type 1 = Static)
        study = cwdoc.CreateNewStudy2(study_name, 1, None)
        
        if study is None:
            return self._result(False, "Failed to create study", SwErrors.swFeatureError)
        
        return self._result(True, f"Created static study: {study_name}", SwErrors.swSuccess)
    except Exception as e:
        return self._result(False, f"Simulation error: {e}", SwErrors.swUnknownError)
```
**Status:** [ ] Not Started

---

#### Task 5.2: Apply Material
```python
def apply_material(self, material_name, library="solidworks materials") -> Dict:
    """
    Apply material to the active part
    
    Args:
        material_name: Material name (e.g., "AISI 1020 Steel")
        library: Material library name
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Get material database
    # SetMaterialPropertyName2: ConfigName, DatabaseFile, MaterialName
    result = doc.SetMaterialPropertyName2(
        "",  # Active configuration
        library,
        material_name
    )
    
    if not result:
        return self._result(False, f"Material '{material_name}' not found", SwErrors.swUnknownError)
    
    return self._result(True, f"Applied material: {material_name}", SwErrors.swSuccess)
```
**Status:** [x] Implemented and `current_live` (as of 2026-09-24). The registered
tool `apply_material` applies a material to the active configuration and is
live-verified (material read back; density/mass consistent with the geometry).
This is material assignment only, **not** a Simulation study: `create_static_study`,
fixtures, loads, run and results (`5.1`, `5.3`–`5.6`) remain absent. See §12.3.

---

#### Task 5.3: Apply Fixed Fixture
```python
def apply_fixture_fixed(self, face_name) -> Dict:
    """
    Apply fixed fixture to a face
    
    Args:
        face_name: Face to fix (e.g., "Face<1>")
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    try:
        cosworks = self._sw_app.GetAddInObject("SldWorks.Simulation")
        cwdoc = cosworks.ActiveDoc
        study = cwdoc.ActiveStudy
        
        if study is None:
            return self._result(False, "No active study", SwErrors.swUnknownError)
        
        # Select face
        doc.Extension.SelectByID2(face_name, "FACE", 0, 0, 0, False, 0, None, 0)
        
        # Apply fixed restraint (Type 0)
        lbc = study.AddRestraint(0, None, None, 0, 0, 0, 0, 0, 0, 0, 0)
        
        if lbc is None:
            return self._result(False, "Failed to apply fixture", SwErrors.swFeatureError)
        
        return self._result(True, f"Fixed fixture on {face_name}", SwErrors.swSuccess)
    except Exception as e:
        return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
```
**Status:** [ ] Not Started

---

#### Task 5.4: Apply Force Load
```python
def apply_force(self, face_name, force_value, direction="normal", unit="N") -> Dict:
    """
    Apply force load to a face
    
    Args:
        face_name: Face to apply force
        force_value: Force magnitude
        direction: "normal", "x", "y", "z"
        unit: Force unit ("N", "kN", "lbf")
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Convert force to Newtons
    force_conversion = {"N": 1.0, "kN": 1000.0, "lbf": 4.44822}
    force_n = force_value * force_conversion.get(unit, 1.0)
    
    try:
        cosworks = self._sw_app.GetAddInObject("SldWorks.Simulation")
        cwdoc = cosworks.ActiveDoc
        study = cwdoc.ActiveStudy
        
        if study is None:
            return self._result(False, "No active study", SwErrors.swUnknownError)
        
        # Select face
        doc.Extension.SelectByID2(face_name, "FACE", 0, 0, 0, False, 0, None, 0)
        
        # Direction components
        dir_vectors = {
            "normal": (0, 0, 0),  # Normal to face
            "x": (1, 0, 0),
            "y": (0, 1, 0),
            "z": (0, 0, 1),
        }
        dx, dy, dz = dir_vectors.get(direction.lower(), (0, 0, 0))
        
        # Apply force (Type 1)
        load = study.AddLoad(1, None, None, force_n, dx, dy, dz, 0, 0, 0)
        
        if load is None:
            return self._result(False, "Failed to apply force", SwErrors.swFeatureError)
        
        return self._result(True, f"Applied {force_value}{unit} force on {face_name}", SwErrors.swSuccess)
    except Exception as e:
        return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
```
**Status:** [ ] Not Started

---

#### Task 5.5: Run Analysis
```python
def run_simulation(self) -> Dict:
    """
    Run the active simulation study
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    try:
        cosworks = self._sw_app.GetAddInObject("SldWorks.Simulation")
        cwdoc = cosworks.ActiveDoc
        study = cwdoc.ActiveStudy
        
        if study is None:
            return self._result(False, "No active study", SwErrors.swUnknownError)
        
        # Create mesh
        mesh = study.Mesh
        if mesh is None:
            return self._result(False, "Failed to create mesh", SwErrors.swFeatureError)
        
        mesh.Quality = 1  # High quality
        mesh_result = mesh.CreateMesh(0, 0)  # Auto element size
        
        if mesh_result != 0:
            return self._result(False, f"Mesh failed (code {mesh_result})", SwErrors.swFeatureError)
        
        # Run analysis
        run_result = study.RunAnalysis()
        
        if run_result != 0:
            return self._result(False, f"Analysis failed (code {run_result})", SwErrors.swFeatureError)
        
        return self._result(True, "Simulation completed successfully", SwErrors.swSuccess)
    except Exception as e:
        return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
```
**Status:** [ ] Not Started

---

#### Task 5.6: Get Stress Results
```python
def get_stress_results(self) -> Dict:
    """
    Get stress results from completed simulation
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    try:
        cosworks = self._sw_app.GetAddInObject("SldWorks.Simulation")
        cwdoc = cosworks.ActiveDoc
        study = cwdoc.ActiveStudy
        
        if study is None:
            return self._result(False, "No active study", SwErrors.swUnknownError)
        
        # Get results
        results = study.Results
        if results is None:
            return self._result(False, "No results available", SwErrors.swUnknownError)
        
        # Get von Mises stress
        stress = results.GetMinMaxStress(
            0,      # Component (0 = VON Mises)
            1,      # Step
            None,   # Entities
            0,      # Unit (Pa)
            None, None  # Min/Max location arrays
        )
        
        min_stress = stress[0] / 1e6  # Convert to MPa
        max_stress = stress[1] / 1e6
        
        return self._result(True, f"Max stress: {max_stress:.2f} MPa", SwErrors.swSuccess, {
            "min_stress_mpa": min_stress,
            "max_stress_mpa": max_stress,
            "stress_type": "von Mises"
        })
    except Exception as e:
        return self._result(False, f"Error: {e}", SwErrors.swUnknownError)
```
**Status:** [ ] Not Started

---

### 8.3 Phase 5 Tool Summary

| # | Tool | Category | Priority |
|---|------|----------|----------|
| 1 | create_static_study | Simulation | HIGH |
| 2 | apply_material | Simulation | HIGH |
| 3 | apply_fixture_fixed | Simulation | HIGH |
| 4 | apply_force | Simulation | HIGH |
| 5 | run_simulation | Simulation | HIGH |
| 6 | get_stress_results | Simulation | HIGH |

Status as of 2026-09-24: only `apply_material` (`5.2`) is implemented and
live-verified. It assigns a material to the active configuration and does **not**
create or run a Simulation study. `create_static_study`, `apply_fixed_fixture`,
`apply_force_load`, `run_analysis` and `get_stress_results` (`5.1`, `5.3`–`5.6`)
remain absent and are deferred.

### 8.4 Phase 5 Deliverables
- [ ] Static analysis workflow — deferred (`5.1`, `5.3`–`5.6` absent)
- [x] Material assignment — `apply_material` (`5.2`) live-verified (assignment only)
- [ ] Boundary conditions — deferred
- [ ] Results extraction — deferred

---


# 9. PHASE 6: PRODUCTION HARDENING
## Week 11-12 | Priority: HIGH

### 9.1 Goals
- [ ] Comprehensive error handling
- [ ] Recovery mechanisms
- [ ] Performance optimization
- [ ] Validation & sanitization
- [ ] Documentation completion
- [ ] Test coverage > 80%

### 9.2 Error Recovery System

#### Task 6.1: Connection Recovery
```python
class ConnectionManager:
    """Robust connection management with recovery"""
    
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    
    def __init__(self, automation):
        self.automation = automation
        self.connection_attempts = 0
        self.last_error = None
    
    async def ensure_connected(self) -> bool:
        """Ensure connection with automatic recovery"""
        if self.automation.is_connected:
            return True
        
        for attempt in range(self.MAX_RETRIES):
            try:
                result = self.automation.connect()
                if result["success"]:
                    self.connection_attempts = 0
                    return True
                
                self.last_error = result["message"]
                logger.warning(f"Connection attempt {attempt + 1} failed: {self.last_error}")
                
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)
                    
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Connection error: {e}")
        
        return False
    
    def handle_com_error(self, error) -> Dict:
        """Handle COM errors with recovery suggestions"""
        error_str = str(error)
        
        recovery_actions = {
            "RPC server": "SolidWorks may have crashed. Restart required.",
            "Call was rejected": "SolidWorks is busy. Wait and retry.",
            "Interface not registered": "COM registration issue. Repair SolidWorks.",
            "Access denied": "Permission issue. Run as administrator.",
        }
        
        for pattern, action in recovery_actions.items():
            if pattern.lower() in error_str.lower():
                return {
                    "error": error_str,
                    "recovery": action,
                    "retry_possible": "rejected" in error_str.lower()
                }
        
        return {"error": error_str, "recovery": "Unknown error. Check log file."}
```
**Status:** [ ] Not Started

---

#### Task 6.2: Input Validation
```python
from typing import Union, List, Tuple
import re

class InputValidator:
    """Validate and sanitize user inputs"""
    
    @staticmethod
    def validate_filepath(filepath: str) -> Tuple[bool, str]:
        """Validate file path"""
        if not filepath:
            return False, "File path cannot be empty"
        
        # Check for invalid characters
        invalid_chars = '<>"|?*'
        for char in invalid_chars:
            if char in filepath:
                return False, f"Invalid character '{char}' in path"
        
        # Check extension
        valid_extensions = ['.sldprt', '.sldasm', '.slddrw', '.step', '.stl', '.dxf']
        ext = os.path.splitext(filepath)[1].lower()
        if ext and ext not in valid_extensions:
            return False, f"Invalid extension: {ext}"
        
        return True, "Valid"
    
    @staticmethod
    def validate_dimension(value: Union[int, float], 
                          min_val: float = 0.0001, 
                          max_val: float = 1000.0,
                          unit: str = "m") -> Tuple[bool, str]:
        """Validate dimension value"""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False, "Invalid numeric value"
        
        if value < min_val:
            return False, f"Value too small (min: {min_val}{unit})"
        if value > max_val:
            return False, f"Value too large (max: {max_val}{unit})"
        
        return True, "Valid"
    
    @staticmethod
    def validate_plane(plane: str) -> Tuple[bool, str]:
        """Validate plane name"""
        valid_planes = ["Front", "Top", "Right", "front", "top", "right"]
        if plane not in valid_planes:
            return False, f"Invalid plane. Use: Front, Top, or Right"
        return True, "Valid"
    
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Sanitize filename by removing invalid characters"""
        # Remove or replace invalid characters
        invalid = '<>:"/\\|?*'
        for char in invalid:
            name = name.replace(char, '_')
        return name.strip()
```
**Status:** [ ] Not Started

---

#### Task 6.3: Performance Optimization
```python
import functools
import time
from threading import Lock

class PerformanceOptimizer:
    """Optimize MCP server performance"""
    
    _cache = {}
    _cache_lock = Lock()
    _cache_ttl = 60  # seconds
    
    @classmethod
    def cached(cls, ttl: int = None):
        """Decorator to cache function results"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
                
                with cls._cache_lock:
                    if cache_key in cls._cache:
                        result, timestamp = cls._cache[cache_key]
                        if time.time() - timestamp < (ttl or cls._cache_ttl):
                            return result
                
                result = func(*args, **kwargs)
                
                with cls._cache_lock:
                    cls._cache[cache_key] = (result, time.time())
                
                return result
            return wrapper
        return decorator
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached results"""
        with cls._cache_lock:
            cls._cache.clear()
    
    @staticmethod
    def batch_operations(operations: List[callable]) -> List:
        """Execute multiple operations in batch"""
        results = []
        for op in operations:
            try:
                results.append(op())
            except Exception as e:
                results.append({"error": str(e)})
        return results

# Usage example
class SolidWorksAutomationOptimized(SolidWorksAutomation):
    
    @PerformanceOptimizer.cached(ttl=30)
    def get_document_info(self) -> Dict:
        """Cached document info"""
        return super().get_document_info()
    
    @PerformanceOptimizer.cached(ttl=300)
    def get_available_materials(self) -> List[str]:
        """Cached material list"""
        # ... implementation
        pass
```
**Status:** [ ] Not Started

---

### 9.3 Additional Utility Tools

#### Task 6.4: Undo/Redo Support
```python
def undo(self) -> Dict:
    """Undo last operation"""
    doc, err = self.get_active_doc()
    if err: return err
    
    # EditUndo2 returns True if successful
    result = self._sw_app.EditUndo2(1)  # Undo 1 step
    
    if result:
        return self._result(True, "Undo successful", SwErrors.swSuccess)
    return self._result(False, "Nothing to undo", SwErrors.swUnknownError)

def redo(self) -> Dict:
    """Redo last undone operation"""
    doc, err = self.get_active_doc()
    if err: return err
    
    result = self._sw_app.EditRedo2(1)
    
    if result:
        return self._result(True, "Redo successful", SwErrors.swSuccess)
    return self._result(False, "Nothing to redo", SwErrors.swUnknownError)
```
**Status:** [ ] Not Started

---

#### Task 6.5: Screenshot/View Capture
```python
def capture_view(self, filepath, width=1920, height=1080) -> Dict:
    """
    Capture current view as image
    
    Args:
        filepath: Output image path (.png, .jpg, .bmp)
        width: Image width in pixels
        height: Image height in pixels
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    # Ensure directory exists
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # Get model view
    view = doc.ActiveView
    if view is None:
        return self._result(False, "No active view", SwErrors.swUnknownError)
    
    # Capture to file
    # SaveBMP: FileName, Width, Height
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.png':
        result = doc.SaveBMP(filepath, width, height)
    elif ext in ['.jpg', '.jpeg']:
        result = doc.SaveBMP(filepath.replace(ext, '.bmp'), width, height)
        # Convert BMP to JPG if needed
    else:
        result = doc.SaveBMP(filepath, width, height)
    
    if not result:
        return self._result(False, "Failed to capture view", SwErrors.swFileSaveError)
    
    return self._result(True, f"Captured: {filepath}", SwErrors.swSuccess, {
        "path": filepath,
        "width": width,
        "height": height
    })
```
**Status:** [ ] Not Started

---

#### Task 6.6: Zoom and View Control
```python
def zoom_fit(self) -> Dict:
    """Zoom to fit all geometry"""
    doc, err = self.get_active_doc()
    if err: return err
    
    doc.ViewZoomtofit2()
    return self._result(True, "Zoomed to fit", SwErrors.swSuccess)

def set_view(self, view_name="isometric") -> Dict:
    """
    Set standard view
    
    Args:
        view_name: "front", "back", "left", "right", "top", "bottom", "isometric", "trimetric", "dimetric"
    """
    doc, err = self.get_active_doc()
    if err: return err
    
    view_map = {
        "front": ("*Front", 1),
        "back": ("*Back", 2),
        "left": ("*Left", 3),
        "right": ("*Right", 4),
        "top": ("*Top", 5),
        "bottom": ("*Bottom", 6),
        "isometric": ("*Isometric", 7),
        "trimetric": ("*Trimetric", 8),
        "dimetric": ("*Dimetric", 9),
    }
    
    view_data = view_map.get(view_name.lower())
    if view_data is None:
        return self._result(False, f"Unknown view: {view_name}", SwErrors.swUnknownError)
    
    doc.ShowNamedView2(view_data[0], view_data[1])
    doc.ViewZoomtofit2()
    
    return self._result(True, f"Set view: {view_name}", SwErrors.swSuccess)
```
**Status:** [ ] Not Started

---

### 9.4 Phase 6 Tool Summary

| # | Tool | Category | Priority |
|---|------|----------|----------|
| 1 | undo | Utility | MEDIUM |
| 2 | redo | Utility | MEDIUM |
| 3 | capture_view | Export | MEDIUM |
| 4 | zoom_fit | View | LOW |
| 5 | set_view | View | LOW |

### 9.5 Phase 6 Deliverables
- [ ] 5 new tools (55+ total)
- [ ] Connection recovery system
- [ ] Input validation
- [ ] Performance caching
- [ ] Error recovery
- [ ] Complete test suite
- [ ] Documentation

---

# 10. TESTING STRATEGY

## 10.1 Test Categories

### Unit Tests
```python
# tests/test_units.py
import pytest
from utils.units import UnitConverter, mm, inch

class TestUnitConverter:
    def test_mm_to_meters(self):
        assert mm(50) == 0.05
    
    def test_inch_to_meters(self):
        assert abs(inch(1) - 0.0254) < 0.0001
    
    def test_converter_mm(self):
        conv = UnitConverter("mm")
        assert conv.to_meters(100) == 0.1
    
    def test_converter_inch(self):
        conv = UnitConverter("inch")
        assert abs(conv.to_meters(1) - 0.0254) < 0.0001
```

### Integration Tests
```python
# tests/test_integration.py
import pytest
from solidworks_mcp_server import sw_automation

class TestSolidWorksIntegration:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Connect to SolidWorks before tests"""
        result = sw_automation.connect()
        if not result["success"]:
            pytest.skip("SolidWorks not available")
    
    def test_create_part(self):
        result = sw_automation.create_new_part()
        assert result["success"] == True
        sw_automation.close_document()
    
    def test_create_sketch(self):
        sw_automation.create_new_part()
        result = sw_automation.create_sketch("Front")
        assert result["success"] == True
        sw_automation.close_document()
    
    def test_draw_circle(self):
        sw_automation.create_new_part()
        sw_automation.create_sketch("Front")
        result = sw_automation.draw_circle(0, 0, 0.05)
        assert result["success"] == True
        sw_automation.close_document()
    
    def test_full_workflow(self):
        """Test complete part creation workflow"""
        sw_automation.create_new_part()
        sw_automation.create_sketch("Front")
        sw_automation.draw_circle(0, 0, 0.025)
        result = sw_automation.extrude_sketch(0.01)
        assert result["success"] == True
        sw_automation.close_document()
```

## 10.2 Test Coverage Goals

| Phase | Target Coverage |
|-------|-----------------|
| Phase 1 | 60% |
| Phase 2 | 70% |
| Phase 3 | 75% |
| Phase 4 | 80% |
| Phase 5 | 80% |
| Phase 6 | 85%+ |

---

# 11. DOCUMENTATION PLAN

## 11.1 Documentation Files

| File | Purpose |
|------|---------|
| README.md | Quick start guide |
| INSTALLATION.md | Detailed installation |
| API_REFERENCE.md | All tools documented |
| EXAMPLES.md | Usage examples |
| TROUBLESHOOTING.md | Common issues |
| CHANGELOG.md | Version history |
| CONTRIBUTING.md | Developer guide |

## 11.2 API Documentation Template

```markdown
## Tool: `draw_circle`

### Description
Draw a circle in the active sketch.

### Parameters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| x | number | 0 | Center X coordinate |
| y | number | 0 | Center Y coordinate |
| radius | number | 50 | Circle radius |
| unit | string | "mm" | Unit (mm, inch, m) |

### Returns
```json
{
  "success": true,
  "message": "Circle r=50mm",
  "error_code": 0,
  "data": {
    "radius_mm": 50
  }
}
```

### Example Usage
"Draw a circle with 25mm radius at the origin"

### Notes
- Requires an active sketch
- Use `create_sketch` first
```

---

# 12. PROGRESS TRACKING

## 12.1 Phase Checklist

Status below is grounded in the generated capability register
(`docs/upgrade/specs/CAPABILITY-REGISTER.md`), which is derived from
`scripts/capability_requirements.json`. Registration and live verification are
separate: a checked box means the capability is registered and implemented, not
that it has live COM evidence.

### Phase 1: Foundation [DONE]
- [x] Project structure created — `1.1` internal_only (`registry.registered_tools`)
- [x] Configuration system — `1.2` internal_only (`config.get_config`)
- [x] Unit conversion — `1.3` registered (`set_units`)
- [x] Auto-detect SolidWorks — `1.4` registered (`get_solidworks_info`)
- [x] 5 new tools — `1.5` registered, current_live (`get_capabilities`)
- Evidence: `1.5` `get_capabilities` is current_live; `set_units` and `get_solidworks_info` are registered (static_only); structure and config are internal_only.

### Phase 2: Core Features [DONE]
- [x] Arc tools — `draw_arc`, `draw_arc_3point` (`2.1`, current_live)
- [x] Spline tool — `draw_spline` (`2.2`, current_live)
- [x] Polygon tool — `draw_polygon` (`2.3`, current_live)
- [x] Cut extrude — `cut_extrude` (`2.5`, current_live)
- [x] Fillet/Chamfer — `fillet_edges`, `chamfer_edges` (`2.6`, `2.7`, current_live)
- [x] Revolve — `revolve_sketch` (`2.8`, current_live)
- [x] Measurements — `measure_distance` (`2.9`), `get_mass_properties` (`2.summary.mass`), both current_live. (`2.4` `draw_slot` is also current_live.)
- Evidence: `2.1`–`2.9` are all registered and current_live.

### Phase 3: Advanced [DONE]
- [x] Sweep — `sweep_sketch` (`3.1`, current_live)
- [x] Loft — `loft_sketches` (`3.2`, current_live)
- [x] Patterns — `linear_pattern`, `circular_pattern` (`3.3`, `3.4`) and `mirror_feature` (`3.5`), all current_live
- [x] Shell — `shell_feature` (`3.6`, current_live)
- [x] Export tools — `export_step` (`3.7`), `export_stl` (`3.8`) and `export_face_to_dxf` (`3.9`, superseded) all current_live
- Evidence: `3.1`–`3.10` are registered and current_live; `3.9` is superseded by the explicit DXF tools.

### Phase 4: Assembly & Drawing [PARTIAL]
- [x] Assembly support — `create_new_assembly` (`4.1`), `insert_component` (`4.2`), both current_live
- [x] Mates — `mate_coincident`, `mate_concentric`, `mate_distance` (`4.3`–`4.5`), all current_live
- [x] Drawing support — `create_new_drawing` exists in automation (`4.6`, internal_only, not exposed as an MCP tool); `add_standard_3_view` (`4.7`, current_live); `list_drawing_views` and `insert_cut_list_table` (`F`, current_live) are registered
- [x] Views & dimensions — `add_drawing_dimension` (`4.8`) is now live-verified (auto-dimensioning a view)
- Evidence (as of 2026-09-24): `4.1`–`4.5`, `4.7` and `4.8` are current_live in `scripts/capability_requirements.json` (assembly created with components and mates; standard views plus a cut-list table on a saved weldment drawing; a model view gaining drawing dimensions). `4.6` stays internal_only. The `D1` marked-vs-unmarked dimension filter is also live-verified: only the marked dimension is imported, and the counterpart option imports only the unmarked one.

### Phase 5: Simulation [DEFERRED — out of the active plan]
- [ ] Static study — `create_static_study` (`5.1`) absent
- [x] Materials — `apply_material` (`5.2`) registered and current_live (material assignment only; no study is created)
- [ ] Loads & fixtures — `apply_fixed_fixture` (`5.3`), `apply_force_load` (`5.4`) absent
- [ ] Results — `run_analysis` (`5.5`), `get_stress_results` (`5.6`) absent
- Evidence (as of 2026-09-24): `5.2` `apply_material` is implemented and verified live (material read back in the active configuration; density/mass consistent). The rest of Phase 5 (`5.1`, `5.3`–`5.6`) is absent / not_run: applying a material does not run a Simulation study. Simulation is deferred, not deleted; the Phase 5 documentation below is kept for later.

### Phase 6: Production [DONE]
- [x] Error recovery — `connect_solidworks` (`6.1`, registered, static_only)
- [x] Validation — input validation (`6.2`, internal_only)
- [x] Performance — bounded traversal (`6.3`) registered and live-verified
- [x] Tests — unit tests plus opt-in live COM tests in `solidworks_mcp/tests`
- [x] Documentation — `HANDOFF.md` and `docs/api-findings.md`
- Evidence (as of 2026-09-24): `6.3` bounded traversal is live-verified (`inspect_document` depth 1..32 and paging, `list_components` depth); `6.4` `undo`/`redo`, `6.5` `capture_view` and `6.6` `set_view`/`zoom_fit` are current_live; `6.1` `connect_solidworks` remains registered static_only. No numbered Phase 6 item is absent any more.

## 12.2 Weekly Log Template

```markdown
## Week [X] - [Date]

### Completed
- [ ] Task 1
- [ ] Task 2

### In Progress
- [ ] Task 3

### Blocked
- [ ] Task 4 - Reason: ...

### Notes
- ...

### Next Week
- [ ] Task 5
- [ ] Task 6
```

## 12.3 Delivered vs Remaining (2026-09-24)

This section records PksOck's work in the `additional-upgrades` branch after
the verification recorded in `scripts/capability_requirements.json`. It does
not describe an upstream release. As of
24 September 2026 the generated register covers **138 requirement rows**:
registered 122, internal_only 4, superseded 1, blocked 4, absent 6, partial 1.
The one `partial` row is the new backlog item `B20` (fast and detailed
traversal for large assemblies): `list_components` exists but only in the
detailed mode. `B18` `save_document` is `registered`. By verification
status: current_live 118, static_only 9, not_run 7, failed 4.

### Delivered

**PART**
- Documents & utility (foundation): `create_new_part`, `open_document`, `close_document`, `get_document_info`, `list_open_documents`, `connect_solidworks`, `get_capabilities`, `bind_active_document`, `get_solidworks_info`, `set_units`, `undo`, `redo`, `set_view`, `zoom_fit`, `capture_view`
- Sketching: `create_sketch`, `create_sketch_on_face`, `draw_line`, `draw_circle`, `draw_rectangle`, `draw_arc`, `draw_arc_3point`, `draw_spline`, `draw_polygon`, `draw_slot`, `close_sketch`, `get_sketch_status`
- Sketch editing: `trim_entities`, `extend_entities`
- Features: `extrude_sketch`, `cut_extrude`, `revolve_sketch`, `fillet_edges`, `chamfer_edges`, `sweep_sketch`, `loft_sketches`, `shell_feature`
- Patterns: `linear_pattern`, `circular_pattern`, `mirror_feature`
- Reference geometry: `create_reference_plane`
- Measurement & inspection: `measure_distance`, `get_body_bounding_box`, `get_mass_properties`, `list_features`, `list_planes`, `list_planar_faces`, `inspect_document`
- Export: `export_step`, `export_stl`, `export_face_to_dxf`

**ASSEMBLY**
- Assembly creation: `create_new_assembly`
- Components: `insert_component`, `list_components`, `list_component_faces`
- Mates: `mate_coincident`, `mate_concentric`, `mate_distance`, `list_mates`

**DRAWING**
- Drawing documents: `create_new_drawing` (automation; `4.6`, internal_only)
- Views: `create_new_drawing` output plus `add_standard_3_view`, `list_drawing_views`
- Annotation: `insert_marked_dimensions`, `auto_balloon`

**EXTENSIONS**
- Weldments: `list_weldment_profiles`, `create_structural_member`
- Sheet metal: `get_sheet_metal_info`, `flatten_sheet_metal`, `get_flat_pattern_info`, `export_flat_pattern`
- Cut lists: `get_cut_list`, `insert_cut_list_table`
- Drawing annotations: `insert_marked_dimensions`, `auto_balloon`
- Guarded saving: `save_document`

**REGISTERED EXTENSION REQUIREMENTS M1/M2/M3 (as of 2026-09-24)**
- **M1 (sketching)** — 36 rows, 35 current_live, 1 not_run (`M1.1-k` perimeter/3-point circle is `absent` because the SW 2025 API exposes no such call). Covers centerline/point, circles and rectangles, ellipse/elliptical arc/parabola, tangent arc, arc slots, equation curves (2D and 3D), sketch fillet/chamfer, offset/mirror/split/scale/rotate/toggle-construction, relations and driving dimensions, sketch text, convert entities, and 2D/3D sketch creation.
- **M2 (advanced solid features)** — 21 rows: 20 current_live and 1 blocked (`M2.4-f` Split). Revolve/sweep/loft/boundary as cuts, draft, rib, dome, Hole Wizard, reference axis, custom properties, configurations, equations, appearance, coordinate systems, scale/move-copy/delete body, combine bodies, and Insert Part have live evidence.
- **M3 (surfaces)** — 14 rows: 12 current_live and 2 blocked (Standard and Mutual Trim Surface). Planar/extrude/revolve/offset/loft/sweep/filled/knit/ruled/extend surface, thicken, and cut with surface have live evidence.

Combined, the currently recorded M1/M2/M3 requirements contribute 71 rows,
67 of them current_live; `M1.1-k` is absent by API, while `M2.4-f` Split and
`M3-m`/`M3-n` Trim are blocked in the tested COM workflows. This count is **not** the
coverage of every command in the Parts plan: additional M2/M3 functionality
still needs implementation and its own unit/live evidence (see below).

### Remaining

| ID | Capability | Tool | Status | One-line reason |
|---|---|---|---|---|
| B20 | Fast / detailed traversal for large assemblies | `list_components` | partial | `list_components` has only the detailed mode; on a 77-instance assembly it takes ~124 s at `depth=32` while `depth=1` takes 0.17 s. Backlog item; plan and measurements in `docs/upgrade/PERFORMANCE-LARGE-ASSEMBLIES.md`. |
| 5.1 | Create static study | `create_static_study` | absent | Simulation / analysis is intentionally deferred. |
| 5.3 | Apply fixed fixture | `apply_fixed_fixture` | absent | Simulation / analysis is intentionally deferred. |
| 5.4 | Apply force load | `apply_force_load` | absent | Simulation / analysis is intentionally deferred. |
| 5.5 | Run analysis | `run_analysis` | absent | Simulation / analysis is intentionally deferred. |
| 5.6 | Read stress results | `get_stress_results` | absent | Simulation / analysis is intentionally deferred. |
| B19 | Pack and Go / independent copy | `pack_and_go` | blocked | Register marks it `blocked` / `failed`; deliberately not attempted. |
| M2.4-f | Split body | `split_body` | blocked | `PreSplitBody2` reports both halves, but `PostSplitBody2` does not create a Split feature with pywin32; see `docs/api-findings.md` §54. |
| M3-m / M3-n | Trim Surface Standard / Mutual | `trim_surface` | blocked | Both `PreTrimSurface` modes return True, but `PostTrimSurface` creates no feature and changes no sheet area; see `docs/api-findings.md` §56. |

The register has no `partial` implementation status as of 2026-09-24. `B18`
(`save_document`) is now `registered` with `current_live` verification; the
registered MCP tool exists next to the older automation method. `5.2`
(`apply_material`) was previously listed as remaining and is now delivered
(`registered`, `current_live`) — material assignment only, without a Simulation
study.

### Priority order for the next work (as of 2026-09-24)

1. **PART extensions (active)** — continue the unfinished M2/M3 commands in
   `docs/upgrade/PARTS-COVERAGE-PLAN.md`: Save Bodies,
   curve/sketch/table/fill patterns, additional Fillet/Chamfer/Hole Wizard
   modes, Wrap/Intersect/Thread, and Boundary/Untrim/Replace/Delete/
   Flatten Surface. Each new supported mode needs a separate geometric live
   test. Reference Point, Split and both Trim Surface modes remain blocked
   in the tested COM workflows (`docs/api-findings.md` §§42, 54, 56). The 21 M2 and 14 M3 rows above are only the
   capabilities already entered in the requirement register.
2. **DRAWING (done)** — `4.8` (`add_drawing_dimension`) and the `D1`
   marked-vs-unmarked dimension filter are both implemented and live-verified
   (`docs/api-findings.md` §§57–58). `insert_marked_dimensions` was corrected to
   use `IDrawingDoc.InsertModelAnnotations4`, which actually filters; the
   earlier `InsertModelDimensions(32768)` imported every dimension. The
   remaining drawing items in the Parts plan are BOM tables, tolerances,
   datums and surface finish.
3. **PRODUCTION (done)** — `6.3` bounded traversal is registered and
   live-verified: `inspect_document` (depth 1..32, page_size 1..500),
   `inspect_feature_tree(max_depth)` and `list_components(depth)` all stop at
   the requested depth, and paging returns a `next_cursor` until the last page.
   See `docs/upgrade/research-bounded-traversal-6.3.md`. The only optional
   follow-up is live evidence for the still-`static_only` foundation tools
   `1.3` (`set_units`), `1.4` (`get_solidworks_info`) and `6.1`
   (`connect_solidworks`).
4. **LARGE ASSEMBLIES (backlog, `B20`)** — add a fast and a detailed mode to
   `list_components`. On a real 77-instance assembly `depth=32` costs ~124 s
   while `depth=1` costs 0.17 s, because every COM member on a nested component
   costs ~0.08 s. The fast mode should read only `Name2`/`GetPathName` and
   recurse only into `.SLDASM` children (identifying sub-assemblies by path, not
   by the expensive `GetChildren` call). Measurements, design and guidance for
   choosing a mode are in `docs/upgrade/PERFORMANCE-LARGE-ASSEMBLIES.md`.
5. **SIMULATION (Phase 5)** — `5.2` (`apply_material`) is implemented and live,
   but the study workflow `5.1`, `5.3`–`5.6` stays explicitly deferred and out
   of the active plan.
6. **BLOCKED** — `B19` (`pack_and_go`), `M2.4-f` (`split_body`) and
   `M3-m`/`M3-n` (`trim_surface`) remain blocked/failed. Do not retry their
   COM calls without a different approach.

Live COM verification is this project's definition of done: a capability counts
as delivered only once the registered tool has been exercised against
SolidWorks and the evidence is recorded in `scripts/capability_requirements.json`.
After a change, run the focused live test and the appropriate unit regression
suite; re-run broader live tests when shared model state or behavior changes.

## 12.4 Live verification status

Based strictly on the `verification_status` fields in the generated register
(`docs/upgrade/specs/CAPABILITY-REGISTER.md`, derived from
`scripts/capability_requirements.json`):

- **current_live (118 rows)** — the large majority. It includes Phase 1–3 core geometry (with `3.7`–`3.10` exports/reference plane now live), the Phase 4 assembly block `4.1`–`4.5`, drawing view `4.7`, `4.8` `add_drawing_dimension` and the `D1` marked-dimension filter, `5.2` `apply_material`, production tools `6.3` (bounded traversal) and `6.4`–`6.6`, extensions `B18`, `C`, `D`, `D2`, `E`, `F`, `G`, and every **currently registered** M1/M2/M3 requirement row except `M1.1-k` and blocked `M2.4-f`, `M3-m` and `M3-n`. The Parts plan lists further commands not yet represented by requirement rows.
- **static_only (9 rows)** — implemented but not yet live-verified: `1.1`/`1.2` (internal_only), `1.3` `set_units`, `1.4` `get_solidworks_info`, `1.5-a`/`1.5-b`, `4.6` `create_drawing` (internal_only), `6.1` `connect_solidworks` and `6.2` (internal_only).
- **not_run (7 rows)** - the absent capabilities `5.1`, `5.3`-`5.6` and `M1.1-k`, plus the `partial` backlog item `B20` (fast/detailed traversal for large assemblies; `docs/upgrade/PERFORMANCE-LARGE-ASSEMBLIES.md`).
- **failed (4 rows)** — `B19` `pack_and_go`, `M2.4-f` `split_body` and `M3-m`/`M3-n` `trim_surface` (blocked).

---

# 13. RESOURCES

## 13.1 SolidWorks API Documentation
- [SolidWorks API Help](https://help.solidworks.com/2024/english/api/sldworksapiprogguide/welcome.htm)
- [API Object Model](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks_namespace.html)

## 13.2 MCP Protocol
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/anthropics/mcp-python-sdk)

## 13.3 Python COM
- [pywin32 Documentation](https://pypi.org/project/pywin32/)
- [COM Automation Guide](https://pbpython.com/windows-com.html)

---

# 13.4 Additional Focus Areas (Weldments, Sheet Metal, Cut Lists)

This roadmap (as authored) does not cover Weldments, Sheet Metal, or Cut
Lists. A separate research brief for these areas — driven by actual
end-user workflow (weldment profiles, sheet metal, assembly, drawings/cut
lists) — is tracked in `docs/opus-research-brief.md` on the
`additional-upgrades` branch. Treat it as a parallel extension to Phase 4
(Assembly & Drawing Support) rather than a replacement.

## 13.5 Weldments/Features and Sheet Metal execution backlog (2026-09-25)

This is **planned scope, not a claim of implementation**. The historical
inventory in §12 is a snapshot from 24 September; for current, per-capability
live evidence use `scripts/capability_requirements.json`. Do not add these
planned rows to its `current_live` set before a registered MCP tool, a focused
unit test and a successful live test exist. The detailed M2/M3 backlog remains
in `docs/upgrade/PARTS-COVERAGE-PLAN.md`.

**Definition of done for each supported mode:** verify the exact SW 2025 COM
signature/selection marks in the installed `sldworks.tlb` and local API help;
write a mock-COM unit test for validation, unit conversion, selection and
failure paths; create a *scratch* part, exercise the public MCP operation,
rebuild and measure the changed body/feature parameter. Merely receiving a
non-null COM return or a feature name is insufficient. Save/close only scratch
documents under the approved output root; leave users' open documents and
global profile/file-location preferences untouched. Where an operation does
not change volume (e.g. cosmetic beads, unfold, bend parameters), compare its
own persistent parameter or physical geometry (bounding box, area, bends,
edge topology, flat pattern) before/after. Record the live evidence and any
failed approach in the register/findings *after* the test, not in advance.
Weldment tests must use installed `.sldlfp` profiles (e.g. DIN IPE or ISO
square tube), not rectangular proxy solids.

### W1–W10: weldments and adjacent part features

`✅` means the **listed base mode** already has live evidence; it does not
cover additional modes on the same row. `⬜` means research/implementation
pending. API names below are leads for V4.1, not validated pywin32 recipes.

| ID | Operation / current coverage | Research lead and separate live proof to request |
|---|---|---|
| W1 | Structural Member ✅ (`create_structural_member`; library profiles, connected frame and separate picket groups) | Tested one connected four-line frame sketch with Custom 50×20 and one three-line picket sketch with Custom 8-mm rod: two features, seven solid bodies. Explicit `corner_type="miter"` on the frame reads back `ApplyCornerTreatment=True` and `CornerTreatmentType=1`; `separate_groups=True` creates one group per disconnected picket. Group connected runs together; split unusually placed segments when necessary. The original single-group default remains intact. Rotation and locate-profile still need separate proof; see `W1.fence`. |
| W2 | Trim/Extend ✅ **miter, zero gap only** (`trim_weldment_members`); **trim/extend to face blocked** | `IFeatureManager.InsertWeldmentTrimFeature2`; local help documents body selection mark 1 and boundary mark 2. Two separate ISO-profile members gave persistent `WeldCornerFeat` and a solid-volume delta above 10 mm³ (`W2.miter`). On a scratch fence, `swEndConditionTrim=4` against the real underside of the top rail returned a proxy but no persistent feature: the short rod stayed at Z=230 mm instead of reaching the Z=275 mm face. This mode is **not exposed**; record a UI macro for selection/corner details before retrying (`W2.face`). Butt, nonzero gap and cut-list effects remain unverified. Do not confuse with blocked **surface** Trim in M3. |
| W3 | End Cap ✅ (`create_weldment_end_cap`) | `InsertEndCapFeature3` (selection based, 10 args) is the only variant that sets the thickness direction; `InsertEndCapFeature2` (faces array) always caps outward. On a hollow ISO square-tube member the tool caps both auto-detected end faces or named `list_planar_faces` indices, and `direction` picks the side of the end face: `outward` protrudes, `inward` (default) is flush and shortens the member, `inset` recesses by `inset_mm`. Caps become their own bodies, so the live proof sums the whole document volume (added 1683–3020 mm³ for a 5 mm cap); a persistent `EndCap` feature is required. See `W3.endcap`. |
| W4 | Gusset ✅ (`create_weldment_gusset`) | `InsertGussetFeature3` (selection based, 20 args) uses the two supporting faces from the current selection at mark 1; `InsertGussetFeature2` (faces array) created no feature in any of eight probed combinations. The fixture must be a **T-joint**: the through member continues past the joint so the through member's face and the butting member's near face share a real edge; a corner where both members stop at the same point has no shared edge and no gusset. Triangle/polygon profile, thickness side (inner/both/outer), profile location, legs, angles, offset and the weld-bead chamfer are all exposed. The gusset is its own body, so the live proof sums the whole document volume (1562.5 mm³ for 25×25×5). Confirmed against the user's manually built Part200. See `W4.gusset`. |
| W5 | Weld Bead ✅ **cosmetic, weld-path only** (`create_cosmetic_weld_bead`); modelled fillet bead blocked | `InsertCosmeticWeldBead2` in weld-path mode (mode 1) takes a path of edges from `list_body_edges` and creates a persistent `CosmeticWeldBead` in the Weld Folder; it adds no material, so the proof is the feature plus the recorded weld-folder total length (and an asserted zero volume change), never a volume delta. Weld-geometry mode (two face sets, marks 4/8) welded only one intersection edge per call, and the modelled fillet bead was not created in seven probed combinations, so it stays blocked until a UI macro is recorded. See `W5.bead`. |
| W6 | Extruded Boss ✅ (`extrude_sketch`) | Existing blind mode is not every end condition: investigate mid-plane, two directions and up-to-reference separately; verify target thickness/volume and direction. |
| W7 | Extruded Cut ✅ (`cut_extrude`) | Investigate blind/through-all/normal cut and direction individually; measure removed volume and resulting openings rather than just COM status. |
| W8 | Hole Wizard ✅ (straight blind ANSI metric only) | `hole_wizard`: counterbore, countersink, straight/pipe tap, slots, Through All and multiple positions are **not** implied by existing evidence. For each accepted mode verify hole topology, standard/size and depth/read-back; do not simulate a threaded hole with a plain cylinder. |
| W9 | Chamfer ✅ (one angle–distance edge) | `chamfer_edges`: distance–distance, vertex and multiple edges each need a distinct geometry/angle test; measure removed material. |
| W10 | Reference Geometry ✅ (axis and plane, basic modes) | `create_reference_axis` and `create_reference_plane` exist. Investigate alternative reference combinations individually; verify transform/direction and use the reference in a dependent feature. |

**Execution order:** W3/W4 done → W5 once the bead representation is decided;
remaining W2 modes (butt, nonzero gap, cut list) when a UI macro is
recorded. W6–W10 are *mode-completion* work, not requests to
re-implement their proven base tools. Log blocked COM modes honestly and stop
after repeated identical failures rather than cycling signatures blindly.

### S1–S26: sheet-metal candidate operations

This numbered worklist covers 26 **toolbar operations** from the official
SOLIDWORKS 2025 Sheet Metal Toolbar list (27 entries). **Stamp**, new in 2025,
is an explicit additional research item below, not quietly counted as
implemented or dropped. `Base-Flange/Tab` is one toolbar entry; the existing
`export_flat_pattern` is a separate MCP workflow, not a toolbar entry.
`Break-Corner/Corner-Trim` is one toolbar entry, distinct from `Corner Trim`
on a flattened part. These are scope conventions for this plan, not a claim
that the user's original count necessarily excluded Stamp. The exact callable
API and viable input topology for ⬜ rows remain research questions.
Prerequisite for all bending
tests: known thickness, bend radius and K-factor/bend allowance, with the
folded *and* flat-pattern extents recorded. Gauge-table support is an
additional parameter-mode investigation, not a proven option of the current
base-flange tool.

| ID | Operation / current state | Candidate route and measurable live acceptance |
|---|---|---|
| S1 | Base-Flange/Tab ✅ **base flange only** (`create_sheet_metal_base_flange`) | `InsertSheetMetalBaseFlange` path has live evidence; sketch-on-face tab and bend-allowance modes still need separate area/thickness and developed-outline proofs. Do not confuse Tab with S22. |
| S2 | Edge Flange ✅ (`create_edge_flange`) | 20 mm flange on the 100 mm edge of a 100×50×1 mm base-flange plate added **2135.6 mm³** and took the sheet from 6 to 14 faces with the body count unchanged at 1; 45° gave 2076.4 mm³ and `bend_radius_mm=5` (which clears `swInsertEdgeFlangeUseDefaultRadius` so the argument is read) gave 2363.9 mm³. Route: `IModelDoc2.InsertSketchForEdgeFlange` → `EditSketch` + `SketchUseEdge` + three lines closing the bend line into the same four-line rectangle SolidWorks itself stores (read from the absorbed profile sketch of a hand-made flange) → `IFeatureManager.InsertSheetMetalEdgeFlange2`. **Only `swFlangePositionTypeBendOutside` (3) builds through the API**: material-inside/outside, bend-centerline, bend-sharp and bend-tangent all returned no feature. `CreateDefinition(swFmEdgeFlange=37)` + `IEdgeFlangeFeatureData.AddEdges` returned `swEdgeFlangeError_EdgeNotSpecified` (1) with `GetEdgeCount` 0 for every marshalling and edge source tried. One edge per call: two and three edges at once, and `swInsertEdgeFlangeFlipDir`, are **not exposed**. See `S2.eflange`. |
| S3 | Miter Flange ✅ **single-edge, four-line profile** (`create_miter_flange`) | `IFeatureManager.InsertSheetMetalMiterFlange` works when **both** the straight sheet edge and a closed, real four-segment profile sketch are selected (edge `Select4(False)`, sketch `Select2(True, 0)`); selecting only one returns NULL. On a 100×50×1 mm plate, a Right-Plane open path from the back top edge gives four `SketchBend` sub-features, 5000→6990.607 mm³, 6→38 faces, one body. An earlier false-negative was caused by a coordinate-transform spike that silently supplied `(0,0)` for every line: `CreateLine2` returned NULL four times and the empty sketch disappeared. Only this profile/default gap-radius-position combination is exposed; joined edges, alternate profiles and flat outline still need separate live proofs. |
| S4 | Swept Flange ⬜ | `ISweptFlangeFeatureData` exists locally, but creation entry point unverified; find via TLB/macro, then verify swept wall and flat pattern. |
| S5 | Hem ⬜ | Local help: `IFeatureManager.InsertSheetMetalHem2`; test open/closed hem separately; measure folded rim and developed length. |
| S6 | Jog ⬜ | Local help: `IModelDoc2.InsertSheetMetalJog`; verify offset and two bends at unchanged sheet thickness. |
| S7 | Sketched Bend ⬜ | `IFeatureManager.InsertSheetMetal3dBend` exists; its mapping to the toolbar command/selection is **unconfirmed**. Verify bend angle and displaced face orientation. |
| S8 | Lofted-Bend ⬜ | Local help: `IFeatureManager.InsertSheetMetalLoftedBend2`; start from two open profiles (not an existing base flange) and verify section geometry and flat pattern. |
| S9 | Convert to Sheet Metal ⬜ | Local help: `IFeatureManager.InsertConvertToSheetMetal2`; verify conversion of a valid solid/surface and read back acquired sheet-metal parameters plus flat pattern. |
| S10 | Insert Bends ⬜ | No verified creation entry point; record a macro for a suitable constant-thickness part; measure bends and developed shape. |
| S11 | Rip ⬜ | Local help: `IModelDoc2.InsertRip`; verify selected edges, gap width and newly open edges. |
| S12 | Bend Notch ⬜ | 2025 toolbar operation; no dedicated method verified in local API extract. Macro-record first; measure notch depth/width on the flat pattern. |
| S13 | Closed Corner ⬜ | Local help: `IModelDoc2.InsertSheetMetalClosedCorner`; measure changed gap/overlap at adjacent flanges. |
| S14 | Break-Corner/Corner-Trim ⬜ | Local help: `IModelDoc2.InsertSheetMetalBreakCorner`; check whether both UI modes map to this API and test each accepted mode's edge/corner geometry. |
| S15 | Corner Trim (flattened) ⬜ | Local help: `IFeatureManager.InsertSheetMetalCornerTrim`; on a flat sheet verify relief/corner outline and removed material. Distinct from S14. |
| S16 | Corner Relief ⬜ | Separate creation API not verified; documented example uses Edge Flange. Investigate independent route/macros, then compare relief area/shape in developed part. S2 may be prerequisite. |
| S17 | Sheet Metal Gusset ⬜ | Local help: `IFeatureManager.InsertSheetMetalGussetFeature3`; verify gusset thickness and geometry; distinct from W4 weldment gusset. |
| S18 | Cross-Break ⬜ | Local help: `IFeatureManager.InsertCrossBreak`; read break angle/radius and observe crease geometry; do not require volume delta for a graphic break. |
| S19 | Forming Tool ⬜ | `InsertFormToolFeature` appears in local help; signature/placement still unverified. Use a real library forming tool; measure impression and height. |
| S20 | Normal Cut ⬜ | Local help: `AddSMNormalCut` / `AddSMNormalCutType` / `FinishSMNormalCut`; establish their sequence, then measure thickness-normal walls and flat opening. |
| S21 | Welded Corner ⬜ | 2025 toolbar operation distinct from W5; no dedicated API confirmed. Macro-record first; inspect weld size/path and physical versus cosmetic representation separately. |
| S22 | Tab and Slot ✅ (`create_tab_and_slot`), **flat sheets and profiles** | `IFeatureManager.CreateDefinition(swFmTabAndSlot = 88)` → `SelectionAddNewGroup()` → set `SelectionTabEdge`, `SelectionSlotFace`, `TabLength`, `SlotClearance`, `TabHeightType`+`TabHeightValue` (blind), `TabEdgesType`, spacing → `CreateFeature`. The group holds the raw edge and face objects, so no selection marks are used. On two 1 mm sheet-metal plates meeting at a corner a 10×1×6 mm tab grew and a 10.4×1.2×1 mm slot was cut (tab body +60 mm³/−12.48 mm³, +2/+4 faces). On **real weldment profiles** — a Custom 50×50 tube with 2 mm walls and a Custom 30X30 tube standing on it — the butting tube's base rim edge grew a 10×2×2 mm tab that ran from Z=25 down to Z=23, i.e. through the wall and flush with its inner face when `tab_height_mm` is the wall thickness, and cut 45.52 mm³ from the through tube; half the wall left a blind pocket and wall+3 mm reached into the hollow section. `spacing="equal"` with 3 instances gave three tabs and three slots (+180 / −37.44 mm³) and `edge_treatment="fillet"` also worked. The tab's reference face is derived automatically as the face sharing the tab edge that is coplanar with the slot face (on plates the thin rim face, on tubes the end face). `TabFace` on a perpendicular face, or omitted on a tube, never created a feature; `UpToSurface` and `OffsetFromSurface` heights produced no feature and are **not exposed**. `TabThickness` defaults to 1 mm, so pass the wall thickness for a snug fit. See `S22.tabs`. |
| S23 | Unfold (selected bends) ⬜ | Local help: `IModelDoc2.InsertSheetMetalUnfold()` on selected bends; measure flattened selected bends without losing the folded definition. |
| S24 | Fold (selected bends) ⬜ | Local help: `IModelDoc2.InsertSheetMetalFold()`; verify inverse geometry and restoration of pre-unfold extents. |
| S25 | Flatten / refold ✅ (`flatten_sheet_metal`) | Existing Flat-Pattern suppression toggle; compare flat/folded face count and extents; multibody mode remains to test separately. |
| S26 | No Bends ⬜ | 2025 toolbar operation; no verified API entry point. Determine whether feature suppression or a distinct feature is required; verify bendless physical geometry and preserved original bend definition. |

**Outside this 26-row baseline:** `Stamp` appears as a **27th toolbar command
in SOLIDWORKS 2025**, with no verified creation API in the installed CHM
extract. Investigate by recording a macro before deciding whether to add it
to implementation scope. `export_flat_pattern` is already live as a separate
MCP workflow; keep its existing DXF geometry/scale regression, not a duplicate
toolbar row. `get_sheet_metal_info` and `get_flat_pattern_info` are likewise
existing read operations outside the toolbar inventory.

**Priority and dependencies:** S1 → S2 ✅ → S22 ✅ (live 25 September 2026, see
`S2.eflange` and `S22.tabs`). S2 unblocked the bend-dependent row: the flange
itself is proven, and **the lesson is that a dead `CreateDefinition` route does
not mean the feature is impossible** — `CreateDefinition(swFmEdgeFlange)` +
`IEdgeFlangeFeatureData.AddEdges` returned `EdgeNotSpecified` for every marshalling,
while the documented `InsertSheetMetalEdgeFlange2` method call built the flange
once the caller drew the profile it asks for. Try the documented method call
before recording a macro. S2's own scope: **one straight edge per call and
bend-outside only**; multi-edge and `FlipDir` are unexposed, and other
`swFlangePositionTypes_e` values returned no feature (docs/api-findings.md §65).
Next along the bend chain: S3 Miter Flange, S5 Hem, S6 Jog, then the corner rows
S13–S18 which all need a flange to exist first. S22 remaining work is other
profile shapes (rounded rectangular, angle, channel) and a tab on a profile
*side* wall rather than its end face. After that S4/S7–S12/S17–S21/S26, followed
by S23–S25 regression. V4.1's read-only investigation found the local API entry
points above; a separate offline TLB read confirmed the S22 enum value. Before
COM mutation, check each required signature in the local `sldworksapi.chm` and
`sldworks.tlb`. Next, run a guarded scratch-document spike; if repeated calls
fail, stop and report. For S4/S7/S10/S12/S16/S19/S21/S26 (and Stamp), record a
macro or find the feature-data creation path before guessing positional
parameters. This research is **not** live evidence.

**Performance rule (measured on S2, holds for every `part_edges` consumer):**
one body per document. `list_body_edges` on the same fixture cost 0.14 s with one
body, 5.77 s with two and 8.54 s with three — 12 extra edges cost 5.6 s, because
each COM access to the bodies of a multibody document is expensive, not because
of the edge count (`IBody2::GetEdges` is only ~1.8x faster). Building the three
S2 variants in one document took 125 s; one document per test took 47.6 s. Bases
are cheap (~2.8 s) and `create_new_part` is ~1.4 s, so save **edge scans**, not
documents. Keep one document per live test method, and make a test that opens two
documents verify the fresh one is empty, otherwise the earlier document stays
active and the new geometry lands in it (seen as "1 != 2 bodies"). See
docs/api-findings.md §65.6.

Official 2025 research entry points:
[Tab and Slot C# example](https://help.solidworks.com/2025/english/api/sldworksapi/Create_Tab_And_Slot_Example_CSharp.htm),
[Tab and Slot feature data](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ITabAndSlotFeatureData.html),
[Sheet Metal toolbar](https://help.solidworks.com/2025/english/solidworks/sldworks/r_Sheet_Metal_Toolbar.htm),
[Trim/Extend API](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~InsertWeldmentTrimFeature2.html),
[Weldment feature example](https://help.solidworks.com/2025/English/api/sldworksapi/Insert_Weldment_Features_Example_CSharp.htm).

---

# 14. VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 2.3 | Jan 2026 | Historical baseline - 11 tools (see §12 for current state) |
| 3.0 | Target | 55+ tools, full CAD support |

---

**END OF ROADMAP**

*Last Updated: 24 September 2026 (progress sections §7–§12 grounded in `scripts/capability_requirements.json`)*
*Original author: Samsaam Ali Baig. Additional development and progress updates: PksOck.*
