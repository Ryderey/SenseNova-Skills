# sn-motion-html 代码质量审查报告

- 审查日期：2026-09-17
- 审查范围：`6d67e74...b97a36e`，全部 49 个改动文件。
- 覆盖内容：脚本、前端、模板、技能指令、文档和集成测试。
- 审查边界：未修改功能代码，未调用生成接口；问题通过源码核对、临时项目或离线模拟确认。
- 结论：**修复🔴后可合并。**

本文记录该提交版本的审查结果，不表示问题已经修复。下列行号均对应 `b97a36e`。

## 验证结果

- 开启 `PYTHONUTF8=1` 后，53 项 motion 测试、26 项集成测试全部通过。
- 仓库范围检查通过。
- 13 个 Python 文件语法检查及两个 JavaScript 文件语法检查通过。
- 默认 Windows 环境首次执行 motion 测试时，有一项因中文错误输出的 UTF-8 解码失败而报错；开启 UTF-8 后通过。
- 本轮未重新执行真实生成接口或浏览器视觉验收。

## 🔴 必须修复（安全 / 数据风险 / 功能错误）

### R1. 视频清单可以越界读取、写入文件

位置：[agnes_video.py](../skills/sn-motion-html/scripts/agnes_video.py)，第 133、297 行。

`prompt`、`anchor_prompt`、`output` 直接拼接项目根目录，没有路径约束。实测 `../outside.txt` 被读取为提示词，`../outside.mp4` 也被接受；前者可能把敏感文件作为提示词发送给提供商，后者可越界写文件。

**修复建议：**调用接口前统一解析路径，拒绝绝对路径、目录逃逸及符号链接逃逸，并分别限制到提示词、视频输出目录。

### R2. 预览服务可通过符号链接泄露 .env

位置：[serve_project.py](../skills/sn-motion-html/scripts/serve_project.py)，第 79 行。

白名单只检查请求路径，解析链接后仅检查是否仍在项目内。实测 `assets/exposed.png → .env`，HTTP 请求返回 **200 和假密钥原文**。

**修复建议：**对解析后的真实相对路径再次执行白名单检查，或拒绝符号链接；补充 `.env`、私有状态文件的链接访问测试。

### R3. 图片压缩可能覆盖项目外文件或其他母版

位置：[make_posters.py](../skills/sn-motion-html/scripts/make_posters.py)，第 55 行。

`target.relative_to(...)` 没有先解析链接；母版保护也只比较当前源文件。实测输出 `.webp` 链接到项目外 PNG 时，外部 PNG 被覆盖成 WebP，脚本仍退出成功。

**修复建议：**校验解析后的目标路径，并禁止目标与任意输入母版指向同一文件。

### R4. --force 刷新会丢失用户的视频配置

位置：[init_project.py](../skills/sn-motion-html/scripts/init_project.py)，第 53、183 行。

已复现两种情况：`--force --media video` 覆盖自定义视频清单和模板同名提示词；仅传 `--force` 则默认切换为 images，删除视频清单、提示词及故事中的视频字段。这与“保留 story.json”的承诺不符。

**修复建议：**刷新默认沿用原模式，保留用户清单和提示词；模式转换必须明确指定，并保留可恢复的原配置。

### R5. 视频产物的成功判定不可靠，失败后无法正确恢复

位置：[agnes_video.py](../skills/sn-motion-html/scripts/agnes_video.py)，第 143、359 行。

FFmpeg 直接写最终路径；模拟归一化失败留下残片后，重跑仅凭文件存在就跳过并返回成功。跳过分支也不会补做缺失的 `--write-stills`。此外，实测将 1 秒输入归一化为 4 秒，输出仍只有 1 秒，函数正常返回。

**修复建议：**先写临时产物，校验编码、尺寸、帧率和时长后原子替换；短片明确补帧或报错；已有视频与静帧分别检查、分别恢复。

### R6. URL 锚定的场景无法供默认过渡片段使用

位置：[agnes_video.py](../skills/sn-motion-html/scripts/agnes_video.py)，第 433 行。

仅 `generate` 模式记录锚定图。实测两个场景采用合法 `url + first_frame` 后均生成成功，但默认 `reference` 过渡因找不到锚定记录而失败；已有旧记录时还可能引用过期图片。此处生成行为由离线模拟验证，未调用实际提供商。

**修复建议：**记录实际使用的首帧 URL，并在重新生成时更新或清除旧记录；执行前检查过渡所需的锚定条件。

