# Mana Nodes - Feature Guide

A collection of custom nodes for ComfyUI focused on text-based content
creation: dynamic captions, animated typography, speech-to-text, and
video/audio utility nodes.

---

## Node List

To find these in ComfyUI's node search, type any of the search aliases
listed below. The class names (used in workflows / API calls) are also
listed.

| Display Name | Class Name | Search Aliases |
|--------------|------------|----------------|
| ✒️ Text to Image Generator | `Text to Image Generator` | `text`, `caption`, `subtitle`, `typography`, `mana` |
| 🆗 Font Properties | `Font Properties` | `font`, `text style`, `mana font` |
| 🖼️ Canvas Properties | `Canvas Properties` | `canvas`, `background`, `image size` |
| ⏰ Scheduled Values | `Scheduled Values` | `animation`, `keyframe`, `timeline`, `chart` |
| 🌈 Preset Color Animations | `Preset Color Animations` | `color`, `palette`, `rainbow`, `gradient` |
| 🎤 Speech Recognition | `Speech Recognition` | `whisper`, `speech`, `transcribe`, `stt`, `asr`, `caption`, `中文` |
| 📣 Generate Audio | `Generate Audio` | `tts`, `bark`, `speech`, `voice` |
| 🎞️ Split Video | `Split Video` | `video`, `frames`, `extract`, `ffmpeg` |
| 🎥 Combine Video | `Combine Video` | `video`, `render`, `mp4`, `mux` |
| 📝 Save/Preview Text | `Save/Preview Text` | `text`, `string`, `save`, `file`, `txt` |

> **Search tip:** ComfyUI's node search is fuzzy. If you can't find a
> node by class name, try the **display name** (e.g. `Text to Image
> Generator`) or any of the search aliases (e.g. `caption`).

---

## 1. Text to Image Generator ✒️

The main node. Renders text onto a sequence of frames as IMAGE
tensors (compatible with all downstream ComfyUI image nodes).

### Inputs

| Input | Type | Notes |
|-------|------|-------|
| `font` | TEXT_GRAPHIC_ELEMENT | Required. From a Font Properties node. |
| `canvas` | CANVAS_SETTINGS | Required. From a Canvas Properties node. |
| `text` | STRING | Multiline. Plain text or JSON timeline (see below). |
| `frame_count` | INT | Number of frames to render. |
| `transcription` | TRANSCRIPTION | Optional. From Speech Recognition. |
| `highlight_font` | TEXT_GRAPHIC_ELEMENT | Optional. Highlights tagged words. |
| `skip_first_frames` | INT | Optional. Skip the first N frames of a JSON timeline. |

### Plain text vs JSON timeline

Plain text is rendered identically on every frame:

```
Hello world
```

JSON timeline format renders different text per frame:

```
"1": "Hello",
"10": "Hello world",
"20": "Goodbye"
```

Frames between keyframes inherit the most recent text (cumulative
build-up).

### Outputs

- `images` - ComfyUI IMAGE tensor batch.
- `framestamps_string` - JSON-line string (useful for round-tripping
  to the Speech Recognition node).

---

## 2. Font Properties 🆗

Defines the visual style of a piece of text. Connect its output to
`font` on the Text to Image Generator.

### Widgets

- `font_file` (dropdown) - System + custom fonts in `font_files/`.
- `font_size` (int) - Pixel size. Animatable via Scheduled Values.
- `font_color` (color string) - CSS color or `rgb(r,g,b)`. Animatable.
- `kerning` (int) - Spacing between characters.
- `border_width` (int) - Text outline thickness.
- `border_color` (color string) - Animatable.
- `shadow_color` (color string) - Animatable.
- `shadow_offset_x` / `shadow_offset_y` (int) - Shadow offset.
- `x_offset` / `y_offset` (int) - Position on canvas. Animatable.
- `rotation` (int) - Degrees, -360 to 360. Animatable.
- `rotation_anchor_x` / `rotation_anchor_y` (int) - Pivot point.
- `scheduled_values` (STRING, optional) - Wire a Scheduled Values or
  Preset Color Animations output here to drive any animatable
  property. Format: `JSON-keyframes$reset_mode`. Flat lists broadcast
  to every animatable property; per-property dicts let you target
  individual ones.

---

## 3. Canvas Properties 🖼️

