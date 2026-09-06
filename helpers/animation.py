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
def parse_scheduled_string(raw: str) -> tuple[Schedule, str | None]:
    """Parse a "JSON-list$animation_reset" string.

    Returns (keyframes, animation_reset). The animation_reset is None
    when the user wrote the schedule by hand without the suffix.
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
    if not isinstance(data, list):
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
    """Look up the value at a given sequence frame, or the most-recent prior one."""
    items = list(schedule) if not isinstance(schedule, list) else schedule
    if not items:
        return default
    by_x = {item["x"]: item["y"] for item in items}
    if sequence_frame_number in by_x:
        return by_x[sequence_frame_number]
    prior = max((x for x in by_x if x <= sequence_frame_number), default=1)
    return by_x.get(prior, items[0]["y"])
