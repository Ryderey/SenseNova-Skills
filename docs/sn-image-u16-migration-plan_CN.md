# sn-image 系列 U1.5 → U1.6 Lite 更新方案

日期：2026-11-24　状态：方案待确认，未动代码
依据：① 官方公告（2026-11-24）：`sensenova-u1.5-lite`、`sensenova-u1.5-fast` 计划下线，过渡期平台自动路由到 `sensenova-u1.6-lite`，下线后兼容路由失效；② platform.sensenova.cn/docs「SenseNova U1.6 Lite」章节（浏览器快照取证）。

## 1. 官方事实与差异分析

模型总览中图像类模型仅 `sensenova-u1.6-lite` 一个；`u1.5-*` 与代码现用的 `sensenova-u1-fast` 均不在列。端点（`/v1/images/generations`、`/v1/images/edits`）与 Bearer 鉴权不变。

| 项 | 现状代码（U1.5） | U1.6 文档 | 影响 |
|---|---|---|---|
| 默认模型 | `sensenova-u1.5-lite` | `sensenova-u1.6-lite` | 改常量与 env 默认 |
| 回退模型 | `sensenova-u1-fast` | 不在模型总览 | 回退默认值需决策（见决策 1） |
| size | 客户端默认 2K；edit 默认 auto；支持 1K/2K/4K/显式 WxH | 服务端默认 auto；2K/4K 常量 + 显式 WxH（32 倍数、512–4096、≤3:1）；**未列 1K** | 客户端 2K 默认保留；1K 走显式映射（决策 3） |
| 2K 16:9 / 9:16 | 2720x1536 / 1536x2720 | 建议分辨率一致 | 桶值不变，仅命名去 U15 |
| watermark | 客户端显式传（默认 false） | 服务端默认 **true**；建议显式传；无水印当前免费公测、后续付费 | 保持显式传，文档加付费风险注 |
| self_correction | 无此字段 | **新增** boolean，默认 true（文字自修正） | 决策 2 |
| prompt_extend / output_format / response_format / n=1 | 同 | 同 | 不变 |
| edit 参考图 | 代码未限张数 | **至多 5 张**，第 1 张为主编辑图 | 边界校验补 ≤5 |
| 返回 URL 时效 | 临时链接 | 固定 24 小时 | 不变，文档核对 |
| usage | 客户端不读 | `images_count` 将下线 | 无影响 |
| fast 专属分支 | 精简 payload、拒 edit、独立尺寸桶 | fast 不在列 | 随决策 1 处置 |

区域定位编辑：公告提及，但文档请求参数无新增 mask/region 字段，按提示词层面能力对待，仅更新 prompting 参考，不改客户端 schema。

## 2. 决策项（编号待选）

1. **fast 回退处置**
   - A（推荐）：删除 `FAST_MODEL` 专属分支（payload 裁剪、edit 拒绝、Fast 桶），`SN_IMAGE_GEN_FALLBACK_MODEL` 默认改空（自动回退关闭）；保留 `--fallback-model` 机制供用户显式指定任意模型。
   - B：保留 fast 兼容分支与机制，仅把默认回退改空。
   - C：维持现状（不推荐：`u1-fast` 不在公告路由保障范围，下线后回退必失败）。
2. **self_correction**
   - A（推荐）：lite 路径显式传 `self_correction`（默认 true），CLI 加 `--self-correction/--no-self-correction`；与 watermark 同理由防服务端默认值变更。
   - B：不传，依赖服务端默认 true（零改动，但默认值变更时无防护）。
3. **1K 档位**
   - A（推荐）：保留 1K 作为客户端显式尺寸映射（桶值均满足显式 WxH 约束，≤261 万像素走 SD 计费档），文档注明非服务端常量。
   - B：删除 1K，仅留 2K/4K/显式。
4. **验证方式**
   - A（推荐）：仅离线回归（两套 pytest + doctor），零成本。
   - B：离线回归 + 2 张付费探针（1 生成 + 1 编辑，验证 u1.6 受理与 self_correction），执行前编号确认张数并披露积分扣减，回执落盘。

## 3. 变更清单（按层）

**代码层**
- `skills/sn-image-base/scripts/sn_image_base/configs.py:113-116` — env 默认值（唯一 env 定义点）。
- `skills/sn-image-base/scripts/sn_image_base/generation/sensenova.py:38-39` 常量；`:98-99,135-139` 选模型与 fast 拒 edit；`:301-315` payload 裁剪；`:324-364` 尺寸解析；`:489-519` 三套桶；`:49,97,134` docstring。
- `skills/sn-image-base/scripts/sn_agent_runner.py:312-320,453-488` 回退矩阵与执行；CLI help 泛指文案。
- `skills/sn-motion-html/scripts/motion_stage.py:75`、`scripts/agnes_video.py:51` — `IMAGE_MODEL` 硬编码（锚图禁回退，agnes_video 校验返回 model）。
- `skills/sn-image-doctor/scripts/check_environment.py:180` 文案；无 ID 白名单，`:165-169` 尺寸断言值不变、无需改。

**配置层**：`.env.example:13-14`；`INSTALL.md:63-64`；`INSTALL_CN.md:63-64`。

