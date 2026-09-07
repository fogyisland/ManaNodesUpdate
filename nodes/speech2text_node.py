from __future__ import annotations

import functools
import json
import os
import re
import threading
import time

import numpy as np

# Whisper is the new ASR backend. It replaces wav2vec2 because:
#   - It auto-detects 99 languages (no need to pick a model per language)
#   - It outputs word-level timestamps natively (no manual grouping)
#   - It handles noisy / music audio far better than wav2vec2 XLSR,
#     which was trained on clean CommonVoice / LibriSpeech speech only.
#
# Whisper is imported lazily inside _load_whisper() so the module is
# cheap to import even when the user never runs the Speech Recognition
# node (e.g. on a server with no GPU).

# Curated Whisper model sizes. We expose only the openai-whisper model
# variants; users who want faster-whisper or whisper.cpp can fork the
# node. Numbers shown next to each entry are rough on-disk sizes so the
# user can predict download time before they commit.
WHISPER_MODELS: tuple[str, ...] = (
    "whisper-tiny",       # 75 MB  - fastest, lowest accuracy
    "whisper-base",       # 140 MB - decent English
    "whisper-small",      # 460 MB - balanced (DEFAULT)
    "whisper-medium",     # 1.5 GB - strong multilingual
    "whisper-large-v3",   # 3 GB   - state-of-the-art
)

# Human-readable description of each Whisper variant. Shown in the UI
# badge so the user can sanity-check what they picked.
WHISPER_MODEL_INFO: dict[str, str] = {
    "whisper-tiny":     "tiny (75 MB, fastest, lower accuracy)",
    "whisper-base":     "base (140 MB, decent English)",
    "whisper-small":    "small (460 MB, balanced - default)",
    "whisper-medium":   "medium (1.5 GB, strong multilingual)",
    "whisper-large-v3": "large-v3 (3 GB, best accuracy)",
}

# Approximate on-disk size of each curated Whisper model. Used in the
# progress log so the user knows whether to expect 30 seconds or
# 30 minutes for a first download. Numbers are conservative.
_WHISPER_SIZES_MB: dict[str, int] = {
    "whisper-tiny":     75,
    "whisper-base":     140,
    "whisper-small":    460,
    "whisper-medium":   1500,
    "whisper-large-v3": 3000,
}

# Languages Whisper can transcribe. "auto" lets the model detect.
# The subset below is shown as quick-pick suggestions in the node
# description; any ISO 639-1 code is still accepted as free text.
_LANGUAGE_HINTS: tuple[str, ...] = (
    "auto", "zh", "en", "ja", "ko", "es", "fr", "de", "ru", "ar",
)


