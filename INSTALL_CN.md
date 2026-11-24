# 安装图像与可视化技能

[English](INSTALL.md)

## 环境要求

- Git
- Python 3.9+
- 兼容 Agent Skills 的宿主，或直接使用 CLI
- 具备图像能力的 SenseNova API Key

## 克隆与安装

```bash
git clone https://github.com/Ryderey/SenseNova-Skills.git
cd SenseNova-Skills
python -m venv .venv
```

如需固定某个发布版本（例如宿主可复现安装），可以改为克隆发布标签，如 `git clone --branch v1.0.0 --single-branch https://github.com/Ryderey/SenseNova-Skills.git`。标签发布后不会移动。

激活虚拟环境：

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

安装本分支唯一一套运行依赖：

后续命令假定已激活上述虚拟环境，`python` 指向其中的解释器。若未激活，请使用该解释器的绝对路径。

```bash
python -m pip install -r skills/sn-image-base/requirements.txt
```

宿主必须使用同一个 Python 解释器。若宿主不会继承终端里的虚拟环境，请把 `.venv\Scripts\python.exe`（Windows）或 `.venv/bin/python`（macOS/Linux）的绝对路径配置给宿主；Doctor 会显示它实际检查的解释器路径。

## 配置

复制 `.env.example` 为 `.env` 并填写 Key；`.env` 已被 Git 忽略。运行时先使用进程环境；否则读取 `SN_ENV_FILE` 指定的文件，再从当前任务目录向上查找最近的 `.env`。若宿主的工作目录不在项目中，请在宿主环境中把 `SN_ENV_FILE` 设置为 `.env` 的绝对路径。

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
SN_IMAGE_GEN_MODEL=sensenova-u1.6-lite
SN_IMAGE_GEN_FALLBACK_MODEL=
```

自动回退默认关闭。需要时显式设置 `SN_IMAGE_GEN_FALLBACK_MODEL`（或 `--fallback-model`）开启；`sensenova-u1.5-fast` 与 `sensenova-u1-fast` 已退役且不再受支持，请迁移到 `sensenova-u1.6-lite`。

除非明确需要外部文本/视觉适配器，否则不要设置 `SN_CHAT_MODEL`。通常应由当前 Agent 直接完成提示词规划与图片评审。

## 验证

```bash
python skills/sn-image-doctor/scripts/check_environment.py --verbose
```

输出中的 Python 路径应与宿主实际执行图片任务的解释器一致。本地配置检查离线执行，Doctor 默认还会检查仓库 Release，可用 `--no-update-check` 关闭；需要原生图片编辑时加 `--require-edit`。

随后可运行一次文生图命令，或直接让宿主 Agent 创建信息图。

## 安装到 Agent Skills 宿主

只需把 `skills/` 下 5 个目录复制或软链接到宿主的技能目录：

- `sn-image-base`
- `sn-image-doctor`
- `sn-infographic`
- `sn-image-imitate`
- `sn-image-resume`

重启或刷新宿主，使其重新发现 `SKILL.md`。本分支不需要 PPT、搜索、研究、数据分析或 Workbench 运行时。

如果宿主只能使用自己的 Python，请使用该解释器重新执行依赖安装命令，再用同一个解释器运行 Doctor。

## 更新已安装技能

五个图像/可视化技能共享同一版本。Runner 和 Doctor 会缓存检查仓库的最新正式 GitHub Release，每 24 小时最多检查一次；检查不访问 SenseNova 模型端点，不发送 Key、提示词、图片或机器标识。断网不会新增阻断，但此前已缓存的必需更新仍会阻断受影响操作。

强制检查：

```bash
python skills/sn-image-doctor/scripts/check_environment.py --check-update
```

也可以运行：

```bash
python skills/sn-image-base/scripts/sn_agent_runner.py sn-check-update
```

设置 `SN_SKILLS_NO_UPDATE_CHECK=1` 可关闭自动检查；显式的 `--check-update` 或 `sn-check-update` 仍会执行。

根据安装方式更新：

- **Git 克隆（默认分支）**：在克隆目录执行 `git pull --ff-only`。
- **Git 克隆（固定 tag）**：执行 `git fetch --tags`，再 `git checkout v<新版本>`。
- **软链接安装**：更新软链接指向的源仓库，然后刷新宿主。
- **复制安装**：下载新 Release，备份并替换 `sn-image-base`、`sn-image-doctor`、`sn-infographic`、`sn-image-imitate`、`sn-image-resume` 五个目录；保留 `.env` 和自定义配置，然后刷新宿主。

普通更新显示 `UPDATE INFO`，建议更新显示 `UPDATE RECOMMENDED`。如果更新被标记为必需、本地版本低于最低支持版本，或任一当前配置模型（包括回退、文本和视觉模型）已在发布清单中标记为下线，相关命令会以退出码 3 停止，并每次都显示原因。完成更新并刷新宿主后再继续。

## 可选外部适配器

如需兼容显式选择的文本/视觉服务，请配置 Key、Base URL、模型和协议；模型名没有代码默认值：

```dotenv
SN_TEXT_MODEL=your-text-model
SN_VISION_MODEL=your-vision-model
SN_CHAT_TYPE=openai-completions
```

## 维护者发布约束

默认模型、模型下线状态或接口兼容性发生变化时，必须同步更新五个技能目录中的 `VERSION`、各 `SKILL.md` 的 `metadata.version` 和根目录 `release.json`，再运行测试。`release.json` 的 `version` 必须为无 `v` 前缀的 `X.Y.Z`，`severity` 可选 `info`、`recommended`、`required`。发布时创建对应 `vX.Y.Z` tag，并发布为非草稿、非预发行的 GitHub Release；先运行 `python skills/sn-image-doctor/scripts/prepare_release_manifest.py --output sensenova-release.json` 校验并生成资产，再上传该文件。已安装技能只把最新的正式 Release 识别为可更新版本。

需要自动化上述流程时，在 `Actions` 页面从 `main` 手动运行 [Release workflow](.github/workflows/release.yml)，输入规范版本号和可选 Markdown 发布说明，并确认所选提交。首次使用前，请在 **Settings > Environments** 创建 `release` Environment 并配置必需审批人。校验作业只有只读权限；校验通过后，发布作业等待审批，再使用工作流 Token 的 `contents: write` 权限创建附注标签、发布最新正式 Release 并上传 `sensenova-release.json`。Gitee 标签与 Release 镜像仍手动同步。

## 排障

- 401/403：检查 Key 和账号权限；不会通过回退掩盖。
- 400 或安全错误：修正提示词/参数；不会回退。
- 文生图遇到 404、429 或重试后仍失败的 5xx：自动回退默认关闭；显式配置回退模型后才会切换，并记录原因。
- 图片编辑失败：编辑不自动切换模型；参考图最多 5 张，第 1 张为主编辑图。已退役的 `sensenova-u1.5-fast` 不再受支持，请改用 `sensenova-u1.6-lite`。
- 尺寸非法：宽高须为 32 的倍数、各在 512–4096 之间，比例不超过 3:1。

命令和输出字段见[图像指南](docs/sn-image-generate.md)。
