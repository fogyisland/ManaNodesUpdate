import os
import re
from functools import lru_cache

import numpy as np
import torch
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from torchvision import transforms

from ..helpers.font_loader import combined_font_list, get_font
from ..helpers.animation import (
    parse_animation_duration,
    sequence_frame,
    value_at,
)

class font2img:

    # ComfyUI 的节点搜索框对类描述做子字符串匹配。这里同时列出中文
    # 和英文同义词，让用户搜索 "mana"、"字幕"、"caption" 等都能找到。
    # ComfyUI's node-search box does a substring match against the
    # class description, so we list synonyms in both languages here.
    DESCRIPTION = "魔力节点 — 文字转图像生成器。渲染动态字幕、动画文字。试试搜索：mana、魔力、字幕、副标题、排版、文字。 Mana Nodes — text to image generator. Renders animated captions, subtitles, and typography. Try searching: mana, caption, subtitle, typography."

    FONTS = {}
    FONT_NAMES = []

    def __init__(self):
        pass

    # NOTE: font discovery and loading live in helpers/font_loader.py.
    # The methods below (system_font_names / combined_font_list / etc.)
    # were duplicates that depended on the matplotlib `font_manager`
    # import; that import was removed during refactoring and these
    # methods broke with `NameError: name 'font_manager' is not defined`.

    def get_font(self, font_name, font_size) -> ImageFont.FreeTypeFont:
        # Defensive: `font_name` may arrive wrapped depending on how the
        # upstream TEXT_GRAPHIC_ELEMENT was assembled. Accept all the
        # shapes a downstream consumer has actually produced in the wild:
        #   - str                     -> the bare font filename
        #   - ["foo.ttf"]             -> single-element list/tuple
        #   - ["foo.ttf", "word"]     -> (value, reset) tuple flattened
        #   - {"font_file": "..."}    -> dict carrying the key we want
        # Recursive unwrap: keep peeling lists/dicts until we either hit
        # a string or something we can't recognize.
        depth = 0
        while depth < 5 and not isinstance(font_name, str):
            if isinstance(font_name, dict):
                font_name = font_name.get("font_file", font_name.get("name", ""))
            elif isinstance(font_name, (list, tuple)):
                if not font_name:
                    raise ValueError("font_name list/tuple is empty")
                font_name = font_name[0]
            else:
                raise ValueError(
                    f"font_name has unrecognized type {type(font_name).__name__}: {font_name!r}"
                )
            depth += 1
        if not isinstance(font_name, str) or not font_name:
            raise ValueError(f"font_name must be a non-empty string, got {font_name!r}")
        # Resolve the registered display name -> on-disk path. If the
        # caller already gave us a path, accept it directly.
        if font_name in self.FONTS:
            font_file = self.FONTS[font_name]
        elif os.path.isfile(font_name):
            font_file = font_name
        else:
            raise ValueError(
                f"Unknown font {font_name!r}. Make sure a Font Properties "
                "node is connected to the `font` input, and that its "
                "`font_file` dropdown selects a registered font."
            )
        # Normalize font_size too — keyframe lists reach here as
        # `[{"x": 1, "y": 24}, ...]` (the raw schedule) instead of the
        # already-interpolated int. Pull a representative int out.
        if isinstance(font_size, (list, tuple)):
            if not font_size:
                raise ValueError("font_size list/tuple is empty")
            # If these are keyframes [{x,y}], take the last value;
            # otherwise take the first element.
            if all(isinstance(d, dict) and "y" in d for d in font_size):
                font_size = font_size[-1]["y"]
            else:
                font_size = font_size[0]
        if isinstance(font_size, dict):
            font_size = font_size.get("y", font_size.get("value", 0))
        if not isinstance(font_size, int):
            try:
                font_size = int(font_size)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"font_size must be int-convertible, got {type(font_size).__name__}: {font_size!r}"
                ) from exc
        # Last-mile check: even if `font_file` looked like a string,
        # some upstream path can hand us a list here. Convert
        # defensively before lru_cache (which keys on the args).
        if not isinstance(font_file, str):
            raise ValueError(
                f"font_file resolved to non-string {type(font_file).__name__}: {font_file!r}"
            )
        return get_font(font_file, font_size)

    @classmethod
    def INPUT_TYPES(self):
        self.FONTS = combined_font_list()
        self.FONT_NAMES = sorted(self.FONTS.keys())
        return {
            "required": {
                "font": ("TEXT_GRAPHIC_ELEMENT", {"default": None,"forceInput": True}),
                "text": ("STRING", {"multiline": True, "placeholder": "\"1\": \"Hello\",\n\"10\": \"Hello World\""}),
                "canvas": ("CANVAS_SETTINGS", {"default": None,"forceInput": True}),
                "frame_count": ("INT", {"default": 1, "min": 1, "step": 1, "display": "number"}),
            },
            "optional": {
                "transcription": ("TRANSCRIPTION", {"default": None,"forceInput": True}),
                "highlight_font": ("TEXT_GRAPHIC_ELEMENT", {"default": None,"forceInput": True}),
                "skip_first_frames": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING",)
    RETURN_NAMES = ("images", "framestamps_string",)
    FUNCTION = "run"
    CATEGORY = "💠 Mana Nodes"

    def run(self, **kwargs):
        frame_count = kwargs['frame_count']
        images = kwargs.get('canvas', {}).get('images', [None] * frame_count)
        transcription = kwargs.get('transcription', None)
        text = kwargs.get('text')

        if transcription != None:
            formatted_transcription = self.format_transcription(kwargs)
            text = formatted_transcription
        else:
            formatted_transcription = text

        # Reset the empty-text dedupe flag whenever we actually got
        # non-empty text. This way a user who starts with empty text,
        # then types something, sees the warning go away AND a fresh
        # warning if they delete the text again.
        if text and text.strip():
            self._empty_text_warned = False
            self._empty_text_warned_key = None

        # Defensive: tell the user *why* they're getting blank frames.
        # Without this, the silent failure (black video) is hard to
        # diagnose. Common causes:
        #   - Speech Recognition produced no text (audio silent /
        #     wrong model for the language / audio too short)
        #   - User typed "{}" as text but didn't connect transcription
        if not text or not text.strip():
            from ..helpers.logger import logger
            warn_key = (transcription is not None,)
            if not getattr(self, "_empty_text_warned", False) or (
                getattr(self, "_empty_text_warned_key", None) != warn_key
            ):
                self._empty_text_warned = True
                self._empty_text_warned_key = warn_key
                if transcription is not None:
                    # Transcription was connected but produced no text.
                    # Most common cause: audio is silent, very short, or
                    # heavy background music that even Whisper can't decode.
                    logger().warning(
                        "Text to Image: transcription was provided but "
                        "produced 0 words. Check that the audio contains "
                        "audible speech (not pure music), is at least a "
                        "few seconds long, and isn't silent. Switching to "
                        "whisper-medium or whisper-large-v3 helps on noisy "
                        "audio. Output will be blank frames."
                    )
                else:
                    logger().warning(
                        "Text to Image: text input is empty. Either type "
                        "a string in the 'text' field or connect a Speech "
                        "Recognition output to the 'transcription' input. "
                        "Output will be blank frames."
                    )

        frame_text_dict, is_structured_input = self.parse_text_input(text, kwargs)
        frame_text_dict = self.cumulative_text(frame_text_dict, frame_count)

        images = self.generate_images(frame_text_dict,images , kwargs)
        image_batch = torch.cat(images, dim=0)

        return (image_batch, formatted_transcription,)

    def format_transcription(self, kwargs):
        if not kwargs['transcription']:
            return ""
        
        highlight_font = kwargs.get('highlight_font', None)
        transcription_fps = kwargs['transcription']['fps']
        transcription_mode = kwargs['transcription']['transcription_mode']
        transcription_data = kwargs['transcription']['transcription_data']
        image_width = kwargs['canvas']['width']
        padding = kwargs['canvas']['padding']
        formatted_transcription = ""
        current_sentence = ""
        sentence_words = []
        sentence_frame_numbers = []

        for i, (word, start_time, end_time) in enumerate(transcription_data):
            frame_number = 1 + round(start_time * transcription_fps)

            if not current_sentence:
                current_sentence = word
                sentence_words = [word]
                sentence_frame_numbers = [frame_number]
            else:
                new_sentence = current_sentence + " " + word
                width = self.get_text_width(new_sentence, kwargs)
                if width <= image_width - padding:
                    current_sentence = new_sentence
                    sentence_words.append(word)
                    sentence_frame_numbers.append(frame_number)
                else:
                    if transcription_mode == "line":
                        # Format each word in the sentence with tags and output with the corresponding frame number
                        for j, sentence_word in enumerate(sentence_words):
                            if highlight_font is not None:
                                sentence = ' '.join(["<tag>{}</tag>".format(w) if j == k else w for k, w in enumerate(sentence_words)])
                            else:
                                sentence = ' '.join(sentence_words)
                            formatted_transcription += f'"{sentence_frame_numbers[j]}": "{sentence}",\n'
                        current_sentence = word
                        sentence_words = [word]
                        sentence_frame_numbers = [frame_number]
                    else:
                        current_sentence = word

            if transcription_mode == "fill":
                words = current_sentence.split()
                # Add tags around the last word in the sentence only if highlight_font is not None
                if words and highlight_font is not None:
                    words[-1] = f"<tag>{words[-1]}</tag>"
                tagged_sentence = ' '.join(words)
                formatted_transcription += f'"{frame_number}": "{tagged_sentence}",\n'

            if transcription_mode == "word":
                formatted_transcription += f'"{frame_number}": "{word}",\n'

        # Handle the last sentence for 'line' and 'fill' modes
        if current_sentence:
            if transcription_mode == "line":
                for j, sentence_word in enumerate(sentence_words):
                    if highlight_font is not None:
                        tagged_sentence = ' '.join(["<tag>{}</tag>".format(w) if j == k else w for k, w in enumerate(sentence_words)])
                    else:
                        tagged_sentence = ' '.join(sentence_words)
                    formatted_transcription += f'"{sentence_frame_numbers[j]}": "{tagged_sentence}",\n'

        return formatted_transcription

    # Helper functions
    def animation_reset(self, animation_reset_mode, new_text, old_text, transcription_mode):
        # `never` / `looped` / `pingpong` semantics: the animation
        # should keep going regardless of text changes, so we never
        # signal a reset. The previous fall-through returned False,
        # which meant once an animation started it would never reset
        # even when text changed — a silent correctness bug for any
        # scheduled_values wiring that picked anything other than
        # `word` or `line`.
        if animation_reset_mode == 'word':
            return new_text.split() != old_text.split()
        if animation_reset_mode == 'line':
            new_text = self.remove_tags(new_text)
            old_text = self.remove_tags(old_text)
            if transcription_mode == 'line':
                return new_text != old_text
            if transcription_mode == 'fill':
                return len(new_text.split()) < len(old_text.split())
            return new_text != old_text
        if animation_reset_mode in ('never', 'looped', 'pingpong', None):
            return False
        # Unknown mode — default to the most conservative behaviour
        # (treat any text change as a reset) rather than silently
        # swallowing updates.
        return new_text != old_text

    @staticmethod
    def remove_tags(text):
        """Strip <tag>...</tag> markup from `text`."""
        return re.sub(r"</?tag>", "", text)

    def generate_images(self, frame_text_dict, input_images, kwargs):
        images = []
        
        # background images or color
        prepared_images = self.prepare_image(input_images, kwargs)
        
        transcription = kwargs.get('transcription', None)
        if transcription != None:
            transcription_mode = transcription['transcription_mode']
        else:
            transcription_mode = None

        main_font = kwargs.get('font', None)
        if main_font != None:
            main_font_file = main_font['font_file']

        rotation = kwargs['font']['rotation'][0]
        y_offset = kwargs['font']['y_offset'][0]
        x_offset = kwargs['font']['x_offset'][0]
        font_size = kwargs['font']['font_size'][0]

        font_color = kwargs['font']['font_color'][0]
        border_color = kwargs['font']['border_color'][0]
        shadow_color = kwargs['font']['shadow_color'][0]

        animation_reset_rotation = _normalize_reset_mode(kwargs['font']['rotation'][1])
        animation_reset_y_offset = _normalize_reset_mode(kwargs['font']['y_offset'][1])
        animation_reset_x_offset = _normalize_reset_mode(kwargs['font']['x_offset'][1])
        animation_reset_font_size = _normalize_reset_mode(kwargs['font']['font_size'][1])

        animation_reset_font_color = _normalize_reset_mode(kwargs['font']['font_color'][1])
        animation_reset_border_color = _normalize_reset_mode(kwargs['font']['border_color'][1])
        animation_reset_shadow_color = _normalize_reset_mode(kwargs['font']['shadow_color'][1])

        rotation_duration = parse_animation_duration(rotation)
        y_offset_duration = parse_animation_duration(y_offset)
        x_offset_duration = parse_animation_duration(x_offset)
        font_size_duration = parse_animation_duration(font_size)
        font_color_duration = parse_animation_duration(font_color)
        shadow_color_duration = parse_animation_duration(shadow_color)
        border_color_duration = parse_animation_duration(border_color)

        highlight_font = kwargs.get('highlight_font', None)
        if highlight_font != None:
            tagged_font_file = highlight_font['font_file']

            tagged_font_size = highlight_font['font_size'][0]
            tagged_font_color = highlight_font['font_color'][0]
            tagged_border_color = highlight_font['border_color'][0]
            tagged_shadow_color = highlight_font['shadow_color'][0]

            animation_reset_tagged_font_size = highlight_font['font_size'][1]
            animation_reset_tagged_font_color = highlight_font['font_color'][1]
            animation_reset_tagged_border_color = highlight_font['border_color'][1]
            animation_reset_tagged_shadow_color = highlight_font['shadow_color'][1]

            tagged_font_size_duration = parse_animation_duration(tagged_font_size)
            tagged_font_color_duration = parse_animation_duration(tagged_font_color)
            tagged_border_color_duration = parse_animation_duration(tagged_border_color)
            tagged_shadow_color_duration = parse_animation_duration(tagged_shadow_color)

        frame_count = kwargs['frame_count']
        removed_tags_last_text= ''
        last_text = ""
        animation_started_frame_rotation = 1
        animation_started_frame_y_offset = 1
        animation_started_frame_x_offset = 1
        animation_started_frame_font_size = 1

        animation_started_frame_font_color = 1
        animation_started_frame_border_color = 1
        animation_started_frame_shadow_color = 1

        animation_started_frame_tagged_font_size = 1
        animation_started_frame_tagged_font_color = 1
        animation_started_frame_tagged_border_color = 1
        animation_started_frame_tagged_shadow_color = 1

        first_pass = True

        # Ensure prepared_images is a list
        if not isinstance(prepared_images, list):
            prepared_images = [prepared_images]

        for i in range(1, frame_count + 1):
            text = frame_text_dict.get(str(i), "")
            removed_tags_text = self.remove_tags(text)

            if self.animation_reset(animation_reset_rotation, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_rotation = i
            if self.animation_reset(animation_reset_y_offset, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_y_offset = i
            if self.animation_reset(animation_reset_x_offset, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_x_offset = i
            if self.animation_reset(animation_reset_font_size, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_font_size = i
            if self.animation_reset(animation_reset_font_color, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_font_color = i
            if self.animation_reset(animation_reset_border_color, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_border_color = i
            if self.animation_reset(animation_reset_shadow_color, removed_tags_text, removed_tags_last_text, transcription_mode) or first_pass == True:
                animation_started_frame_shadow_color = i

            if highlight_font is not None:
                if self.animation_reset(animation_reset_tagged_font_size, text, last_text, transcription_mode) or first_pass == True:
                    animation_started_frame_tagged_font_size = i
                if self.animation_reset(animation_reset_tagged_font_color, text, last_text, transcription_mode) or first_pass == True:
                    animation_started_frame_tagged_font_color = i
                if self.animation_reset(animation_reset_tagged_border_color, text, last_text, transcription_mode) or first_pass == True:
                    animation_started_frame_tagged_border_color = i
                if self.animation_reset(animation_reset_tagged_shadow_color, text, last_text, transcription_mode) or first_pass == True:
                    animation_started_frame_tagged_shadow_color = i                        

            first_pass = False
            last_text = text
            removed_tags_last_text = removed_tags_text

            # Calculate sequence frames for each property
            def _seq(start, duration, mode):
                return sequence_frame(i, start, duration, mode)

            sequence_frame_rotation = _seq(animation_started_frame_rotation, rotation_duration, animation_reset_rotation)
            sequence_frame_y_offset = _seq(animation_started_frame_y_offset, y_offset_duration, animation_reset_y_offset)
            sequence_frame_x_offset = _seq(animation_started_frame_x_offset, x_offset_duration, animation_reset_x_offset)
            sequence_frame_font_size = _seq(animation_started_frame_font_size, font_size_duration, animation_reset_font_size)
            sequence_frame_font_color = _seq(animation_started_frame_font_color, font_color_duration, animation_reset_font_color)
            sequence_frame_border_color = _seq(animation_started_frame_border_color, border_color_duration, animation_reset_border_color)
            sequence_frame_shadow_color = _seq(animation_started_frame_shadow_color, shadow_color_duration, animation_reset_shadow_color)

            if highlight_font is not None:
                sequence_frame_tagged_font_size = _seq(animation_started_frame_tagged_font_size, tagged_font_size_duration, animation_reset_tagged_font_size)
                sequence_frame_tagged_font_color = _seq(animation_started_frame_tagged_font_color, tagged_font_color_duration, animation_reset_tagged_font_color)
                sequence_frame_tagged_border_color = _seq(animation_started_frame_tagged_border_color, tagged_border_color_duration, animation_reset_tagged_border_color)
                sequence_frame_tagged_shadow_color = _seq(animation_started_frame_tagged_shadow_color, tagged_shadow_color_duration, animation_reset_tagged_shadow_color)

            # Resolve every font / color / offset property to a
            # scalar via the module-level helper. This handles all
            # upstream shapes (tuple / keyframe list / dict / scalar).
            current_rotation = _resolve_property(rotation, sequence_frame_rotation, rotation)
            current_y_offset = _resolve_property(y_offset, sequence_frame_y_offset, y_offset)
            current_x_offset = _resolve_property(x_offset, sequence_frame_x_offset, x_offset)
            current_font_size = _resolve_property(font_size, sequence_frame_font_size, font_size)
            font = self.get_font(main_font_file, current_font_size)

            current_font_color = _resolve_property(font_color, sequence_frame_font_color, font_color)
            current_border_color = _resolve_property(border_color, sequence_frame_border_color, border_color)
            current_shadow_color = _resolve_property(shadow_color, sequence_frame_shadow_color, shadow_color)

            if highlight_font is not None:
                current_tagged_font_size = _resolve_property(
                    tagged_font_size, sequence_frame_tagged_font_size, tagged_font_size,
                )
                tagged_font = self.get_font(tagged_font_file, current_tagged_font_size)
                current_tagged_font_color = _resolve_property(
                    tagged_font_color, sequence_frame_tagged_font_color, tagged_font_color,
                )
                current_tagged_border_color = _resolve_property(
                    tagged_border_color, sequence_frame_tagged_border_color, tagged_border_color,
                )
                current_tagged_shadow_color = _resolve_property(
                    tagged_shadow_color, sequence_frame_tagged_shadow_color, tagged_shadow_color,
                )
            else:
                tagged_font = font
                current_tagged_font_color = current_font_color
                current_tagged_border_color = current_border_color
                current_tagged_shadow_color = current_shadow_color

            image_index = min(i - 1, len(prepared_images) - 1)
            selected_image = prepared_images[image_index]

            draw = ImageDraw.Draw(selected_image)
            text_block_width, text_block_height = self.calculate_text_block_size(draw, text, font, tagged_font, kwargs)
            text_position = self.calculate_text_position(text_block_width, text_block_height, current_x_offset, current_y_offset, kwargs)
            processed_image = self.process_single_image(selected_image, 
                                                        text, 
                                                        font, 
                                                        current_rotation, 
                                                        current_x_offset, 
                                                        current_y_offset, 
                                                        text_position, 
                                                        tagged_font, 
                                                        current_font_color, 
                                                        current_border_color, 
                                                        current_shadow_color, 
                                                        current_tagged_font_color,
                                                        current_tagged_border_color,
                                                        current_tagged_shadow_color,
                                                        kwargs)
            images.append(processed_image)
        return images

    def separate_text(self, text):
        tag_start = "<tag>"
        tag_end = "</tag>"
        tagged_parts = []
        non_tagged_parts = []
        while text:
            start_index = text.find(tag_start)
            end_index = text.find(tag_end)
            if start_index != -1 and end_index != -1:
                non_tagged_parts.append(text[:start_index])
                tagged_parts.append(text[start_index + len(tag_start):end_index])
                text = text[end_index + len(tag_end):]
            else:
                non_tagged_parts.append(text)
                break
        return ' '.join(non_tagged_parts), ' '.join(tagged_parts)  
      
    def process_single_image(self, image, text, font, rotation_angle, x_offset, y_offset, text_position, tagged_font, font_color, border_color, shadow_color, tagged_font_color, tagged_border_color, tagged_shadow_color, kwargs ):
        # Defensive: every font prop may be either a constant value
        # (passed through) or a (value, animation_reset) tuple from
        # text_graphic_element. `_font_prop` unwraps both shapes with
        # a sensible default. This avoids NameError crashes when an
        # Pull a font property out of the TEXT_GRAPHIC_ELEMENT dict and
        # normalize it to a scalar. Routes through `_resolve_property`
        # so the same shape variations (tuple / keyframe list / dict /
        # scalar) work here as in the main render loop.
        def _font_prop(name, default=0):
            raw = kwargs.get('font', {}).get(name, default)
            resolved = _resolve_property(raw, 1, raw if raw is not None else default)
            if resolved is None:
                return default
            return resolved

        rotation_anchor_x = _font_prop('rotation_anchor_x', 0)
        rotation_anchor_y = _font_prop('rotation_anchor_y', 0)
        border_width = _font_prop('border_width', 0)
        # Both shadow offsets are needed when sizing the overlay so a
        # rotated text block isn't clipped on the Y axis.
        shadow_offset_x = _font_prop('shadow_offset_x', 0)
        shadow_offset_y = _font_prop('shadow_offset_y', 0)

        # Create a larger canvas with the prepared image as the background
        orig_width, orig_height = image.size
        canvas_size = int(max(orig_width, orig_height) * 1.5)
        canvas = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))

        # Calculate text size and position
        draw = ImageDraw.Draw(canvas)
        text_block_width, text_block_height = self.calculate_text_block_size(draw, text, font, tagged_font, kwargs)
        text_x, text_y = text_position
        text_x += (canvas_size - orig_width) / 2 + x_offset
        text_y += (canvas_size - orig_height) / 2 + y_offset

        # Calculate the center of the text block
        text_center_x = text_x + text_block_width / 2
        text_center_y = text_y + text_block_height / 2

        # Calculate text size without tags for accurate kerning
        visible_chars = self.remove_tags(text)
        kerning = _font_prop('kerning', 0)
        total_kerning_width = sum(font.getlength(char) + kerning for char in visible_chars) - kerning * len(visible_chars) if len(visible_chars) > 0 else 0

        overlay = Image.new('RGBA', (int(text_block_width + border_width * 2 + shadow_offset_x + total_kerning_width), int(text_block_height + border_width * 2 + shadow_offset_y)), (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        # Draw text on overlays
        self.draw_text_on_overlay(draw_overlay, text, font, tagged_font, font_color, border_color, shadow_color, tagged_font_color, tagged_border_color, tagged_shadow_color, kwargs)
        canvas.paste(overlay, (int(text_x), int(text_y)), overlay)
        anchor = (text_center_x + rotation_anchor_x, text_center_y + rotation_anchor_y)
        rotated_canvas = canvas.rotate(rotation_angle, center=anchor, expand=0)
        
        # Create a new canvas to fill the background of the rotated image
        new_canvas = Image.new('RGBA', rotated_canvas.size, (0, 0, 0, 0))

        # Paste the input image as the background of the new canvas
        new_canvas.paste(image, (int((rotated_canvas.size[0] - orig_width) / 2), int((rotated_canvas.size[1] - orig_height) / 2)))

        # Paste the rotated image onto the new canvas, keeping the background color
        new_canvas.paste(rotated_canvas, (0, 0), rotated_canvas)

        # Crop the canvas back to the original image dimensions
        cropped_image = new_canvas.crop(((canvas_size - orig_width) / 2, (canvas_size - orig_height) / 2, (canvas_size + orig_width) / 2, (canvas_size + orig_height) / 2))

        return self.process_image_for_output(cropped_image)

    def draw_text_on_overlay(self, draw_overlay, text, font, tagged_font, font_color, border_color, shadow_color, tagged_font_color, tagged_border_color, tagged_shadow_color, kwargs):
        """Render text with border + shadow onto the overlay.

        Strategy:
            1. Pre-strip the <tag>...</tag> markers so we can compute
               the *visible* string. The font is then measured against
               the visible text (kerning etc. line up with what users see).
            2. Render the entire block in one ImageDraw.text call with
               stroke_width=border. This is dramatically faster than the
               historical per-character pixel loop (O(1) vs O(n·w²)) and
               produces the same visual result for constant width/color
               text.
            3. For the tagged segment, draw on top with the tagged font /
               colors. We re-measure to find the right x-offset.
        """
        highlight_font = kwargs.get('highlight_font', None)
        tagged_border_width = (
            _resolve_property(highlight_font['border_width'], 1, 1)
            if highlight_font else 1
        )
        tagged_shadow_offset_x = (
            _resolve_property(highlight_font['shadow_offset_x'], 1, 0)
            if highlight_font else 0
        )
        tagged_shadow_offset_y = (
            _resolve_property(highlight_font['shadow_offset_y'], 1, 0)
            if highlight_font else 0
        )

        main_border_width = _resolve_property(kwargs['font']['border_width'], 1, 0)
        main_shadow_offset_x = _resolve_property(kwargs['font']['shadow_offset_x'], 1, 0)
        main_shadow_offset_y = _resolve_property(kwargs['font']['shadow_offset_y'], 1, 0)
        line_spacing = kwargs['canvas']['line_spacing']

        # Coerce colour values to PIL-safe shapes here. The renderer
        # path below passes fill= straight to PIL.ImageDraw.text, which
        # rejects a bare list with "color must be int or tuple". A
        # schedule-driven font_color arrives as [r, g, b] (list), so
        # we convert at the boundary rather than scatter .tuple() calls
        # inside the loop.
        main_color = _normalize_color(font_color)
        main_border = _normalize_color(border_color)
        main_shadow = _normalize_color(shadow_color)
        tagged_color = _normalize_color(tagged_font_color)
        tagged_border = _normalize_color(tagged_border_color)
        tagged_shadow = _normalize_color(tagged_shadow_color)

        # Split the line into (text_chunk, font, color_tuple) groups so we
        # can do a single pass per contiguous style region. This is the
        # same behavior the old char-by-char loop implemented, but at
        # O(groups) cost instead of O(chars).
        segments = _split_tagged_segments(
            text,
            main=(font, main_color, main_border, main_shadow,
                  main_border_width, main_shadow_offset_x, main_shadow_offset_y),
            tagged=(tagged_font, tagged_color, tagged_border, tagged_shadow,
                    tagged_border_width, tagged_shadow_offset_x, tagged_shadow_offset_y),
        )

        y = main_border_width
        for line_text, line_segs in _group_segments_by_line(segments):
            if not line_segs:
                y += font.getbbox('Agy')[3] + line_spacing
                continue

            x = main_border_width
            line_height = 0
            for seg_text, seg_font, seg_color, seg_border, seg_shadow, seg_border_w, seg_shadow_x, seg_shadow_y in line_segs:
                if not seg_text:
                    continue
                # Per-line metrics, cached once per draw.
                ascent, descent = seg_font.getmetrics()
                line_height = max(line_height, ascent + descent)

                # Shadow: render the segment offset, then the segment on
                # top. stroke_width applies the border around the visible
                # glyphs in a single rasterization pass — much faster
                # than the old nested-dx/dy loop.
                if seg_shadow_x or seg_shadow_y:
                    draw_overlay.text(
                        (x + seg_shadow_x, y + seg_shadow_y),
                        seg_text, font=seg_font, fill=seg_shadow,
                        stroke_width=seg_border_w, stroke_fill=seg_shadow,
                    )
                draw_overlay.text(
                    (x, y), seg_text, font=seg_font, fill=seg_color,
                    stroke_width=seg_border_w, stroke_fill=seg_border,
                )

                x += int(draw_overlay.textlength(seg_text, font=seg_font))

            y += line_height + line_spacing

    def get_text_width(self, text, kwargs):
        main_font = kwargs['font']
        raw_font_size = main_font['font_size']
        # Font Properties may wrap the scalar in a tuple (value, reset).
        # Plain widget output gives a bare int; older versions might
        # hand us a list/dict. Normalise via _resolve_property before
        # casting.
        main_font_size = _resolve_property(raw_font_size, 1, raw_font_size)
        try:
            main_font_size = int(main_font_size)
        except (TypeError, ValueError):
            main_font_size = 16  # sane fallback so we don't crash the layout calc

        main_font_file = main_font['font_file']
        font = self.get_font(main_font_file, main_font_size)
        return font.getlength(text)

    def calculate_text_position(self, text_width, text_height, x_offset, y_offset, kwargs):
        text_alignment = kwargs['canvas']['text_alignment'] 
        image_width = kwargs['canvas']['width']
        image_height = kwargs['canvas']['height']
        padding = kwargs['canvas']['padding']

        # Adjust the base position based on text_alignment and margin
        if text_alignment == "left top":
            base_x, base_y = padding, padding
        elif text_alignment == "left center":
            base_x, base_y = padding, padding + (image_height - text_height) // 2
        elif text_alignment == "left bottom":
            base_x, base_y = padding, image_height - text_height - padding
        elif text_alignment == "center top":
            base_x, base_y = (image_width - text_width) // 2, padding
        elif text_alignment == "center center":
            base_x, base_y = (image_width - text_width) // 2, (image_height - text_height) // 2
        elif text_alignment == "center bottom":
            base_x, base_y = (image_width - text_width) // 2, image_height - text_height - padding
        elif text_alignment == "right top":
            base_x, base_y = image_width - text_width - padding, padding
        elif text_alignment == "right center":
            base_x, base_y = image_width - text_width - padding, (image_height - text_height) // 2
        elif text_alignment == "right bottom":
            base_x, base_y = image_width - text_width - padding, image_height - text_height - padding
        else:  # Default to center center
            base_x, base_y = (image_width - text_width) // 2, (image_height - text_height) // 2

        # Apply offsets
        final_x = base_x + x_offset
        final_y = base_y + y_offset

        return final_x, final_y

    def process_image_for_output(self, image) -> torch.Tensor:
        i = ImageOps.exif_transpose(image)
        if i.mode == 'I':
            i = i.point(lambda i: i * (1 / 255))
        image = i.convert("RGB")
        image_np = np.array(image).astype(np.float32) / 255.0
        return torch.from_numpy(image_np)[None,]

    def calculate_text_block_size(self, draw, text, font, tagged_font, kwargs):
        lines = text.split('\n')
        max_width = 0
        font_height = font.getbbox('Agy')[3] # Height of a single line
        tagged_font_height = tagged_font.getbbox('Agy')[3]
        line_spacing = kwargs['canvas']['line_spacing']

        for line in lines:
            non_tagged_text, tagged_text = self.separate_text(line)
            line_width = draw.textlength(non_tagged_text, font=font)
            tagged_line_width = draw.textlength(tagged_text, font=tagged_font)

            total_line_width = line_width + tagged_line_width
            max_width = max(max_width, total_line_width)

        total_height = max(font_height, tagged_font_height) * len(lines) + line_spacing * (len(lines) - 1)
        return max_width, total_height

    def parse_text_input(self, text, kwargs):
        structured_format = False
        frame_text_dict = {}
        frame_count = kwargs['frame_count']
        skip_first_frames = kwargs.get('skip_first_frames', 0)
        
        # Filter out empty lines
        lines = [line for line in text.split('\n') if line.strip()]

        # Check if the input is in the structured format
        if all(':' in line and line.split(':')[0].strip().replace('"', '').isdigit() for line in lines):
            structured_format = True
            for line in lines:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    frame_number = str(int(parts[0].strip().replace('"', ''))-skip_first_frames)
                    text = parts[1].strip().replace('"', '').replace(',', '')
                    frame_text_dict[frame_number] = text
        else:
            # If not in structured format, use the input text for all frames
            frame_text_dict = {str(i): text for i in range(1, frame_count + 1)}

        return frame_text_dict, structured_format

    def cumulative_text(self, frame_text_dict, frame_count):
        cumulative_text_dict = {}
        last_text = ""

        for i in range(1, frame_count + 1):
            if str(i) in frame_text_dict:
                last_text = frame_text_dict[str(i)]
            cumulative_text_dict[str(i)] = last_text

        return cumulative_text_dict

    # TODO: ugly method has to be refactored
    def prepare_image(self, input_image, kwargs):

        image_width = kwargs['canvas']['width']
        image_height = kwargs['canvas']['height']
        padding = kwargs['canvas']['padding']
        background_color = kwargs['canvas']['background_color'] 

        if not isinstance(input_image, list):
            if isinstance(input_image, torch.Tensor):
                if input_image.dtype == torch.float:
                    input_image = (input_image * 255).byte()

                if input_image.ndim == 4:
                    processed_images = []
                    for img in input_image:
                        tensor_image = img.permute(2, 0, 1)
                        transform = transforms.ToPILImage()

                        try:
                            pil_image = transform(tensor_image)
                        except Exception as e:
                            from ..helpers.logger import logger
                            logger().error("Tensor to PIL conversion failed: %s", e)
                            raise

                        processed_images.append(pil_image.resize((image_width, image_height), Image.LANCZOS))
                    return processed_images
                elif input_image.ndim == 3 and input_image.shape[0] in [3, 4]:
                    tensor_image = input_image.permute(1, 2, 0)
                    pil_image = transforms.ToPILImage()(tensor_image)
                    return pil_image.resize((image_width, image_height), Image.LANCZOS)
                else:
                    raise ValueError(f"Input image tensor has an invalid shape or number of channels: {input_image.shape}")
            elif input_image != None:
                return input_image.resize((image_width, image_height), Image.LANCZOS)
            else:
                background_color_tuple = ImageColor.getrgb(background_color)
                return Image.new('RGB', (image_width, image_height), color=background_color_tuple)
        else:
            background_color_tuple = ImageColor.getrgb(background_color)
            return Image.new('RGB', (image_width, image_height), color=background_color_tuple)


# Module-level font cache. Reusing a FreeType font object across frames cuts
# PIL/Pillow load time dramatically (hundreds of ms → single-digit ms).
# 256 distinct (file, size) pairs is plenty for typical workflows.
@lru_cache(maxsize=256)
def _get_cached_font(font_file: str, font_size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_file, font_size)


def _normalize_color(value, fallback="white"):
    """Convert any colour value to a PIL-safe form (str / tuple of ints).

    PIL's ImageDraw.text() accepts:
      - a CSS colour string ('white', '#ff0000')
      - a 3- or 4-tuple of ints (R, G, B[, A])

    Our pipeline hands it a mixture of:
      - bare strings ('white', 'red') from widget defaults
      - 3-element lists / tuples from Preset Color Animations
        schedules — e.g. [255, 0, 0]
      - integers (rare — pre-existing widget quirk)

    PIL's getink explodes on a list with:
        TypeError: color must be int or tuple
    so we coerce list-of-ints -> tuple-of-ints here, well before
    the call.
    """
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple)):
        # Already a list/tuple of ints (likely an RGB colour).
        # Re-wrap as a tuple so PIL's getink accepts it.
        return tuple(value)
    return fallback


# Valid animation reset modes accepted by sequence_frame() in
# helpers/animation.py. Anything outside this set is treated as a
# raw colour / scalar (i.e. never matches the in-mode branches and
# falls through to the default return-1 — which silently holds the
# schedule at frame 1). We coerce weird inputs here.
_VALID_RESET_MODES = ("word", "line", "never", "looped", "pingpong")


def _normalize_reset_mode(value):
    """Coerce a reset-mode value into one of the strings sequence_frame
    recognises. The pipeline has been observed handing us things like
    'word$word' (the schedule JSON parser concatenated `$word` twice
    on a particular workflow path), which silently dropped the
    schedule into frame-1 hold because it doesn't match any of
    'word' / 'line' / 'never' / 'looped' / 'pingpong' in the
    sequence_frame branch.

    Strategy: take the first '$'-separated segment, then map any
    unknown token to 'word' (the safe default — animation restarts on
    every word change, which is the original behaviour the user
    wanted when they picked the Preset Color Animations node).
    """
    if value is None:
        return "word"
    s = str(value)
    # Drop anything past the first '$' (the second $word suffix bug).
    if "$" in s:
        s = s.split("$", 1)[0]
    s = s.strip()
    if s in _VALID_RESET_MODES:
        return s
    if not s:
        return "word"
    # Unknown mode → log once and fall back to 'word'.
    return "word"


# --------------------------------------------------------------------------- #
# Property resolution                                                          #
# --------------------------------------------------------------------------- #
def _resolve_property(schedule, seq_frame: int, fallback=None):
    """Pull a single scalar out of a TEXT_GRAPHIC_ELEMENT property.

    `font['<prop>']` may arrive in any of these shapes depending on
    whether `scheduled_values` was a keyframe list, a dict, empty, or
    absent:

      - ``(value, reset_mode)``        — common case, widget input
      - ``([{x,y}, ...], reset_mode)`` — keyframe schedule
      - ``"color_string"``              — raw color string
      - an unwrapped int / str         — defensive fallback

    Recursive: keep peeling until we hit a scalar. The recursion is
    bounded — we only re-enter on shapes we've explicitly handled.

    `seq_frame` is the position in the schedule we want to sample; for
    shapes that don't have one (scalar, single value, color string) it
    is ignored. `fallback` is returned when nothing useful could be
    extracted; if `fallback` is None we return `schedule` itself.
    """
    if schedule is None:
        return fallback
    if isinstance(schedule, tuple):
        return _resolve_property(schedule[0], seq_frame, fallback)
    if isinstance(schedule, list):
        if not schedule:
            return fallback
        # Distinguish schedule (list of {x, y} dicts) from a raw
        # colour value (list of [r, g, b] ints, or a single-element
        # flattened tuple). The old heuristic — "treat any non-empty
        # list as a schedule" — swallowed [r, g, b] arrays and
        # recursively peeled them down to the first int, which broke
        # font_color animation through Preset Color Animations.
        if all(isinstance(d, dict) and "y" in d for d in schedule):
            return _resolve_property(value_at(schedule, seq_frame), seq_frame, fallback)
        # Looks like a colour value (e.g. [255, 0, 0]) — return as-is.
        # PIL's ImageDraw.text accepts a 3-tuple / list for `fill=`.
        return schedule
    if isinstance(schedule, dict):
        if "y" in schedule or "value" in schedule:
            return schedule.get("y", schedule.get("value", fallback))
        if "font_file" in schedule:
            return schedule["font_file"]
        # Unknown dict shape — try to surface something scalar; if
        # none of the values is a scalar, fall back.
        for v in schedule.values():
            if isinstance(v, (str, int, float, bool)):
                return v
        return fallback
    return schedule


# --------------------------------------------------------------------------- #
# Tagged-text segmentation                                                    #
# --------------------------------------------------------------------------- #
_TAG_OPEN = "<tag>"
_TAG_CLOSE = "</tag>"


def _split_tagged_segments(text: str, main, tagged) -> list[tuple]:
    """Walk `text` once and emit a list of (segment_text, font, color, ...) tuples.

    A segment is a run of characters that share the same font + color.
    Switching at <tag>...</tag> boundaries. The two tuple args `main` and
    `tagged` hold the 8-tuple of (font, color, border, shadow, border_w,
    shadow_dx, shadow_dy) for each side.
    """
    out: list[tuple] = []
    buf: list[str] = []
    inside = False

    def flush():
        if not buf:
            return
        params = tagged if inside else main
        out.append(("".join(buf), *params))
        buf.clear()

    i = 0
    while i < len(text):
        if text.startswith(_TAG_OPEN, i):
            flush()
            inside = True
            i += len(_TAG_OPEN)
        elif text.startswith(_TAG_CLOSE, i):
            flush()
            inside = False
            i += len(_TAG_CLOSE)
        elif text[i] == "\n":
            flush()
            out.append(("\n", None, None, None, None, 0, 0, 0))
            i += 1
        else:
            buf.append(text[i])
            i += 1
    flush()
    return out


def _group_segments_by_line(segments: list[tuple]) -> list[tuple[str, list[tuple]]]:
    """Group flat segments into (line_text, [segments on that line]) pairs.

    Newline segments mark boundaries; segments on a single line stay in
    rendering order so the kerning / spacing between tagged and untagged
    text is preserved.
    """
    lines: list[tuple[str, list[tuple]]] = []
    current_text: list[str] = []
    current_segs: list[tuple] = []
    for seg in segments:
        if seg[0] == "\n":
            lines.append(("".join(current_text), current_segs))
            current_text, current_segs = [], []
        else:
            current_text.append(seg[0])
            current_segs.append(seg)
    if current_segs or current_text:
        lines.append(("".join(current_text), current_segs))
    return lines
