"""Split Video node.

Reads a video file from the input/video directory, extracts a frame range
as ComfyUI IMAGE tensors, and (optionally) writes the matching audio
slice to the output directory.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

import cv2
import folder_paths
import torch
from moviepy import VideoFileClip  # moviepy 2.x top-level API
from PIL import Image

from ..helpers.utils import ensure_opencv, pil2tensor


class video2audio:
    """Read a video range, return frames + audio path."""

    DESCRIPTION = "Mana Nodes — split video. Extract a frame range as IMAGE tensors and the matching audio slice. Try searching: mana, video, frames, extract, ffmpeg, split."

    # Class-level cache so INPUT_TYPES doesn't re-scan the directory
    # every time a node is dropped on the canvas.
    _input_video_cache: list[str] | None = None

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    # ComfyUI metadata                                                    #
    # ------------------------------------------------------------------ #
    CATEGORY = "💠 Mana Nodes"
    RETURN_TYPES = ("IMAGE", "STRING", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("images", "audio_file", "fps", "frame_count", "height", "width")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": (cls._list_input_videos(), {"mana_video_upload": True}),
                "frame_limit": ("INT", {"default": 16, "min": 1, "max": 10240, "step": 1}),
                "frame_start": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF, "step": 1}),
                "filename_prefix": ("STRING", {"default": "audio\\audio"}),
            },
            "optional": {},
        }

    @classmethod
    def IS_CHANGED(cls, video, *args, **kwargs):
        video_path = folder_paths.get_annotated_filepath(video)
        m = hashlib.sha256()
        with open(video_path, "rb") as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, video, *args, **kwargs):
        if not folder_paths.exists_annotated_filepath(video):
            return f"Invalid video file: {video}"
        return True

    # ------------------------------------------------------------------ #
    # Main pipeline                                                       #
    # ------------------------------------------------------------------ #
    def run(self, video: str, frame_limit: int, frame_start: int,
            filename_prefix: str, **_):
        video_path = folder_paths.get_annotated_filepath(video)
        frames, width, height = self._extract_frames(video_path, frame_limit, frame_start)
        if not frames:
            raise ValueError("No frames could be extracted from the video.")

        audio_path, fps = self._extract_audio(
            Path(video_path), frame_limit, frame_start, filename_prefix
        )
        if audio_path is None:
            audio_path = "No audio track in the video."

        return (torch.cat(frames, dim=0), audio_path, fps, len(frames), height, width)

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #
    @classmethod
    def _list_input_videos(cls) -> list[str]:
        if cls._input_video_cache is not None:
            return cls._input_video_cache
        input_dir = os.path.join(folder_paths.get_input_directory(), "video")
        os.makedirs(input_dir, exist_ok=True)
        cls._input_video_cache = sorted(
            f"video/{f}"
            for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f))
        )
        return cls._input_video_cache

    @staticmethod
    def _extract_frames(video_path: str, frame_limit: int, frame_start: int):
        ensure_opencv()
        cap = cv2.VideoCapture(video_path)
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)

            frames = []
            for _ in range(frame_limit):
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(pil2tensor(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))))
            return frames, width, height
        finally:
            cap.release()

    @staticmethod
    def _extract_audio(video_path: Path, frame_limit: int, frame_start: int,
                       filename_prefix: str):
        with VideoFileClip(str(video_path)) as video:
            fps = video.fps
            if video.audio is None:
                return None, fps

            start = frame_start / fps
            end = (frame_start + frame_limit) / fps
            audio = video.subclipped(start, end).audio

            out_path = _unique_output_path(
                folder_paths.get_output_directory(), filename_prefix, ".wav"
            )
            audio.write_audio(out_path)
            return str(Path(out_path).resolve()), fps


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _unique_output_path(base_dir: str, prefix: str, ext: str) -> str:
    """Build a unique output path: <base>/<prefix><ext>, or with _N suffix on collision."""
    full = os.path.join(base_dir, os.path.normpath(prefix))
    if not full.endswith(ext):
        full += ext
    counter = 1
    while os.path.exists(full):
        full = os.path.join(base_dir, f"{prefix}_{counter}{ext}")
        counter += 1
    Path(os.path.dirname(full)).mkdir(parents=True, exist_ok=True)
    return full
