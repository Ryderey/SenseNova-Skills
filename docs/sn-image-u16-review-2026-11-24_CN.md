# U1.6 迁移审查（main 工作区，2026-11-24）

范围：main 未提交改动（4 脚本 44+/22-、2 测试、19 文档）。重点：以前使用是否受影响；u1.6 完整能力实测。审查轮只报问题，不改文件。

## 1. 以前使用影响判定

| 项 | 以前 | 现在 | 判定 |
|---|---|---|---|
| env 钉 u1.5-lite | 直连 | 无白名单透传，过渡路由到 u1.6 | 无影响（待 C5 实测） |
| env 钉 u1.5-fast 回退 | 自动回退 fast | 路由覆盖 u1.5-*，过渡期仍可用 | 无影响（待 C6 实测）；下线后失效已文档化 |
| env 钉 u1-fast | 回退可用 | 不在路由保障，404 | 遗留风险，迁移段已提示 |
| 依赖默认自动回退 | 失败自动换 fast | 默认空=关闭，失败直接 failed | 有意行为变更（决策 1B），.env.example/INSTALL/api_spec 已注 |
| CLI 旧旗标 | 全量 | 全保留，--self-correction 纯增量 | 无影响 |
| size 各档 | 1K/2K/4K/显式/auto(edit) | 同，桶值不变 | 无影响 |
| edit >5 张 | lite 客户端不限，服务端裁 | 客户端 ≤5 结构化报错（runner:840 捕获 ValueError） | 报错前移、文案清晰，符合 u1.6 文档；低影响 |
| payload | 无 self_correction | 显式 true（服务端默认亦 true） | 无影响，探针已受理 |
| watermark/url/格式/重试/回退矩阵 | — | 零改动 | 无影响 |
| task lifecycle | SN_IMAGE_OUTPUT_DIR/MANAGER | diff 零触碰，test_task_files 全绿 | 无影响 |
| doctor 标签 | 旧文案 | 改名，git grep 无外部引用 | 无影响 |
| motion 分支 | image-base u1.5 基线 | motion 显式 --model u1.6 可用；无 --model 时仍 u1.5-lite（路由） | 跨分支口径差，合并后消解，方案§7 已记 |

## 2. 发现（编号带归属）

- **N1 能力缺口（非回归）**：u1.6 官方 generate 的 size 默认 auto（服务端受理 auto），客户端仍拒 generate auto（sensenova.py `_resolve_size` allow_auto 仅 edit）。照新文档用 `--image-size auto` 生成的用户会得 ValueError。api_spec.md:36 把 auto 口径收窄到 edits，与官方 generate 默认 auto 不一致。建议修复轮评估放开。
- **N2 文档口径**：api_spec.md:25-27 将 prompt_extend/response_format/output_format 的"Server default"列写"—"，官方文档实有默认（true/b64_json/png）。保守留空造成与官方默认表不齐。建议按官方补全。
- **N3 遗留 fast payload**：main 设计对 fast 发全 schema（含 self_correction）。过渡期 u1.5-fast 路由到 u1.6 可受理；fast 已公告下线，原生端点未知字段风险极低，仅记录。
- 无 S 级：未发现破坏以前使用的改动。

## 3. 实测矩阵（编号待确认）

复用既有 2 回执：gen 2K b64 png wm=false sc=true pe=true；edit auto 单参考 b64 png。新增 6 张：

| 编号 | 调用 | 覆盖能力 | 档位 |
|---|---|---|---|
| C1 | generate 4K 16:9 b64 png | 4K preset | HD |
| C2 | generate 1K 1:1 b64 png | 1K 显式映射 | SD |
| C3 | generate 2K 16:9 url webp --watermark --no-prompt-extend --no-self-correction | url 传输/webp/水印开/双开关关 | HD |
| C4 | edit 3 参考 2K 16:9 url --watermark --no-self-correction | 多参考/size 覆盖/edit url/水印开/sc 关 | HD |
| C5 | generate --model sensenova-u1.5-lite | 过渡路由兼容（旧 env 用户） | HD |
| C6 | --model sensenova-u1-fast --fallback-model sensenova-u1.5-fast | 主 404 免费→回退机制+u1.5-fast 路由 | HD |

