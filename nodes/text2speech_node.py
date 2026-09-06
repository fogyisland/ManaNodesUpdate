import functools
from transformers import pipeline
import scipy.io.wavfile
from pathlib import Path
import os
import folder_paths

# Bark weights are ~5 GB; cache them under models/Mana/TextToSpeech/
# so the user can manage them like every other ComfyUI model.
from ..helpers.models import get_feature_models_dir

# Standard Bark model id. Centralised so a future "switch model"
# feature only has to change one place.
BARK_MODEL_ID = "suno/bark"


@functools.lru_cache(maxsize=2)
def _get_bark_pipeline():
    """Cache the (huge) Bark pipeline so we don't re-download on every call.

    Weights go to <ComfyUI>/models/Mana/TextToSpeech/ via
    cache_dir. The first call downloads ~5 GB; subsequent calls
    return immediately. The user can also pre-place the
    HuggingFace cache structure there manually to skip the download.
    """
    cache_dir = get_feature_models_dir("TextToSpeech")
    return pipeline("text-to-speech", BARK_MODEL_ID, cache_dir=cache_dir)


class text2speech:

    DESCRIPTION = "魔力节点 — 生成音频。Bark 文字转语音。试试搜索：mana、魔力、语音合成、tts、语音、音频。 Mana Nodes — generate audio. Bark text-to-speech. Try searching: mana, tts, bark, speech, voice, audio."

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
            "text": ("STRING", {"display": "text", "placeholder": "[laughter]\n[laughs]\n[sighs]\n[music]\n[gasps]\n[clears throat]\n— or … for hesitations\n♪ for song lyrics\nCapitalization for emphasis of a word\nMAN/WOMAN: for bias towards speaker", "multiline": True}),                "filename_prefix": ("STRING", {"display": "text", "default": "audio\\audio"})
            },
        }

    CATEGORY = "💠 Mana Nodes"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("audio_file",)
    FUNCTION = "run"
    OUTPUT_NODE = True

    def run(self, text, **kwargs):
        # filename_prefix comes through **kwargs because it's not in the
        # explicit signature; support both list and scalar (INPUT_IS_LIST).
        prefix = kwargs.get('filename_prefix', 'audio\\audio')
        if isinstance(prefix, list):
            prefix = prefix[0]

        full_path = os.path.join(folder_paths.get_output_directory(), os.path.normpath(prefix))
        if not full_path.endswith('.wav'):
            full_path += '.wav'
        Path(os.path.dirname(full_path)).mkdir(parents=True, exist_ok=True)

        synthesizer = _get_bark_pipeline()
        speech = synthesizer(text, forward_params={"do_sample": True})

        audio_waveform = speech['audio']
        if audio_waveform.ndim == 2:
            audio_waveform = audio_waveform.T

        scipy.io.wavfile.write(full_path, rate=speech['sampling_rate'], data=audio_waveform)

        full_path_to_audio = os.path.abspath(full_path)
        return (full_path_to_audio,)

