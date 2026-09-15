# Motion HTML 故事网页指南

简体中文 | [English](sn-motion-html.md)

[`sn-motion-html`](../skills/sn-motion-html/SKILL.md) 把一组图片和一段简短叙事编排成一个随滚动推进的网页。读者滚动，页面对应地在单一固定媒体舞台上按章节顺序前进，每一章的文案都在自己的场景上完整可读。

适合图片故事、滚动产品展示、图像时间线和沉浸式场景浏览。单张信息图、海报或长图属于 [`sn-infographic`](../skills/sn-infographic/SKILL.md)；参考图改版属于 [`sn-image-imitate`](../skills/sn-image-imitate/SKILL.md)。普通网页应用、后台仪表盘和自动播放视频页面不在范围内。

## 产物

- 可复用的项目，而不是一次性的 HTML 文件：网页源码、`content/story.json`、验收过的图片、网页海报和简短说明。
- 可编辑的内容：章节、文案、导航标签和来源都在 `content/story.json` 里。
- 单一固定媒体舞台加一条有序路线，通过页头、面板材质、字体层级、导航和每章文案位置来体现风格。
- 由无损母版生成网页海报，压缩不会覆盖原图。
- 减少动态效果时仍可阅读的静帧路径。

## 环境要求

图片模式是默认路径，只需要 Python 和 Pillow。需要新静帧时复用现有的 SenseNova 运行层，不安装第二套图片客户端。

| 能力 | 图片模式（默认） | 视频模式（需显式选择） |
|---|---|---|
| Python + Pillow | 必需 | 必需 |
| SenseNova 凭证 | 仅在生成新静帧时需要 | 仅在生成新静帧时需要 |
| FFmpeg + ffprobe | 不使用 | 必需 |
| 视频服务凭证 | 不使用 | 必需 |

没有 FFmpeg、ffprobe 或任何视频凭证时，图片故事依然可以完成初始化、制作、校验和交付。这是一个受支持的配置，不是降级状态。

## 媒体模式

每个项目在 `content/story.json` 的 `meta.mediaMode` 记录自己的模式：

- `images`——默认。每章需要一张有效静帧。不要求 `clip` 和 `connectors`；即使残留这些字段，页面也不会请求片段。
- `video`——仅在明确要求时使用。每章需要静帧和场景片段，每对相邻章节需要连接片段。此时才需要 FFmpeg、ffprobe 和服务凭证。

显式的 `images` 优先于残留的视频字段。没有 `mediaMode` 的项目只有在确实声明了片段或连接片段时才按视频处理，否则按图片处理。

## 初始化项目

先解析这些逻辑路径。它们是执行时的解析结果，不是需要配置的环境变量。

- `PYTHON`——通过 [`sn-image-doctor`](../skills/sn-image-doctor/SKILL.md) 的解释器。
- `MOTION_SKILL_DIR`——包含技能 `SKILL.md` 的目录。
- `PROJECT_ROOT`——故事的输出目录。

```bash
"<absolute PYTHON path>" "<absolute MOTION_SKILL_DIR>/scripts/init_project.py" "<absolute PROJECT_ROOT>" \
  --title "故事标题" \
  --style cinematic \
  --ui folio \
  --media images \
  --lang zh
```

| 选项 | 含义 |
|---|---|
| `--title` | 故事标题。引号、反斜杠和 HTML 字符都会被安全转义。 |
| `--style` | `anime`、`cinematic` 或 `cgi`。控制视觉世界与静帧提示词。 |
| `--ui` | `folio`、`caption` 或 `graphic`。控制页头、文案处理、导航和字体层级。 |
| `--media` | `images`（默认）或 `video`。 |
| `--lang` | `zh` 或 `en`。设置界面语言与 `html lang`。 |
| `--force` | 合并非空目录。 |

风格与界面是两个独立选项，不要从一个推断另一个。

`--force` 只刷新模板脚手架，绝不覆盖 `content/story.json`、`assets/`、`.env`、`tmp/` 和 `.motion-state/`，并会打印实际保留的文件。

图片项目有意不生成视频清单、视频凭证文件和空的视频目录，避免暗示项目并不具备的视频依赖。

## 制作流程

1. 收集主题、受众、语言、目标设备、章节规模、已有图片、参考图和事实要求。用户已明确给出的要求计入决策，不重复提问。
2. 事实型故事先做研究，来源笔记与展示文案分开保存。
3. 产出章节蓝图：每章一个主导视觉事件、对应静帧、文案和文案位置。
4. 提交一份评审包，同时覆盖视觉方向与章节安排，并记录用户的决定。
5. 需要新静帧时，先做小规模一致性验证（通常取开头、中间、结尾），方向确认后再完成整套静帧。复用现有 SenseNova 运行层，见 [`sn-image-base`](../skills/sn-image-base/SKILL.md)。
6. 文字交给 HTML，不要放进像素。正文、标题、导航标签和来源都留在 `content/story.json`，便于继续编辑和翻译。
7. 无损母版存入 `assets/images/scenes/`，再生成网页海报。
8. 校验、查看联系表、用全新浏览器会话验收，然后交付。

## 常用命令

