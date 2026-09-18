# Motion HTML 故事网页指南

简体中文 | [English](sn-motion-html.md)

[`sn-motion-html`](../skills/sn-motion-html/SKILL.md) 把一组图片和一段简短叙事编排成一个随滚动推进的网页，并把同一份故事导出为分镜稿。读者滚动，页面对应地在单一固定媒体舞台上按章节顺序前进，每一章的文案都在自己的场景上完整可读。

适合图片故事、滚动产品展示、图像时间线和沉浸式场景浏览。单张信息图、海报或长图属于 [`sn-infographic`](../skills/sn-infographic/SKILL.md)；参考图改版属于 [`sn-image-imitate`](../skills/sn-image-imitate/SKILL.md)。普通网页应用、后台仪表盘和自动播放视频页面不在范围内。

## 产物

- 可复用的项目，而不是一次性的 HTML 文件：网页源码、`content/story.json`、验收过的图片、网页压缩图和简短说明。
- 可编辑的内容：章节、文案、导航标签和来源都在 `content/story.json` 里。
- 单一固定媒体舞台加一条有序路线，通过页头、面板材质、字体层级、导航和每章文案位置来体现风格。
- 分镜稿：`exports/storyboard.md` 与 `exports/storyboard.html`，由同一份故事数据生成，不滚动网页也能一次读完整套镜头顺序，可批注、可打印。
- 减少动态效果时仍可阅读的静帧路径。

展示海报（有自己主题和重点信息的成图）是按需交付的独立成果，由 [`sn-infographic`](../skills/sn-infographic/SKILL.md) 制作并保存为 `exports/story-poster.png`，和本技能写出的网页压缩图不是一回事。

## 环境要求

只需要 Python、Pillow 和浏览器。生成新静帧时复用现有 SenseNova 运行层，不安装第二套图片客户端。已有图片可以直接使用，因此整套流程可以做到零模型调用。

| 能力 | 是否需要 |
|---|---|
| Python + Pillow | 必需 |
| SenseNova 凭证 | 仅在生成新静帧或展示海报时需要 |
| FFmpeg 与 ffprobe | 仅视频片段需要：归一化与校验 |
| Agnes 凭证（`AGNES_API_KEY`） | 仅视频片段需要 |
| 图床或公网存储 | 仅当片段以你自己的静帧为锚点（`anchor_mode: url`）时需要 |

没有 FFmpeg、ffprobe 和任何视频凭证时，图片故事依然可以完成初始化、制作、校验、导出和交付。这是一个受支持的配置，不是降级状态。

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
| `--media` | `images`（默认）或 `video`（后置阶段，见文末说明）。 |
| `--lang` | `zh` 或 `en`。设置界面语言与 `html lang`。 |
| `--force` | 合并非空目录。 |

风格与界面是两个独立选项，不要从一个推断另一个。

`--force` 只刷新模板脚手架，绝不覆盖 `content/story.json`、`assets/`、`.env`、`tmp/` 和 `.motion-state/`，并会打印实际保留的文件。

图片项目有意不生成视频清单、视频凭证文件和空的视频目录，避免暗示项目并不具备的视频依赖。

## 制作流程

1. 收集主题、受众、语言、目标设备、章节规模、已有图片、参考图和事实要求。用户已明确给出的要求计入决策，不重复提问。
2. 事实型故事先做研究，来源笔记与展示文案分开保存。
3. 产出章节蓝图：每章一个主导视觉事件、对应静帧、文案和文案位置；值得记录时同时写下镜头意图（`intent`、`framing`、`motionNote`）。
4. 提交一份评审包，同时覆盖视觉方向与章节安排，并记录用户的决定。
5. 需要新静帧时，先做小规模一致性验证（通常取开头、中间、结尾），方向确认后再完成整套静帧。复用现有 SenseNova 运行层，见 [`sn-image-base`](../skills/sn-image-base/SKILL.md)。
6. 文字交给 HTML，不要放进像素。正文、标题、导航标签和来源都留在 `content/story.json`，便于继续编辑和翻译。
7. 无损母版存入 `assets/images/scenes/`，再生成网页压缩图。
8. 需要在一次阅读里审完整个故事时，导出分镜稿。
9. 校验、查看联系表、在桌面／平板／手机三种宽度用全新浏览器会话验收，然后交付。

## 常用命令

可在任意目录执行；所有路径都是绝对路径。

```bash
# 校验故事数据与静帧（不会调用 ffprobe）
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/verify_media.py" "<absolute PROJECT_ROOT>"

# 由 PNG 母版生成页面实际加载的网页压缩图
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/make_posters.py" "<absolute PROJECT_ROOT>"

# 导出分镜稿：Markdown 与静态 HTML
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/export_storyboard.py" "<absolute PROJECT_ROOT>"

# 生成带标注的评审联系表（默认写入系统临时目录）
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/contact_sheet.py" "<absolute PROJECT_ROOT>"

# 本地预览
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/serve_project.py" "<absolute PROJECT_ROOT>" --port 8080
```

