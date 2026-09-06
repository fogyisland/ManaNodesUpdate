import { app } from '../../../scripts/app.js';
import { api } from "../../../scripts/api.js";

// `scripts/ui.js` is deprecated; in newer ComfyUI builds the helpers
// (including `$el`) live in `scripts/ui/element.js`. We try the new
// path first and fall back to a tiny inline shim so the preview still
// works on older installs. We deliberately do NOT import from
// `scripts/ui.js` because ComfyUI prints a deprecation warning for it.
async function _loadEl() {
    try {
        const mod = await import("../../../scripts/ui/element.js");
        return mod.$el;
    } catch (_) {
        // Inline shim: just create an element with the given props.
        return (tag, props) => Object.assign(document.createElement(tag), props || {});
    }
}

// ANIM_PREVIEW_WIDGET moved out of app.js into a separate module in newer
// ComfyUI releases. Look it up defensively; fall back to the historical
// name so the video preview still attaches.
const ANIM_PREVIEW_WIDGET = (() => {
    try {
        // Newer ComfyUI exposes it via app itself
        if (app && app.ANIM_PREVIEW_WIDGET) return app.ANIM_PREVIEW_WIDGET;
    } catch (_) { /* ignore */ }
    return "$$disc_widget_animation_preview";
})();

// createImageHost used to live at scripts/ui/imagePreview.js; in newer
// versions it was moved/renamed. Try both locations and fall back to a
// minimal local host so the video preview never silently breaks.
let _imageHostFactory = null;
async function _getImageHostFactory() {
    if (_imageHostFactory !== null) return _imageHostFactory;
    try {
        const mod = await import("../../../scripts/ui/imagePreview.js");
        if (mod && typeof mod.createImageHost === "function") {
            _imageHostFactory = mod.createImageHost;
            return _imageHostFactory;
        }
    } catch (_) { /* fall through to local fallback */ }
    _imageHostFactory = false; // marker: not available, use local fallback
    return _imageHostFactory;
}

// Local $el shim. Resolved lazily via _loadEl so the deprecated
// `scripts/ui.js` import never runs (ComfyUI logs a warning for it).
let _elShim = null;
async function _el(tag, props) {
    if (!_elShim) _elShim = await _loadEl();
    return _elShim(tag, props);
}

function _createLocalImageHost(node) {
    // Minimal stand-in: render the first image directly. Good enough for
    // video preview; not a drop-in for the full ComfyUI image host.
    let el = document.createElement("div");
    el.className = "comfy-img-preview";
    el.style.width = "100%";
    let currentImg = null;
    return {
        el,
        getHeight: () => currentImg ? currentImg.clientHeight : 0,
        onDraw: function () { /* no-op */ },
        updateImages: function (imgs) {
            if (currentImg && el.contains(currentImg)) el.removeChild(currentImg);
            currentImg = imgs[0] || null;
            if (currentImg) el.appendChild(currentImg);
        },
    };
}

const URL_REGEX = /^(https?:\/\/|\/view\?|data:image\/)/;

const style = `
.comfy-img-preview video {
  object-fit: contain;
  width: var(--comfy-img-preview-width);
  height: var(--comfy-img-preview-height);
}
`;

export function chainCallback(object, property, callback) {
  if (object == undefined) {
    return;
  }
  if (property in object) {
    const callback_orig = object[property];
    object[property] = function () {
      const r = callback_orig.apply(this, arguments);
      callback.apply(this, arguments);
      return r;
    };
  } else {
    object[property] = callback;
  }
};

export function formatUploadedUrl(params) {
  if (params.url) {
    return params.url;
  }

  params = { ...params };

  if (!params.filename && params.name) {
    params.filename = params.name;
    delete params.name;
  }
  const url = api.apiURL("/view?" + new URLSearchParams(params));
  return url;
};

