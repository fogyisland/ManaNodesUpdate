"""Model storage path for Mana Nodes.

Centralises the on-disk location where large model weights
(wav2vec2, future Whisper, etc.) are cached. We deliberately put
this under `<ComfyUI>/models/Mana/` rather than the default
HuggingFace cache (~/.cache/huggingface) so the user can:

  - See what models are installed
  - Pre-download weights manually (no internet on the box, slow
    link, or just want to control versions)
  - Back up the directory alongside other ComfyUI model files
  - Delete individual models without nuking a global cache

The path is read from ComfyUI's folder_paths module so it works
regardless of where the user installed ComfyUI.
"""
from __future__ import annotations

import os

# ComfyUI's folder_paths is the canonical way to find the models dir.
# Import lazily so this helper can be reused by tests that don't
# have ComfyUI installed.
def _get_models_root() -> str:
    try:
        import folder_paths  # type: ignore
        roots = folder_paths.get_folder_paths("models")
        if roots:
            return roots[0]
    except Exception:
        pass
    # Fallback: assume we're inside ComfyUI/custom_nodes/<this>
    # and the models dir is two levels up + "models".
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "models"))


MANA_MODELS_DIR = os.path.join(_get_models_root(), "Mana")


def ensure_mana_models_dir() -> str:
    """Create models/Mana/ if it doesn't exist. Returns the path.

    The directory is shared across all Mana Nodes (Speech Recognition,
    future Whisper node, etc.) so each extension doesn't get its own
    duplicate copy of the same 1-2 GB wav2vec2 weights.
    """
    os.makedirs(MANA_MODELS_DIR, exist_ok=True)
    return MANA_MODELS_DIR