`verify_media.py` 全部通过时返回 `0`，检查失败返回 `1`，声明媒体缺失返回 `2`。`--allow-missing` 会把缺失媒体的情况改为返回 `0`，适合项目尚在组装时使用。

`export_storyboard.py` 成功返回 `0`，故事数据非法返回 `1`，声明的静帧缺失返回 `2`。它没有 allow-missing 选项：一份指向不存在图片的分镜稿本身就是坏件。任何一项检查不通过时它不会写出文件。

## 分镜稿

`exports/storyboard.md` 与 `exports/storyboard.html` 由 `content/story.json` 生成，按章节顺序列出每一个镜头及其静帧、正文、标签、章节 ID 和已声明的镜头意图。

- 它们是生成物，不是手写文档：改完 `content/story.json` 重新导出即可。手工修改会在下次导出时丢失。
- 两份文档的镜头顺序、正文和来源完全一致，不会互相漂移。
- Markdown 适合继续编辑和比对差异；图片路径是相对 `exports/` 的，支持渲染 Markdown 的编辑器能直接显示图片。
- HTML 是静态的可打印文档：不需要服务器、不加载任何 JavaScript，宽屏双栏、窄屏自动堆叠，打印时每个镜头不被拆页，并带打印样式。它不是滚动故事页，也不共用故事页的运行层。
- 预览服务只提供正式导出物：`exports/storyboard.html`、`exports/story-poster.png`，以及可选的其他海报方向 `exports/story-poster-clarity.png`、`exports/story-poster-photo.png`；Markdown 和 `exports/` 下的其他文件都不对外提供。

## 项目结构

```text
index.html               入口页面
styles.css               舞台与界面处理
src/app.js               读取并校验 story.json，本地化界面
src/motion-runtime.js    编排舞台、进度映射与交叉淡化
content/story.json       可编辑的故事：meta、章节、来源
prompts/style-preamble.txt   选定的图片风格块
prompts/style-motion.txt     选定的运动块（初始化时写入，图片故事不会读取）
assets/images/scenes/    场景静帧及其网页压缩图
exports/                 导出后的 storyboard.md、storyboard.html 与按需生成的 story-poster.png
scripts/                 项目自带的校验、压缩、分镜、联系表和预览工具（视频项目另有片段流水线 agnes_video.py）
```

## 预览与托管

`scripts/serve_project.py` 是本地预览服务，不是部署目标。它只提供页面真正需要的文件——入口 HTML、`styles.css`、`src/` 下的 JavaScript、`content/` 下的 JSON、`assets/` 下的正式媒体，以及 `exports/storyboard.html`——并拒绝配置文件、提示词、脚本、私有状态、临时文件、点号开头的文件、目录列表，以及解析后落在项目之外的路径。它支持范围请求，媒体可以拖动定位。

请通过 HTTP 打开页面。页面用 `fetch` 读取 `content/story.json`，所以直接用文件系统打开 `index.html` 不会工作。导出的分镜 HTML 例外：直接打开、经 HTTP 预览或打印都可以。

## 排障

- **预览拒绝某个文件。** 只有上面列出的路径会被提供。把素材移到 `assets/` 下；如果它是故事数据，则改为从 `content/` 引用。
- **提示无法读取故事数据。** 页面是通过 `file://` 打开的，或者 `content/story.json` 不存在。请使用预览服务。
- **提示故事数据不完整。** `meta`、`chapters` 或章节列表缺失、为空。错误信息会指出具体字段。
- **`verify_media.py` 返回 1。** 某个声明值非法：章节 `id` 不安全、`id` 重复、`span` 非正数、`shot` 字段不是非空字符串、枚举值未知，或图片无法解码。具体问题会逐项打印。
- **`verify_media.py` 返回 2。** 有静帧缺失，报告会逐条列出。组装阶段可用 `--allow-missing`。
- **`export_storyboard.py` 返回 2。** 有声明的静帧缺失，且没有写出任何文件。补上图片后重新导出；「待配图」草稿属于评审环节，不放进 `exports/`。
- **分镜稿的修改不见了。** 导出文件是生成物。请改 `content/story.json` 后重新导出。
- **某张静帧被判为无法读取。** 文件不是可解码图片，或被截断。请重新导出。
- **`make_posters.py` 报告找不到 PNG 母版。** 静帧本身已是网页格式，或母版不在 `assets/images/scenes/` 下。请让 `content/story.json` 指向实际拥有的网页格式文件。
- **需要的是海报，不是压缩图。** `make_posters.py` 只把已有静帧压小，不做版式和文字。带标题和重点信息的展示海报是交给 [`sn-infographic`](../skills/sn-infographic/SKILL.md) 的独立任务，交付为 `exports/story-poster.png`；请明确说明，因为它有自己的生成与评审流程。
- **联系表标签只有编号。** 本机没有找到支持中文的字体，标签退化为编号以保证可读。安装中文字体即可恢复标题。
- **页面显示回退面板。** 该静帧加载失败；检查 `content/story.json` 中的路径和网络面板。
- **成片里能看到水印或品牌字样。** 水印在像素里，CSS 无法去除，必须在交付前用联系表逐张确认。若静帧由外部工具生成，请先用不带水印的档位重新出图，或按输出方约定处理；本仓库的图像能力默认 `watermark=false`。
- **界面语言与内容不一致。** `meta.lang` 缺失时页面会按内容的字形推断（中文内容判为 `zh`），但推断结果不如显式声明确定。请补写 `meta.lang`。
- **页面完全没有动效。** 系统关闭了动画（Windows 的「在 Windows 中显示动画」等）时浏览器会上报 `prefers-reduced-motion: reduce`，技能会据此关闭图片缩放——这是正确行为，不是故障。审阅时可在地址后加 `?motion=full` 强制完整动效，加 `?motion=reduce` 强制减弱；不带参数时始终以系统偏好为准。
- **淡化太快或太慢、缩放幅度不合适。** 用 `meta.crossfade`（单位：视口高度，图片模式默认 0.8）和 `meta.drift`（单章缩放幅度，图片模式默认 0.16）调整。

