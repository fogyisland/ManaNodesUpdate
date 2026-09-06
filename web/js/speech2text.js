// Speech Recognition node UI helper.
//
// Shows the current wav2vec2 model's language as a small badge
// above the spell_check_language widget, and auto-picks the matching
// spell_check_language when the user changes the model.

import { app } from "../../../scripts/app.js";

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
    "Multilingual 1000+": "English",
    "Multilingual 100+": "English",
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
            const modelWidget = this.widgets.find((w) => w.name === "wav2vec2_model");
            const spellWidget = this.widgets.find((w) => w.name === "spell_check_language");
            const upperWidget = this.widgets.find((w) => w.name === "uppercase");
            if (!modelWidget || !spellWidget) return;

            // Language badge so the user can see which language the
            // currently-selected model covers. The badge stretches
            // the full node width and is tall enough to fit two
            // lines of text — long names like "Multilingual 1000+"
            // or "Chinese (中文)" can wrap on narrow nodes without
            // getting clipped.
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
                this.addDOMWidget("model_language_badge", "text", badge, {
                    getMinHeight: () => 36,
                    getMaxHeight: () => 80,
                });
            } catch (e) {
                console.warn("[Mana] addDOMWidget for badge failed", e);
            }

            const updateBadge = () => {
                const lang = MODEL_LANGUAGES[modelWidget.value] || "Unknown";
                badge.textContent = `\u{1F399} Model language: ${lang}`;
            };
            updateBadge();

            // On model change: update spell_check_language and uppercase.
            const originalCallback = modelWidget.callback;
            modelWidget.callback = function (value) {
                if (originalCallback) originalCallback.apply(this, arguments);
                const lang = MODEL_LANGUAGES[value];
                if (lang && LANGUAGE_TO_SPELL_CHECK[lang] && spellWidget) {
                    spellWidget.value = LANGUAGE_TO_SPELL_CHECK[lang];
                }
                if (upperWidget) {
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
