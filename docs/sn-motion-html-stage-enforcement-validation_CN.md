# sn-motion-html 阶段执行约束：实施与验证记录

日期：2026-09-22

执行依据：[sn-motion-html-stage-enforcement-plan-v2_CN.md](sn-motion-html-stage-enforcement-plan-v2_CN.md)

仓库修订基线：`3cf8ce8`（本次变更尚未提交）

**一句话结论：L1（阶段契约与停止规则）与 L2（最小阶段执行器）已在仓库内完成并通过离线程序验收；L1 行为在目标宿主 hy3 上的实测、以及 L3 宿主强制保障均未执行、未验证。本次不宣布"分阶段执行已可靠"。**

## 1. 采用的约束层级与理由

| 层级 | 状态 | 理由 |
|---|---|---|
| L1 阶段契约与停止规则 | 已完成（仓库内） | 方案 §4 规定本次必做 |
| L2 最小项目执行器 | 已完成并通过离线程序验收 | 已有一次越阶段失败事实，且方案 §7.1 允许"明确需要程序检查时的直接选项"；本机无法在 WorkBuddy 中复测 L1，故不等待 L1 复测结果 |
| L3 宿主强制限制 | 未实施，仅交付接入规格与缺口 | 本机不存在 WorkBuddy 客户端或其配置（见 §2），无法探测实际事件与工具分发接口。方案 §8 要求此时交付规格而非假装完成 |

L2 的保证范围必须如实说明：它是**正常入口处的程序检查**，不是不可绕过的审批。拥有任意 shell、可改写 `.motion-state/review.json`、或直接持凭证调用 runner 的 Agent 仍能绕过（方案 §4、§7.6、§8.3）。模型自行记录的决策记为 `agent-recorded`，不能证明真实用户事件存在。

## 2. P0：实际加载版本核验结果

**本机可确认的事实：**

