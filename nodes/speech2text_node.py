import functools
import json
import os
import threading
import time

import librosa
import numpy as np
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

# Curated list of wav2vec2 model ids. The old code queried HuggingFace
# over HTTP on every INPUT_TYPES call — that made opening the node
# pause for seconds and broke offline. Users can still type any other
# model id from HuggingFace into the dropdown.
# Curated list of wav2vec2 model ids. The old code queried HuggingFace
# over HTTP on every INPUT_TYPES call — that made opening the node
# pause for seconds and broke offline. Users can still type any other
# model id from HuggingFace into the dropdown.
#
# We display the model id verbatim in the dropdown but pair each with
# a language hint in MODEL_LANGUAGES so the JS side can show a
# "currently selected: Mandarin Chinese" indicator next to the
# spell_check_language default.
DEFAULT_WAV2VEC2_MODELS: tuple[str, ...] = (
    # English (DEFAULT — most common; this is what [0] picks)
    "jonatasgrosman/wav2vec2-large-xlsr-53-english",
    "facebook/wav2vec2-base-960h",
    "facebook/wav2vec2-large-960h-lv60-self",
    # Multilingual (good fallback when language unknown)
    "facebook/mms-1b-all",
    "facebook/mms-1b-fl102",
    # CJK
    "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
    "facebook/wav2vec2-large-xlsr-53-chinese-zh-cn",
    "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
    "jonatasgrosman/wav2vec2-large-xlsr-53-korean",
    # European
    "jonatasgrosman/wav2vec2-large-xlsr-53-spanish",
    "jonatasgrosman/wav2vec2-large-xlsr-53-french",
    "jonatasgrosman/wav2vec2-large-xlsr-53-german",
    "jonatasgrosman/wav2vec2-large-xlsr-53-italian",
    "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese",
    "jonatasgrosman/wav2vec2-large-xlsr-53-russian",
    "jonatasgrosman/wav2vec2-large-xlsr-53-arabic",
)

# Human-readable language labels for each model id. Used by the JS
# extension to surface "Selected: Mandarin Chinese" in the node UI
# and to drive the spell_check_language default below.
MODEL_LANGUAGES: dict[str, str] = {
    "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn": "Chinese (中文)",
    "facebook/wav2vec2-large-xlsr-53-chinese-zh-cn": "Chinese (中文)",
    "facebook/mms-1b-all": "Multilingual 1000+",
    "facebook/mms-1b-fl102": "Multilingual 100+",
    "jonatasgrosman/wav2vec2-large-xlsr-53-english": "English",
    "facebook/wav2vec2-base-960h": "English",
    "facebook/wav2vec2-large-960h-lv60-self": "English",
    "jonatasgrosman/wav2vec2-large-xlsr-53-japanese": "Japanese (日本語)",
    "jonatasgrosman/wav2vec2-large-xlsr-53-korean": "Korean (한국어)",
    "jonatasgrosman/wav2vec2-large-xlsr-53-spanish": "Spanish",
    "jonatasgrosman/wav2vec2-large-xlsr-53-french": "French",
    "jonatasgrosman/wav2vec2-large-xlsr-53-german": "German",
    "jonatasgrosman/wav2vec2-large-xlsr-53-italian": "Italian",
    "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese": "Portuguese",
    "jonatasgrosman/wav2vec2-large-xlsr-53-russian": "Russian",
    "jonatasgrosman/wav2vec2-large-xlsr-53-arabic": "Arabic",
}

# All languages the user can pick. pyspellchecker only supports the
# top half (Latin-alphabet); the bottom half (CJK etc.) all map to
# None in LANGUAGE_TO_ISO which short-circuits the spell-check step.
# We list them by their actual name rather than "None" so the user
# sees a familiar label when their audio is Chinese / Japanese / etc.
SPELL_CHECK_LANGUAGES: tuple[str, ...] = (
    # Latin-alphabet (actual spell check)
    "English", "Spanish", "French", "Portuguese", "German", "Italian",
    "Russian", "Arabic", "Basque", "Latvian", "Dutch",
    # CJK + others (no spell check available; pyspellchecker can't
    # word-boundary these languages)
    "Chinese (中文)", "Japanese (日本語)", "Korean (한국어)",
    "Hindi (हिन्दी)", "Thai (ไทย)", "Vietnamese (Tiếng Việt)",
    "Arabic (already listed)",  # alias kept for backwards compat
    "None (skip spell check)",  # catch-all
)

