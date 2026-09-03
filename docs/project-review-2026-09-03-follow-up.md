# 当前项目跟进审查与优化清单

审查日期：2026-09-03
初审基线：完整工作树，`e193511`（`main`）
审查方式：只读代码与契约审查、离线测试、静态检查、仓库一致性检查
初审边界：初审阶段仅新增本报告，未调用生产图像 API
复查状态：2026-09-03 已完成 R01-R12 的修复或针对性优化、离线回归及一次生产图像 API 验证
已发布整改提交：`55539a4`、`43c2d9a`（`main`）

## 结论

初审时，项目主路径已经具备较好的离线回归基础：41 项测试、Ruff、仓库范围检查和 Doctor 均通过，87 个布局与 66 个风格资源完整。初审发现的主要风险不是普遍性的代码质量问题，而是“测试全绿但契约仍可能失效”的边界问题。

建议优先处理四项：

1. 修复空环境变量阻断共享 API Key 回退；
2. 修复安装文档指向不存在的 `image-viz` 分支；
3. 限制远程图片 URL 访问内网、回环及云元数据地址；
4. 消除简历事实字段“必须逐字保留”与“允许翻译全部信息”的冲突。

## 复查与修复结果

| 编号 | 状态 | 落地结果 |
|---|---|---|
| R01 | 已修复 | 空白能力级环境变量不再阻断共享 Key 回退，并增加优先级回归测试 |
| R02 | 已修复 | 中英文安装文档改为克隆默认分支，范围检查与契约测试同步更新 |
| R03 | 已修复 | 远程图片连接绑定到已验证的公网 IP，并保留原始 Host/SNI；首次请求及每次重定向均重新校验和绑定 |
| R04 | 已修复 | 简历提示词明确仅叙述性文本与结构标题可翻译，事实台账值默认逐字保留 |
| R05 | 已修复 | 编辑入口在发起请求前拒绝非 SenseNova 生成后端 |
| R06 | 已修复 | `image-size=auto` 与显式 `--aspect-ratio` 组合改为本地清晰报错 |
| R07 | 已修复 | 共享配置模块统一校验 Base URL 与接口协议；URL 限定 HTTP(S) 并拒绝 userinfo/query/fragment，错误不回显凭证 |
| R08 | 已修复 | Ruff 默认关闭自动修复，CI 显式使用 `--no-fix` |
| R09 | 已修复 | Doctor 对已选择的文本/视觉适配器校验 Key、URL 与接口协议；未选择时仍保持可选 |
| R10 | 已修复 | Base64 在解码前按编码长度拒绝超限输入，解码后仍保留二次大小检查，三个生成后端共用实现 |
| R11 | 已修复 | 信息图要求审查每个候选图（包含第 1 轮）；只有继续修正受轮次预算控制 |
| R12 | 已优化 | 新增高价值跨文件不变量和运行时边界测试，避免对提示词全文做脆弱快照 |

最终离线验证：51 项单元测试通过；Ruff `--no-fix` 通过；Repository scope 通过；Doctor 通过。

漂移复查：D1 已补齐回退参数透传，并在 Fast 返回格式不一致时执行本地转码；D2 已把 4 个受支持配置项加入 `.env.example`；D3 已统一 README 的 Key 优先级；D4 已删除零引用的 `extract_json.py`；D5 已在历史台账顶部添加归档指针。回退契约和配置清单均有离线回归测试。

安全复查：远程图片下载现将实际连接绑定到已验证的公网 IP，同时保留原始 Host 与 TLS SNI；首次请求及每次重定向均重新解析、校验并绑定，且禁用环境代理，关闭 DNS 重绑定窗口。真实公网 HTTPS 冒烟检查成功下载并验证了一张 8,090 字节的 PNG，未调用模型 API。

生产验证：使用默认 `sensenova-u1.5-lite` 发起一次 1K、1:1、无水印、禁用回退的真实生成请求。请求在 22.64 秒内成功，重试 0 次、回退 0 次；返回文件为有效 PNG，尺寸 1344×1344，大小 1,695,883 字节，SHA-256 为 `fa67476b775891418264b2ec0b80b02682cccd835cdeb6f985ce388bc82b3ad4`。输出位于系统临时目录，未写入仓库。

