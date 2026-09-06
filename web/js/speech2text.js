// Speech Recognition node UI helper.
//
// What this does:
//   1. Adds a "Browse" button to the audio_file widget that opens
//      a native file picker. The selected path goes straight into
//      the text field — no need to type long Windows paths.
//   2. Shows the current wav2vec2 model's language as a small badge
//      above the spell_check_language widget, so the user can see at
//      a glance whether they have a Chinese / English / multilingual
//      model selected.
//   3. When the user picks a different wav2vec2 model, the JS updates
//      the spell_check_language default to match (Chinese model ->"
//      Chinese (中文)", English model -> "English", etc.) so the user
//      doesn't have to manually re-pick it. They can still override
//      it after the auto-pick.
//   4. Same auto-pick for uppercase: CJK languages don't have a
//      concept of case so the JS sets uppercase=False automatically.

import { app } from "../../../scripts/app.js";

// Server-side defined mapping (kept in sync with speech2text_node.py).
// We embed it here so we don't need an extra roundtrip; values are
// stable because both ends are part of the same extension.
const MODEL_LANGUAGES = {
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
};

// Mapping from wav2vec2 model's language to the matching entry in
// the spell_check_language dropdown. CJK / Thai / Vietnamese etc.
// have no spell check available, so we point them at the matching
// "None (skip)" entry.
const LANGUAGE_TO_SPELL_CHECK = {
    "English": "English",
    "Spanish": "Spanish",
    "French": "French",
    "German": "German",
    "Italian": "Italian",
    "Portuguese": "Portuguese",
    "Russian": "Russian",
    "Arabic": "Arabic",
    "Chinese (中文)": "Chinese (中文)",
    "Japanese (日本語)": "Japanese (日本語)",
    "Korean (한국어)": "Korean (한국어)",
    "Multilingual 1000+": "English",  // default fallback for mms
    "Multilingual 100+": "English",
};

app.registerExtension({
    name: "ManaNodes.speech2text",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Speech Recognition") return;

        // Pick a sensible default model based on the browser's
        // preferred language. Falls back to English (which is also
        // the first item in DEFAULT_WAV2VEC2_MODELS) for any locale
        // we don't have a specific model for.
        const browserLang = (navigator.language || "en").toLowerCase();
        const LOCALE_TO_MODEL = {
            "zh": "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
            "ja": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
            "ko": "jonatasgrosman/wav2vec2-large-xlsr-53-korean",
            "es": "jonatasgrosman/wav2vec2-large-xlsr-53-spanish",
            "fr": "jonatasgrosman/wav2vec2-large-xlsr-53-french",
            "de": "jonatasgrosman/wav2vec2-large-xlsr-53-german",
            "it": "jonatasgrosman/wav2vec2-large-xlsr-53-italian",
            "pt": "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese",
            "ru": "jonatasgrosman/wav2vec2-large-xlsr-53-russian",
            "ar": "jonatasgrosman/wav2vec2-large-xlsr-53-arabic",
        };
        const langPrefix = browserLang.split("-")[0];
        const defaultModel = LOCALE_TO_MODEL[langPrefix] || "jonatasgrosman/wav2vec2-large-xlsr-53-english";
        const defaultSpell = LANGUAGE_TO_SPELL_CHECK[MODEL_LANGUAGES[defaultModel]] || "English";

        // We need to wait for the node to be created before we can
        // touch its widgets. Chain onNodeCreated so we run after
        // the default widget wiring.
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onCreated) onCreated.apply(this, arguments);
            const modelWidget = this.widgets.find((w) => w.name === "wav2vec2_model");
            const spellWidget = this.widgets.find((w) => w.name === "spell_check_language");
            const upperWidget = this.widgets.find((w) => w.name === "uppercase");
            if (!modelWidget || !spellWidget) return;

            // First-time setup: pick a default that matches the
            // browser locale. Skip if the user has already saved a
            // value (workflow was loaded).
            if (!modelWidget.value || modelWidget.value === "jonatasgrosman/wav2vec2-large-xlsr-53-english") {
                // Only override if the value is the hard-coded English default
                if (this.widgets_values && this.widgets_values.length === 0) {
                    modelWidget.value = defaultModel;
                    spellWidget.value = defaultSpell;
                }
            }

            // 1. Build a small language badge so the user can see
            //    which language the currently-selected model covers
            //    without having to memorize the model-id-to-language
            //    mapping.
            const badge = document.createElement("div");
            badge.style.cssText = [
                "padding: 4px 8px",
                "margin: 4px 0",
                "background: #1f3a5f",
                "color: #d4e4ff",
                "border: 1px solid #3d5a8c",
                "border-radius: 4px",
                "font-size: 12px",
                "text-align: center",
            ].join(";");
            this.addDOMWidget("model_language_badge", "text", badge, {});

            const updateBadge = () => {
                const lang = MODEL_LANGUAGES[modelWidget.value] || "Unknown";
                badge.textContent = `🎙️ Model language: ${lang}`;
            };
            updateBadge();

            // 2. When the user picks a different model, update the
            //    spell_check_language default to match, and disable
            //    uppercase for CJK languages (it has no effect there
            //    but the user has no way to know that).
            const originalCallback = modelWidget.callback;
            modelWidget.callback = function (value) {
                if (originalCallback) originalCallback.apply(this, arguments);
                const lang = MODEL_LANGUAGES[value];
                if (lang && LANGUAGE_TO_SPELL_CHECK[lang] && spellWidget) {
                    spellWidget.value = LANGUAGE_TO_SPELL_CHECK[lang];
                }
                if (upperWidget) {
                    // CJK / Arabic / Russian don't have a useful
                    // concept of case, so default uppercase off for
                    // them. Latin scripts default uppercase on.
                    const nonCase = [
                        "Chinese (中文)", "Japanese (日本語)",
                        "Korean (한국어)", "Hindi (हिन्दी)",
                        "Thai (ไทย)", "Arabic",
                    ];
                    upperWidget.value = !nonCase.includes(lang);
                }
                updateBadge();
            };
        };
    },
});