可在任意目录执行；所有路径都是绝对路径。

```bash
# 校验故事数据与静帧（图片模式不会调用 ffprobe）
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"

# 由 PNG 母版生成网页海报
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/make_posters.py" "<absolute PROJECT_ROOT>"

# 生成带标注的评审联系表（默认写入系统临时目录）
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"

# 本地预览
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

`verify_media.py` 全部通过时返回 `0`，检查失败返回 `1`，声明媒体缺失返回 `2`。`--allow-missing` 会把缺失媒体的情况改为返回 `0`，适合项目尚在组装时使用。

## 项目结构

```text
index.html               入口页面
styles.css               舞台与界面处理
src/app.js               读取并校验 story.json，本地化界面
src/motion-runtime.js    编排舞台、进度映射与交叉淡化
content/story.json       可编辑的故事：meta、章节、来源
prompts/style-preamble.txt   选定的图片风格块
prompts/style-motion.txt     选定的运动块（视频模式）
assets/images/scenes/    场景静帧及其海报
scripts/                 项目自带的校验、海报、联系表和预览工具
```

视频项目额外包含 `prompts/video-manifest.json`、`prompts/video/`、`assets/video/`、`.env` 和 `scripts/seedance_pipeline.py`。

## 预览与托管

`scripts/serve_project.py` 是本地预览服务，不是部署目标。它只提供页面真正需要的文件——入口 HTML、`styles.css`、`src/` 下的 JavaScript、`content/` 下的 JSON，以及 `assets/` 下的正式媒体——并拒绝配置文件、提示词、脚本、私有状态、临时文件、点号开头的文件、目录列表，以及解析后落在项目之外的路径。它支持范围请求，媒体可以拖动定位。

请通过 HTTP 打开页面。页面用 `fetch` 读取 `content/story.json`，所以直接用文件系统打开 `index.html` 不会工作。

## 排障

- **预览拒绝某个文件。** 只有上面列出的路径会被提供。把素材移到 `assets/` 下；如果它是故事数据，则改为从 `content/` 引用。
- **提示无法读取故事数据。** 页面是通过 `file://` 打开的，或者 `content/story.json` 不存在。请使用预览服务。
- **提示故事数据不完整。** `meta`、`chapters` 或章节列表缺失、为空。错误信息会指出具体字段。
- **`verify_media.py` 返回 2。** 有静帧或片段缺失，报告会逐条列出。组装阶段可用 `--allow-missing`。
- **`verify_media.py` 返回 1。** 某个声明值非法：章节 `id` 不安全、`id` 重复、`span` 非正数、枚举值未知，或图片无法解码。具体问题会逐项打印。
- **某张静帧被判为无法读取。** 文件不是可解码图片，或被截断。请重新导出。
- **`make_posters.py` 报告找不到 PNG 母版。** 静帧本身已是网页格式，或母版不在 `assets/images/scenes/` 下。请让 `content/story.json` 指向实际拥有的网页格式文件。
- **联系表标签只有编号。** 本机没有找到支持中文的字体，标签退化为编号以保证可读。安装中文字体即可恢复标题。
- **页面显示回退面板。** 该静帧加载失败；检查 `content/story.json` 中的路径和网络面板。
- **成片里能看到水印或品牌字样。** 水印在像素里，CSS 无法去除，必须在交付前用联系表逐张确认。若静帧由外部工具生成，请先用不带水印的档位重新出图，或按输出方约定处理；本仓库的图像能力默认 `watermark=false`。
- **界面语言与内容不一致。** `meta.lang` 缺失时页面会按内容的字形推断（中文内容判为 `zh`），但推断结果不如显式声明确定。请补写 `meta.lang`。
- **页面完全没有动效。** 系统关闭了动画（Windows 的「在 Windows 中显示动画」等）时浏览器会上报 `prefers-reduced-motion: reduce`，技能会据此关闭图片缩放——这是正确行为，不是故障。审阅时可在地址后加 `?motion=full` 强制完整动效，加 `?motion=reduce` 强制减弱；不带参数时始终以系统偏好为准。
- **淡化太快或太慢、缩放幅度不合适。** 用 `meta.crossfade`（单位：视口高度，图片模式默认 0.8）和 `meta.drift`（单章缩放幅度，图片模式默认 0.16）调整。
- **视频模式提示需要 ffprobe。** 视频校验需要安装 FFmpeg。图片模式绝不需要。

## 可选视频片段

片段生成是独立且需明确授权的交付物。生成片段尚未存在时，不得把图片故事描述为具有生成式连续镜头的成果。

在任何按量或付费请求之前，先说明服务商、模型、计划片段数、允许重试次数和费用依据，并就该批次取得授权。对故事的创意确认不等于生成授权。没有凭证时，仍可离线校验清单并交付图片故事。

依赖顺序是固定的：先生成场景片段，抽取真实首尾帧，再由相邻边界帧生成连接片段。所有最终片段归一化为相同的编码、尺寸、帧率、精确时长、短 GOP 和 `faststart`。Ark 请求契约见 [references/seedance.md](../skills/sn-motion-html/references/seedance.md)，使用前请核实当前模型文档。
