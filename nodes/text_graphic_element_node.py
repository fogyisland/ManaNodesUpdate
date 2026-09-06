import json

from ..helpers.font_loader import combined_font_list


class text_graphic_element:

    FONTS = {}
    FONT_NAMES = []

    def __init__(self):
        pass

    # Font discovery is shared with font2img via helpers/font_loader.
    # The legacy per-class duplicates were removed when matplotlib's
    # `font_manager` dependency moved to the helper module.

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
                # Lets users feed outputs of Scheduled Values / Preset Color Animations
                # into any of the animatable properties (font_size, x_offset, etc.).
                # Format: JSON-list string optionally followed by "$<animation_reset>".
                "scheduled_values": ("STRING", {"default": "{}", "display": "text", "forceInput": True}),
            },
        }

    CATEGORY = "💠 Mana Nodes/⚙️ Generator Settings"
    RETURN_TYPES = ("TEXT_GRAPHIC_ELEMENT",)
    RETURN_NAMES = ("font",)
    FUNCTION = "run"
    #INPUT_IS_LIST = True

    def parse_int_or_json(self, value):
        """Parse the input as JSON if it's a string in JSON format, otherwise return as is."""
        if isinstance(value, str):
            # Extracting and removing the $animation_reset part
            if '$' in value:
                parts = value.split('$', 1)
                value = parts[0]  # JSON part
                animation_reset = parts[1]  # animation_reset part
            else:
                animation_reset = None

            try:
                json_value = json.loads(value)
            except json.JSONDecodeError:
                json_value = value

            return json_value, animation_reset
        
        return value, None

    def process_color_input(self, border_color):
        if isinstance(border_color, str):
            return (border_color, None)
        return border_color

    def run(self, **kwargs):
        settings_string = kwargs.get('scheduled_values', '{}')
        json_settings, animation_reset_from_string = self.parse_int_or_json(settings_string)
        settings = {
            'font_file': json_settings.get('font_file', kwargs.get('font_file')),
            'font_color': self.process_color_input(kwargs.get('font_color')),
            'kerning': json_settings.get('kerning', self.parse_int_or_json(kwargs.get('kerning'))),
            'border_width': json_settings.get('border_width', self.parse_int_or_json(kwargs.get('border_width'))),
            'border_color': self.process_color_input(kwargs.get('border_color')),
            'shadow_color': self.process_color_input(kwargs.get('shadow_color')),
            'shadow_offset_x': json_settings.get('shadow_offset_x', self.parse_int_or_json(kwargs.get('shadow_offset_x'))),
            'shadow_offset_y': json_settings.get('shadow_offset_y', self.parse_int_or_json(kwargs.get('shadow_offset_y'))),
            'font_size': json_settings.get('font_size', self.parse_int_or_json(kwargs.get('font_size'))),
            'x_offset': json_settings.get('x_offset', self.parse_int_or_json(kwargs.get('x_offset'))),
            'y_offset': json_settings.get('y_offset', self.parse_int_or_json(kwargs.get('y_offset'))),
            'rotation': json_settings.get('rotation', self.parse_int_or_json(kwargs.get('rotation'))),
            'rotation_anchor_x': json_settings.get('rotation_anchor_x', self.parse_int_or_json(kwargs.get('rotation_anchor_x'))),
            'rotation_anchor_y': json_settings.get('rotation_anchor_y', self.parse_int_or_json(kwargs.get('rotation_anchor_y'))),
        }

        return (settings,)