## 初审验证基线

| 检查 | 结果 |
|---|---|
| `python -m unittest discover` | 41 项通过 |
| Ruff | 通过；但初审时配置启用了自动修复，见 R08 |
| Repository scope | 通过 |
| Offline Doctor | 通过，未消耗模型额度 |
| 远程分支核对 | 初审时 `origin` 仅暴露 `main`，不存在 `image-viz` |
| 工作树状态 | 审查开始时干净 |

## 优化清单

### R01 — High：`.env.example` 的空覆盖项会阻断共享 Key 回退

- 证据：`.env.example:12-24` 将 `SN_IMAGE_GEN_API_KEY`、`SN_CHAT_API_KEY`、`SN_TEXT_API_KEY`、`SN_VISION_API_KEY` 等可选覆盖项保留为空；`INSTALL.md:38-51` 与 `INSTALL_CN.md:38-51` 明确要求复制该文件并将覆盖项留空。
- 根因：`skills/sn-image-base/scripts/sn_image_base/configs.py:54-63` 返回第一个“存在于环境中”的变量，即使值为空字符串，也不再尝试后续的 `SENSENOVA_API_KEY`。
- 复现：设置 `SENSENOVA_API_KEY=shared-test-key` 并将四个专用 Key 设为空，解析结果为 `'' '' '' ''`。
- 影响：完全按快速安装文档操作的新用户可能得到“缺少 API Key”，文档宣称的最小配置不可用。
- 最小整改：让 `Field.resolve()` 跳过空白值，再继续读取下一优先级变量；新增一项使用“复制后的 `.env.example` 状态”的回归测试。
- 验收：仅填写 `SENSENOVA_API_KEY` 时，图片、共享聊天、文本和视觉 Key 均正确回退；显式非空专用 Key 仍优先。

### R02 — High：安装命令指向不存在的远程分支

- 初审证据：`INSTALL.md:15`、`INSTALL_CN.md:15` 使用 `git clone --branch image-viz --single-branch ...`；当时 `origin` 仅有 `main@e193511`。
- 初审放大因素：`skills/sn-image-base/tests/test_skill_integrity.py:174-183` 和 `skills/sn-image-doctor/scripts/check_repository_scope.py:35-37,95-103` 将过期命令固化为通过条件；当时的历史台账 `docs/project-review-2026-09-03.md:4` 也仍记录 `image-viz`。
- 影响：全新安装在克隆阶段立即失败，而 CI 仍显示绿色。
- 最小整改：安装命令改为克隆默认分支，避免再次硬编码短期分支名；同步调整两个离线检查。历史台账可保留，但应标明对应提交或归档状态。
- 验收：在空目录执行文档中的克隆命令可成功取得当前五个技能；测试不再要求不存在的分支名称。

### R03 — High：所谓“公开 URL”可访问本机与内网目标

- 证据：`skills/sn-image-base/SKILL.md:78` 将远程输入描述为公开 HTTP(S) URL；`skills/sn-image-base/scripts/sn_image_base/image_utils.py:41-50` 对任意 HTTP(S) 地址发起请求并自动跟随重定向，没有拒绝回环、私网、链路本地或云元数据地址。
- 影响：来自不可信内容的图片链接可让 Agent 主机向内部服务发起 GET 请求，形成 SSRF/本地网络探测面；重定向可绕过只检查首个 URL 的实现。
- 最小整改：在首次请求及每次重定向前解析目标地址，默认拒绝非公网 IPv4/IPv6、localhost 和带用户信息的 URL；实际连接必须绑定到已经验证的 IP，并保留原始 Host 与 TLS SNI，避免二次解析产生 DNS 重绑定窗口。
- 验收：离线测试覆盖 IPv4、IPv6、DNS 解析、连接目标绑定、原始 Host/SNI、重定向转入私网和合法公网 URL。

### R04 — High：简历事实保护规则仍存在内部冲突

