# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Params model + JSON presets. Units mm. Every field needs a default.

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import model_validator

from .serial import JsonModel


class Seating(str, Enum):
    AXIS = "axis"
    FACE = "face"
    PLANE = "plane"


class SkeletonStyle(str, Enum):
    POCKETED = "pocketed"
    HONEYCOMB = "honeycomb"
    RIBBED = "ribbed"
    SOLID = "solid"


class BaseProfile(str, Enum):
    PLAIN = "plain"
    GRIDFINITY = "gridfinity"


class RibPattern(str, Enum):
    GRID = "grid"
    DIAGONAL = "diagonal"
    HEX = "hex"


class CellShape(str, Enum):
    """Honeycomb void cell shape."""
    HEX = "hex"
    TRIANGLE = "triangle"
    SQUARE = "square"
    ROUND = "round"


class DivotShape(str, Enum):
    SCALLOP = "scallop"
    ROUND = "round"
    SQUARE = "square"
    RECT = "rect"
    U_CHANNEL = "u_channel"


class DivotStrategy(str, Enum):
    PERIMETER = "perimeter"
    SHARED_WEB = "shared_web"
    ALL = "all"


class PackMode(str, Enum):
    BBOX = "bbox"          # pitch from rotated bbox
    HULL = "hull"          # pitch from nearest-point gap, lets L/V/^ nest


class DivotAxis(str, Enum):
    X = "X"
    Y = "Y"


class DivotSide(str, Enum):
    POS = "pos"
    NEG = "neg"


class PushHoleShape(str, Enum):
    ROUND = "round"
    SLOT = "slot"


class PinStyle(str, Enum):
    TAPER = "taper"
    PIN = "pin"


class Closure(str, Enum):
    NONE = "none"
    SCREW = "screw"


class SandwichMode(str, Enum):
    CLAMSHELL = "clamshell"      # full close, taper pins
    STACKING = "stacking"        # big gap, separate pins


class ExportFormat(str, Enum):
    STL = "stl"
    STEP = "step"          # B-rep only
    MM3 = "3mf"            # B-rep only


class LabelMode(str, Enum):
    DEBOSS = "deboss"
    EMBOSS = "emboss"
    NONE = "none"


class LabelPlace(str, Enum):
    TOP = "top"
    FRONT = "front"
    FRONT_FACE = "front_face"


class Axis(str, Enum):
    X = "X"
    Y = "Y"
    Z = "Z"


class CaptureQuality(str, Enum):
    """Heightmap raster pitch (mm/pixel)."""
    DRAFT = "draft"        # 0.2 mm
    NORMAL = "normal"      # 0.1 mm
    FINE = "fine"          # 0.05 mm


