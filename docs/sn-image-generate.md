# SN 图像与可视化指南

简体中文 | [English](sn-image-generate_en.md)

本仓库仅包含 `sn-image-base`、`sn-image-doctor`、`sn-infographic`、`sn-image-imitate`、`sn-image-resume`。

## 默认行为

- `sensenova-u1.5-lite`：首选文生图和图片编辑模型。
- `sensenova-u1-fast`：仅用于可恢复的文生图回退，不支持图片输入。
- `watermark=false`、`prompt_extend=true`、`response_format=b64_json`，结果立即落盘。
- 没有默认 `SN_CHAT_MODEL`；优先由当前 Agent 规划、看图和评审。

模型调用按账号套餐及积分规则计费。`watermark=false` 当前仅在公测期免费，官方说明公测结束后将作为高级付费特性。

请打开 [SenseNova API 官方文档](https://platform.sensenova.cn/docs)，按标题查找 `SenseNova U1.5 Lite` 或 `SenseNova U1 Fast`。文档站的深链接在首次加载时不能可靠定位。

## 配置与检查

```dotenv
SENSENOVA_API_KEY=your-key
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_IMAGE_GEN_MODEL=sensenova-u1.5-lite
SN_IMAGE_GEN_FALLBACK_MODEL=sensenova-u1-fast
```

默认只需配置 `SENSENOVA_API_KEY`。只有不同能力使用不同凭证时才设置覆盖项：

运行时先使用已有进程环境，再读取 `SN_ENV_FILE` 指定的文件，最后从当前工作目录向上查找最近的 `.env`。Doctor 的详细输出会显示所用 Python 和配置文件路径，但不会显示 Key。

| 变量 | 用途 | 读取优先级 |
| --- | --- | --- |
| `SENSENOVA_API_KEY` | 所有能力共用的默认 Key | 共享后备 |
| `SN_IMAGE_GEN_API_KEY` | 图片生成与编辑 | `--api-key` > 本变量 > 共享 Key |
| `SN_CHAT_API_KEY` | 文本与视觉适配器共用的可选 Key | `--api-key` > 能力专用 Key > 本变量 > 共享 Key |
| `SN_TEXT_API_KEY` | 仅文本适配器 | `--api-key` > 本变量 > Chat Key > 共享 Key |
| `SN_VISION_API_KEY` | 仅视觉适配器 | `--api-key` > 本变量 > Chat Key > 共享 Key |

以下命令假定已按[安装说明](../INSTALL_CN.md)创建并激活虚拟环境，`python` 指向安装依赖时使用的解释器。若未激活，请使用该解释器的绝对路径；Agent 宿主也须使用同一解释器。

```bash
python -m pip install -r skills/sn-image-base/requirements.txt
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

宿主必须使用这里通过检查的同一个 Python。Doctor 是离线配置检查；原生编辑任务可加 `--require-edit`。

## 文生图

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-generate \
  --prompt "产品架构信息图，准确中文标签" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path result.png \
  --output-format json
```

支持官方 `2k` / `4k`、本仓库兼容预设 `1k`，以及 `WIDTHxHEIGHT`。`1k` 不会作为 API 常量发送，而会映射为合法显式尺寸。U1.5 的 2K 16:9 / 9:16 使用官方建议的 `2720x1536` / `1536x2720`；Fast 使用其固定桶 `2752x1536` / `1536x2752`。显式宽高必须为 32 的倍数、512–4096、比例最大 3:1。格式支持 PNG/JPEG/WEBP；回退到 Fast 时，运行时会把下载结果转码为用户要求的格式。

选择 URL 返回时会立即下载：U1.5 生成/编辑 URL 有效 24 小时，U1 Fast URL 有效 1 小时。默认 Base64 路径不受 URL 时效影响。

可用 `--model`、`--fallback-model`、`--no-fallback` 控制模型。仅 404、429 或同模型重试后仍失败的 5xx 会自动回退。400/安全拦截、401/403、文件错误不会回退。

长提示词可保存为 UTF-8 文件并用 `--prompt-path prompt.txt` 传入；它与 `--prompt` 互斥。信息图、简历和包含大量中文标点的请求优先使用文件方式。

## 图片编辑

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-edit \
  --prompt "保持构图，修正标题并加强层级" \
  --images result.png https://example.com/reference.webp \
  --image-size auto \
  --save-path revised.png \
  --output-format json
```

本地图片、公开 URL 与 Data URL 都会经过统一校验，限制为 64 MiB / 4000 万解码像素，必要时规范化为 PNG/JPEG 后再以 Data URL 发送。支持多参考图和把上一轮输出继续编辑；编辑只用 U1.5，绝不回退 U1 Fast。

## 五个技能

- `sn-image-base`：生成、编辑，以及显式配置的文本/视觉兼容适配器。
- `sn-image-doctor`：离线诊断模型、端点、依赖、尺寸、水印和 Key。
- `sn-infographic`：87 布局、66 风格、用户限定的 1–15 轮、视觉评审和排序；后续按错误范围选择编辑或重新生成。
- `sn-image-imitate`：参考图解析、内容改写、原生编辑仿制、多轮一致性评审。
- `sn-image-resume`：正文优先或作品集两种视觉模式、事实防虚构，以及生成后文字/层级/布局纠错。

## JSON 字段

成功结果保留 `status`、`output`、`message`，并增加 `model`、`operation`、`retry_count`、`fallback_used`、`fallback_reason`。失败时包含 `error_type`、`error`，有 HTTP 响应时还包含 `http_status`。

## 常见问题

- 401/403：Key 或权限问题，不回退。
- 400/安全拦截：修正参数或内容，不回退。
- 429：文生图可回退；编辑不可回退。
- 5xx：U1.5 先做同模型重试；耗尽后文生图可回退。
- 图片编辑失败：确认模型不是 U1 Fast，图片路径存在，URL 可公开访问。
- 外部文本/视觉命令提示缺少模型：显式传 `--model` 或设置 `SN_TEXT_MODEL` / `SN_VISION_MODEL`；Skill 不会替你选择。