- 证据：`skills/sn-image-resume/SKILL.md:38-40` 要求姓名、日期、数字、职位、机构和联系方式逐字保留；`skills/sn-image-resume/prompts/resume.md:52` 却允许翻译“all user information”，`resume.md:67` 仅在“when appropriate”时保留关键专名。
- 影响：职位、机构、项目标题或其他事实台账字段可能被翻译或改写；这与历史台账中 R05“Complete”的结论冲突。
- 最小整改：明确只有叙述性说明和结构标题可以翻译；事实台账保护字段在任何输出语言下均逐字保留，除非用户逐项明确授权翻译。
- 验收：加入跨文件契约测试，确保保护字段列表在 `SKILL.md` 与 `resume.md` 中一致，并用中英混合简历样例验证。

### R05 — Medium：编辑命令未防止替代生成后端污染 U1.5 编辑路径

- 证据：`skills/sn-image-base/SKILL.md:26` 允许显式选择 `nano-banana` 或 `openai-image` 生成后端；但 `skills/sn-image-base/scripts/sn_agent_runner.py:475-489` 的编辑命令无论当前 `SN_IMAGE_GEN_MODEL_TYPE` 为何，都直接使用同一套 base URL/model 构造 `SensenovaText2ImageClient`。
- 影响：用户为生成配置替代后端后再执行编辑，可能把 U1.5 编辑负载发送到不兼容端点，得到难以理解的失败，甚至产生无效请求成本。
- 最小整改：编辑入口显式要求 `SN_IMAGE_GEN_MODEL_TYPE=sensenova`，不满足时在网络请求前清晰失败。若未来确需多后端编辑，再引入独立编辑后端配置，不要复用生成后端状态。
- 验收：为三种生成后端各加一项离线编辑分派测试；只有 SenseNova 路径能够构造编辑客户端。

### R06 — Medium：默认编辑尺寸会静默忽略显式 `--aspect-ratio`

- 证据：`skills/sn-image-base/references/api_spec.md:23` 将 `--aspect-ratio` 列为编辑参数；Runner 在 `sn_agent_runner.py:497-498` 传递该值，但 `generation/sensenova.py:321-325` 在默认 `image_size=auto` 时立即返回，完全不读取比例。
- 影响：用户看到参数被接受，却无法获得要求的画幅；这违反“已支持参数必须生效”的契约。
- 最小整改：当 `image_size=auto` 且显式传入比例时，在本地报错并提示同时选择 `1K/2K/4K`；若 API 明确支持 auto+ratio，再实现实际映射。
- 验收：禁止静默成功；测试覆盖 auto+ratio、2K+ratio 和无 ratio 的默认路径。

### R07 — Medium：URL 与协议配置验证过宽，并可能输出 URL 中的凭证

- 证据：`configs.py:303-307` 只检查 scheme 与 netloc，因此 `ftp://`、`file://`、`mailto://` 均被判定为有效；环境变量中的非法适配器协议也不会按 `Literal` 运行时校验，`sn_agent_runner.py:693-718` 会把任何非 Anthropic 值当作 OpenAI 协议。可选适配器还会在 JSON/stderr 中返回原始 base URL（`sn_agent_runner.py:546-551,703-719`）。
- 影响：Doctor 可批准运行时无法使用的 URL；错误协议被静默路由；形如 `https://user:secret@host` 的 userinfo 可能出现在日志或 JSON。
- 最小整改：统一配置验证：仅允许 HTTP(S)、必须有 hostname、拒绝 userinfo/fragment；显式枚举并拒绝未知协议；所有对外输出使用脱敏 URL。
- 验收：覆盖非法 scheme、userinfo、未知协议、合法 localhost API 地址和合法公网 HTTPS 地址。

### R08 — Medium：Ruff 在 CI 中可能自动修改后通过，而不是严格阻断

- 证据：`skills/sn-image-base/scripts/ruff.toml:4` 设置 `fix = true`；`.github/workflows/test.yml:27-28` 直接运行 `ruff check`，没有禁用修复或检查工作树是否被改动。
- 影响：可自动修复的违规可能在 CI 临时工作区被修改后返回成功，提交本身仍不符合规范。
- 最小整改：将默认配置改为 `fix = false`，本地修复显式使用 `ruff check --fix`；CI 使用 `--no-fix`，必要时追加 `git diff --exit-code`。
- 验收：提交一个可自动修复的临时违规时，CI 必须失败且不修改文件。

