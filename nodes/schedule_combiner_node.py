"""Schedule Combiner node.

Fuse N optional `scheduled_values` inputs (each the standard
`JSON-keyframes$reset_mode` wire format emitted by Scheduled Values
and Preset Color Animations) into a single dict-style schedule
string like:

    {"x_offset": [{"x":1,"y":0}, ...],
     "font_color": [{"x":1,"y":[255,0,0]}, ...]}$word

Downstream, Font Properties / Text to Image Generator already know
how to read the dict form — they look each property up by name in
the schedule instead of broadcasting a flat list to every
animatable property. See `text_graphic_element_node.run()`'s
`elif isinstance(keyframes, dict)` branch.

This node exists because ComfyUI widget connections are
single-input: Font Properties' `scheduled_values` widget can only
accept one upstream connection, so without an explicit combiner
the user can't drive `x_offset` from Scheduled Values AND
`font_color` from Preset Color Animations at the same time.

All inputs are optional. Empty / None inputs are silently skipped,
so the node behaves as a pass-through for whichever schedules are
connected — drop in only the inputs you actually need.
"""
from __future__ import annotations

from typing import Optional

from ..helpers.animation import parse_scheduled_string


# Property names the combiner exposes. Each maps to one optional
# STRING input. Keep this list in sync with Font Properties'
# _ANIMATABLE_PROPS + _COLOR_ANIMATABLE_PROPS — anything you add
# here becomes a connectable input on this node.
_COMBINER_INPUTS = (
    ("x_offset", "STRING"),
    ("y_offset", "STRING"),
    ("font_size", "STRING"),
    ("rotation", "STRING"),
    ("kerning", "STRING"),
    ("border_width", "STRING"),
    ("shadow_offset_x", "STRING"),
    ("shadow_offset_y", "STRING"),
    ("rotation_anchor_x", "STRING"),
    ("rotation_anchor_y", "STRING"),
    ("font_color", "STRING"),
    ("border_color", "STRING"),
    ("shadow_color", "STRING"),
)


class schedule_combiner:
    """Merge multiple property-specific schedules into a dict schedule."""

    DESCRIPTION = (
        "魔力节点 — 调度值合并。把多个 scheduled_values 输入合并成一个字典形式的 "
        "schedule，按属性名精确驱动 Font Properties 的动画字段。"
        "比如同时让 x_offset 从 Scheduled Values 走、font_color 从 Preset Color Animations 走。"
        " Mana Nodes — schedule combiner. Merge multiple scheduled_values inputs into a "
        "single dict-form schedule, keyed by property name. Lets you drive x_offset "
        "from Scheduled Values and font_color from Preset Color Animations at the same "
        "time without one overwriting the other. Try searching: mana, combine, schedule, "
        "merge, multi-property."
    )

    CATEGORY = "💠 Mana Nodes/📅 Value Scheduling"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("scheduled_values",)
    FUNCTION = "run"

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls):
        # One optional STRING input per property name. Default value
        # is empty so the input sits blank until the user connects
        # something — an empty string means "skip this property".
        optional = {}
        for prop_name, _type in _COMBINER_INPUTS:
            optional[prop_name] = ("STRING", {
                "default": "",
                "display": "text",
                "forceInput": True,
            })
        return {"required": {}, "optional": optional}

    @staticmethod
    def _parse_one(raw: Optional[str]):
        """Parse a single `JSON-keyframes$reset_mode` string.

        Returns (keyframes_list, reset_mode) on success, or
        (None, None) for empty / unparseable input. The reset_mode
        of the FIRST non-empty input is used as the dict's reset
        mode — callers in practice pick the same mode on every
        upstream node, so this is just a convenience.
        """
        if not raw or not str(raw).strip():
            return None, None
        try:
            keyframes, reset = parse_scheduled_string(str(raw))
        except Exception:
            return None, None
        if not keyframes:
            return None, None
        if not isinstance(keyframes, list):
            # Dict-shaped input on a single property — uncommon but
            # pass it through; Font Properties will treat it as a
            # schedule for *this* property, not a multi-prop dict.
            keyframes = [keyframes]
        return keyframes, reset

    def run(self, **kwargs):
        merged: dict = {}
        chosen_reset: Optional[str] = None

        for prop_name, _ in _COMBINER_INPUTS:
            raw = kwargs.get(prop_name)
            keyframes, reset = self._parse_one(raw)
            if keyframes is None:
                continue
            merged[prop_name] = keyframes
            if chosen_reset is None and reset:
                chosen_reset = reset

        # Empty combiner (no inputs connected): emit the same
        # empty-schedule sentinel Font Properties already knows to
        # ignore. Don't raise — the user might be still wiring up.
        if not merged:
            return ("",)

        # Re-serialise using the same wire format the rest of the
        # pipeline speaks: JSON dict + '$' + reset_mode.
        import json
        head = json.dumps(merged, separators=(",", ":"))
        tail = f"${chosen_reset}" if chosen_reset else ""
        return (f"{head}{tail}",)


__all__ = ["schedule_combiner"]