export function addVideoPreview(nodeType, options = {}) {
  const createVideoNode = (url) => {
    return new Promise((cb) => {
      const videoEl = document.createElement('video');
      Object.defineProperty(videoEl, 'naturalWidth', {
        get: () => {
          return videoEl.videoWidth;
        },
      });
      Object.defineProperty(videoEl, 'naturalHeight', {
        get: () => {
          return videoEl.videoHeight;
        },
      });
      videoEl.addEventListener('loadedmetadata', () => {
        videoEl.controls = false;
        videoEl.loop = true;
        videoEl.muted = true;
        cb(videoEl);
      });
      videoEl.addEventListener('error', () => {
        cb();
      });
      videoEl.src = url;
    });
  };

  const createImageNode = (url) => {
    return new Promise((cb) => {
      const imgEl = document.createElement('img');
      imgEl.onload = () => {
        cb(imgEl);
      };
      imgEl.addEventListener('error', () => {
        cb();
      });
      imgEl.src = url;
    });
  };

  nodeType.prototype.onDrawBackground = function (ctx) {
    if (this.flags.collapsed) return;

    let imageURLs = (this.images ?? []).map((i) =>
      typeof i === 'string' ? i : formatUploadedUrl(i),
    );
    let imagesChanged = false;

    if (JSON.stringify(this.displayingImages) !== JSON.stringify(imageURLs)) {
      this.displayingImages = imageURLs;
      imagesChanged = true;
    }

    if (!imagesChanged) return;
    if (!imageURLs.length) {
      this.imgs = null;
      this.animatedImages = false;
      return;
    }

    const promises = imageURLs.map((url) => {
      if (url.startsWith('/view')) {
        url = window.location.origin + url;
      }

      const u = new URL(url);
      const filename =
        u.searchParams.get('filename') || u.searchParams.get('name') || u.pathname.split('/').pop();
      const ext = filename.split('.').pop();
      const format = ['gif', 'webp', 'avif'].includes(ext) ? 'image' : 'video';
      if (format === 'video') {
        return createVideoNode(url);
      } else {
        return createImageNode(url);
      }
    });

    Promise.all(promises)
      .then((imgs) => {
        this.imgs = imgs.filter(Boolean);
      })
      .then(async () => {
        if (!this.imgs.length) return;

        this.animatedImages = true;
        const widgetIdx = this.widgets?.findIndex((w) => w.name === ANIM_PREVIEW_WIDGET);

        const finishWithHost = (host) => {
          if (widgetIdx > -1) {
            const widget = this.widgets[widgetIdx];
            widget.options.host.updateImages(this.imgs);
          } else {
            this.setSizeForImage(true);
            const widget = this.addDOMWidget(ANIM_PREVIEW_WIDGET, 'img', host.el, {
              host,
              getHeight: host.getHeight,
              onDraw: host.onDraw,
              hideOnZoom: false,
            });
            widget.serializeValue = () => ({
              height: host.el.clientHeight,
            });
            widget.options.host.updateImages(this.imgs);
          }
        };

        const factory = await _getImageHostFactory();
        const host = (typeof factory === "function")
          ? factory(this)
          : _createLocalImageHost(this);
        finishWithHost(host);

        this.imgs.forEach((img) => {
          if (img instanceof HTMLVideoElement) {
            img.muted = true;
            img.autoplay = true;
            img.play();
          }
        });
      });
  };

  const { textWidget, comboWidget } = options;

  if (textWidget) {
    chainCallback(nodeType.prototype, 'onNodeCreated', function () {
      const pathWidget = this.widgets.find((w) => w.name === textWidget);
      pathWidget._value = pathWidget.value;
      Object.defineProperty(pathWidget, 'value', {
        set: (value) => {
          pathWidget._value = value;
          pathWidget.inputEl.value = value;
          this.images = (value ?? '').split('\n').filter((url) => URL_REGEX.test(url));
        },
        get: () => {
          return pathWidget._value;
        },
      });
      pathWidget.inputEl.addEventListener('change', (e) => {
        const value = e.target.value;
        pathWidget._value = value;
        this.images = (value ?? '').split('\n').filter((url) => URL_REGEX.test(url));
      });

      // Set value to ensure preview displays on initial add.
      pathWidget.value = pathWidget._value;
    });
  }

  if (comboWidget) {
    chainCallback(nodeType.prototype, 'onNodeCreated', function () {
      const pathWidget = this.widgets.find((w) => w.name === comboWidget);
      pathWidget._value = pathWidget.value;
      Object.defineProperty(pathWidget, 'value', {
        set: (value) => {
          pathWidget._value = value;
          if (!value) {
            return this.images = []
          }

          const parts = value.split("/")
          const filename = parts.pop()
          const subfolder = parts.join("/")
          const extension = filename.split(".").pop();
          const format = (["gif", "webp", "avif"].includes(extension)) ? 'image' : 'video'
          this.images = [formatUploadedUrl({ filename, subfolder, type: "input", format: format })]
        },
        get: () => {
          return pathWidget._value;
        },
      });

      // Set value to ensure preview displays on initial add.
      pathWidget.value = pathWidget._value;
    });
  }

  chainCallback(nodeType.prototype, "onExecuted", function (message) {
    if (message?.videos) {
      this.images = message?.videos.map(formatUploadedUrl);
      if(nodeType.comfyClass === 'audio2video') {
        localStorage.setItem('savedVideoUrls', JSON.stringify(this.images));
      }
    }
  });

  // Restoring state in onConfigure
  chainCallback(nodeType.prototype, "onConfigure", function () {
    if(nodeType.comfyClass === 'audio2video') {
      const savedVideoUrls = JSON.parse(localStorage.getItem('savedVideoUrls'));
      if (savedVideoUrls) {
          this.images = savedVideoUrls;
      } 
    }

  });

}

app.registerExtension({
  name: "ManaNodes.audio2video",
  init() {
    $el('style', {
      textContent: style,
      parent: document.head,
    });
  },
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "Combine Video") {
      return;
    }

    addVideoPreview(nodeType);
  },
});