## 视频片段（Agnes video）

仅在明确要求时使用。片段由 Agnes video 生成，经由兄弟技能 `agnes-media` 自带的 CLI，由 `scripts/agnes_video.py` 驱动。默认模型是 `agnes-video-v2.0`，输出高清片段（默认 `1080p`，交付目标 1920×1080）；`agnes-video-2.5-flash` 是备选，用于需要参考图或只能锚定尾帧的场合，它上限为 720P。请求契约、约束与实测表现见 [references/agnes-video.md](../skills/sn-motion-html/references/agnes-video.md)，流程见 [references/workflow.md](../skills/sn-motion-html/references/workflow.md) 第 10 节。

```bash
# 只打印将要发起的调用，不消耗任何额度
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/agnes_video.py" "<absolute PROJECT_ROOT>" --dry-run

# 生成、归一化，并把每个片段的首帧写成页面静帧
"<absolute PYTHON path>" "<absolute PROJECT_ROOT>/scripts/agnes_video.py" "<absolute PROJECT_ROOT>" \
  --image-cli "<absolute BASE_SKILL_DIR>/scripts/sn_agent_runner.py" \
  --agnes-cli "<absolute AGNES_SKILL_DIR>/scripts/agnes_media.py" --write-stills
```

前置条件：进程环境或项目被忽略的 `.env` 中配置 `AGNES_API_KEY`，准备 FFmpeg、ffprobe，并传入上面的客户端绝对路径（或配置 `AGNES_SKILL_DIR`、`SN_IMAGE_BASE_DIR`）。流水线只从项目 `.env` 读取相关提供方设置，进程变量优先，不展开变量或执行脚本；`python-dotenv` 已包含在 SenseNova 运行时依赖中。生成锚图还需要 SenseNova 凭据。纯图片项目无需 Agnes 或视频工具。PowerShell 中在引号包围的 Python 路径前加 `&`。

要片段之前，有两点值得先知道：

- **图片生成、编辑、修复、增强和合成都使用 SenseNova，Agnes 只生成视频。** 每个片段必须显式选择 `generate`（SenseNova 生成锚图）、`reference`（显式参考图或相邻章节锚图）、`url`（已托管的首末帧）。缺失模式和 `text` 均会被拒绝。自动锚图路径固定使用 SenseNova 后端及 U1.5 模型，并禁用回退。本技能不会自行公开发布你的图片。
- **提供方输出不是成品。** 实测请求 1920×1080 返回 1920×1088，请求 720P 返回 1280×704 且时长 4.46 秒，所以流水线一律本地归一化；随后 `verify_media.py` 要求严格等于清单声明的尺寸、帧率与时长。

过渡片段可借用两章的公开锚图 URL；v2.0 将其作为首末关键帧。它们不一定等于上一段视频的实际尾帧，因此需要目视检查接缝。URL 缺失会阻止生成；若已接受硬切，可在故事的连接项写 `null`，并从生成清单中移除对应连接片段。

图片模式保留 SenseNova 4K PNG 母版，默认压缩为 2560px WebP；要求网页本身加载 4K 时使用 `make_posters.py --max-width 4096`，并核验浏览器实际加载尺寸。视频模式的 `--write-stills` 则按视频交付尺寸抽取静帧，通常为 1080p。本地压缩、保存和视频抽帧不调用图片模型。
