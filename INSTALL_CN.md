# 安装图像与可视化技能

[English](INSTALL.md)

## 环境要求

- Git
- Python 3.9+
- 兼容 Agent Skills 的宿主，或直接使用 CLI
- 具备图像能力的 SenseNova API Key

## 克隆与安装

```bash
git clone --branch image-viz --single-branch https://github.com/Ryderey/SenseNova-Skills.git
cd SenseNova-Skills
python -m venv .venv
```

激活虚拟环境：

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

安装本分支唯一一套运行依赖：

```bash
python -m pip install -r skills/sn-image-base/requirements.txt
```

## 配置

复制 `.env.example` 为 `.env` 并填写 Key；`.env` 已被 Git 忽略。

```dotenv
SENSENOVA_API_KEY=your-key
```

默认配置使用这一个共享 Key 即可。仅当某项能力需要不同凭证时，才使用以下可选覆盖项：

- `SN_IMAGE_GEN_API_KEY`：图片生成与编辑。
- `SN_CHAT_API_KEY`：显式配置的文本与视觉适配器共用的后备 Key。
- `SN_TEXT_API_KEY`：仅用于文本适配器，优先于 `SN_CHAT_API_KEY`。
- `SN_VISION_API_KEY`：仅用于视觉适配器，优先于 `SN_CHAT_API_KEY`。

Key 读取顺序为 `--api-key` > 当前能力专用 Key > 适用时的 `SN_CHAT_API_KEY` > `SENSENOVA_API_KEY`。如果所有能力共用同一个商汤 Key，所有覆盖项都留空。

图像默认值已经内置：

```dotenv
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_IMAGE_GEN_MODEL=sensenova-u1.5-lite
SN_IMAGE_GEN_FALLBACK_MODEL=sensenova-u1-fast
```

除非明确需要外部文本/视觉适配器，否则不要设置 `SN_CHAT_MODEL`。通常应由当前 Agent 直接完成提示词规划与图片评审。

## 验证

```bash
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

随后可运行一次文生图命令，或直接让宿主 Agent 创建信息图。

## 安装到 Agent Skills 宿主

只需把 `skills/` 下 5 个目录复制或软链接到宿主的技能目录：

- `sn-image-base`
- `sn-image-doctor`
- `sn-infographic`
- `sn-image-imitate`
- `sn-image-resume`

重启或刷新宿主，使其重新发现 `SKILL.md`。本分支不需要 PPT、搜索、研究、数据分析或 Workbench 运行时。

## 可选外部适配器

如需兼容显式选择的文本/视觉服务，请配置 Key、Base URL、模型和协议；模型名没有代码默认值：

```dotenv
SN_TEXT_MODEL=your-text-model
SN_VISION_MODEL=your-vision-model
SN_CHAT_TYPE=openai-completions
```

## 排障

- 401/403：检查 Key 和账号权限；不会通过回退掩盖。
- 400 或安全错误：修正提示词/参数；不会回退。
- 文生图遇到 404、429 或重试后仍失败的 5xx：默认可转 U1 Fast，并记录原因。
- 图片编辑失败：U1 Fast 不支持图片输入，因此编辑绝不回退。
- 尺寸非法：宽高须为 32 的倍数、各在 512–4096 之间，比例不超过 3:1。

命令和输出字段见[图像指南](docs/sn-image-generate.md)。