- 仓库工作树与基线一致：`SKILL.md` 原始字节哈希 `15d07f4a…28b2`、`references/workflow.md` `52fcda8b…7f4e`，与方案 §2.2 记录的基线哈希逐位相符（小写形式）。
- 本机检查的技能发现位置均**不存在** `sn-motion-html`：`C:\Users\Ryder\.agents\skills\`（该目录存在且含多个技能，但无 `sn-*` 前缀项）、`C:\Users\Ryder\.codex\skills\`（仅 `.system`）、`C:\Users\Ryder\.codebuddy\`（不存在）、仓库根 `.codebuddy\`（不存在）。
- 本机开始菜单与用户目录下未发现 WorkBuddy/CodeBuddy 桌面安装痕迹。

**由此可以得出的结论：** 本机不存在被 hy3 读取的技能副本；宿主实际加载位置未知（可能在其它机器、容器或应用托管环境）。因此**本机无法验证宿主加载了哪一版**，也无法取证一次真实工具事件轨迹。

**明确未确认（不得当作已知）：**

- WorkBuddy 客户端版本、实际模型标识、任务所选工作目录。
- 宿主实际读取的 SKILL/workflow/prompting/runner 绝对路径。
- 宿主是否自动续跑、其系统/开发者指令是否要求"一直执行到最终交付"。
- 失败那次运行的完整工具调用与用户消息时间线。

**推断而非事实：** 模型自述引用"§4 评审包""§5 一致性闸门"，该结构与 `a7bb945` 的旧 workflow 相符、与 `3cf8ce8` 的 A/B 结构不符，因此"加载了旧副本或混合副本"是优先假设。这是排查方向，不是证明。

## 3. 修改清单与迁移说明

新增：

- `skills/sn-motion-html/references/review-story.md` —— 草稿与确认 A（原 workflow §1 迁移并收紧）
- `skills/sn-motion-html/references/review-visuals.md` —— 代表样图与确认 B（原 workflow §2）
- `skills/sn-motion-html/references/produce-and-deliver.md` —— 补齐静帧、组装、验收、交付、按需海报、视频（原 workflow §3、§4、§8.1、§9、§10）
- `skills/sn-motion-html/scripts/motion_stage.py` —— L2 阶段执行器
- `skills/sn-motion-html/tests/test_motion_stage.py` —— 门禁行为测试（第四轮后 51 项）
- 本记录

修改：

- `SKILL.md` —— 文首执行契约、`metadata.workflow_protocol: 2`、阶段路由与指针、受控入口说明、直接完成分支收紧
- `references/workflow.md` —— 改为精简路由：阶段路由表、暂停的可观察定义、接受范围、冒烟规则、生产记录、恢复与变更矩阵、成本纪律、程序检查边界
- `references/prompting.md` —— 新增"环境检查与冒烟测试"一节；生图指向受控入口
- `references/schemas.md` —— 新增 `.motion-state/review.json` 字段契约与摘要/失效规则
- `agents/openai.yaml` —— 入口描述体现"先文案等待、再样图等待"
- `scripts/init_project.py` —— `motion_stage.py` 进入 `ALWAYS_SCRIPTS`，新项目自动携带执行器
- `docs/sn-motion-html.md` / `docs/sn-motion-html_CN.md` —— 新增"分阶段执行的实际形态"（三轮形态、继续方式、冒烟区别、版本核验、程序检查边界）；视频指针由 workflow 第 10 节改为 produce-and-deliver 视频一节

**旧规则迁移对照（停止引用旧编号）：**

| 旧（`a7bb945` 结构） | 新（本次） |
|---|---|
| §4 Present the review package（文案与样图混在一个评审包） | 确认 A：逐幕文案（`review-story.md`）；确认 B：代表样图（`review-visuals.md`） |
| §5 Build the image set | `produce-and-deliver.md`「补齐静帧并展示总览」 |
| 首/中/尾固定三张样图 | 按实际风险 1～3 张，名单随 A 包提前展示；不做机械的开中末凑数 |
| workflow「第 10 节」= 视频 | 视频位于 `produce-and-deliver.md` 视频一节；不再存在"section 10" |
| 「无需机器状态」 | L2 引入 `.motion-state/review.json`（仅记机器阶段字段，正文仍只在 `content/story.json`） |

内部审计：`SKILL.md` 与全部 references 的 Markdown 链接由现有测试 `test_skill_markdown_links_resolve` 校验通过，无悬空"section 10"引用。

## 4. 交付文件哈希（部署核验用）

规范化换行、编码或打包会改变字节哈希，因此哈希不一致是"继续核对内容"的信号，不单独证明版本过旧。

```text
SKILL.md                           c0c209e3d3c1d1a840f2b815b8d72592dd365efaa5c2c88f064392813cb7432b
references/workflow.md             49bce713133e717d41154de53dc2d6ed5c4a7d94332efafe0486b9b5c1848da9
references/review-story.md         1596f4c615c0ee109d8eb6758fa46e1884549e15f8f424b82208f4e5c3cc64fb
references/review-visuals.md       bb32bac1fc27060745fd822ec75b15e77268a9aac4f019b895af526f36286137
references/produce-and-deliver.md  e939883b6f38cf1385ad2da5aaa40414f797ba95f0ddc6970d486d4a686c21bc
references/prompting.md            5c59764f40b22bb66a84b7e72f12e795fb4d95ea9be36264b1461ac3f6b6cf4d
references/schemas.md              5f9314581ce9de059006bacd5d4ceaa6f5c5765e264059c522a3587ab4c6f1b8
scripts/motion_stage.py            9d53db69cf7f5228e6ce014d57cf8f4437262cb07b957294b04a40dfe4625cd2
scripts/init_project.py            3e5fb3c2c89642f8b0053ffc823dbd81a9fa75b10fbdb9415742970d4f29f960
agents/openai.yaml                 82672c1c88b0008c068ebfcc1c0a79b372ce0d911361454c36b51f2ed74854ee
tests/test_motion_stage.py         f7ad96720782e1192837e798ca57c85696a6d16ec7dad3173c9bca8548d0dbf4
```

以上为提交前工作树的当前文件哈希；若之后再次修改技能文件，必须重算本表再部署核验。第四轮开工前实测 `motion_stage.py` 为 `c7897e6f…`，与本表当时记录的 `21b01701…` 不一致，说明该表在第三轮修复后未刷新；本轮已按当前工作树整体重算。

协议标记：`metadata.workflow_protocol: 2`，状态文件 `workflow_protocol: 2`、`schema_version: 3`。

## 5. L2 程序验收（第一批：离线 fake runner）

测试命令与结果：

```text
$ python -m unittest discover -s skills/sn-motion-html/tests -p "test_*.py"
Ran 127 tests in 90.0s
OK
```

第五轮后：74 项原有（未改动，回归通过）+ 53 项门禁测试（首轮 24 + 复审第二轮 11 + 第三轮 9 + 第四轮 7 + 第五轮 2，见 §12、§13、§14、§15）= 127 项。fake runner 现在复刻真实 runner「按输出格式重写文件后缀」的行为，否则只在新版下才会暴露的缺陷会被旧行为掩盖。这些测试只证明**本地程序挡住了调用**，不证明 hy3 会展示草稿或结束回合（方案 §10.1）。

用例与方案编号对应：

| 方案编号 | 测试 | 断言要点 | 结果 |
|---|---|---|---|
| G01/G06 | `test_samples_are_blocked_before_confirmation_A`、`test_smoke_generation_is_blocked_before_confirmation_A` | A 前任一生图请求 `status=blocked`、`provider_calls=0`、磁盘无文件 | 通过 |
| G04 | `test_only_the_recorded_sample_ids_are_generated` | 仅生成 A 包记录的 2 幕，其余 7 幕文件不存在 | 通过 |
| G07 | `test_submitting_all_chapters_at_the_sample_stage_is_refused_whole` | 9 张整批拒绝，真实调用 0，未先执行允许的子集 | 通过 |
| G08 | `test_an_unlisted_character_board_is_refused`、`test_renaming_every_target_sample_does_not_widen_the_scope` | 白名单外 ID（含角色板）与改名规避均整批拒绝 | 通过 |
| G09 | `test_editing_the_story_after_A_invalidates_the_shown_package`、`test_a_scoped_revision_decision_covers_the_changed_chapter` | 改稿后旧 A 不覆盖；显式作用域修订后放行 | 通过 |
| G10 | `test_a_replaced_sample_file_invalidates_confirmation_B` | 同路径图片被换 → `visual_review_stale`，调用 0 | 通过 |
| G15 | `test_resuming_skips_files_that_already_exist` | 已存在样图记为 `skipped_existing`，仅补缺失，1 次调用 | 通过 |
| G16 | `test_a_copy_only_revision_makes_no_image_call` | 交付后改文案 → 图片调用 0，阶段仍 `delivered` | 通过 |
| G17 | `test_an_explicitly_authorized_single_image_revision_touches_one_asset` | 授权第 6 幕时夹带第 3 幕 → 整批拒绝，第 3 幕字节不变 | 通过 |
| G19 | `test_two_processes_cannot_enter_at_once`、`test_a_live_holder_keeps_the_lock`、`test_a_lock_file_left_by_a_dead_process_does_not_block` | 持有者仍在跑时第二个进程 `project_locked`、调用 0（真实并发进程复现）；持有者崩溃后系统锁随进程释放，无需接管仪式即可继续 | 通过 |
| G20 | `test_a_result_without_a_file_is_recorded_as_unknown_and_not_resent`、`test_a_failed_provider_call_keeps_the_previous_asset` | 无产物的成功返回记 `unknown`，重发须显式 `--retry-unknown`；失败候选不覆盖已采用素材 | 通过 |
| G21 | `test_decisions_default_to_agent_recorded_trust`、`test_a_host_verified_decision_requires_an_event_reference`、`test_there_is_no_force_or_yes_flag` | 默认信任级 `agent-recorded`；`host-verified` 必须带 `--event-ref`；不存在 `--force-approved/--yes` 绕过参数 | 通过 |
| G22 | `test_a_copied_state_file_cannot_authorize_another_project` | 复制他项目 `.motion-state` → `state_project_mismatch`，调用 0 | 通过 |
| G24 | `test_a_state_written_by_another_protocol_is_refused` | 协议不符 → `protocol_mismatch`，拒绝当作新版测试 | 通过 |
| 计数 | `test_the_full_path_spends_exactly_nine_calls` | A→2 张样图→B→补 7 张，总 9 次，阶段 `delivered`，缺失 0 | 通过 |
| 边界 | `test_the_review_state_is_never_web_visible` | `.motion-state/review.json` 与 `review.lock` 不被预览服务暴露 | 通过 |
| 委托 | `test_a_delegation_covers_the_waits_but_not_the_artifacts` | 委托取消等待但不取消展示与自检；样图仍先做、仍展示 | 通过 |
| 预算 | `test_a_generation_limit_blocks_the_call_that_would_exceed_it` | 超出既定额度整批拒绝，调用 0 | 通过 |

实际轨迹摘录（fake runner，9 幕《小红帽》，样图 01/05）：

```text
$ motion_stage <proj> run-samples --runner <fake> --prompts-dir <p>
  exit=2 {"status":"blocked","reason":"phase_drafting","provider_calls":0}