Defines the output canvas.

### Widgets

- `width` / `height` (int) - Output dimensions in pixels.
- `background_color` (color string) - Default background.
- `text_alignment` (dropdown) - 3x3 grid: `left/center/right top/center/bottom`.
- `padding` (int) - Space between image border and text.
- `line_spacing` (int) - Space between lines of text.
- `images` (IMAGE, optional) - Use an image batch as the background
  instead of a solid color.

---

## 4. Scheduled Values ⏰

Interactive keyframe timeline. Click on the chart to add keyframes,
edit values, and interpolate between them.

### Widgets

- `frame_count` / `value_range` - Chart bounds.
- `easing_type` (dropdown) - `linear`, `easeInQuad`, ..., `exponential`.
- `step_mode` (single/auto) - Tick density.
- `animation_reset` (word/line/never/looped/pingpong) - When the
  animation restarts.

### Output

- `scheduled_values` - String of `JSON-keyframes$reset_mode`. Connect
  to Font Properties' `scheduled_values` input.

### Keyframe persistence

Keyframes are saved to browser `localStorage` (per-node). IDs are
stable per ComfyUI node id, so reopening a workflow keeps your data.

---

## 5. Preset Color Animations 🌈

Curated color palettes animated over N frames. Same wire format as
Scheduled Values.

### Available presets

- `rainbow` - full spectrum
- `sunset`, `sky`, `ocean`, `forest`, `fire`, `earth` - themed
- `grey` - grayscale ramp

---

## 6. Speech Recognition 🎤

Transcribes an audio file using OpenAI Whisper and emits a
transcription object that the Text to Image Generator can consume
directly. Whisper auto-detects 99 languages (Chinese, English,
Japanese, Korean, Spanish, French, German, Russian, Arabic + 90
more) so a single model covers everything. Output quality on
noisy / song audio is far better than the old wav2vec2 backend
because Whisper was trained on a much broader audio distribution.

### Inputs

- `audio_file` (STRING) - Path or URL.
- `asr_model` (dropdown) - Whisper size:
  - `whisper-tiny` (75 MB, fastest, lower accuracy)
  - `whisper-base` (140 MB, decent English)
  - `whisper-small` (460 MB, balanced) — **default**
  - `whisper-medium` (1.5 GB, strong multilingual)
  - `whisper-large-v3` (3 GB, best accuracy)
- `language` (STRING, default `auto`) - Force a specific ISO 639-1
  code (`zh`, `en`, `ja`, ...). Leave `auto` to let Whisper detect.
- `spell_check_language` - Optional spell correction (requires
  `pyspellchecker`). CJK / non-spaced languages short-circuit.
- `framestamps_max_chars` - Max characters per caption line.
- `fps` - Frames per second (default 30).
- `transcription_mode` - `word` (one word per line), `line` (one
  phrase per line), `fill` (cumulative build-up).
- `uppercase` - Render in all caps.

### Outputs

- `transcription` - TRANSCRIPTION object (consumed by Text to Image).
- `raw_string` - Plain text.
- `framestamps_string` - JSON-line timeline for the text field.
- `timestamps_string` - Word + start_time + end_time per word.

### Performance

The Whisper model is cached after the first run under
`models/Mana/SpeechRecognition/Whisper/`. Subsequent transcriptions
of the same model size only pay the inference cost.

### Requirements

WAV / FLAC input needs no extra setup — librosa uses soundfile
internally. For mp3 / m4a / aac / ogg input, librosa needs an
`ffmpeg` binary. The node calls `helpers.utils.ensure_ffmpeg()`
on first run; resolution order is:

  1. `<ComfyUI-Mana-Nodes>/app/ffmpeg(.exe)` — if the user already
     placed one there, or a previous run copied one in
  2. System PATH (`apt install ffmpeg` / `brew install ffmpeg` /
     `choco install ffmpeg`)
  3. `imageio-ffmpeg` (auto-installed via pip if missing), copied
     into `app/ffmpeg(.exe)` for future runs

The copied binary in `app/` ships-and-unships with the
custom_node directory, so uninstalling Mana Nodes also drops the
~80 MB ffmpeg.exe.

---

## 7. Generate Audio 📣

Text-to-speech via the Bark model. Output is a WAV file written to
`ComfyUI/output/`.

