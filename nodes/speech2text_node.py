import functools
import json

import librosa
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

# Curated list of wav2vec2 model ids. The old code queried HuggingFace
# over HTTP on every INPUT_TYPES call — that made opening the node
# pause for seconds and broke offline. Users can still type any other
# model id from HuggingFace into the dropdown.
DEFAULT_WAV2VEC2_MODELS: tuple[str, ...] = (
    # English
    "jonatasgrosman/wav2vec2-large-xlsr-53-english",
    "facebook/wav2vec2-base-960h",
    "facebook/wav2vec2-large-960h-lv60-self",
    # Chinese — Mandarin (Simplified)
    "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
    "facebook/wav2vec2-large-xlsr-53-chinese-zh-cn",
    # Multilingual (covers Chinese + 100+ other languages)
    "facebook/mms-1b-all",
    "facebook/mms-1b-fl102",
    # European
    "jonatasgrosman/wav2vec2-large-xlsr-53-spanish",
    "jonatasgrosman/wav2vec2-large-xlsr-53-french",
    "jonatasgrosman/wav2vec2-large-xlsr-53-german",
    "jonatasgrosman/wav2vec2-large-xlsr-53-italian",
    "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese",
    "jonatasgrosman/wav2vec2-large-xlsr-53-russian",
    # Japanese
    "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
    # Korean
    "jonatasgrosman/wav2vec2-large-xlsr-53-korean",
    # Arabic
    "jonatasgrosman/wav2vec2-large-xlsr-53-arabic",
)

# Languages the SpellChecker (pyspellchecker) supports. Chinese is in the
# wav2vec2 model list but NOT here because pyspellchecker only handles
# space-separated Latin-alphabet languages; Chinese has no concept of
# word-boundary spelling correction.
SPELL_CHECK_LANGUAGES: tuple[str, ...] = (
    "English", "Spanish", "French", "Portuguese", "German", "Italian",
    "Russian", "Arabic", "Basque", "Latvian", "Dutch",
    # Pseudo-languages for the languages that the wav2vec2 model
    # list covers but spell-check doesn't:
    "None (skip spell check)",
)

# ISO 639-1 codes for pyspellchecker. "None (skip spell check)" maps to
# None which short-circuits the spell-check step in _spell_correct.
LANGUAGE_TO_ISO: dict[str, str | None] = {
    "English": "en", "Spanish": "es", "French": "fr",
    "Portuguese": "pt", "German": "de", "Italian": "it",
    "Russian": "ru", "Arabic": "ar", "Basque": "eu",
    "Latvian": "lv", "Dutch": "nl",
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
                "audio_file": ("STRING", {"display": "text", "forceInput": True}),
                "wav2vec2_model": (DEFAULT_WAV2VEC2_MODELS, {"display": "dropdown", "default": DEFAULT_WAV2VEC2_MODELS[0]}),
                "spell_check_language": (SPELL_CHECK_LANGUAGES, {"default": "English", "display": "dropdown"}),
                "framestamps_max_chars": ("INT", {"default": 25, "step": 1, "display": "number"}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 60, "step": 1}),
                "transcription_mode": (TRANSCRIPTION_MODES, {"default": "fill", "display": "dropdown"}),
                "uppercase": ("BOOLEAN", {"default": True}),
            }
        }

    def run(self, audio_file: str, wav2vec2_model: str, spell_check_language: str,
            framestamps_max_chars: int, fps: int = 30, transcription_mode: str = "fill",
            uppercase: bool = True, **_):
        audio = _load_audio(audio_file)
        words = self._transcribe(audio, wav2vec2_model)
        words = _spell_correct(words, spell_check_language)
        if not uppercase:
            words = [(w.lower(), s, e) for w, s, e in words]

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
def _load_audio(file_path: str, sr: int = 16_000):
    try:
        audio, _ = librosa.load(file_path, sr=sr)
        return audio
    except Exception as exc:
        raise ValueError(f"Could not load audio file: {file_path}") from exc


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

        
