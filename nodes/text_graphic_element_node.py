from ..helpers.animation import parse_scheduled_string
from ..helpers.font_loader import combined_font_list


# Properties that font2img treats as "animatable" — i.e. it expects a
# (value, animation_reset) tuple. When `scheduled_values` is a flat
# keyframe list (the format emitted by Scheduled Values /
# Preset Color Animations), the same list is broadcast to every property
# in this set. Per-property dict input is also supported for advanced use.
_ANIMATABLE_PROPS = (
    "kerning", "border_width",
    "shadow_offset_x", "shadow_offset_y",
    "font_size", "x_offset", "y_offset", "rotation",
    "rotation_anchor_x", "rotation_anchor_y",
)


class text_graphic_element:

    DESCRIPTION = "魔力节点 — 字体属性。定义字体、字号、颜色、描边、阴影、偏移。试试搜索：mana、魔力、字体、排版、文字样式。 Mana Nodes — font properties. Defines font, size, color, border, shadow, and offsets. Try searching: mana, font, typography, text style."

    FONTS = {}
    FONT_NAMES = []

    def __init__(self):
        pass

    # Font discovery is shared with font2img via helpers/font_loader.

    @classmethod
    def INPUT_TYPES(cls):
        cls.FONTS = combined_font_list()
        cls.FONT_NAMES = sorted(cls.FONTS.keys())
        return {
            "required": {
                "font_file": (cls.FONT_NAMES, {"default": cls.FONT_NAMES[0]}),
                "font_size": ("INT", {"default": 75, "min": 1, "step": 1, "display": "number"}),
                "font_color": ("STRING", {"default": "white", "display": "text"}),
                "kerning": ("INT", {"default": 0, "step": 1, "display": "number"}),
                "border_width": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number"}),
                "border_color": ("STRING", {"default": "grey", "display": "text"}),
                "shadow_color": ("STRING", {"default": "grey", "display": "text"}),
                "shadow_offset_x": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number"}),
                "shadow_offset_y": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number"}),
                "x_offset": ("INT", {"default": 0, "step": 1, "display": "number"}),
                "y_offset": ("INT", {"default": 0, "step": 1, "display": "number"}),
                "rotation": ("INT", {"default": 0, "min": -360, "max": 360, "step": 1}),
                "rotation_anchor_x": ("INT", {"default": 0, "step": 1}),
                "rotation_anchor_y": ("INT", {"default": 0, "step": 1}),
            },
            "optional": {
                # Accepts the wire format from Scheduled Values /
                # Preset Color Animations: `JSON-keyframes$reset_mode`.
                # A flat list of {x, y} keyframes is broadcast to every
                # animatable property; a dict with property names is
                # used per-property.
                "scheduled_values": ("STRING", {"default": "{}", "display": "text", "forceInput": True}),
            },
        }

    CATEGORY = "💠 Mana Nodes/⚙️ Generator Settings"
    RETURN_TYPES = ("TEXT_GRAPHIC_ELEMENT",)
    RETURN_NAMES = ("font",)
    FUNCTION = "run"

    # ------------------------------------------------------------------ #
    # Output shaping — font2img expects each animatable property to be a  #
    # (value, animation_reset) tuple, and color props to be (color, None) #
    # when supplied as strings.                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _shape_scalar(value, reset):
        """Wrap a scalar widget value as (value, reset_or_None)."""
        return (value, reset)

    @staticmethod
    def _shape_color(value, reset=None):
        """Colors come in as plain strings; wrap so the consumer sees a tuple."""
        if isinstance(value, str):
            return (value, reset)
        return value

    # ------------------------------------------------------------------ #
    # Main pipeline                                                       #
    # ------------------------------------------------------------------ #
    def run(self, **kwargs):
        # Parse scheduled_values. The string is either
        #   "{...}" / "[]"        — no animation_reset suffix
        #   "[...]$word"          — list with reset mode
        #   "{prop: [...], ...}$word" — per-property dict (advanced)
        keyframes, reset_mode = parse_scheduled_string(
            kwargs.get("scheduled_values", "{}")
        )

        # If a non-empty flat list was supplied, broadcast to every
        # animatable property. If a dict was supplied, look up per
        # property; if a key is missing, fall back to the widget value.
        # An empty list means "no schedule" — leave widget values alone.
        if isinstance(keyframes, list):
            per_property = (
                {prop: (keyframes, reset_mode) for prop in _ANIMATABLE_PROPS}
                if keyframes else {}
            )
        elif isinstance(keyframes, dict):
            per_property = {
                prop: (keyframes[prop], reset_mode)
                for prop in _ANIMATABLE_PROPS
                if prop in keyframes
            }
        else:
            per_property = {}

        settings = {
            "font_file": kwargs.get("font_file"),
            "font_color": self._shape_color(kwargs.get("font_color")),
            "border_color": self._shape_color(kwargs.get("border_color")),
            "shadow_color": self._shape_color(kwargs.get("shadow_color")),
        }
        # Add the animatable properties, preferring the scheduled list
        # over the widget's static value.
        for prop in _ANIMATABLE_PROPS:
            if prop in per_property:
                schedule, reset = per_property[prop]
                settings[prop] = (schedule, reset)
            else:
                settings[prop] = self._shape_scalar(kwargs.get(prop), None)

        return (settings,)