# --------------------------------------------------------------------------- #
# Model loader                                                                #
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=2)
def _load_whisper(model_size: str):
    """Load and cache a Whisper model.

    The model_size argument is one of "tiny" / "base" / "small" /
    "medium" / "large-v3" (without the "whisper-" prefix that the UI
    uses - we strip it here). Weights are placed under
    models/Mana/SpeechRecognition/Whisper/ so the user can manage
    them like every other ComfyUI model. The first call downloads
    the .pt file; subsequent calls return from lru_cache instantly.

    Whisper's openai-whisper package supports `download_root=` since
    20231117 to override the default ~/.cache/whisper location. Older
    releases ignore the kwarg silently and still work.
    """
    from ..helpers.models import get_feature_models_dir
    from ..helpers.logger import logger

    bare = model_size.removeprefix("whisper-") if model_size.startswith("whisper-") else model_size
    cache_dir = get_feature_models_dir("SpeechRecognition")
    whisper_dir = os.path.join(cache_dir, "Whisper")

    # First-call diagnostic. Tell the user what we already have on
    # disk so they can verify a manual download landed in the right
    # place. Whisper doesn't use the HuggingFace snapshots/ layout,
    # so we just look for the bare .pt file the package writes.
    existing_pt = os.path.join(whisper_dir, f"{bare}.pt")
    if not os.path.isfile(existing_pt):
        size_mb = _WHISPER_SIZES_MB.get(model_size, 1500)
        logger().info(
            "Whisper dir %s is missing %s.pt; the model will be "
            "downloaded on first use (~%d MB, %.1f GB). If the "
            "download fails (firewall / slow link / no internet), "
            "download the file from "
            "https://github.com/openai/whisper and place it in:\n  %s",
            whisper_dir, bare, size_mb, size_mb / 1024, whisper_dir,
        )
    else:
        logger().info("Whisper: found cached %s.pt at %s", bare, existing_pt)

    # Periodic progress reporter. Whisper is small enough that this
    # only matters for large-v3, but a stuck download still benefits
    # from a periodic "still alive" log line.
    stop_flag = threading.Event()
    started = time.time()

    def _reporter():
        last_log = 0.0
        while not stop_flag.is_set():
            time.sleep(2.0)
            now = time.time()
            if now - last_log < 5.0:
                continue
            last_log = now
            size_mb = _WHISPER_SIZES_MB.get(model_size, 1500)
            size_gb = size_mb / 1024
            elapsed = now - started
            logger().info(
                "Whisper: still loading %s (%.1f GB). Elapsed: %.0fs. "
                "Cache: %s",
                model_size, size_gb, elapsed, whisper_dir,
            )

    reporter = threading.Thread(target=_reporter, daemon=True)
    reporter.start()

    try:
        import whisper  # openai-whisper package
        os.makedirs(whisper_dir, exist_ok=True)
        try:
            # openai-whisper >= 20231117 accepts download_root=
            model = whisper.load_model(bare, download_root=whisper_dir)
        except TypeError:
            # Older API: no download_root kwarg. Fall back to default
            # cache (~/.cache/whisper) - the user will still see the
            # weights, just not in our Mana folder.
            logger().warning(
                "openai-whisper is too old to support download_root=; "
                "falling back to ~/.cache/whisper. Upgrade with: "
                "pip install -U openai-whisper"
            )
            model = whisper.load_model(bare)
        stop_flag.set()
        elapsed = time.time() - started
        logger().info(
            "Whisper: loaded %s in %.1fs (cache: %s)",
            model_size, elapsed, whisper_dir,
        )
        return model
    except Exception as e:
        stop_flag.set()
        from ..helpers.models import MANA_MODELS_DIR
        logger().error(
            "Failed to load Whisper model '%s': %s\n"
            "Automatic download failed. To fix manually:\n"
            "  1. Make sure ffmpeg is installed and on PATH\n"
            "  2. pip install -U openai-whisper\n"
            "  3. If the model file is half-downloaded, delete:\n"
            "       %s\n"
            "  4. Re-run the node (the model will be re-downloaded)\n"
            "  5. If it still fails, download the .pt file from\n"
            "       https://github.com/openai/whisper/blob/main/whisper/__init__.py\n"
            "     and place it in:\n"
            "       %s",
            model_size, e, whisper_dir, whisper_dir,
        )
        raise