### R09 — Medium：Doctor 对已启用的可选文本/视觉适配器只检查 model 名称

- 证据：`skills/sn-image-doctor/SKILL.md:3,29-31` 宣称诊断可选适配器；`check_environment.py:167-185` 只把 model 是否非空当作 configured，随后无条件返回成功。
- 影响：缺 Key、错误 base URL 或未知协议时，Doctor 仍可能报告环境 ready，直到真正调用才失败。
- 最小整改：仅对已启用的适配器离线验证 model/key/base URL/protocol 组合；未启用时继续保持可选且不失败。
- 验收：分别覆盖未启用、完整配置、缺 Key、非法 URL 和非法协议。

### R10 — Medium：Base64 大小限制发生在完整解码之后

- 证据：`image_utils.py:33-40` 先执行完整 `b64decode`，再调用 64 MiB 边界；`generation/sensenova.py:401-405` 对模型响应也先完整解码。限制能拒绝最终数据，但不能阻止解码阶段的峰值内存占用。
- 影响：超大 Data URL 或异常模型响应可在被拒绝前占用大量内存。
- 最小整改：根据 Base64 长度预估解码大小并在解码前拒绝超限内容；统一使用严格校验；保留解码后的二次检查。
- 验收：构造超过边界的编码字符串时，不执行大块解码；边界内 PNG/JPEG/WebP 仍正常工作。

### R11 — Medium：信息图默认单轮路径没有执行其宣传的视觉质量门

- 证据：`README.md:15` 宣传 visual review；`skills/sn-infographic/SKILL.md:25` 默认 `max_rounds=1`，而 `SKILL.md:65` 仅在 `max_rounds > 1` 时要求检查图片。
- 影响：最常见的默认调用无法可靠给出 `quality_passed`，文字乱码、事实错误或布局红线可能未经检查直接返回。
- 最小整改：所有轮次都审查首张候选图；只有“继续生成修正版”才受 `max_rounds > 1` 控制。
- 验收：单轮执行也产生完整评分、红线结果和 `quality_passed`；若失败但无剩余轮次，返回最佳图并明确标记未通过。

### R12 — Low：契约测试偏向字符串存在，无法发现跨文档矛盾

- 证据：`test_skill_integrity.py:80-114` 的多项提示契约测试主要断言关键词存在；它没有发现 R04，也没有验证示例 JSON/schema。历史台账 `docs/project-review-2026-09-03.md:28,43` 对“targeted contract tests”的表述强于实际覆盖。
- 影响：关键规则可在 CI 全绿的情况下相互冲突或退化。
- 最小整改：增加少量高价值跨文件不变量测试：事实保护字段、评审阈值、结果 schema、默认单轮质量门和配置优先级。避免为提示词全文做脆弱快照。
- 验收：人为恢复任一已知矛盾时，对应测试能准确失败。

## 建议执行顺序

1. **立即修复：** R01、R02、R03、R04。
2. **补齐运行时契约：** R05、R06、R07、R08、R09。
3. **加强边界与回归：** R10、R11、R12。

## 暂不建议的改动

- 不建议仅因 `sn_agent_runner.py` 较长就立即拆分；先解决上述可复现契约问题，出现第二个实际编辑后端时再抽象分派层。
- 不建议现在引入新的测试框架、类型检查器或依赖管理工具；现有 `unittest` 与 Ruff 足以承载本清单中的最小回归测试。
- 不建议为了缩小仓库立即迁移 96 张案例图；当前图片总量约 30.4 MiB，且画廊是项目的明确交付物。只有克隆时间或托管配额出现实际压力时再评估 LFS 或外部制品存储。

## 完成标准

每一项整改应同时满足：实现与文档一致、存在针对根因的离线回归测试、41 项基线测试继续通过、Ruff 以非修复模式通过、Repository scope 与 Doctor 通过，并在新的整改台账中记录对应提交和证据。首轮整改提交为 `55539a4`；安全复查和漂移修复后的最终套件包含 51 项测试。
