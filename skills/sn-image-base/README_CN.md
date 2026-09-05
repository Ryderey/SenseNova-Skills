# sn-image-base

以下 `python` 命令假定已按[安装说明](../../INSTALL_CN.md)创建并激活虚拟环境。若未激活，请使用该环境解释器的绝对路径；依赖安装、Doctor 和 Agent 宿主须使用同一解释器。

面向 `sensenova-u1.5-lite` 文生图与原生图片编辑的底层运行时。默认无水印、从 `b64_json` 立即落盘；文生图仅在规定的可恢复故障下回退到 `sensenova-u1-fast`。

在本技能目录中执行 `python -m pip install -r requirements.txt`，设置 `SENSENOVA_API_KEY`，然后阅读 [SKILL.md](SKILL.md) 与 [references/api_spec.md](references/api_spec.md)。Agent 从其他目录调用时，应解析技能目录，并使用通过 Doctor 的同一个 Python 解释器与绝对脚本路径。复杂中文提示词优先通过 UTF-8 `--prompt-path` 传入。

运行时先使用进程环境，再读取 `SN_ENV_FILE` 指定的文件，最后从当前工作目录向上查找 `.env`。

文本/视觉模型没有默认值；只有显式配置时才使用外部适配器。