### Inputs

- `text` (STRING, multiline) - Supports Bark's special tokens
  (`[laughter]`, `MAN:`, `♪ lyrics ♪`, etc.).
- `filename_prefix` (STRING) - Output path.

### Performance

The Bark pipeline is cached after the first run.

---

## 8. Split Video 🎞️

Extracts a frame range from a video file as ComfyUI IMAGE tensors
and optionally writes the matching audio slice.

### Inputs

- `video` (dropdown) - Files in `ComfyUI/input/video/`. Use the
  upload button to add new ones.
- `frame_limit` / `frame_start` - Range to extract.
- `filename_prefix` - Where to write the audio.

### Outputs

- `images` - IMAGE tensor batch.
- `audio_file` - Path to the WAV.
- `fps`, `frame_count`, `height`, `width` - Metadata.

---

## 9. Combine Video 🎥

Stitches an IMAGE batch into an MP4 and optionally muxes in an
audio file. The result is previewable inline in the node.

### Inputs

- `images` (IMAGE) - Required.
- `filename_prefix` (STRING) - Default `video\\video`.
- `audio_file` (STRING, optional).
- `fps` (INT, default 30).

---

## 10. Save/Preview Text 📝

Renders a STRING value in a read-only preview pane inside the node
and writes it to a text file.

### Inputs

- `string` (STRING) - The text to save.
- `filename_prefix` (STRING) - Default `text\\text`. Saved under
  `ComfyUI/output/`.

---

## Quick start workflows

### 1. Static caption

```
[Canvas Properties] -> canvas ->
                          [Text to Image Generator] -> images
[Font Properties]  -> font   ->
[text: "Hello"]    -> text   ->
[frame_count: 60]  -> frame_count
```

### 2. Word-by-word karaoke from audio

```
[audio file] -> [Speech Recognition (mode: word, uppercase: True)]
                                       -> transcription
[Font Properties]  -> font     -> [Text to Image Generator]
[Canvas Properties] -> canvas        (highlight_font: another Font)
[text: "{}"]        -> text          -> images
[frame_count: 240]  -> frame_count
```

### 3. Animated text

```
[Scheduled Values] -> scheduled_values -> [Font Properties]
                                            -> font
                                          [Text to Image Generator]
[Canvas Properties] -> canvas             -> images
[text: "BOOM"]      -> text
[frame_count: 60]   -> frame_count
```

### 4. Color-cycling caption

```
[Preset Color Animations] -> scheduled_colors -> [Font Properties]
                                                    -> font (font_color)
                                                  [Text to Image Generator]
[Canvas Properties] -> canvas                    -> images
[Font Properties]  -> font
[text: "RAINBOW"]   -> text
[frame_count: 60]   -> frame_count
```

---

## Requirements

- Python 3.10 / 3.11 / 3.12
- Pillow >= 10.0.0
- torch >= 2.0
- transformers >= 4.30
- moviepy >= 1.0.3 (1.x and 2.x supported)
- opencv-python-headless >= 4.8
- librosa, matplotlib, scipy, requests, pyspellchecker

See `requirements.txt` for the full pinned list.

---

## Troubleshooting

**Node not found in search:** Try the **display name** (e.g. `Text to
Image Generator`) instead of the class name, or one of the search
aliases listed above.

**`NameError: name 'font_manager' is not defined`:** ComfyUI is
running an older copy of the node files. Copy the latest
`nodes/font2img_node.py` and `nodes/text_graphic_element_node.py`
over the install directory.

**`pip install` fails with `UnicodeDecodeError: 'gbk'`:** Your
`requirements.txt` got rewritten with non-ASCII characters. The
pinned version of this repo is pure ASCII.

**`UnicodeDecodeError: 'gbk' codec can't decode byte 0x94`:** same as
above - re-download `requirements.txt` from the latest commit.

**Chart in Scheduled Values is too small / doesn't resize:** Make
sure you're running the latest `web/js/scheduled_values.js`. Recent
versions use `getMinHeight`/`getMaxHeight` so the chart scales with
the canvas zoom.

**Deprecation warnings about `/scripts/ui.js`, `groupNode.js`,
`buttonGroup.js`, `button.js`:** These are from other ComfyUI
extensions, not from Mana. The current Mana code does not import any
of these paths.