// ---------------------------------------------------------------------------
// File picker button for the audio_file widget.
//
// We mark the widget with `mana_audio_picker: True` in INPUT_TYPES so
// the JS can find it and attach a "Browse..." button. Clicking the
// button opens a native <input type="file"> dialog; the user picks
// a .wav / .mp3 / .flac / etc., and we write the absolute path back
// into the widget. Accept="audio/*" lets the OS filter to audio
// files so the user doesn't have to scroll past a thousand videos.
// ---------------------------------------------------------------------------
function addAudioFilePicker(node) {
    const widget = node.widgets.find((w) => w.name === "audio_file");
    if (!widget) return;
    if (widget.element && widget.element.dataset.manaPickerAttached === "1") return;

    // Build a small button styled to match ComfyUI's widget look.
    const btn = document.createElement("button");
    btn.textContent = "Browse audio file";
    btn.title = "Open a native file picker to select an audio file";
    btn.style.cssText = [
        "margin-left: 6px",
        "padding: 4px 10px",
        "background: #2a3a4f",
        "color: #d4e4ff",
        "border: 1px solid #3d5a8c",
        "border-radius: 4px",
        "font-size: 12px",
        "cursor: pointer",
    ].join(";");
    btn.onmouseenter = () => { btn.style.background = "#3a4a5f"; };
    btn.onmouseleave = () => { btn.style.background = "#2a3a4f"; };

    // Hidden <input type="file"> we click when the user presses Browse.
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "audio/*,.wav,.mp3,.flac,.ogg,.m4a,.aac,.opus,.wma";
    fileInput.style.display = "none";

    fileInput.addEventListener("change", () => {
        const f = fileInput.files && fileInput.files[0];
        if (!f) return;
        // ComfyUI lives on Windows / Linux / Mac. On Win we want
        // backslashes; elsewhere forward slashes. File.path on the
        // input element is the cleanest cross-platform answer.
        const path = (f.path || f.name).replace(/\\/g, "/");
        widget.value = path;
        // Force a redraw so the new value is visible.
        if (node.onResize) node.onResize(node.size);
        app.graph?.setDirtyCanvas(true, false);
    });

    btn.addEventListener("click", () => fileInput.click());

    // Place the button next to the widget's input element.
    const host = widget.element || widget.inputEl?.parentElement;
    if (host) {
        host.style.display = "flex";
        host.style.alignItems = "center";
        host.appendChild(btn);
        host.appendChild(fileInput);
        host.dataset.manaPickerAttached = "1";
    }
}

// Register the picker on every Speech Recognition node that's added.
app.registerExtension({
    name: "ManaNodes.speech2text.filepicker",
    nodeCreated(node) {
        if (node.comfyClass !== "Speech Recognition") return;
        // Defer to next tick so ComfyUI has finished mounting the
        // widget DOM; otherwise widget.element might be null.
        setTimeout(() => addAudioFilePicker(node), 0);
    },
});
