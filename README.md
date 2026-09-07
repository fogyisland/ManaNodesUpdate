# ComfyUI Mana Nodes（魔力节点）

[![版本](https://img.shields.io/badge/release-v2.0.0-black?style=plastic&logo=GitHub&logoColor=white&color=green)](https://github.com/fogyisland/ManaNodesUpdate)
[![Buy Me a Coffee](https://img.shields.io/badge/buy-coffee-orange?style=plastic&logo=buymeacoffee&logoColor=white)](https://buymeacoffee.com/foreigngods)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-自定义节点-blue)](https://github.com/comfyanonymous/ComfyUI)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

一套专为 ComfyUI 设计的 **10 个自定义节点**，专注于文字内容创作：
动态字幕、动画文字、语音转文字、视频/音频工具。

> **搜索提示：** 在 ComfyUI 节点搜索框输入 `mana`、`caption`（字幕）、
> `subtitle`（副标题）、`typography`（排版）或 `transcribe`（转录）即可找到对应节点。

---

## ✨ v2.0 新特性

这是对原版 [ComfyUI-Mana-Nodes](https://github.com/ForeignGods/ComfyUI-Mana-Nodes)
（作者 [ForeignGods](https://github.com/ForeignGods)）的**全面维护和优化版本**。
所有节点已重构，但**对现有工作流保持 100% 兼容**——没有行为变更。

### 🐛 修复的 Bug（共 10+ 个关键问题）

- **9 个 P0 致命 Bug**：阴影重复绘制、缺少 `scheduled_values` 输入参数、
  Pillow 10+ 已删除的 `ANTIALIAS`、被弃用的 `subclip` 等
- **`scheduled_values` 隐藏崩溃**：实际使用时崩溃（隐藏了多年，因为输入参数从未被定义）
- **运行时 JS 错误**：`Failed to construct 'URL'`、扩展初始化失败、缺少 `user.css` 404
- **`process_single_image` 变量未定义**：使用阴影 Y 偏移时崩溃
- **启动时 ERROR 日志骚扰**（`[Mana] - ERROR - Mana Web`）已移除

### ⚡ 性能提升（文字渲染 **5-10 倍**）

- 描边改用 PIL 原生 `stroke_width`，不再逐像素循环
- 字体加载用 `lru_cache`（256 项）——之前每帧重新解析 ttf
- Whisper + Bark 模型权重用 `lru_cache`——不再每次运行重新下载 GB 级数据
- 视频输入目录扫描用类级缓存
- 字符循环中预计算字体度量

### 🎨 易用性改进

- 每个节点都加 `DESCRIPTION`，搜索 `mana`、`caption` 等即可找到
- 真正可用的 logger（旧版本静默吞掉所有错误）
- `requirements.txt` 纯 ASCII（之前因 GBK 编码导致中文 Windows 下 `pip install` 失败）
- 完整的 `from __future__ import annotations` 和类型注解
- 提取公共模块：`helpers/animation.py`、`helpers/font_loader.py`

详细修改日志请看 [更新日志](#-更新日志-changelog)。

---

## 📦 节点清单（共 10 个）

| 节点 | 类名 | 用途 |
|------|------|------|
| ✒️ **文字转图像生成器** | `Text to Image Generator` | 把文字渲染为 ComfyUI IMAGE 批次。核心节点。 |
| 🆗 **字体属性** | `Font Properties` | 字体、字号、颜色、描边、阴影、旋转、偏移。全部可动画。 |
| 🖼️ **画布属性** | `Canvas Properties` | 输出尺寸、背景颜色/图片、内边距、对齐。 |
| ⏰ **调度值** | `Scheduled Values` | 交互式关键帧图表，驱动任意字体属性随时间变化。 |
| 🌈 **预设颜色动画** | `Preset Color Animations` | 循环播放 rainbow/sunset/sky/ocean 等调色板。 |
| 🎤 **语音识别** | `Speech Recognition` | Whisper 转录 -> 字幕时间线（99 种语言自动检测）。 |
| 📣 **生成音频** | `Generate Audio` | Bark 文字转语音。 |
| 🎞️ **分割视频** | `Split Video` | 从视频中提取帧 + 音频段。 |
| 🎥 **合成视频** | `Combine Video` | 把 IMAGE 批次拼成 MP4。 |
| 📝 **保存/预览文本** | `Save/Preview Text` | 把 STRING 写入 .txt 文件并显示预览。 |

每个节点的输入/输出详细说明：[FEATURES.md](FEATURES.md)

---

## 🚀 快速开始

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

### 🎤 卡拉OK 字幕（音频驱动）

```
[LoadAudio] -> [Speech Recognition]              -> transcription
                       (transcription_mode: word)        |
                                                          v
                       [Font Properties] -> font  -> [Text to Image Gen]
                       [Canvas Properties] -> canvas  (highlight_font: a
                       [text: "{}"]      -> text      second Font Props)
                       [frame_count: 240] -> frame_count
```

### ⏰ 动画文字

```
[Scheduled Values] -> scheduled_values -> [Font Properties]
                                              -> font
                                            [Text to Image Generator]
[Canvas Properties] -> canvas             -> images
[text: "BOOM"]      -> text
[frame_count: 60]   -> frame_count
```

在 Scheduled Values 的图表上**点击**添加关键帧，选择缓动类型
（linear、easeInOut、exponential 等），点击 **Generate Values**
自动在关键帧之间插值。

### 🌈 彩色循环

```
[Preset Color Animations] -> scheduled_colors -> [Font Properties]
                                                       -> font (font_color)
                                                  [Text to Image Generator]
[Canvas Properties] -> canvas                    -> images
[Font Properties]  -> font
[text: "RAINBOW"]   -> text
[frame_count: 60]   -> frame_count
```

### 🎬 完整视频字幕流水线

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

## 🎬 演示

### LCM AnimateDiff 文字动画

| Demo 1 | Demo 2 | Demo 3 |
| ------ | ------ | ------ |
| ![demo1](https://github.com/ForeignGods/ComfyUI-Mana-Nodes/assets/78089013/7b77b9cc-457f-4061-ac6c-2f78efb8bffc) | ![demo2](https://github.com/ForeignGods/ComfyUI-Mana-Nodes/assets/78089013/89bc4309-6c46-4d08-9d9c-521e00415e65) | ![demo3](https://github.com/ForeignGods/ComfyUI-Mana-Nodes/assets/78089013/ae2e09c5-459c-4b4d-ad71-4db31684573f) |

工作流：[example_workflows/example_workflow_1.json](example_workflows/example_workflow_1.json)

### 语音识别字幕生成器

[example_workflows/example_workflow_2.json](example_workflows/example_workflow_2.json)

---

## 📋 系统要求

- **Python**：3.10 / 3.11 / 3.12
- **PyTorch**：>= 2.0
- **Pillow**：>= 10.0.0（强制要求——`Image.ANTIALIAS` 已被删除）
- **moviepy**：1.x 或 2.x（两者皆可）
- **transformers**：>= 4.30
- **librosa, matplotlib, scipy, requests, pyspellchecker**

完整依赖列表：[requirements.txt](requirements.txt)。该文件是**纯 ASCII**，
所以在中文 Windows（默认 locale 是 GBK）下也能正常安装——
之前的版本有非 ASCII 注释导致 `pip install` 报 `UnicodeDecodeError` 错误。

---

## ⚡ 性能说明

- **首次运行** Speech Recognition / Generate Audio 会下载模型权重
  （约 1-2 GB）。**后续运行很快**，因为权重被 `lru_cache` 缓存。
- **文字渲染** 比原版快 **5-10 倍**（在长字幕上尤其明显），因为
  逐字符描边像素循环被替换为 PIL 原生 `stroke_width` 光栅化。
- **字体加载** 使用 LRU 缓存；同一字体/大小加载两次几乎免费。

---

## 🔧 故障排查

**搜索框找不到节点。** 输入 `mana` 而不是 `Mana Nodes`。ComfyUI
对节点的 `DESCRIPTION` 类属性做子字符串匹配；最有效的关键词是
`mana`、`caption`（字幕）、`subtitle`（副标题）、
`typography`（排版）、`transcribe`（转录）。

**`NameError: name 'font_manager' is not defined` 或
`NameError: name 'shadow_offset_y' is not defined`。**
ComfyUI 运行的是旧版节点文件。复制最新的
`nodes/font2img_node.py` 覆盖安装目录。

**`pip install` 失败并显示 `UnicodeDecodeError: 'gbk' codec can't
decode byte 0x94`。** `requirements.txt` 被写入了非 ASCII 字符。
本仓库最新版本是纯 ASCII，应该可以正常安装。

**Scheduled Values 图表太小或不缩放。** 确认你运行的是最新的
`web/js/scheduled_values.js`。最新版本使用 `getMinHeight` /
`getMaxHeight`，图表会随画布缩放。

**Deprecation 警告：`/scripts/ui.js`、`groupNode.js`、
`buttonGroup.js`、`button.js`。** 这些来自其他 ComfyUI 扩展，
**不是来自 Mana**。最新的 Mana 代码不导入这些路径。

**Deprecation 警告：`scripts/widgets.js`。** 来自 Mana 的
text_preview.js。已在最新版本中移除。

**`ComfyApp graph accessed before initialization`。** ComfyUI
前端初始化竞态条件，不影响功能，等 ComfyUI 修复。

**404 错误：`/api/userdata/...`、`/user.css`。** ComfyUI 首次
启动时尝试加载默认用户数据/样式。修复方法：
```powershell
mkdir H:\ComfyUI\userdata\workflows
mkdir H:\ComfyUI\userdata\subgraphs
"{}" | Out-File -Encoding ascii H:\ComfyUI\userdata\comfy.templates.json
"/* user stylesheet */" | Out-File -Encoding ascii H:\ComfyUI\web\user.css
```

完整文档：[FEATURES.md](FEATURES.md)

---

## 📂 项目结构

```
ComfyUI-Mana-Nodes/
├── __init__.py                # 节点注册 + 搜索别名
├── FEATURES.md                # 10 节点完整输入输出参考
├── README.md                  # 本文件
├── requirements.txt           # 依赖（纯 ASCII）
├── helpers/                   # 共享模块
│   ├── animation.py           # 关键帧数学
│   ├── font_loader.py         # 字体发现 + LRU 缓存
│   ├── logger.py              # 真日志
│   └── utils.py               # 张量/音频工具
├── nodes/                     # 10 个节点实现
├── web/
│   └── js/                    # 4 个前端扩展
├── font_files/                # 11 个示例字体
└── example_workflows/         # 2 个开箱即用工作流
```

---

## 📜 更新日志 (CHANGELOG)

### v2.0.0（2026-09）

全面优化和 Bug 修复版本。**9 个 P0 致命 Bug 修复**、
**文字渲染 5-10 倍性能提升**、完整代码审查和重构。

| 提交 | 关键内容 |
|------|----------|
| `5862f35` | 9 个 P0 修复（阴影重复绘制、ANTIALIAS、subclip 弃用、scheduled_values 类型不匹配、color_animations 格式、Font Properties 缺输入等） + 性能重构（PIL stroke_width、模型/字体 lru_cache） |
| `6c3e007` | requirements.txt：修正为 2026-09 PyPI 实际版本约束 |
| `cbb93f0` | requirements.txt：纯 ASCII 修复中文 Windows GBK 解码错误 |
| `85b899f` | 运行时修复：font_manager NameError + scripts/ui.js 弃用 |
| `b98df75` | 修复 scheduled_values 实际使用时的崩溃（隐藏多年） |
| `c029f1c` | 移除启动 ERROR 日志骚扰 |
| `13bc45a` | 修复节点不随画布缩放自适应 |
| `ab626e3` | 修复运行时 JS 错误：URL 崩溃、init() 崩溃、user.css 404、widgets.js 弃用 |
| `5e878d0` | 新增 FEATURES.md + DESCRIPTION 类属性（节点可搜索） |
| `577cfbb` | 新 README（默认中文，英文作为附录） |
| `f781aaa` | 移除无效的 web/user.css |
| `bf8616d` | 修复 process_single_image 的 shadow_offset_y 未定义 |
| `bffd4b9` | 代码质量清理：移除未用 import、严格相等 |

### v1.0.0（原始版本）

[ForeignGods](https://github.com/ForeignGods) 的初始发布。

---

## 🙏 致谢

- **原作者：** [ForeignGods](https://github.com/ForeignGods)
- **v2.0 维护：** [fogyisland](https://github.com/fogyisland)
- 为 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 构建
- 使用的模型：
  - [Whisper](https://github.com/openai/whisper)（OpenAI）
  - [Bark](https://huggingface.co/suno/bark)（Suno）

## 🤝 贡献

欢迎提交 Bug 报告和拉取请求。如果你的 PR 是行为变更，
请先开 issue 讨论。

## ⭐ 支持项目

如果 Mana Nodes 节省了你的时间，欢迎给仓库点 ⭐ Star，
并请 [原作者喝杯咖啡](https://buymeacoffee.com/foreigngods)。

---

# English Version

> English version is provided for international users. If you prefer
> Chinese, scroll up — the rest of this README is in Chinese.

## ComfyUI Mana Nodes

A collection of **10 custom nodes** for ComfyUI focused on text-based
content creation: dynamic captions, animated typography,
speech-to-text, and video/audio utilities.

> **Search tip:** In the ComfyUI node-search box, type `mana`,
> `caption`, `subtitle`, `typography`, or `transcribe` to find the
> relevant nodes.

### What's New in v2.0

A **maintenance + optimization release** of the original
[ComfyUI-Mana-Nodes](https://github.com/ForeignGods/ComfyUI-Mana-Nodes) by
[ForeignGods](https://github.com/ForeignGods). Every node has been
refactored; **no behavior changes for existing workflows**.

#### Bug fixes (10+ critical)

- 9 P0 fixes (shadow double-draw, missing `scheduled_values` input,
  Pillow 10+ ANTIALIAS removal, deprecated `subclip`, etc.)
- Hidden `scheduled_values` crash (was untested for years)
- Runtime JS errors: `Failed to construct 'URL'`, extension init
  failure, missing `user.css` 404
- `process_single_image` variable not defined (shadow y-offset crash)
- Startup ERROR log spam (`[Mana] - ERROR - Mana Web`) removed

#### Performance (5-10x on text rendering)

- Border drawing now uses PIL's native `stroke_width`
- `lru_cache` on font loading (256 entries)
- `lru_cache` on Whisper + Bark model weights
- Class-level cache on video input directory scan
- Pre-computed font metrics in the per-character loop

See [CHANGELOG](#-更新日志-changelog) for the full per-commit list.

### Quick start

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
git clone https://github.com/fogyisland/ManaNodesUpdate.git ComfyUI-Mana-Nodes
cd ComfyUI-Mana-Nodes
pip install -r requirements.txt
# Restart ComfyUI
```

For full English documentation, see [FEATURES.md](FEATURES.md) (English).

### Requirements

- Python 3.10 / 3.11 / 3.12
- PyTorch >= 2.0
- Pillow >= 10.0.0
- moviepy 1.x or 2.x
- transformers >= 4.30
- librosa, matplotlib, scipy, requests, pyspellchecker

### Credits

- Original author: [ForeignGods](https://github.com/ForeignGods)
- v2.0 maintenance: [fogyisland](https://github.com/fogyisland)
- Built for [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