**测试层**：`skills/sn-motion-html/tests/test_motion_html.py:1171,1178,1246,1358,1370` 五处硬编码；`test_sensenova.py:214-249` 尺寸断言随桶值不变；`test_skill_integrity.py:452,469` 自定义串不受影响；新增 u1.6 payload 断言。

**文档层**：根 `README.md`/`README_CN.md`；`docs/sn-image-generate.md`/`_en.md`；`sn-image-base` 的 `SKILL.md`、`README*`、`references/api_spec.md:13,17,27`；`sn-image-doctor/SKILL.md`；`sn-infographic/SKILL.md`、`references/runtime-parameters.md:28`、`references/prompts-expand-system.md:7`（系统提示词写死模型名，必改）；`sn-image-resume/SKILL.md`；`sn-image-imitate/SKILL.md`+`README*`；`sn-motion-html/SKILL.md:49`、`references/prompting.md:17`、`references/agnes-video.md:56`、`references/produce-and-deliver.md:7`、`docs/sn-motion-html.md:201`/`_CN.md:200`。历史记录类（`docs/sn-motion-html-integration-plan_CN.md`、`docs/project-review-2026-09-03-follow-up.md`）保留原文不改。

## 4. 执行阶段

- **P1 代码**（按决策 1/2/3）：常量与 env 默认 → `sensenova-u1.6-lite`；`U15_BUCKETS_2K` 更名 `BUCKETS_2K`（值不变）；fast 分支与回退默认按决策 1；`self_correction` 按决策 2；edit 入口补 ≤5 张校验。
- **P2 配置与文档**：env 示例、INSTALL、文档层全量替换；`api_spec.md` 重写为 u1.6 schema（self_correction、watermark 服务端默认 true 与付费风险、URL 24h、≤5 张、删 fast 1h 描述）；新增迁移段：过渡期路由只保障 `u1.5-*`，自配 env 旧 ID（尤其 `u1-fast`）的用户须自行改 `SN_IMAGE_GEN_MODEL`。
- **P3 测试**：motion 五处改 u1.6；新增 payload 断言（model、self_correction、watermark 显式）；两套 pytest 回归。
- **P4 验证**：doctor + 离线回归；决策 4B 时走付费探针流程（编号确认、披露计费、回执落盘、修复后零成本 replay）。
- **P5 提交**：commit/push 仅在明确指令后执行。

## 5. 风险

- 无水印后续付费：保持显式 `watermark=false` 并关注公告，文档已注。
- 过渡期结束路由失效：旧 ID 直接报错，靠迁移段与 doctor 文案提示。
- 1K 非服务端文档常量：走显式 WxH 文档化路径，风险可控；若探针拒绝则回决策 3B。
- `self_correction=true` 的时延/积分影响无官方量化：决策 2A 暴露开关可关。

## 6. 决策记录与验证结果（2026-11-24）

决策：1B 保留 fast 分支、仅回退默认改空；2A 显式传 + CLI 开关；3A 保留 1K 显式映射；4B 两张付费探针。

实施：代码层 configs / sensenova（self_correction、≤5 校验、桶更名 BUCKETS_2K）/ runner（--self-correction 三处接入）/ motion_stage / agnes_video / doctor；测试层 motion 五处、payload 与 ≤5 新断言、默认值断言；文档层 25 文件（api_spec 重写、CN/EN 迁移段），历史文件保留。

验证：
- 离线：194 passed + 69 subtests；doctor 全 OK。
- 探针回执 `.tmp/probes/gen_receipt.json`、`edit_receipt.json`：生成 2720x1536 HD，total_tokens 4612；编辑 auto→2752x1568 HD，total_tokens 13152；watermark=false 与 self_correction=true 均被受理。目视：生成文字清晰无水印；编辑仅换背景、文字保留。
- 观察：edit `size=auto` 返回服务端自适应桶（2752x1568），与主图尺寸不完全相同，属文档"auto 自动适配主图"口径，客户端无需处理。

改动未提交，commit/push 待明确指令。

## 7. 分支处置与 main 重做记录（2026-11-24）

- 处置决策（用户改选）：放弃移植合并流程。motion 分支仅提交 motion 侧 u1.6（`1810cbc`，9 文件）；image 侧工作区改动丢弃；切 main 对着新基线重做。
- main 基线差异与适配：`FAST_MODEL=sensenova-u1.5-fast` 保留遗留；payload 不再为 fast 裁剪；edit 的 fast-only ≤5 改通用 ≤5（报错文案兼容旧测试正则 "at most 5"）；doctor 保留遗留 fast Base64 校验、文案改 opt-in。
- 重做范围：configs / sensenova / runner / doctor / test_sensenova / test_skill_integrity + 19 文档文件（api_spec 重写、CN/EN 迁移段、task lifecycle 描述保留）。
- 验证：main 全量回归 123 passed + 30 subtests；doctor 全 OK；离线比对 main 的 u1.6 wire payload 与探针回执逐字段 MATCH，复用 motion 阶段 2 张付费探针回执，未新增付费调用。
- 状态：main 的 u1.6 改动未提交；main 原有 2 个本地 commit 未 push；motion 分支 `1810cbc` 未 push。commit/push 待明确指令。