# SenseNova 图像与可视化技能

[English](README.md) | 简体中文

![SenseNova 图像与可视化案例](docs/images/teasers/teaser_v2.webp)

本分支只维护 5 个完整的“图像与可视化”技能，适用于任何兼容 Agent Skills 的智能体。生图与图片编辑默认使用 `sensenova-u1.5-lite`；模型调用按账号当前套餐及积分规则计费。

## 保留的技能

| Skill | 能力 |
|---|---|
| [`sn-image-base`](skills/sn-image-base/SKILL.md) | U1.5 文生图、原生多参考图编辑、显式可选的文本/视觉适配器，以及受控的 U1 Fast 回退 |
| [`sn-image-doctor`](skills/sn-image-doctor/SKILL.md) | 离线检查安装、依赖、Key、端点、模型、尺寸及无水印默认值 |
| [`sn-infographic`](skills/sn-infographic/SKILL.md) | 87 种布局、66 种风格、提示词扩写、1–8 轮生成、视觉评审、编辑式修正和质量排序 |
| [`sn-image-imitate`](skills/sn-image-imitate/SKILL.md) | 参考图解析、内容改写、U1.5 原生仿制、一致性评审与多轮排序 |
| [`sn-image-resume`](skills/sn-image-resume/SKILL.md) | 事实不虚构、固定视觉规则、生成后编辑纠错的可视化简历 |

完整的信息图中英文案例库仍保留：[中文](docs/sn-infographic-examples_CN.md) / [English](docs/sn-infographic-examples.md)。

## 默认策略

- 首选模型：`sensenova-u1.5-lite`
- 文生图次选：`sensenova-u1-fast`
- 默认无水印
- 默认启用 U1.5 提示词扩展
- U1.5 默认返回 Base64 并立即落盘
- 不设置默认文本/视觉聊天模型；优先由当前 Agent 完成规划和评审

只有文生图遇到 404、429 或同模型重试后仍失败的 5xx 才自动回退。图片编辑、401/403、参数/安全错误和本地文件错误均不回退。

本仓库有意显式发送 `watermark=false`。SenseNova 当前在公测期免费开放无水印，官方说明公测结束后将作为高级付费特性；届时用于生产前应先确认账号费用。

请打开 [SenseNova API 官方文档](https://platform.sensenova.cn/docs)，按标题查找 `SenseNova U1.5 Lite` 或 `SenseNova U1 Fast`。文档站的深链接在首次加载时不能可靠定位。

## 快速开始

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r skills/sn-image-base/requirements.txt
```

复制 `.env.example` 为本地 `.env`，默认配置只需填写：

```dotenv
SENSENOVA_API_KEY=your-key
```

通常只需这一个共享 Key。仅当某项能力使用不同凭证时，才设置可选的 `SN_IMAGE_GEN_API_KEY`、`SN_CHAT_API_KEY`、`SN_TEXT_API_KEY` 或 `SN_VISION_API_KEY`；读取优先级为命令行参数 > 能力专用 Key > 共享 Key。详见[安装说明](INSTALL_CN.md#配置)。

检查环境：

```bash
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

文生图：

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-generate \
  --prompt "一张清晰的双语可再生能源信息图" \
  --image-size 2k \
  --aspect-ratio 16:9 \
  --save-path output.png \
  --output-format json
```

编辑或连续修改：

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-edit \
  --prompt "保持版式，修正标题文字" \
  --images output.png \
  --save-path corrected.png \
  --output-format json
```

Agent Skills 安装方法见 [INSTALL_CN.md](INSTALL_CN.md)，CLI 与 API 细节见[图像指南](docs/sn-image-generate.md)。

## 安全

禁止提交 API Key。请使用被 Git 忽略的 `.env`、Agent 的密钥存储或临时非回显环境注入。JSON 与 Doctor 输出会脱敏，不会主动打印授权请求头。

## 许可证

见 [LICENSE](LICENSE)。
