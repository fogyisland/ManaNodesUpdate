import functools
import json
import os

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
    "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
    "facebook/wav2vec2-large-xlsr-53-chinese-zh-cn",
    "facebook/mms-1b-all",
    "facebook/mms-1b-fl102",
    "jonatasgrosman/wav2vec2-large-xlsr-53-english",
    "facebook/wav2vec2-base-960h",
    "facebook/wav2vec2-large-960h-lv60-self",
    "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
    "jonatasgrosman/wav2vec2-large-xlsr-53-korean",
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


@functools.lru_cache(maxsize=4)
def _load_wav2vec2(model_id: str) -> tuple:
    """Cache (model, processor) so we don't re-download GBs of weights per call."""
    return (
        Wav2Vec2ForCTC.from_pretrained(model_id),
        Wav2Vec2Processor.from_pretrained(model_id),
    )


class speech2text:
    """Speech recognition node (wav2vec2 + optional spell correction)."""

    DESCRIPTION = "魔力节点 — 语音识别。支持中文、英文、日文、韩文等多语种 wav2vec2 转录 + 字幕格式化。试试搜索：mana、魔力、语音、转录、字幕、识别、中文、中文识别。 Mana Nodes — speech recognition. Multilingual wav2vec2 transcription (Chinese, English, Japanese, Korean + 9 more languages) with caption-line formatting. Try searching: mana, speech, transcribe, whisper, wav2vec, stt, asr, caption, chinese, 中文."

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
                # `audio_file` is a free-form STRING so the user can
                # either type a path / URL or connect an output that
                # produces a path. The shape of the runtime value is
                # detected in _load_audio():
                #   - string starting with http(s) -> download
                #   - other string -> passed to librosa.load
                #   - dict with a "waveform" key (AUDIO type from
                #     LoadAudio / VHS) -> take channel 0, resample
                "audio_file": ("STRING", {
                    "display": "text",
                    "placeholder": "Path, URL, or connect an AUDIO output",
                }),
                "wav2vec2_model": (DEFAULT_WAV2VEC2_MODELS, {"display": "dropdown", "default": DEFAULT_WAV2VEC2_MODELS[0]}),
                "spell_check_language": (SPELL_CHECK_LANGUAGES, {"default": "English", "display": "dropdown"}),  # default set later based on wav2vec2 model selection
                "framestamps_max_chars": ("INT", {"default": 25, "step": 1, "display": "number"}),
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
        model, processor = _load_wav2vec2(model_id)
        inputs = processor(audio_array, sampling_rate=16_000, return_tensors="pt", padding=True)
        with torch.no_grad():
            predicted_ids = model(inputs.input_values).logits.argmax(dim=-1)
        return _group_tokens_into_words(_token_timestamps(predicted_ids, processor))


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _load_audio(source, sr: int = 16_000):
    """Load an audio waveform as a 1-D numpy array at `sr` Hz.

    Accepts three input shapes so the user can wire this node however
    they want:

      1. STRING — local file path. Passed straight to librosa.load.
      2. STRING — http(s)://... URL. Downloaded to a temp file, then
         read with librosa.load.
      3. dict with a "waveform" key (ComfyUI's AUDIO type, e.g. from
         LoadAudio). The waveform is a torch tensor of shape
         (channels, samples); we take channel 0 and trust the dict's
         sample_rate.
    """
    # Case 3: AUDIO dict from LoadAudio / VHS_AudioLoader / etc.
    if isinstance(source, dict) and "waveform" in source:
        waveform = source["waveform"]
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

    # Local file path
    try:
        audio, _ = librosa.load(source, sr=sr)
        return audio
    except Exception as exc:
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
    stride = int(0.02 * 16_000)
    out = []
    for idx in range(predicted_ids.shape[1]):
        token_id = predicted_ids[0, idx].item()
        if token_id == -100:
            continue
        out.append((
            processor.tokenizer.convert_ids_to_tokens(token_id),
            (stride * idx) / 16_000,
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
    """Walk the words, building cumulative substrings of length <= max_chars."""
    lines: list[str] = []
    current = ""
    for word, start_time, _ in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            current = word
        lines.append(f'"{round(start_time * fps)}": "{current}",\n')
    return "".join(lines)

        