class Params(JsonModel):
    """All generation parameters; flat JSON."""

    model_config = {"use_enum_values": True, "validate_assignment": True,
                    "validate_default": True}

    seating: Seating = Seating.AXIS
    seating_axis: Axis = Axis.Z
    seating_normal: Optional[List[float]] = None  # FACE/PLANE down normal
    flip: bool = False
    # part lean and tray angle, independent
    part_lean_deg: float = 0.0
    part_lean_axis: Axis = Axis.X
    tray_angle_deg: float = 0.0
    tray_angle_axis: Axis = Axis.X
    tilt_back_wall: bool = True

    hold_height: float = 8.0
    bottom_margin: float = 2.0
    part_clearance: float = 0.25
    mouth_chamfer: float = 1.2
    capture_quality: CaptureQuality = CaptureQuality.NORMAL
    # CAVEAT: flattens load-bearing internal plateaus too, don't enable for those
    min_internal_feature: float = 0.0    # min recess width to remove mm, 0 = keep
    remove_internal_features: bool = True
    internal_wall_floor: float = 0.0     # floor left under removed recesses, mm
    min_island_area: float = 0.5         # mm^2

    rows: int = 3
    cols: int = 3
    part_spacing: float = 5.0
    part_spacing_x: Optional[float] = None  # per-axis gap, None = part_spacing
    part_spacing_y: Optional[float] = None  # may be negative, nest L/V/^ parts
    pack_mode: PackMode = PackMode.BBOX
    pitch_x: Optional[float] = None      # overrides spacing
    pitch_y: Optional[float] = None
    row_stagger: float = 0.0             # 0..1
    pocket_rotate: bool = False
    pocket_rotate_deg: float = 180.0     # uniform Z-rotation, all pockets
    fit_to_bed: bool = False
    bed_x: Optional[float] = None
    bed_y: Optional[float] = None
    border: float = 15.0
    # advanced per-side margins, None = fall back to border
    margin_advanced: bool = False
    margin_x: Optional[float] = None       # left/right X
    margin_y: Optional[float] = None       # back +Y
    margin_front: Optional[float] = None   # front -Y, label/divot face
    drawer_pack_gap: float = 5.0           # gap between packed parts

    skeleton_style: SkeletonStyle = SkeletonStyle.RIBBED
    rim_width: float = 2.0
    wall_thickness: float = 2.0
    web_floor: float = 1.2
    lightening_through: bool = True
    outside_lightening: bool = True
    outside_wall: float = 4.0            # mm
    outside_rim: float = 3.0             # mm
    honeycomb_cell: float = 10.0
    honeycomb_wall: float = 1.2
    cell_shape: CellShape = CellShape.HEX
    rib_width: float = 0.8
    rib_spacing: float = 12.0
    rib_pattern: RibPattern = RibPattern.DIAGONAL
    base_profile: BaseProfile = BaseProfile.PLAIN
    magnet_holes: bool = False
    magnet_dia: float = 6.0
    bed_split: bool = False
    corner_fillet: float = 10.0          # mm; 0 = sharp
    edge_chamfer: float = 2.0            # mm; 0 = sharp
    stacking_feet: bool = False
    vent_holes: bool = True

    finger_divot: bool = True
    divot_count: int = 2                 # 1 or 2
    divot_shape: DivotShape = DivotShape.SCALLOP
    divot_diameter: float = 17.0
    divot_depth: float = 5.0             # < hold_height
    divot_chamfer: float = 1.2           # mm; 0 = sharp
    divot_axis: DivotAxis = DivotAxis.X
    divot_side: DivotSide = DivotSide.POS
    divot_offset: float = 0.0            # mm
    divot_angle: Optional[float] = None  # deg override
    divot_strategy: DivotStrategy = DivotStrategy.ALL
    push_hole: bool = True
    push_min_size: float = 20.0          # mm
    push_hole_diameter: float = 25.0
    push_hole_shape: PushHoleShape = PushHoleShape.ROUND
    push_hole_countersink: bool = True

    two_sided: bool = False
    two_sided_mode: SandwichMode = SandwichMode.CLAMSHELL
    top_hold_height: Optional[float] = None  # None = 50% of hold_height
    grip_gap: float = 0.2                # neg = friction hold
    pin_count: int = 4
    pin_diameter: float = 4.0
    pin_clearance: float = 0.15
    pin_depth: float = 6.0
    pin_style: PinStyle = PinStyle.TAPER
    pin_taper: bool = True
    pin_tip_ratio: float = 0.5
    pin_on: str = "bottom"
    # stacking pins, holes both halves, separate dowel model
    stack_pins: bool = True
    stack_pin_diameter: float = 5.0
    stack_pin_clearance: float = 0.2
    stack_pin_length: float = 16.0       # max printed dowel length (caps reach)
    stack_pin_hole_depth: float = 8.0    # blind hole depth per half
    closure: Closure = Closure.NONE
    screw_dia: float = 3.0
    screw_boss: float = 6.0

    export_format: ExportFormat = ExportFormat.STL
    tess_linear: float = 0.05            # mm
    tess_angular: float = 0.5            # deg
    label_text: str = ""                 # blank = derive from part name
    label_mode: LabelMode = LabelMode.DEBOSS
    label_place: LabelPlace = LabelPlace.TOP
    pocket_index: bool = False
    pocket_index_start: int = 1
    name_pattern: str = "{part}_{rows}x{cols}"

    @model_validator(mode="after")
    def _clamp(self) -> "Params":
        """Clamp degenerate inputs to safe minimums."""
        def _set(name, val):
            if getattr(self, name) != val:
                object.__setattr__(self, name, val)
        _set("rows", max(1, int(self.rows)))
        _set("cols", max(1, int(self.cols)))
        _set("hold_height", max(0.1, float(self.hold_height)))
        _set("bottom_margin", max(0.0, float(self.bottom_margin)))
        _set("part_clearance", max(0.0, float(self.part_clearance)))
        _set("part_spacing", max(0.0, float(self.part_spacing)))
        _set("drawer_pack_gap", max(0.0, float(self.drawer_pack_gap)))
        _set("border", max(0.0, float(self.border)))
        _set("min_island_area", max(0.0, float(self.min_island_area)))
        _set("divot_diameter", max(0.1, float(self.divot_diameter)))
        _set("divot_chamfer", max(0.0, float(self.divot_chamfer)))
        _set("internal_wall_floor", max(0.0, float(self.internal_wall_floor)))
        _set("outside_wall", max(0.0, float(self.outside_wall)))
        _set("outside_rim", max(0.0, float(self.outside_rim)))
        _set("pin_diameter", max(0.1, float(self.pin_diameter)))
        _set("part_lean_deg", max(-45.0, min(45.0, float(self.part_lean_deg))))
        _set("tray_angle_deg", max(-45.0, min(45.0, float(self.tray_angle_deg))))
        _set("stack_pin_diameter", max(0.1, float(self.stack_pin_diameter)))
        _set("stack_pin_clearance", max(0.0, float(self.stack_pin_clearance)))
        _set("stack_pin_length", max(1.0, float(self.stack_pin_length)))
        _set("stack_pin_hole_depth", max(0.5, float(self.stack_pin_hole_depth)))
        if self.top_hold_height is not None:
            _set("top_hold_height", max(0.5, float(self.top_hold_height)))
        for _m in ("margin_x", "margin_y", "margin_front"):
            if getattr(self, _m) is not None:
                _set(_m, max(0.0, float(getattr(self, _m))))
        if self.pitch_x is not None:
            _set("pitch_x", max(0.1, float(self.pitch_x)))
        if self.pitch_y is not None:
            _set("pitch_y", max(0.1, float(self.pitch_y)))
        return self