class speech2text:
    """Speech recognition node (Whisper + optional spell correction)."""

    DESCRIPTION = (
        "魔力节点 — 语音识别。Whisper 多语种转录（中/英/日/韩等 99 种语言）+ 字幕格式化。"
        "试试搜索：mana、魔力、语音、转录、字幕、识别、中文、whisper、whisper。"
        "**在 audio_file 文本框输入文件路径或 URL**。"
        " Mana Nodes — speech recognition. OpenAI Whisper transcription "
        "(99 languages auto-detected: Chinese, English, Japanese, Korean, "
        "Spanish, French, German, Russian, Arabic + 90 more) with caption "
        "formatting. Try searching: mana, speech, transcribe, whisper, "
        "stt, asr, caption, chinese, 中文. "
        "**Type a file path or URL into the audio_file text field.**"
    )

    CATEGORY = "💠 Mana Nodes"
    RETURN_TYPES = ("TRANSCRIPTION", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("transcription", "raw_string", "framestamps_string", "timestamps_string")
    FUNCTION = "run"
    OUTPUT_NODE = True

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # `audio_file` is a plain STRING - type or paste the
                # full path to an audio file (e.g. "H:\audio\myfile.wav")
                # or a URL ("https://example.com/audio.mp3"). librosa
                # loads the file directly. We deliberately don't
                # accept an AUDIO connection here because some
                # ComfyUI versions pass through empty (1-sample)
                # data from LoadAudio, which yielded 0-word output.
                "audio_file": ("STRING", {
                    "default": "",
                    "placeholder": "Path to audio file (e.g. H:\\audio\\myfile.wav)",
                }),
                "asr_model": (WHISPER_MODELS, {
                    "display": "dropdown",
                    "default": "whisper-small",  # balanced: 460 MB, decent multilingual
                }),
                "language": ("STRING", {
                    "default": "auto",
                    "placeholder": "auto (default) or ISO code: zh, en, ja, ko, es, fr, de, ru, ar ...",
                }),
                "spell_check_language": (cls._spell_check_choices(), {"default": "English", "display": "dropdown"}),
                "framestamps_max_chars": ("INT", {"default": 40, "step": 1, "display": "number"}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 60, "step": 1}),
                "transcription_mode": (("word", "line", "fill"), {"default": "fill", "display": "dropdown"}),
                "uppercase": ("BOOLEAN", {"default": True}),
            }
        }

    @staticmethod
    def _spell_check_choices() -> tuple[str, ...]:
        # pyspellchecker supports the Latin-alphabet languages below.
        # CJK / non-spaced languages short-circuit in _spell_correct
        # and skip spell-check entirely. We list them by their actual
        # name so the user sees a familiar label.
        return (
            "English", "Spanish", "French", "Portuguese", "German", "Italian",
            "Russian", "Arabic", "Basque", "Latvian", "Dutch",
            "Chinese (中文)", "Japanese (日本語)", "Korean (한국어)",
            "Hindi (हिन्दी)", "Thai (ไทย)", "Vietnamese (Tiếng Việt)",
            "None (skip spell check)",
        )

    # ------------------------------------------------------------------ #
    # Main                                                                #
    # ------------------------------------------------------------------ #
    def run(self, audio_file, asr_model: str, language: str,
            spell_check_language: str, framestamps_max_chars: int,
            fps: int = 30, transcription_mode: str = "fill",
            uppercase: bool = True, **_):
        audio = _load_audio(audio_file)
        lang = (language or "auto").strip().lower()
        if lang in ("", "auto", "detect"):
            lang = None  # let Whisper auto-detect
        words = self._transcribe(audio, asr_model, lang)
        words = _spell_correct(words, spell_check_language)

        # .upper() is a no-op for CJK characters but harmless; for
        # Latin-alphabet text it folds to caps. We keep the call so
        # the behavior matches the user's intent regardless of
        # whether the language has a concept of case.
        if uppercase:
            words = [(w.upper(), s, e) for w, s, e in words]

        # Final NaN sweep on the way out. Whisper occasionally
        # returns inf timestamps on the trailing padding tokens;
        # strip them so the four outputs are always well-formed for
        # downstream JSON parsers.
        import math
        words = [(w, s, e) for w, s, e in words
                 if math.isfinite(s) and math.isfinite(e)]

        return (
            {"transcription_data": words, "fps": fps, "transcription_mode": transcription_mode},
            " ".join(w for w, _, _ in words),
            _to_framestamps(words, fps, framestamps_max_chars),
            json.dumps(
                [{"word": w, "start_time": s, "end_time": e} for w, s, e in words],
                indent=2,
            ),
        )

    # ------------------------------------------------------------------ #
    # Transcribe (Whisper)                                                #
    # ------------------------------------------------------------------ #
    def _transcribe(self, audio_array, model_size: str, language: str | None):
        """Run Whisper on a numpy waveform. Returns [(word, start, end), ...]."""
        from ..helpers.logger import logger
        import math

        if audio_array is None:
            logger().warning("Whisper: audio_array is None - "
                             "audio_file likely didn't load. Returning [].")
            return []
        if len(audio_array) == 0:
            logger().warning("Whisper: audio has 0 samples. Returning [].")
            return []

        # Diagnostic info - printed once per run. Helps the user
        # figure out *why* they got 0 words: silent input, too-short
        # input, or unsupported sample rate.
        duration_s = len(audio_array) / 16_000
        peak = float(abs(audio_array).max()) if len(audio_array) else 0.0
        rms = float(np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))) if len(audio_array) else 0.0
        logger().info(
            "Whisper input: %d samples (%.2fs @ 16kHz), peak=%.3f, "
            "rms=%.4f, model=%s, language=%s",
            len(audio_array), duration_s, peak, rms,
            model_size, language or "auto",
        )

        if not math.isfinite(peak) or peak < 1e-6:
            logger().warning(
                "Whisper: audio is silent (peak=%.6f). Whisper needs "
                "audible speech to produce output.",
                peak,
            )
            return []

        # Whisper handles arbitrary lengths natively (it chunks
        # internally via the 30s window), so unlike wav2vec2 XLSR
        # we don't have to truncate. We do warn if the file is very
        # long so the user knows transcribe() will take a while.
        if duration_s > 600:  # 10 minutes
            logger().info(
                "Whisper: audio is %.1fs long; expect transcribe() "
                "to take 1-5 minutes depending on model size.",
                duration_s,
            )

        model = _load_whisper(model_size)
        try:
            # word_timestamps=True is the key flag - it makes Whisper
            # populate seg["words"] with {word, start, end, probability}.
            # We rely on this for both transcription_data and
            # framestamps_string outputs.
            #
            # fp16=False on CPU because fp16 inference only works on
            # CUDA; on CPU it silently downcasts and crashes. Whisper
            # auto-detects CUDA and uses fp16 there.
            result = model.transcribe(
                audio_array,
                language=language,
                word_timestamps=True,
                verbose=False,
                fp16=False,
            )
            words: list[tuple[str, float, float]] = []
            for seg in result.get("segments", []) or []:
                for w in seg.get("words", []) or []:
                    token = (w.get("word") or "").strip()
                    start = float(w.get("start", 0.0))
                    end = float(w.get("end", 0.0))
                    if not token:
                        continue
                    # Whisper sometimes returns inf for end-of-segment
                    # padding; filter here so the JSON output is clean.
                    if not math.isfinite(start) or not math.isfinite(end):
                        continue
                    # Word-tokens like "'s" or punctuation-only tokens
                    # add visual noise to subtitle output; skip them
                    # when they don't carry alphabetic content. We
                    # keep CJK characters and digit-only tokens.
                    if not _has_meaningful_content(token):
                        continue
                    words.append((token, start, end))
            logger().info(
                "Whisper: produced %d word(s) (detected language: %s)",
                len(words), result.get("language", "?"),
            )
            return words
        except Exception as e:
            logger().error("Whisper transcribe failed: %s", e)
            return []


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _has_meaningful_content(token: str) -> bool:
    """True if `token` carries at least one alphanumeric / CJK char.

    Whisper's word timestamps include tokens like "'s", "-", ".",
    which add visual noise to subtitle output without improving
    readability. CJK characters and digit-only tokens pass through.
    """
    if not token:
        return False
    for c in token:
        if c.isalnum():
            return True
        # CJK ranges
        code = ord(c[0]) if isinstance(c, str) else 0
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0x3040 <= code <= 0x30FF
            or 0xAC00 <= code <= 0xD7AF
        ):
            return True
    return False


