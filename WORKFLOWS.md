# Mana Nodes 详细工作流指南

> 本文档详细说明 4 个核心功能的完整流程、每个参数的具体含义，
> 以及典型场景的最佳实践。配合 [FEATURES.md](FEATURES.md) 的节点
> 参数参考使用。

---

## 目录

1. [文字动画（Scheduled Values + Font Properties）](#1-文字动画)
2. [画布动画（Canvas + 文字组合）](#2-画布动画)
3. [语音识别（Speech Recognition 完整流程）](#3-语音识别)
4. [字幕生成（从音频到完整字幕视频）](#4-字幕生成)

---

# 1. 文字动画

**功能**：让文字的任意属性（字号、颜色、位置、旋转）随时间变化。
**涉及节点**：`Scheduled Values` + `Font Properties` + `Text to Image Generator`

## 完整工作流

```
[Scheduled Values] -> scheduled_values -> [Font Properties]
                                               -> font
                                          [Text to Image Generator]
[Font Properties (静态部分)] -> font ——/         |
[Canvas Properties]            -> canvas ——————/
[text input]                   -> text
[frame_count: 60]              -> frame_count
```

## 步骤详解

### 步骤 1：放置 Scheduled Values 节点

在画布上添加 `⏰ Scheduled Values` 节点。该节点会显示一个**交互式图表**：

- **X 轴**：帧号（1 到 frame_count）
- **Y 轴**：数值（-value_range 到 +value_range）
- **关键帧**：在图表上显示为小方块

**操作关键帧**：
- **添加**：点击图表任意位置
- **编辑**：双击关键帧打开小输入框
- **删除**：点击徽章上的垃圾桶图标
- **复制**：暂不支持，需要重新添加

**生成插值**：
1. 添加至少 2 个关键帧
2. 选择缓动类型（linear / easeInQuad / ...）
3. 点击 "Generate Values" 按钮
4. 系统在关键帧之间插入过渡值
5. 点击 "Delete Generated" 可清除插值（保留原始关键帧）

### 步骤 2：配置 Scheduled Values 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `frame_count` | INT | 30 | 关键帧的帧范围上限。**必须与 Text to Image 的 frame_count 一致** |
| `value_range` | INT | 15 | Y 轴显示范围。值范围是 -value_range 到 +value_range。例如 value_range=100，则图表显示 -100 到 100 |
| `easing_type` | dropdown | linear | 14 种缓动函数（见下表） |
| `step_mode` | dropdown | single | `single` 显示每个整数刻度；`auto` 自动去除重叠刻度 |
| `animation_reset` | dropdown | word | 何时重新启动动画（见下表） |
| `id` | INT | 0 | 自动生成的唯一 ID。**不要手动改** |

**缓动类型**：
- `linear` - 线性
- `easeInQuad / easeOutQuad / easeInOutQuad` - 二次方
- `easeInCubic / easeOutCubic / easeInOutCubic` - 三次方
- `easeInQuart / easeOutQuart / easeInOutQuart` - 四次方
- `easeInQuint / easeOutQuint / easeInOutQuint` - 五次方
- `exponential` - 指数

**animation_reset 行为**：
- `word` - 每当文字变化一个**单词**时重新启动动画
- `line` - 每当文字变化一**行**时重新启动
- `never` - 只播放一次
- `looped` - 无限循环
- `pingpong` - 来回播放

### 步骤 3：连接 Font Properties

在 `Font Properties` 节点的某个**可动画属性**上右键 → "Convert widget to input"，
该属性变成一个橙色连接点。然后连接 `Scheduled Values` 的 `scheduled_values` 输出。

**所有可动画属性**：
- `font_size` - 字号
- `x_offset` / `y_offset` - 位置
- `rotation` - 旋转角度
- `font_color` - 字体颜色
- `border_color` - 描边颜色
- `shadow_color` - 阴影颜色

**重要提示**：
- 一个 Scheduled Values 节点只能驱动 Font Properties 的**一个属性**
- 想同时动画多个属性？用**多个 Scheduled Values 节点**
- `scheduled_values` 数据格式：`[{"x": 帧号, "y": 数值}, ...]$动画重置模式`

### 步骤 4：完整示例

**场景**：文字 "BOOM!" 从小到大、从远到近飞来

1. **Scheduled Values** (字号动画)
   - 添加关键帧：(1, 10) → (60, 200)
   - easing_type: easeInQuad
   - 连接到 Font Properties 的 `font_size`

2. **Font Properties** 设置：
   - font_size: 75（被 Scheduled Values 覆盖）
   - font_color: red
   - 其他属性保持默认

3. **Canvas Properties** 设置：
   - width: 512, height: 512
   - background_color: black
   - text_alignment: center center

4. **Text to Image Generator** 设置：
   - text: "BOOM!"
   - frame_count: 60

5. 输出：60 帧动画，从 10px 字号放大到 200px

---

# 2. 画布动画

**功能**：让背景/画布随时间变化（颜色切换、图片轮播、背景移动）。
**涉及节点**：`Canvas Properties` + 可选 `Scheduled Values` 或 `Preset Color Animations`

## 完整工作流

```
[Scheduled Values / Preset Color Animations] -> scheduled_values -> [Canvas Properties]
                                                                       -> canvas
                                                                  [Text to Image Generator]
[Font Properties] -> font
[text input]      -> text
[frame_count: N]  -> frame_count
```

## 步骤详解

### 步骤 1：基础 Canvas Properties 配置

`Canvas Properties` 定义画布的所有视觉属性：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `width` / `height` | INT | 512 | 输出尺寸（像素） |
| `background_color` | STRING | black | 背景色。接受 CSS 颜色名（black, white, red, transparent）、`rgb(r,g,b)` 或 `#RRGGBB` |
| `text_alignment` | dropdown | center center | 9 种对齐方式：left/center/right × top/center/bottom |
| `padding` | INT | 0 | 文字到画布边缘的距离（像素） |
| `line_spacing` | INT | 5 | 多行文字之间的间距 |
| `images` | IMAGE (optional) | - | **背景图张量**。如果提供，**完全覆盖 background_color** |

### 步骤 2：静态背景（最简单）

```
Canvas Properties:
  width: 1024, height: 1024
  background_color: "#1a1a1a"
  text_alignment: center center
  padding: 50
  line_spacing: 10
```

### 步骤 3：动态背景色（用 Preset Color Animations）

**用彩虹色循环背景**：

1. 添加 `🌈 Preset Color Animations` 节点
2. 配置：
   - color_preset: rainbow
   - animation_duration: 30（30 帧循环一次）
   - animation_reset: looped
3. 转换 Canvas Properties 的 `background_color` 为输入
4. 连接输出

**结果**：背景色在 30 帧内从红→橙→黄→绿→蓝→紫循环

### 步骤 4：背景图轮播

如果有 IMAGE 张量序列（来自视频、生成的图像等）：

1. 连接到 `Canvas Properties` 的 `images` 输入
2. **注意**：如果提供了 `images`，`background_color` 被忽略
3. 每帧使用对应的图像作为背景

**示例**：从视频提取的帧作为字幕背景

```
[Split Video (frames output)] -> [Canvas Properties (images input)]
                                       -> canvas
                                  [Text to Image Generator]
[Font Properties] -> font
```

### 步骤 5：移动背景（高级）

通过 `x_offset` / `y_offset` 动画实现：

**注意**：Canvas Properties 的 `padding` 不是动画的。
但 Font Properties 的 `x_offset` / `y_offset` **是动画的**，
可以用来移动文字（看起来像背景在动）。

---

# 3. 语音识别

**功能**：把音频文件转录为带时间戳的文字。
**涉及节点**：`Speech Recognition`

## 完整工作流

```
[LoadAudio] -> audio_file -> [Speech Recognition]
                                    |
                                    |-> transcription (TRANSCRIPTION object)
                                    |-> raw_string
                                    |-> framestamps_string
                                    |-> timestamps_string
```

## 输入参数详解

### 必需输入

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `audio_file` | STRING | - | 音频文件路径或 URL。本地文件：`H:\ComfyUI\input\audio\myfile.wav`。URL：`https://example.com/audio.mp3` |
| `asr_model` | dropdown | whisper-small | Whisper 模型档位。5 档可选。**自动检测 99 种语言**，无需按语言切换 |
| `language` | STRING | auto | 强制指定语言（ISO 639-1 码，如 `zh` / `en` / `ja`）。默认 `auto` 让 Whisper 自动检测 |
| `spell_check_language` | dropdown | English | 拼写校正语言（仅拉丁字母生效） |
| `framestamps_max_chars` | INT | 25 | 字幕最大字符数。超过则新起一行 |
| `fps` | INT | 30 | 帧率。决定每个时间戳对应的帧号 |
| `transcription_mode` | dropdown | fill | 见下表 |
| `uppercase` | BOOLEAN | true | 是否转为大写 |

### Whisper 模型档位选择

| 模型 | 大小 | 适用场景 |
|------|------|----------|
| `whisper-tiny` | 75 MB | 仅测试 / 实时优先 / 低算力 |
| `whisper-base` | 140 MB | 简单英文短句 |
| `whisper-small` | 460 MB | **平衡首选**（中文够用，下载快） |
| `whisper-medium` | 1.5 GB | 中文歌曲 / 多语种混合 |
| `whisper-large-v3` | 3 GB | 最高精度 / 嘈杂音频 |

### transcription_mode 三种模式对比

**示例音频**：`"THE GREATEST TRICK THE DEVIL EVER PULLED..."`

#### 模式 1：`word`（逐词）

每帧一个单词。适合做卡拉OK 效果。

输出：
```
"27": "THE",
"31": "GREATEST",
"43": "TRICK",
"73": "THE",
...
```

#### 模式 2：`line`（逐行）

每行累积单词，直到行宽超过 `framestamps_max_chars`。
适合做对话式字幕。

输出（max_chars=25）：
```
"1": "THE",
"31": "THE GREATEST",
"43": "THE GREATEST TRICK",
"73": "THE GREATEST TRICK THE",
"77": "DEVIL",
...
```

#### 模式 3：`fill`（累积构建）

每行包含之前所有单词。适合做"打字机效果"字幕。

输出（max_chars=25）：
```
"27": "THE",
"31": "THE GREATEST",
"43": "THE GREATEST TRICK",
...
```

### 输出 4 个字段说明

| 输出 | 类型 | 用途 |
|------|------|------|
| `transcription` | TRANSCRIPTION | **核心输出**。喂给 Text to Image Generator 的 `transcription` 输入 |
| `raw_string` | STRING | 纯文本，可保存到文件 |
| `framestamps_string` | STRING | JSON 帧戳字符串，可粘贴到 Text to Image Generator 的 `text` 输入 |
| `timestamps_string` | STRING | JSON 时间戳数组，每个词带 start_time / end_time |

## 性能说明

- **首次运行**会下载模型（约 1-2 GB）
- **后续运行**使用缓存，几秒钟完成
- 模型在内存中保留直到 ComfyUI 重启

## 常见问题

**Q: 转录是空的？**
- 检查音频文件是否有效（尝试用 VLC 打开）
- Whisper 自动检测语言；如失败，尝试在 `language` 字段强制指定（`zh` / `en` / `ja` 等）
- 确认音频不是纯静音 / 纯背景音乐（Whisper 也需要人声才能识别）
- 查看 ComfyUI 控制台是否有错误

**Q: 转录错字很多？**
- 启用 spell_check（默认开启；CJK 自动跳过）
- 切到 `whisper-medium` 或 `whisper-large-v3`（小模型在嘈杂音频上精度差）
- 中文音频切到 `language="zh"` 强制指定能提升 ~10%
- 歌曲场景建议先人声分离（`audio-separator` / UVR）再喂节点

**Q: 处理太慢？**
- 第一次运行慢是正常的（下载模型）
- 长音频（>10 分钟）可能需要 1-2 分钟

---

# 4. 字幕生成

**功能**：从音频文件生成完整字幕视频（含视频帧 + 文字 + 音频）。
**涉及节点**：`Split Video` + `Speech Recognition` + `Font Properties` + `Canvas Properties` + `Text to Image Generator` + `Combine Video`

## 完整工作流

```
[Load Video] -> [Split Video] -> frames ────┐
                         |                  +-> [Speech Recognition]
                         |                       -> transcription
                         +-> audio_file ───┐   |
                                            |   v
                                            |  [Font Properties] -> font ──┐
                                            |                              +-> [Text to Image Gen]
                                            |  [Canvas Properties] -> canvas ┘  -> images
                                            |  [text: "{}"]          -> text      |
                                            |  [frame_count]         -> frame_count  |
                                            |                                                  v
                                            +────────────────────────────────── [Combine Video]
                                                                                          |
                                                                                          v
                                                                                  [VHS_VideoCombine]
                                                                                  (最终 MP4)
```

## 完整步骤

### 步骤 1：准备输入视频

1. 准备一个视频文件
2. 放入 `H:\ComfyUI\input\video\` 目录
3. 在 ComfyUI 中用 `Load Video`（来自 VideoHelperSuite）加载

### 步骤 2：分割视频（Split Video）

`Split Video` 节点配置：

| 参数 | 说明 |
|------|------|
| `video` | 视频文件（下拉选择） |
| `frame_limit` | 提取多少帧。**应与视频时长 × fps 一致**。30fps × 60秒 = 1800 |
| `frame_start` | 从哪一帧开始。0 = 从头开始 |
| `filename_prefix` | 音频保存路径，默认 `audio\audio` |

**输出**：
- `images` - IMAGE 张量序列（每帧一张图）
- `audio_file` - 提取的音频文件路径
- `fps` - 视频原始帧率
- `frame_count` - 实际提取的帧数

### 步骤 3：语音识别（Speech Recognition）

将 Split Video 的 `audio_file` 连接到 Speech Recognition 的 `audio_file` 输入。

**关键参数**：
- `asr_model` - 默认 `whisper-small`；嘈杂音频选 `whisper-medium` 或 `whisper-large-v3`
- `language` - 默认 `auto`；已知音频语言可强制指定（如中文填 `zh`）提升精度
- `transcription_mode`:
  - **word** - 卡拉OK（每帧一个词）
  - **line** - 标准字幕（每行累积）
  - **fill** - 累积构建（每行越来越多）
- `framestamps_max_chars` - 字幕宽度（推荐 30-50）
- `fps` - **必须与视频帧率一致**！

**输出**：
- `transcription` - 喂给 Text to Image Generator

### 步骤 4：配置文字样式（Font Properties）

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `font_file` | 系统字体 | 如 "Arial" 或自定义字体 |
| `font_size` | 60-100 | 根据画面大小调整 |
| `font_color` | white | 白字配深色背景 |
| `border_width` | 2-4 | 描边让白字在亮背景上可见 |
| `border_color` | black | 黑描边 |
| `shadow_color` | black | 阴影增强可读性 |
| `shadow_offset_x` / `shadow_offset_y` | 2-4 | 阴影偏移 |

**卡拉OK 模式**（逐词高亮）：
- 额外添加**第二个 Font Properties** 节点作为 `highlight_font`
- 这个节点可以设置**不同颜色/字号**用于当前词
- 在 Text to Image Generator 上连接 `highlight_font` 输入

### 步骤 5：配置画布（Canvas Properties）

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `width` | 视频宽度 | **必须与视频帧尺寸一致** |
| `height` | 视频高度 | 同上 |
| `background_color` | transparent | 让视频帧透出 |
| `text_alignment` | center bottom | 标准字幕位置（底部居中） |
| `padding` | 50-100 | 字幕距离底部边缘 |

**关键**：`width` 和 `height` **必须与 Split Video 输出的视频帧尺寸一致**！

### 步骤 6：生成字幕帧（Text to Image Generator）

| 参数 | 说明 |
|------|------|
| `font` | Font Properties 输出 |
| `canvas` | Canvas Properties 输出 |
| `text` | `"{}"`（空 JSON 字典，字幕来自 transcription） |
| `frame_count` | **必须与 Split Video 的 frame_limit 一致** |
| `transcription` | Speech Recognition 输出 |
| `highlight_font` | （可选）高亮字体 |
| `skip_first_frames` | 跳过开头的 N 帧（默认 0） |

**输出**：`images` - 字幕帧的张量序列

### 步骤 7：合成最终视频（Combine Video）

| 参数 | 说明 |
|------|------|
| `images` | 字幕帧 |
| `audio_file` | 原始音频（来自 Split Video） |
| `fps` | 视频帧率（与之前一致） |
| `filename_prefix` | 输出文件名，默认 `video\video` |

**输出**：`video_file` - 最终 MP4 路径

### 步骤 8：保存到磁盘（VHS_VideoCombine）

用 VideoHelperSuite 的 `VHS_VideoCombine` 节点：
- `video`: Combine Video 输出
- `format`: video/h264-mp4
- `save_output`: true

## 常见错误及解决

### 错误 1：字幕位置错乱

**原因**：transcription 的 fps 与视频 fps 不一致
**解决**：在 Speech Recognition 中设置正确的 fps（与视频帧率匹配）

### 错误 2：字幕显示为乱码方块

**原因**：字体不支持某些字符
**解决**：
- 选择支持更广字符集的字体（如思源黑体）
- 或者降低 text 复杂度

### 错误 3：字幕超出画布

**原因**：font_size 太大
**解决**：减小 font_size（建议先在 Font Properties 节点测试）

### 错误 4：视频帧与字幕不同步

**原因**：transcription 的帧号与视频帧不对应
**解决**：
- 检查 Speech Recognition 的 fps 设置
- 检查 frame_count 与 frame_limit 一致
- 已知音频语言时，在 `language` 字段强制指定（如 `zh`）可提升精度

### 错误 5：转换非常慢

**原因**：
- 第一次运行 Whisper 模型（下载 ~75 MB - 3 GB，取决于档位）
- 音频文件很大（> 10 分钟）
- 显卡/CPU 性能不足

**解决**：
- 等待首次下载完成
- 短音频测试
- 升级硬件

---

## 实用技巧

### 技巧 1：测试参数而不渲染完整视频

先用 `PreviewImage` 节点看 Text to Image 的输出，确认样式正确，
再连接 Combine Video。

### 技巧 2：保存转录结果以便复用

连接 Speech Recognition 的 `raw_string` 到 `Save/Preview Text` 节点，
转录结果保存为 .txt 文件，可重复使用。

### 技巧 3：批量生成不同样式的字幕

用 `Save/Preview Text` 节点的 `framestamps_string` 输出，可以拷贝
到 Text to Image 的 `text` 输入。这样不需要每次都跑 Speech Recognition。

### 技巧 4：使用相同音频创建不同语言版本

Whisper 自动检测语言，无需为每种语言准备不同模型。要切语言只需在 `language` 字段指定：
- 中文：`language = "zh"`
- 日文：`language = "ja"`
- 英文：`language = "en"`

### 技巧 5：避免重复下载模型

Whisper 模型被 `lru_cache` 缓存，权重落在
`<ComfyUI>/models/Mana/SpeechRecognition/Whisper/<size>.pt`。
如需清空缓存：删除该目录或重启 ComfyUI。

---

## 完整示例：英语视频加字幕

### 目标
- 输入：`myvideo.mp4`（1280×720, 30fps, 60秒, 英语人声）
- 输出：`subtitled.mp4`（带底部白色字幕）

### 节点配置

**Load Video**:
- video: `video/myvideo.mp4`

**Split Video**:
- video: 上面输出
- frame_limit: 1800（60秒 × 30fps）
- frame_start: 0
- filename_prefix: `audio\myvideo`

**Speech Recognition**:
- audio_file: Split Video 输出
- asr_model: `whisper-small`（默认；英文够用）
- language: `en`（已知是英文，强制指定可提精度）
- spell_check_language: English
- framestamps_max_chars: 40
- fps: **30**（与视频帧率一致）
- transcription_mode: **line**（标准字幕）
- uppercase: true

**Font Properties**:
- font_file: Montserrat-Black
- font_size: 60
- font_color: white
- border_width: 3
- border_color: black
- shadow_color: black
- shadow_offset_x: 2
- shadow_offset_y: 2

**Canvas Properties**:
- width: **1280**（与视频宽度一致）
- height: **720**（与视频高度一致）
- background_color: transparent
- text_alignment: center bottom
- padding: 50
- line_spacing: 10

**Text to Image Generator**:
- font: Font Properties 输出
- canvas: Canvas Properties 输出
- text: `"{}"`
- frame_count: **1800**（与 Split Video 一致）
- transcription: Speech Recognition 输出

**Combine Video**:
- images: Text to Image 输出
- audio_file: Split Video 的 audio_file
- fps: 30
- filename_prefix: `video\subtitled`

**VHS_VideoCombine**:
- video: Combine Video 输出
- format: video/h264-mp4
- save_output: true

### 执行

点击 "Queue Prompt"，等待：
- Speech Recognition: 1-5 分钟（首次）
- Text to Image: 30 秒 - 2 分钟（1800 帧）
- Combine Video: 5-30 秒

最终 MP4 在 `H:\ComfyUI\output\video\`。