# ISO 639-1 codes for pyspellchecker. CJK / non-spaced languages map
# to None which short-circuits the spell-check step in _spell_correct.
LANGUAGE_TO_ISO: dict[str, str | None] = {
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
    "Arabic (already listed)": "ar",
    "None (skip spell check)": None,
}

TRANSCRIPTION_MODES: tuple[str, ...] = ("word", "line", "fill")


# Approximate on-disk size of each curated model. Used in the
# progress log so the user knows whether to expect 1 minute or
# 30 minutes for a first download. Numbers are conservative.
_MODEL_SIZES_MB: dict[str, int] = {
    "jonatasgrosman/wav2vec2-large-xlsr-53-english": 1200,
    "facebook/wav2vec2-base-960h": 360,
    "facebook/wav2vec2-large-960h-lv60-self": 1200,
    "facebook/mms-1b-all": 3500,
    "facebook/mms-1b-fl102": 1500,
    "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn": 1200,
    "facebook/wav2vec2-large-xlsr-53-chinese-zh-cn": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-japanese": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-korean": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-spanish": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-french": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-german": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-italian": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-russian": 1200,
    "jonatasgrosman/wav2vec2-large-xlsr-53-arabic": 1200,
}


@functools.lru_cache(maxsize=4)
def _load_wav2vec2(model_id: str) -> tuple:
    """Cache (model, processor) so we don't re-download GBs of weights per call.

    Weights go under <ComfyUI>/models/Mana/SpeechRecognition/
    (see helpers.models.get_feature_models_dir). The user can
    pre-place the HuggingFace cache structure there manually to
    skip the download — useful when the box has no internet, has
    a slow link, or sits behind a firewall that blocks
    huggingface.co.
    """
    from ..helpers.models import get_feature_models_dir, list_cached_models
    from ..helpers.logger import logger
    cache_dir = get_feature_models_dir("SpeechRecognition")

    # First-call diagnostic: list what we already have on disk so
    # the user can verify their manual download landed in the right
    # place. Only printed the very first time this runs (the lru_cache
    # means the actual download happens at most once per model_id).
    existing = list_cached_models("SpeechRecognition")
    if not existing:
        org, name = model_id.split("/", 1) if "/" in model_id else ("", model_id)
        snapshot_dir = f"{cache_dir}{os.sep}models--{org}--{name}{os.sep}snapshots{os.sep}<hash>"
        size_mb = _MODEL_SIZES_MB.get(model_id, 1500)
        logger().info(
            "Mana models dir %s is empty; %s will be downloaded "
            "on first use (~%d MB, %.1f GB). If the download fails "
            "(firewall / slow link / no internet), download manually "
            "from https://huggingface.co/%s and place all files in:\n"
            "  %s",
            cache_dir, model_id, size_mb, size_mb / 1024,
            model_id, snapshot_dir,
        )
    else:
        # Tell the user what we found so they can verify it's the
        # right model. Saves a debugging round when the model is
        # cached but stale.
        for path in existing:
            logger().info("Speech recognition: found cached model at %s", path)

    # Periodic progress reporter so the user sees that the node is
    # alive while transformers is downloading. Without this the green
    # execution bar just sits there for 1-5 minutes on a 1.2 GB
    # model with no indication of what's happening.
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
            size_mb = _MODEL_SIZES_MB.get(model_id, 1500)
            size_gb = size_mb / 1024
            elapsed = now - started
            # Rough bandwidth estimate: 1 MB/s = 8 Mbps. A slow
            # connection (256 Kbps) is 0.03 MB/s.
            logger().info(
                "Speech recognition: still loading %s (%.1f GB). "
                "Elapsed: %.0fs. Cache: %s",
                model_id, size_gb, elapsed, cache_dir,
            )

    reporter = threading.Thread(target=_reporter, daemon=True)
    reporter.start()

    try:
        result = (
            Wav2Vec2ForCTC.from_pretrained(model_id, cache_dir=cache_dir),
            Wav2Vec2Processor.from_pretrained(model_id, cache_dir=cache_dir),
        )
        stop_flag.set()
        elapsed = time.time() - started
        logger().info(
            "Speech recognition: loaded %s in %.1fs (cache: %s)",
            model_id, elapsed, cache_dir,
        )
        return result
    except Exception as e:
        stop_flag.set()
        # Network failure, firewall, missing local cache, etc. Print
        # a clear error pointing the user at the exact HuggingFace
        # URL and the local path to drop the weights into. Without
        # this, the user sees a stack trace and has to guess.
        from ..helpers.models import MANA_MODELS_DIR
        logger().error(
            "Failed to load wav2vec2 model '%s': %s\n"
            "Automatic download failed. To fix manually:\n"
            "  1. Open https://huggingface.co/%s in a browser\n"
            "  2. Click 'Files and versions' -> download all files "
            "(config.json, model.safetensors, *.json, vocab.json)\n"
            "  3. Create the directory:\n"
            "       %s/models--%s/snapshots/<any-hash>/\n"
            "  4. Drop the downloaded files into that directory\n"
            "  5. Re-run the node",
            model_id, e, model_id, MANA_MODELS_DIR,
            model_id.split("/")[0] if "/" in model_id else model_id,
        )
        raise