def _load_audio(source, sr: int = 16_000):
    """Load an audio waveform as a 1-D numpy array at `sr` Hz.

    Three input shapes are supported:

      1. dict with "waveform" key  ->  AUDIO type (ComfyUI LoadAudio)
      2. string starting with http(s)://  ->  download to temp, load
      3. local file path string  ->  load directly with librosa
    """
    # Case 1: AUDIO dict from LoadAudio / VHS_AudioLoader / etc.
    if isinstance(source, dict) and "waveform" in source:
        waveform = source["waveform"]
        from ..helpers.logger import logger
        try:
            shape = tuple(waveform.shape)
        except AttributeError:
            shape = type(waveform).__name__
        logger().info(
            "Whisper AUDIO dict: waveform shape=%s, sample_rate=%s, keys=%s",
            shape,
            source.get("sample_rate"),
            list(source.keys()),
        )
        # waveform is (channels, samples) or (1, samples) or (samples,)
        if hasattr(waveform, "detach"):  # torch tensor
            arr = waveform.detach().cpu().float().numpy()
        else:
            arr = np.asarray(waveform, dtype=np.float32)
        if arr.ndim == 2:
            arr = arr[0]  # take first channel
        src_sr = int(source.get("sample_rate", sr))
        if src_sr != sr:
            arr = _resample_numpy(arr, src_sr, sr)
        return arr.astype(np.float32)

    # Cases 2 & 3: STRING (file path or URL)
    if not isinstance(source, str):
        from ..helpers.logger import logger
        logger().error(
            "audio_file must be a STRING (path/URL) or an AUDIO dict; "
            "got %s: %r",
            type(source).__name__, source,
        )
        raise ValueError(
            f"audio_file must be a STRING (path/URL) or an AUDIO dict; "
            f"got {type(source).__name__}: {source!r}"
        )

    if source.startswith(("http://", "https://")):
        # Download to a temp file, then load.
        import tempfile
        import requests as _requests
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            resp = _requests.get(source, stream=True, timeout=60)
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if chunk:
                    tmp.write(chunk)
            tmp_path = tmp.name
        try:
            audio, _ = _load_audio_file(tmp_path, sr)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return audio

    return _load_audio_file(source, sr)


