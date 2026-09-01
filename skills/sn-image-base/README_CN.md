# sn-image-base

面向 `sensenova-u1.5-lite` 文生图与原生图片编辑的底层运行时。默认无水印、从 `b64_json` 立即落盘；文生图仅在规定的可恢复故障下回退到 `sensenova-u1-fast`。

在本技能目录中执行 `python -m pip install -r requirements.txt`，设置 `SENSENOVA_API_KEY`，然后阅读 [SKILL.md](SKILL.md) 与 [references/api_spec.md](references/api_spec.md)。Agent 从其他目录调用时，应先解析技能目录并使用绝对路径。

文本/视觉模型没有默认值；只有显式配置时才使用外部适配器。
