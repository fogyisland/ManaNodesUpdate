class scheduled_values:

    DESCRIPTION = "魔力节点 — 调度值。交互式关键帧图表，驱动任意字体属性动画。试试搜索：mana、魔力、动画、关键帧、时间线、图表。 Mana Nodes — scheduled values. Interactive keyframe chart for animating any Font Properties widget. Try searching: mana, animation, keyframe, timeline, chart."

    def __init__(self):
        pass


    @classmethod
    def INPUT_TYPES(cls):
        animation_reset = ["word", "line", "never","looped","pingpong"]
        easing_types = [
            "linear",
            "easeInQuad",
            "easeOutQuad",
            "easeInOutQuad",
            "easeInCubic",
            "easeOutCubic",
            "easeInOutCubic",
            "easeInQuart",
            "easeOutQuart",
            "easeInOutQuart",
            "easeInQuint",
            "easeOutQuint",
            "easeInOutQuint",
            "exponential"
        ]        
        step_mode = ["single", "auto"]
        return {
            "required": {
                "frame_count": ("INT", {"default": 30, "step": 1, "display": "number"}),
                "value_range": ("INT", {"default": 15, "step": 1, "display": "number"}),
                "easing_type": (easing_types, {"default": "linear", "display": "dropdown"}),
                "step_mode": (step_mode, {"default": "single", "display": "dropdown"}),
                "animation_reset": (animation_reset, {"default": "word", "display": "dropdown"}),
                "id": ("INT", {"default": 0, "step": 1, "display": "number"}),
                "scheduled_values": ("STRING", {"default": "[]", "display": "text","readOnly": True }),
            },            
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO"
            }
        }

    CATEGORY = "💠 Mana Nodes/📅 Value Scheduling"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("scheduled_values",)
    FUNCTION = "run"

    def run(self, **kwargs):
        scheduled_values = kwargs.get('scheduled_values')
        animation_reset = kwargs.get('animation_reset')

        # Empty schedule (the default state when the chart hasn't been
        # touched yet) is a valid input — Font Properties treats it as
        # "no animation, use widget values". Don't raise; just hand
        # back an empty string so downstream consumers skip it.
        # Treat None, "", whitespace, and the literal "[]" / "{}"
        # sentinels as empty. Str() happens AFTER the empty check so
        # we don't turn None into the string "None".
        if scheduled_values is None:
            return ("",)
        scheduled_values = str(scheduled_values).strip()
        if not scheduled_values or scheduled_values in ("[]", "{}"):
            return ("",)

        return (f"{scheduled_values}${animation_reset}",)