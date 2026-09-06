"""Shared utilities for Mana Nodes."""
from __future__ import annotations

import subprocess
import sys
from typing import Iterable

import numpy as np
import torch
from PIL import Image
from torch.nn.functional import pad


# --------------------------------------------------------------------------- #
# Tensor <-> PIL                                                              #
# --------------------------------------------------------------------------- #
def tensor2pil(image: torch.Tensor) -> Image.Image:
    """Convert a ComfyUI IMAGE tensor (H,W,C float in 0..1) to a PIL image."""
    arr = np.clip(255.0 * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def pil2tensor(image: Image.Image) -> torch.Tensor:
    """Convert a PIL image to a ComfyUI IMAGE tensor (1,H,W,C float in 0..1)."""
    arr = np.asarray(image).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


# --------------------------------------------------------------------------- #
# OpenCV self-install                                                          #
# --------------------------------------------------------------------------- #
def ensure_opencv() -> None:
    """Make sure cv2 is importable. Try a one-shot pip install if not.

    Idempotent: subsequent calls return immediately. Surfaces a clear
    error if the install fails rather than silently printing and
    crashing later in cv2.VideoCapture.
    """
    if getattr(ensure_opencv, "_cv2_ok", False):
        return

    try:
        import cv2  # noqa: F401
    except ImportError:
        pip_prefix = (
            [sys.executable, "-s", "-m", "pip", "install"]
            if "python_embedded" in sys.executable
            else [sys.executable, "-m", "pip", "install"]
        )
        # Prefer headless in containers / servers; fall back to full
        # package for users who already have a desktop install.
        last_exc: Exception | None = None
        for pkg in ("opencv-python-headless", "opencv-python"):
            try:
                subprocess.check_call(pip_prefix + [pkg])
                break
            except Exception as exc:
                last_exc = exc
        else:
            raise RuntimeError(
                "Failed to install opencv. Run `pip install opencv-python-headless` manually."
            ) from last_exc

    ensure_opencv._cv2_ok = True


# --------------------------------------------------------------------------- #
# Audio batching                                                               #
# --------------------------------------------------------------------------- #
def stack_audio_tensors(tensors: Iterable[torch.Tensor], mode: str = "pad") -> torch.Tensor:
    """Stack audio tensors (channels, samples) to a common length.

    Modes:
        pad / pad_r / pad_l : zero-pad shorter tensors
        trunc / trunc_r / trunc_l : truncate to the shortest
    """
    tensors = list(tensors)
    if not tensors:
        raise ValueError("stack_audio_tensors requires at least one tensor")

    sizes = [t.shape[-1] for t in tensors]
    if mode in {"pad_l", "pad_r", "pad"}:
        target = max(sizes)
        left_pad = mode == "pad_l"
        return torch.stack([
            pad(t, pad=(target - t.shape[-1], 0) if left_pad else (0, target - t.shape[-1]))
            for t in tensors
        ])
    if mode in {"trunc_l", "trunc_r", "trunc"}:
        target = min(sizes)
        right = mode == "trunc_r"
        return torch.stack([
            t[:, t.shape[-1] - target:] if right else t[:, :target]
            for t in tensors
        ])

    raise ValueError(f"unknown stack_audio_tensors mode: {mode!r}")
