"""Shared utilities for Mana Nodes."""
from __future__ import annotations

import os
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


# --------------------------------------------------------------------------- #
# ffmpeg self-install                                                          #
# --------------------------------------------------------------------------- #
def _local_ffmpeg_path() -> str:
    """Where we keep a copy of the ffmpeg binary inside this package.

    Lives at `<ComfyUI-Mana-Nodes>/app/ffmpeg(.exe)`. Copying here
    instead of using imageio-ffmpeg's pip site-packages location
    means the binary goes away when the user removes the
    custom_nodes directory — no orphan file left behind in the
    Python venv.
    """
    pkg_root = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."
    ))
    app_dir = os.path.join(pkg_root, "app")
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    return os.path.join(app_dir, exe_name)


def ensure_ffmpeg(logger=None) -> str | None:
    """Make sure an `ffmpeg` binary is reachable. Returns the resolved path.

    Resolution order:

      1. `<ComfyUI-Mana-Nodes>/app/ffmpeg(.exe)` (copied here on first
         run from imageio-ffmpeg so it ships-and-unships with the
         custom_node directory)
      2. System PATH (fastest, latest version)
      3. `imageio-ffmpeg` static binary (~30 MB, ships with no system
         dependency) — copied into app/ on first use

    `imageio-ffmpeg` is declared in requirements.txt so pip installs
    it when the custom_node is installed. If for some reason it's
    missing, we log a clear error rather than pip-installing on
    the fly (silent pip installs inside ComfyUI's embedded Python
    behave unpredictably).

    Returns the path to a working ffmpeg binary, or None if no
    source is available (in which case the caller surfaces the
    error to the user).

    Notes:
      - openai-whisper itself only needs ffmpeg when transcribe() is
        given a file path. We feed numpy arrays (decoded by librosa)
        so model.transcribe() never shells out. However, librosa's
        compressed-format decoder (mp3 / m4a / aac / ogg) DOES shell
        out to ffmpeg via audioread, so mp3 input still needs this.
      - Cached after first successful resolve to avoid repeated PATH
        lookups on every Speech Recognition run.
    """
    if getattr(ensure_ffmpeg, "_resolved", False):
        return ensure_ffmpeg._path

    import shutil

    local = _local_ffmpeg_path()

    # 1. Already copied into the package's app/ directory.
    if os.path.isfile(local):
        ensure_ffmpeg._resolved = True
        ensure_ffmpeg._path = local
        _add_to_path(os.path.dirname(local))
        return local

    # 2. System ffmpeg on PATH.
    found = shutil.which("ffmpeg")
    if found:
        ensure_ffmpeg._resolved = True
        ensure_ffmpeg._path = found
        return found

    # 3. imageio-ffmpeg static binary. Required by requirements.txt;
    #    if it's missing the user bypassed the normal install flow.
    try:
        import imageio_ffmpeg
    except ImportError:
        if logger is not None:
            logger().error(
                "ffmpeg not found on PATH and imageio-ffmpeg is not "
                "installed. This package is declared in "
                "requirements.txt and should install automatically.\n"
                "Manual fix: pip install imageio-ffmpeg\n"
                "Or install a system ffmpeg:\n"
                "  Windows: choco install ffmpeg\n"
                "  macOS:   brew install ffmpeg\n"
                "  Linux:   sudo apt install ffmpeg\n"
                "Whisper can still transcribe WAV files via librosa, "
                "but mp3 / m4a / aac input will fail without ffmpeg."
            )
        return None

    src = imageio_ffmpeg.get_ffmpeg_exe()
    if not src or not os.path.isfile(src):
        if logger is not None:
            logger().error(
                "imageio-ffmpeg is installed but get_ffmpeg_exe() "
                "returned no usable path: %r", src,
            )
        return None

    # Copy the static binary into the package's app/ directory so
    # future runs (and future re-installs of the custom_node) find
    # it without re-downloading or depending on the venv.
    try:
        os.makedirs(os.path.dirname(local), exist_ok=True)
        shutil.copy(src, local)
        if logger is not None:
            logger().info(
                "Copied ffmpeg static binary from %s to %s (%.1f MB). "
                "It will be removed when you uninstall the Mana "
                "Nodes custom_node directory.",
                src, local, os.path.getsize(local) / (1024 * 1024),
            )
    except (OSError, PermissionError) as exc:
        # Couldn't copy (read-only install, permission, etc.) — fall
        # back to the imageio-ffmpeg source location for this session.
        if logger is not None:
            logger().warning(
                "Could not copy ffmpeg into app/ (%s); using imageio-ffmpeg "
                "source location %s for this session.", exc, src,
            )
        ensure_ffmpeg._resolved = True
        ensure_ffmpeg._path = src
        _add_to_path(os.path.dirname(src))
        return src

    ensure_ffmpeg._resolved = True
    ensure_ffmpeg._path = local
    _add_to_path(os.path.dirname(local))
    return local


def _add_to_path(directory: str) -> None:
    """Prepend `directory` to PATH so subprocess calls find the binary."""
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep)
    if directory not in parts:
        os.environ["PATH"] = directory + os.pathsep + current


# Backwards-compat alias used by speech2text_node.
def _ensure_ffmpeg_available(logger=None):
    return ensure_ffmpeg(logger)
