import { app } from "../../../scripts/app.js";

// Note: we deliberately do NOT import from scripts/widgets.js. ComfyUI
// logs a deprecation Notice for that import. Instead we build the
// preview widget with the raw DOM API — ComfyUI's addWidget
// accepts any HTMLElement, so we only need a textarea + a small
// wrapper that matches the widget interface.
app.registerExtension({
    name: "ManaNodes.string2file",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Save/Preview Text") return;

        function _createPreviewWidget(node, app) {
            const wrapper = document.createElement("div");
            wrapper.style.width = "100%";
            const textarea = document.createElement("textarea");
            textarea.readOnly = false;
            textarea.style.opacity = "0.6";
            textarea.style.width = "100%";
            textarea.style.minHeight = "80px";
            textarea.style.resize = "vertical";
            textarea.style.boxSizing = "border-box";
            wrapper.appendChild(textarea);

            const widget = {
                name: "preview",
                type: "STRING",
                value: "",
                inputEl: textarea,
                element: wrapper,
                // Minimal widget interface that LiteGraph expects.
                draw: function () {},
                computeSize: function () {
                    // ~20 chars per line, +1 line for the textarea chrome
                    const lines = (this.value || "").split("\n").length;
                    return [Math.max(200, this.element.clientWidth || 200), Math.max(80, (lines + 1) * 18)];
                },
            };
            // Hook up two-way binding through the standard `value` setter
            // so other code can read .value without surprises.
            Object.defineProperty(widget, "value", {
                get: () => textarea.value,
                set: (v) => { textarea.value = v ?? ""; },
            });
            node.addDOMWidget("preview", "string", wrapper, {
                getValue: () => widget.value,
                setValue: (v) => { widget.value = v; },
            });
            return widget;
        }

        function populate(values) {
            if (!values || !values.length) return;
            const previewText = values.length === 1
                ? values[0]
                : values[values.length - 1];

            let previewWidget = this.widgets.find((w) => w.name === "preview");
            if (!previewWidget) {
                previewWidget = _createPreviewWidget(this, app);
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
    },
});