计费披露：新增 6 张付费（5 HD + 1 SD），按账户图像积分规则扣减，usage 落回执；C6 主调用 404 不计费，若 u1-fast 意外成功则多 1 张计费。回执 `.tmp/probes/round2/`。
离线覆盖：>5 拒绝、auto+ratio 冲突、尺寸校验、回退矩阵单测、fast 遗留 payload、doctor、task lifecycle。

## 4. 离线证据

main 全量 123 passed + 30 subtests；doctor 全 OK；main u1.6 wire payload 与首轮探针回执逐字段 MATCH；git grep 无 U15_BUCKETS/旧 doctor 标签残留；脚本 diff 4 文件 44+/22-。

## 5. 实测结果（round2，6 张，回执 `.tmp/probes/round2/`）

- C1 4K preset → 4096x2304 HD，9758 tokens，ok。
- C2 1K → 1344x1344 **SD**，4489 tokens，ok（SD 计费档成立）。
- C3 url+webp+watermark=true+pe=false+sc=false → ok；目视 webp 格式、右下角官方水印；双开关关时标题照排不润色，开关语义到达服务端。
- C4 edit 3 参考+2K 16:9 覆盖+url+wm=true+sc=false → ok；usage.input_image_count=3、raw.size=2720x1536；目视背景改暖色、水印在；sc=false 时文字缺陷不修正（副标题重复、"Labb" 拼错），反证开关语义；文字密集多参考编辑建议 sc=true。
- C5 --model u1.5-lite → ok（2720x1536 HD）：过渡路由兼容成立，旧 env 用户无影响。
- C6 --model u1-fast --fallback-model u1.5-fast → 主 HTTP 404（免费）触发回退，fallback_used=true，回退经 u1.5-fast 路由成功：回退矩阵与遗留 ID 行为符合文档。
- 计费合计：round2 6 张（5HD+1SD）+ round1 2 张 = 8 张付费回执；C6 主 404 不计费。
- 覆盖口径：生成 1K/2K/4K、url/b64、png/webp、水印开/关、pe/sc 开/关、edit 1–5 参考/auto/size 覆盖、遗留路由、回退矩阵均实测；显式 WxH 与 jpeg 由离线校验+单测覆盖（服务端受理同形尺寸已实测）。
- **N4 跨分支合并风险**：main 基线 `_request_and_save` 无 `provider_url` 字段（该 hunk 来自 motion 分支 a7bb945），agnes_video 依赖它；u1.6 diff 零触碰（非回归）。日后 motion→main 合并须保留该 hunk，否则 motion 视频管线在 main 失去公网地址交接。归属：main sensenova.py `_request_and_save` / motion agnes_video.py。
- 结论：无 S 级；N1/N2 待修复轮，N3/N4 仅记录。以前使用不受破坏，u1.6 完整能力实测闭环。

## 6. 修复轮记录（N1/N2，2026-11-24）

- N1 已修：sensenova.generate 放开 auto（allow_auto=True；auto 时 ratio 不参与，非 auto 客户端补 16:9，旧默认不变）；runner gen 尺寸校验 allow_auto=True、--aspect-ratio 默认 None（非 auto 由客户端补 16:9，CLI 旧行为不变）；auto+显式 ratio 仍按统一规则报错。新增 test_generation_auto_size_and_default_ratio（auto payload、默认 2K 16:9、冲突规则）。
- N2 已修：api_spec 服务端默认列补 prompt_extend=true / response_format=b64_json / output_format=png；auto 口径同步 api_spec、CN/EN 指南、sn-image-base SKILL、runner help 五处。
- 复验：124 passed + 30 subtests（新用例即零成本 replay）；doctor 全 OK；`_normalize_image_size('auto', allow_auto=True)='auto'`。auto 服务端受理依官方默认口径，未新增付费调用。
- N3/N4 仍仅记录。全部改动未提交，commit/push 待指令。