def _load_audio_file(path: str, sr: int):
    """Load a local audio file with librosa. Gives a clear error if missing."""
    if not os.path.isfile(path):
        from ..helpers.logger import logger
        logger().error(
            "audio_file path not found: %s\n"
            "Check the file exists and the path is correct. "
            "Use forward slashes (H:/audio/file.wav) or escaped "
            "backslashes (H:\\\\audio\\\\file.wav) in the text field.",
            path,
        )
        raise FileNotFoundError(f"audio_file path not found: {path}")
    try:
        import librosa
        audio, _ = librosa.load(path, sr=sr)
        return audio
    except Exception as exc:
        from ..helpers.logger import logger
        logger().error(
            "librosa failed to load %s: %s\n"
            "Most likely causes: (1) unsupported audio format - "
            "convert with ffmpeg to 16kHz mono WAV; (2) ffmpeg not "
            "installed - install it and ensure it's on PATH; (3) "
            "corrupted file. Path: %s",
            path, exc, path,
        )
        raise ValueError(f"Could not load audio file: {path}") from exc


def _resample_numpy(arr: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Minimal resampler for already-decoded numpy audio.

    Avoids pulling in torchaudio just for the resample step.
    """
    from scipy.signal import resample
    if src_sr == dst_sr:
        return arr
    n_src = len(arr)
    n_dst = int(round(n_src * dst_sr / src_sr))
    return resample(arr, n_dst).astype(np.float32)


# ISO 639-1 codes for pyspellchecker. CJK / non-spaced languages map
# to None which short-circuits the spell-check step.
_LANGUAGE_TO_ISO: dict[str, str | None] = {
    "English": "en", "Spanish": "es", "French": "fr",
    "Portuguese": "pt", "German": "de", "Italian": "it",
    "Russian": "ru", "Arabic": "ar", "Basque": "eu",
    "Latvian": "lv", "Dutch": "nl",
    "Chinese (中文)": None,
    "Japanese (日本語)": None,
    "Korean (한국어)": None,
    "Hindi (हिन्दी)": None,
    "Thai (ไทย)": None,
    "Vietnamese (Tiếng Việt)": None,
    "None (skip spell check)": None,
}


def _spell_correct(words: list[tuple[str, float, float]], language: str):
    """Run pyspellchecker on each word. CJK / unknown languages short-circuit."""
    iso = _LANGUAGE_TO_ISO.get(language, "en")
    if iso is None:
        return words
    try:
        from spellchecker import SpellChecker
        spell = SpellChecker(language=iso)
    except ImportError:
        from ..helpers.logger import logger
        logger().info("SpellChecker not installed; skipping spell correction.")
        return words
    return [
        ((spell.correction(w) or w).upper(), s, e)
        for w, s, e in words
    ]


def _to_framestamps(words: list[tuple[str, float, float]], fps: int, max_chars: int) -> str:
    """Walk the words, building cumulative substrings of length <= max_chars.

    Skips words whose start_time is non-finite - these come from the
    model when the audio is too short, silent, or the input was padded
    with no real signal. Without this guard the JSON would contain
    "NaN": "..." which downstream nodes fail to parse.
    """
    import math
    lines: list[str] = []
    current = ""
    for word, start_time, _ in words:
        if not math.isfinite(start_time):
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            current = word
        lines.append(f'"{round(start_time * fps)}": "{current}",\n')
    return "".join(lines)
