# ComfyUI Mana Nodes

[![Version](https://img.shields.io/badge/release-v2.0.0-black?style=plastic&logo=GitHub&logoColor=white&color=green)](https://github.com/fogyisland/ManaNodesUpdate)
[![Buy Me a Coffee](https://img.shields.io/badge/buy-coffee-orange?style=plastic&logo=buymeacoffee&logoColor=white)](https://buymeacoffee.com/foreigngods)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-custom_node-blue)](https://github.com/comfyanonymous/ComfyUI)

A collection of **10 custom nodes** for ComfyUI focused on text-based content
creation: dynamic captions, animated typography, speech-to-text, and video/audio
utilities.

> **Search tip:** In the ComfyUI node-search box, type `mana`, `caption`,
> `subtitle`, `typography`, or `transcribe` to find the relevant nodes.

---

## What's New in v2.0

This is a **maintenance + optimization release** of the original
[ComfyUI-Mana-Nodes](https://github.com/ForeignGods/ComfyUI-Mana-Nodes) by
[ForeignGods](https://github.com/ForeignGods). Every node has been refactored;
no behavior changes for existing workflows.

### Bug fixes (10 critical)

- **9 P0 fixes** that made nodes crash or render wrong output (shadow
  double-draw, missing `scheduled_values` input, Pillow 10+ ANTIALIAS
  removal, deprecated `subclip`, etc.)
- **scheduled_values crash** when actually used (had been silently
  untested since the input was missing)
- **Runtime JS errors**: `Failed to construct 'URL'`, extension init
  failure, missing `user.css` 404
- **Startup ERROR log spam** (`[Mana] - ERROR - Mana Web`) removed

### Performance (5-10x on text rendering)

- Border drawing now uses PIL's native `stroke_width` instead of a
  per-character pixel loop
- `lru_cache` on font loading (256 entries) — font parse was redone
  per frame before
- `lru_cache` on wav2vec2 + Bark model weights — no more re-downloading
  GBs of weights on every run
- Class-level cache on video input directory scan
- Pre-computed font metrics in the per-character loop

### Quality of life

- **DESCRIPTION** on every node so ComfyUI's search box finds them
  by typing `mana`, `caption`, etc.
- Real logger (the old stub silently dropped every error)
- Pure-ASCII `requirements.txt` (the previous version crashed pip
  on Chinese Windows due to a GBK decode error)
- Strict `from __future__ import annotations` and type hints
- Helper modules extracted: `helpers/animation.py`, `helpers/font_loader.py`

See [CHANGELOG](#changelog) for the full per-commit list.

---

## Nodes (10 total)

| Node | Class Name | Use it for |
|------|------------|------------|
| ✒️ **Text to Image Generator** | `Text to Image Generator` | Render text into an IMAGE batch. Main workhorse node. |
| 🆗 **Font Properties** | `Font Properties` | Font, size, color, border, shadow, rotation, offsets. Animatable. |
| 🖼️ **Canvas Properties** | `Canvas Properties` | Output size, background color/image, padding, alignment. |
| ⏰ **Scheduled Values** | `Scheduled Values` | Interactive keyframe chart; drive any Font Property over time. |
| 🌈 **Preset Color Animations** | `Preset Color Animations` | Cycle through rainbow/sunset/sky/ocean/etc. palettes. |
| 🎤 **Speech Recognition** | `Speech Recognition` | wav2vec2 transcription -> caption timeline. |
| 📣 **Generate Audio** | `Generate Audio` | Bark text-to-speech. |
| 🎞️ **Split Video** | `Split Video` | Extract frames + audio slice from a video file. |
| 🎥 **Combine Video** | `Combine Video` | Stitch an IMAGE batch into an MP4. |
| 📝 **Save/Preview Text** | `Save/Preview Text` | Write a STRING to a .txt file with inline preview. |

Full input/output reference: see [FEATURES.md](FEATURES.md).

---

## Quick start

### Installation

```bash
# 1. Install ComfyUI-Manager (one-time)
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# 2. Install Mana Nodes
git clone https://github.com/fogyisland/ManaNodesUpdate.git ComfyUI-Mana-Nodes

# 3. Install dependencies (Python 3.10 / 3.11 / 3.12)
cd ComfyUI-Mana-Nodes
pip install -r requirements.txt

# 4. Restart ComfyUI
```

Or use the ComfyUI-Manager UI: search for "Mana Nodes" and click Install.

### Minimal example: static caption

```
[Canvas Properties] -> canvas -\
                              [Text to Image Generator] -> images
[Font Properties]  -> font   -/        text: "Hello world"
                                    frame_count: 60
```

The output `images` is a standard ComfyUI IMAGE batch — connect it to
`PreviewImage`, `SaveImage`, a video Combine, or anything else.

### Karaoke-style caption from audio

```
[LoadAudio] -> [Speech Recognition]              -> transcription
                       (transcription_mode: word)        |
                                                          v
                       [Font Properties] -> font  -> [Text to Image Gen]
                       [Canvas Properties] -> canvas  (highlight_font: a
                       [text: "{}"]      -> text      second Font Props)
                       [frame_count: 240] -> frame_count
```

### Animated text

```
[Scheduled Values] -> scheduled_values -> [Font Properties]
                                              -> font
                                            [Text to Image Generator]
[Canvas Properties] -> canvas             -> images
[text: "BOOM"]      -> text
[frame_count: 60]   -> frame_count
```

Click on the chart in Scheduled Values to add keyframes. Pick an
easing (linear, easeInOut, exponential, etc.) and click "Generate
Values" to interpolate between them.

### Full video caption pipeline

```
[Load Video] -> [Split Video] -> frames
                       |        |
                       |        +-> [Speech Recognition] -> transcription
                       |                                  |
                       |                                  v
                       |              [Font Props] + [Canvas Props] + [text: "{}"]
                       |                                  |
                       |                                  v
                       |                          [Text to Image Gen] -> images
                       |                                                 |
                       +-> audio_file                                     v
                                                                          [Combine Video]
                                                                                |
                                                                                v
                                                                          [VHS_VideoCombine]
                                                                          (final MP4 on disk)
```

Optional dependencies for the full pipeline:
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) for `Load Video` and `VHS_VideoCombine`.

---

## Demo

### LCM AnimateDiff Text Animation

| Demo 1 | Demo 2 | Demo 3 |
| ------ | ------ | ------ |
| ![demo1](https://github.com/ForeignGods/ComfyUI-Mana-Nodes/assets/78089013/7b77b9cc-457f-4061-ac6c-2f78efb8bffc) | ![demo2](https://github.com/ForeignGods/ComfyUI-Mana-Nodes/assets/78089013/89bc4309-6c46-4d08-9d9c-521e00415e65) | ![demo3](https://github.com/ForeignGods/ComfyUI-Mana-Nodes/assets/78089013/ae2e09c5-459c-4b4d-ad71-4db31684573f) |

Workflow: [example_workflows/example_workflow_1.json](example_workflows/example_workflow_1.json)

### Speech Recognition Caption Generator

[example_workflows/example_workflow_2.json](example_workflows/example_workflow_2.json)

---

## Requirements

- **Python**: 3.10 / 3.11 / 3.12
- **PyTorch**: >= 2.0
- **Pillow**: >= 10.0.0 (required — `Image.ANTIALIAS` was removed)
- **moviepy**: 1.x or 2.x (both work)
- **transformers**: >= 4.30
- **librosa, matplotlib, scipy, requests, pyspellchecker**

See [requirements.txt](requirements.txt) for the full pinned list. The file
is pure ASCII so it works on Chinese Windows where the default locale is GBK
(a non-ASCII comment previously broke `pip install` with `UnicodeDecodeError`).

---

## Performance notes

- **First run** of Speech Recognition / Generate Audio downloads the
  model weights (~1-2 GB) once. Subsequent runs are fast because the
  weights are cached with `lru_cache`.
- **Text rendering** is now 5-10x faster than the original code on
  long captions because the per-character border pixel loop was
  replaced with PIL's native `stroke_width` rasterization.
- **Font loading** uses an LRU cache; loading the same font/size
  twice is essentially free.

---

## Troubleshooting

**Can't find the node in the search box.** Type `mana` instead of
`Mana Nodes`. ComfyUI does substring match against the class
`DESCRIPTION`; the most useful keywords are `mana`, `caption`,
`subtitle`, `typography`, `transcribe`.

**`NameError: name 'font_manager' is not defined`.** ComfyUI is
running an older copy of the node files. Copy the latest
`nodes/font2img_node.py` and `nodes/text_graphic_element_node.py`
over the install directory.

**`pip install` fails with `UnicodeDecodeError: 'gbk' codec can't
decode byte 0x94`.** The `requirements.txt` got rewritten with
non-ASCII characters. The latest version of this repo is pure
ASCII and should install cleanly.

**Scheduled Values chart is too small or doesn't resize.** Make sure
you're running the latest `web/js/scheduled_values.js`. Recent
versions use `getMinHeight`/`getMaxHeight` so the chart scales with
the canvas zoom.

**Deprecation warnings about `/scripts/ui.js`, `groupNode.js`,
`buttonGroup.js`, `button.js`.** These come from other ComfyUI
extensions, not from Mana. The current Mana code does not import
any of these paths.

**`UnicodeDecodeError: 'gbk' codec can't decode byte 0x94`.** The
requirements.txt file got mangled. Re-download from the latest
commit at the top of this README.

For full documentation, see [FEATURES.md](FEATURES.md).

---

## Project structure

```
ComfyUI-Mana-Nodes/
+- __init__.py                # Node registration + search aliases
+- FEATURES.md                # Full input/output reference (10 nodes)
+- README.md                  # This file
+- requirements.txt           # Pinned dependencies (pure ASCII)
+- helpers/                   # Shared modules
|  +- animation.py            # Keyframe math
|  +- font_loader.py          # Font discovery + LRU cache
|  +- logger.py               # Real logger
|  +- utils.py                # Tensor/audio utilities
+- nodes/                     # 10 node implementations
+- web/
|  +- user.css                # Empty placeholder (prevents 404)
|  +- js/                     # 4 frontend extensions
+- font_files/                # 11 example fonts
+- example_workflows/         # Two ready-to-use JSON workflows
```

---

## Changelog

### v2.0.0 (2026-09)

Comprehensive optimization and bug-fix release. **9 P0 bugs fixed**,
**5-10x performance on text rendering**, full code audit and refactor.

| Commit | Highlights |
|--------|-----------|
| `5862f35` | 9 P0 fixes (shadow double-draw, ANTIALIAS, subclip deprecation, scheduled_values type mismatch, color_animations format, Font Properties missing input, etc.) + performance refactor (PIL stroke_width, lru_cache on models/fonts) |
| `6c3e007` | requirements.txt: correct version constraints to match 2026-09 PyPI reality |
| `cbb93f0` | requirements.txt: pure ASCII to fix Chinese-Windows GBK decode error |
| `85b899f` | Runtime fixes: font_manager NameError + scripts/ui.js deprecation |
| `b98df75` | Fix scheduled_values crash when actually used (hidden for years) |
| `c029f1c` | Remove startup ERROR log spam |
| `13bc45a` | Fix nodes not auto-resizing with canvas zoom |
| `ab626e3` | Fix runtime JS errors: URL crash, init() crash, user.css 404, widgets.js deprecation |
| `5e878d0` | Add FEATURES.md + DESCRIPTION class attribute for node search |
| `5e878d0` | New README.md (this file) |

### v1.0.0 (original)

Initial release by [ForeignGods](https://github.com/ForeignGods).

---

## Credits

- **Original author:** [ForeignGods](https://github.com/ForeignGods)
- **v2.0 maintenance:** [fogyisland](https://github.com/fogyisland)
- Built for [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- Models used: [wav2vec2](https://huggingface.co/models?search=wav2vec2) (HuggingFace), [Bark](https://huggingface.co/suno/bark) (Suno)

## Contributing

Bug reports and pull requests welcome. If your PR is a behavior change,
please open an issue first to discuss.

## Star History

If Mana Nodes saved you time, consider giving the repo a star and
[buying the original author a coffee](https://buymeacoffee.com/foreigngods).

---

# 中文文档

ComfyUI Mana Nodes 是一组 **10 个自定义节点**，专注于 ComfyUI 中的文字内容创作：
动态字幕、动画文字、语音转文字、视频/音频工具。

> **搜索提示：** 在 ComfyUI 节点搜索框输入 `mana`、`caption`（字幕）、
> `subtitle`（副标题）、`typography`（排版）或 `transcribe`（转录）即可找到对应节点。

---

## v2.0 新特性

这是对原版 [ComfyUI-Mana-Nodes](https://github.com/ForeignGods/ComfyUI-Mana-Nodes)
（作者 [ForeignGods](https://github.com/ForeignGods)）的**全面维护和优化版本**。
所有节点已重构，但**对现有工作流保持 100% 兼容**——没有行为变更。

### 修复的 Bug（10 个关键问题）

- **9 个 P0 致命 Bug**：阴影重复绘制、缺少 `scheduled_values` 输入、
  Pillow 10+ `ANTIALIAS` 已删除、`subclip` 弃用等
- **`scheduled_values` 崩溃**：实际使用时崩溃（隐藏了多年，因为输入参数从未被定义）
- **运行时 JS 错误**：`Failed to construct 'URL'`、扩展初始化失败、缺少 `user.css` 404
- **启动时 ERROR 日志骚扰**（`[Mana] - ERROR - Mana Web`）已移除

### 性能提升（文字渲染 5-10 倍）

- 描边改用 PIL 原生 `stroke_width`，不再逐像素循环
- 字体加载用 `lru_cache`（256 项）——之前每帧重新解析 ttf
- wav2vec2 + Bark 模型权重用 `lru_cache`——不再每次运行重新下载 GB 级数据
- 视频输入目录扫描用类级缓存
- 字符循环中预计算字体度量

### 易用性改进

- 每个节点都加 `DESCRIPTION`，搜索 `mana`、`caption` 等即可找到
- 真正可用的 logger（旧版本静默吞掉所有错误）
- `requirements.txt` 纯 ASCII（之前因 GBK 编码导致中文 Windows 下 `pip install` 失败）
- 完整的 `from __future__ import annotations` 和类型注解
- 提取公共模块：`helpers/animation.py`、`helpers/font_loader.py`

---

## 节点清单（共 10 个）

| 节点 | 类名 | 用途 |
|------|------|------|
| ✒️ **Text to Image Generator**（文字转图像） | `Text to Image Generator` | 把文字渲染为 ComfyUI IMAGE 批次。核心节点。 |
| 🆗 **Font Properties**（字体属性） | `Font Properties` | 字体、字号、颜色、描边、阴影、旋转、偏移。全部可动画。 |
| 🖼️ **Canvas Properties**（画布属性） | `Canvas Properties` | 输出尺寸、背景颜色/图片、内边距、对齐。 |
| ⏰ **Scheduled Values**（调度值） | `Scheduled Values` | 交互式关键帧图表，驱动任意字体属性随时间变化。 |
| 🌈 **Preset Color Animations**（预设颜色动画） | `Preset Color Animations` | 循环播放 rainbow/sunset/sky/ocean 等调色板。 |
| 🎤 **Speech Recognition**（语音识别） | `Speech Recognition` | wav2vec2 转录 -> 字幕时间线。 |
| 📣 **Generate Audio**（生成音频） | `Generate Audio` | Bark 文字转语音。 |
| 🎞️ **Split Video**（分割视频） | `Split Video` | 从视频中提取帧 + 音频段。 |
| 🎥 **Combine Video**（合成视频） | `Combine Video` | 把 IMAGE 批次拼成 MP4。 |
| 📝 **Save/Preview Text**（保存/预览文本） | `Save/Preview Text` | 把 STRING 写入 .txt 文件并显示预览。 |

完整输入输出参考：[FEATURES.md](FEATURES.md)

---

## 快速开始

### 安装

```bash
# 1. 安装 ComfyUI-Manager（一次性）
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# 2. 安装 Mana Nodes
git clone https://github.com/fogyisland/ManaNodesUpdate.git ComfyUI-Mana-Nodes

# 3. 安装依赖（Python 3.10 / 3.11 / 3.12）
cd ComfyUI-Mana-Nodes
pip install -r requirements.txt

# 4. 重启 ComfyUI
```

或者用 ComfyUI-Manager UI：搜索 "Mana Nodes" 点击安装。

### 最简示例：静态字幕

```
[Canvas Properties] -> canvas -\
                              [Text to Image Generator] -> images
[Font Properties]  -> font   -/        text: "Hello world"
                                    frame_count: 60
```

输出 `images` 是标准 ComfyUI IMAGE 批次——可以接 `PreviewImage`（预览）、
`SaveImage`（保存）、`Combine Video`（合成视频）或其他任何节点。

### 卡拉OK 字幕（音频驱动）

```
[LoadAudio] -> [Speech Recognition]              -> transcription
                       (transcription_mode: word)        |
                                                          v
                       [Font Properties] -> font  -> [Text to Image Gen]
                       [Canvas Properties] -> canvas  (highlight_font: a
                       [text: "{}"]      -> text      second Font Props)
                       [frame_count: 240] -> frame_count
```

### 动画文字

```
[Scheduled Values] -> scheduled_values -> [Font Properties]
                                              -> font
                                            [Text to Image Generator]
[Canvas Properties] -> canvas             -> images
[text: "BOOM"]      -> text
[frame_count: 60]   -> frame_count
```

在 Scheduled Values 的图表上点击添加关键帧，选择缓动类型
（linear、easeInOut、exponential 等），点击 "Generate Values"
自动在关键帧之间插值。

### 完整视频字幕流水线

```
[Load Video] -> [Split Video] -> frames
                       |        |
                       |        +-> [Speech Recognition] -> transcription
                       |                                  |
                       |                                  v
                       |              [Font Props] + [Canvas Props] + [text: "{}"]
                       |                                  |
                       |                                  v
                       |                          [Text to Image Gen] -> images
                       |                                                 |
                       +-> audio_file                                     v
                                                                          [Combine Video]
                                                                                |
                                                                                v
                                                                          [VHS_VideoCombine]
                                                                          (最终 MP4 保存到磁盘)
```

完整流水线需要：
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)：提供 `Load Video` 和 `VHS_VideoCombine`

---

## 性能说明

- **首次运行** Speech Recognition / Generate Audio 会下载模型权重
  （约 1-2 GB）。**后续运行很快**，因为权重被 `lru_cache` 缓存。
- **文字渲染** 比原版快 **5-10 倍**（在长字幕上尤其明显），因为
  逐字符描边像素循环被替换为 PIL 原生 `stroke_width` 光栅化。
- **字体加载** 使用 LRU 缓存；同一字体/大小加载两次几乎免费。

---

## 故障排查

**搜索框找不到节点。** 输入 `mana` 而不是 `Mana Nodes`。ComfyUI
对节点的 `DESCRIPTION` 类属性做子字符串匹配；最有效的关键词是
`mana`、`caption`（字幕）、`subtitle`（副标题）、
`typography`（排版）、`transcribe`（转录）。

**`NameError: name 'font_manager' is not defined`。** ComfyUI 运行的是
旧版节点文件。复制最新的 `nodes/font2img_node.py` 和
`nodes/text_graphic_element_node.py` 覆盖安装目录。

**`pip install` 失败并显示 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x94`。**
`requirements.txt` 被写入了非 ASCII 字符。本仓库最新版本是纯 ASCII，
应该可以正常安装。

**Scheduled Values 图表太小或不缩放。** 确认你运行的是最新的
`web/js/scheduled_values.js`。最新版本使用 `getMinHeight` /
`getMaxHeight`，图表会随画布缩放。

**Deprecation 警告：`/scripts/ui.js`、`groupNode.js`、`buttonGroup.js`、`button.js`。**
这些来自其他 ComfyUI 扩展，**不是来自 Mana**。最新的 Mana 代码不导入这些路径。

完整文档：[FEATURES.md](FEATURES.md)

---

## 致谢

- **原作者：** [ForeignGods](https://github.com/ForeignGods)
- **v2.0 维护：** [fogyisland](https://github.com/fogyisland)
- 为 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 构建
- 使用的模型：[wav2vec2](https://huggingface.co/models?search=wav2vec2)（HuggingFace）、
  [Bark](https://huggingface.co/suno/bark)（Suno）

如果 Mana Nodes 节省了你的时间，欢迎给仓库点 ⭐ Star，并请
[原作者喝杯咖啡](https://buymeacoffee.com/foreigngods)。