## 🟡 建议改进（测试 / 可维护性 / 性能）

### Y1. 视频中间产物没有清理机制

位置：[agnes_video.py](../skills/sn-motion-html/scripts/agnes_video.py)，第 349、160 行。

所有任务共用 `sn-motion-video`，下载视频、锚定图没有成功或失败后的清理；抽帧失败也可能留下 `.frame.png`。

**改进建议：**使用任务独立临时目录和 `finally` 清理，只保留恢复任务必需的状态。

### Y2. 参数测试存在假通过，实际执行路径覆盖不足

位置：[test_motion_html.py](../skills/sn-motion-html/tests/test_motion_html.py)，第 749、788 行。

各子用例复用同一项目，第二次初始化失败却未检查返回值；首个“错误模型”污染后续清单。实测后续用例仍因错误模型失败，未验证各自参数。视频测试主要停留在 dry-run。

**改进建议：**每个子用例从独立有效清单开始，断言初始化结果及具体错误原因；补充离线模拟提交、归一化失败、重跑、静帧补写和锚定状态测试。

### Y3. 调用生成接口前的检查不完整

位置：[agnes_video.py](../skills/sn-motion-html/scripts/agnes_video.py)，第 344 行。

非法比例、零尺寸、负帧率能通过规划；FFmpeg 到生成完成后才检查，Pillow 到写静帧时才导入，可能先消耗生成资源再发现本地条件不满足。

**改进建议：**在首次接口调用前校验全部交付参数、工具依赖和输出条件，使 dry-run 能准确报告阻塞项。

### Y4. Python 校验与浏览器契约不一致

位置：[project_model.py](../skills/sn-motion-html/scripts/project_model.py)，第 77 行；[app.js](../skills/sn-motion-html/assets/template/src/app.js)，第 86 行。

Python 静默过滤非对象章节，且未校验 `tags` 类型；`chapters` 含 `null`、`tags` 为字符串时可能通过校验，页面却失败。缺少 `mediaMode` 时，Python 可推断 video，前端始终选 images。

**改进建议：**统一类型检查和模式推断规则，以同一组故事数据验证 CLI、网页及分镜导出。

### Y5. 视频启用后，技能指令和文档尚未同步

位置：[SKILL.md](../skills/sn-motion-html/SKILL.md)，第 92 行；[agnes-video.md](../skills/sn-motion-html/references/agnes-video.md)，第 3 行；[.env.example](../skills/sn-motion-html/assets/template/.env.example)，第 2 行。

技能仍无条件禁止加载视频，参考说明仍称流水线未实现，凭证模板仅列旧 Seedance 配置，与现有 Agnes 入口冲突。这会使宿主在已支持的视频请求上发生拒绝或降级。

**改进建议：**将禁止视频的规则限定于 images 模式，同步触发描述、Agnes 配置要求及默认双锚过渡方案。

### Y6. 冻结的 Seedance 路径仍保留重复提交风险

位置：[seedance_pipeline.py](../skills/sn-motion-html/scripts/seedance_pipeline.py)，第 198 行。

重试包住提交、轮询、下载和归一化全过程；下载或本地归一化失败也会重新创建生成任务。该问题虽已在方案中声明，扩展 Seedance 时仍不能直接复用此恢复逻辑。

**改进建议：**分离提交与后续恢复，持久化任务 ID，按失败阶段重试。

## 🟢 可选优化

### G1. 提取提供商无关的交付处理

位置：[agnes_video.py](../skills/sn-motion-html/scripts/agnes_video.py)，第 143 行；[seedance_pipeline.py](../skills/sn-motion-html/scripts/seedance_pipeline.py)，第 103 行。

两套归一化实现已经出现补帧行为分歧。可共用目标参数校验、归一化和媒体验收小函数；Agnes、Seedance、未来 MiniMax M3 的请求逻辑保持独立，无需提前建立复杂注册框架。

### G2. 固定测试子进程编码

位置：[test_motion_html.py](../skills/sn-motion-html/tests/test_motion_html.py)，第 73 行。

默认 Windows 环境实测有一项因中文输出解码失败；开启 UTF-8 后通过。建议测试统一设置子进程 UTF-8，避免依赖机器区域配置。

## 总体评价与合并结论

图片默认路径、分镜导出和轻量前端的职责较清楚，但视频执行路径及文件边界仍有可复现的安全、数据丢失和恢复缺陷。当前测试通过不足以证明这些关键路径可靠。

**结论：修复🔴后可合并。**