class speech2text:
    """Speech recognition node (wav2vec2 + optional spell correction)."""

    DESCRIPTION = "魔力节点 — 语音识别。支持中文、英文、日文、韩文等多语种 wav2vec2 转录 + 字幕格式化。试试搜索：mana、魔力、语音、转录、字幕、识别、中文、中文识别。**在 audio_file 文本框输入文件路径或 URL**。 Mana Nodes — speech recognition. Multilingual wav2vec2 transcription (Chinese, English, Japanese, Korean + 9 more languages) with caption-line formatting. Try searching: mana, speech, transcribe, whisper, wav2vec, stt, asr, caption, chinese, 中文. **Type a file path or URL into the audio_file text field.**"

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
                # `audio_file` is a plain STRING — type or paste the
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
                "wav2vec2_model": (DEFAULT_WAV2VEC2_MODELS, {"display": "dropdown", "default": DEFAULT_WAV2VEC2_MODELS[0]}),
                "spell_check_language": (SPELL_CHECK_LANGUAGES, {"default": "English", "display": "dropdown"}),  # default set later based on wav2vec2 model selection
                "framestamps_max_chars": ("INT", {"default": 40, "step": 1, "display": "number"}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 60, "step": 1}),
                "transcription_mode": (TRANSCRIPTION_MODES, {"default": "fill", "display": "dropdown"}),
                "uppercase": ("BOOLEAN", {"default": True}),
            }
        }

    def run(self, audio_file, wav2vec2_model: str, spell_check_language: str,
            framestamps_max_chars: int, fps: int = 30, transcription_mode: str = "fill",
            uppercase: bool = True, **_):
        audio = _load_audio(audio_file)
        words = self._transcribe(audio, wav2vec2_model)
        words = _spell_correct(words, spell_check_language)
        # .upper() is a no-op for CJK characters but harmless; for
        # Latin-alphabet text it folds to caps. We keep the call so
        # the behavior matches the user's intent regardless of
        # whether the language has a concept of case.
        if uppercase:
            words = [(w.upper(), s, e) for w, s, e in words]

        # Final NaN sweep on the way out. Even with the per-stage
        # filters above, defense in depth: strip any residual
        # non-finite timestamps so the four outputs are always
        # well-formed for downstream Text to Image / JSON parsers.
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
    # Internals                                                           #
    # ------------------------------------------------------------------ #
    def _transcribe(self, audio_array, model_id: str):
        # Defensive: empty / silent / too-short audio can crash the
        # model and produce NaN logits. Bail out early with an empty
        # list so downstream nodes see a well-defined empty result
        # instead of a stack of "NaN" timestamps.
        from ..helpers.logger import logger
        import math

        if audio_array is None:
            logger().warning("Speech recognition: audio_array is None — "
                             "LoadAudio likely didn't connect. Returning [].")
            return []
        if len(audio_array) == 0:
            logger().warning("Speech recognition: audio has 0 samples. Returning [].")
            return []

        # Diagnostic info — printed once per run. Helps the user
        # figure out *why* they got 0 words: silent input, too-short
        # input, or all-NaN model output.
        from ..helpers.models import get_feature_models_dir
        cache_dir = get_feature_models_dir("SpeechRecognition")
        duration_s = len(audio_array) / 16_000
        peak = float(abs(audio_array).max()) if len(audio_array) else 0.0
        rms = float(np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))) if len(audio_array) else 0.0
        logger().info(
            "Speech recognition input: %d samples (%.2fs @ 16kHz), peak=%.3f, rms=%.4f, model=%s, cache_dir=%s",
            len(audio_array), duration_s, peak, rms, model_id, cache_dir,
        )

        if not math.isfinite(peak) or peak < 1e-6:
            logger().warning(
                "Speech recognition: audio is silent (peak=%.6f). "
                "wav2vec2 needs audible speech to produce output.",
                peak,
            )
            return []

        # wav2vec2 XLSR models are trained on ~15-30s clips. Longer
        # audio gets sliced or produces NaN in the attention. Cap at
        # 30s and emit a warning so the user knows why we truncated.
        if duration_s > 30:
            logger().info(
                "Speech recognition: audio is %.1fs long, taking the "
                "first 30s (wav2vec2 XLSR context window). For longer "
                "files, split the audio with ffmpeg first.",
                duration_s,
            )
            audio_array = audio_array[:16_000 * 30]

        model, processor = _load_wav2vec2(model_id)
        try:
            inputs = processor(audio_array, sampling_rate=16_000, return_tensors="pt", padding=True)
            with torch.no_grad():
                predicted_ids = model(inputs.input_values).logits.argmax(dim=-1)
            words = _group_tokens_into_words(_token_timestamps(predicted_ids, processor))
            logger().info("Speech recognition: produced %d word(s)", len(words))
            return words
        except Exception as e:
            logger().error("Speech recognition failed: %s", e)
            return []


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _load_audio(source, sr: int = 16_000):
    """Load an audio waveform as a 1-D numpy array at `sr` Hz.

    The canonical input is an AUDIO dict from ComfyUI's LoadAudio
    node ({"waveform": Tensor[channels, samples], "sample_rate": int}).
    We also accept a few legacy / fallback shapes so the function is
    robust to other ComfyUI versions:

      1. dict with "waveform" key  ->  AUDIO type (the main case)
      2. string starting with http(s)://  ->  download to temp, load
      3. local file path string  ->  load directly with librosa
    """
    # Case 3: AUDIO dict from LoadAudio / VHS_AudioLoader / etc.
    if isinstance(source, dict) and "waveform" in source:
        waveform = source["waveform"]
        # Diagnostic: log exactly what we got so the user can see
        # if LoadAudio produced empty data or a different shape.
        from ..helpers.logger import logger
        try:
            shape = tuple(waveform.shape)
        except AttributeError:
            shape = type(waveform).__name__
        logger().info(
            "Speech recognition AUDIO dict: waveform shape=%s, "
            "sample_rate=%s, keys=%s",
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
        # Resample if needed (librosa doesn't take numpy — we use scipy)
        src_sr = int(source.get("sample_rate", sr))
        if src_sr != sr:
            arr = _resample_numpy(arr, src_sr, sr)
        return arr.astype(np.float32)

    # Cases 1 & 2: STRING (file path or URL)
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
            audio, _ = librosa.load(tmp_path, sr=sr)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return audio

    # Local file path. Check existence first so the user gets a
    # clear error message instead of librosa's cryptic FileNotFound.
    if not os.path.isfile(source):
        from ..helpers.logger import logger
        logger().error(
            "audio_file path not found: %s\n"
            "Check the file exists and the path is correct. "
            "Use forward slashes (H:/audio/file.wav) or escaped "
            "backslashes (H:\\\\audio\\\\file.wav) in the text field.",
            source,
        )
        raise FileNotFoundError(f"audio_file path not found: {source}")

    try:
        audio, _ = librosa.load(source, sr=sr)
        return audio
    except Exception as exc:
        from ..helpers.logger import logger
        logger().error(
            "librosa failed to load %s: %s\n"
            "Most likely causes: (1) unsupported audio format — "
            "convert with ffmpeg to 16kHz mono WAV; (2) ffmpeg not "
            "installed — install it and ensure it's on PATH; (3) "
            "corrupted file. Path: %s",
            source, exc, source,
        )
        raise ValueError(f"Could not load audio file: {source}") from exc


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


def _token_timestamps(predicted_ids: torch.Tensor, processor) -> list[tuple[str, float]]:
    """Approximate timestamps: 20ms stride for 16 kHz audio."""
    import math
    stride = int(0.02 * 16_000)
    out = []
    for idx in range(predicted_ids.shape[1]):
        token_id = predicted_ids[0, idx].item()
        if token_id == -100:
            continue
        time = (stride * idx) / 16_000
        # The model occasionally emits NaN/inf timestamps for the
        # padding tail; filter them so the JSON output stays clean.
        if not math.isfinite(time):
            continue
        out.append((
            processor.tokenizer.convert_ids_to_tokens(token_id),
            time,
        ))
    return out


def _is_cjk_char(c: str) -> bool:
    """True if `c` is a Chinese / Japanese / Korean character."""
    if not c:
        return False
    code = ord(c[0])
    return (
        0x4E00 <= code <= 0x9FFF        # CJK Unified Ideographs
        or 0x3400 <= code <= 0x4DBF     # CJK Extension A
        or 0x3040 <= code <= 0x30FF     # Hiragana + Katakana
        or 0xAC00 <= code <= 0xD7AF     # Hangul Syllables
    )


def _group_tokens_into_words(timestamps: list[tuple[str, float]]) -> list[tuple[str, float, float]]:
    """Group sub-word tokens into words.

    Three tokenizer families are supported:

      - SentencePiece ("▁" prefix marks word start) — most XLSR models
      - Wav2Vec2 ("|" or " " as word boundary) — base/large-960h
      - CJK models (each character is its own word; no boundary marker)
        — Chinese / Japanese / Korean XLSR models

    For CJK, every character both closes the previous word and starts
    a new one, so the model output of "你好世界" becomes four separate
    one-character words.
    """
    words: list[tuple[str, float, float]] = []
    current: list[tuple[str, float]] = []

    def _flush():
        nonlocal current
        if current:
            words.append((_join(current), current[0][1], current[-1][1]))
            current = []

    for token, time in timestamps:
        if token == "<pad>":
            # Hard word boundary.
            _flush()
            continue

        # Strip the SentencePiece word-start marker. The remainder is
        # the actual content of the token (e.g. "▁Hello" -> "Hello").
        starts_new_word = token.startswith("▁") or token in ("|", " ")
        content = token[1:] if starts_new_word else token
        if not content:
            # Pure boundary marker with no content (e.g. just "▁").
            _flush()
            continue

        if _is_cjk_char(content[0]):
            # CJK: each character is its own word.
            _flush()
            words.append((content, time, time))
            continue

        if starts_new_word:
            _flush()

        current.append((content, time))

    _flush()
    return words


def _join(tokens: list[tuple[str, float]]) -> str:
    return "".join(t[0].lstrip("▁") for t in tokens)


def _spell_correct(words: list[tuple[str, float, float]], language: str):
    # Chinese / Japanese / Korean have no concept of word-level spelling
    # correction. The UI offers "None (skip spell check)" for these; we
    # also accept any unknown language code and bail safely.
    iso = LANGUAGE_TO_ISO.get(language, "en")
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

    Skips words whose start_time is NaN/inf — these come from the model
    when the audio is too short, silent, or the input was padded with
    no real signal. Without this guard the JSON would contain
    "NaN": "..." which downstream nodes (Text to Image) fail to parse.
    """
    import math
    lines: list[str] = []
    current = ""
    for word, start_time, _ in words:
        # Defensive: skip NaN / inf timestamps. Word itself is kept
        # if we have any valid earlier word so the output isn't empty.
        if not math.isfinite(start_time):
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            current = word
        lines.append(f'"{round(start_time * fps)}": "{current}",\n')
    return "".join(lines)

        
