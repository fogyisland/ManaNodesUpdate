import functools
from transformers import pipeline
import scipy.io.wavfile
from pathlib import Path
import os
import folder_paths


@functools.lru_cache(maxsize=2)
def _get_bark_pipeline():
    """Cache the (huge) Bark pipeline so we don't re-download on every call."""
    return pipeline("text-to-speech", "suno/bark")


class text2speech:

    DESCRIPTION = "Mana Nodes — generate audio. Bark text-to-speech. Try searching: mana, tts, bark, speech, voice, audio."

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

