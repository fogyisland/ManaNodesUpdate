"""Keyframe / animation helpers used by the Text to Image node.

A "scheduled value" is a list of {x, y} dicts (one per keyframe). A
"reset mode" controls how the timeline behaves when the visible text
changes (`word`, `line`, `never`, `looped`, `pingpong`).

The same JSON+'$'-suffix wire format is used by:
    - Scheduled Values node
    - Preset Color Animations node
    - Font Properties `scheduled_values` input

so we centralize parsing/serialization here.
"""
from __future__ import annotations

import json
from typing import Iterable, List, Sequence, Tuple

# A scheduled value is a list of (frame, value) pairs.
Keyframe = Tuple[int, object]
Schedule = List[dict]


# --------------------------------------------------------------------------- #
# Parsing / serialization                                                     #
# --------------------------------------------------------------------------- #
def parse_scheduled_string(raw: str) -> tuple[list | dict, str | None]:
    """Parse a "JSON$animation_reset" string.

    Returns (schedule, animation_reset). The schedule is whatever the
    JSON head parsed to:
      - list of {x, y} dicts (the output of Scheduled Values /
        Preset Color Animations)
      - dict mapping property name -> list (advanced per-property input)
      - empty list when the input is empty / unparseable
    """
    if not raw or raw == "{}":
        return [], None
    if "$" in raw:
        head, _, tail = raw.partition("$")
        reset = tail or None
    else:
        head, reset = raw, None
    try:
        data = json.loads(head)
    except (json.JSONDecodeError, TypeError):
        return [], reset
    if not isinstance(data, (list, dict)):
        return [], reset
    return data, reset


def serialize_scheduled_string(keyframes: Sequence[dict], animation_reset: str | None) -> str:
    """Inverse of parse_scheduled_string."""
    return f"{json.dumps(list(keyframes))}${animation_reset or ''}"


# --------------------------------------------------------------------------- #
# Sequence math                                                                #
# --------------------------------------------------------------------------- #
def parse_animation_duration(anim: Sequence[dict] | object) -> int:
    """Highest x-value in a keyframe list, or 1 for a constant value."""
    if isinstance(anim, list) and anim:
        return max(item["x"] for item in anim)
    return 1


def _pingpong_position(current: int, duration: int) -> int:
    if duration <= 1:
        return 0
    cycle = duration * 2 - 2
    pos = current % cycle
    return cycle - pos if pos >= duration else pos


def sequence_frame(current_frame: int, start_frame: int, duration: int, reset_mode: str) -> int:
    """Where in the schedule should we sample for `current_frame`?

    Mirrors the JS implementation in scheduled_values.js.
    """
    if reset_mode in ("word", "line"):
        active = (current_frame - start_frame) < duration
        return (current_frame - start_frame) + 1 if active else duration
    if reset_mode == "never":
        return current_frame + 1 if current_frame <= duration else duration
    if reset_mode == "looped":
        return (current_frame % duration) + 1
    if reset_mode == "pingpong":
        return _pingpong_position(current_frame, duration)
    return 1


def value_at(schedule: Iterable[dict], sequence_frame_number: int, default=None):
    """Look up the value at a given sequence frame.

    Hold-style interpolation: returns the value of the most recent
    prior keyframe, or the first keyframe's value if the requested
    frame is before all keyframes, or the last keyframe's value if
    the requested frame is past every keyframe. This matches the
    behavior the JS frontend uses in `scheduled_values.js`
    `generateInBetweenValues` after the user has already expanded
    the schedule by clicking 'Generate Values'.

    Note: we deliberately do NOT linearly interpolate here. The JS
    side already pre-interpolates the schedule on the chart; if the
    Python side also interpolated, the easing applied by the user
    would be applied twice (once in JS, once in Python). Hold is
    also what `parse_scheduled_string` callers rely on for the
    most-recent-prior semantics that reset modes like `word` /
    `line` depend on.

    Returns `default` when the schedule is empty.
    """
    items = list(schedule) if not isinstance(schedule, list) else schedule
    if not items:
        return default
    items.sort(key=lambda d: d.get("x", 0))

    # Frame is at or past the last keyframe: hold the last value.
    last_x = items[-1].get("x", 0)
    if sequence_frame_number >= last_x:
        return items[-1].get("y", default)

    # Frame is at the first keyframe.
    first_x = items[0].get("x", 0)
    if sequence_frame_number <= first_x:
        return items[0].get("y", default)

    # Frame is between two keyframes: find the latest prior keyframe
    # by scanning in order (the list is already sorted by x above).
    for i in range(len(items) - 1):
        cur_x = items[i].get("x", 0)
        nxt_x = items[i + 1].get("x", 0)
        if cur_x <= sequence_frame_number < nxt_x:
            return items[i].get("y", default)

    # Unreachable: the schedule covers [first_x, last_x] and we
    # handled both endpoints. If we got here, fall back to the
    # last item's value rather than crashing.
    return items[-1].get("y", default)
