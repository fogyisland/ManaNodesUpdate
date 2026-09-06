class canvas_settings:

    DESCRIPTION = "魔力节点 — 画布属性。输出尺寸、背景颜色/图片、内边距、对齐。试试搜索：mana、魔力、画布、背景、图片尺寸。 Mana Nodes — canvas properties. Output dimensions, background color/image, padding, alignment. Try searching: mana, canvas, background, image size."

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        alignment_options = ["left top", "left center", "left bottom",
                             "center top", "center center", "center bottom",
                             "right top", "right center", "right bottom"]
        return {
            "required": {
                "height": ("INT", {"default": 512, "step": 1, "display": "number"}),
                "width": ("INT", {"default": 512, "step": 1, "display": "number"}),
                "background_color": ("STRING", {"default": "black", "display": "text"}),
                "text_alignment": (alignment_options, {"default": "center center", "display": "dropdown"}),
                "padding": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number"}),
                "line_spacing": ("INT", {"default": 5, "step": 1, "display": "number"}),
            },
            "optional": {
                "images": ("IMAGE", {"default": None}),
            },
        }

    CATEGORY = "💠 Mana Nodes/⚙️ Generator Settings"
    RETURN_TYPES = ("CANVAS_SETTINGS",)
    RETURN_NAMES = ("canvas",)
    FUNCTION = "run"

    def run(self, **kwargs):

        settings = {
            'height': kwargs.get('height'),
            'width': kwargs.get('width'),
            'background_color': kwargs.get('background_color'),
            'text_alignment': kwargs.get('text_alignment'),
            'padding': kwargs.get('padding'),
            'images': kwargs.get('images'),
            'line_spacing': kwargs.get('line_spacing'),
        }

        return (settings,)

