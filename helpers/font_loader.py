"""Font discovery and loading for Mana Nodes.

Centralizes the system + custom-font merge and the per-file/size
LRU cache so every node that needs a font agrees on the same instance.
"""
from __future__ import annotations

import os
from functools import lru_cache

from matplotlib import font_manager
from PIL import ImageFont

_CUSTOM_FONT_DIRS = ("font", "font_files")
_SUPPORTED_EXTS = (".ttf", ".otf", ".woff", ".woff2")


def _script_root() -> str:
    """`<repo>/nodes/<this>.py` -> `<repo>`."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(here)


def list_system_fonts() -> dict[str, str]:
    """All TrueType fonts matplotlib knows about, keyed by family name."""
    return {font.name: font.fname for font in font_manager.FontManager().ttflist}


def list_custom_fonts() -> dict[str, str]:
    """Fonts shipped in `<repo>/font` and `<repo>/font_files`.

    Keyed by file stem (e.g. "AURORA-PRO") so a missing system
    registration doesn't break the dropdown.
    """
    out: dict[str, str] = {}
    for dir_name in _CUSTOM_FONT_DIRS:
        full = os.path.join(_script_root(), dir_name)
        if not os.path.isdir(full):
            continue
        for f in os.listdir(full):
            path = os.path.join(full, f)
            if os.path.isfile(path) and f.endswith(_SUPPORTED_EXTS):
                out[os.path.splitext(f)[0]] = path
    return out


def combined_font_list() -> dict[str, str]:
    """System + custom fonts merged, custom wins on conflict."""
    return {**list_system_fonts(), **list_custom_fonts()}


@lru_cache(maxsize=256)
def get_font(font_file, font_size) -> ImageFont.FreeTypeFont:
    """LRU-cached FreeType font loader.

    Pillow's truetype constructor parses the font file (~50-200 ms on a
    cold call). Caching by (file, size) means a 200-frame render pays
    that cost once instead of 200 times.

    `font_file` and `font_size` are coerced via `str`/`int` so that an
    upstream caller that slipped through a list-shaped value doesn't
    blow up `lru_cache`'s hash with `TypeError: unhashable type: 'list'`.
    The error is reported with the original shape so it's still
    diagnosable.
    """
    if not isinstance(font_file, str):
        raise TypeError(
            f"get_font expected str font_file, got "
            f"{type(font_file).__name__}: {font_file!r}"
        )
    if not isinstance(font_size, int):
        raise TypeError(
            f"get_font expected int font_size, got "
            f"{type(font_size).__name__}: {font_size!r}"
        )
    return ImageFont.truetype(font_file, font_size)