$ motion_stage <proj> prepare-review --kind story --sample-ids 01-opening,05-wolf --generation-limit 9
  exit=0 {"story_package":"sr-b3b9e463-6afdfb88c2dd","phase":"drafting"}
$ motion_stage <proj> record-display --kind story
  exit=0 {"phase":"awaiting_story_review"}
$ motion_stage <proj> run-samples --runner <fake> --prompts-dir <p>          # A 之前
  exit=2 {"reason":"awaiting_story_review","allowed_action":"show_current_draft_and_end_turn","provider_calls":0}
$ motion_stage <proj> record-decision --scope story --message-ref user-1
  exit=0 {"phase":"sampling"}
$ motion_stage <proj> run-samples --target 01-opening=… --target 02-forest=…  # 夹带未授权幕
  exit=2 {"reason":"targets_outside_allowed_scope","provider_calls":0}
$ motion_stage <proj> run-samples --runner <fake> --prompts-dir <p>
  exit=0 {"provider_calls":2,"total_provider_calls":2}
$ motion_stage <proj> prepare-review --kind visual && record-display --kind visual
  exit=0 {"visual_package":"vr-b3b9e463-aa4e2a66dbad","phase":"awaiting_visual_review"}
$ motion_stage <proj> run-remaining --runner <fake> --prompts-dir <p>         # B 之前
  exit=2 {"reason":"phase_awaiting_visual_review","provider_calls":0}
$ motion_stage <proj> record-decision --scope visual --message-ref user-2
  exit=0 {"phase":"producing"}
$ motion_stage <proj> run-remaining --runner <fake> --prompts-dir <p>
  exit=0 {"provider_calls":7,"total_provider_calls":9,"phase":"delivered"}
