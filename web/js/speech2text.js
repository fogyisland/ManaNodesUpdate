// Speech Recognition node UI helper.
//
// Shows the currently-selected Whisper model's size + accuracy hint
// as a small badge above the spell_check_language widget.

import { app } from "../../../scripts/app.js";

// Whisper model id -> human-readable description. The badge shows
// this so the user can sanity-check which model is currently
// selected without opening a dropdown.
const MODEL_INFO = {
    "whisper-tiny":     "tiny - 75 MB (fastest, lower accuracy)",
    "whisper-base":     "base - 140 MB (decent English)",
    "whisper-small":    "small - 460 MB (balanced, default)",
    "whisper-medium":   "medium - 1.5 GB (strong multilingual)",
    "whisper-large-v3": "large-v3 - 3 GB (best accuracy)",
};

// When the user picks a Whisper model, we suggest a default spell
// check language. Whisper auto-detects the audio language, but
// spell-check is still a Latin-alphabet-only post-processing step
// so we map by the model *size* heuristic: small/medium/large are
// multilingual, tiny/base are most often used on English.
const WHISPER_DEFAULT_SPELL = {
    "whisper-tiny":     "English",
    "whisper-base":     "English",
    "whisper-small":    "English",
    "whisper-medium":   "English",
    "whisper-large-v3": "English",
};

function chainCallback(object, property, callback) {
    if (object == undefined) return;
    if (property in object) {
        const original = object[property];
        object[property] = function () {
            const r = original.apply(this, arguments);
            callback.apply(this, arguments);
            return r;
        };
    } else {
        object[property] = callback;
    }
}

app.registerExtension({
    name: "ManaNodes.speech2text",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Speech Recognition") return;

        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onCreated) onCreated.apply(this, arguments);
            const modelWidget = this.widgets.find((w) => w.name === "asr_model");
            const spellWidget = this.widgets.find((w) => w.name === "spell_check_language");
            if (!modelWidget) return;

            // Model info badge so the user can see at a glance what
            // they picked and how big the download will be.
            const badge = document.createElement("div");
            badge.style.cssText = [
                "box-sizing: border-box",
                "width: 100%",
                "padding: 6px 10px",
                "margin: 4px 0",
                "background: #1f3a5f",
                "color: #d4e4ff",
                "border: 1px solid #3d5a8c",
                "border-radius: 4px",
                "font-size: 12px",
                "line-height: 1.4",
                "text-align: center",
                "word-wrap: break-word",
                "overflow-wrap: anywhere",
            ].join(";");
            try {
                this.addDOMWidget("model_info_badge", "text", badge, {
                    getMinHeight: () => 36,
                    getMaxHeight: () => 80,
                });
            } catch (e) {
                console.warn("[Mana] addDOMWidget for badge failed", e);
            }

            const updateBadge = () => {
                const info = MODEL_INFO[modelWidget.value]
                    || `Unknown model: ${modelWidget.value}`;
                badge.textContent = `\u{1F399} ${info}`;
            };
            updateBadge();

            // On model change: refresh badge + suggest a default
            // spell-check language. Whisper auto-detects the audio
            // language itself, so we don't try to map model -> audio
            // language here (we used to, with the old wav2vec2 list).
            const originalCallback = modelWidget.callback;
            modelWidget.callback = function (value) {
                if (originalCallback) originalCallback.apply(this, arguments);
                if (spellWidget && WHISPER_DEFAULT_SPELL[value]) {
                    spellWidget.value = WHISPER_DEFAULT_SPELL[value];
                }
                updateBadge();
            };
        };
    },
});
