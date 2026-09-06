import { app } from "../../../scripts/app.js";
import { ComfyWidgets } from "../../../scripts/widgets.js";

app.registerExtension({
    name: "ManaNodes.string2file",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "Save/Preview Text") {
            function populate(values) {
                let previewText;
                if (!values || !values.length) return;
                if (values.length === 1) {
                    // Called during execution — message.text is a list of strings.
                    previewText = values[0];
                } else {
                    // Called during configuration — widgets_values layout is
                    // [filename_prefix, string, ...]. The preview sits at the
                    // same index as the source widget, which is the last one.
                    previewText = values[values.length - 1];
                }
                let previewWidget = this.widgets.find(w => w.name === "preview");
                if (!previewWidget) {
                    // ComfyWidgets.STRING signature is
                    // (node, inputName, inputData, app). The historical
                    // 4-arg form is what the rest of ComfyUI uses; the
                    // 3-arg variant was a typo that crashed on newer builds.
                    previewWidget = ComfyWidgets["STRING"](
                        this, "preview", ["STRING", { multiline: true }], app
                    ).widget;
                    if (previewWidget.inputEl) {
                        previewWidget.inputEl.readOnly = false;
                        previewWidget.inputEl.style.opacity = 0.6;
                        // Give the preview a sensible min height so it
                        // doesn't render as a single-line box on first
                        // add. ComfyUI's string widget defaults to ~24px.
                        previewWidget.inputEl.style.minHeight = "80px";
                        previewWidget.inputEl.style.resize = "vertical";
                    }
                }
                previewWidget.value = previewText;

                requestAnimationFrame(() => {
                    if (typeof this.computeSize !== "function") return;
                    const sz = this.computeSize();
                    if (this.size) {
                        if (sz[0] < this.size[0]) sz[0] = this.size[0];
                        if (sz[1] < this.size[1]) sz[1] = this.size[1];
                    }
                    this.onResize?.(sz);
                    // Force a redraw so the new text height is picked up.
                    app.graph?.setDirtyCanvas(true, false);
                });
            }

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                if (message?.text) populate.call(this, message.text);
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                onConfigure?.apply(this, arguments);
                if (this.widgets_values?.length) {
                    populate.call(this, this.widgets_values);
                }
            };
        }
    },
});