$ motion_stage <proj> status
  exit=0 {"phase":"delivered","missing_stills":[],"total_provider_calls":9}
```

## 6. L1 行为验收：**未执行**（第二批待放行）

方案 §10.4 第二批要求在实际 hy3 宿主跑 G01、G02、G03、G04、G13、G14、G24。本机不存在 WorkBuddy，无法执行，因此**这些项当前状态为"未测"，不是"通过"**。模型自查、道歉或"我会遵守新版"均不计为证据。

复测协议（由使用者在授权后于 WorkBuddy 新会话执行）：

1. 按 §8.5 定位实际加载路径，比对第 4 节全部哈希（不只 `SKILL.md`），确认非混合副本；更新后开新会话并显式选择技能。
2. 固定同一模型配置与同一技能副本，逐条记录：会话标识、当前 `workflow_protocol`、事件顺序与来源、当前阶段、操作类型、目标 ID、**是否真的提交了图片请求**、回合结束位置。状态检查与生成调用分开计数。
3. 关键暂停场景各用至少 3 个独立新会话；任一协作测试出现未确认就进入后续生图，即不得宣布分阶段执行可靠。
4. 若普通请求仍连跑，先做 §8.6 的三次显式限定指令对照试验，据结果判断是阶段路由问题还是宿主指令/工具约束问题，不据单次结果归因模型品牌。

WorkBuddy 项目指令建议文本（只放一个权威位置，勿同时复制进项目指令、全局记忆和多个规则文件）：

```text
仅在调用 sn-motion-html 制作或修订故事页时适用。
普通制作请求默认分阶段：先展示逐幕正文，结束当前回复等待用户；
确认正文后只做已约定的代表样图，展示并结束当前回复等待用户；
确认样图后才补齐素材和网页。
在上述等待点交出阶段成果，算本轮任务完成，不算执行失败。
自动续跑、工具成功、Agent 自检和完成计划项不等于用户接受。
已确定内容及明确局部修改直接复用；用户明确不用等待时按委托范围继续。
```

## 7. 兼容性回归（方案 §10.3）

| 项目 | 验证方式 | 结果 |
|---|---|---|
| 纯 WebP 项目不被要求补造 PNG 母版 | 新增 `test_a_supplied_webp_set_is_never_asked_for_a_png_master`（全套可用 WebP：样图轮与补齐轮均 0 次调用、不生成任何 `.png`、仍走到 delivered）；`--force` 后 webp 实测保留 | 通过 |
| 压缩不默认把 4K 网页资产降到 2560 | 原有 `test_4k_master_and_web_delivery_have_independent_dimensions`、`test_stills_are_documented_at_4k` | 通过（未改动） |
| 正式分镜导出仍要求真实图片齐全 | 原有导出测试 + 执行器不改 `export_storyboard.py` | 通过 |
| 失败候选不先覆盖已采用素材 | 新增 `test_a_failed_provider_call_keeps_the_previous_asset`（写盘走 staging，成功才换入，旧件归档到 `tmp/replaced/`） | 通过 |
| 预览服务不公开 `.motion-state` | 新增 `test_the_review_state_is_never_web_visible` + 原有 `test_live_server_serves_only_the_page` | 通过 |
| `--force` 不覆盖用户内容、已采用素材与流程状态 | 实测：`--force` 后 `.motion-state/review.json` 与 webp 均保留 | 通过 |
| 旧项目仍能做明确局部修改 | 无状态文件时执行器不假定已接受；文档 §「恢复与按幕修改」保留原规则 | 通过（文档 + 无状态路径测试） |
| 纯图片任务不引入视频依赖 | `init_project` 图片模式仍不创建视频清单/凭证/目录；执行器只读 `content/story.json` 且拒绝 video 模式 | 通过 |
| 其它 `sn-image-base` 技能契约 | 未修改 `sn-image-base` 任何文件 | 不受影响 |

## 8. L3：宿主接入规格与未解决限制

**未解决（不得宣称已完成）：** 用户事件可信来源、等待期暂停自动续跑、替代入口（shell/HTTP/其它图片插件/子任务）覆盖、生图凭证隔离。本次未对 WorkBuddy 作任何配置改动，也未编写适配器——方案 §8.7 要求探测成立后才写适配器。

官方资料核查（2026-09-22，以目标客户端版本为准）：

- CodeBuddy **Code/CLI** 的 Hooks 文档列出 `PreToolUse`、`PostToolUse`、`UserPromptSubmit`、`Stop`、`SubagentStop`、`SessionStart/End`、`Pre/PostCompact`、`Notification`；注册位置 `.codebuddy/settings.json`；拒绝方式 `{"continue":false,"reason":"…"}` 或 `{"hookSpecificOutput":{"permissionDecision":"deny"}}`；`PreToolUse` 载荷含 `tool_name`、`tool_input`。
- **关键限制：`UserPromptSubmit` 载荷字段为 `session_id`、`transcript_path`、`cwd`、`permission_mode`、`generation_id`、`prompt`，没有任何字段区分"真实用户输入"与"自动续跑/系统注入"。** 因此即便接入 hook，也不能据此实现方案 §8.1 要求的可信自动批准——批准来源仍不可验证。
- WorkBuddy **应用**是否支持同一套 hook、以及是否覆盖其工具分发，上述文档未定义，本机也无法探测。不要把 CodeBuddy Code 的结论当作 WorkBuddy 已验证契约，更不要往技能 frontmatter 粘贴 hook 配置。

无成本探测清单（须在授权后的独立测试项目内、由能访问 WorkBuddy 的会话执行；不使用图片凭证、不调用真实生成）：

1. 从目标客户端的插件配置与诊断信息确认是否真的支持工具执行前拦截，记录注册位置、工具名、事件载荷与返回格式。
2. 注册仅写入简短测试事件的 Hook，确认一次无副作用工具调用确实触发它。
3. 对一个明确命名的本地测试操作返回拒绝，确认测试进程**完全没有执行**，而不只是 UI 显示警告。
4. 确认用户提交事件能否区分真实输入与自动续跑；不能区分则不用于可信自动批准（当前文档证据指向"不能区分"）。
5. 确认后台工具、子任务与并行请求是否经过同一拦截点，并记录实际范围。
6. 上述全部成立后才编写阶段适配器；Hook 失败、配置未加载或版本不支持时必须报错，不无声降级放行。
7. `Stop` Hook 语义须实测：目标是"允许模型在阶段末结束"，若误用为"阻止结束、要求继续工作"会加重本次问题。
8. 不以匹配命令串中的 `sn_agent_runner.py` 作为完整保障；强制限制仍须满足 §8.3 的调用与凭证边界。

若最终只能实现"拦截生图工具调用、但批准来源仍由模型自报"，则交付形态是 **L2 + 宿主工具拦截**，仍**不是**不可绕过的强制审批，必须在交付中这样标注。

## 9. 成本与可观测性

- 本次不承诺 token 节省。可观测项：文本输入/输出、图片生成/编辑**尝试**次数、用户回复次数、总耗时分别记录；读不到 usage 时标"不可得"，不以字数冒充 token。
- 执行器把"状态检查"与"真实生图调用"分开计数（`status`/`prepare-review`/`record-*` 恒为 `provider_calls: 0`；`total_provider_calls` 只统计实际尝试），第 5 节轨迹即按此口径记录。
- 取消了独立 1K 冒烟与额外人物板的默认地位：A 后第一张正式样图兼作链路验证并直接进入成品。
- 阶段参考按需读取降低上下文噪声，但这不是权限隔离；宿主若已注入全部内容，拆分不能隐藏后续流程，边界由停止规则与 L2 检查承担。

## 10. 逐条对照方案 §13 的交付状态

| §13 要求 | 状态 |
|---|---|
| 1. 宿主与加载版本核验结果，含未确认事项 | 已交付（第 2 节）；宿主侧仍未知 |
| 2. 修改文件清单、采用层级及 L2/L3 取舍理由 | 已交付（第 1、3 节） |
| 3. 旧规则到新规则的迁移说明 | 已交付（第 3 节对照表） |
| 4. 行为与程序验收记录 | 程序部分已交付（第 5 节，含轨迹）；行为部分**未执行**，已给出协议与放行点（第 6 节） |
| 5. 兼容性检查结果 | 已交付（第 7 节） |
| 6. 未完成的宿主限制与真实生图验收 | 已交付（第 8 节）；真实付费端到端样例未执行，方案 §10.4 第三批需另行授权 |
| 7. 不承诺不可绕过 | 已遵守：全文按"程序检查，非不可绕过审批"表述 |

## 11. 下一步需要用户放行的事项

1. 在 WorkBuddy 侧核对实际加载路径与第 4 节哈希（需要能访问该宿主的会话）。
2. 放行第 6 节第二批行为测试（G01–G05、G13、G14、G24，各 ≥3 个新会话）。
3. 若需要 L3：放行第 8 节的无成本 Hook 探测（不含真实生图、不使用凭证）。
4. 本次变更尚未提交，也未合并或推送；按方案 §14 要求等待指示。
5. 第四轮修复（§14）待复核；同时发现 §4 哈希表在第三轮后未刷新（实测与记录不符），本轮已按当前工作树重算。

## 12. 复审第二轮修复记录（2026-09-22）

首轮交付经复审发现 7 项缺陷，全部修复并各加回归测试。前三项会造成真实损失（误判失败、重复计费、并发生成），后四项是审批范围泄漏。

| # | 问题 | 根因 | 修复 | 回归测试 |
|---|---|---|---|---|
| 1 | 默认项目把成功生图误判为失败 | 生成目标直接取 `story.still`（模板默认 `.webp`），而 runner 在 `image_utils.py:186` 按输出格式重写文件名（`save_path.with_suffix(MIME_SUFFIX[mime])`），产物落在 `.png`；执行器找不到预期文件 → 记 unknown，图片滞留暂存目录 | 生成一律指向无损母版（声明为页面格式时目标改为同名 `.png`）；产物按暂存 token 前缀识别，兼容后缀重写；区分 `needs_generation` 与 `needs_page_copy`，缺网页图只提示跑 `make_posters.py`，不再消耗模型调用；`delivered` 需两者皆空 | `test_generation_targets_the_png_master_when_the_page_asset_is_webp`，并把 fake runner 改成复刻真实重写行为 |
| 2 | 中断恢复会重复提交、重复计费 | `committed` 记录在请求返回后才落盘，提交后被杀则磁盘上无痕，恢复时当作没发生 | 提交前先写 `committed` 记录并占用额度；恢复时把停留在 `committed` 的记录按 unknown 处理；重发必须 `--retry-unknown <op-id>` 显式核对；拒绝信息列出暂存区遗留文件，避免重复付费 | `test_a_call_killed_mid_flight_is_not_resent`（真实 kill 执行器进程） |
| 3 | 超 15 分钟夺取仍在使用的锁 | 仅按锁文件年龄判断失效，长批次中第二个进程可进入 | 改为持有者 PID 存活检查（Windows 用 `OpenProcess`/`GetExitCodeProcess`，显式避开 `os.kill(pid,0)` 在 Windows 会终止进程的问题）；存活持有者永不移锁；只有确认持有者已消失且超过 30 秒宽限才接管，并在 stderr 报告接管事件 | `test_a_live_holder_keeps_the_lock`、`test_a_lock_of_a_dead_holder_is_taken_over` |
| 4 | 局部确认连带接受其它未授权修改 | 修订决策刷新整个故事与样图摘要，未授权的第 9 幕新结局因此不再触发拦截 | 修订决策**不再改写任何包基线**；改为在比对时按章节查询授权，只有被点名的章节豁免 | `test_a_revision_does_not_bless_an_unauthorized_chapter` |
| 5 | 重排章节不使旧确认失效 | 摘要按章节 ID 建字典比较，忽略顺序；整体元数据与画风变更也不在比较范围内 | 包内分维度记录章节顺序、逐章摘要、画风基线、元数据摘要；顺序变化直接判 `<structure>`、画风变化判 `<style>`、元数据变化判 `<meta>`，三者都不允许用逐章修订放行 | `test_reordering_chapters_retires_confirmation_A`、`test_a_metadata_change_retires_confirmation_A` |
| 6 | 旧项目无法直接执行单图修改 | 无状态文件时修订决策后阶段仍是 drafting，指定目标被阶段检查拒绝 | 允许「无任何审阅包」的旧项目按当前用户指令建立最小作用域记录并进入 producing，但只接受显式列出的授权目标；无目标批量补齐仍然拒绝 | `test_an_old_project_can_take_one_authorized_image_revision` |
| 7 | 样图返修后回不到确认 B | 等待 B 时的返修被转入 producing 且停在那里，而视觉审阅包只允许在 sampling 准备 | 修订决策记录 `return_to`；B 尚未通过时返修结束回到 sampling、作废旧视觉包、保留有效 A，必须重新准备并再次询问 B | `test_a_sample_revision_before_B_returns_to_confirmation_B` |

同轮顺带修掉的四个隐患（复审未点名，但同一批代码及端到端复测中发现）：

- `record-display --kind visual` 用包内自身数据重算摘要再与包比较，恒成立，等于没有检查；改为与磁盘上的实际样图文件比较。
- `prepare-review --kind story` 在中途重备包时把展示记录标记为 `inherited` 继承过来，允许不重新展示就再次接受 A；改为一律要求重新展示。
- `<meta>` 判定原先依赖「聚合摘要不等且无其它差异」，被授权的章节改动会让聚合摘要失配却无人可归因；改为元数据独立比对。
- 样图身份原先取「先网页图、后母版」，于是 `make_posters.py` 生成网页图会被当成图片被替换、误退 B 并造成重新确认死循环；改为身份始终锚定无损母版（无母版的纯 WebP 项目仍以该文件为准），`--edit` 的输入同样优先无损母版。真实默认模板（`still` 为 `.webp`）端到端复测：9 张母版 + 9 张网页图、2+7=9 次调用、`verify_media.py` 与 `export_storyboard.py` 均通过。

机器契约变更：`schema_version` 由 1 升到 2（新增分维度基线、`return_to`、`token`、`page_copy_needed` 字段）。旧状态文件不会被当作新版继续用——协议字段不符即 `protocol_mismatch` 拒绝。文档同步：`schemas.md` 状态与母版/页面图小节、`workflow.md` 程序检查边界、`review-visuals.md` 返修回 B 路径、`produce-and-deliver.md` 母版与网页图关系、双语指南的程序检查段落。

## 13. 复审第三轮修复记录（2026-09-22）

又发现 6 项，其中第 4、5 项属方案符合性问题（审批范围被扩大解释、批准被当作一次性记录）。

| # | 问题 | 根因 | 修复 | 回归测试 |
|---|---|---|---|---|
| 1 | 新母版生成后网页仍用旧图 | `production_needs` 只判断 WebP 是否存在，替换母版后旧页面图被当作已完成 | 增加派生新鲜度判定（母版晚于页面图即视为待刷新）；`delivered` 要求无待生成**且**无待刷新；修订生命周期把页面刷新算作未完成的一部分；旧项目在全零调用情况下允许做一次零调用完成确认 | `test_a_replacement_master_marks_the_old_page_copy_stale` |
| 2 | 修订未完成即清除授权 | 完成判定只看文件是否存在，且一次运行后整体清除修订 | 修订记录逐章 `done`，只统计本次真正成功的产出；仍有章节未交付就保持 producing 并保留授权；调用失败同样保持开放可重试 | `test_one_revision_covers_every_chapter_it_authorized`、`test_a_failed_revision_target_stays_authorized_and_open` |
| 3 | 并发恢复可能删掉他进程活锁 | 检查旧锁后无条件 `unlink`，释放也无条件删路径 | 锁文件带本进程 token；接管前复验"仍是同一实例"（内容与 mtime）才移除；释放只删自己持有的锁，被顶替时保留他人锁并在 stderr 报告 | `test_a_release_never_deletes_another_processes_lock` |
| 4 | 一次修订授权成为该章长期豁免 | 覆盖判定只匹配评审包 ID 与章节 ID | 授权记录绑定**当时的章节摘要**：同章再次变化即为新改动，需新决策；被替换的样图文件还必须是"该次修订的那次运行"产出的同一指纹，事后手工覆盖仍被拒 | `test_an_authorized_change_does_not_exempt_later_changes_to_the_same_chapter` |
| 5 | 用户撤回批准后旧批准仍放行批量生成 | `changes-requested` 只回一条阻止信息，既不落盘也不撤销先前接受；`accepted()` 取任意一条 accept | 撤回作为正式决定持久化；同一作用域**最新记录**生效；撤回 A 连带作废据其构建的样图包与修订，撤回 B/委托回落到对应关卡 | `test_a_withdrawn_B_stops_production`、`test_a_withdrawn_A_voids_the_samples_built_from_it`、`test_a_revoked_delegation_returns_to_the_real_gates` |
| 6 | 合法替换样图后项目被锁死 | run-remaining 仍在比较旧 B 的整体摘要，且提示的重新准备与当前阶段互斥 | 去掉整体摘要比较，改为逐样图覆盖判定；连续多次授权替换互不影响，无需重新准备 B | `test_consecutive_authorized_sample_replacements_do_not_lock_the_project` |

同轮附带修正：`record-display --kind visual` 在等待 B 时的提示语原先指向"先生成样图"（该阶段并不适用），改为说明同一已展示样图集无需重复登记展示。

机器契约再变更：`schema_version` 升到 3（`approvals` 新增 `digests`/`revision_id`，`revision` 新增 `done`，`operations` 新增 `sha256`/`revision_id`，锁文件新增 `token`）。`workflow_protocol` 仍为 2（阶段语义未变）。

第三轮复测：`Ran 118 tests ... OK`（74 原有 + 44 门禁）。真实默认模板（`still` 为 `.webp`）端到端复跑：撤回 B 立即停止生产（`provider_calls: 0`）、重新确认 B 后连续替换两张样图各 1 次调用且不再被 `visual_review_stale` 锁死。

## 14. 复审第四轮修复记录（2026-09-22）

第四轮复审提出 6 项（3 项 P1、3 项 P2），全部修复；本轮新增 7 项回归测试，门禁测试增至 51 项。

| # | 严重度 | 问题 | 根因 | 修复 | 回归测试 |
|---|---|---|---|---|---|
| 1 | P1 | 撤销局部修订反而建立生成授权 | `record-decision` 先按 `scope=revision` 分派、后判决策类型，`--decision changes-requested` 被当成新修订处理 | 非 `accept` 的决策一律先走撤销；撤回记录带上被撤的 `revision_id`，`withdrawn_revision_ids` 使旧 accept 不再被 `matching_revision` 命中；撤回同时清空活动修订并回落到最早未满足关卡 | `test_a_withdrawn_revision_stops_generating` |
| 2 | P1 | 等待 B 时的局部修订不校验批准版本 | 内容摘要比对只在 B 已生效的分支里做，B 未生效时修订分支完全跳过 | 新增 `check_revision_digests`：B 未生效时，本次目标章节的当前摘要必须仍等于该修订决策记录时的摘要，否则拒绝并要求新决策 | `test_a_revision_while_waiting_for_B_binds_to_the_content_it_approved` |
| 3 | P1 | 旧委托覆盖用户后来的撤销 | `delegation_covers` 与有效批准直接取"或"，晚于委托的 `changes-requested` 不生效 | 委托有效性改看该阶段的最新语义：委托之后出现该作用域的 `changes-requested` 即失效；scoped 撤回同时清空 `delegation` 描述与 `interaction_mode` | `test_an_explicit_withdrawal_overrides_an_earlier_delegation` |
| 4 | P2 | 锁回收竞态：快照比较与删除非原子 | 接管者可在比较之后删掉他人新建的锁，两个执行者同时进入 | 弃用"接管旧锁"整套逻辑，改用操作系统排他锁（Windows `msvcrt.locking` LK_NBLCK / POSIX `fcntl.flock`）：进程退出即释放，无宽限期、无 token 比较、无 unlink；锁文件仅作持有者描述（pid/at）保留不删 | `test_two_processes_cannot_enter_at_once`、`test_the_lock_file_is_never_deleted_and_stays_acquirable`、`test_a_lock_file_left_by_a_dead_process_does_not_block` |
| 5 | P2 | 重试部分失败的修订批次重复生成成功项 | 计划直接采用 `--target` 全量，不排除本次修订已完成的章节 | `split_already_revised` 在规划阶段剔除"该修订已完成产出且磁盘指纹一致"的章节，记为 `skipped_existing`（0 调用），只把未完成项交给 runner | `test_retrying_a_partial_revision_batch_reuses_what_already_succeeded` |
| 6 | P2 | 同一样图第二次合法替换仍被阻断 | `produced_by_revision` 只查最新修订批准，第二次批准尚无产出记录时把第一次的合法产物判为失效 | 改为按文件来源判定：最新 completed 运行的指纹相符、且那次运行所属修订确实授权该章，即为合法来源；待执行的修订授权另行判定，手工覆盖仍被拒 | `test_a_second_authorized_replacement_of_one_sample_is_not_blocked`、`test_a_manual_overwrite_of_a_revised_sample_is_still_refused` |

机器契约：`schema_version` 仍为 3（撤回记录现在也携带 `revision_id`）；锁文件字段 `token` 随接管逻辑一并移除，仅保留 `pid`/`at` 描述。`workflow_protocol` 仍为 2。

文档同步：`references/schemas.md` 的项目锁段落与 `references/workflow.md` 的程序检查条目改写为系统锁语义（OS 释放、崩溃不留死锁、文件不删除）。

第四轮复测：`python -m unittest discover -s skills/sn-motion-html/tests -p "test_*.py"` → `Ran 125 tests ... OK`（74 原有 + 51 门禁），其中锁相关用真实两进程交错复现（一个进程在批次中、另一个启动）验证只允许一个进入且总调用数为 2。

## 15. 复审第五轮修复记录（2026-09-22）

第五轮复审提出 2 项 P2，全部修复；本轮新增 2 项回归测试，门禁测试增至 53 项。

| # | 问题 | 根因 | 修复 | 回归测试 |
|---|---|---|---|---|
| 1 | 中断恢复后，成功图片未计入修订完成状态 | `_advance_after_run` 只把本次运行返回的 `completed` 计入 `done`；图片已落盘、操作记录已持久化为 completed，但进程在批次收尾前被杀时 `done` 不更新。重试会正确复用该文件（跳过），可修订却永远欠着这一章，阶段停在 producing，`return_to=sampling` 时也无法重新准备 B | 完成状态改为从持久化记录恢复：`revision_produced_chapters` 逐章核对"最新 completed 运行属于本修订且文件哈希与其记录一致"，把命中的章节并入 `done`；与第四轮的 `split_already_revised`（规划阶段跳过）同源判定 | `test_a_run_cut_short_after_a_file_landed_still_counts_it`（真实 kill：第一章落盘、第二章调用中杀进程，重试 `--retry-unknown` 后 revision 关闭并回到 `delivered`；fake runner 新增 `FAKE_RUNNER_DELAY_MATCH` 支持按目标延时） |
| 2 | 局部修订的版本检查遗漏全局画风 | `check_revision_digests` 只比较章节摘要；等待 B 时修订决策是唯一授权，改 `style-preamble.txt` 即可夹带未确认的新画风 | 修订批准绑定当时全局维度（`chapter_order`/`style_basis`/`meta_digest`），`check_revision_content` 在 B 未生效的修订分支里四维校验（顺序/逐章摘要/画风/元数据），任一移动即拒绝并要求新决策；待执行授权与合法来源仍分开判定 | `test_a_revision_while_waiting_for_B_rejects_a_new_unapproved_style`（改画风 → `<style>` 拒绝、0 调用；在新画风上重新决策后放行 1 次调用） |

机器契约：`schema_version` 仍为 3；修订批准（`approvals`）新增 `chapter_order`/`style_basis`/`meta_digest` 三个绑定字段，旧状态文件里缺字段的授权按未绑定维度跳过（不追溯拦截）。

文档同步：`references/schemas.md` 修订绑定段落（含全局维度与中断恢复）、`references/workflow.md` 程序检查条目。

第五轮复测：`python -m unittest discover -s skills/sn-motion-html/tests -p "test_*.py"` → `Ran 127 tests ... OK`（74 原有 + 53 门禁）。
