"""Combine Video node.

Stitch a batch of ComfyUI IMAGE tensors into an MP4 and (optionally)
mux in an audio file.
"""
from __future__ import annotations

import os
from pathlib import Path

import folder_paths
import numpy as np
import torch
from moviepy import AudioFileClip, ImageSequenceClip

from ..helpers.logger import logger
from ..helpers.utils import tensor2pil


class audio2video:
    """Combine image batch + optional audio into an MP4."""

    DESCRIPTION = "魔力节点 — 合成视频。把 IMAGE 批次拼成 MP4，可选混音。试试搜索：mana、魔力、视频、合成、渲染、mp4。 Mana Nodes — combine video. Stitch an IMAGE batch into an MP4, optionally mux in audio. Try searching: mana, video, render, mp4, mux, combine."

    CATEGORY = "💠 Mana Nodes"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_file",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"display": "text", "forceInput": True}),
                "filename_prefix": ("STRING", {"default": "video\\video"}),
            },
            "optional": {
                "audio_file": ("STRING", {"display": "text", "forceInput": True}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 60, "step": 1}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    # ------------------------------------------------------------------ #
    # Main pipeline                                                       #
    # ------------------------------------------------------------------ #
    def run(self, images, filename_prefix: str, audio_file: str | None = None,
            fps: int = 30, **_):
        pil_frames = [_to_pil(frame) for frame in images]
        full_path = _unique_video_path(filename_prefix)
        self._write_video(pil_frames, fps, audio_file, full_path)
        preview = self._preview_metadata(full_path)
        return {"ui": {"videos": preview}, "result": ((True, full_path),)}

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _write_video(pil_frames, fps, audio_file, out_path):
        numpy_frames = [np.asarray(f) for f in pil_frames]
        clip = ImageSequenceClip(numpy_frames, fps=fps)
        if audio_file:
            try:
                clip = clip.with_audio(AudioFileClip(audio_file))
            except (OSError, ValueError) as exc:
                # Bad path / corrupt file / decoder mismatch. The
                # video frames are still valid — log loudly and
                # continue without audio rather than fail the whole
                # export.
                logger().warning(
                    "Combine Video: skipped audio (%s); writing "
                    "video-only output to %s.", exc, out_path,
                )
        clip.write_videofile(out_path, codec="libx264")

    @staticmethod
    def _preview_metadata(full_path: str) -> list[dict]:
        filename = os.path.basename(full_path)
        parent = os.path.dirname(full_path)
        subfolder = "" if os.path.basename(parent) == "output" else os.path.basename(parent)
        return [{"filename": filename, "subfolder": subfolder, "type": "output", "format": "video/mp4"}]


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _to_pil(frame) -> "PIL.Image.Image":
    """Normalize a single ComfyUI IMAGE frame (H,W,C float 0-1) to PIL."""
    if not isinstance(frame, torch.Tensor):
        # Allow numpy / PIL inputs in case upstream shape changes.
        return tensor2pil(torch.as_tensor(frame))
    return tensor2pil(frame)


def _unique_video_path(prefix: str) -> str:
    base_dir = folder_paths.get_output_directory()
    full = os.path.join(base_dir, os.path.normpath(prefix))
    if not full.endswith(".mp4"):
        full += ".mp4"
    counter = 1
    while os.path.exists(full):
        full = os.path.join(base_dir, f"{prefix}_{counter}.mp4")
        counter += 1
    Path(os.path.dirname(full)).mkdir(parents=True, exist_ok=True)
    return full
