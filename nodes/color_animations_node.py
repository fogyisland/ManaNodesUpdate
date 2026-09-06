"""Preset Color Animations node.

Interpolates one of a few hand-picked color palettes across `duration`
frames and emits the result in the same wire format as Scheduled Values
(so Font Properties can parse it transparently).
"""
from __future__ import annotations

import json
from typing import Sequence

# Animation modes are shared with Scheduled Values; we keep them as a
# module constant so adding a mode touches one place.
_ANIMATION_RESET_MODES: tuple[str, ...] = ("word", "line", "never", "looped", "pingpong")

# Each preset is a list of (r, g, b) stops; intermediate frames are
# linearly interpolated. Add more here to grow the palette.
_COLOR_PRESETS: dict[str, Sequence[tuple[int, int, int]]] = {
    "rainbow": [(255, 0, 0), (255, 165, 0), (255, 255, 0),
                (0, 255, 0), (0, 0, 255), (75, 0, 130), (238, 130, 238)],
    "sunset":  [(255, 76, 0), (255, 108, 0), (255, 139, 0), (255, 171, 0), (255, 203, 0)],
    "grey":    [(50, 50, 50), (100, 100, 100), (150, 150, 150), (200, 200, 200), (250, 250, 250)],
    "ocean":   [(0, 0, 255), (0, 0, 200), (0, 0, 150), (0, 0, 100), (0, 0, 50)],
    "forest":  [(0, 100, 0), (34, 139, 34), (46, 139, 87), (60, 179, 113), (85, 107, 47)],
    "fire":    [(255, 0, 0), (255, 69, 0), (255, 99, 71), (255, 140, 0), (255, 165, 0)],
    "sky":     [(135, 206, 235), (135, 206, 250), (70, 130, 180), (100, 149, 237), (240, 248, 255)],
    "earth":   [(101, 67, 33), (139, 69, 19), (160, 82, 45), (165, 42, 42), (210, 105, 30)],
}
_DEFAULT_PRESET = "rainbow"
_BLACK = ((0, 0, 0),)


class color_animations:
    """Animate a hand-picked RGB palette across N frames."""

    DESCRIPTION = "Mana Nodes — preset color animations. Cycle through rainbow, sunset, sky, ocean, etc. Try searching: mana, color, palette, rainbow, gradient."

    CATEGORY = "💠 Mana Nodes/📅 Value Scheduling"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("scheduled_colors",)
    FUNCTION = "run"

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "color_preset": (
                    list(_COLOR_PRESETS.keys()),
                    {"default": _DEFAULT_PRESET, "display": "dropdown"},
                ),
                "animation_duration": ("INT", {"default": 30, "step": 1, "display": "number"}),
                "animation_reset": (
                    list(_ANIMATION_RESET_MODES),
                    {"default": "word", "display": "dropdown"},
                ),
            }
        }

    def run(self, color_preset: str, animation_duration: int, animation_reset: str, **_):
        schedule = self._build_schedule(color_preset, animation_duration)
        return (f"{json.dumps(schedule)}${animation_reset}",)

    @staticmethod
    def _build_schedule(preset: str, duration: int) -> list[dict]:
        colors = _COLOR_PRESETS.get(preset, _BLACK)
        if duration <= 0:
            return []

        n_colors = len(colors)
        last_idx = n_colors - 1
        out: list[dict] = []
        for i in range(duration):
            # t in [0, 1] walks the palette from start to end.
            t = i / max(duration - 1, 1)
            pos = t * last_idx
            idx = int(pos)
            nxt = min(idx + 1, last_idx)
            frac = pos - idx
            r, g, b = colors[idx]
            rn, gn, bn = colors[nxt]
            out.append({
                "x": i + 1,
                "y": [
                    int((1 - frac) * r + frac * rn),
                    int((1 - frac) * g + frac * gn),
                    int((1 - frac) * b + frac * bn),
                ],
            })
        return out
