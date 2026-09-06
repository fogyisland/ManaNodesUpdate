"""Model storage path for Mana Nodes.

Centralises the on-disk location where large model weights are
cached. We deliberately put these under `<ComfyUI>/models/Mana/`
rather than the default HuggingFace cache (~/.cache/huggingface) so
the user can:

  - See what models are installed
  - Pre-download weights manually (no internet on the box, slow
    link, or just want to control versions)
  - Back up the directory alongside other ComfyUI model files
  - Delete individual models without nuking a global cache

**Per-feature subdirectories**: each Mana feature (Speech Recognition,
future Whisper node, etc.) gets its own subdirectory so the user can
manage them independently. For example:

  - models/Mana/SpeechRecognition/   <- wav2vec2 weights
  - models/Mana/Whisper/             <- future
  - models/Mana/OCR/                 <- future

The `get_feature_models_dir(name)` helper creates the subdir on
demand. HuggingFace's `from_pretrained(cache_dir=...)` will then
place the standard `models--<org>--<name>/snapshots/<hash>/...`
structure inside that subdir.

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


# Parent directory for ALL Mana-managed model weights. Each feature
# gets its own subdirectory under this; never write weights directly
# into MANA_MODELS_DIR (they'd be mixed across features).
MANA_MODELS_DIR = os.path.join(_get_models_root(), "Mana")


def get_feature_models_dir(feature: str) -> str:
    """Return the on-disk directory for a specific Mana feature.

    Creates the subdirectory on first call. Callers pass this to
    transformers' `cache_dir=` so each feature's weights live in
    their own namespace, e.g.:

        # Speech Recognition
        cache = get_feature_models_dir("SpeechRecognition")

        # Future Whisper node
        cache = get_feature_models_dir("Whisper")

    The `feature` name should match the class name (without "Node"
    suffix) so the user can find a feature's weights by looking at
    the directory name. Names are case-sensitive and should be
    CamelCase to match the node class.
    """
    if not feature or not isinstance(feature, str):
        raise ValueError(f"feature name must be a non-empty string, got {feature!r}")
    path = os.path.join(MANA_MODELS_DIR, feature)
    os.makedirs(path, exist_ok=True)
    return path


# Backwards-compat alias: older code that called ensure_mana_models_dir
# (e.g. before per-feature split) still gets a working directory.
def ensure_mana_models_dir() -> str:
    """Create models/Mana/ if it doesn't exist. Returns the path.

    Prefer get_feature_models_dir(name) for new code; this function
    is kept only for backwards compatibility.
    """
    os.makedirs(MANA_MODELS_DIR, exist_ok=True)
    return MANA_MODELS_DIR


def list_cached_models(feature: str | None = None) -> list[str]:
    """Return paths of model snapshots currently on disk.

    If `feature` is given, only that feature's directory is scanned.
    Returns the absolute path of every `snapshots/<hash>/` directory,
    which is what HuggingFace's from_pretrained() looks for. The
    user can use this to verify a manually-downloaded model landed
    in the right place.
    """
    base = (os.path.join(MANA_MODELS_DIR, feature)
            if feature else MANA_MODELS_DIR)
    if not os.path.isdir(base):
        return []
    found: list[str] = []
    for repo in os.listdir(base):
        repo_path = os.path.join(base, repo)
        snaps = os.path.join(repo_path, "snapshots")
        if not os.path.isdir(snaps):
            continue
        for hash_dir in os.listdir(snaps):
            full = os.path.join(snaps, hash_dir)
            if os.path.isdir(full) and os.listdir(full):
                found.append(full)
    return sorted(found)


def report() -> str:
    """Human-readable summary of where every feature's models live.

    Useful as a sanity check after a fresh install or after a
    manual model drop. Logs each feature directory and the models
    currently cached under it.
    """
    from .logger import logger
    lines = [f"Mana models root: {MANA_MODELS_DIR}"]
    for feature in sorted(os.listdir(MANA_MODELS_DIR)) if os.path.isdir(MANA_MODELS_DIR) else []:
        fdir = os.path.join(MANA_MODELS_DIR, feature)
        cached = list_cached_models(feature)
        if cached:
            lines.append(f"  {feature}/  ({len(cached)} cached)")
            for c in cached:
                lines.append(f"    - {c}")
        else:
            lines.append(f"  {feature}/  (empty)")
    report_text = "\n".join(lines)
    logger().info("\n" + report_text)
    return report_text
