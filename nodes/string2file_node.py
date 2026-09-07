"""Save/Preview Text node.

Writes a STRING to a .txt file under ComfyUI/output/ and renders it
in the inline preview pane. List-mode is deliberately not enabled
here — `string` and `filename_prefix` are scalar widgets, not batch
inputs.
"""
from __future__ import annotations

import os
from pathlib import Path

import folder_paths

from ..helpers.logger import logger


class string2file:

    DESCRIPTION = "魔力节点 — 保存/预览文本。把 STRING 写入 .txt 文件并显示预览。试试搜索：mana、魔力、文本、字符串、保存、文件。 Mana Nodes — save/preview text. Writes a STRING to a .txt file and shows an inline preview. Try searching: mana, text, string, save, file, txt, write."

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filename_prefix": ("STRING", {"default": "text\\text"}),
                "string": ("STRING", {"forceInput": True, "multiline": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    # Not a list-input node — `string` arrives as a single STRING.
    CATEGORY = "💠 Mana Nodes"
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "run"
    OUTPUT_NODE = True

    def run(self, string: str, filename_prefix: str = "text\\text",
            unique_id=None, extra_pnginfo=None, **_):
        full_path = self.construct_text_path(filename_prefix)

        try:
            with open(full_path, "w", encoding="utf-8") as file:
                file.write(string)
        except OSError as e:
            raise OSError(f"Failed to write {full_path}: {e}") from e

        # Tag the workflow with the saved text so reloading the saved
        # PNG/API payload shows what was written. extra_pnginfo is
        # either a list [{workflow: ...}] or a bare dict depending on
        # the ComfyUI version — handle both. unique_id is the same
        # shape (list in some versions, scalar in others).
        epi = extra_pnginfo[0] if isinstance(extra_pnginfo, list) else extra_pnginfo
        uid = unique_id[0] if isinstance(unique_id, list) else unique_id
        if uid and isinstance(epi, dict) and "workflow" in epi:
            workflow = epi["workflow"]
            node = next((x for x in workflow["nodes"] if str(x.get("id")) == str(uid)), None)
            if node is not None:
                node["widgets_values"] = [string]

        return {"ui": {"text": [string]}, "result": ()}

    def construct_text_path(self, filename_prefix: str) -> str:
        base_directory = folder_paths.get_output_directory()
        normalised_prefix = os.path.normpath(filename_prefix or "text\\text")
        full_path = os.path.join(base_directory, normalised_prefix)

        if not full_path.endswith(".txt"):
            full_path += ".txt"

        counter = 1
        while os.path.exists(full_path):
            new_filename = f"{normalised_prefix}_{counter}.txt"
            full_path = os.path.join(base_directory, new_filename)
            counter += 1

        Path(os.path.dirname(full_path)).mkdir(parents=True, exist_ok=True)
        return full_path
