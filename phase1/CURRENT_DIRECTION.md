# 当前研究方向唯一入口（2026-09-02）

> 本文件按日期与撤回链整理，覆盖最近两周的实验记录与 Git 提交。后续实验先读本文件，
> 不得用更早报告、旧 `AGENTS.md` 摘要或旧 HCE 配置覆盖这里的裁决。

> **2026-08-24 cohort authority clarification（覆盖下文所有“唯一主实验”旧措辞）**：当前没有已获批的
> GPU effect 主实验。论文容器仍是 Decision Corpus + Predictor Benchmark。`first-960 + closure` 保留为较早冻结的
> fixed-scorer critic 时间外确认人口；新的 target-300 identity cohort（保留 boundary-archive overshoot）则只授权 score-channel dual-truth 支持审计、
> 结果前 prediction escrow 及其 revised raw-grade supporting hypothesis。两者 estimand 不同、互不 supersede、不得混池；
> 300-run cohort 闭合或支持门通过也不会自动授权 replay/effect，仍需另做功效/成本矩阵并获用户 GPU 预算批准。
> 因而下文 0BK 的 first-960 契约继续有效，而 0DX 的旧 120s `SCORE_CHANNEL_MECHANISM_KILL` 也不被新 300-run
> 支持审计改写；所有更早“唯一主实验”“主线已确认”措辞均按本段降为历史状态。
> 第一次达到 target-300（含完整 boundary archive overshoot）的 formal output 必须自动写入固定 one-time closure anchor；
> 后续 runner 不接受调用者另选 cohort path/SHA，避免在多个合法-looking snapshot 中选择。

## 0L0. 2026-09-02 未来 20 天执行裁决：停止堆微型事后审计，集中完成 clean scaling 的来源门与论文初稿

本节覆盖下文所有“继续找一个小审计正数”的历史倾向，但不改变任何冻结 cohort、揭盲门或 GPU 审批规则。未来
20 天只保留四条并行工作：现有 outcome-blind closure watcher；真实 producer 的 config-v2 outcome-before 部署；
来源门通过后另报 GPU·时并获批的一次 `Qwen3 Base 0.6B/4B/8B × seeds 6/7` clean critic scaling；以及立即开始的
数据卡、贡献表、撤回表和论文完整初稿。新的 CPU-only audit 只有在关闭数据可发布性、split/label 完整性、claim
去重、前瞻 closure 或 scaling provenance 之一时才允许；对已发布 aggregate 的重新组合必须标为非独立证据。

当前结构起点仍为 source archives / eligible runs=`283/517`，Target-522 还差 `5` runs，first-960 还差 `443` runs；
按学长给出的理想生产速度 60 runs/day，后者条件点估计为 `7.383333` 天，不是进度保证。source 中 canonical
`*.config_v2.jsonl` 仍为 `0`；state root 内只出现一个非 canonical、metadata-only 的 config-v2 相关文件，内容未读，
不构成真实 producer sidecar。因而最大时限风险是学长尚未 review/apply 已验证的 producer hook；旧 archive 禁止事后
回填，缺 provenance 的新 runs 不能用于 exact-stratum scaling confirmation。完整日程、kill 条件与防 scoop 定位见
`phase1/TWENTY_DAY_POSITIVE_RESULT_SPRINT_20260902.md`；当前论文标题、摘要、贡献、主表/主图与 Evidence Index 路由见
`phase1/PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md`；数据发布事实、用途、偏差与未闭合许可/隐私门见
`phase1/DATACARD_DECISION_CORPUS_DRAFT_20260902.md`。旧 `phase1/paper.tex` 已显式标为历史稿，不得继续作为当前论文；
旧 `phase1/RELEASE_COMPLIANCE.md` 已标为只覆盖 v6 的历史初版，不得当作 v11 release clearance。
给学长的最小 producer 动作、sidecar patch SHA、联合 scaling 边界与贡献归属已整理在
`phase1/SENIOR_HANDOFF_20_DAY_SPRINT_20260902.md`。

## 0L1. 2026-09-02 v11 schema gate 已关闭；完整 release 仍受内容与许可门阻塞

为执行 0L0 中“只做能关闭 release blocker 的 CPU 工作”，现已对历史 v11 cards 与九个 decision JSONL 做值盲
schema inventory：10 个资源、24,119 行，producer 与不导入 producer 的 verifier 对每个 JSON path 的 type、presence/
null count、array-length bounds、bytes 与 hash 完全一致；focused tests=`3 passed`。inventory/verifier SHA-256=
`9a48bde7...6440eb` / `d6725443...7b1f8`，source value、candidate identity、label、prediction、prospective resource
read/emission=`false/false/false/false/false`，GPU/API/model fit/base update=`0/0/0/0`。

逐字段字典已固定 type、nullable、source、availability、release class 与 sensitivity，并正式记录一个历史 schema 边界：
train+extension 的 6,021/8,107 decision rows 显式带 `run_id`，三份 frozen 的 2,086 行全部缺该字段；后者必须由
endpoint→`card_run_map.json` 重建且接受 true-sibling/zero-overlap audit，不能任意回填。cards 中 fidelity fields 与
val_curve 全部未记录，`obs.error` 全 null；`val_at_low`、runtime、stdout 与 parent value 均不是 execution-free 输入，
`children_ids/n_siblings` 是 retrospective structure。`better/worse/gap_raw` 是 target，原始 ID/split/run 只供审计。
b1/b2 仍是历史 descendant-budget resource，不因 schema 完成而恢复 K>=1 lookahead 主张。

该工作关闭 `v11 schema dictionary` 单项 gate，但绝不等于数据 release clearance：code/stdout competition-data、
credential/PII/path 扫描，22/22 competition rules，provider terms，最终 LICENSE/NOTICE/licenses.json 与 Croissant/RAI
metadata 仍未闭合。公开件见 `phase1/SCHEMA_DICTIONARY_DECISION_CORPUS_V11_20260902.md` 与
`phase1/results/release_schema_inventory_v11_20260902/`；它是数据资产/复现补强，不计为新的 predictor/scaling/effect
科学证据，也不进入 Evidence Index 的 distinct claim count。

同一写作冲刺已把论文 Table 1--3 从蓝图占位展开成 `phase1/PAPER_TABLES_1_3_DRAFT_20260902.md`：直接竞品与相邻
方法定位、historical/prospective 分母分栏、十项 audit readout/does-not-prove 及 evidence routing 均已成稿。表中继续把
mle-traj raw true-sibling recoverability 标为 unknown，把 13,581 structural endpoints 与 13,098 scorer-common-support
endpoints 分开，并保持 Table 4/5 为 closure/scaling 条件槽；它是论文写作资产，不是新的实验结果。

## 0L2. 2026-09-02 v11 release-content scan 已完成 13 项预注册，正式结果尚未产生

schema 闭合后，当前最高价值的 CPU-only release blocker 是把 2026-08-08 只覆盖 v6/20 tasks 的 stdout 扫描升级到
v11。metadata-only preflight 已确认 exact cards rows/bytes/SHA=`16,012/305,750,663/6794acbf...1b75`；25 个历史
tasks 中 23 个已有 prepared text，合计 `1,377,069,541` bytes，仍缺 `aptos2019-blindness-detection` 与
`histopathologic-cancer-detection`，故本轮最多是 partial clearance，不能改写为 25/25。

结果前冻结 `release-content-scan-v1`：stdout 全行与 code decoded literals/literal containers/comments 使用固定
`40-byte / 12-distinct / 24-nonspace` 窗口，prepared suffix 固定为 csv/json/jsonl/txt/tsv/yaml/yml；public 只写
coverage/count/hash，raw patterns/matches、source file records 与 card identity 均留 mode-0700/0600 private root。
producer 支持 per-task receipt/resume；不导入 producer 的 verifier 重建 candidate patterns、source manifests、
affected-card aggregates，并逐 match 确认 source occurrence。synthetic focused=`3 passed`，Python compile 与 runner
`bash -n` 均通过。

正式执行必须从公开 exact commit 的 fresh no-smudge worktree 运行 producer A + resume B + verifier A/B，A/B 逐字一致，
另跑 focused+full tests、file/network trace、prospective-path 与 credential non-emission 门。GPU/API/model fit/base update=
`0/0/0/0`，预估 wall=`15--60 min`、hard timeout=`4 h`。若发现 match，只触发 review/sanitized successor protocol；
禁止原地修改 v11 LFS batch。完整 13 项 checklist 与 runner 见
`phase1/V11_RELEASE_CONTENT_SCAN_PREFLIGHT_20260902.md` / `phase1/scripts/run_release_content_scan_v11_20260902.sh`。
截至本段尚未在真实数据运行，不得报告 match/affected-card 数。

第一次公开 commit=`6bb82e59cb30db8612f4aa7dbbe6f6c4b4fda005` 的 remote launch 在任何 worktree、tests、
cards/source content read 或 scan output 前 fail-closed：runner 把 stdout 重定向到异步 `tee` 后立即 `chmod runner.log`，
文件创建存在竞态，本次恰好先执行 chmod，故 rc=`1`。失败 root/FAILED_RC 保留，GPU/API/model fit/base update=
`0/0/0/0`，科学/发布 readout=`0`。修复只是在 process substitution 前同步创建并 chmod log；新增契约测试固定语句顺序，
下一次必须用新的公开 exact commit/root，不能覆盖 r1 失败证据。

第二次公开 commit=`2bc056edb1a61e94e23b70c0b81cba175424cf1c` 已通过 13 项 immutable-input preflight 并创建
fresh exact worktree，但在第一个 focused test 前因 `source ~/env_setup.sh` 后的默认 `/usr/bin/python` 不含 pytest
而 fail-closed（rc=`1`）；cards/source scan、producer/verifier 与科学/发布 readout 仍均为 `0`。远端元数据门已确认项目
既有 `/research/d7/spc/yzyang4/venvs/exp/bin/python` 可执行，解析到 CPython `3.11.15` 且 pytest=`7.4.3`。
第三次只允许把 runner 的所有 test/producer/verifier/summary Python 调用统一固定到该解释器，并在 worktree 前执行
`import pytest` capability gate；protocol、输入、阈值与 estimand 均不变，仍须使用新的公开 exact commit/root。

## 0KZ. 2026-09-02 Structural Gate Utility Certificate 正式通过：当前 7/7 受影响 competition 未见最后可用支持被清空

为把 0KI/0KV/0KW 与 zero-checkpoint 审计转成一条可直接写进论文的数据工程结论，本节只做**事后逻辑合成**，
不读取新的 prospective value，也不把共享输入重复计成第五项独立结果。结果前协议把 7 个 distinct rejected
competitions 固定为互斥完备分区：仍有 accepted eligible support，或唯一链接到零 checkpoint trigger；只有前者也
消失时才计为 observed last-usable-support elimination。协议及八份输入 result/verifier 均绑定精确 SHA-256，producer
A/B 与不导入 producer 的 verifier A/B 另做 trace 重建；`counts_as_distinct_claim_evidence=false` 从协议到发布件保持。

公开 exact commit=`a0e04d27bcf900c2a1293f8ffad38d5104f6d3a3` 的 fresh formal v4 完整通过：focused/full=
`12/2,013 passed`（48 warnings，140.68 秒），13 项 preflight、9 个输入 hash before/after、builder/verifier A/B 与
trace 均逐字节一致；root mode/files=`0500/39`，COMPLETE/FAILED_RC=`true/false`，formal manifest=
`1078227f...45d82`（37 members）。独立 postflight 逐项复核 manifest、clean exact worktree、A/B、JSON contract 与
security receipt 后 PASS；certificate/verifier SHA-256=`b50e99e2...b1f55` / `9ec64e09...1d055`，forbidden-open/
network/credential filename/content hits=`0/0/0/0`。

正式分区为 retained-support / invalid-only=`6/1`，accounted=`7/7`，observed last-usable-support elimination=`0`。
6 个 retained competitions 合计有 accepted archives / physical runs / eligible runs / endpoints=`20/94/92/2,558`，
每个至少 `4` eligible runs 与 `50` endpoints；唯一 no-support competition 所链接 archive 的 discovered roots /
checkpoint runs / live-only excluded=`2/0/2`。因此 paper-safe 正结论是：**在已结算 283-archive 状态中，结构校验
表现为 support-preserving quality gate；有可用 checkpoint 支持时它仍被保留，唯一无支持事件本身没有 checkpoint 数据。**

边界：这是四份已发布 aggregate evidence 的 post-hoc certificate，不是新的独立实验或 fully blind confirmation；
不得外推未来 stationarity、宣称普适无损定理、断言 malformed archive 无法修复，或声称 predictor accuracy、scaling、
search utility、因果方法效果或 task 白/黑名单。前三次执行环境失败均在任何 tests/certificate/verifier/formal summary 前
停止并保留：v1 缺 LFS filter rc=`128`；v2 交互连接中断后最终记录 post-checkout hook rc=`2`；v3 持久化复现同一
hook rc=`2`。v4 只对单次 worktree-add 使用空 hooks path，未改远端仓库钩子。prospective values/raw senior archives/
identity read=`false/false/false`，GPU/API/model fit/base update=`0/0/0/0`。公开件见
`phase1/results/structural_gate_utility_certificate_20260902_a0e04d2/`。

公开 release commit=`3cda09d73292255381ce032de032987194785441` 的 fresh-checkout v1 已先完成 focused/full=
`18/2,019 passed`，但旧 credential regex 将 `CURRENT_DIRECTION.md` 中普通 `task-*` 子串误判为 `sk-*`，因此按
fail-closed 以 rc=`1` 停止且未写 COMPLETE；安全复核确认只有这一文件路径命中。v2 只增加 `sk-` 左侧边界并使用
全新 worktree/root，正式通过 `18/2,019 passed`（48 warnings，139.01 秒），公开 package manifest 全部一致，
credential filename/content hits=`0/0`；root mode/files=`0500/15`，post-push manifest=
`bfab7b18...1b5f69d`。独立复核再次验证 exact commit/parent、clean worktree、两层 manifest 与固定 certificate/verifier
hash 后 PASS。该步骤仅确认公开提交可复现，没有重算、重选或增加科学结果。

## 0KY. 2026-09-02 Target-522 两个下游纯等待 watcher 第三次自然超时后已无结果续接

outcome-blind 复核确认 source/LATEST/snapshot dirs 仍为 `283/e9e12c63...8a6d/133`，Target-522 selection
账本仍为 SHA/lines/runs=`02774632...170f/29/517`，距固定 `522` 还差 `5` runs；selection PID=`2930562`
live、lock held，无 COMPLETE/FAILED/TIMEOUT/CONTINUITY_GAP。Stage-A 与 contrast-rank 的上一轮纯等待 PID=
`3451204/3451299` 均在 poll=`720` 后自然写出 `TIMEOUT_RC=124` 并退出；两锁 free、无 COMPLETE/FAILED/
INTERRUPTED，两个正式 output root 均不存在，初始 gap context 与第一次 repeat-timeout context 的 SHA-256=
`eec0154f...f508` / `9e305ace...425e` 均保持不变。

结果前冻结 `target522-downstream-third-timeout-renewal-v1`，唯一允许动作是分别调用已安装且哈希绑定的两个
`source_script.sh resume` 一次，并追加第二份 repeat-timeout context；selection、target、protocol、producer/analyzer、
verifier、tests、runner 均不可改变，旧 within/lineage/selective/yield/lookahead watcher 不恢复。公开 exact commit=
`4223ade7670d3ba6a6f66debf63a7b0c6872d9c1` 的 remote check 通过后执行，Stage-A/rank 新 PID=
`4041657/4041733` 均 live、locks held、新 marker-only waiting 日志存在，selection ledger 逐字节不变。

独立 postdeploy v1 已完成全部状态核验，但在最后的 credential 零命中 grep 因 pipefail rc=`1` 提前退出；它没有修改
远端状态。v2 只修零命中计数语义后完整 PASS：selection+两个下游共三锁 held，旧 context 保留，新 context 两份
逐字节一致（SHA-256=`b670658c...01fb`），action root mode=`0700`、manifest=`1f4dce42...ecec5`，credential
filename/content hits=`0/0`。这是监控连续性修复，不是科学结果；outcome/prediction/candidate identity/profile 未读，
GPU/API/model fit/base update=`0/0/0/0`。

## 0KX. 2026-09-02 Evidence Index v10 正式通过：四项 distinct 资产入索引，0KW 强制只计 reconstruction

0KW 的 prior-evidence omission 表明仅靠人工阅读长方向文档不足以防止同一 estimand 被重复包装。新增
`decision_corpus_evidence_index_v10` 作为 post-result reporting/audit 修复：逐字保留 v9 的 16 个条目与
`AWAITING_FIRST960` 状态，只新增四项 distinct evidence entry：0KH archive-disposition longitudinal、0KI
archive-granularity retention、0KU 494→517 WL append-only snapshot chain、0KV 14-event support census。
0KW support floor 不进入 distinct `entries`，而进入单独 `reconstructions`，必须指向 0KI 的
`prior_support_depth` component 且 `counts_as_distinct_claim_evidence=false`。

除结构 signature/pointer 门外，builder 与**不导入 builder**的 verifier 都直接交叉比较 0KI/0KW 的 competition
数、四类 totals、四类 min/median/max 与两项 dominance，共 `19` 个共享数值；任一不等、缺失 prior pointer、
把 reconstruction 计为 distinct、修改任一 v9 entry 或提升 provisional 状态都 fail-closed。v10 的机器 accounting
为 source/distinct-added/reconstruction/total-distinct/duplicate-counted=`16/4/1/20/0`；旧 v9 条目尚未追溯结构化
fingerprint，因此该门的明确覆盖范围是 v10 additions 与 reconstruction records，不能声称已自动解决全部历史语义重复。

第一次 formal launcher 因调用方传入不存在的完整 commit 字符串在 worktree 前以 rc=`128` 停止；worktree/index/
verifier/COMPLETE=`false/0/0/false`，没有 reporting 或科学 readout。随后 exact commit=
`983bdec9c19da52ca12fd58d6f1a9ae371ea24d5` 的 fresh v2 完整通过：focused/full=`105/1,988 passed`
（48 warnings，115.29 秒），13 项 preflight、13 个输入 hash before/after、builder A/B、verifier A/B、trace
重建均一致；root mode/files=`0500/41`，COMPLETE/FAILED_RC=`true/false`，forbidden-open/network/credential
filename/content hits=`0/0/0/0`。index/verifier/manifest SHA-256=`51da3ccb...ae7af` /
`b31e389d...c0e0f` / `0c98fde4...55d00`。

这是一项正面的 **Audit Protocol 完整性资产**：它把近期有效结果纳入单一机器索引，并机械阻止本次已发生的重复证据
计数；但它不增加新的科学 effect、predictor accuracy、scaling 或 search-utility 结果，也不解除 first-960 closure。
prospective values/raw senior archives/candidate identities read=`false/false/false`，GPU/API/model fit/base update=
`0/0/0/0`。公开件见 `phase1/results/decision_corpus_evidence_index_v10_20260902_983bdec/`。

公开 release commit=`492fad67a43c2e4ddd4aaad3d290d8c2570b41f9` 的 fresh post-push 复验也完整通过：
focused/full=`112/1,995 passed`（48 warnings，124.38 秒），13 项 preflight、13 个输入 hash before/after、
builder/verifier A/B 与 trace 重建均一致；root mode/files=`0500/41`，COMPLETE/FAILED_RC=`true/false`，
forbidden-open/network/credential filename/content hits=`0/0/0/0`。post-push manifest SHA-256=
`303a350b...e6e8`（39 members，全部逐字节一致），index/verifier SHA-256 仍为 `51da3ccb...ae7af` /
`b31e389d...c0e0f`。该复验只确认公开 commit 可独立重建，没有重算或重选科学结论。

## 0KW. 2026-09-02 support floor 已完成；证据索引勘误后降级为独立重建 + current-window lineage

> **证据索引勘误（覆盖本节所有“未知/新正结果/推进”旧措辞）**：本节首次发布时漏检了 0KI 的 2026-08-31
> `archive_granularity_retention_audit_v1`。本次 prior totals=`20/94/92/2,558`、四指标 min/median/max、eligible-run 与
> endpoint dominance 都已由 0KI 在同一 prior snapshot 正式发布；因此它们不是新未知量，本节也不能与 0KI 分开计作
> 第二项正结果。当前固定分类为 `PRIOR_EVIDENCE_OMISSION_CORRECTED_INDEPENDENT_RECONSTRUCTION`：保留有效的独立
> 重建、14-event census 绑定与 current-window `+1/+4/+4/+96` lineage，但撤回“新突破”定位。完整机器 crosswalk 与责任
> 说明见 release 的 `prior_evidence_crosswalk.json` / `ERRATUM.md`。

0KV 已完成的 aggregate census 表明 14 个结构拒绝事件来自 7 个匿名 competition，event 四类计数为
prior/window/archive-only/no-support=`13/0/0/1`，competition 去重计数为 `6/0/0/1`；这些量及 event-weighted
support totals 已公开，不能再伪装为未知或 fully blind。本段只提出一个更窄的 **post-hoc identity-erased full-census**
问题：对每个 rejected competition，prior/current 支持究竟有多深、是否只靠单个 archive/run、支持是否高度集中；
不设置二元成功阈值，不作抽样推断，也不估计未来 rejection 频率或因果效应。

真实 floor readout 前冻结 `archive_rejection_support_floor_v1`：exact prior/current snapshot=`30945550...104f` /
`e9e12c63...8a6d`，transactions=`126/133`、window=`7`，observations SHA/bytes=`d2ed361a...a704a/200,613`；
并逐字节绑定已发布 census result/verifier SHA=`f904ff54...917fad` / `39a634f0...276e6`。协议当时错误声明为未知的量包括 distinct-
competition totals、四指标的 min/exact-rational-median/max/zero/one/max-share、6 个 prior-supported competition 的
最小 eligible-run fraction 与 endpoints-per-eligible-run，以及 current window 有增量的 competition 数。输出禁止
competition/archive/task/run/candidate 身份值及逐 competition 向量；其中 prior totals/ranges/dominance 实际已由 0KI 公开，
这是 predecessor evidence omission，不是合法盲测未知量。

producer 与不导入 producer 的独立 verifier 已分别实现；合成四类 fixture 验证动态 `4/1` competition，而非把真实
`7/6` 写死进实现。精确摘要、census evidence/window/candidate 篡改、identity non-emission、verifier non-import 与真实
协议 hash-binding 共 focused=`8 passed`。protocol/producer/verifier/test SHA-256=`e60500f7...66b2d` /
`25b74e48...0b58` / `97321e0f...c8f2` / `207b5530...faf9`。截至该历史时点尚未在真实 state 上运行
producer，但 prior core 数值并非科学未知；GPU/API/model fit/base update=`0/0/0/0`，不得外推 predictor accuracy、
scaling、search utility 或方法效果。

随后冻结 exact-commit formal runner：13 项 preflight、fresh no-smudge worktree、focused+full tests、producer A/B、
不导入 producer 的 verifier A/B、allowed-metadata read-only before/after、file/network trace、credential 与 identity-schema
门、clean-worktree 及 append-only COMPLETE/FAILED receipt。runner static check=`PASS`，floor+runner focused=`12 passed`，
全部相邻 archive 审计=`57 passed`；runner/contract-test SHA-256=`5b66502a...c3229` / `880dfcab...3392a`。
截至本段 runner **尚未 formal 执行**，因此上一段的未知量仍不得读取或报告；必须先公开该 runner 的 exact commit，
再从 fresh formal root 单次执行。

公开 exact commit=`5609a8e70098af0a912e61284529ca20d0a91f8e` 的 fresh formal 已完整通过：focused/full=
`12/1,963 passed`（48 warnings，147.02 秒），producer A/B、非导入 verifier A/B、read-only before/after 均逐字节
一致；root mode/files=`0500/29`，COMPLETE/FAILED_RC=`true/false`，network/forbidden-path/identity-schema/credential
hits=`0/0/0/0`，manifest=`86973b22...06a1`，result/verifier SHA-256=`ce8b3010...f4248` /
`3ab7085a...796c`。

6 个 prior-supported competition 在 prior anchor 的 accepted archives / physical runs / eligible runs / endpoints
总量为 `20/94/92/2,558`；min/median/max 分别为 archives=`1/4/5`、physical runs=`4/17/29`、eligible
runs=`4/17/29`、endpoints=`50/458.5/944`。恰好一个 accepted archive 的 competition 有 `1` 个，但恰好一个
physical 或 eligible run 的 competition 都为 **`0`**；即使最弱支持也不是 single-run artifact。最小 eligible-run
fraction=`5/7=0.7142857`，最小 endpoints/eligible-run=`25/2=12.5`。最大 competition concentration share 在
archives/physical/eligible/endpoints 上分别为 `1/4`、`29/94`、`29/92`、`472/1279`（最高 36.90%），未出现单个
competition 完全垄断。current 7-transaction window 仅给 `1` 个 competition 增加 `1/4/4/96`，因此 prior floor 不是
窗口普遍补齐造成的。

数值上再次得到“6 个 prior-supported competition 均有至少 4 个 eligible runs 和 50 个 endpoints，且支持分布未被单个
competition 垄断”，但该核心证据归属于 0KI；本节只构成独立实现重建与新 snapshot lineage，不推进科学证据计数。它仍是 aggregate census 揭盲后的 post-hoc
descriptive audit，只有 7 个 competition，不是新的 fully blind confirmation；prior anchor 不等于 event-time preexistence，
不得估计未来 rejection 频率、因果效应、predictor accuracy/scaling、search utility 或建立 task 白/黑名单。
release contract=`5 passed`，floor+runner+release focused=`17 passed`，全部相邻 archive 审计=`62 passed`；
GPU/API/model fit/base update=`0/0/0/0`，label/grade/outcome/prediction/accuracy/utility/candidate identity/profile
read=`false/false/false/false/false/false/false/false`，identity values emitted=`false`。

公开 release commit=`d1766d1aa767af9e61d1f6a23132978a9af3e238` 的 fresh-Linux post-push 复验也已通过：
formal receipt hashes=`7/7 exact`，focused/full=`17/1,968 passed`（48 warnings，140.61 秒），公开 result/verifier
hash、identity release contract、changed-path credential filename/content 与 clean-worktree 门均通过。post-push root
mode/files=`0500/10`，COMPLETE/FAILED_RC=`true/false`，manifest=`0364ddca...064d`；该步骤只验证 GitHub checkout，
没有重算或重选科学结果。

证据索引勘误与机器 crosswalk 已由公开 commit=`c0189bba0d808c4faddc9a83f69dcb75c4143ae2` 固定；其
fresh-Linux corrected-release post-push 复验完整通过：formal receipt hashes=`7/7 exact`，focused/full=
`18/1,969 passed`（48 warnings，123.21 秒），公开 result/verifier hash、identity release contract、changed-path
credential filename/content 与 clean-worktree 门均通过。post-push root mode/files=`0500/10`，
COMPLETE/FAILED_RC=`true/false`，manifest=`6b7a5411...9011f`；固定分类为
`PRIOR_EVIDENCE_OMISSION_CORRECTED_INDEPENDENT_RECONSTRUCTION`，且 crosswalk 明确
`counts_as_independent_new_scientific_result=false`。该步骤只验证纠错后的公开 checkout 与既有 formal receipts，
没有重算、重选或增加科学结果。

截至 `2026-09-01T17:18:39Z` 的 outcome-blind 结构复核：学长 source 仍为 `283` archives，最新 archive mtime=
`2026-08-31T15:21:59Z`，LATEST/snapshot dirs=`e9e12c63...8a6d/133`，canonical config-v2 sidecars=`0`；intake、
Target-522 selection、Stage-A、contrast-rank 四个既有 PID 均 live，未重复启动。`fork/dojo-reproduce` 已到
`5baccb170ce287f9c8eed7b23ccf693a0268515a`，相对已处理 outcome commit=`f534114e...c8ad` 有 3 个 commit、20 个
changed paths（16 live、4 deleted），但没有 `src/mle_critic/docs/outcomes` 变更；增量 credential content/filename
hits=`0/0`。这些变更集中在旧 augmented data/training/lookahead 路径，内容未读，也不会据此恢复已关闭 lookahead
或旧训练方向；远端旧 checkout 有 1 个 tracked dirty 文件，未覆盖、未 reset。

## 0KV. 2026-09-01 全部 14 个结构拒绝的支持度普查完成：13/14 在 prior anchor 已有 eligible support

为避免把 0KT 的单个 absent 事件误写成总体频率，本段把当前 immutable observer census 中**全部 14 个结构拒绝事件**
定义为完整描述性人口，并在任何真实全量支持 readout 前冻结四级互斥分类：`PRIOR_ANCHOR_ELIGIBLE_SUPPORT`、
`CURRENT_WINDOW_ELIGIBLE_SUPPORT`、`ACCEPTED_ARCHIVE_ONLY_NO_ELIGIBLE_SUPPORT`、
`NO_ACCEPTED_ARCHIVE_SUPPORT`。prior anchor 只表示到 `30945550...104f` 快照时已有支持，不能解释为拒绝发生前已有支持或
因果关系；14 事件是 census，不作抽样推断，也不预注册二元成功阈值。

已知信息被显式写入协议：旧 12 个事件来自 6 个 competition，且到旧 `7cda` 快照时 6 个都有某种 accepted transaction；
最新第 14 个事件已由 0KT 独立证明为全零 support。因此 headline **不是 fully blind**。真实执行前仍未知的是第 13 个事件的
类别、14 事件四类计数、reason×class 整数表、distinct competition 四类计数及匿名支持量聚合。输出禁止事件、competition、
archive、task、run、candidate 身份值，只保留整数聚合和 classification digest；不得据此建立 task 白/黑名单，也不得声称
predictor accuracy、scaling、search utility 或方法效果。

协议把 current/prior transaction lines=`133/126` 与 window=`7` 分别绑定，producer 与不导入 producer 的独立 verifier 均
从协议读取 window，避免实现写死。四类合成正控、prefix/payload/candidate 篡改、协议引用哈希、窗口绑定与 identity
non-emission 合计 focused=`8 passed`；与相邻单事件审计合跑=`19 passed`。protocol/producer/verifier/test SHA-256=
`c1429763...d409f3` / `fa9f182d...c46b15` / `902da600...487a6` / `335185e2...e223b`。

随后冻结 exact-commit formal runner：13 项 preflight、fresh no-smudge worktree、focused+full tests、producer A/B、
不导入 producer 的 verifier A/B、allowed-metadata read-only before/after、file/network trace、credential 与 identity-schema
门、append-only COMPLETE/FAILED receipt。runner/static check=`PASS`，census+runner focused=`12 passed`，连同相邻单事件
审计=`23 passed`；runner/contract-test SHA-256=`8ac1f769...5dd0a` / `21028895...c2761`。

公开 exact commit=`ec2bf654750080ffce6f1972789adc50033c5e0e` 的第一次 formal 已通过 focused/full=
`12/1,947 passed`（48 warnings），但第一个 producer 以绝对脚本路径从远端 home 启动，导入阶段即触发
`ModuleNotFoundError: No module named 'phase1'`；result/verifier/COMPLETE=`0/0/false`，FAILED_RC=`1`，因此没有任何真实
事件分类或科学 readout。只允许执行层修正为在 exact worktree 中以 `python -m` 启动 producer/verifier；协议、输入、
分类、资源与访问契约均不变，并须从新的公开 exact commit 使用 fresh formal root 重跑。修正后 static check=`PASS`，
focused/adjacent=`12/23 passed`，runner/contract-test SHA-256=`fe3bc55f...fc7c4d` / `556a2a94...5e72c`。
fresh exact commit=`7ad0164d85b892fc0e809bcc43b3c235344620d0` 的 formal 已完整通过：focused/full=
`12/1,947 passed`（48 warnings，119.83 秒），producer A/B、非导入 verifier A/B、read-only before/after 均逐字节一致；
root mode/files=`0500/29`，network/forbidden-path/identity-schema/credential hits=`0/0/0/0`，manifest=
`69fdc6cb...76764f`，result/verifier SHA-256=`f904ff54...917fad` / `39a634f0...276e6`。

正式四类计数为 event：prior/window/archive-only/no-support=`13/0/0/1`，即 prior support=`13/14=92.857143%`；按匿名
competition 去重为 `6/0/0/1`，即 `6/7=85.714286%`。此前未知的第 13 个事件因此属于 prior support；唯一 no-support
competition 是 0KT 已披露的最新事件。按原因分层，no-checkpoint=`2 prior + 1 absent`，identity-absent=`2 prior`，
identity-not-exactly-one=`9 prior`。这支持“当前结构拒绝主要是冗余/质量门，而非系统性删光 competition 支持”的正向
benchmark-audit 结论，同时唯一 absent 事件证明 gate 非 vacuous。

该 headline 仍是 partially predisclosed complete census，不是 fully blind confirmation；prior anchor 不等于 event-time
preexistence，event-weighted 数量会重复计算同一 competition，不能用于 task 白/黑名单、未来频率外推、因果效应、predictor
accuracy/scaling 或 search utility。公开 release contract=`4 passed`，census+runner+release focused=`16 passed`；
GPU/API/model fit/base update=`0/0/0/0`，label/outcome/prediction/accuracy/utility/candidate identity/profile
read=`false/false/false/false/false/false/false`，identity values emitted=`false`。

公开 release commit=`361e94171139630b90d8b969da06d78b06e601e3` 的 post-push v1 focused=`16 passed`，但外部
harness 未设 `umask 077`，一个既有 private-file 权限测试在 full=`1,950 passed/1 failed` 后正确停止；该失败不涉及 census
或 release artifact。fresh v2 只补 harness umask，随后 focused/full=`16/1,951 passed`（48 warnings，145.85 秒），root
mode/files=`0500/10`，result/verifier/remote-manifest 字节绑定、identity release contract、credential 与 clean-worktree 门全过；
manifest=`4cbbd83b...2f270`。v1 失败根保留，v2 未重算科学结果。

## 0KU. 2026-09-01 517-run WL 冻结链完成：旧 494-run 前缀零删除，新增 23 runs

零 fit support renewal v2 的 WL 路径已在 current snapshot=`e9e12c63...8a6d` 上完整结束并 promotion；远端 formal root
权限=`0500`、files=`52`、COMPLETE/FAILURE/FAILED_RC=`true/false/false`，producer、非导入 independent verifier 与
snapshot-chain verifier rc=`0/0/0`，三者 wall time=`25:14.25/23:46.31/0:02.09`。完整 SHA256SUMS 独立复验全过，
forbidden-path/credential hits=`0/0`。

append-only 结构覆盖从 `494` 增至 `517` eligible runs：added/removed/unchanged=`23/0/494`；旧 endpoint/pair 行
`13,098/3,230` 均逐行保持，当前为 `13,581/3,325`，新增 `483/95`，prior set/sequence/frozen-order invariants 全过。
snapshot-chain status=`PROVISIONAL_FIRST960_SNAPSHOT_CHAIN_INDEPENDENTLY_VERIFIED`，独立当前 verifier status=
`INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED`。这是一项**benchmark coverage + audit protocol** 正证据，
不是 predictor accuracy、scaling、effect size 或 search utility；first-960 尚未 closure，support gate 仍 provisional。

公开记录只保存结构 receipts、rc、runtimes 与 hash；endpoint scores、pair predictions、artifact summary、traces、commands
及 full independent payload 均未复制。outcome/prediction value/candidate identity/profile read=`false/false/false/false`，
GPU/API/model fit/base update=`0/0/0/0`。截至 `2026-09-01T15:18:34Z`，学长 source 仍为 `283` archives，LATEST 未变；
transition/receipt state 仍在 `30945550...104f`，因为 transition 需要另行批准的 6 次 model fit，本次没有擅自重启。

公开 commit=`cbb22c5bce60b6eb592a10da4bf9672212d7866a` 的 post-push v1 focused=`6 passed`，但 full 从远端 home
启动，16 项 repository-relative path 测试触发 `FileNotFoundError`（`1,919 passed/16 failed`）；该 harness 错误根已按
`EXECUTION_HARNESS_CWD_FAILURE` 只读封存，科学/发布代码未改。fresh v2 只把 cwd 固定到 exact clean worktree，随后
focused/full=`6/1,935 passed`（48 warnings，pytest=`122.59s`），13-item preflight、filename/content credential scan、
manifest 与 scope 门全过，COMPLETE=`true`。v1/v2 manifest SHA-256=`70ed232f...fae0a/d27e9da9...e0421`；
GPU/API/model fit/base update=`0/0/0/0`，outcome/prediction value/identity/profile read=`false/false/false/false`。

## 0KT. 2026-09-01 新增单个结构拒绝的时间顺序支持审计已在 overlap readout 前冻结

相对 `30945550...104f`，当前 `e9e12c63...8a6d` 的 outcome-blind archive 增量为 observed/accepted/structural reject/
alias/pending=`8/7/1/0/0`；累计 observations SHA-256/bytes=`54a8d773...6571e0/200,613`，current/prior
transactions SHA-256/lines=`fabae2e4...f7467/133` 与 `4f05659d...6ec60/126`。新增唯一结构拒绝由结果前已固定的
no-checkpoint registry SHA-256=`0c138eb6...129ffe` 选择，reason=`ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS`；截至本段尚未
读取它对应的 competition，也未计算其 accepted support。

预注册 `incremental_archive_rejection_support_audit_v1`：strong 要求该匿名 competition 在旧 126-transaction prefix 中已
至少有 `1` accepted archive、`1` eligible run、`1` endpoint；若仅新增 7 个 accepted transactions 后才有 support，降为
contemporaneous-only；当前仍无 eligible support 则 absent。producer/verifier 必须各自 A/B 逐字节一致，并证明 current
transactions 有 exact prior byte prefix、目标 registry 只选中 1 个结构拒绝、accepted provenance 单任务且 run IDs 唯一。
该项只是单个前向事件的 event-level confirmation，不得称 population-level replication、predictor 效果或 search utility；
registry content、archive payload、label/outcome/prediction/identity read=`false`，GPU/API/model fit/base update=`0/0/0/0`。
protocol SHA-256=`9d1c9377...8acfaff`，focused contract tests=`4 passed`；当前只有结果前冻结，尚未执行真实 overlap readout。

随后在真实 readout 前完成 producer 与**不导入 producer**的独立 verifier。实现审阅先纠正 observer `path` 必须等于
`source_root + relative`（不能误当纯 relative），并把 accepted increment 从硬编码改为读取冻结协议，同时补齐
LATEST/intake summary/source provenance 的 no-symlink 门；纠正发生在任何 target competition/support readout 之前。
producer/verifier SHA-256=`ddc09da3...9c2c51` / `a6098cdf...247f7`；三种 decision path 及 prefix tamper、重复目标、
payload overlap、路径伪造、候选结果篡改与 identity non-emission 共 `14 passed`，连同既有 archive longitudinal 契约为
`24 passed`。截至本段仍未执行真实 overlap readout，故不得提前报告 strong/partial/absent。

真实执行前进一步冻结 exact-commit formal runner：fresh no-smudge worktree、13 项 preflight、focused+full `phase1/tests`、
producer A/B、非导入 verifier A/B、allowed-metadata read-only receipt、file/network trace、credential/identity-schema 门及
append-only COMPLETE/FAILED receipt。runner/runner-contract-test SHA-256=`0f5e561c...8f44eb` / `1b783b37...70d10d`；
远端 `bash -n + check` PASS，focused 总计=`18 passed`。截至本段 runner 尚未 formal 执行，科学 readout 仍未知。

第一次 exact-commit 提取在 formal root/worktree 创建前因外层 launcher 未加载 proxy 失败；第二次仍在提取前因
`env_setup.sh` 与 caller 的 nounset 冲突失败。两次独立检查均为 formal root/worktree absent，producer/result files=`0/0`，
因此没有科学 readout。仅作执行修复：外层 launcher 加载环境，formal runner 在 source 前后临时 `set +u`/恢复 `set -u`；
科学协议、输入、producer/verifier 与资源矩阵不变。修正 runner SHA-256=`e64cc237...60c22f`，focused 仍为
`18 passed`；须从新的公开 exact commit 重新开始 fresh formal。

`4cb063d...` fresh formal 随后在 focused tests/producer 前被 observations whole-file hash 门停止：FAILED_RC=`2`，
result/verifier/COMPLETE=`0/0/false`。复验显示 mutable observations 新 SHA/bytes=`d2ed361a...a704a/200,613`，但
LATEST、transactions SHA/lines、prior-prefix、disposition partition、target-registry match 与 inventory 仍精确为
`e9e12c63...8a6d`、`fabae2e4...f7467/133`、true、`283/128/133/14/8/0`、`1`、
`543/517/13,581/3,325/38`；旧 bytes 未保存，故**不能**声称只改了 `updated_at_utc`。

在 support readout 前已把当前完整 observations 封存到权限 `0444` 的远端不可变副本，SHA/receipt SHA=
`d2ed361a...a704a` / `f5c722af...b93cfa`。execution-v2 通过机器比较证明相对原协议只改
`inputs.current_observations_sha256`，科学/资源/access changes 均为空；execution protocol/addendum/runner SHA=
`451f4b64...7008b2` / `7a144f73...04628f` / `d52b3c73...6f7d5d`，远端 static check PASS，focused=`21 passed`。
截至本段 execution-v2 尚未 formal 执行，strong/partial/absent 仍未知。

`78fe667...` execution-v2 已通过 immutable-input preflight，但 focused test 立即因系统 `/usr/bin/python3` 缺 pytest
而停止；FAILED_RC=`1`，focused/full/producer/result/verifier/COMPLETE=`0/not-started/false/0/0/false`，仍无科学
readout。只把 runner 解释器固定为项目既有 `/research/d7/spc/yzyang4/venvs/exp/bin/python`，并在 formal 前验证
executable + `import pytest`（远端 pytest=`7.4.3`）；协议与输入均不变。v3 addendum/runner SHA=
`8768d4d9...a8da3d` / `a0d0bca8...91a7d2`，远端 static check PASS，focused=`22 passed`；须再从新的公开
exact commit 运行 fresh root。

`2f77069...` fresh formal 的 focused/full tests 已精确通过 `22/1,930`（48 warnings），随后 producer 在任何 entry
classification、target support/status 或 result write 之前以 `observations schema mismatch` fail-closed；result/verifier/
COMPLETE=`0/0/false`。只输出键名的独立 schema 检查证明 frozen observer 顶层为
`baseline_sealed_at_epoch,entries,protocol,source_root`，而实现误用了相邻 watcher 的
`minimum_age_seconds,updated_at_utc` 容器。producer 与非导入 verifier 已分别改为真实四键 schema，并验证 baseline seal
为 finite nonnegative；fixture 同步改正且新增 adjacent-schema 反例。v4 addendum/producer/verifier SHA=
`b1495de4...2f187` / `0d5ac76f...112e4` / `6e688332...9bc4e`，focused=`24 passed`，与既有 archive
longitudinal 合跑=`21 passed`；科学协议、输入与资源不变，仍须新的公开 exact commit fresh run。

公开 exact commit=`ce9f50531779174c497da5eae5c66b570de92880` 的 fresh formal 已完整通过。focused/full=
`24/1,930 passed`（48 warnings）；producer A/B、非导入 verifier A/B、read-only before/after 均逐字节一致，network/
forbidden-path/credential/identity-schema hits=`0/0/0/0`，worktree exact-clean。result/verifier/formal-manifest SHA=
`c95b8e0f...742080` / `4acc607c...4d836` / `65f0d2eb...e476de`。

预注册 status=`INCREMENTAL_ARCHIVE_SUPPORT_ABSENT`：该唯一新 `ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS` 事件的匿名
competition 在 prior 126-transaction prefix、新 7-transaction window 与 current 133-transaction registry 中，
accepted archives/physical runs/eligible runs/endpoints 均精确为 **`0/0/0/0`**。这只证明 support gate 非 vacuous、能识别
一个真实 prospective coverage gap；不能称 population-level replication、不能估计 gap 频率、不能建 task whitelist/
blacklist，也不涉及 predictor accuracy、scaling 或 search utility。GPU/API/model fit/base update=`0/0/0/0`。

## 0KS. 2026-09-01 零 fit support v1 在 state promotion 前停止；v2 只修启动回执与进程组清理

0KR 的公开 exact commit=`7d89d1bce13cbf5223b380a167d8868df1cbb6bc` 已冻结。第一次部署在提取 launcher 前因
集群 remote 名是 `fork` 而非本地 `myfork` 以 rc=`128` 停止，action root 尚不存在。fresh deploy v2 的 frozen preflight
通过并启动 WL/receipt，但 v1 launcher 错误要求 immutable WL monitor 从未实现的 `new_snapshot` 日志事件，60 秒后以 rc=`1`
fail-closed；WL/receipt state 仍逐字节停在 494-run `30945550...104f`，没有 COMPLETE 或 receipt，也没有使用 partial output。

失败 trap 只 TERM 了父 Bash，producer 的 `time/strace/python` 三个后代与 receipt 的 sleep 暂时继承锁；独立核验后对精确
PID=`3463566/3463567/3463570` 执行 TERM，receipt sleep 已自然退出。cleanup 后两锁 free、state 不变，v1 partial basename=
`20260901T122214Z_e9e12c639fde`，files=`28`，COMPLETE/FAILURE/producer rc 均 absent；cleanup safe receipt SHA-256=
`45d186e7...18618`。prediction value/outcome/identity/profile 未读。

结果前冻结 `outcome-blind-no-fit-support-renewal-v2`，科学动作不变：仍只有 frozen-bundle WL 与纯 receipt waiter，transition/
config-v2 不重启。唯一执行修正是用 fresh action root，以 matrix 中 exact prior/current/run counts/threshold/commit/resource 字段
作为 WL start receipt，并用两个独立 `setsid` process groups 保证失败时清理全部后代。历史同协议 wall time 为 producer/
independent verifier/chain=`27:10.13/24:33.12/0:01.32`，所以修正 ETA 为 active CPU `45–70` 分钟而非 v1 的 `5–30`；
协议/launcher SHA-256=`0f907e22...57be11` / `a396aa69...54cd7e`，focused contract tests=`7 passed`；
GPU/API/model fit/base update 仍为 `0/0/0/0`。截至该冻结点 v2 尚未执行。

随后从公开 exact commit=`0fb6a7f811be7eb6b7dbea91f4924479d0cdb881` 提取 v2 launcher 并通过 frozen
`check`。正式 start receipt 与不导入 launcher 的 postdeploy 均 PASS：WL/receipt PID=`3476431/3476432`，各自独立
process group 与 lock 精确；fresh WL output basename=`20260901T123808Z_e9e12c639fde` 的 matrix 逐项绑定
prior/current=`30945550...104f/e9e12c63...8a6d`、runs=`494/517`、threshold=`12` 及 resource/effect=`0`。
v1 partial 未复用，transition state/log 逐字节不变，config-v2 count=`0`。launcher/postdeploy safe receipt SHA-256=
`b62d125c...f7b3c` / `0bdc2e1e...25376`；独立 verifier SHA-256=`31404a6b...ff429`。当前只是已验证启动，
WL state 尚未 promotion，预计 `45–70` 分钟完成；receipt 仍须等待另行授权的 transition，不能提前称 common support 完成。

## 0KR. 2026-09-01 517-run support 链落后原因已定位；零 model-fit 续接在行动前冻结

当前 immutable LATEST=`e9e12c63...8a6d` 的聚合库存为 physical/eligible runs/endpoints/structural pairs/tasks=
`543/517/13,581/3,325/38`。transition、WL 与 receipt-support state 都仍停在上一正式
`30945550...104f`（494 eligible runs）；三条旧进程均已退出、锁 free、FAILED/CONTINUITY_GAP 均不存在，日志分别以
`13/10/13` 次自然 `monitor_complete` 结束。因此落后不是 scorer 失败或 batch gate：WL 的 run delta=`23`，已经严格越过
预注册 `minimum_new_runs=12`。config-v2 sidecar filename count 仍为 `0`，内容未打开。

由于 transition exact monitor 每个 snapshot 会进行 producer+independent verifier 合计 `6` 次确定性 HGB refit，而当前没有
新 model-fit 授权，本次结果前只冻结 `outcome-blind-no-fit-support-renewal-v1`：允许从公开 exact commit 启动 frozen-bundle
WL chain 与纯 receipt waiter，各 `72x300s`；transition/config-v2 都不重启。preflight 精确绑定 LATEST、`283` 个 source
archives、五项 inventory、三条 state/log SHA、clean exact worktrees、旧 PID/锁、首个 WL observation 和零 sidecar；任一漂移
fail-closed。协议/launcher SHA-256=`ba9b1fa6...b4beea` / `d28918f5...cdb670`；协议与 launcher 尚未执行；
GPU/API/model fit/base update=`0/0/0/0`，prediction value、outcome、accuracy、
utility、candidate identity/profile 均未读。即使 WL 成功，也只允许主张当前 snapshot 的冻结 WL escrow 结构覆盖，不能提前
声称 transition common-support、accuracy、scaling、utility 或方法效果。

## 0KQ. 2026-09-01 三个等待守护自然耗尽；两份独立续接契约已在重启前冻结

连续 intake PID=`2920968` 已退出；只读诊断证明它正常写完固定 `145` polls，末态为
`PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE ... outcomes_read=false`，不存在 fail-closed tail。control
worktree 仍为 clean exact commit=`b20dd268...2fc0`，monitor SHA-256=`ef658449...8eead`；source/LATEST 仍为
`283/e9e12c63...8a6d`，没有新归档或账本变化。结果前冻结
`outcome-blind-intake-natural-completion-renewal-v1`：只允许对同一 exact monitor 调用一次 `--initialize`，首个新 poll
必须 rc=0，旧日志与完成证据不得覆盖；任一 source/LATEST/hash/PID/clean-worktree 漂移即停止。

Target-522 selection 仍为 PID=`2930562` live、lock held，observed bytes/lines/tail=
`02774632...170f/29/517`，无 COMPLETE/FAILED/TIMEOUT/CONTINUITY_GAP。Stage-A 与 contrast-rank 的第一次 gap-resume
PID=`2931879/2931942` 都在纯等待期间再次自然写出 `TIMEOUT_RC=124` 后退出；两锁 free、无 COMPLETE/FAILED/
INTERRUPTED、两个正式 output root 均不存在，第一份 gap context 仍逐字节等于 `eec0154f...f508`。结果前冻结
`target522-downstream-repeat-timeout-renewal-v1`：只调用两个 installed immutable `source_script.sh resume`，追加独立
second-timeout context，绝不覆盖第一次 context 或恢复旧 within/lineage/selective watchers。

两份协议/脚本 SHA-256 分别为 `0007ea11...032e` / `97d27cae...d5e` 与 `5f1e4151...5f78` /
`5474618d...a77d`；本地与远端 `bash -n`、两份 `check` preflight 均 PASS。截至本段只有结果前冻结与只读检查，
尚未重启任何进程；outcome/prediction/accuracy/utility/candidate profile/private identity 均未读，GPU/API/model fit/
base update=`0/0/0/0`。

随后从公开 exact commit=`b00eeea7aa993a13bf3f6cce0b7a7bcda84fcf3c` 提取两份脚本，重新通过 exact-commit
preflight 后执行。Stage-A/contrast-rank 已续接为 PID=`3451204/3451299`，两锁 held，分别继续等待 selection 与
Stage-A COMPLETE；selection bytes/PID/lock 仍为 `02774632...170f/2930562/held`，正式 output roots 仍不存在。
intake 已续接为 PID=`3451688`，首个新 poll rc=`0`，source/LATEST 仍为 `283/e9e12c63...8a6d`。不导入续接脚本的
独立 postdeploy verifier=`PASS`；intake safe receipt / 两份 second-timeout context SHA-256=
`c5b4c8ec...ba52` / `9e305ace...425e`，verifier SHA-256=`bf3a74c6...d8c8`。prospective values、候选
profile/private identity 仍未读，GPU/API/model fit/base update=`0/0/0/0`。

## 0KP. 2026-09-01 Target-522 七步缺口正式通过：494→517，未错过首次 crossing

`target522-selection-gap-recovery-v1` 的 exact-commit formal 已完成。第一次 formal v1 的 8 项 focused 与 1,901 项
full tests 均通过，但部署 harness 预建 producer 输出目录，触发 no-overwrite producer 的正确拒绝（rc=1）；该次已经完成
结构分析但未发出 formal result，失败根原样保留。只修正 harness、不改提交/协议/producer/verifier 的 fresh v2 再次通过
focused/full=`8/1,901`（48 warnings），producer A/B、独立 verifier A/B、manifest、只读、trace/network/credential 门均通过。

七个按 intake 顺序固定的 successor 把 observed structural count 从 494 单调推进至 **517/522**，每一步均严格小于 522，
remaining=`5`；因此可以排除旧六小时 watcher 在缺口中跳过首次 crossing。formal manifest / summary / independent
verification SHA-256=`9c0f96eb...64c0` / `db980217...6812` / `ef801e5d...3e3b`，恢复后 ledger 预期
SHA-256=`02774632...170f`。outcome/prediction/accuracy/utility/candidate profile/private identity 均未读，registry/run
payload 只做 hash，GPU/API/model fit/base update=`0/0/0/0`。

在修改旧 ledger 前又冻结独立 `target522-selection-gap-resume-v1`：只允许在旧 ledger
SHA/lines/tail=`0e444525...8c47/22/494`、当前 LATEST=`e9e12c63...8a6d`、formal 根完整且只读、monitor 锁空闲及
所有候选/失败标记仍为空时，把 exact extension（SHA-256=`d998e8a3...8da9`）在同目录临时文件验证为
29 lines / 517 runs / `02774632...170f` 后原子替换，再调用旧根保存的 exact source script `resume`。协议 / safe receipt /
resume script SHA-256=`81f04069...22d4` / `078a0c8b...ca71` / `6e91660d...a7f8`。该结果前状态由公开
commit=`b407182e8d61ac31cbae0212c0864d491c735b7a` 固定。

同一提交的 fresh nosmudge worktree 通过 script/JSON/hash/security、focused=`8 passed` 后执行原子追加；旧 ledger 精确成为
29 lines / 517 runs / SHA-256=`02774632...170f`。旧 exact source script 的 `resume` 已上线为 PID=`2930562`，独立
postdeploy 证明 cmdline、锁、TIMEOUT 删除、无 FAILED/CONTINUITY_GAP，仍差 5 runs。当前优先下游 Stage-A 与只读
contrast-rank watcher 也只按各自旧 exact source/commit 从自然 TIMEOUT 恢复为 PID=`2931879/2931942`，三把锁均 held；
它们在 selection/Stage-A COMPLETE 前只读 marker existence。postdeploy safe receipt 已逐项固定，prospective values、候选
profile/private identity 仍未读；receipt SHA-256=`e06e1e70...64ea`。更早 within/lineage/selective watcher 的旧
`FAILED_RC` 未删除，也未擅自恢复；其恢复需另立
upstream-timeout amendment，不能混入本次 Stage-A/rank 续接。

## 0KO. 2026-09-01 Target-522 超时缺口恢复已在读取七个 successor counts 前冻结

原 Target-522 first-crossing watcher 正常耗尽固定轮数时仍停在 LATEST=`30945550...104f`、494 runs，candidate/READY/
COMPLETE/FAILED/CONTINUITY_GAP 均不存在，只写 `TIMEOUT_RC=124`。当前 LATEST 已推进至 `e9e12c63...8a6d`；直接
`resume` 会违反原协议的 changed-LATEST continuity 门，不能为了继续守候而删除缺口证据。

在读取七个缺口 snapshots 的 first-960 run counts 前，冻结 `target522-selection-gap-recovery-v1`：旧 observed ledger
SHA-256/lines=`0e444525...8c47/22`，最后观察固定为 494 runs；successor 只能是 intake log 中按提交顺序出现的七个 exact
SHA，且每个 summary/registry/run-ledger hash 已单独固定。producer A/B 与不导入 producer 的 verifier A/B 必须证明旧 ledger
是 exact prefix、七步计数单调、final=当前 LATEST、security fields 全关闭，并且 **七个 counts 全部严格小于 522**；任一
successor 已达到 522 就说明可能跳过首次 crossing，恢复必须 KILL。registry/run payload 只做字节 hash，不解析身份。

协议/producer/verifier/test SHA-256=`e86b29e6...b29f` / `e5933a6f...923d` / `327605a3...a30b` /
`e5e7793a...7512`，本地 focused=`8 passed`。当前只有结果前冻结实现，尚未读取七个 counts、未追加 observed ledger、未删除
TIMEOUT、未重启 selection 或下游 watcher；远端 exact-commit full tests、双 A/B、independent verifier、trace/security 与
append-only postflight 全过后才允许恢复。outcome/prediction/accuracy/utility/candidate profile/private identity 均未读，
GPU/API/model fit/base update=`0/0/0/0`。

## 0KN. 2026-09-01 八归档已全部结算；Target-300 attempt 2 推进至 242/300

学长 source 从 275 增至 283 个 archives；冻结的 6 小时/三观察稳定门通过后，append-only intake 顺序提交前 4 个并
形成新 LATEST。随后唯一下一 archive 在 `phase1.prospective_drop_intake` 以 `drop produced no physical runs` 停止，
monitor poll=14、rc=1；失败 attempt 原样保留，未跳过、未重试、未换候选。私有 intake log bytes/SHA-256=
`1756` / `966e7e67...f6001`，credential-shape hit=`0`。Target-300 ordered chain 与该 intake 故障隔离，仍按最后成功
LATEST 的稳定计数继续；这不是 outcome、accuracy、utility 或方法效果结果。

在读取 raw archive 结构计数前冻结 `prospective_no_checkpoint_rejection_amendment_20260901_v1`：候选只能来自上述唯一
失败 attempt；producer A/B 与不导入 producer 的 verifier A/B 必须分别逐字节一致，并同时证明 discovered roots>0、
checkpoint runs=0、live-only roots=all roots、credential-shaped member names=0，且 verifier 读取 journal bytes=0。
只有全部通过才允许生成相邻 immutable rejection registry、给 monitor 增加一个 extra registry、跑 focused/full tests 并
启动 fresh instance；否则保持 fail-closed。失败 attempt 不删除，已有 4 个 transactions 必须保持 exact prefix。
诊断 producer / verifier / registry builder SHA-256=`b74c6dc9...b876e` / `56b60bbf...cd19` /
`338c979c...e10c`；GPU/API/model fit/base update=`0/0/0/0`，label/outcome/prediction/accuracy/utility 均未读。

正式诊断 v1 在任何 producer 前因 Git LFS 缺失历史对象停止；fresh nosmudge v2 已生成 producer/verifier/registry 双份
文件，但 safe summary 前的 trace 扫描把 Python 标准库 `token.py` / `tokenize.py` / `secrets.py` 误判为敏感路径而停止。
在读取 archive-audit aggregate 前冻结 trace addendum v2：不重跑三类产物，只允许上述六个 exact basename（含对应
`.pyc`），其余 `label_vault/prediction/accuracy/utility/.env/api_key` 与非白名单 token/secret 路径仍必须为 0；
任一 A/B、hash、failure binding 或 trace 不符均不生成可部署 registry。v1/v2 失败根均保留。

addendum 后的正式 finalizer 已通过：同一唯一失败 archive 含 2 个 discovered physical run roots，二者均只有 live-event、
checkpoint journals=`0`，故 2/2 被归为 live-only 并按既有 `ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS` taxonomy 拒绝；
credential-shaped member names=`0`，独立 verifier 读取 journal bytes=`0`，outcomes/identities 均未读。producer/verifier/registry
A/B 均逐字节一致，safe-summary/diagnostic/verification/registry SHA-256=`0819fdbe...df10` / `b9259872...a06` /
`9b1b715c...98a0` / `0c138eb6...ffe`。registry 接入后的远端恢复保留了全部失败证据：v1 在测试前因 zero-hit grep rc
语义停止；v2 的同一 full suite 在新 synthetic GBM 单测处出现约 30 线程过度并行，超过既有 2–4 分钟基线后被中止；
v3 只固定 BLAS/OpenMP thread ceiling=`1`，同一提交与同一测试集合通过 focused/full=`23/1,893`（48 warnings，
98.74s）。monitor 随后启动为 PID=`2920968`；wrapper 只在启动后的 Bash PID 正则写法处停止，v4 因而不重启，独立核验
PID/cmdline、clean worktree、script/registry hash 与首个 poll。postdeploy=`PASS`，monitor script/postdeploy receipt SHA-256=
`ef658449...8eead` / `3a2e38d3...381e`；首个恢复 poll 已提交 1 个新 transaction，LATEST=`63037694...eeae`。
两次运行层失败都在 outcome-blind 边界内，未改变 source 顺序、已有 transaction exact prefix 或 scientific commit。
恢复 monitor 随后按唯一时间顺序再提交 2 个 transaction；因此 source 的 8 个新增 archives 已全部结算为 7 个
transaction + 1 个冻结结构拒绝。最终结构状态为 archives/baseline/ready/rejected/transactions=`283/128/0/22/133`，
LATEST=`e9e12c63...8a6d`；PID/cmdline/clean worktree 持续通过。该结算只证明 append-only intake 完整，不是方法效果。

与此同时，Target-300 ordered chain 在最后成功 LATEST 上独立完成 attempt 1：formal/verifier 状态为
`FUTURE_COHORT_COLLECTING` / `PASS_COLLECTING_TRUTH_UNREAD`，exact 219-run prefix 完整保留并推进至 235 runs /
73 archives / 33 tasks，remaining=`65`、boundary absent；相对上一正式点为 `+16/+4/+2`。summary/verification/safe-receipt
SHA-256=`ebf8426a...908` / `2e5f0d69...96f1c` / `d9deb91b...df7f`。continuous monitor PID=`2206791`、lock held，
已转入 attempt 2 等待下一个不同且稳定的 LATEST。该进展只证明冻结人口按序增长，不是 predictor、scaling 或 search-utility
正结果；GPU/API/model fit/base update=`0/0/0/0`。

最终 LATEST 达到 `5×300s` 后，ordered chain 自动执行 attempt 2；formal rc=`0`、exact 235-run prefix 完整保留，状态仍为
`FUTURE_COHORT_COLLECTING` / `PASS_COLLECTING_TRUTH_UNREAD`，当前为 242 runs / 76 archives / 35 tasks，remaining=`58`、
boundary absent；相对 attempt 1 为 `+7/+3/+2`。summary/verification/safe-receipt SHA-256=`7b416089...c3aac` /
`94ad8859...d73b` / `9e2218c2...f1dd`。chain 已推进至 attempt 3 继续等待后续新 LATEST；未读取 outcomes/identities，
GPU/API/model fit/base update=`0/0/0/0`。

## 0KM. 2026-08-31 219-run 后续接已冻结为 ordered continuous chain

为消除 one-shot formal collecting 后 monitor 退出造成的人工延迟与 snapshot 选择空间，冻结
`target300_continuous_schema_v2_continuation_v1`：从 0KL 的 219 runs / 69 archives formal exact prefix 开始，
只处理不同于上一个 formal candidate 的第一个 `5×300s` 稳定 LATEST；调用者不能传、跳过或替换 snapshot。

每次 formal collecting 成功后，该结果自动成为下一轮 previous exact prefix；任一 formal/hash/A-B/verifier/trace/security/read-only
失败则整条链停止，失败 candidate 不重试。closed 时必须写 one-time anchor 后停止。protocol/monitor/deployer SHA-256=
`8a499b62...fa6a23` / `11119500...7a599d` / `3d67dd07...81760bb`，6 项契约测试覆盖顺序、prefix、失败与资源门。
固定 science commit 仍为 `4a68c83...6104`；单线程 CPU，GPU/API/model fit/base update=0。safe monitor 不输出/读取
candidate identity/profile/private selection 或 truth/outcome/prediction/accuracy/utility，闭合也不自动授权后续 effect。

## 0KL. 2026-08-31 Target-300 schema v2 正式通过，当前为 219/300 collecting

v2 在 v1 自动冻结的同一 `30945550...104f` candidate 上一次运行成功，未重试 v1、未换 snapshot。远端正式门为
14 focused + 1,877 full tests，producer A/B 与独立 verifier A/B 均逐字节一致；manifest/read-only、forbidden-open、
filename/content secret scans 全通过。summary/verifier/formal-manifest SHA-256=`6a9301af...42428` /
`5d3dec87...d785a` / `f0544657...fcbdc`。

白名单独立复验状态为 `FUTURE_COHORT_COLLECTING` / `PASS_COLLECTING_TRUTH_UNREAD`：219 physical runs / 69 archives /
31 tasks，remaining=81，boundary/anchor 均不存在。83 个 observed future archives 已全部 settled：69 accepted、14 structural
rejections，pending head 不存在；所以当前缺口是后续新增语料，不是 unresolved intake。相对 `98f2` 的 193-run / 60-archive
前缀新增 26 runs / 9 archives / 1 task，且 previous exact prefix 完整保留。

这正式验证了 schema amendment 与 append-only cohort 管线，但 target 尚未闭合，只能称结构进度；不构成 predictor accuracy、
scaling、search utility 或 method-effect 正结果，也不授权 truth-support/replay/effect/GPU/API/model fit。安全收据为
`target300_schema_v2_safe_receipt_20260831.json`；未读取 candidate identity/profile/private selection 或任何结果值。

## 0KK. 2026-08-31 Target-300 v1 因前向 schema 漂移 fail-closed；v2 修正已在结果前冻结

0KJ 的 monitor 在 `30945550...104f` 连续 `5×300s` 稳定后按协议触发。12 focused tests 与 965 full tests 通过，
但 producer A 在任何 verifier/anchor/scientific readout 前以 rc=2 退出；v1 不得重试。key-only 审计确认根因不是数据损坏：
126 个 provenance 文件共 520 行，495 行是原 12-key schema，25 行保留全部旧字段并只增加正式 intake fallback 引入的
`competition_id_source`；缺旧字段与其他额外字段均为 0。未读取或输出候选身份/profile/private selection，也未读取
truth/outcome/prediction/accuracy/utility。失败 safe receipt SHA-256=`aef8d5a8...5da42`。

结果前冻结 `target300_provenance_schema_amendment_v2`（SHA-256=`ef6de30a...6df1`）：candidate 仍是 v1 自动固定的同一
`30945550...104f`，previous 仍是 193 runs / 60 archives exact prefix，不允许换 snapshot。唯一修正是 producer 与独立 verifier
接受原 required keys，或 required keys 加唯一可选字段 `competition_id_source`；字段存在时只允许
`explicit_journal` / `archive_consensus_fallback`，且不进入 cohort identity rows。任意其他 extra、missing 或非法值仍 fail-closed。
archive 时间序、run 去重、eligibility、target/boundary 与盲性均不变。

v2 实现/运行前必须补 mixed-schema 正例及 producer/verifier 非法值反例，再过 focused/full tests、A/B、独立 verifier、
trace/security、clean worktree 门。v2 失败也不得重试。该技术修正只授权同一冻结 candidate 的 CPU 结构闭合；即使成功也不授权
truth-support、replay/effect、GPU、API 或模型训练，且不构成 predictor accuracy/scaling/search utility 结论。

结果前最小实现已完成：producer/verifier 只把 strict equality 改为 `required <= keys <= required|{competition_id_source}`，
并各自验证固定二值 enum；cohort output schema 不含新字段。mixed legacy/new 正例、producer/verifier 非法值反例及部署静态门合计
24/24 通过。producer/verifier/wrapper/deployer SHA-256=`0273b1e1...1d25f` / `4ed03a0f...5622e` /
`16747430...761c5` / `08fe5351...99306`；运行时只对旧 formal runner 增加唯一 worktree 后缀与固定 candidate 断言，
patched runner SHA-256=`0f50c1dc...edbff`。本地 full suite 因未安装 scipy/sklearn 在 collection 前停止，不计科学失败；
远端正式 venv 的 full suite 是 producer 启动前硬门，任何失败均不产生 cohort 或 anchor。

## 0KJ. 2026-08-31 Target-300 已从 `98f2` 的 193-run 前缀冻结结果盲续接

原 quiescent monitor 在 `98f2` 正式确认 `193 runs / 60 archives / 30 tasks / remaining 107` 后自然退出；当前
LATEST 已为 `30945550...104f`、first-960 公共结构总量为 494 runs，但尚未读取当前 successor 的 Target-300 selected
runs、boundary overshoot、candidate profile/private selection。为避免延迟续接变成人工挑 snapshot，新增
`target300_continuation_after_98f2_v1`：部署后只接受第一个观察到的非 `98f2` LATEST，连续 `5×300s` 稳定后自动调用
原 fixed runner；调用者不能传 snapshot，变化重置，formal 失败不得换候选或重试。

续接精确绑定 science commit=`ab59a011d945e4a96daf7dbbbc927a59027da077`、原 protocol/runner SHA-256=
`54187f38...377d` / `c6f6ed7a...660e`，以及 previous manifest/summary/verification=`81831f68...cb2e` /
`01d67cec...8b42` / `59624c59...ee12`。fixed runner 必须把 193 runs/60 archives 逐行保留为 exact prefix，再按既有
时间序达到 target=300 并保留完整 boundary archive overshoot。continuation protocol/monitor SHA-256=
`3a902779...70f97` / `e35ea6e2...1be7b`。producer/verifier 双 A/B、focused/full tests、trace/security、clean worktree
门保持不变；CPU-only，GPU/API/model fit/base update=`0/0/0/0`。

当前只有结果前冻结协议，尚无 successor Target-300 scientific result。第一次闭合仍只能写 fixed one-time anchor；后续只读
status、totals、hash 与 blindness receipt，不得读取 candidate identity/profile/private selection 或 truth/outcome/prediction/
accuracy/utility。闭合不自动授权 truth-support、replay、effect、GPU 或付费 API；Target-300 与 first-960 estimand 继续分离。

## 0KI. 2026-08-31 archive-granularity retention audit 强门正式通过

为把 0KH 的“6/6 结构拒绝 competition 也有 accepted archive”从定性结论变成 corpus utility 数量级，新增
`archive_granularity_retention_audit_v1`。它比较两个明示策略：archive-granular validation 只丢结构无效 archive；
task-level blacklist 则丢掉 affected competition 下全部 accepted archives。主 estimand 是后者会额外丢失的 eligible
runs/endpoints 占当前 accepted corpus 的 exact share；这是冻结 corpus 的确定性 accounting，不是线上方法因果效果。

冻结时只知道 prior aggregate structural competitions/mixed=`6/6`，未读/未输出 task identity，也未读取 retained
archive/physical-run/eligible-run/endpoint 数或 dominance。强门预先固定为：6 个 affected tasks 全部有 eligible support，
retained eligible-run 与 endpoint share 均≥10%，两项 dominant-task share 均≤70%；partial 为 tasks≥4、shares≥5%、
dominance≤85%，其余 kill。alias quarantine 明确排除。输入绑定同一 LATEST=`30945550...104f`、frozen observations=
`dccd59d9...e855` 及 0KH result/verification hashes。

exact scientific commit=`bc88298cb410183cf642c132c5d1df2e2d9497ba` 的正式结果为
`ARCHIVE_GRANULARITY_RETENTION_STRONG`：6/6 affected competitions 都有 eligible support；archive-granular validation
保留了 task blacklist 会额外丢掉的 accepted archives/physical runs/eligible runs/endpoints=`20/94/92/2,558`。
eligible-run 与 endpoint share=`18.6235%/19.5297%`，dominant-task share=`31.5217%/36.9038%`，均以充分余量
通过冻结强门。affected-task 匿名 run min/median/max=`4/17/29`，endpoint=`50/458.5/944`，结果不由单任务主导。

producer A/B 与不导入 producer 的 verifier A/B 逐字节一致；focused/full=`10/1860 passed`（48 warnings），独立
postflight PASS，network/forbidden/credential/identity hits=`0/0/0/0`。result/verification/manifest=`f28ef794...9a2184` /
`4965c047...d3b187` / `5a5f5168...957823`。允许主张：当前冻结语料若因一个结构无效 archive 而 blacklist 整个
task，会额外丢掉约五分之一的有效 accepted support，因此 archive-level fail-closed validation 有明确 corpus utility。
但这是确定性 counterfactual accounting，不是观察到的方法效果；不支持 predictor accuracy、scaling、search utility、
task whitelist/blacklist 或未来 stationarity。affected identity、archive payload、label、outcome、prediction value、accuracy、
utility 均未读取/输出，GPU/API/model fit/base update=`0/0/0/0`。机器件见
`phase1/results/archive_granularity_retention_v1_20260831_bc88298/`。

## 0KH. 2026-08-31 archive disposition taxonomy-aware 纵向审计强门通过

旧 v1 在结果写出前因 `unknown rejection reason` fail-closed：它漏列了 8 个早已单独预注册并逐字节验证的 byte-alias
quarantine，同时错误要求 accepted 与 alias 的 payload hash 互异。v1 永久保留为
`ARCHIVE_DISPOSITION_REPLICATION_INTEGRITY_FAIL`；没有 result、未启动 verifier、未计算结构 competition overlap。

在 taxonomy-only 诊断后、任何结构 overlap readout 前冻结 v2，将当前 21 个 rejected archives 精确分成 structural=`13`
与 aliases=`8`。exact commit=`43ce72a94dc70a4bdff07c9b5494176ff1926f15` 在 fresh root 通过 focused/full=
`16/1848 passed`（48 warnings），producer A/B 与独立 verifier A/B 逐字节一致，独立 postflight PASS。

冻结强门正式通过：current structural rejected competitions=`6`，其中 accepted-overlap=`6/6=1.0`，Wilson 95% CI=
`[0.6096657121,1.0]`；overall extension settled=`57>=50`。hash taxonomy 同时精确通过：accepted unique=`126`，
structural unique=`13` 且 overlap accepted=`0`，alias unique=`8` 且 overlap accepted=`8`，aliases 未进入结构 estimand。
result/verification/manifest=`58539382...c104e` / `854f81e5...21ab4f` / `f5440d4d...65b7b`；
network/forbidden/credential/identity hits=`0/0/0/0`。

这是正面的 benchmark-audit / corpus-validity 结果：语料扩张后，结构拒绝仍不是 task blacklist，且生产账本可把结构无效
archive 与 byte aliases 可复验地分层。但新增目标结构拒绝只有 `1`（accepted/structural/alias extension=`48/1/8`），
所以论文措辞必须是 **longitudinal persistence**，不得称一批独立新结构拒绝上的 replication。它不支持 predictor accuracy、
模型 scaling、search utility、metadata 修复因果效果或拒绝率稳定；archive payload、label、outcome、prediction value、
accuracy、utility 均未读取，GPU/API/model fit/base update=`0/0/0/0`。机器件见
`phase1/results/archive_disposition_longitudinal_replication_v2_20260831_43ce72a/`。

## 0KG. 2026-08-31 0829 语料摄取已排空；494-run 双 escrow 公共结构支持正式认证

senior source 与 intake 现均为 275 个 archives；baseline/transactions/rejected/ready=`128/126/21/0`。
其中一个 archive 的 8 个 discovered run roots 全部只有 live state、checkpoint journals=`0`，因此按
`ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS` 整包结构拒绝。该拒绝先在 exact pre-change commit=`eff8970...`
完成不变性 A/B、独立诊断及 focused/full=`29/1835 passed`，再以 commit=
`b81dd3bfb34a18e85875680fa849884a3d6fae4e` 部署；diagnostic/registry SHA-256=
`094fe135...f4a` / `e77654a7...2093`。它是 append-only intake 的合法结构拒绝，不是数据丢失或科学负结果。

队列排空后的不可变 LATEST=`30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f`，
transactions=`126`；physical/eligible first-960 runs/endpoints/structural pairs/tasks=
`520/494/13,098/3,230/34`，closure 尚未提供。continuous snapshot-delta chain 的 exact control commit=
`2e59423736747f7d806d50a69fd1f312d4927c48`；final manifest=
`88188e3b983e13ce1efc21dd3f7b3a1c9f65f11827d0e6d5d4b2c6104a267f07`，primary A/B 与不导入
production 的 grounded A/B、完整 payload/hash、trace/security 和只读门均 PASS。

transition chain 在 control/scorer commits=`bc362dfe...6ee0` / `7458f096...748e` 上提升到同一 LATEST；
selected/added/removed runs=`494/20/0`，与前态 common pairs=`3,152`。artifact summary=
`9826529f...3c7`，额外 postflight manifest=`dc2647e3...3d8`。WL chain 在 control/scorer commits=
`c8e6775d...93e7` / `031edb34...fb1c` 上恰好跨过预注册 `minimum_new_runs=12` 批门；
selected/added/removed=`494/12/0`、与前态 common pairs=`3,163`，artifact summary=`e33edc1e...83db`。

当 `WL=transition=LATEST` 连续三次稳定后，receipt-support exact commit=
`9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f` 完成 builder A/B 与不导入 builder 的 verifier A/B，
两组均逐字节一致；receipt SHA-256=`6f281979732c3171d99bef59ad7064934f053ab185dec92c498185f7549e4f9e`。
独立 postflight 再验 manifest、四个 rc、trace/security、symlink 与只读门，认证当前两个 escrow 的 exact
canonical common support=`3,230 structural pairs`；postflight manifest=`fc581b06...f3bed`。

允许主张：我们已有可逐快照复验、能在真实 schema/code epoch 与无 journal 归档上 fail-closed，并能对两个冻结
prediction escrow 给出 exact common-support certificate 的正面 benchmark-audit 资产。禁止将其解释为 critic
accuracy、模型 scaling、search utility 或方法效果提升；first-960 仍未 closure，prediction pair files/values、label、
outcome、accuracy、utility、candidate identity 均未读取，GPU/API/model fit/base update=`0/0/0/0`。机器回执见
`phase1/results/prospective_final_support_30945550_20260831/`。

## 0KF. 2026-08-31 score 双层 code epoch 迁移正式通过；新归档已进入不可变 LATEST

第二个 0828 archive 的共识回填本身已通过，但第一次生产重试在重放历史 score registry 时 fail-closed：旧 118 个
top-level score summary 全部来自 exact commit=`90842c4...`/source=`f7fc2aa...`，其中 117 个 nested scorer 全部来自
同一 commit/source=`678ecb2...`，另 1 个是无 eligible endpoint、因而没有 nested score。此前修复只迁移了 intake schema，
没有迁移这两个 score code identity 层。只读 summary 元数据审计 receipt SHA-256=
`9688d3544268a84d4b7073fcba1d470ab74a330c57b4f99d2a65a04c81840102`；没有打开 blind-score CSV、label vault，
也没有读取 outcome/prediction value/accuracy/utility 或输出 candidate identity。

结果前冻结的修复只允许两个完整 epoch：上述唯一 legacy top+nested tuple，或 fresh exact commit 的 current
top+nested tuple；top/nested 混搭、部分 tuple、未知 SHA 或 caller-supplied identity 全部 fail-closed。另有不导入
production pipeline 的独立 verifier。v1 exact commit=`d414676...` 通过 focused=`72 passed`，但 full suite 在 producer
启动前因远端默认 umask 令一个隐私测试的 synthetic tempfile 成为 `0644` 而停止（`1813 passed / 1 failed`）；失败根
manifest=`87bd5f0e...fdb60ec` 已只读封存，无 intake/score/registry 科学输出。v2 唯一执行改动是结果前固定
`umask 0077`，科学协议、输入、身份白名单、测试范围与解释均不变。

v2 exact scientific commit=`5ed1988045a3fd8c365d001c87977314572383d9` 在 fresh root `formal-5ed1988-v2`
通过 focused/full=`72/1814 passed`（48 warnings）；intake、archive verifier、blind score、119-transaction registry、
独立 epoch verifier、accumulator 六层 A/B 全部逐字节一致。formal manifest SHA-256=
`06a877e2fe3e9ee34122cb3f7f3fe9b112e0124fdd74a7f1fcc56e556700f65f`；legacy/current top counts=`118/1`，
nested=`117/1`，无 nested=`1`。control commit=`c8e6775d11d20d5008add11763b93e7d6c99362d` 已部署，deployment manifest=
`108c01fac59fc8e00b84bad5f1cd9104220dfad7c66ab9c3a3f7f5f9b72896fb`。

新不可变 LATEST=`0c0584b87140d9a3242f2aa59920829e07e9178749880e3c1f3bd0d065e0b07a`，transactions=`119`；
all physical/eligible runs/endpoints/structural pairs/tasks=`499/473/12,680/3,151/34`。相对上一 LATEST，新增
`4 eligible runs / 144 endpoints / 7 structural pairs / 0 tasks`。snapshot 全 manifest、formal、deployment 与 recovery
均独立 postflight PASS；label vault opened=`false`，outcome/prediction value/accuracy/utility read=`false`，
GPU/API/model fit/base update=`0/0/0/0`。transition snapshot chain 已完成并独立复核：selected/added/removed runs=
`473/4/0`、common pairs=`3,144`、outcomes/effect metrics=`false/0`。WL 相对上次正式 468-run state 仅
`delta=5<12` 而按预注册批门 deferred，并已续挂 outcome-blind monitor；Target-522 只观察到 473-run 结构、candidate=none。

允许主张：append-only 语料在遇到真实 schema/code-epoch 漂移时可 fail-closed、独立复验并无损恢复，且新数据已安全增长。
禁止把本节解释成 critic 精度、scaling、search utility 或方法效果正结果。

在此基础上，新增了不导入 production runner 的通用 snapshot-delta verifier，用于证明任意两个不可变生产
snapshot 之间的 append-only lineage，而不输出 archive/drop/run/endpoint/pair/candidate identity。第一次 formal
在 focused/full=`34/1819 passed` 后因独立实现错误地使用 compact JSON separators 而在第一个真实 projection 门
fail-closed，未生成 receipt；失败根 manifest=`ff5a27a190443f01d9cdb91f69286ec321b8ce125169d1eec9402758b50e2d8b`。
修复只令独立重建与已冻结 production canonical JSONL 的标准 separators 一致，并新增与 production bytes 的精确
兼容测试；随后一次 checkout 前失败源于远端尚未 fetch 新 commit，producer/tests 均未启动，失败根 manifest=
`2255a2fb50f02ab7aa6d1bd7c02b7d3e53e4aeefa001f7282b1aaab64a0c4697`。两者均只读封存且未复用目录。

最终 exact commit=`734a2b14bc20e97c95421c8faaf26b1109c329e5`、fresh root=`formal-734a2b1-v3` 通过
focused/full=`36/1821 passed`（48 warnings），producer A/B 与不导入 production 的 grounded verifier A/B 均逐字节
一致；grounded verifier 自行复验每个 manifest payload，并从 transactions 重建 intake/score projections。formal
manifest=`69149e510d0bc519363dc48b57e578a3933757ae500e8e830ab60ff849d0bba0`。它确认
`813f3c1c...2b54d -> 0c0584b8...b07a` 为 exact append：transactions=`118->119`，inventory
`495/469/12,536/3,144/34 -> 499/473/12,680/3,151/34`，增量=`4/4/144/7/0`；独立 postflight
再次通过 manifest、只读、trace/security 与 clean-worktree 门，network/forbidden/credential hits=`0/0/0`。
这是数据版本 lineage/auditability 的正面基础设施结果，不是 predictor 精度或 search utility 结果。

同次 outcome-blind 状态核验：senior source/ledger archives=`267/267`，baseline/committed/rejected/pending/ready=
`128/119/20/0/0`，故当前没有漏处理的新 archive；transition 已与 LATEST 对齐，WL 仍为 468 runs，距离 LATEST
473 仅 `5<12`，按冻结 batch 门等待，receipt-support 也因此等待；Target-522 还差 49 runs。所有八个相关 monitor
均存活；没有读取 label/outcome/prediction value/accuracy/utility，GPU/API/model fit/base update=`0/0/0/0`。

一次性 delta receipt 随后被升级为独立 continuous chain，固定 exact commit=
`2e59423736747f7d806d50a69fd1f312d4927c48`、seed=`0c0584b8...b07a`、默认 `96 polls x 300s=8h`。
每次 LATEST 变化必须 primary A/B 与不导入 primary/production 的 grounded A/B 全部逐字节一致；两者都复验完整
payload manifest 并独立重建 registry projections，任何失败不得推进唯一 state。primary 另新增 output/input overlap 与重复
manifest path 拒绝门，grounded 拒绝 candidate hash、内容、额外字段、runner count 与 projection 漂移。

第一次 activation 在 focused=`50 passed` 后，full suite 因 formal runner 声明但未实际导出 BLAS 单线程上限而达到约
`2,948% CPU`；在 15% 主动终止精确 pytest process group，receipt/monitor/state promotion=`0/0/0`，失败根只读
manifest=`1352c528368f70eff55a6e4ba8dfde809373785c21de4922efb4553af34c88f3`。v2 唯一执行变化是导出并逐项断言
六个 thread caps=`1`，实测 pytest 约 79% CPU。fresh activation 通过 focused/full=`50/1835 passed`（48 warnings）、
真实 primary/grounded 双 A/B 和 seed no-change smoke；activation manifest=
`0b41b37e11355d5907ef0dac75913f7940d122def141d667f68e4d7db4b8fe6a`。部署 manifest=
`30525bb7d78af6f2b76e9dee83368413efe57b853988476a92f1bacc67bca3c0`，postflight 时 PID=`1599587` live、
lock held、state=LATEST、artifact count=0。该链是数据版本 lineage/auditability 的持续正面基础设施，不是 predictor/scaling/
search-utility 方法效果；GPU/API/model fit/base update=`0/0/0/0`。

## 0KE. 2026-08-31 新归档 intake 在第二个 uncommitted archive fail-closed；共识回填规则已在 stem-match 前冻结

267 个归档中的第一个新 archive 已形成 LATEST=`813f3c1c...2b54d`，first-960=`469 runs / 12,536 endpoints /
3,144 structural pairs / 34 tasks`；transition 已处理，WL 因仅 `delta_runs=1<12` 正确 deferred。随后第二个 archive
在 `prospective_drop_intake` 以 `journal must identify exactly one competition` 退出，intake monitor fail-closed，未提交该
archive。credential-first 聚合诊断只读 4 个 checkpoint journals：2 个有一个 ID、2 个没有 ID、0 个有多个 ID；全归档 exact/
normalized distinct 均为 1，所有 root ID 缺失；没有输出名称、节点、代码或 label/outcome/prediction 值，也未打开 env/key 成员。

在读取 archive stem-match 布尔值前，已冻结 `prospective-intake-archive-consensus-fallback-v1`：仅当每 journal ID 数∈{0,1}、
全归档 exact/normalized union 均唯一、至少一个显式 ID、且唯一 normalized ID 与去掉 `-Nseeds` 的 archive stem 完全一致时，
才允许 0-ID journal 继承；显式 ID 不改，任一歧义继续失败。协议 SHA-256=
`3110da4403fa0477454d8e1415fd23e9a7a7482694b778784c9d5270b8e4993e`；GPU/API/model fit/base update=
`0/0/0/0`。现有 469-run snapshot 不变，任何修复只能 fresh exact commit + A/B + independent verifier 后重试该 uncommitted archive。

## 0KD. 2026-08-30 FOREAGENT LOEO v5 正式完成：不支持单模型去噪提升，支持图修正后的模型比较稳健性

exact commit=`942957757fd0c8464b1670ab3e35da64f4cccebf` 在 fresh root `formal-9429577-v5` 完成。
preflight/focused/full=`13/16/1789 passed`、48 warnings；producer A/B 与 opposite-orientation grounded verifier A/B
各自逐字节一致，45 个独立数值字段最大差=`0.0`；result/verification/manifest SHA-256=
`b00ab6b7...1e96b` / `a6912890...c524` / `a3453efa...3eee0`。独立 postflight 再验全部哈希、trace/security 与
只读树均 PASS，forbidden/network/credential/writable hits 全为 0。

预注册分类=`NO_DENOISING_GAIN_MODEL_COMPARISON_REMAINS_STABLE`。DeepSeek/GPT LOEO pair coverage=
`0.9914585714/0.9927098634`；hybrid−raw task-macro=`+0.0034202548/-0.0014593090`，task CI=
`[-0.0043703960,0.0099193214]` / `[-0.0103567258,0.0067942615]`，故不能称单模型去噪提升。正支持项是
DeepSeek−GPT：raw task-macro delta=`0.0259935224`，CI=`[-0.0002093901,0.0570976139]`；hybrid delta=
`0.0308730863`，CI=`[0.0067339847,0.0593877218]`，26/26 LOTO 正号。允许定位为 Predictor Benchmark 的
graph-aware robustness baseline；禁止称算法首创、通用 judge accuracy gain 或 prospective critic/search utility。
prospective/confidence read=`false/false`，GPU/API/model fit/base update=`0/0/0/0`。详见正式报告与机器回执。

## 0KC. 2026-08-30 FOREAGENT LOEO v4 完成 A/B+独立复验后被零命中计数器误杀；v5 只修 pipefail

exact commit=`7ad86cd312dde2c40c8b0842af1f6a6ca732f71c` 的第四次 formal 通过 focused/full=
`14/1787 passed`、48 warnings，producer A/B 与 verifier A/B 都完成且各自逐字节一致，result/verification schema、
forbidden trace、network、credential、symlink、权限门逐项复查均 PASS/0。但 runner 在写 security summary 与 `COMPLETE`
前，把“network grep 无命中”的规范退出码 `1` 经 `pipefail` 误判为失败；失败根=`formal-7ad86cd-v4`。

v4 的两份 result 与两份 verification 只做了存在性、哈希、A/B、schema gate，不读取科学 outcome 数值或具体
classification，继续作废。execution addendum v5 唯一改动是在 grep→wc 的零命中计数 assignment 末尾加 `|| true`；
后续 `test network_hits = 0` 仍强制，安全门不放宽。科学协议、源码、输入、统计、判据与资源均不变；本地
focused=`16 passed`。addendum SHA-256=`10abe7f5ca55879063fdf2790611c2b3f4650314fcd9bc63b178c652ace17214`，
GPU/API/model fit/base update=`0/0/0/0`。下一次必须 fresh exact commit/root 并重算所有科学输出。

## 0KB. 2026-08-30 FOREAGENT LOEO v3 在结果写入前被 raw 数值门拦截；v4 只修公式容差

exact commit=`701b4058b56b65121d939736a0920b81adb86fae` 的第三次 formal 通过 focused/full=
`11/1784 passed`、48 warnings，随后 producer 在图投影与结果写入前以 `ValueError: known raw reproduction`
fail-closed。result/verification 文件仍为 `0`，verifier 未启动；失败根=`formal-701b405-v3`，不得复用。

独立整数诊断在固定 18,381 pairs=`55,143` judgments 上得到 DeepSeek/GPT 正确轮数=`33,925/32,477`，即
`33925/55143` 与 `32477/55143`。普通 binary64 累加相对冻结小数仅差 `18ε/13ε`，旧门 `2e-15` 小于合法
summation error。numeric addendum v4 在任何完整 LOEO 结果前把 production-only raw reproduction 门改为
`64 * binary64 epsilon = 1.4210854715202004e-14`；18ε 必须通过、128ε synthetic drift 必须失败。
KNOWN raw constants、support、LOEO、estimands、bootstrap、verifier、分类门和资源均不变；本地 focused=`14 passed`。
addendum SHA-256=`94fa4b3ae4fa591dd7d56fe32d8f9b6c1bf1ea96ef7a5f3f6bf2c37e5d144d6c`，
GPU/API/model fit/base update=`0/0/0/0`。下一次仍须 fresh exact commit/root 与全部 formal 门。

## 0KA. 2026-08-30 FOREAGENT LOEO v2 在结果前暴露全仓 pytest 范围错误；v3 只修测试边界

exact commit=`29a523cf6d50f95eba24fb29df6b39c765044273` 的第二次 formal 已通过 fresh no-smudge checkout 与
focused=`9 passed`，随后因 runner 使用 bare repository-wide `pytest` 在 collection 阶段返回 `2`。它误收集两个历史
`*_test.py` 命令行模块，并触发两个依赖可选 `dojo` 包的无关顶层 integration tests；producer/verifier 均未启动，
result/verification 文件均为 `0`，相关进程清零。失败根=`formal-29a523c-v2`，不得复用或解释科学结果。

execution addendum v3 唯一改动是把 full regression 从 bare repo root 收敛到项目一贯的 `phase1/tests`；其中测试文件不删减。
科学协议、输入、estimands、20,000 task bootstrap、分类门、producer/verifier 与资源均不变。新增静态门同时要求 scoped
full-suite 命令并禁止失败的 bare 命令；本地 focused=`11 passed`。addendum/runner/execution-test SHA-256=
`6f10eab92fbda4594ce428695c2da5522ed8e9bd38022a7587b1c8db42f392b5` /
`a2cb11ef27746b9981f68f525a99e99ca1093fc21fa110a4f0321ee92d0f08c3` /
`0b8da1319b0a44f2a73445c490904eba19da8a5dce2396a7ac4db2f4eb76769e`，GPU/API/model fit/base update=
`0/0/0/0`。下一次必须 fresh exact commit + fresh output root，重新跑完整 `phase1/tests` 后才允许 producer 启动。

## 0JZ. 2026-08-30 FOREAGENT LOEO v1 在测试前因无关 LFS smudge 失败；v2 只修 checkout

exact commit=`9cdf42dbce45a7edbf3053589384cc4c50efcf91` 的第一次 formal 在 fresh worktree checkout 时，
Git LFS 试图下载一个本实验不使用、且服务器缺失对象的历史 tarball，返回 `128`。focused/full tests、producer、verifier
均未开始，四份 result/verification 文件均不存在；失败根固定为 `formal-9cdf42d-v1`，不得复用或解释科学结果。

execution addendum v2 唯一改动是在 fresh `git worktree add` 前局部设置 `GIT_LFS_SKIP_SMUDGE=1`；科学协议、18,381-pair
support、estimands、bootstrap、分类门、producer/verifier 和资源全不变。新增静态控制要求恰好一个 scoped no-smudge checkout，
focused=`9 passed`。addendum SHA-256=`8cb1c80c36d6bc75b605ba9498cd75691f3e30077cadea4d952f432ea3b58a45`，
GPU/API/model fit/base update=`0/0/0/0`。下一次必须 fresh exact commit + fresh output root，并重新通过全部 formal 门。

## 0JY. 2026-08-30 FOREAGENT target-edge-excluded 图一致性基线已结果前冻结

近期 related-work gate 找到 2026 年 5 月的 Topological Consensus Rewards，以及更早的 Hodge/least-squares ranking、
Bradley–Terry、LLM-judge non-transitivity、TrustJudge/Sage；因此“用全局传递性给 pairwise judge 去噪”已经被直接
scoop，禁止声称算法首创。本实验只作为 Predictor Benchmark 的强基线与 MLE-solution domain transfer。

固定输入仍是 exact common finite `18,381 pairs / 26 tasks / 894 vertices / rank 868`。每个 model×task 将三轮
winner 编为 signed edge flow；对目标边 `e`，只用其他边的 Hodge least-squares potential 预测它，闭式 LOEO 为
`(fitted_e - h_e*y_e)/(1-h_e)`。bridge 或精确零预测回退 raw triplicate majority，形成 full-coverage hybrid；
truth 只在预测完成后评分。primary 是 equal-task task-macro `hybrid−raw`，20,000 次 task bootstrap，不做 pair-IID。

结果前固定正门：LOEO pair coverage≥`0.90`；至少一个固定模型的 task-macro gain CI 下界>`0`；两个模型 point gain
均非负。若方法提升门失败但 hybrid DeepSeek−GPT CI 下界仍>`0`，只能记为模型比较稳健，不能称去噪提升。截至冻结，
majority/LOEO coverage、accuracy、gain、residual 与 hybrid model delta 均未计算或读取；synthetic focused=`7 passed`。
protocol SHA-256=`bcd25033e2340a0b98c362ae1fffb29fe39c5222ceb531e5112d4675d7be033c`，GPU/API/model
fit/base update=`0/0/0/0`。正式运行必须 fresh exact commit、A/B byte match、opposite-orientation grounded verifier、
trace/security 与只读门全过；无论正负都记录。

## 0JX. 2026-08-30 FOREAGENT exact-grid UST outcome sensitivity 正式完成：外部模型比较对图重加权稳健

v4 exact commit=`b0fddf62134f006809278418a109411f4426da87` 已在 fresh root
`/research/d7/spc/yzyang4/foreagent-ust-outcome-sensitivity/formal-b0fddf6-v4` 完成。focused/full=
`13/1773 passed`、48 warnings；producer A/B 与独立 grounded-inverse verifier A/B 各自逐字节一致，23-entry manifest
全通过，独立最大数值差=`2.2737367544323206e-13`，结果树只读，forbidden-path/network/credential hits 全为 0。

exact common support 为 18,381 pairs、894 vertices、26 components、incidence rank=`868`、cycle rows=`17,513`；
edge/task-weight TV=`0.11449711207982645/0.11373050512738934`。DeepSeek pair-micro raw/UST=
`0.6152186134232811/0.6052414090772692`，shift=`-0.0099772043460119031`，95% task CI=
`[-0.024529104704855254,0.0026177484893845637]`；GPT raw/UST=
`0.58895961409426412/0.58113517235648726`，shift=`-0.0078244417377768549`，CI=
`[-0.020361700974923402,0.0032945061117868324]`。两项下降均不能称显著。

正结果是模型比较的外部稳健性：DeepSeek−GPT equal-task task-macro 在 raw 下为 `0.026657533634302202`，
95% CI=`[0.0021004144235817652,0.053036401295895153]`；UST 后为 `0.02671874905758977`，CI=
`[0.0019568230933495541,0.053442489897444191]`，26/26 LOTO 均保持正号。允许主张 graph-aware correction
非平凡地改变绝对 headline，但不推翻主要模型比较；禁止称 UST 提升、显著降分、ESS、新图定理或重写 FOREAGENT 的
agent-level/prior insufficient-support 结论。result/verification/manifest SHA-256=`ec51dcfa...4083` /
`6a0942e0...43f1` / `a5d35103...0567`，GPU/API/model fit/base update=`0/0/0/0`。详见正式报告与机器回执。

## 0JW. 2026-08-30 FOREAGENT v3 的 raw reproduction 门误设为 `1e-15`；v4 以 `64ε` 修正

v3 exact commit=`93154e54987c3fec720f50b754785737f3e0a1c2` 通过 focused/full=`12/1772 passed`、48 warnings，
但 producer 在写任何 result 前被 raw reproduction guard 拒绝，失败根=`formal-93154e5-v3`，四份 result/verification
均不存在。该门比较的是协议中已披露的四个 raw accuracy，不是新 UST outcome。

独立整数/`Fraction` 诊断确认四项与同一 110,620-row 输入精确一致；普通 binary64 求和顺序相对冻结 decimal 的最大偏差
为 DeepSeek pair-micro 的 `3.9968028886505635e-15 = 18ε`，另外三项为 `12.5ε/1ε/0ε`。原绝对门
`1e-15` 小于合法 summation error。v4 在任何完整 UST result 前冻结为 `64 * binary64 epsilon =
1.4210854715202004e-14`；18ε 必须通过，128ε synthetic drift 必须失败。KNOWN raw constants、输出算法、support、UST、
四 estimands、bootstrap/verifier/classification 全不变。focused=`13 passed`，numeric addendum SHA-256=
`5a47d185...83fb69`，GPU/API/model fit/base update=`0/0/0/0`。下一次仍用 fresh exact commit/root。

## 0JV. 2026-08-30 FOREAGENT endpoint identity 必须是 `(task,path)`；v2 无结果失败，v3 已冻结

v2 exact commit=`293576b1cab6f46a7ffab0ad0df768325701d390` 的 focused/full=`11/1771 passed`、48 warnings，
线程修正有效；但 producer A 在写任何 result 前以 `ValueError: endpoint crosses tasks` fail-closed。`COMPLETE` 与四份
result/verification 文件均不存在；历史公开 scores/predictions 已被 producer 读取，但没有完整 common graph、UST outcome
artifact 或可解释 aggregate，partial in-memory work 全部作废。失败根固定为 `formal-293576b-v2`。

随后独立 path-only 审计只读 `source_index + solution_paths`：18,430 个 finite-filter 前共同 grid pairs、26 tasks，
按任务命名空间有 895 个 endpoint membership，裸 path 字符串只有 885 个；9 个字符串跨任务复用，覆盖 19 个
task-path membership。故官方 path 是 task-relative，endpoint identity 必须是 `(task,solution_path)`；这也精确恢复论文的
895 solutions，而不是允许跨任务合图。

identity addendum v3 在任何完整 UST result 前冻结：producer 保持 task-local UnionFind，独立 verifier 保持 task-local
adjacency/DFS，只删除错误的全局 raw-path guard；同 source/task 内 duplicate、release task drift 和跨 task 合图仍 fail-closed。
18,381-pair support、四 estimands、20,000 task bootstrap、分类政策均不变。新增“两任务复用同一 raw pair”控制，要求
`4 vertices / 2 components / rank 2`，focused=`12 passed`；addendum SHA-256=`e2d8f6a5...6f3684`，
GPU/API/model fit/base update=`0/0/0/0`。下一次仍须 fresh exact commit/root 重跑完整 formal。

## 0JU. 2026-08-30 FOREAGENT UST v1 在结果前因 BLAS 线程过订阅失效；v2 仅修执行资源

exact commit=`5abfbd44d1459f9170904e0c8e1b954ead5628df` 的第一次 formal 在 full suite 完成 270 个测试后，
进入一个 36-pair synthetic tamper test 时出现 119 threads、`2948%` CPU、elapsed=`00:09:08`、累计
CPU=`04:29:28`。此时 `COMPLETE` 与四份 result/verification 文件均不存在，任何 UST outcome aggregate 均未生成或读取；
故主动终止并保留无结果根 `formal-5abfbd4-v1`。shell EXIT trap 留下的 `FAILED_RC=0` 不是成功证据，固定
`ABORTED_ENGINEERING_OVERSUBSCRIPTION` 才是该根的 disposition。

同一 exact commit、同一测试在 `OPENBLAS/OMP/MKL/NUMEXPR=1` 下 `1 passed`，pytest=`2.95s`、总墙钟
`10.14s`。因此新增 additive execution addendum v2，只在 runner 顶部强制四项线程上限并把 addendum 纳入 hash binding；
producer、独立 verifier、18,381-pair support、四个 estimands、20,000 次 task bootstrap、阈值与科学分类全部不变。
父科学协议 SHA-256 仍为 `7d47b1aa...557a425`；本地 focused=`11 passed`，GPU/API/model fit/base update=
`0/0/0/0`。下一次必须 fresh exact commit + fresh output root 重跑全部 formal gates，不能复用 v1 根。
详见同日工程失效记录与 `foreagent_ust_outcome_sensitivity_execution_addendum_v2.json`。

## 0JT. 2026-08-30 FOREAGENT exact-grid UST outcome sensitivity 已结果前冻结

FOREAGENT 官方 ACL 2026 论文明确从 895 solutions 穷举 18,438 pair rows，并以 micro-averaged pair accuracy 为 primary；
这使已验证的 graph-rank inflation 直接对应一个公开 benchmark estimand。旧 auto parquet 与 official alignment 相差 77 rows
且 5,068 个共同 finite pairs 的 winner 版本不同，故绝不复用旧 graph weights。新协议固定在 156-file、110,620-row compact
primitive 上重建 exact common graph：DeepSeek exact 三轮 grid、GPT 三轮 intersection、cross-model intersection、finite
directional filter后固定 `18,381 pairs / 26 tasks`；confidence 不读，三次 correctness 先在 pair 内平均。

四个强制估计量为 raw pair micro、UST rank micro、raw task macro、UST task macro，并在同 pair 上报告 DeepSeek−GPT；
20,000 次 task bootstrap seeds=`20260830/20260831`，固定 LOTO sign tolerance=`1e-10`。UST rank micro 只解释为随机
spanning basis sensitivity，不是唯一正确 accuracy；prior `INSUFFICIENT-SUPPORT` 不得重写，也不得据此否定 FOREAGENT 的
agent-level 6×/+6%。protocol SHA-256=`7d47b1aa6ef3ffb61c47f1fe3d6631a5bb7b2c97228de8a7c9192b9fc557a425`；
focused=`11 passed`，GPU/API/model fit/base update=`0/0/0/0`。截至冻结，exact-grid graph rank/UST weights 与所有新 UST
outcome metrics 均未计算或读取；只能先公开 exact source，再运行 fresh formal。详见同日结果前冻结记录。

## 0JS. 2026-08-30 historical UST sensitivity 正式完成：结构非平凡，旧 predictor 排名稳健但未获性能突破

v2 exact commit=`65b2e2a6669a1ddc41059746c843fab501895190` 已在 fresh detached formal 根
`/research/d7/spc/yzyang4/historical-ust-predictor-sensitivity/formal-65b2e2a-v2` 完成。focused/full=
`13/1760 passed`、48 个既有 warning；producer A/B 与 grounded-inverse verifier A/B 均逐字节一致，独立最大数值差=
`1.1368683772161603e-13`，23-entry manifest 全通过，结果树只读，file/network/credential hits 全为 0。

结构读数为 931 pair rows、1,346 endpoint memberships、28 tasks、550 decision parents、559 connected components、
incidence rank=`787`、cycle rows=`144`；UST edge TV=`0.12106505144691318`，task-weight TV=
`0.049068032215226765`。这确认 graph/rank audit 在历史支持上也是非平凡的，但不能称 effective sample size 或独立标签数。

冻结 nested `pair→parent→task` headline 下，`static_gbm_task` raw/UST=`0.54801174684043918/0.5483277645334842`，
UST−raw=`0.00031601769304501204`，95% CI=`[-0.00037747374181428185,0.001145659286141352]`；UST
headline CI=`[0.49819079664424992,0.60078820168816471]`，下界未超过 0.5。相对固定 TF-IDF 的 paired delta=
`-0.018259007376133896`，CI=`[-0.10907272623875371,0.086268880671008574]`。12-model 与 primary-panel
headline ranking discordance 均为 0，TF-IDF 继续第一。因此允许的正主张是“graph-aware benchmark correction 可量化且旧排序对其稳健”，
不是 critic 性能提升或 prospective confirmation。详见同日正式结果与机器回执。

## 0JR. 2026-08-30 Target-300 在 `98f2` 增至 193/300；严格前缀保持，truth 继续封存

固定 quiescent formal 在 snapshot=`98f2cba9ca4b3ac6404305da2528a4e8c391ba795f74438a5e4cca1a162765fa`
完成，exact control commit=`ab59a011d945e4a96daf7dbbbc927a59027da077`，focused/full=`12/965 passed`、
47 warnings。最小白名单结构回执显示 selected physical runs=`160→193`、archives=`49→60`、tasks=`30`、remaining=`107`，
previous exact prefix survived=`true`；boundary archive 与 first-closed anchor 都不存在。producer 状态仍为
`FUTURE_COHORT_COLLECTING`，独立 verifier=`PASS_COLLECTING_TRUTH_UNREAD`。

producer/verifier A/B diff=`0/0 bytes`，52-entry manifest 全通过，forbidden/credential hits 全为 0；truth、prediction values、
accuracy、search utility 均未读。第一次检查的官方 aggregate stdout 附带 task-level 结构 run counts，超出原定 totals-only
白名单但不含 identity/value/effect；偏差已记录且这些 task rows 不复制、不使用，后续复核固定为 totals-only。Target-300 尚未闭合，
不授权 truth support、replay、effect、GPU 或付费 API。详见同日安全进度回执。

## 0JQ. 2026-08-30 historical UST sensitivity v1 在 outcome aggregate 前作废；v2 补齐既有 nested headline

v1 exact commit=`52951ebfe80d4fdb28b13ac970ceff524a00ed22` 的 focused=`11 passed`，但 pre-flight 复核发现它只算
task-pair macro 与 global-parent macro，漏掉 0GA 已冻结的 `pair→parent→task` nested headline。formal 在 full tests
最近可见 `40%` 时主动终止；`result_a/b.json` 与 verification A/B 全不存在，故没有 UST accuracy、shift 或 ranking
被计算/读取。无结果失败根保留为 `/research/d7/spc/yzyang4/historical-ust-predictor-sensitivity/formal-52951eb-v1`，
不能引用其科学分类。

v2 在任何 historical UST outcome aggregate 前唯一增加：parent 内 UST-weight pair credit → task 内等权 parent →
28 tasks 等权；uniform reference 保持相同层级。task-pair 与 global-parent 只作 mandatory sensitivity，不能 rescue
headline；固定 `static_gbm_task` champion 不重选。新增 2:1 parent-count control 精确区分 global-parent=`2/3` 与
nested task-parent=`1/2`，以及完整 931-pair×12-model synthetic end-to-end verifier；后者抓到并修复“TF-IDF 尚未
重建就求 paired delta”的顺序 bug。v2 focused=`13 passed`，GPU/API/model fit/base update=`0/0/0/0`；正式结果尚未运行。
本段最后一句是冻结时状态，现已由 0JS 的正式结果 supersede。详见同日 v1 失效与 v2 修订记录及
`historical_ust_predictor_sensitivity_v2.json`。

## 0JP. 2026-08-30 FOREAGENT UST/rank 权重出现非平凡外部结构正结果

在任何 per-edge leverage、task edge count 或 task redistribution 读数前，先以 commit=
`1ad29a9568421a2a864d279a5cb71f67ec74e99f` 冻结 effective-resistance / uniform-spanning-tree 权重协议；
其数学不是首创，贡献定位为 MLE pair benchmark 的审计标准。fresh detached formal 根=
`/research/d7/spc/yzyang4/foreagent-ust-pair-weighting/formal-1ad29a9-v1`，focused/full=`10/1747 passed`、
48 warnings；eigendecomposition producer A/B 与 grounded-inverse verifier A/B 各自逐字节一致，Foster 总和的
双实现残差约 `1.85e-11/1.84e-11`，file/network forbidden hits=`0`，结果树只读。

正式结构结果：18,361 rows、895 vertices、26 components、rank=`869`；相对 uniform rows，edge distribution
TV=`0.11721717545274284`，task-weight TV=`0.11712428448024467`。raw-row 与 rank weighting 的 effective task
count 分别为 `17.066060493372625/20.574912132523227`，最大 task share 从 `0.066608572517836723` 降为
`0.056386651323360182`；最大 edge weight=`2/3`，为 uniform mean 的 `14.085922516302263` 倍。这证明 `2/k`
不是我方 sibling clique 特例：任意 graph 上可用 UST inclusion probability 推广，且会造成非平凡的 benchmark
隐式重加权。

边界：只读公开 `paths`，scores/predictions/code/identity 未读或输出；GPU/API/model-fit/base-update=`0/0/0/0`。
不得称新图定理、ESS、独立标签数或 FOREAGENT accuracy 无效。下一步只能先冻结历史同池 931-pair sensitivity
protocol，再检查 11 个 static/heuristic arms + fixed TF-IDF 的 raw/UST task-macro 与排序稳定性；不得事后换 champion。

## 0JO. 2026-08-30 FOREAGENT incidence-rank 外部审计已完成 formal 复验

exact commit=`dcf03949bb8afc3a71ff12242277cf03d381efdf` 的 post-push changed paths=`8`、credential filename/blob
hits=`0/0`、四个 source bindings 全一致。fresh detached formal 根=
`/research/d7/spc/yzyang4/foreagent-pair-graph-linear-rank/formal-dcf0394-v1`，focused/full=`7/1737 passed`、48 个
既有 warning，union-find A/B 与 independent adjacency/DFS A/B 逐字节一致，file/network forbidden hits=`0`，输出只读。
result SHA-256=`0ecb166d...6c1275`、manifest SHA-256=`47a9f871...f63689`。

正式结果：18,361 rows、895 vertices、26 tasks/components、26/26 task graphs connected、incidence rank=`869`、
cycle-space rows=`17,492`、rows/rank=`21.128883774453396`、redundant share=`0.95267142312510211`。只读 `paths`，
scores/predictions/code/identities 均未读或输出；GPU/API/model-fit/base-update=`0/0/0/0`。分类严格保持
`DESCRIPTIVE_PAIR_GRAPH_LINEAR_RANK_AUDIT_COMPLETE`，不是 confirmatory effect。机器回执见同日 JSON。

## 0JN. 2026-08-30 学长 0828 outcome 已安全接入；新 self-improvement 想法不得直接转成底座微调

`dojo-reproduce` 仍为 `5baccb170ce287f9c8eed7b23ccf693a0268515a`；最新 outcome 是
`0828/MIXED_PAIRWISE_REWARD_AND_RL_EXPERIMENTS.md`，不是新 commit。原 blob 的 credential-shape hits=`1`，先在远端
流式脱敏为 mode-0600 副本；source/sanitized SHA-256=`17317a2d...129ad6` / `15f04f80...76c3f5`，脱敏后 hits=`0`，
原值未打印、未使用、未转存本地。

报告的正面信息是 seed-7 的 Qwen3 Base 从 1.7B 到 14B 有 proxy scaling，14B best=`62.76%`，超过同一 1,160-pair
test 的轻量基线；但 seed-6 不复现、0.6B seed-6 缺失，mixed 输出无 source provenance，shared endpoint 未聚类，
best validation checkpoint 不是 frozen outer test，RL prompt 还把 task 第一条 journal 的资源条件错配到其他 experiment。
因此它继续是探索性容量信号，不升级为 clean scaling confirmation。

学长提出的 generator+verifier+昂贵稀缺 label 循环，在一般方法上已与 ReST、Self-Rewarding LM、SPIN、ReST-MCTS*、
VDS-TTT、Sol-Ver、RAFT/CodeRL 高度重叠，不能申通用框架首创；直接微调 Qwen generator 还违反本项目“不微调/RL agent
底座”硬约束，当前不启动。仅保留一个以后需另批的 MLE-specific extension：固定真实 execution-label 预算，用不更新底座
参数的 experience retrieval/in-context memory 让 generator 利用已执行经验，并与 critic-only、memory-only、joint 及 uniform
做 end-to-end 等预算对照。OpenRouter full-context judge 继续沿既有预注册 panel；聊天/报告中的 key 不存不使用，付费矩阵需
精确成本批准。W&B token 已脱敏且禁止使用，只有学长提供 public/safe export 后才分析 3 个 RL trajectories。详见同日安全接入记录。

## 0JM. 2026-08-30 FOREAGENT 公开 pair 图验证了 rank 审计的外部适用性

对直接竞品 FOREAGENT / PredictBeforeExecute 的官方自动转换 parquet（SHA-256=`79363b7e...f0b5f`，8,456,690 bytes）
只读 `paths` 一列；scores、predictions、solution code 均未读。Union-find producer 与不导入它的 adjacency/DFS verifier
逐字节一致：18,361 unique rows、895 vertices、26 tasks/connected components，26/26 task graphs 连通，故 endpoint-edge
incidence rank=`895-26=869`，cycle-space rows=`17,492`，rows/rank=`21.128883774453396`，redundant-row share=
`0.95267142312510211`，degree sum=`36,722=2E`。development focused=`7 passed`，GPU/API/model-fit/base-update=`0/0/0/0`。

这是已知 counts 后的 deterministic descriptive addendum，不是预注册 effect。允许的正结论是：pair-row inflation 不是我方
sibling corpus 特例；MLE preference benchmark 应同时报告 rows、vertices、components/incidence rank、endpoint degree、真实
decision/run grouping 与 cluster assumptions。禁止把 869 写成 effective sample size、独立 labels 或信息量，也不据此否定
FOREAGENT accuracy。InstructGPT 已明确指出同一 K-way ranking 派生的 `K choose 2` comparisons 相关并需成组训练，所以这里的
贡献是把该问题做成 MLE benchmark 的精确、可复验 graph-linear audit，而不是宣称依赖发现首创。当前 formal exact-commit
复验待代码公开后执行，开发 smoke 不能替代 post-push 回执。

## 0JL. 2026-08-30 Target-522 contrast-rank 链已公开复验并开始结果盲守候

结果前冻结链已作为 exact commit=`984876ff8ca812af64fe9c761180ecf78cf33ff1` 推送。fresh detached
post-push 根=`/research/d7/spc/yzyang4/target522-linear-contrast-rank-postpush-20260830-r1`：changed paths=`9`、
credential filename/blob hits=`0/0`、科学/执行与五个 source bindings 全一致；focused/full=`17/1730 passed`、48 个既有
warning，worktree clean，包只读，manifest SHA-256=`bf60c797...169a59`。本机 full collection 因没有 scipy/sklearn 而停，
正式远端固定 venv 已补足并通过，不用本机环境掩盖缺口。

部署时 Target-522 candidate/READY/COMPLETE/FAILED/CONTINUITY_GAP/TIMEOUT 全不存在，Stage-A output 也不存在。
固定 monitor=`/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-monitor-984876f-v1`，PID=`955941` live、
lock held；poll 0 只记录 `stage_a_complete=false/prospective_values_read=false`。它在 Stage-A `COMPLETE` 前不打开 public
profile，之后也只校验 public producer A/B，不读取或整体 hash private selection。当前仍无 contrast-rank 科学结果；
GPU/付费 API/model fit/base update=`0/0/0/0`。完整机器回执见同日 post-push/monitor receipt。

## 0JK. 2026-08-30 Target-522 线性 contrast-rank 审计已在候选出现前冻结

VCCD 的 endpoint-cost 论证暴露出一个可独立验证、但不依赖模型效果的 benchmark 审计问题：同一 parent 执行 `k` 个
endpoints 会物化 `k(k-1)/2` 条 sibling pair rows，但该 complete-clique endpoint-edge incidence design 的秩只有
`k-1`。在互不共享 endpoint 的 sibling cliques 上，总秩精确为 `endpoints - parents`。这不是 effective sample size、
Shannon information、统计独立标签数或任意 critic 的 feature-matrix rank。

历史 v11 开发读数已完整披露：4,263 条唯一 pair rows、2,293 parents、5,499 次 within-parent endpoint membership，
incidence rank=`3,206`、冗余 rows=`1,057`、rows/rank=`1.3296943231441047`；但其中有 34 个不完整 parent groups，且读数
先于阈值，因此只能用于阈值开发，不能作为确认。另纠正一处容易制造假证据的设计：`rows/rank >= 6/5` 与冗余行占比
`>=1/6` 数学等价，只计为同一个门，后者仅作可读报告。

在 `2026-08-30T03:48:16Z`，Target-522 candidate/READY/COMPLETE/FAILED 和 Stage-A output 全部不存在、既有 Stage-A
monitor PID live，且 candidate profile/identity 与 prospective values 均未读。此时冻结科学协议 SHA-256=
`3c8b8f87...7ad323`：acquisition 与 evaluation 两个 physical-run-disjoint 图必须分别达到 rows/rank `>=6/5`，并分别
满足 Stage-A 原有规模/任务集中门；Stage-A 任一支持门失败只记 limited support。两图全过才允许分类
`TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED`，否则按预先规则记 not-confirmed 或 limited-support，不换阈值。

analyzer 与不导入 analyzer 的 verifier 已通过 focused=`17 passed`；execution SHA-256=`50baf5c7...9b41ac`。六小时
monitor 在 Stage-A `COMPLETE` 前只看 marker，之后也只校验公开 `producer_a/b.json`，不 hash/打开 private selection；
fresh exact-commit full tests、A/B 逐字节复跑、mode-0600、file/network trace 与独立算术重建全部 fail-closed。
GPU/付费 API/model fit/base update=`0/0/0/0`。该项若为正，只能强化数据集的 clique-dependence、endpoint 成本与 `2/k`
权重审计；不替代 first-960 predictor benchmark，也不扩大 VCCD 的算法 novelty 主张。

## 0JJ. 2026-08-30 VCCD 的 vertex-query 主张进一步收窄

部署后继续按更精确的“付费节点观测”关键词查重，发现 graph-signal sampling 已长期研究从图上选择少量 vertices、读取其
scalar values，并用 experimental design / D-optimal 或 volume-maximization 目标重建未观测节点；Chen et al. (IEEE TSP 2015)
给出 experiment-designed graph sampling operator，Jayawant & Ortega (Signal Processing 2022) 明确以 D-opt 近似选择 vertex set。
Osting et al. (JMLR 2014) 还已用 A/D/E-optimal design 选择 ranking comparison graph。

因此追加禁止“首次把付费 unit 从 edge 改成 vertex”“首次 D-opt vertex observation”“首次图上最优采样”等主张。即使未来
Target-522 为正，VCCD 也只能说：把已知 optimal-design 思路实例化到 MLE 搜索树中，其中 grade 只在 sibling clique 内诱导
依赖比较、可行点由异质 task/physical run/parent topology 限制，目标是跨 run 的 code critic 而非 bandlimited graph-signal
reconstruction，并与语料泄漏、标签噪声、query/init 成本和聚类推断共同审计。该收窄不改变已冻结 execution、arm、预算或统计门；
论文主贡献仍是 Decision Corpus + Predictor Benchmark + Audit Protocol。详见 additive related-work v2。

## 0JI. 2026-08-30 VCCD Stage-A 执行链已公开复验并开始结果盲守候

Stage-A 执行链已作为 exact commit=`4fc9c3e4c9629ac86960a9cca198569e6a80ee2c` 推送。fresh detached
post-push 根=`/research/d7/spc/yzyang4/vccd-target522-execution-postpush-20260830-r1`：changed blobs=`8`、
credential pattern hits=`0`、execution bindings=`8`，focused/full=`33/1713 passed`、48 个既有 warning，worktree clean；
execution contract SHA-256=`66937a1f...15856`，prospective values 未读，GPU/付费 API/model fit/base update=`0/0/0/0`。

随后在 Target-522 candidate/READY/COMPLETE/FAILED 均不存在时启动固定 monitor
`/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-monitor-4fc9c3e-selection-v1`。独立检查于
`2026-08-30T03:28:25Z` 证明 PID=`939255` live、lock held、poll 0 正在等待；它在 selection `COMPLETE` 前只看 marker，
之后只能调用已哈希绑定的 Stage A。启动时 LATEST=`98f2cba9...2765fa`、structural runs=`468`、config-v2 count=`0`；
receipt-support 已以 `values_accessed=false/outcomes_read=false` 完成固定 snapshot 的结构回执。该状态仍不是效果结论，
first-960 + accrual-closure 前禁止任何 fit 或结果读取。

## 0JH. 2026-08-30 VCCD Target-522 Stage-A 自动执行链已结果前冻结

0JG 的科学协议已公开为 commit=`63a5b38bcdb6f057c6ea86309cd4ae7ca82dcce7`，fresh detached post-push
再次通过 focused/full=`25/1705 passed`、48 个既有 warning；changed blobs=`7`、credential pattern hits=`0`、
15 个协议绑定全一致、worktree clean，prospective values 未读。该回执只证明代码与协议发布完整，不是效果结论。

为避免 Target-522 到达后人工挑 snapshot、临时换参数或漏做复验，追加冻结
`vertex-cost-contrast-target522-stage-a-execution-v1`，SHA-256=`66937a1f...15856`。六小时 monitor 在 selection
`COMPLETE` 前只看 marker；激活后先重验 selection manifest，再在 fresh exact-commit worktree 跑 focused/full tests、producer
A/B、mode-0600 private selection A/B、以及不导入 producer 的 verifier A/B，全部要求逐字节一致，并对 producer/verifier 做
file+network trace。任一 hash、mode、重复、forbidden path、network 或 byte mismatch 都 fail-closed。

候选前严格查重另发现 ICML 2025 *Comparing Few to Rank Many* 已对 K-way 完整排序反馈做 D-optimal subset design；NeurIPS 2024
也已做 contextual logistic preference 的主动 pair 采样与 out-of-sample 泛化，NeurIPS 2021 则给出 multi-wise active ranking 样本复杂度。
因此明确禁止“D-opt/K-way/contextual active ranking 首创”和未匹配 oracle 的算法优越性主张。VCCD 只能定位为已知思路在 MLE 的付费 endpoint
执行、受 parent-clique 约束、依赖派生偏好、跨 physical-run critic 泛化与完整审计下的领域实例化。related-work addendum SHA-256=
`4176772f...2a816`；这收窄方法主张，但不影响 Decision Corpus + Predictor Benchmark + Audit Protocol 论文容器。

该链仍是纯 Stage A：GPU/付费 API/model fit/base update=`0/0/0/0`；单线程 CPU，两个 producer 的 yield solver 各至多
900 秒，预期总墙钟 `10--70` 分钟、90 分钟停止。first-960 closure 对 Stage A 不需要，但对任何 grade/outcome/orientation/
gap/prediction 读取和 7 个 CPU critic fits 仍是绝对前置门。截至 `2026-08-30T03:03:57Z`，LATEST=`98f2cba9...2765fa`、
snapshot dirs=`117`、structural runs=`468`，Target-522 candidate/COMPLETE/FAILED 均不存在、config-v2 count=`0`、values 未读。
详见同日 Stage-A 执行链冻结记录。

## 0JG. 2026-08-30 VCCD Target-522 结果前协议已冻结；效果读数仍必须等 first-960 closure

0JF 的工程门现已补齐为独立科学协议 `vertex-cost-contrast-target522-effect-v1`：在同一自动 Target-522 增量中，先按 task 内
salted physical-run hash 固定 acquisition/evaluation；Stage A 只能用 code + sibling topology，比较 exact-B representative
uniform、既有 yield-guarded breadth 与 VCCD 三条 nested endpoint 轨迹，fit checkpoint 固定为 `4/32`、`8/32`。producer 与
不导入 producer 的 verifier 已分别冻结；后者重新构造 run split、uniform/VCCD 顺序与 yield 证书约束。

真正效果阶段仍受最高优先级门约束：**first-960 + accrual-closure 前绝不读任何 grade/outcome/orientation/gap/prediction，绝不 fit**。
闭合后才允许在 acquisition runs 选中 endpoints 的非平局 sibling pairs 上训练固定 char-TFIDF LR，并在完全不交叠的 evaluation
runs 上一次性评估。训练与主指标均使用 clique `2/k` rank-normalization；主指标是 task-macro accuracy，proper scores、task/run
clustered CI、drop-dominant-task 和固定 gap buckets 全报，不能删预算或换指标救结果。最大矩阵为三臂×两预算加 full-data reference=
7 个 CPU fits，GPU/API/base update=`0/0/0`，预计单 CPU 35–90 分钟；当前没有执行授权需求，因为 closure 尚不存在。

冻结观测 `2026-08-30T02:32:51Z`：LATEST=`98f2cba9...2765fa`、structural runs=`468`、snapshot dirs=`117`，Target-522
candidate/COMPLETE/FAILED 均不存在、config-v2 count=`0`、prospective values 未读。focused synthetic+end-to-end=`14 passed`；该状态只是
**结果前协议冻结，不是正效果结论**。OpenRouter、历史 single-fold rescue 和任何事后 arm 均不得混入本 cohort。

## 0JF. 2026-08-30 vertex-cost contrast design 已冻结工程合同，尚非效果正结论

新的窄正方向不再最大化 materialized sibling pairs：同 parent 执行 k 个 endpoints 虽产生 `k(k-1)/2` 条 rows，但独立
contrast rank 至多 `k-1`。新 selector 以 endpoint execution 为成本，向已开 parent 加点时使用精确 centered-scatter 更新
`sqrt(k/(k+1))*(x_new-mean)`，按 D-opt logdet gain/endpoint 选点，并固定 task/run terminal caps；未来 fit 的每条 clique pair
权重为 `2/k`，使 parent 总权重恰为 `k-1`。这直接针对旧 yield 的 clique 膨胀、任务集中与 calibration 风险。

查重后明确不宣称 D-opt pair design、active preference learning 或 feedback graph 首创；可检验差异仅是 MLE 中“付费顶点执行→
依赖的 sibling pair 派生标签”加完整成本/异质性/run-clean 审计。纯 NumPy outcome-blind 核心与 synthetic tests SHA-256=
`e241864e...fcd68f` / `7e799d46...7f0518`，focused=`11 passed`；接口不接收 label/grade/outcome/prediction/accuracy/utility。

当前只到 **`ENGINEERING_CONTRACT_FROZEN_BEFORE_TARGET522_CANDIDATE_PROFILE_OR_VALUES`**：冻结时 Target-522 structural runs=466、
candidate/COMPLETE/FAILED 均不存在，values 未读。必须在 candidate 前补齐 code-only firewall、固定外层 run split、exact-B baselines、
critic matrix、独立 verifier 和效果门，才能成为科学预注册；OpenRouter 结果不得事后混入 v0。详见同日工程冻结记录。

## 0JE. 2026-08-30 OpenRouter 目录价格漂移已在任何 live call 前追加式修复

四个冻结模型 ID 在官方公共目录中仍全部存在，但 DeepSeek V4 Flash 0731 的 prompt/completion 价格已从旧冻结值
`0.045/0.09` 变为 `0.065/0.18 USD per million tokens`；旧 `provider.max_price` 会错误拒绝该 arm。旧 hardening/receipt
保持不可变，新增 public catalog receipt、append-only hardening 与 launch receipt，SHA-256 分别为
`a534573d...73ab4`、`924526a4...b99d7`、`8899c1bf...7f35`。panel、prompt、四模型、双方向、64 calls、2 USD stop、
reliability gates、分析与科学边界逐字段不变；只更新 DeepSeek 目录价格。focused=`9 passed`，API/GPU/model fit/base update=
`0/0/0/0`。远端固定 venv 在正式 `umask 077` 下又通过 focused/full=`9/1680 passed`；第一次漏设 umask 的 0644 private
fixture 被安全门正确拒绝并保留为工程失败回执。

公开 commit=`b19e23d5090a08e2f1d059131772266644f17a98` 的 fresh detached post-push 又通过 focused/full=
`9 passed in 1.33s` / `1680 passed, 48 warnings in 97.36s`；changed paths=`8`、credential filename/blob=`0/0`、
三项新增机器 artifact SHA 与冻结值逐字节一致，worktree clean。独立根=`openrouter-catalog-refresh-postpush/verify-3KnXk4`。

远端 `.env` mode=600，但截至 `2026-08-30T01:41:34Z` 仍没有 `OPENROUTER_API_KEY` 变量；聊天明文没有转存。只有用户或
学长直接安全安装后，才重跑不回显值的 account/catalog/privacy gate；目录再漂移或任何 transport contract 不满足即
fail-closed。smoke PASS 也不自动授权 full。详见同日结果前修复记录。

## 0JD. 2026-08-30 v5 首批 successor 已连续摄取，支持链仍结果盲运行

v5 guard 在 `01:16:30Z` 正常 handoff 第一 successor `c04bbd2c...6a575` 后 COMPLETE、无 FAILED；固定 intake 又连续纳入
六个累计 successor，`LATEST=13d67288...1c449`，snapshot dirs=`113`。截至 `01:50:08Z`，intake、transition、receipt、
config-v9、Target-300、WL PID 均 live，support locks held；Target-522 纯结构计数=`460` runs，candidate 不存在。

WL 最近正式处理到 `a22a56ae...a348` 的 selected runs=446、baseline delta=11，故仍 deferred；最新结构已到 460，WL PID/lock
仍 live/held 但尚未写下一条，可能正在构建 threshold 后 extension。不得读取中间文件、杀进程或提前推断门通过。Target-300
仍等待 quiescence，config-v2 filename count=0；
prospective label/outcome/prediction/accuracy/utility 全部未读。详见同日 successor 结构记录。

## 0JC. 2026-08-30 学长最新 5baccb 语料已增长，但 clean-scaling sidecar 仍未部署

`dojo-reproduce@5baccb170ce287f9c8eed7b23ccf693a0268515a` 已把 cards、value/mixed/merged decision、runsplit 与
RL train/test 换成更大的不可变 LFS objects；这里只核验 pointer OID/size，未展开数据。代码树仍没有
`DOJO_CONFIG_V2_SIDECAR`、`DOJO_GENERATOR_RELEASE` 或 config-v2 hook，outcome-blind source 的 sidecar 文件名数也为 0；
故本批不能事后升级为 exact-stratum clean scaling confirmation。

正向工程门没有失效：原 producer hook patch SHA=`56a3e4b6...54c9a5` 对最新 5baccb 仍 clean apply。Linux sparse/no-data
复验只取 `src/dojo/docs/tests`，4 个变更路径、focused=`19 passed`、compile 通过、credential filename/blob=`0/0`；
未修改/推送学长分支，也未读 LFS/prospective values。当前分类仍为
**`PATCH_COMPATIBLE_WITH_LATEST_SENIOR_COMMIT_NOT_DEPLOYED`**。只有学长 review/apply 并在未来 producer 显式启用后，
才报告并审批 0.6B/4B/8B × seeds GPU 矩阵；当前 GPU/API/model-fit/base-update=`0/0/0/0`。详见同日兼容复验。

## 0JB. 2026-08-30 outcome-blind 887 v5 续接已在重启前冻结

纯结构复核发现旧 continuous intake 已正常跑满 `145×300s` 后退出；v4 guard 最后一个成功状态仍是 poll 71、baseline
`887491a...62697`、所有支持链 healthy，下一轮只因 intake PID 已自然结束而留下 `FAILED_RC=1`。这不是 snapshot、sidecar、
label 或科学故障。复核时 LATEST 仍为 887，config-v2 文件名数=0，Target-522 候选/READY/COMPLETE/FAILED 均不存在，四个
Target-522 monitor 仍 live/持锁；前瞻 value 未读。

结果前冻结 v5：先绑定旧正常完成、RC1/poll71、死 PID、free lock、三个 state SHA 与六个脚本 SHA，再按固定顺序重启
credential-first intake → transition/receipt/config-v9/Target-300/WL → 六小时 guard。所有 cohort/scorer/state root/门保持不变；
guard 只读 PID、锁、LATEST、marker、文件名计数、哈希和 `outcomes_read=false` 结构汇总。唯一 successor 只写 identity handoff，
config-v2 只写 metadata 后停在 redaction/review 前；未知重复、哈希漂移或进程异常 fail-closed。GPU/API/model-fit/base-update=
`0/0/0/0`。

v5 已由公开 exact commit=`fc1ca43b...79f86d` 部署。第一次推前回执因中文路径 quote bug 漏扫一个 blob，已作废且未部署；
NUL-path r2 重跑为 changed paths=`6`、credential filename/blob=`0/0`、focused/full=`14/1677 passed`。启动后七个
intake/support/guard PID 全 live、锁 held，launcher manifest=`760c8300...5dcf8c`；独立 post-deploy 仍为 LATEST 887、
sidecar count 0、guard first poll 正常、prospective values 未读。当前状态为 **`V5_LIVE_AT_BASELINE_887`**，详见同日部署回执。

## 0JA. 2026-08-30 influence-bounded task reweight 已在新模型 readout 前冻结

0IZ 的 distribution-matched selection 精确改变了 task mixture，却因丢弃旧 yield pairs 而六个 efficacy 门失败；因此本项不再改
selection，而是原样保留旧 yield budget=`96/192` 的 `49/99` 个 induced pairs，只把训练 loss 的任务混合向完整 outer-train
availability 校正。旧 fold0 uniform/yield 结果、0IZ 负结果和全部结构诊断均已写入机器协议，仍是 historical development，不能
重分类 0IZ，也不能替代未来 physical-run confirmation。

直接 density ratio 在 budget96 会使 ESS fraction=`0.4291236656381884`、最大单 pair 梯度份额=
`0.12987012987012989`；预先提出的平方根 ratio 虽把 ESS 提到 `0.7850387062365991`，但单 pair 份额仍为
`0.05810467312403285`，超过先定 `1/20` 影响门，故在任何模型 fit 前停止。最终唯一规则是闭式 influence-bounded shrinkage：
先把每条 pair 的 `availability_task_count/selected_task_count` 归一到均值 1，再用
`w_i(lambda)=1+lambda(r_i-1)`；`lambda` 取同时满足 ESS≥`7/10`、单 pair weight share≤`1/20` 的最大值。
不搜索温度、clip、budget 或任务，不读 outcome 决定 `lambda`；正反 antisymmetric rows 使用同一权重。

协议 `endpoint_budget_influence_bounded_task_reweight_v1.json` 在任何新 weight、prediction 或 metric 前冻结。表示、LR、选样、
外部 eval 与旧 private baseline witness 全不变，只跑两个 CPU critic fits；primary 要求两个预算 task-macro accuracy 均严格优于
旧 yield，并同时过 terminal pooled/proper-score、uniform/drop-dominant、task-sign 与结构七门。任一失败即
`HISTORICAL_SINGLE_FOLD_INFLUENCE_BOUNDED_TASK_REWEIGHT_DOES_NOT_ADVANCE`，不得在 fold0 上换公式救回；全过也只能称
`...PROMISING_PENDING_NEW_RUN_CONFIRMATION`。GPU/付费 API/base update=`0/0/0`。详见
`phase1/实验记录/2026-08-30/EndpointBudget_InfluenceBoundedTaskReweight_预注册.md`。

formal r1 已完整结束，严格分类为 **`HISTORICAL_SINGLE_FOLD_INFLUENCE_BOUNDED_TASK_REWEIGHT_DOES_NOT_ADVANCE`**：
七门 `5/7` 通过。结构机制和 primary direction 都成立——budget 96/192 的 task-macro delta（new-old yield）为
`+0.005352833441068732/+0.08566095669036845`，pair-micro accuracy delta 为
`+0.036231884057971016/+0.021739130434782608`，drop-dominant 也为正；但 terminal log-loss/Brier 各恶化
`+0.0005388794995246778/+0.0002654579027394411`，且相对 uniform 的 terminal task-macro/drop-dominant 仍为
`-0.018359728506787333/-0.009615384615384616`，第二个 efficacy gate 失败。两档 task-macro 95% bootstrap CI 也均跨 0。

因此允许的窄正证据是：在相同 yield pairs 上，结果盲闭式 task-density reweight 能把旧 yield 的 task-macro 与 pooled accuracy
同时推高，尤其 terminal task-macro 为 +8.57pp；但它尚未超过强 uniform baseline 的跨任务稳健性，也未保持 calibration，不能
晋级或在 fold0 上调参救回。formal/postflight manifest=`df1df724...f6273` / `92f9e4b0...cd762`，第三 verifier 与 A/B
逐字节一致，focused/full=`37/1663 passed`，5,240 个 manifest members 零失败，五类扫描为空。正式包见
`phase1/results/endpoint_budget_influence_bounded_task_reweight_20260830_d768cb2/`；发布前 package-focused/full 又通过
`44/1670`，详见同日正式裁决。

## 0IZ. 2026-08-30 distribution-matched yield：结果前冻结的历史开发筛选

0IY 已证明旧 pure breadth 的 pooled 小增益由大任务集中贡献，且 task-macro 在两个 endpoint budget 都下降；因此不再扩大旧规则，
也不再拟合更大模型来掩盖 acquisition 机制。v1 协议 SHA=`371a5a2d...b06e` 的 formal r1 在 focused/full
`25/1651 passed` 后，于第一阶段 300 秒时限 fail-closed，RC=1；selection public/private 和 fit 均未写出，因此不是科学负结果。
无标签结构诊断随后证明 exact task-count DP 下界可在图上达到：总 objective=`22282`，耗时 `128.11160844005644s`，
run/parent=`349/93`，且不输出 endpoint witness；原 SHA 全局 tie 则在 300 秒后因缺失 mip gap 的诊断处理 bug 退出，也未写 witness。

上述失败与诊断结果已全部披露并绑定后，结果前冻结 v2：
`endpoint_budget_distribution_matched_yield_screen_v2.json`，SHA-256=
`37ad2fab68227d4aa236f1ce8c70c6197d1160b3f885adc466288ea1af41b06e`。当前状态是
**`FROZEN_AFTER_V1_SOLVER_FAILURE_BEFORE_V2_ENDPOINT_WITNESS_OR_PREDICTION`**；冻结当时尚无 v2 endpoint witness、预测或 task metric。

v2 formal r2 的 selection A/B、两个 fit 与 verifier A/B 已写出，但在 COMPLETE 前被 forbidden-path scanner 终止，故 summary/指标未读。
独立结果盲审计证明 30 条命中全部是仓库的 `target522.py/.pyc` 代码模块，data-path lines=`0`、network bytes=`0`，
receipt manifest=`b278058f2c6775acf4ed6c2456710b2d5abef14404b49013ff8a0b94af3b2205`；r2 已只读封存。
r3 只把 scanner 收窄为同名 token 下的 raw/prospective 数据扩展名；v2 protocol、selection、fit、七门与 private A/B 要求均不变。

formal r3 已通过并按冻结七门分类为 **`POST_AUDIT_DISTRIBUTION_MATCHED_YIELD_SCREEN_DOES_NOT_ADVANCE`**：只有 task-L1 gate
为 true，其余 6 个 efficacy gate 全 false。结构优化本身完全成功：六个 checkpoint 的 new L1 均低于 old yield，terminal 从
`0.37869971535806946` 降到 `0.08816342980931514`，objective=`22282` 精确等于 DP 下界；但 budget 96/192 相对 old yield 的 pooled
accuracy delta=`-0.050724637681159424/-0.07971014492753623`，task-macro=`+0.017860913596207714/-0.08391887524240466`。
terminal 相对 uniform pooled/task-macro/drop-dominant=`-0.043478260869565216/-0.18793956043956045/-0.09615384615384616`，且相对
old yield 的 log-loss/Brier 均变差。结论是“按 availability 配平任务分布”不是旧异质性的解决机制，不得继续扩大或救回。

formal commit=`ba75d078e1abf9542a11fa73c0de1a960312b5da`，manifest=`44c41f55...ed87`；postflight manifest=
`60949acd...bf4d`，第三次独立 verifier SHA=`9de0e843...a27e4f`，focused/full=`26/1652 passed`，全部扫描为空。
下一项若继续历史开发，必须另立协议：保留 yield pair，不再用 selection 丢信息，仅测试 task-balanced/hierarchical critic fitting；
这不是对当前七门的 post-hoc rescue，仍不能替代 rule-frozen 新 physical runs confirmation。

新规则只改 endpoint acquisition：在与旧 yield arm 完全相同的 nested endpoint checkpoints
`72/96/120/144/168/192` 和 induced-pair counts `36/49/61/73/85/99` 下，使 35 个 outer-train task 的已选 pair
分布匹配其 train-only availability；每个 checkpoint 同时固定 task share `<=20%`、run share `<=10%`，并保留 integrated
closed-run floor=`317`、terminal parent floor=`86`。独立整数 DP 给出所有 task-count allocation 的图外全局下界；单线程 MILP
必须在完整 graph/nesting/cap/floor 约束下精确达到该下界。tie 固定为 pinned numpy `1.26.4`、scipy `1.16.2`、HiGHS `1.8.0`、
threads=1、seed=0 的 constant-objective feasibility witness，并要求 producer A/B private bytes 完全一致；任何时限、gap 或漂移终止。

只在历史 train-only fold0 开发人口上，预算 `96/192` 各拟合一个与 0IX 完全相同的 char-TFIDF LR；旧 uniform/yield prediction
witness 原样复用，合计仅 2 个 CPU critic fits，GPU/付费 API/base update=`0/0/0`。七个结果前门同时要求：两预算 task-L1
均严格改善、两预算 new-old task-macro accuracy 均为正、terminal 相对 uniform 的 pooled/macro/drop-dominant 不退化、terminal
相对 old yield 的 log-loss/Brier 不退化、以及正 task 数不少于负 task 数。任一门失败即
`POST_AUDIT_DISTRIBUTION_MATCHED_YIELD_SCREEN_DOES_NOT_ADVANCE`；禁止删任务、改权重、换预算或换 tie-break 救回。

selection 命令行不接收 labels/cards/predictions/eval topology；fit 才接收已绑定的 train-only firewall。formal runner 要求 13 项预检、
focused/full tests、producer A/B、private A/B、独立 verifier A/B、strace 网络/路径边界、credential scan、整棵 SHA manifest 和 sealed
private files。即使七门全过，也只能称 **post-audit historical development promising**；确认必须等 rule-frozen 新 physical runs。
完整设计见 `phase1/实验记录/2026-08-30/EndpointBudget_DistributionMatchedYield_Screen冻结.md`。

## 0IY. 2026-08-29 task-heterogeneity 机制审计：旧 breadth 过度分散，新规则应匹配任务密度

0IX 的 smoke 严格不晋级，但两个 endpoint budget 的 accuracy/calibration 描述性同向且诱导 pair 数几乎相等；当前关键未知量不是
再跑更多模型，而是 terminal 增益为何被一个任务主导。为避免看完 task 表再选择解释，协议
`endpoint_budget_task_heterogeneity_audit_v1.json` 已在任何 task sign、coverage delta、task metric delta、coverage-metric correlation、
LOTO distribution 与 positive-gain concentration 未见时冻结，SHA-256=`f3aea619...0a99e`。

审计只重用已完成的四个 historical train-only 模型 witness，固定预算 `96/192`，0 model refit；逐 task 计算 endpoint/run/induced-pair
coverage delta、三项 metric delta、净正确贡献、全 20-task Spearman、LOTO 与 gain concentration。任务 SHA 和逐 task 行只写远端
mode-0600 private witness；公开产物不含 raw/hash identity 或 per-pair probability。独立 verifier 不导入 producer，从六个绑定输入
重建全部 task rows 与 aggregate。该审计没有 efficacy promotion gate，不能删任务、重加权、救回 smoke 或把 fold0 当 confirmation；
唯一允许用途是决定是否另行冻结 task-quota + yield-floor acquisition rule。

formal 结果固定为 **`EXPLORATORY_TASK_HETEROGENEITY_AUDIT_COMPLETE_NOT_CONFIRMATORY`**。budget 96/192 的 pooled accuracy delta 虽为
`+0.021739130434782608/+0.036231884057971016`，task-macro accuracy delta 却为
`-0.03829778065072183/-0.1040206851971558`；terminal 任务符号=`6 positive / 6 zero / 8 negative`。terminal 最大正贡献占
全部正贡献 `0.5294117647058824`，前两项占 `0.7058823529411765`；20 个 LOTO 中 1 个为负，复现主导任务反转。

机制上，yield arm 的 induced-pair task distribution 到 outer-train availability 的 L1 距离在 budget 96 从 baseline
`0.5776184538653364` 恶化到 `0.8042139549086468`，budget 192 也从 `0.3624937655860349` 恶化到
`0.37869971535806946`：最大化 unique task/run 把有限 labels 铺得过薄。另一方面，endpoint/run/pair coverage delta 与 task accuracy
delta 的 Spearman 仍为弱正（两预算约 `0.150--0.303`），说明“任务内密度”可能有效。下一规则应冻结为
**distribution-matched yield + anti-dominance**，而不是继续 pure breadth；任何同一 fold0 后续结果只能作 post-hoc development。

formal commit=`d2fb68c38b75eabd0f3520775da9aa16ea0e6ad6`，manifest=`69282730...51d8`；focused/full=
`7 passed` / `1645 passed`。producer A/B、private A/B、verifier A/B 逐字节一致；独立重建 40 个 task-budget rows，四类扫描为空，
sealed private mode=`0400`。GPU/API/model-fit/base-update=`0/0/0/0`。完整设计与失败留痕见
`phase1/实验记录/2026-08-29/EndpointBudget_TaskHeterogeneity_机制审计冻结.md`。

## 0IX. 2026-08-29 endpoint-budget label-efficiency smoke：描述性同向，但严格不晋级

0IV 的 Target-522 topology rule 只有结构可行性，论文价值必须落到真实 endpoint execution 成本下的 downstream critic label
efficiency。结果前冻结的 single-fold smoke 使用已认证 senior-0819 strict residual 539 pairs：salted physical-run fold0 历史评估、
fold1--4 训练；只比较 exact-B uniform-edge 与 yield-guarded breadth，在 `4/32,8/32` 两个 endpoint budgets 拟合固定
char-TFIDF LR，共 4 fits。固定分类为
**`HISTORICAL_SINGLE_FOLD_ENDPOINT_LABEL_EFFICIENCY_SMOKE_DOES_NOT_ADVANCE`**：四项 advancement gate 只过 3 项，不能把该规则
升级为确认性正主张，也不能按原两臂规则直接扩规模。

协议 SHA-256=`e0dd7414...9761` 在本 comparison 的 selection witness、prediction、accuracy、log-loss 与 Brier 均未见时冻结。
为落实“senior test 行绝不能进训练进程”，raw decision 只交给可信 split-firewall；selection 仅接收无方向 topology，fit 仅接收
train-only orientation，二者命令行都没有 raw decision path。precommit firewall 功能检查精确复现 source/core/train-core/
residual=`7644/1270/952/539` 与既有 residual fingerprint；formal receipt 再次确认 `senior_test_rows_exported=0`。

两个预算上，yield-guarded breadth 的 accuracy delta 分别为 `+0.021739130434782608` 与
`+0.036231884057971016`，log-loss delta 为 `-0.0025496231820229844` 与 `-0.004405386232297436`，Brier delta 为
`-0.0012740898302717129` 与 `-0.0021991937887723906`；诱导训练 pairs 几乎相同（`49 vs 48`、`99 vs 100`），所以描述性信号
不是简单的 label 数量膨胀。但两组 task/run-clustered 95% CI 均跨 0，且 terminal drop-dominant-task accuracy delta=
`-0.038461538461538464`，触发预注册否决门。terminal 总体净增 5 个正确 pair，而去掉占 `34/138` 的最大任务后净少 4 个，
说明当前增益高度异质，不能事后删任务或重加权救回 headline。

每个 fit 原子 mode-0600 checkpoint/resume；私有 per-pair witness 只含 pair/task/run hashes 与 probability。独立 verifier 不导入
训练模块且 0 refit，精确重算 pair-set、三项指标、task/run clustered bootstrap、drop-dominant-task 与最终 gate；A/B 双跑逐字节
一致。focused/full=`35 passed` / `1638 passed`。formal manifest=`4995bdf6...c6e38`，独立 summary/CSV SHA-256=
`b8068e69...d6ec` / `5037e206...7a12`；postflight 对 4 个 checkpoint mode、7 个 boundary/network/credential scanner、整棵
SHA256SUMS 全部精确通过。GPU/API/base-update=`0/0/0`。下一步仅允许先做不调参的匿名异质性机制审计，再结果前冻结新的
task-quota/yield-guarded 规则；fold0 已用于开发，不能再冒充外部确认。完整设计与结果见
`phase1/实验记录/2026-08-29/EndpointBudgetMatched_CriticLabelEfficiency_下一步设计.md`。

## 0IW. 2026-08-29 supervisor v1 因完成产物只读锁 fail-closed；v2 修复已冻结

guard v3 在 `05:37:17Z` 正常 COMPLETE；v1 supervisor 于下一轮以 RC=`65` 退出，且 guard v4 root 完全不存在。
真实复验显示 v3 完成后 `chmod -R a-w` 令 lock path 不可写，旧 `flock -n PATH -c true` 因 path-open permission
返回 65；同一 inode 用 read-only FD + nonblocking shared flock 为 free，而四个 live monitor 的 exclusive locks 在相同 probe
下均为 held。因此这是结果盲编排 bug，不是 snapshot/sidecar/duplicate/scientific failure。

结果前修复统一把 guard、renewal 与新 supervisor v2 的外部 lock 检查改为 read-only shared probe；v2 还绑定旧 v1/guard
source SHA、RC65、最后 baseline status、旧 guard manifest、dead PID 与 free lock，才可依次启动 guard v4 和 support renewal。
不改 cohort/scorer/WL/门；LATEST 仍为 887、sidecar filename count=0，prospective values 未读，GPU/API/model-fit/base-update=
`0/0/0/0`。详见 `phase1/实验记录/2026-08-29/OutcomeBlind_只读锁故障与Supervisor_v2修复.md`。

修复公开 commit=`7212167f0bf39e0be95b07085baca4208f8fbc6a` 的 Linux focused/full=
`7 passed in 0.08s` / `1626 passed, 47 warnings in 93.74s`，credential filename/blob=`0/0`。`05:55:37Z`
exact-source supervisor v2 PID=`289403` 与 guard v4 PID=`289483` 已上线，exclusive locks 均经 shared probe 确认为 held；
LATEST exact baseline、sidecar count=0。部署 manifest=`0bed43b9...3469`，support renewal 仍等旧 monitors 自然完成后触发。

## 0IV. 2026-08-29 Target-522 yield-guarded breadth 前瞻执行链已在 candidate 前冻结

唯一协议 `yield_guarded_breadth_forward_target522_v1.json` 在 Target-522 candidate/READY/COMPLETE 与失败 marker 全不存在时
冻结，SHA-256=`ce50247e...13cf`。producer 只接受相对 snapshot 887 的第一次自动选择、physical-run disjoint 且完整的
append-only increment；逐文件绑定 intake structural-pair SHA，并要求 pair rows 与增量 cards 重建出的 sibling cliques 完全
相等。exact-B uniform-edge baseline 每 seed/checkpoint 必须用满 endpoint budget。MILP 只读 unordered endpoint/parent/task/run
拓扑，公开文件只含 aggregate，endpoint witness 只写远端 mode-0600 private 文件。

独立 verifier 不导入 producer，也不复用其 MILP constraint builder：它重写 Target-522 loader、pair graph、exact-B baseline 与
完整约束矩阵；有 witness 时从 endpoint IDs 直接重算 induced edges 和全部固定门，无 witness 时独立求解并要求同 status。
formal runner 绑定公开 commit 与 protocol/producer/verifier/test/runner SHA，在 fresh detached worktree 先跑 focused/full tests，
再要求 producer/private/verifier A/B 各自逐字节一致，并用 strace 审计 forbidden path 与 network。六小时 monitor 在 start 时要求
候选仍不存在，等待阶段只测 marker existence；只有 selection COMPLETE 后才验 manifest 并运行唯一 formal root。

结果前最终 focused=`27 passed in 6.16s`；单线程 full=`1624 passed, 47 warnings in 89.91s`，RC=`0`，manifest SHA-256=
`4936e680...e2d9b`。一份旧开发 launcher 因遗漏线程环境产生 119 threads/约 30 CPU cores 而被主动终止并留中断回执；它没有
科学 readout，不计为通过。当前状态仍是 **`IMPLEMENTATION_FROZEN_BEFORE_TARGET522_CANDIDATE`**，不是正/负科学结论；
prospective label/outcome/prediction/accuracy/utility 未读，GPU/API/model-fit/base-update=`0/0/0/0`。

公开 commit=`219438e65d1275498e44a650306ce561696fdb8c` 的 fresh post-push focused/full 为
`27 passed in 6.51s` / `1624 passed, 47 warnings in 98.28s`，changed path/credential filename/blob=`9/0/0`。
在所有 selection marker 仍不存在时，exact-source monitor PID=`283216` 已上线且首轮只写
`selection_complete=false prospective_values_read=false`；部署回执已独立封存。Git fetch 的正常两行 stderr 是部署回执脚本的
白名单修正，不影响 live monitor，也没有重启它。

即使未来结构 witness 通过，也不能把 generic constrained graph selection 当 novelty。下一项正面主张必须是 endpoint-cost-matched
downstream label efficiency：历史 train-only、physical-run outer folds、exact-B 四臂、固定 CPU char-TFIDF LR，比较诱导 labels
对未见 run critic accuracy/calibration 的贡献；equal-pair-count 只能作机制 secondary，不能 rescue primary。详见
`phase1/实验记录/2026-08-29/YieldGuardedBreadth_Target522前瞻执行链冻结.md` 与
`EndpointBudgetMatched_CriticLabelEfficiency_下一步设计.md`。

## 0IU. 2026-08-29 exact-Budget 勘误后 yield-guarded breadth 开发正结论仍存活

冻结 Target-522 前发现旧 `uniform_edge` 的双 endpoint 原子 action 会让奇数 checkpoint 实际只使用 `B-1`：两折
`256×6×2=3072` 行中 fold0/fold1 分别 `503/453` 行 underfill，共 `956`。这是真实公平性缺陷，故先停止旧前瞻草案，
固定保留 edge priority、确定性线性化两个 endpoint、最后独立 salt singleton-fill 的 exact-B baseline，并要求每 seed/每
checkpoint `selected_endpoints==budget`。

修正后两折所有 pointwise 与 integrated nearest-rank median baseline 门均未变化；重新单核求解仍为 fold0/fold1 integrated
closed edges=`276/276,262/259`，task=`138/96,167/122`，run=`248/191,240/198`，terminal parent=`66/66,61/62`，
原七门全部通过。producer A/B SHA=`86bdcee7...1314` 且逐字节一致；不导入 producer、独立重写 baseline order 与直接
prefix induced-edge accounting 的 aggregate verifier A/B SHA=`7e3524f2...d37e`。它明确不声称重算未公开 private witness。

公开 commit=`dfdf8c28e29860f62327403e83f6bf7a3130a282` 的 fresh detached post-push replay 再次逐字节复现同一 result/verifier
SHA；focused=`3 passed in 0.43s`，network/prospective boundary/credential filename/blob hits=`0/0/0/0`。

固定分类为 **`HISTORICAL_RUN_SPLIT_EXACT_BUDGET_YIELD_GUARDED_BREADTH_JOINTLY_FEASIBLE_DEVELOPMENT_ONLY`**：仍是已读历史图
开发，不是外部确认、predictor accuracy 或 search utility。Target-522 candidate/profile 未见时，前瞻协议已改为 exact-B、
private mode-0600 witness + non-importing graph verifier；不得用原 underfilled baseline。r1–r4 的 pre-readout 工程失败原样
保留，r5 才是首个 scientific run。GPU/API/model-fit/base-update=`0/0/0/0`，prospective values/senior test 未读。详见
`phase1/实验记录/2026-08-29/YieldGuardedBreadth_ExactBudget基线勘误与前瞻冻结.md`。

## 0IT. 2026-08-29 outcome-blind 六小时续接已在运行窗口前冻结

`LATEST=887491a...62697`，config-v2 sidecar filename count=`0`；intake、WL、Target-522 与 task-balance v5-r3
仍 live。现有 guard v3 预计先于用户离开窗口结束，transition/receipt/config-v7/Target-300 随后自然结束，因此在任何
successor 或 sidecar 出现前冻结三段式结果盲续接：supervisor 先等待 v3 exact manifest 正常完成，再启动 fresh guard v4；
只有 transition、receipt、config-v7 与 Target-300 同时以固定 887 tail 正常结束、旧 PID 退出、锁 free、state/prior hash
不变时，才启动 transition/receipt/config-v8/Target-300 的原协议续接。live monitor 不重启，guard 必须先于 support
renewal，任何 snapshot/sidecar/FAILED/hash/duplicate 漂移均 fail-closed 或只写 identity handoff。

guard/renewal/supervisor/static-test SHA-256=`7c67778b...48a12` / `53c24da6...6a29` /
`8febae8e...337e9` / `398dc9d4...8f01c`；Bash syntax 与 focused=`5 passed`。固定成本为 CPU metadata polling，
GPU/API/model-fit/base-update=`0/0/0/0`；只读 PID、锁、LATEST、具名结构尾部、hash、sidecar filename count 与
`outcomes_read=false` 汇总，prospective label/outcome/prediction/accuracy/utility 与 sidecar/archive 内容均不读。部署必须从
公开 exact commit 的 Git object 执行，且 child first-poll 与 postflight manifest 均通过后才记为上线。详见
`phase1/实验记录/2026-08-29/OutcomeBlind_887六小时无空窗续接预检.md`。

## 0IS. 2026-08-29 TaskBalance v5/v5-r2 均在 candidate 前失败；v5-r3 只修 typed identity parser

权威 v4 在 `LATEST=887491a...62697` 不变时以 `TIMEOUT_RC=124` 正常结束；自动交接 v5 随即 `FAILED_RC=1`。
旧 v5 exact 11-file set SHA-256=`d3ee4736...3ba50`，candidate/READY/COMPLETE/monitor.log/preflight/handoff
receipt 均不存在，gap snapshot 与第一次 transition heartbeat 文件均为空，observed IDs 去重后只有 baseline；PID 已退出且
v4/v5/supervisor 锁均 free。故失败被定位为 10 秒 latch 在 300 秒 support monitor 下一次 heartbeat 前启动，使空 `grep`
pipeline 在 `pipefail` 下提前退出的工程竞态，不是候选或科学门失败。

第一次修复 commit=`1dab029...e3d1` 经 fresh post-push 与 focused=`14 passed` 后部署；v5-r2 又在 candidate/preflight/
monitor loop 前 `FAILED_RC=1`。其 exact 18-file set=`0f858d36...d02aa`，gap snapshot directory 仍为空，WL/receipt 只见
baseline；transition 中的额外 64-hex=`87ed6fa6...b9161` 经字段核对是 `script_sha256`，所有具名 snapshot identity 仍为 887。
因此第二次失败是“任意 64-hex”parser 缺陷，也不是科学门失败。

结果前 r3 固定新 root `latch-continuation-after-887-v5-r3`：绑定 v5 与 v5-r2 两个失败 fileset/source/protocol/marker；
继续从 v4 最后 observation 扫描完整 gap；日志只接受 `snapshot/prior_snapshot/latest/wl/transition/prior` 具名 identity，
若尚无具名 heartbeat 才允许使用结果盲 state identity 且必须等于 baseline 或唯一 current LATEST。多个 successor、support
skip、identity/hash 漂移仍 fail-closed。formal runner 只在 v4 clean-timeout + v5/v5-r2 exact pre-candidate failure +
v5-r3 唯一 COMPLETE 时接受 r3。population、1/4 task-share 门、producer/verifier 与解释完全不改；r3 部署前 prospective
values 未读；真实结果盲 transition/WL/receipt 日志的 typed-extractor replay 各自只输出 887，独立通过。GPU/API/model-fit/
base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/TaskBalance_v5心跳竞态与v5-r2结果前修复.md`。

r3 由公开 commit=`9f1b57f02cdf6b9a70c870268127ffacb3bc44b7` 部署；fresh post-push changed files=`5`、focused=
`14 passed in 0.38s`、typed replay=PASS、credential filename/blob=`0/0`。`2026-08-29T03:58:22Z` 独立 postflight
确认 PID=`194734` live、lock held、LATEST/handoff unique identity 均为 887，candidate/READY/COMPLETE/FAILED 全为空，
连续四个 poll 正常。handoff/preflight/deploy manifest SHA-256=`75e13644...07128` / `585385de...c37f6` /
`a4975902...8f5`；公开回执见 `phase1/results/task_balance_v5_r3_monitor_repair_20260829_9f1b57f/`。

## 0IR. 2026-08-29 学长最新 outcome 已对齐；全上下文 evaluator smoke 已冻结在凭据门前

学长 0828 outcome 的科学提交=`f534114e60658043c07f7a15d6440492caffc8ad`，后续 context-repair branch head=
`30b396323f28064040bb0bdf9cccb198d676dd27`；原文 Git blob=`7f691d9b6fa3d971bf889738fa8661694b6b0051`、
SHA-256=`17317a2d239cb862ec16d57aa0a2fa168f2c1a6cd841117950d8ee8127129ad6`。凭据行先在远端内存整行脱敏后才读；
明文 token、带权 W&B 链接与 raw reasoning 均未复制、调用或进入 Git。学长的新判断是 pair proxy 可能只有 60%—70% 可见
上限，应把重点转到真实 MLE end-to-end/label efficiency；mixed scaling 仅 seed7 明显、RL judger 尚不稳定且 prompt 存在
resource mismatch。故这些仍是探索线索，不升级为规模律或 RL 正结论。

允许推进的直接诊断是冻结历史 8-pair smoke panel 上，四个完整上下文 evaluator × AB/BA 共 64 calls 的 transport、parse、
顺序与 route reliability；accuracy 只描述、不作 smoke gate。generator 微调会更新 agent 底座，继续受 hard NO 禁止；RL/W&B
只接收学长先行脱敏导出。prospective first-960/Target-300/Target-522 values、search utility 与任何 future confirmation 均未读。

live-v2 已在任何真实调用前补齐：ZDR/deny-collection/require-parameters/price-sort/no-fallback、每模型 max-price、router
metadata、context-compression kill、attempt=1、同模型单 provider、按完整 context cap 的 2 USD pre-call upper-bound stop，以及
mode-0600 pre-call intent journal。
只有 intent/raw 构成冻结矩阵 exact prefix 且原始 response 可独立重算相同 route/pick/cost 才能续跑；pending intent 或失败记录
禁止 retry；launch receipt SHA 也写入每个 intent/raw row。hardening/runner/analyzer SHA-256=`01af5ff7...b5d60` /
`1c7da717...fc9a5` / `64ac3dbe...d7260`。

fresh r5 development 已完成：focused=`18 passed`；dry-run=`64` requests、network=`0`；mock intent/raw/parsed=
`64/64/64`，attempt-one 与 single-provider gates 过，随机 mock 被顺序门裁为 FAIL，证明 gate 非空泛。有效 launch receipt 的
missing-key attack 为 `rc=1`、network=`0`、raw/intent 均未创建。实际 live/API calls、GPU、model fit、base update=
`0/0/0/0`。公开包见 `phase1/results/openrouter_full_context_live_v2_preflight_20260829_01af5ff/`。

公开实现 commit=`69aa57acba50d298e20b222cd27ad8ee72a03d3d` 的 fresh detached post-push 复验也已完成：预检包
`9/9`、focused=`18 passed in 1.87s`、dry/mock network=`0/0`，缺失凭据攻击仍在网络和 intent/raw 之前阻断；
changed files=`18`、credential filename/blob=`0/0`。公开最小回执包见
`phase1/results/openrouter_full_context_live_v2_postpush_20260829_69aa57a/`。一次 precommit 无界 full suite 曾错误消耗
login-node 多线程 CPU，已中断且无科学输出；此后禁止在 login node 重复，详见
`phase1/实验记录/2026-08-29/OpenRouterFullContext_v2_LiveTransport_PostPush回执.md`。

当前状态固定为 **`LIVE_SMOKE_AUTHORIZED_BUT_CREDENTIAL_NOT_INSTALLED_FAIL_CLOSED`**：远端 mode-0600 `.env` 尚无
`OPENROUTER_API_KEY` 变量。不得把聊天中的明文重新放进 tool command/stdin；只能由用户或学长直接写入远端 `.env`。变量名
就绪后仍须先做不回显 key 的 account/catalog/privacy gate，再从公开 exact post-push commit 运行 smoke；PASS 也不自动授权
512-call full。详见 `phase1/实验记录/2026-08-29/OpenRouterFullContext_v2_LiveSmoke预检与凭据门.md`。

## 0IQ. 2026-08-29 breadth-at-near-equal-yield 已冻结 run-disjoint 内部 falsification

0IP 的大幅 label-yield 总门失败不变；事后只观察到六个低预算点的最差 balanced yield 均不低于 uniform-edge median，且终点
task/run breadth 更大。为排除该 pattern 被单一 run/task 子集驱动，在任何 hash split count、support profile 或 fold curve
readout 前，固定将 exact 539-pair residual 按 salted SHA-256 的 physical-run parity 分成两折。

每折先过 pairs/endpoints/parents/runs/tasks=`200/350/180/70/18`、task/run share≤`1/3,1/10`；任一失败不算 curve。
若 support 通过，则固定 `[3..8]/32` endpoint budgets、uniform/tie=`256/32`，要求两折同时满足 yield integral noninferiority、
pointwise≥`5/6`、task/run breadth integral≥`6/5,11/10`、terminal parent≥`9/10` 及 anti-dominance。threshold、salt、fold、
budget、method 均不得结果后修改。

protocol/producer/non-importing verifier/test/runner SHA-256=`76a6ad30...4396` / `cac94d9c...3636` /
`94252e49...bda2` / `29ae8fbe...c323` / `a7859103...3d8e`；新增 synthetic=`7 passed`。这明确是 full-graph
readout 后的内部 falsification，不是外部 confirmation；即使 survives 也仍需第三个未见 graph，且不证明 critic accuracy 或
search utility。GPU/API/model-fit/base-update=`0/0/0/0`，prospective values/senior test 未读。详见
`phase1/实验记录/2026-08-29/RunSplitBreadthParetoFalsification_v1_预注册.md`。

公开冻结 commit=`1563655a998851d41e9038fa5bda79a78f650247` 的 formal r1 在 focused/full=`36/1587 passed` 后，首个
producer 于 full-graph fingerprint assertion fail-closed，`FAILED_RC=1`；没有 producer JSON/verifier/COMPLETE，且发生在 fold
partition、split counts/support/curves 前。根因是错误混比了 qualification 的 profile fingerprint
`(relation,split,endpoints,parent)` 与 graph identity fingerprint `(endpoints,parent,task,run)`。

唯一勘误是分别把 prior census 绑定到前者、当前重建 graph 绑定到 qualification 已发布的后者；protocol/salt/support/budget/
method/threshold/runner 全不改。repaired producer/verifier/test SHA-256=`d8966a0b...b9be` / `d915167b...3fd4` /
`10d36750...a5b`，focused=`37 passed`。必须从公开修复 commit 在 fresh r2 整轮重跑；详见
`phase1/实验记录/2026-08-29/RunSplitBreadthParetoFalsification_v1_r1失败与Fingerprint勘误.md`。

勘误 commit=`6cdcc928b3b654a8c7df31999cc3e332bccb0269` 的 fresh r2 已权威完成。两折 support 全过且
pair/endpoint/parent/run overlap=`0/0/0/0`；producer A/B 逐字节一致、non-importing verifier A/B 全字段 exact，focused/full=
`37/1588 passed`（47 warnings），forbidden/network/credential filename/blob=`0/0/0/0`。result/verifier SHA-256=
`f1d8054c...e042` / `9025f2e5...991b`，formal manifest=`223549d3...5d77`。

fold1 七门全过；fold0 breadth/parent/anti-dominance 全过，但 integrated yield=`274<276` 且 pointwise only=`4/6`，后两预算
分别 `58<59,67<68`。固定分类因此是 **`POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE`**；不得用 fold1、median
tie seed 或降门 rescue。仍可描述的稳定形状是 fold0/fold1 task integral=`164/96,186/122`、run integral=
`262/191,239/198`，而 yield cost 为 `-0.724637681159%/0%`：这是 small-yield-cost / large-breadth tradeoff，不是 free Pareto。

下一步 development 改成 yield-guarded breadth optimization：每个 nested checkpoint 将 topology-only closed-edge yield 硬约束
为至少 uniform-edge median，再最大化 task/run coverage；当前图只做开发，必须在未见 graph 上另冻确认。正式包见
`phase1/results/historical_run_split_breadth_pareto_20260829_6cdcc92/`，详见
`phase1/实验记录/2026-08-29/RunSplitBreadthParetoFalsification_v1_正式裁决.md`。

公开结果 commit=`a38b6f2f299b09a384f2f4a1edc290f97548d82d` 的 fresh detached post-push 也已完成：13 个正式包成员、
result/verifier SHA 全精确，focused/full=`37/1588 passed`，credential filename/blob=`0/0`，remote manifest=
`8aca13de...8cf1`；prospective values/senior test 未读。详见
`phase1/实验记录/2026-08-29/RunSplitBreadthParetoFalsification_v1_PostPush回执.md`。

0IQ 后的 yield-guarded feasibility development 已得到一个窄正结论：把既有逐点 yield、task/run breadth、terminal parent 与
anti-dominance 七门全部编码为同一 nested feasibility contract 后，fold0/fold1 均找到 witness。integrated
closed-edge=`276/276,262/259`，同时 task=`138/96,167/122`、run=`248/191,240/198`；七门两折全过。
result A/B SHA 均为 `e4383194...191d` 且逐字节一致，non-importing aggregate verifier=`c3680fb2...6a2d`；single-CPU
wall=`27.33s`，access/network hits=`0/0`。这只证明已读历史图的联合可行性，未私下重算 endpoint witness，也不是 future
confirmation、predictor accuracy 或 search utility。下一步须在下一张未见且 identity/run-disjoint graph 前先冻 private-witness
双实现。详见 `phase1/实验记录/2026-08-29/YieldGuardedBreadthFeasibility_v2_开发裁决.md`。

公开开发包 commit=`e816a5d8909fbb1d2bd379e625d6a0ec3b419020` 的 fresh post-push r2 已通过：package=`9/9`，
self-test=`PASS`，focused/full=`6/1594 passed`，credential filename/blob=`0/0`，result/verification SHA 保持
`e4383194...191d` / `c3680fb2...6a2d`，remote manifest=`13c84f02...702c`。r1 因 runner 漏 `PYTHONPATH` 在
self-test import 前失败，原样保留且不算通过。详见
`phase1/实验记录/2026-08-29/YieldGuardedBreadthFeasibility_v2_PostPush回执.md`。

## 0IP. 2026-08-29 独立图未确认大幅 yield 增益；出现 breadth-at-near-equal-yield 新假设

0IN 的全局 v1 失败完整保留；新假设明确降为 post-discovery 的稀缺标注区间，不声称全预算优势。0IO 的独立 residual 已知
aggregate=`539 pairs / 1036 endpoints / 505 parents / 190 runs / 36 tasks / 505 components`，但其 acquisition yield、breadth、
method curves 在本协议冻结时均未读取。按 endpoint 总数固定 `[1..6]/32` 向下取整 budgets=`32,64,97,129,161,194`，
每 seed 只允许一条 nested trajectory。

primary=`balanced_closure_greedy` 对能利用 endpoint reuse 的强 `uniform_edge`；固定 uniform/tie seeds=`256/32`。trajectory
六点积分的最差 tie seed 须达到 uniform trajectory-integral 中位数的 `6/5`，逐点 median wins≥`5/6`，终点 yield≥`11/10`，
再过 parent/task/run breadth=`2/3,3/4,3/4` 与 task/run anti-dominance=`1/3,1/10`；所有门缺一不可，高预算诊断不得 rescue。

protocol SHA-256=`69db0331...9581`；producer 与 non-importing verifier 绑定两套既有 graph/acquisition engines，synthetic=
`29 passed`（新测试 7）。只读 unordered topology，senior test、orientation/gap/grade/outcome/code/prediction/runtime 和全部
prospective values 禁用；输出 aggregate-only，GPU/API/model-fit/base-update=`0/0/0/0`。只有公开冻结 commit 的 exact-SHA
formal 才能读结果。详见 `phase1/实验记录/2026-08-29/IndependentLabelScarceYieldConfirmation_v1_预注册.md`。

公开冻结 commit=`c7148fbc40ace86441248f7551c3c9b6637b547e` 的 formal 已完成。uniform trajectory-integral median=
`341`，balanced tie minimum/median/maximum=`343/353/382`；最差仅为 baseline 的 `1.0058651026392962`，未达 `6/5`。
逐点 strict median wins=`4/6`，终点 minimum yield=`99` 对 baseline median=`99`，也分别未达 `5/6,11/10`。因此固定
分类是 **`HISTORICAL_INDEPENDENT_LABEL_SCARCE_FULL_EXECUTION_YIELD_NOT_CONFIRMED`**，不得降门或删相等点。

六个预算上最差 balanced yield 都不低于 uniform median；终点 balanced median yield/task/run/parent=`103/36/94/94`，
uniform median=`99/27/70/96`。这是结果后形成的 **yield non-inferiority + task/run breadth superiority** Pareto 假设，不能
救回 v1；只有在第三个未见图上先冻新门才可确认。producer/verifier A/B 各自逐字节一致且独立全字段 exact，result/verifier
SHA-256=`aea7a45b...622d` / `13b70a87...1d63`，focused/full=`29/1580 passed`（47 warnings），forbidden/network/
credential filename/blob=`0/0/0/0`。正式包见
`phase1/results/historical_independent_label_scarce_yield_20260829_c7148fb/`，详见
`phase1/实验记录/2026-08-29/IndependentLabelScarceYieldConfirmation_v1_正式裁决.md`。

## 0IO. 2026-08-29 b1/b2 因物理 run 嵌套关闭；senior-0819 独立残余图资格门已权威通过

0IN 后先做 identity gate、没有读取 b1/b2 acquisition curves。Python 与独立 PowerShell census 逐项一致：b0--b1 的
pair/endpoint/parent/run overlap=`848/1307/589/140`，b0--b2=`677/1024/457/105`，b1--b2=
`690/1042/465/105`。b1/b2 总 runs 恰为 `140/105`，即 100% 已在 b0；它们是高度嵌套 budget variants，不能充当
外部 replication，故该路线在 curve readout 前关闭。

新的、仍未 readout 的资格门只检查已认证 senior-0819 **train** direct-sibling core 是否存在严格独立残余图；318 条历史
test core 禁止使用。固定剔除任一 endpoint/parent identity 或 physical run 与 v11 b0 重合的 row，再要求 residual
pairs≥500、retention≥1/2、endpoints≥500、parents≥250、runs≥75、tasks≥15、task/run share≤1/3/1/10，且四层 overlap
与 duplicate/reverse conflict 均为 0。threshold、residual rule、输入 SHA 与 credential-first safe-Cards receipt 已在任何
senior crosswalk 前写入 `phase1/historical_independent_sibling_graph_gate_v1.json`；synthetic=`8 passed`。

本门只决定是否有独立历史图可供**下一份**结果前 acquisition protocol，不运行 curve、不证明 label efficiency/critic effect/
search utility。producer 只输出 aggregate/fingerprint；独立 non-importing verifier 与固定 formal runner 已在 crosswalk 前
补齐，focused synthetic=`15 passed`，只有其公开冻结提交通过 exact-SHA formal 后才允许读取 aggregate。详见
`phase1/实验记录/2026-08-29/IndependentSiblingGraphGate_v1_结果前冻结.md`。

第一次 formal（commit=`f2f5469...`）已完成 producer/verifier A/B、逐字段 exact 与完整测试，固定分类 readout 为
`HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE`；但最终 blob scanner 把 `task-...` 内部的 `sk-` 当密钥前缀，
在三个既有 CURRENT_DIRECTION 行误报并以 `FAILED_RC=90` 退出，故没有 `COMPLETE`、不得作为权威 formal。protocol、
producer、verifier、输入和任何 gate 均不改；只允许给 `sk-` 增加非字母左边界、提高最小长度并加入正/负 self-test，随后
从公开修复提交整轮重跑。r1 producer/verifier SHA-256=`ea66df81...fa18` / `6f7c3a3c...0c8a1` 原样保留。

公开 scanner 修复 commit=`7ad83d2afa16c30df1464bdbe5fbb17ac16ac7c4` 的 fresh r2 是唯一权威 formal：producer/
verifier A/B 各自逐字节一致，独立 verifier 全字段 exact；result/verifier SHA-256=`ea66df81...fa18` /
`6f7c3a3c...0c8a1`，focused/full=`15/1573 passed`（47 warnings），forbidden/network/credential filename/blob=
`0/0/0/0`。固定分类为 **`HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE`**。

senior train core=`952 pairs / 1782 endpoints / 847 parents / 327 runs / 37 tasks`；严格 EP+run exclusion 后 residual=
`539 / 1036 / 505 / 190 / 36`，pair retention=`77/136`，与 v11 的 pair/endpoint/parent/run overlap=`0/0/0/0`，
duplicate/reverse conflict=`0/0`，task/run 最大 share=`58/539,2/49`，八个 integrity 与八个 support gates 全过。
这只是独立历史人口资格正结论，不是 acquisition effect。图有 505 components、endpoint degree max=4，下一步若继续必须在
读取 residual curves 前另冻 label-scarce confirmation，且不得用高预算诊断救回。正式包见
`phase1/results/historical_independent_sibling_graph_gate_20260829_7ad83d2/`，详见
`phase1/实验记录/2026-08-29/IndependentSiblingGraphGate_v1_正式裁决.md`。

发布 commit=`9a8ab7e4ecfd9d43f006a83f5eb891468e6a4251` 随后通过 fresh detached post-push：14 个 changed files、
11 个 package members、producer/verifier SHA 全部精确；focused/full=`15/1573 passed`（47 warnings），credential
filename/blob=`0/0`，prospective values/senior test 未读。r1 因误把整个 `phase1` 当 pytest root 收集命令行脚本而无
`COMPLETE`；r2 只改为正式 `phase1/tests`，权威 manifest=`8d8865d8...840b`。详见
`phase1/实验记录/2026-08-29/IndependentSiblingGraphGate_v1_PostPush回执.md`。

## 0IN. 2026-08-29 Tree Node → Sibling Label Yield 低预算正信号明确，但 v1 总门失败

0IM 的 frozen b0 formal 已完成。task/run-balanced closure greedy 对强 `uniform_edge` 基线在 endpoint budget=512/1024
的 closed-edge median 为 `422/285`、`806/628`，相对高 `48.070175%/28.343949%`，且这两个预算的 yield、breadth、
task/run anti-dominance 单预算门均通过；六个预算有五个 balanced median 更高，trajectory consistency 也过门。

但第三个预注册 headline budget=2048 只有 `1479/1420=1.041549296`，最差 tie seed=`1470`，未达到固定 `6/5`；4096
预算还为 `3163/3222`。因此必须保持分类 **`HISTORICAL_GRAPH_AWARE_FULL_EXECUTION_LABEL_YIELD_NOT_ESTABLISHED`**，
不得删除高预算、降门或用事后看到更强的非均衡 closure secondary 替换 primary。允许的窄诊断是 topology allocation
可能只在 label-scarce regime 有优势，并存在 yield--balance 权衡；下一步若继续，只能把 b0 当 discovery，在 acquisition
curves 尚未读取的 train:b1/b2 上先冻按 fraction 的外部确认，且先核验跨预算身份独立边界。

producer/verifier A/B 各自逐字节一致，result/verifier SHA-256=`dad4197b...b1e2a` / `82d20082...453cc`；独立 verifier
逐字段 exact，focused/full=`7/1558 passed`（47 warnings），network/prospective opens/row identities=`0/0/0`，
GPU/API/model-fit/base-update=`0/0/0/0`。正式包见
`phase1/results/tree_node_label_yield_v1_20260829_ecce970/`，详见
`phase1/实验记录/2026-08-29/TreeNodeLabelYield_v1_正式裁决.md`。

## 0IM. 2026-08-29 Tree Node → Sibling Label Yield 已在真实 acquisition curve 前预注册

防撞后不把 active ranking、graph active learning、active testing 或 NAS acquisition 当 novelty。允许验证的窄结构问题是：
固定 generator 已知树拓扑时，一次**完整** endpoint execution 返回绝对 grade，并可同时闭合多个 sibling pair training
labels；这不是旧多保真、search lookahead 或底座更新。

protocol=`phase1/tree_node_label_yield_v1.json` 已固定 historical v11 train:b0 的 4,263 lineage-direct sibling edges、
5,499 endpoints 和 exact normalized input SHA；算法只能读 unordered endpoint/parent/task/run，禁止 orientation/gap/
outcome/code/prediction。primary 为 task/run-penalized closure greedy 对共享 endpoint 的强 `uniform_edge` 基线，固定 6 个
endpoint budgets、64 random seeds、8 tie-sensitivity seeds及 yield/breadth/anti-dominance 四门。全过也只允许称历史
full-execution label-yield feasible；downstream critic fit、API weighting、predictor effect 与 search utility 均须另冻协议。
当前真实 curves 未运行，GPU/API/model-fit/base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/TreeNodeLabelYield_v1_预注册与防撞.md`。

## 0IL. 2026-08-29 full-context v2 得到精确平衡 panel，并通过第二实现逐字段复验

v2 在 metric-independent eligibility readout 前只删除全库不存在的独立 metric-name 行；其 fresh formal 得到八个固定
strata 的 eligible counts=`86/72/58/102`（decision）与 `103/118/80/279`（value hardware-time），first-feasible
seed=0。固定选择恰好 64 pairs、64 physical runs、29 tasks、128 endpoints，每 stratum=8、每 run≤1、每 task≤4、
endpoint duplicate excess=0；private panel/aggregate receipt SHA-256=`a9d9f1df...be1` / `8736be6a...968`。

公开 commit=`932ef387439c1f3a27ec0ec358bc986226f81bae` 的独立 verifier 不 import builder/judge，从五个 immutable
historical inputs 重建 eligibility、seed、全部私有行和**整份** aggregate receipt，双跑逐字节一致；result SHA-256=
`4ab25eaa...3a5`，focused/full=`14/1551 passed`（47 warnings），network/prospective opens/private-value emission=
`0/0/0`。r1 的 direct-file module-path import failure 无 COMPLETE，r2 才是唯一 formal。该结论只升级为
`METRIC_INDEPENDENT_EXACT_PANEL_FEASIBLE`：证明历史 full-context evaluator 诊断可执行且可审计，不证明模型准确率、
predictor scaling、label efficiency 或 search utility；API/GPU/model-fit/base-update=`0/0/0/0`，live call 仍未授权。
详见 `phase1/实验记录/2026-08-29/OpenRouterFullContext_v2_结构可行性与独立复验正式裁决.md`。

发布 commit=`845751f05016f6093f7be3a1bfe57af811413ee3` 随后通过 fresh detached post-push：7 个 changed files
与预期集合精确相等、4 个 package manifest members 全过，aggregate/verifier SHA 不变，full=`1551 passed`
（47 warnings），filename/blob secret、network、forbidden prospective opens=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/OpenRouterFullContext_v2_PostPush回执.md`。

## 0IK. 2026-08-29 full-context v1 已结构 KILL；v2 只删除全库不存在的 metric-name 行

metric-recovery r4 仍八个 strata eligible=0，故 v1 固定分类为
`RUN_TASK_METRIC_CONSENSUS_RECOVERY_PANEL_INFEASIBLE`，不得缩配额或继续 fallback。独立 verifier commit=
`7b04739...5662`、result=`85a3c828...6379` 证明 845 runs / 40,950 Cards 中非空结构化 metric=0；2,208 endpoints、
174 referenced run-task keys 也全无 consensus，network/prospective opens=`0/0`。

在任何 metric-independent eligibility readout 前，v2 amendment 只删除不可存在的单独 metric-name 行且不猜/查/alias；
完整 task description、higher/lower direction、client/hardware/two timeouts/full code 仍保留。其余输入、2 panels、4×8、
direct sibling、same-run exact-resource、run/endpoint/task caps、模型/双方向/隐私/成本全部继承 v1；若仍不可行就终止，
不设 v3 fallback，仍不授权 API。详见
`phase1/实验记录/2026-08-29/OpenRouterFullContext_v1_结构终局与v2表示协议预注册.md`。

## 0IJ. 2026-08-29 full-context panel 的 endpoint metric 缺失已触发冻结勘误，不改样本规则

原协议 commit=`8ead91f...aedf` 后，r1 因无关 LFS 404、r2 因 endpoint `task.metric` 为空、repair commit=
`c06a77b...3bc8` 的 r3 因八个 strata eligible=0 依次 fail-closed，均无 panel/COMPLETE/API call。aggregate census=
`7a3ac11f...8647` 证明 2,208 个唯一 endpoint 只有 metric 字段全缺；task description/direction、client、hardware、两个
时限和 code 缺失均为 0。

在 run-level metric availability 未见时，`openrouter_full_context_metric_recovery_erratum_v1.json` 只允许从 immutable Cards
中同 `(physical run, task.name)` 的所有非空 metric 做 exact unique consensus 回填；0 个或多值均拒绝，不猜、不查网页、
不 alias。两个 panel、4×8 配额、gap/run/endpoint/task、resource stratum、模型/双方向/隐私/预算均不改；恢复后任一桶仍
不足 8 就正式 infeasible，不再追加 fallback。详见
`phase1/实验记录/2026-08-29/OpenRouterFullContext_v1_结构失败与MetricRecovery勘误预注册.md`。

## 0II. 2026-08-29 学长 0828 NEXT 已收束为全上下文 evaluator 诊断；不授权底座微调或付费调用

学长 outcome commit=`f534114...c8ad` 的三项 NEXT 经防撞与项目硬约束审查：便宜强模型复核历史 reward/decision pair
与 predictor benchmark 直接相关，保留为 full-context、双方向、exact-resource-stratum 的历史诊断；“在简单任务上微调
Qwen 生成器”会更新 agent 底座，违反本项目 hard NO，按原提法不实施；3×8 H200 trajectory 只接受学长提供的脱敏导出，
不得使用 outcome 中带访问凭据的 W&B 链接，该凭据应撤销/轮换并清理历史。

广义 generator-verifier 自演化 novelty 已被 ACE/ReVeal/CURE/V-STaR 等覆盖。允许继续验证的窄正方向是：固定 generator，
在昂贵、延迟、任务异质的真实 MLE execution labels 下，用独立 verifier 改善可审计 label allocation/efficiency，并最终由
未触碰外部 cohort 确认。`openrouter_full_context_judge_v1.json` 先冻结两个 32-pair 历史 panel、4 个 task-unit-gap 桶、
run/endpoint/task 限制、完整不截断 prompt、4 个 exact model IDs、双方向与 2/10 USD stop；本次只实现和 mock 验证，
`live_calls_authorized_by_this_freeze=false`，没有 API/GPU/model fit/base update。详见
`phase1/实验记录/2026-08-29/Senior0828_NEXT_防撞与安全执行裁决.md`。

## 0IH. 2026-08-29 Target-522 order addendum 冻结提交通过公开源复验与提前读取拒绝测试

冻结 commit=`0719d075d584481e72a3d67dd591a156bbaaa62b` 在 fresh detached worktree 通过 focused/full=
`30/1537 passed`（47 warnings），protocol/producer/verifier/test/runner hashes 与预注册逐项一致，commit filename/blob secret
hits=`0/0`。selection 与 upstream formal 均 `COMPLETE=false` 时，固定 runner 在 strace 下 `rc=1`，没有创建 future output/
worktree，candidate/profile/snapshot/result opens=`0`；因此该控制确实在结果前冻结且无法提前 readout。

16-member freeze manifest=`f6a7f53a3f3f31a96089b98c66c247340bef6e5a37bba14d96e87fc1d6ca0f6b`。既有三个 watcher 未修改、
未重启、未复制，没有启动 addendum watcher；prospective values/Target-522 profile/raw archives 未读、无 row-level release，
GPU/API/model-fit/base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/Target522_SelectiveParent_MaxPriorStep前瞻附录_冻结复验回执.md`。

## 0IG. 2026-08-29 Target-522 max-prior-step 前瞻附录已在 candidate 前冻结

LATEST 仍为 `887491a...62697`，Target-522 selection/lineage/selective 三个既有 watcher 均 `complete=false, failed=false`；
candidate、increment profile、content result、max-prior-step 与 paired/breadth values 均未见。在此窗口冻结 protocol=
`81df44e9194fb194611d6ffb7f3fba6c0a3fd1d7d2c0aa1ba6be19d33f84ce87`：未来只在固定 content-selected rows 上对比
有效 `max_prior_step`，support=`selected≥500, comparable≥400, coverage≥9/10`，aggregate=`error ratio≤1/2,
content-only/step-only≥2`，再过匿名 task/run breadth 与 anti-dominance。

关键 fail-closed 顺序是：integrity failure 优先；若 upstream Target-522 selective-parent 不是 strongest classification，则本附录
固定报 `PRIMARY_NOT_CONFIRMED`，绝不能用 order advantage 救回；随后才判断 support/aggregate/breadth。development/forward
不混池，无 threshold/task/population/candidate/formal-root rescue。producer/verifier 独立重建，focused tests=`30 passed`；固定
runner 不接受 roots 参数且当前未启动，也未新增 watcher。prospective values/Target-522 profile/raw archives 未读，
GPU/API/model-fit/base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/Target522_SelectiveParent_MaxPriorStep前瞻附录预注册.md`。

## 0IF. 2026-08-29 order-baseline falsification 发布提交已通过 fresh post-push

发布 commit=`c030d362e13e1a5f1545fd4d5e743e7c98cc15ae` 在 fresh detached worktree 复核 package manifest=`25/25`、
focused/full=`13/1528 passed`（47 warnings）；887 result/verifier 重建均与发布包逐字节相同。正式 integrity-fail 与有效
max-prior-step 的强描述性正证据同时保留，invalid manifest-order baseline 未用于救回；forbidden open/network、commit
filename/blob secret hits=`0/0/0/0`。

r1 在上述科学与测试检查全部通过后，因 line-delimited Git 中文 quoted path 令 blob scanner 退出，`FAILED_RC=1` 原样
保留。r2 只修复操作扫描器为 NUL-delimited path，诊断 old quoted/failures=`1/1`，修复后读取 `29/29` changed blobs、
secret hits=0，没有重跑或改变科学结果。权威 post-push manifest=
`4ab54a464fd0a9d9da8c656f6f7fc12f468e57a3ec17ec5f36161d8abc19e438`。prospective values/Target-522 profile/raw archives
未读、无 row-level release，GPU/API/model-fit/base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/SelectiveParentRecovery_因果顺序基线Falsification_PostPush回执.md`。

## 0IE. 2026-08-29 有效 max-prior-step 对照被内容方法大幅击败，但正式双基线审计须完整性 fail-closed

在任何 order-baseline readout 前冻结的 protocol=`d6553882...f23e` 使用 887 已发布证书完全相同的 time split、候选集、
阈值与 `2691` 个 content-selected test rows。有效 `max_prior_step` 对照全覆盖：content/step errors=`7/492`，配对
content-only/step-only correct=`488/3`；满足最小 discordance 的 task/run=`19/96`，两层净内容优势比例均为 1，最大
单 task/run discordance share=`118/491,49/491`，全部预注册 aggregate/breadth 门通过。因而允许的正面描述是：在该
development split 上，identifier-erased content 包含简单 step recency 不能解释的 recorded-parent 信息。

但第二个预注册 primary `nearest_prior_manifest_row` 的因果前提不成立：`10895` 个 parent-present edges 中有 `5449` 个
parent 不在 child row 之前，且 selected comparable coverage=`2034/2691=226/299<9/10`；generation timestamps 又是
`10895/10895` 相等、覆盖 0。因此正式分类必须保持 **`DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL`**，
不得结果后删除该 baseline、改门或用其极差数字救回 strong pass。正确后续是在未见 Target-522 candidate profile 时另冻
forward addendum，把有效 max-prior-step 作为 mandatory confirmation control；887 不重跑改分类。

source commit=`cb74a936204a44acbf957e9b9345e34c66b49aab`；result/verifier SHA-256=`34412b52...7532` /
`a9cf85a8...8509`；producer/verifier A/B 各自逐字节一致、独立字段全相等，focused/full=`38/1522 passed`（47 warnings）。
r1 在 scientific output 前因 module path 退出，r2 唯一权威；formal/postflight manifests=`0a3d3d27...659` /
`bb6ab5cd...06ed`。prospective values/Target-522 profile/raw archives 未读、无 row-level release，GPU/API/model-fit/
base-update=`0/0/0/0`。详见 `phase1/实验记录/2026-08-29/SelectiveParentRecovery_因果顺序基线Falsification_正式裁决.md`。

## 0ID. 2026-08-29 Selective Parent Recovery 因果顺序基线反证已在 readout 前冻结

887 的 content certificate 已知，但 `max_prior_step`、`nearest_prior_manifest_row`、secondary generation-time 与所有
paired disagreement/breadth values 在冻结时未见。机器协议固定同一 `2691` selected population，两个 primary baseline
各自须 coverage≥`9/10`、comparable rows≥`2000`，再过 content/order error≤`1/2`、content-only/order-only wins≥`2`
及匿名 task/run breadth/anti-dominance；任一 integrity failure 优先于所有数值。它是 post-result development falsification，
不是原始预注册或 Target-522 confirmation。详见
`phase1/实验记录/2026-08-29/SelectiveParentRecovery_因果顺序基线Falsification预注册.md`；正式裁决由 0IE 覆盖。

## 0IC. 2026-08-29 relation-integrity contrast 发布提交已通过 fresh post-push

发布 commit=`e54560778de2c4294e3f8cbcb865caf5168e883c` 在 fresh detached worktree 复核 package manifest=`21/21`、
focused/full=`39/1515 passed`（47 warnings），contrast/verifier 重建均与发布包逐字节相同。commit filename/blob secret
hits=`0/0`；known-result、gate-schema 不可直接比较和 canonical support failure 三项限制均保留。post-push manifest=
`c56eeff476262fe5d7a0f11098f1ca1cac7393a8998691ef11e0c84922fcf4b3`。prospective values/raw archives 未读、无
row-level release，GPU/API/model-fit/base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/DecisionRelationIntegrityContrast_v1_PostPush回执.md`。

## 0IB. 2026-08-29 两个历史资源家族证明 relation-integrity 审计具有诊断区分力，fixed quarantine 可验证修复

这是所有 source results 已知后的 aggregate-only descriptive synthesis，不是预注册确认。exact source commit=
`f66cbdf10989da2e1242964259f31fb8d399db3e` 的 fresh-detached formal 将三份已发布独立证书组成同一机器链：canonical
v11 的 `8107/8107=1` rows 均为 lineage-direct，hard gates=`15/15`；mixed 0819 仅 `1270/7644=
0.16614338042909471` 是 verified direct sibling，`2119` 是 same-run non-sibling、`4255` 是 cross-run，taxonomy hard
gates=`13/15` 且 train/test referenced-run overlap=`96`。固定 direct-sibling quarantine 后 core/quarantine=
`1270/6374`，repair certificate hard/support=`16/16, 8/8`，referenced-run overlap=`0`；`743/743` parent-partition
mismatches 全在 cross-run stratum。

因此允许的正资产是：审计栈在这两个历史家族上不是 constant-accept/constant-reject，并能给出 deterministic、结构定义、
与模型结果无关的 repair path。三套 frozen gate schemas 相关但不相同，不能把 `15/15,13/15,16/16` 当共同标尺，不能称
calibrated sensitivity/specificity、一般审计方法首创、因果资源差异或总体估计；canonical lineage-direct 也显式包含 528 个
orphan-parent lineage-certificate rows，parent-present retention 另报 `7579/8107=0.93487109905020349`。canonical 唯一
support failure `frozen:b2.maximum_single_run_pair_share` 原样保留（35/36），不得隐藏。

producer/verifier A/B 各自逐字节一致，contrast/verifier SHA-256=`96ce1165...a1b4` / `1779e696...5ec2`；focused/full=
`34/1510 passed`（47 warnings），三包 manifest 共 35 个成员全过，forbidden open/network/credential=`0/0/0`。formal/
postflight manifests=`ab2b6fa69...7af54` / `b50a9a29...57b9e`；发布包见
`phase1/results/historical_relation_integrity_contrast_20260829_f66cbdf/`，package manifest=`36320ae5...5c1e`。
prospective values/raw archives 未读、无 row-level release，GPU/API/model-fit/base-update=`0/0/0/0`。详见
`phase1/实验记录/2026-08-29/DecisionRelationIntegrityContrast_v1_正式裁决.md`。

## 0IA. 2026-08-29 Evidence Index v9 发布提交已通过 fresh post-push 复验

发布 commit=`8f82a495ef05f1834432dd2c6229163b99e473e8` 在 fresh detached worktree 重新核对 24 个 package members、
focused/full=`31/1501 passed`（47 warnings）、index/verifier 双重重建逐字节一致，commit filename/blob secret hits=`0/0`。
post-push manifest=`6cb8d6681083405fccc7b1ab47677b844ad2df0884a79062f180aecf73e150ba`；provisional status 与
`frozen:b2.maximum_single_run_pair_share` 唯一失败均保留。prospective values/raw archives 未读、无 row-level release，
GPU/API/model-fit/base-update=`0/0/0/0`。详见 `phase1/实验记录/2026-08-29/DecisionCorpusEvidenceIndex_v9_PostPush回执.md`。

## 0HZ. 2026-08-29 Evidence Index v9 已用 lineage-direct certificate 修复 v8 的 sibling provenance 缺口

Evidence Index v8 的 `decision_corpus` entry 绑定 v1 run-map audit；该 artifact 没有读取 `lineage.parent_id`，因此证据不足以
单独支持 declared-parent direct-child relation。v9 是已知结果后的 reporting/provenance 修复，不冒充新预注册实验：只替换
该 1 项，其余 15 项逐对象不变，first-960 provisional 状态也原样保留。

新 entry 绑定 0HY 的 producer、独立 verifier 与 source bindings，共 3 artifacts / 51 assertions；机器保留 8,107 rows
全部 lineage-direct、parent-present core=7,579、orphan tier=528、15/15 hard gates 与 35/36 support gates。唯一失败仍是
`frozen:b2.maximum_single_run_pair_share`，不得被新 index 隐藏或升级。builder/verifier A/B 各自逐字节一致，index/verifier
SHA-256=`b2d88479...11ff6` / `2319c028...85e6d`；focused/full=`37/1496 passed`（47 warnings），CPU threads=1，
forbidden opens/network/credential filename/content=`0/0/0/0`，内容扫描器 rc=1 明确表示正常无命中。

r1 fetch rc=128、r2 资源守护中断 rc=143、r3 因 `rg` 不存在却被旧 `|| true` 错写成空命中而正式作废，均进入发布包；
r4 是唯一权威 formal。formal/postflight manifests=`2cc3b1b9...e854a` / `fb3cb40c...92b58`。正式包见
`phase1/results/decision_corpus_evidence_index_v9_20260829_f108812/`。该资产不增加一般 evidence-index novelty，不证明
predictor effect/scaling/search utility，不生成 row-level release；prospective values/raw archives 未读，GPU/API/model-fit/
base-update=`0/0/0/0`。

## 0HY. 2026-08-29 v11 全部 lineage-direct sibling 正式认证；parent-complete core 总门仅一项小样本集中度失败

0HX 的冻结 protocol 在 exact public commit=`25148420ee457018a1ee3740c4a1c42da830610d` 上完成 fresh detached
formal，分类必须保持为 **`HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT`**。15/15 hard gates
全部通过：九个 set 共 8,107 行全部为 lineage-direct siblings，其中 parent-present strict core=`7579`，parent Card 被
裁剪但 endpoint lineage 可证的 orphan tier=`528`，same-run non-sibling/cross-run=`0/0`。row task/run/split/budget
violation、duplicate/reverse conflict 均为 0；同 budget train/frozen 在 unordered pair、endpoint、parent 与包含 parent
的 referenced physical run 四层 overlap 全为 0。

36 个 support gates 过 35 个。唯一失败是最小的 `frozen:b2`：strict core 最大单 run share=
`52/254=26/127=0.20472440944881889`，略高于预注册上限 `1/5`，故不得事后升级总分类。其余五个 primary sets 全部
六门通过；既有 headline `frozen:b0` 的 strict core=`1424/1498` pairs、`21/22` tasks、`83/92` runs、
`1929/2022` endpoints，最大单 run share=`67/356=0.18820224719101122`，全部过门。三个 frozen budgets 合计 core=
`1989/2086=0.95349952061361454`；全九 set core=`7579/8107=0.93487109905020349`。因此可守正贡献是：v11 不是
same-run proxy corpus，而是 lineage-direct sibling corpus；parent-complete curated view 的主要代价约 6.5%，b0/b1
支持宽度充分，b2 必须显式标为小样本/单 run 轻微集中，不得隐藏。

producer/verifier A/B 各自逐字节一致，独立 verifier 不 import producer并逐字段相等；focused/full=
`13/1488 passed`（47 warnings），forbidden opens/network/credential filename/content=`0/0/0/0`，remote manifest=
`117678f333d2f053e2cc29aa8ca1e34238a39e52df5444bdd491e4d0ea9d36e4`。正式包见
`phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842/`。v1 输入 root 失败、v2/v3 nested-task parser crash 与
v4 无效 parser receipt 均保留并撤回；生成器源码确认 canonical task 是 `card["task"]["name"]`，协议、population、
taxonomy、阈值和分类顺序未改。该结论不证明 predictor effect/scaling/search utility，不授权 row-level release；
GPU/API/model-fit/base-update=`0/0/0/0`，prospective values/raw archives 未读。

发布 commit=`7e625c603c8c47f433af2967f66c5a7c4b82ba0f` 随后通过 fresh detached post-push：package manifest=
`16/16`、focused/full=`13/1488 passed`，producer/verifier 与正式 A 结果逐字节相等，forbidden opens/network 与
credential filename/content=`0/0/0/0`；post-push manifest=
`4fba37aa41c7563d49b9226d80b9ecb814125972507a317992e3d79b1db0daa4`。详见
`phase1/实验记录/2026-08-29/DecisionCorpusLineageAudit_v2_PostPush回执.md`。

## 0HX. 2026-08-29 Decision-Corpus Audit Protocol v2 已在 lineage readout 前冻结

8 月 14 日的 v1 已认证九个 v11 decision sets 的 endpoint 同 physical run、可映射 parent 不跨 run，以及同 budget
train/frozen 在 pair、endpoint、parent ID、run 四层零交叉；但其 producer/verifier 都没有读取 Card
`lineage.parent_id`，故 `all_rows_true_physical_siblings=true` 只能解释为 run-map consistency，尚不能独立证明两个
endpoint 真是 declared parent 的直接 children。0HR--0HV 在学长 mixed 文件上已证明这不是形式主义风险：same-run
declared context 与 direct sibling 必须分层。

新机器协议 `phase1/decision_corpus_lineage_audit_v2.json` 已绑定 v11 Cards/run map、九个 pair files 与 v1 双 artifact，
SHA-256=`ef3aefd1534fb76d7d0a05d0fc4f4b4cbe02ceac8b183acea635b2b9c8d3c88a`。在真实 lineage readout 前固定四类：
parent-present direct sibling、lineage-verified orphan-parent sibling、same-run non-sibling、cross-run context；严格 curated
core 只保留第一类，其余显式 quarantine。15 个 hard gates 验证 direct-child/task/run/split 引用闭包、四层 train/test
隔离、零 duplicate/conflict、v1 aggregate 精确复现与 aggregate-only 输出；六个 train/frozen sets 另固定 pair/task/run/
endpoint retention≥`4/5,3/4,3/4,3/4`、最大 task/run share≤`3/5,1/5`。不得结果后改类或门。

冻结时已知 v1 counts/breadth/mapped-parent counts；未见 lineage match、relation/core counts、strict-core referenced-run
overlap、support/concentration 或 fingerprints。即使通过，也只允许称 historical v11 lineage-aware audit 与
parent-complete sibling quarantine feasible，不称 prospective/predictor/search 结果，不发布 row identities。TraceML 正式
论文、MLEvolve primary/reference edges 与 ReLoc sibling revision RM 已关闭 tree/parent/sibling/RM 的宽方法首创；当前可守
增量是 MLE decision corpus 上 direct-child + physical-run/split closure + exhaustive quarantine + 双实现 receipt 的组合。
详见 `phase1/实验记录/2026-08-29/DecisionCorpusAuditProtocol_v2_Lineage闭包预注册.md`。本节仅为冻结状态；
GPU/API/model-fit/base-update=`0/0/0/0`，prospective values/raw archives 未读。

## 0HW. 2026-08-29 outcome-blind 887 结构监控已连续续接

LATEST 仍为 `887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`。intake PID=`4008512`、WL 与
Target-522 三条 watcher、六小时 guard 均保持原实例且锁 held；没有重复启动。此前自然完成的 transition、receipt-support、
config-v2 readiness 与 Target-300 quiescent monitor 在核对旧进程为 0、锁 free、state/prior hashes 和 completion tail 后续接。

新 transition/receipt/config-v6/Target-300 PID=`4177250/4177251/4177257/4177258` 均经独立 postflight 确认为 live 且
lock held，first poll/start receipt 正常；config-v2 sidecar count=0。续接脚本 SHA-256=`9601beeb...69ae`，操作回执
manifest=`714e83ffa445328f9353beba40069d454246e88ccf8d788f9417a0776912cf5d`。只读取 PID、锁、LATEST、state/artifact
hash、结构日志尾部与 filename count；prospective values/outcomes/raw archives 未读，GPU/API/model-fit/base-update=
`0/0/0/0`。详见 `phase1/实验记录/2026-08-29/OutcomeBlindMonitor_887续接回执.md`。

## 0HV. 2026-08-29 deterministic sibling quarantine 正式通过全部完整性门

0HU 的 exact public commit=`254fc804c4904635e8f44e9121eab84b425ca6a8` 已完成 fresh detached formal，分类为
**`HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE`**。16/16 hard gates 通过：固定规则得到 core=
`1270`（train/test=`952/318`）和 exhaustive quarantine=`6374`（`5532/842`）；core train/test 在 unordered pair、
endpoint、包含 declared parent 的 referenced physical run 三层 overlap 均为 0，duplicate/orientation conflict=`0/0`，
split counts 与 fingerprints 精确匹配 0HT parent certificate。

冻结前未见的污染定位也闭环：全文件 743 条 parent-partition mismatch（train/test=`516/227`）**全部**位于 cross-run
stratum；direct sibling 与 same-run non-sibling 都为 0。因此旧文件整体失败并非要求丢弃全部 decision 资产：可用一个
确定性、结构定义、与模型结果无关的 quarantine rule 提取 run-clean historical sibling curated view。test 的 318 pairs /
29 tasks / 89 runs / 591 endpoints / 282 components 与 8/8 support compatibility 在本轮冻结前已知，只能说明 repair 后宽度
仍足够，不能包装成独立确认。

producer/verifier A/B 各自逐字节一致，SHA-256=`4f4902ce...56315` / `8b0eb843...57ca0`，独立 verifier 不导入本轮
producer 且逐字段相等；focused/full=`6/1475 passed`，parent package manifest 全项通过，forbidden opens/network=
`0/0`，formal manifest=`9a554d8c1ed3dffe5a5aa1ab7ff1579f890fa749fcbb82e545c3a2a7758d2d63`。正式包见
`phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80/`。这是数据集/审计协议的正资产，不证明
predictor effect、scaling 或 search utility；row-level release 仍未授权。GPU/API/model-fit/base-update=`0/0/0/0`，
prospective values/raw archives 未读。

证书已由公开 commit=`04ed63ebd08bc6406d863b43c93ec61f44b97126` 发布。fresh detached post-push 对 package
manifest、hard/support gates、counts、mismatch localization 与 verifier equality 复核通过，focused/full=`6/1475 passed`，
credential filename/content=`0/0`；post-push manifest=
`4e7093b20bec14cfd5a957db253812125f0620fff24123b9ad9460cb223e6d44`。

## 0HU. 2026-08-29 sibling-only quarantine feasibility 已在 closure readout 前冻结

0HT 后续不修改失败的 0HS 协议，而是另立 post-hoc repair estimand：只保留两个 endpoints 都是 declared parent 的直接
children，且 parent/endpoints 同 task、同 physical run、同 frozen split 的 rows；其余全部显式 quarantine。冻结前已经知道
三类 counts、full-file referenced-run overlap=96 和 test sibling support=318 pairs / 29 tasks / 89 runs / 591 endpoints /
282 components，因此这些不是本轮新证据；尚未直接读取 sibling-only parent-partition closure、含 parent 的 train/test run
overlap、mismatch 的 relation×split 聚合分布或 quarantine fingerprint。

机器 protocol=`phase1/senior_0819_verified_sibling_quarantine_v1.json`，SHA-256=
`f4d09f1203ba72181046ac620862eb10351736cd01a25ac3597b21e4b931b680`。16 个 hard gates 固定 core purity、exhaustive-
disjoint、所有 mismatch 被隔离、pair/endpoint/referenced-run 三层零交叉、零 duplicate/conflict、split counts/fingerprint 与
0HT 证书一致；support compatibility 沿用旧门但明确标记为冻结前已知。strong pass 只允许称 historical sibling-core
quarantine feasible，不称 prospective confirmation，不自动授权 row-level release、GPU 或 predictor effect。详见
`phase1/实验记录/2026-08-29/Senior0819VerifiedSiblingCore_隔离可行性预注册.md`。本节是冻结时状态，正式 readout 与
裁决由 0HV 覆盖；GPU/API/model-fit/base-update=`0/0/0/0`，prospective values/raw archives 未读。

结果前实现已完成：producer/verifier/test/runner SHA-256=`c23f5a43...4d04` / `58adabb2...cdd4` /
`772e1974...d4e1` / `28d882ad...c580`；focused synthetic=`6 passed`，与 0HS tests 合并=`12 passed`。独立 verifier
不导入本轮 producer，攻击测试覆盖 mismatch quarantine、aggregate-only、core reversed duplicate/conflict、support 不足、
parent certificate 与 input hash drift。尚未运行真实 closure readout。

## 0HT. 2026-08-29 relation-aware taxonomy 正式 fail closed；宽 sibling core 仅形成隔离可行性信号

0HS 的 exact public commit=`827fe55dcf03280cd8e9391d4b44c20db38484d3` 已完成 fresh detached formal。冻结分类为
**`HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL`**：15 个 hard gates 中 13 个通过；失败的是
`all_decision_endpoints_parent_tasks_and_splits_valid` 与 `train_test_physical_run_overlap_zero`。train/test unordered pair 与
endpoint overlap 仍为 0，但加入 declared parent run 的引用闭包后有 96 个 physical runs 跨 split；因此旧 7,644 rows
整体不能升级成 run-clean relation-aware benchmark，不能由子组或模型分数 rescue。

固定三类的 total/train/test 为 direct sibling=`1270/952/318`、same-run non-sibling=`2119/1620/499`、cross-run=
`4255/3912/343`；train/test relation mix TV=`578477/1880360`。同时，冻结前未见的 test direct-sibling core 有 318 pairs、
29 tasks、89 runs、591 endpoints、282 components，最大 task/run/component share=`25/159`、`7/106`、`1/53`，8/8
预注册 support gates 均过。这只形成“确定性隔离 sibling core、明确 quarantine 非 sibling/context-leaking rows”的新可行性
信号；当前仍无 row-level release，不能把本轮写成 strong-pass。

producer/verifier A/B 各自逐字节一致，SHA-256=`b75df026f...c6d3` / `d5613fe7...b66a`，独立 verifier 报
`all_aggregate_fields_equal=true`；focused/full=`6/1469 passed`，forbidden opens/network=`0/0`，formal manifest=
`68d845cc6e2801d814bcd320017bce5ae5712c2e01f94dff7a010b1195230f56`。正式包见
`phase1/results/senior_0819_decision_relation_taxonomy_20260829_827fe55/`。下一步若做修复，只能先冻结 aggregate-only
quarantine feasibility protocol，验证 sibling-only train/test 的 parent/run closure；不得事后改 0HS 门、不得自动发布 row
identities 或启动 GPU。GPU/API/model-fit/base-update=`0/0/0/0`，prospective values/raw archives 未读。

证书已由公开 commit=`9a922abbf15cc769c1867f6991423021d661c5dd` 发布。fresh detached post-push 对 package manifest、
失败门、class counts 和 verifier equality 复核通过，focused/full=`6/1469 passed`，credential filename/content=`0/0`；
post-push manifest=`35b168b81ad5488cefd967b19e3f9054c9fa4b5546cf3fdaa775611fbda6b7aa`。

## 0HS. 2026-08-29 relation-aware decision taxonomy 已在 split-specific readout 前冻结

0HR 证明 senior 0819 historical mixed benchmark 的 run/endpoint/unordered-pair 隔离、test 精确保留和 breadth 都成立，
但 frozen sibling gate 失败。为把这个失败转成可发布的 benchmark repair 资产，下一轮不看模型分数，固定把 7,644 条
decision rows 完整互斥地分为 `verified_direct_sibling`、`same_run_declared_context_non_sibling`、
`cross_run_declared_context`。前一轮已知 overall direct/same-run/same-task=`1270/7644` / `3389/7644` /
`7644/7644`；本节冻结时尚未读取 split-specific class counts、test sibling breadth、每类 dependency concentration 或
fingerprints。

protocol SHA-256=`df94c4ec6a3bb2c0856e29d148cb898d2b796cc1279800456b8f8e6108e08e32`。15 个 hard gates 先保证
input/Card/run/task/split、taxonomy purity/exhaustiveness、三层 train-test 零交叉、零 duplicate/conflict，并精确复现 0HR
overall aggregate。strongest test sibling-core 门固定为 pairs/tasks/runs/endpoints/components≥`100/10/30/150/50`，最大
task/run/component share≤`1/3`、`1/5`、`1/4`；不得事后调门或用别类/模型分数 rescue。若通过，只允许称 historical
relation-aware taxonomy 含 broad structurally verified sibling core；不把 recorded parent 升级为语义/因果真值，不把历史
test 称 untouched，也不授权 row-level release 或 GPU 重训。详见
`phase1/实验记录/2026-08-29/Senior0819DecisionRelationTaxonomy_预注册.md`。本节是冻结时状态，正式 readout 与裁决由
0HT 覆盖；GPU/API/model-fit/base-update=`0/0/0/0`，前瞻值与 raw archives 未读。

结果前实现已完成：producer/verifier/test/runner SHA-256=`f32c9a56...299e9` / `84453ca9...e787f` /
`d922222b...8a502` / `bed7ae49...06fa4`；focused synthetic=`6 passed`，与 0HR tests 合并=`13 passed`。独立
verifier 不导入 taxonomy producer；攻击测试覆盖 parent partition mismatch、support 不足、反向 duplicate/conflict 与
input hash drift。尚未运行真实 split-specific readout。

## 0HR. 2026-08-29 senior 0819 mixed pair benchmark 已冻结独立完整性审计

学长 `f534114e...` 的 0828 报告新增探索性 mixed-pair scaling/RL 汇总，但 Qwen3 容量趋势只在 seed 7 出现、seed 6
未复现，RL 也不是 matched 正结论。继续 GPU 前先把其中 1,160-row decision test 能否成为可靠 benchmark 资产单独冻结：
在结果前检查 frozen physical-run、endpoint、unordered pair 三层 train/test 隔离，decision test canonical multiset 精确保留，
declared source-union support，以及 task/run/component breadth；不计算 accuracy、scaling 或 search utility。

协议固定为 `phase1/senior_0819_pair_benchmark_integrity_v1.json`，Cards/run-split/mixed/decision/value/hardware-time 六个
Git-LFS OID 全绑定。strongest 分类要求全部 13 个 hard integrity gates 通过，并满足 test pairs/tasks/runs/endpoints/
components≥1,000/20/50/500/100，最大 task/run/component share≤1/4、1/10、1/4；任一 hard gate 失败不得由模型分数
或子组 rescue。冻结前只看过报告数字、计数和 schema，未看 overlap、preservation、component/breadth 或 source membership
readout。protocol/producer/独立 verifier/test/runner SHA-256=`8991d304...eb30` / `06d19ad9...2437` /
`712be2aa...2901` / `e98bf02f...61d8` / `7276e77a...544a`；synthetic=`7 passed`，formal 已完成，结果见本节末。

779,146,574-byte Cards 在 JSON parse 前完成 credential scan，0 命中且 safe SHA 等于原 OID；八个小输入亦为 0。
首次 v2 input root 因手抄 mixed SHA 错误在 scientific read 前 fail-closed，v3 用 LFS pointer 机器核对值重建。另发现学长
报告正文含 credential-bearing dashboard URL：未访问、临时副本已删除，维护者须撤销并清理历史；不得复制 token。
详细边界见 `phase1/实验记录/2026-08-29/Senior0819PairBenchmark_完整性审计预注册.md`。GPU/API/model-fit/base-update=
`0/0/0/0`，first-960/Target-300 值和 raw archives 均未读。

首次 post-push formal root `formal-16552c6-v1` 在 science producer 前因 runner 未切入 detached worktree 而失败：
focused=`6 passed`，full=`1455 passed, 7 failed, 47 warnings`；7 个失败均为既有测试用 `Path.cwd()` 寻找仓库时误落到
`/data/d0/y24/yzyang4`。producer/verifier A/B 四个结果均不存在。修复只把 pytest 包在 `cd worktree` 内，不改 protocol、
population、gate 或 scientific code；v1 原样保留，新 runner hash 如上，必须从新 root 重跑。

第二个 root `formal-0159f81-v2` 的 focused/full=`6/1462 passed`（47 warnings），随后 producer 在写出结果前发现冻结
gate 的前提不成立而停止：mixed line 6 不是 declared parent 的两个直接 children。随后临时匿名诊断把字符串 parent ID
与 Node 对象直接比较，错误报告 direct-child=`0`；该临时值已撤回。其同-run 计数 `3389/7644`、`1389/2563` 不受此
类型错误影响，并被正式双实现复现。没有删除或改宽 gate；只把逐行 exception 改为匿名 violation 计数，使第三个新 root
按原协议输出 `GATE_FAIL`，并把跨 run test pair 的 run contribution 固定为 incident-run count。producer/verifier/test
hash 因这一 fail-reporting 修复更新为上文值；protocol 和 runner hash 不变，v2 原样保留。

第三个 root `formal-4a84780-v3` 已正式完成，分类为 **`HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL`**。13 个 hard
gates 中 12 个通过；唯一失败的是“全部 decision pairs 同 recorded parent 且同 physical run”：decision 的
direct-child/same-run/same-task=`1270/7644` / `3389/7644` / `7644/7644`，mixed 中 2,563 条 decision-schema rows 为
`537/2563` / `1389/2563` / `2563/2563`。因此不得称 sibling-decision benchmark。

同时形成正的 benchmark 资产：mixed train/test 的 unordered pair、endpoint、physical-run overlap 全为 0，mixed test 与
decision test canonical multiset 精确相等（各 1,160 rows），duplicate/orientation conflict=`0/0`。八个 breadth gates
全过：test=1,160 pairs / 38 tasks / 173 runs / 1,705 endpoints / 724 components，最大 task/run/component share=
`21/232` / `43/1160` / `23/1160`。14,715 个 mixed-train rows 全有 declared source support，但 490 rows 同时属于两个
source pools，actual sampling origin 不可反推。producer/verifier A/B 逐字节一致，focused/full=`7/1463 passed`，
forbidden opens/network=`0/0`，formal manifest=`f5483cf2...47b17`。这只认证隔离、精确保留、支持面广的**历史 mixed pair
benchmark**，不升级 seed-specific scaling，不把周期使用过的 test 称 untouched。正式包见
`phase1/results/senior_0819_pair_benchmark_integrity_20260829_4a84780/`；GPU/API/model-fit/base-update=`0/0/0/0`，
前瞻值与 raw archives 未读。

证书已由公开 commit=`e9e20c2552c97e11794069d8f9b73b791fec5a05` 发布。post-push v1 是 checkout 前环境顺序失败；
v2 因未固定 BLAS 线程在登录节点过度并行而被精确 TERM；v3 虽通过 package 和 `7/1463` tests，但 Git 中文路径 quoting
使 blob scanner 漏扫一个文档，故 superseded。NUL-safe v4 对每个 blob 先 `cat-file`、再显式检查 pipeline rc，package
manifest=`9/9`、focused/full=`7/1463 passed`、credential filename/content=`0/0`，权威 post-push manifest=
`013487f0d70ec27b73f6b1ef82bdf781d88d46985d0433efb7dacb4cbbd2db5a`。v1–v3 均保留，不能冒充权威成功。

## 0HQ. 2026-08-29 fixed-margin selective parent recovery 已冻结 Target-522 真前瞻确认

0HP 的开发正结果仍在同一 disclosed snapshot 内，因此新的 strongest next step 已在 Target-522 candidate/profile 未见时
锁定：只用既有自动 selection 的首次 crossing，相对 887 的至少 87 个完整新增 physical runs；固定复用 train-only
阈值 `1006/16929`，未来数据不重选阈值、不重平衡任务、不换表示，也不允许累计 887+future population rescue。冻结巡检
时间为 `2026-08-28T16:10:51Z`；当时 LATEST 仍为 887，selection `READY/COMPLETE/FAILED_RC/candidate.tsv` 均不存在，
PID=`4047654` 存活。

最强前瞻门要求 ambiguous≥1,000、accepted≥500、wrong alternatives≥5,000、conditionable tasks/runs≥8/60，precision≥
`49/50`、coverage≥`1/2`，selective error 不超过无 reject error 的一半，并通过固定 task/run breadth 与 anti-dominance。
三个 wrong-pointer 分母仍分别报告。即使通过，也只支持 MLE Decision Corpus 的可选
`suggested_parent + confidence + provenance` 自审计层；不验证 orphan/语义 ancestry，不申通用 selective/lineage novelty，
不计算 predictor effect 或 search utility。

protocol/producer/独立 verifier/test/runner/watcher SHA-256=`f3adc77b...3228f` / `0704edfa...30b7` /
`0eaafbec...13c2` / `a74a5c2c...4a13` / `bcedd747...68e2` / `00bc6583...4986`。producer/verifier
分别绑定独立 snapshot/fingerprint helper 与已发布 887 aggregate+verification；本地相关=`51 passed`，本机全套只因缺少
scipy/sklearn 在 collection 阶段不可运行，不能冒充 code failure 或完整通过。详细边界见
`phase1/实验记录/2026-08-29/SelectiveParentRecovery_Target522前瞻确认预注册.md`。

实现随后由公开 commit `349b9ca9ef84defd70e950d873564cbd8973c180` 闭环。fresh detached Linux 对 source hashes、
protocol dependencies、887 development package manifest 和 runner/watcher syntax 均复核通过，focused/full=
`51/1456 passed`，full 有 47 warnings；凭据命中=`0/0`，post-push manifest SHA-256=
`d9f094a562b0bad9b51dd80fbcc35c3d6eee06c562020d30b8b1fc9724c190b0`。outcome-blind watcher 于
`2026-08-28T16:18:01Z` 独立复核为 PID=`4119941`、lock held、13/13 preflight PASS，selection candidate/READY/COMPLETE
仍为空、LATEST 仍为 887；deployment receipt manifest=`e067089795da56e2179320be1bbf310c4e6ecacb6667717614ddb429656fb844`。
因此执行链已就绪但仍无 Target-522 scientific result；GPU/API/model-fit/base-update=`0/0/0/0`，prospective
values/raw archives 均未读。

## 0HP. 2026-08-28 run-disjoint selective parent recovery 正式通过全部强门

结果前冻结的最强分类已一次通过：`DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY`。snapshot 887
按 immutable run-ledger 固定为较早 290 个 train physical runs 与较晚 145 个 test runs；train-only 规则选中 exact
Jaccard margin=`1006/16929`。test 2,907 个 ambiguous edges 中接受 2,691 个，正确 2,684 个：coverage=
`2691/2907=0.92569659442724461`，precision=`2684/2691=0.99739873652917133`。无 reject 的 unique-top 为
`2845/2907=0.97867217062263501`；固定 reject 后错误由 62 个降到 7 个。全部 hard-support、precision、coverage、
selective-error、task/run breadth 与 anti-dominance 门均为 true；25/25 个可条件化 tasks 达到 0.95 reference，138/138
个 runs 达到 0.90 reference，最大 accepted contribution share 分别为 task=`44/207`、run=`55/897`。

wrong-parent 三种口径必须同时保留：all-alternative micro=`7/11257`，uniform one-wrong-per-child expectation=
`58/43605`，child-level adversarial=`7/2907`。producer A/B、非 import 独立 verifier A/B 均逐字节一致；focused/full=
`23/1448 passed`。formal aggregate/verifier/manifest SHA-256=`2aca589f...a2690` / `50b3a280...2955` /
`c51ad094...e281`；正式包见 `phase1/results/tree_content_selective_parent_recovery_887_20260828_63d37cf/`。

证书随后由公开 commit `0b7e873ac3aa89dade1dbfaefb5c69d916ce0579` 发布。首次 fresh post-push root 因远端仓库
不存在误用的 `myfork` alias，在 checkout/test 前失败并原样保留；v2 改用服务器真实 `fork` alias，这是纯基础设施修复，
未重跑科学 readout。v2 对发布包 manifest、classification 与全部 gates 的检查通过，focused/full=`23/1448 passed`，
full 有 47 warnings，凭据命中=`0/0`，post-push manifest SHA-256=
`c1e4692d1da6e722bdcddbc31a4ebf4447f749f9f6da6cd44b3e32ab7d339389`。

这支持一个可选的 `suggested_parent + confidence + provenance` 自审计层，但 recorded parent 不是外部语义/因果真值，
primary 不含 orphan，禁止静默改 canonical edge，也不申一般 selective classification/lineage novelty。下一步只在
Target-522 至少 87 个不重叠未来 runs 上固定复用同一阈值做 forward confirmation；不得重新选阈值、调门或用累计人口
rescue。GPU/API/model-fit/base-update=`0/0/0/0`，prospective truth/prediction、Target-522 profile 与 raw archives 均未读。

结果后只做了不读新 profile 的确定性重表达：selective/unfiltered error-rate ratio=`2261/18538`，即相对错误下降
`16277/18538=0.87803430790808068`。由最大 accepted task/run contribution 恰为 572/165，可得删除任一单 task/run、
并保守假设删掉的全是正确项后，remaining precision 仍至少为 `2112/2119=0.99669655497876353` /
`2519/2526=0.99722882026920034`。这是后验代数鲁棒下界，不是新实验或前瞻证据。ILINE、selective classification、
modelDNA/model-lineage attestation 与 agent provenance survey 又关闭了一般方法首创；完整防撞见
`phase1/实验记录/2026-08-29/SelectiveParentRecovery_防撞与单组删除鲁棒下界.md`。不再切 887 更多漂亮子组。

## 0HO. 2026-08-28 task-balance 重复观察实例已隔离；第二次 timeout handoff 在候选前修复

结构巡检发现两个 CPU latch 同时只读等待 887 的首个后继。较早的
`latch-2363b68-after-887-v4`（PID=`4035896`）在 `2026-08-28T12:17:00Z` 启动，虽写了
`source_commit=2363b687...`，却没有把运行脚本复制并逐字节绑定到 Git object，也没有复核 newest snapshot directory
与三条 support 日志；因此从发现时起明确降为**非权威观察副本**，任何 candidate/READY/分类都不得被 formal runner
消费。正式 authority 仍唯一是 0GT 已公开的 `latch-continuation-after-887-v4`（PID=`4061250`）：它绑定
commit=`6b3a7ba...` 与 script SHA-256=`8900896d...14b8`，formal runner 也只接受该 exact root。独立检查到
`2026-08-28T15:04:54Z` 时，两个实例仍均为 LATEST=887、candidate/READY/COMPLETE/FAILED/TIMEOUT 均为空；未终止继承
进程，也未把重复观察当成科学复现。

同时在任何权威 candidate 出现前补了第二次六小时 timeout 的状态机缺口。新 v5 handoff 必须等待权威 v4 正常
`TIMEOUT_RC=124` 且进程和锁均释放；若 v4 已锁 candidate，则逐字段、逐 hash 保留同一 candidate 与已有 support，绝不
重新看 LATEST 选择；若尚未锁 candidate，则把 timeout 缝隙内的 LATEST、mtime 新增 snapshot directories、三套 state
与三条日志合并，非 baseline identity 至多一个，否则 fail closed。后续第一次 latch 也要求自 handoff 起只有一个新增
snapshot。formal runner 只在 v4 COMPLETE 或 v4 clean-timeout 后 v5 COMPLETE 二选一，任何双 complete/无唯一 generation
都拒绝。脚本 SHA-256 分别为 handoff=`93407853...0e7f`、supervisor=`0674d0a0...ac6b`、generation-aware runner=
`38a138b9...2173`；本节写入时尚未 push/部署，因而仍无新的 balance classification。GPU/API/model-fit/base-update=
`0/0/0/0`，prospective label/outcome/prediction values 与 raw archives 均未读。

该修复随后已由公开 commit `69dd6b22acdf767f237571e0a530da3c659a7bad` 闭环。首次 fresh-worktree
post-push 因仓库历史 LFS object `5d75dc4...` 在服务器不存在而于测试前 `rc=128`；失败根原样保留，没有把它写成测试
通过。第二个新 root 用 `GIT_LFS_SKIP_SMUDGE=1` 只跳过与本测试无关的历史大文件，exact scripts/hash 仍从同一 commit
检出，focused/full=`38/1439 passed`，full 有 47 warnings；凭据命中=`0/0`，manifest SHA-256=
`e5e2af60e98c38577eabdd2bc666cc27f46b5354af65f614ccde74d5ad5de4ff`。supervisor 于
`2026-08-28T15:19:24Z` 上线，独立 postflight 在 `15:20:14Z` 确认 PID=`4098096`、lock held、权威 v4
PID=`4061250` 与非权威旧 observer PID=`4035896` 仍都 candidate-free，v5 尚未创建、LATEST 仍为 887；deployment
manifest=`67041bbb8ea084ca84661904a5db826e579c4e30fd1386908159cb8342bb98b0`。这只是连续选择链闭环，仍不是
`CAP_PASS` 或 predictor 正结果。

## 0HN. 2026-08-28 hierarchy × content parent concordance 已形成开发正信号并冻结 Target-522 前瞻确认

在已公开的 outcome-blind snapshot 887 上，平面 identifier-erased Jaccard graph 与 physical parent graph 明显不是同一
对象：524,810 个 within-run pairs 中，固定 Jaccard≥17/20 的 parent precision/recall/F1 分别为
`5713/11421` / `5713/10876` / `11426/22297`；同 population 直接用 parent label 选阈值的 oracle max F1 也只有
`11446/22315=0.5129285`。但在同一 physical run 内再给出 exact preceding depth 后，9,739 个非 trivial parent
候选集中 recorded parent 是 unique nearest neighbor 的比例达到 `9196/9739=0.9442448`，比同候选集 uniform random
期望高约 64.46pp；穷举 99,039 个同层错误 parent 只有 543 个会被误收，false acceptance=`543/99039=0.00548269`。
这里必须同时披露分母：按 child 计算，“至少存在一个可误收 wrong candidate”的 adversarial vulnerability 为
`543/9739=0.0557552`；每个 child 均匀随机替换一个 wrong candidate 的期望为约 `0.0104840`。`0.00548269` 只允许称
all-alternative micro FPR，不得单独包装成任意 corruption 的总体失败概率。

该信号在 task/run 上很宽：33/33 conditionable tasks、377/394 runs 达到 0.85；移除 depth 后 unique-top 降至
`2633/5438=0.4841854`，33 个 tasks 中 0 个达到 0.85。两阶段 producer 与不导入 producer 的独立实现均逐字段一致；
aggregate/verification SHA-256 分别为 `36bf9db4...e6c5e1` / `b2ce6193...cd9f9` 与
`893772da...96f42` / `b83e03a1...eedd1`。这些都是**已见的 887 development 结果**，不能称前瞻发现。

TraceGraph 已把相似图定位为 descriptive landscape，mle-traj-v3 也已有 version/fork/token-Jaccard 双视图，因此不申
similarity graph、parent recovery 或 dual-view 首创。可守正贡献是：对真实 MLE search physical parent 做结果盲的
structure-content cross-certificate，并明确证明 flat similarity 与 physical hierarchy 不可互换。新协议已在
`2026-08-28T14:29:52Z` candidate 仍为空、LATEST=887、435/522 时冻结，只使用同一自动 selection 的至少 87 个
不重叠未来 runs。强门为 exact-depth unique-top≥0.90、对 random lift≥0.50、wrong-parent FPR≤0.02、task/run breadth
各≥3/4；最强分类还要求 no-depth≤0.70、exact-depth gain≥0.30、flat oracle F1≤0.70。所有门用 exact fractions，
hard support 先判，887/累计人口/替代阈值不得 rescue。协议与完整边界见
`phase1/tree_content_lineage_forward_target522_v1.json` 和
`phase1/实验记录/2026-08-28/PhysicalLineage_ContentConcordance_开发结果与Target522前瞻冻结.md`；真实未来 profile
尚未运行，故当前只可称已独立复验的开发正信号与结果前执行机会。

实现与执行链已由 exact push `bee9e97e839fb4ffa9867f00e026b052a0570662` 闭环：fresh detached Linux
focused/full=`34/1438 passed`，full 有 47 warnings；post-push manifest SHA-256=
`08e384b343fbca1da2ee6d9e17efa62bee1ffe591882ef94336669afdbb01109`，提交文件名/内容凭据命中=`0/0`。
同一 commit 的 watcher 于 `2026-08-28T14:52:33Z` 独立复核为 PID=`4087901`、lock held、selection
`COMPLETE=false`，未读 candidate/profile；部署 postflight manifest=
`f1141aa784bf8873adf1a71edd1469280b25706d7a745618184eb50ad00070d4`。首次外层 launcher 在 watcher 已启动后
因正常 Git fetch 提示写入 stderr 而未完成自身 postcheck；该工程瑕疵已原样记录，watcher 本体未失败且没有重启或重复实例。
截至该回执仍无 Target-522 scientific result。

后续防撞又确认 ILINE 已对真实软件 DAG 做 similarity-based lineage inference 与 graph-arc/partial-order 评价，Neural
Lineage/modelDNA 已对模型 parentage 做 similarity/fingerprint verification，Tracing the Roots 已做数据集演化图重建；
因此“内容验证 lineage”“corruption detector”也不申一般方法 novelty。三层 MLE-specific release integrity stack 与完整
分母裁决见 `phase1/实验记录/2026-08-28/ParentPointer完整性威胁模型与防撞裁决.md`；该文档不改变已冻结 protocol。

## 0HM. 2026-08-28 within-stratum 改为 Target-522 不重叠前瞻确认

**结果前完整性修订（13:03:57Z）**：首个 monitor 上线后、候选仍为空且 LATEST 仍为 887 时，发现协议的
corpus basename 白名单漏列了独立核验 first-observed crossing 所需的 selection-support 文件；同时 TERM 未产生
预期 `FAILED_RC`。旧 commit `3553744e...` 的 monitor 已停止并以 `SUPERSEDED_PRE_CANDIDATE` 原样冻结，未见候选或
increment profile。科学 population、estimand、阈值和分类完全不变；协议现把 corpus 与 selection-support 白名单分开，
并显式捕获 TERM/INT/HUP。新版 monitor 必须在新 commit 上从同一 887 基线重新开始。

新版 monitor 已由 commit `42f1044e...` 从同一 887/435-run 基线重新上线；候选仍为空。候选到达前的 formal
producer 与不导入 producer 的独立 verifier 已实现：两边各自读取 baseline/candidate、复验 first-observed crossing、
严格比较 registry/run-ledger 前缀与旧 endpoint/run 的语义和原始字节，再只对完整新增 physical runs 计算 exact-rational
profile。合成端到端及 hash-valid crossing-skip、old-row drift、cross-run parent、cycle 攻击测试均已通过；真实 candidate
profile 仍未运行，故没有新科学分类。

commit `70a48e3df8c5c764abde277fcad842771de1ffe2` 又冻结了 formal runner 与只看结构状态的 watcher：候选
`COMPLETE` 前 watcher 只检查文件是否存在，闭合后才把 selection package 的精确 hash 交给固定 runner；runner 在全新
detached worktree 中依次执行 producer A/B、非导入式 verifier A/B、字节一致性、文件/网络访问审计、凭据扫描和
manifest，最后才写 `COMPLETE`。该 exact push 的独立 Linux 回执为 focused=`27 passed`、完整
`phase1/tests=1424 passed, 47 warnings`；GPU/API/model-fit/base-update=`0/0/0/0`，凭据文件名与内容命中均为 0，
manifest SHA-256=`5b63572ccaf04df80158be170acaa47aceb3f53c19c6534d3ee723c118ff8dc9`。截至
`2026-08-28T13:36:15Z`，selection PID=`4047654`、formal watcher PID=`4055136`，两把锁均有效；仍为
435/522 runs、candidate=`none`。因此这只是结果前执行链闭环，不得当作真实 scientific positive。

0HJ 的 887 formal 必须永久保留 gate-fail；不得在同 snapshot 把 float-string 门改成 rational 后重跑救回。为避免把
“只新增极少 runs 的下一 snapshot”包装成独立复现，新的 v2 在候选身份与 profile 未见时冻结为首个自动观测到
`provisional_first960_runs>=522` 的 immutable snapshot。`522=ceil(435*6/5)`，primary 只使用 candidate 中不在
887 的完整 physical runs，故至少有 87 个不重叠未来 runs；累计人口 profile 不能 rescue。

科学阈值原样继承 v1，但所有完整性和 gate 比较改用 exact numerator/denominator，`decimal_17g` 永不参与判定。
硬支持另要求至少 1,500 observed edges、60 个可条件化 runs、8 个可条件化 tasks 和至少 3/4 parent-present
endpoint fraction。两轴全过才允许 `FORWARD_INCREMENT_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION`。
公开 5 秒 monitor 只看 identity/count/hash，首个 observed crossing 自动锁定并保留 overshoot，连续 6 次 hash-stable
才 READY；中断且 LATEST 已变化时 fail closed。协议与边界见
`phase1/tree_linearization_within_stratum_forward_target522_v2.json` 和
`phase1/实验记录/2026-08-28/WithinStratum_Target522_不重叠前瞻确认预注册.md`。候选 profile 尚未运行。

## 0HL. 2026-08-28 path-record split 的共享前缀 crossing 正式分类为 run-only broad

结果前冻结的 path-split audit 已在 commit=`aec63564cb4a347a3bb6c61b38ae30850d1d755f` 和固定 blind
snapshot `887491a...` 上正式完成，分类为 **`RUN_ONLY_BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK`**。3,599 条
root-to-leaf paths 若按独立 records 做固定 80/10/10 split，train-test 预计共享
`1291.4019805907681` 条 canonical edges；预计 test unique-edge / path-edge-occurrence contamination ratios 分别为
`0.63841797380705656` / `0.71072159960645032`。这些全局量是已发布 multiplicity histogram 的后验确定性推论，
只有以下匿名 breadth 是结果后新读数。

physical-run 轴 435 个 groups 中 339 个达到 1/4 reference，最大贡献 share=`0.14093310549689442`，通过
1/5 anti-dominance 门；task 轴 34 个中 31 个达到 reference，但最大贡献 share=`0.45161151698862051`，超过
2/5 上限。因此不得宣称 task+run 双轴 broad。fragment/run grouped split 的 exact canonical-edge crossing 都为 0，
作为 release remedy control。formal producer/verifier A/B 均逐字节一致，focused/full=`90/1391 passed`，full 有
47 warnings；manifest=`83b552cdc68443f424c5bed8cdbf758c75eb3a14fdbd9ee34248a66909bc4b0b`。
没有实际模型性能膨胀、random split 或 predictor/search utility 结果。正式包见
`phase1/results/tree_path_split_prefix_leakage_887_20260828_aec6356/`。

## 0HK. 2026-08-28 depth-order 后验解析已正式闭环

结果后声明的 deterministic corollary 已在 commit=`333a3b66ca5399dcf87e586be1339423917d1264` 正式复验，分类为
**`VERIFIED_SHALLOW_DEPTH_STOCHASTIC_ORDER_COROLLARY`**。canonical/path-frequency mean logged depth 分别为
`89213/10895=8.1884350619550261` 与 `183993/26107=7.0476500555406592`；shift 为
`-324480056/284435765=-1.1407850064143656`。path CDF 在全部 observed depths 上不低于 canonical CDF，非零
PMF 差恰交叉一次；最大 CDF gap 在 depth 5，与 depth TV 同为
`27231696/284435765=0.095739352609191045`；median/p90 从 `7/15` 变为 `6/13`。

该结论只说明 path enumeration 把固定 observed forest 的 logged edge-depth 经验分布系统性推向浅层；数值在声明前已见，
不能称预注册发现，也不把 depth 解释为语义重要性。producer/verifier A/B 均逐字节一致，focused/full=
`63/1369 passed`，full 有 47 warnings；manifest=
`ab5df469b2b92e87ab78e998142bd6bcafc8f681f8d0f6efcee7ca78a30f2001`。正式包见
`phase1/results/tree_linearization_depth_order_887_20260828_333a3b6/`。

## 0HJ. 2026-08-28 within-stratum 正式门失败；科学 profile 只作描述性证据

固定 snapshot 的正式分类必须保留为 **`WITHIN_STRATUM_DECOMPOSITION_GATE_FAIL`**。原因是上游 JSON float
曾以字符串 `0.1603376038171571` 披露，而 exact fraction `45605749/284435765` 在固定 `.17g` 规则下重算为
`0.16033760381715709`；严格字符串 round-trip 门失败。这是协议表示层缺陷，但在结果后不得修改门并救回同一 snapshot。

仅作描述性记录：task/run canonical-standardized within-TV 分别为 `0.34286096272939481` /
`0.30840042995574296`；task 32/34、run 356/434 达到 conditional-TV reference 0.10，最大匿名贡献 share 分别为
`0.35387441357728333` / `0.10868797144906397`，两个 scientific axis gates 都通过。这支持在**首个未见未来
snapshot** 上用 exact rational 绑定重做确认，但当前不得宣称正式 `BROAD_NONCOMPOSITIONAL...`。formal producer/verifier
A/B 均逐字节一致，focused/full=`49/1355 passed`，full 有 47 warnings；manifest=
`dea00f84d8efa01585df21b63682a2f501386f06c3f413063403cb5d89ffd628`。正式失败包见
`phase1/results/tree_linearization_within_stratum_887_20260828_2363b68/`。

## 0HI. 2026-08-28 path-record split 的共享前缀 crossing 已做结果前分层冻结

0HC/0HD 已公开 root-to-leaf path multiplicity histogram；据此在冻结前探索性计算固定 80/10/10 path split
（3,599 paths→2,879/360/360）：train-test 预计共享约 1,291.402 条 canonical edges；test path-edge rows 中同一
canonical edge 预计也在 train 出现的 ratio-of-expectations 约 0.71072。两者都是已发布 histogram 的**后验确定性推论**，
不得称新发现或结果前通过。

尚未计算的新 readout 已冻结为匿名 task/run/fragment breadth：ratio reference=1/4，task 至少 1/2、run 至少 1/4
达到 reference，并要求最大 expected-contaminated-occurrence contribution share 不超过 task 2/5、run 1/5；两轴全过才允许
`BROAD_PATH_SPLIT_PREFIX_LEAKAGE_RISK`。固定大小随机分配用 exact combinatorics、不抽 seed；按 fragment/run grouped
split 的 exact canonical-edge crossing 必须为 0，作为 release remedy control。只读 887 blind structure，GPU/API/model-fit/
base-update=`0/0/0/0`。

Tree Training 已覆盖 shared-prefix 线性化重复计算，一般 grouped split/parent-inherits-split 也早已存在；因此不申通用概念
或算法 novelty，也不以 exact crossing 推断模型性能膨胀。可守贡献只是 MLE-agent observed forest 上的精确量化、跨 task/run
广度和可执行 tree-native release contract。协议见 `phase1/tree_path_split_prefix_leakage_v1.json`，时间顺序与边界见
`phase1/实验记录/2026-08-28/TreePathSplit_共享前缀泄漏风险_结果前分层冻结.md`。结果前 exact producer 与未 import
producer 的独立 falling-product verifier 已实现；新 synthetic/exhaustive=`22 passed`，相邻 tree 回归合计
`92 passed, 2 skipped`。producer/verifier/test SHA-256=`c91bcb07...2ac0c` / `974adb65...e414` /
`51465ea7...a6b03`；真实 breadth 尚未运行。

## 0HH. 2026-08-28 depth-order 只按已见数值后的确定性推论推进

0HC 的 formal receipt 已经公开 canonical-edge 与 root-to-leaf path-frequency 两套 depth counts 和 depth TV；随后又
探索性看到了均值、CDF 顺序、交叉数与分位数，才决定补精确解析。因此本线明确是
`POST_HOC_DETERMINISTIC_COROLLARY_DECLARED_AFTER_EXPLORATORY_DERIVATION`，不得称预注册发现、独立确认或新假设检验。

已见结果为：canonical/path depth means=`89213/10895` / `183993/26107`，path-minus-canonical=
`-324480056/284435765`（约 -1.140785，均值比约 0.860683）；path CDF 在全部 observed depths 上均不低于 canonical
CDF，非零 PMF 差只交叉一次，最大 CDF gap 在 depth=5，且与 depth TV 同为
`27231696/284435765`（约 0.0957394）；nearest-rank median/p90 从 `7/15` 变为 `6/13`。

若 exact producer 与不 import producer 的独立 verifier 通过，只允许称：固定 outcome-blind MLE observed forest 的
root-to-leaf 枚举把 logged edge-depth 经验分布系统性推向浅层。Tree Training 已覆盖 shared-prefix 重复计算，TreeAdv
又明确以 descendant 数归一化避免 near-root scale dominance；所以不申 shared-prefix/root bias/tree-aware weighting 的
一般首创。`depth` 不等于语义重要性或难度，也没有 predictor effect/search utility、完整 source tree、first-960 closure
或跨 snapshot 泛化。机器声明与时间顺序见 `phase1/tree_linearization_depth_order_corollary_v1.json` 和
`phase1/实验记录/2026-08-28/TreeLinearization_DepthOrder_后验解析声明.md`。结果后 exact producer 与不 import
producer 的独立 verifier 已实现；新增 13 项测试，与相邻 tree 回归合计 `61 passed, 2 skipped`，两个 skip 都是
Windows symlink 权限边界。protocol/producer/verifier/test SHA-256=`29a4e060...a2e7e3` /
`2d314d4b...ee5321` / `f240a57c...ebb15` / `146b0721...9b524`；真实 formal 尚未运行。

## 0HG. 2026-08-28 within-stratum decomposition 已在新 aggregate 前冻结

为排除 0HC/0HE 的 38.62pp edge-measure shift 只是 task/run composition artifact，已在任何 within-task 或
within-run 数值产生前冻结 canonical-marginal decomposition。主 estimand 为
`W_p(G)=sum_g(E_g/E) TV(p(e|g),q(e|g))`，分别对 task 与 physical run 计算；path-marginal `W_q` 只作
secondary sensitivity，不得 rescue。

结果前已诚实披露：整体 TV 与 task/run marginal TV 已知，因此三角不等式已逻辑保证 `W_p` 至少为
0.22585011065679452 / 0.19724349713897619；仅证明正值或该量级不算新结果。初版 `e99499e...` 曾误把
triangle slack≥0.05 当强门；在任何 synthetic/真实新值产生前发现 slack 只反映界的松紧，纯组内 distortion 时可为 0，
故公开修订为诊断项。强正门现固定为低于已知下界的 task/run `W_p` integrity floor=0.20/0.15，加上
`c_g>=0.10` 的 conditionable-group 比例 task≥1/2、run≥1/4，以及最大匿名 canonical contribution share
不超过 task 0.40、run 0.20。真正的新证据来自 breadth/anti-dominance；两轴全过才允许称
`BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION`；one-axis 和 below-gate 必须按序降级。

协议只读固定 887 blind structural population 与两份 hash-bound aggregate receipts；输出 exact rational 与匿名
histogram/quantiles，不输出 task/run/card/edge identity，不读 truth/prediction。GPU/API/model-fit/base-update=
`0/0/0/0`。结果前实现已补齐 producer 与不 import 新 producer 的独立 verifier；12 个新 synthetic tests 与相邻
回归合计 `48 passed, 1 skipped`，producer/verifier/test SHA-256=
`38aa702d58e1250db31790227778130d6fca41939cdc4f74249cbfa3d766e25c` /
`c6158bb201d604180739c24f9cf57309f2159dbd2e7233190e0fe36db5690e16` /
`08d874d98ed443378627213362e3e66b7af757f0d447228be6fc739ada11e3fd`。尚未运行真实 population，故仍无新
aggregate 或分类；详见
`phase1/tree_linearization_within_stratum_decomposition_v1.json` 与
`phase1/实验记录/2026-08-28/TreeLinearizationWithinStratum_结果前预注册.md`。

## 0HF. 2026-08-28 完整历史 release→future 零链接证书与 Evidence Index v8 已正式闭环

固定 snapshot `887491a...` 上，完整、可逐字节重建的 v11 历史 release（16,012 endpoints / 667 physical
runs / 25 tasks）对 outcome-blind future（11,906 endpoints / 435 runs / 34 tasks）已完成结果前冻结的
identifier/literal-erased Python token 审计。历史侧 fingerprint coverage=`16012/16012=1`；future 为
`11894/11906=0.9989921048210986`，其中 10 个 tokenization failure、2 个 too-short endpoints 不在证书内。

primary Jaccard 17/20 精确检查 18,510,294 个 candidate pairs，near-duplicate links、affected endpoints、
components 均为 0；strict 19/20 sensitivity 也为 0 links，六个预注册完整性门全部通过。分类为
**`ZERO_IDENTIFIER_ERASED_RELEASE_LINKS`**。这把此前只覆盖 5,519 个 critic-train endpoints 的零链接结果扩展到
完整 v11 release，是当前 physical-run/time split 的正向 benchmark-integrity 证据；但仅限固定 syntactic
representation/threshold，不证明 semantic clone 缺失、未知 pretraining 去污染或所有历史来源均已覆盖。

首轮因 1,800 秒资源上限失败（formal rc=124、deployment rc=1，未生成/读取结果）；r2 仅把上限改为 5,400 秒，
科学协议不变。r2 formal/postflight/deployment manifests 分别为
`4089cef1c7a42886ae6a363d3854e2f4e89e254829549a4681ea6bfaaed80fac` /
`868a11eda261ea78f71f4148eb60bf7b36a4b413ee708b7bbc03da3d1c6f5a98` /
`9a178a93e4f2b074363f120a3e1974c47f003cf874a6b0f13942ffede16af69c`；focused/full=
`19/1269 passed`，full 有 47 warnings。紧凑发布包 manifest=
`152f6f7c2d12f8c47e0fd809a56eb2a3ad8cd3dac826b62115c994201a0da985`，见
`phase1/results/historical_release_future_identifier_erased_overlap_887_20260828_8bf9512_r2/`。

同一证据链已按结果前 v8 协议正式写入 clean-provenance Evidence Index：v7 的 14 entries 原样继承，追加
physical-run split 与 complete-release temporal-overlap 两项，成为 16 entries / 43 artifacts / 3 bound files /
499 exact assertions。正式状态为
**`PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960`**；builder/verifier A/B 均逐字节一致，
focused/full=`30/1288 passed`，full 有 47 warnings。index/independent verification/formal manifest SHA-256=
`e97eca05d99a2eb3b5429539469a7e790f20f40cf70670cdbdc6a2c0c3e730a3` /
`3fea00a811c4422485311d4e8a0d7233fd9caf7828282f00c9a910ca8942ab69` /
`73a5884be6fffaed9d8ca3cb7972226c95bd1db3627cd1e330931dfd8f047b06`。prospective
label/grade/outcome/prediction、accuracy/effect/search utility、raw senior archives 均未读取；GPU/API/model-fit/
base-update=`0/0/0/0`。当前仍为 435/960、closure=false，最终 closure 后必须按原合同重签。正式包见
`phase1/results/decision_corpus_evidence_index_v8_887_20260828_3d30826/`。

## 0HE. 2026-08-28 tree linearization 的 estimand sensitivity 后验解析已正式闭环

在 0HC multiplicity aggregate 与 0HD compatibility certificate 均已知后，本轮先探索性看到了数值，再于
commit=`d8214ce0a1aecdc184ef6909fc2542c3e1506719` 如实冻结后验解析声明；因此只能称**已发布聚合量的
确定性解析推论**，不能称结果前发现、独立确认或新假设检验。正式实现 commit=
`5a96d92e0d638af6dba6f65c5f4a96e1ab37e9b4`，分类为
**`VERIFIED_EXACT_EDGE_MEASURE_SENSITIVITY_COROLLARY`**。

对固定 10,895 条 canonical unique edges 与 26,107 个 path edge occurrences，uniform-edge measure 和
path-frequency measure 的精确 total variation 为 `109845598/284435765`=`0.38618771447395162`。达到该
sharp bound 的 multiplicity-defined edge indicator 覆盖 2,286 条 unique edges：canonical mass=
`2286/10895`=`0.20982101881597062`，却占 path mass=`15560/26107`=`0.59600873328992221`，相差恰为
上述 TV。它严格意味着任意 `[0,1]` edge-level bounded statistic 的最坏经验期望偏移上界为 38.6188 个百分点；
不意味着 predictor accuracy 或任何自然指标实际达到该界。

描述性 concentration 同样材料：canonical inverse-HHI diversity=`10895`，path-frequency 为
`681575449/296317`=`2300.1564169453659`，保留率仅
`681575449/3228373715`=`0.2111203686962245`；单 edge 最大质量膨胀为
`1568880/26107`=`60.094227601792625`。inverse-HHI 只称描述性多样性，不称统计 ESS。0HD 的
`1/m_e` occurrence weighting 将每条 edge 的总质量精确恢复为 1，修正 measure 对 canonical 的 TV=`0/1`。

正式 focused/full=`27/1330 passed`，full 有 47 warnings；producer A/B、non-importing verifier A/B 与
第二 fresh-worktree postflight 均逐字节一致。formal/postflight manifest=
`4b82d111df374cdfb742e68a612e07d4c9d8d6bb8f073c81c785f051eaf73d84` /
`cb943d828d2fd4307d5f32b2de5c0e29c7c7a2ce3ae42618988023bf012c27ed`；forbidden/credential=
`0/0/0`。本结果只读两份 hash-bound aggregate receipts；prospective truth/prediction、identity/code、GPU/API/
model-fit/base-update 均未触碰。它强化的是 tree-native benchmark estimand 与发布合同，不是算法 novelty，也不能
rescue predictor primary；当前仍为 435/960、closure=false。结果包见
`phase1/results/tree_linearization_estimand_sensitivity_887_20260828_5a96d92/`。

## 0HD. 2026-08-28 tree-native/path-compatible 双视图 remedy 已正式闭环

在 0HC 的 materials result 已知后、任何 compatibility certificate 产生前，结果前 commit `0deb5b6...` 冻结双视图
合同；正式实现 commit=`cdc90e472eb57189a939187399d6b5fb5ec9a5c1`。固定 snapshot `887491a...` 上分类为
**`VERIFIED_LOSSLESS_TREE_NATIVE_PATH_COMPATIBILITY`**：10,895 条 canonical observed edges 与 3,599 条
root-to-leaf paths/26,107 个 edge occurrences 并列保留；每个 occurrence 使用精确 `1/m_e` mass 后，逐 edge 质量
均恢复为 1，总质量精确为 `10895/1`。task=34、physical run=435、depth cluster=37 的聚合质量也全部逐项恢复，
maximum per-edge mass error=`0/1`。

结构视图另有 1,011 fragments、142 single-node paths、8,307 observed child groups，其中 2,565 个有至少两个
observed children、最大 size=3；只能称 observed sibling groups，不证明 complete source choice sets。该 remedy 允许
tree-native canonical estimand 与 trajectory-only consumer 兼容共存；未加 inverse-multiplicity 的 path-frequency
统计只能作为单列 sensitivity，不能冒充 canonical measure。`1/m_e` 恒等式不是算法 novelty；可守贡献是把 MLE-agent
physical-run provenance、双视图 schema、estimand firewall 与 fail-closed independent verifier 做成可执行发布合同。

formal producer A/B、non-importing verifier A/B 与第二 fresh-worktree postflight 均逐字节一致；focused/full=
`31/1314 passed`，full 有 47 warnings。formal/postflight manifest=`342eefd9...66f2e` / `073b1bdb...fc1a`，
forbidden/credential=`0/0/0`。首个 launcher 因 remote alias 写错在 worktree/科学输入前停止，失败现场完整保留；成功轮只
修正 `myfork→fork`。当前仍为 435/960、closure=false；没有 truth/prediction/accuracy/effect/search utility，最终
closure 后须原合同重签。结果包见 `phase1/results/tree_native_path_compatibility_887_20260828_cdc90e4/`。

## 0HC. 2026-08-28 tree-native 表示的多轴材料性正结果已正式复验

0HB 的结果前协议在 snapshot `887491a...` 上正式分类为
**`MULTI_AXIS_MATERIAL_LINEARIZATION_REWEIGHTING`**。11,906 个 blind endpoints 中，10,895 条 observed
child-parent edges 覆盖全部 435 runs / 34 tasks，parent-present fraction=`0.9150848311775576`，12 个完整性/
支持门全部通过。把每条物理 edge 计一次改成枚举全部 fragment-root-to-leaf paths 后，edge rows 从 `10,895`
变为 `26,107`：重复 occurrence=`15,212`、重复质量占比=`0.5826789749875513`；`0.3877007801743919`
的 unique edges 被重复，mean multiplicity=`2.396236805874254`、p90/p95/max=`4/7/144`。

表示改变同时跨过两个结果前材料门：task-weight TV=`0.1603376038171571`（门 0.05），run-weight
TV=`0.18894421733497543`（门 0.10）。task maximum share 从 `0.25672326755392383` 升至
`0.3858352166085724`，run maximum share 从 `0.06351537402478201` 升至 `0.1158693070823917`；34 个
task 内的匿名 run-TV 中位数=`0.08664274322169059`，12 个达到预设 0.10 reference。因而当前最清楚的正贡献不是
“又发现一个数据问题”，而是：**tree-native node/edge/choice-set provenance 实质决定 benchmark estimand，不能把
root-to-leaf trajectories 当独立样本而不改变经验分布。**

边界必须保留：Tree Training/TreePO 已覆盖 shared-prefix 重复计算，T-STAR/Tree-OPO/SPPD 已覆盖 tree-aware credit/
sampling，Dolma 已比较一般 thread linearization；不得声称首次发现 shared prefixes 或一般 tree 方法。可守 novelty 是在
真实 Python MLE-agent search corpus 上，以结果盲、physical-run-bound、可重建协议量化 task/run reweighting，并把
tree-native release 与 task→parent→pair estimand panel 一起交付。该结果仍是 435/960、closure=false 的 provisional
结构证据；不证明完整 source tree、predictor accuracy、search utility 或因果机制。

正式 source commit=`e9f4fb9cf495d6751fb77d061095f6dca312728c`；focused/full=`19/1299 passed`，full 有 47
warnings；producer A/B、同 worktree 独立 verifier A/B、fresh-worktree postflight A/B 均逐字节一致。formal/postflight
manifest SHA-256=`d8972749b7ee7e98abcbcc85dcefc7080ad674f2bdc260d01c27c6bf8628d46a` /
`725566a5a928764a5700d08b086c2f815f55d4240c30403bdcd3ccb3e0392961`；forbidden/credential=`0/0/0`。
结果包见 `phase1/results/tree_linearization_weight_887_20260828_e9f4fb9/`。

## 0HB. 2026-08-28 tree linearization weight 已在 aggregate 前冻结

为把 0HA 的 canonical-linearization 边界转成 outcome-blind MLE 实证，已固定 snapshot `887491a...` 上的结构审计：
同一 blind observed fragment 分别按“一条 child-parent edge 一次”和“枚举全部 fragment-root-to-leaf paths”计权；后者
中每条 edge 的 multiplicity 等于 descendant leaves 数。只比较由表示产生的 task/run empirical-weight 变化，不读取
label/outcome/prediction，不补缺失 parent，也不称 complete source tree。

结果前支持门为 parent-present endpoint fraction≥0.75、unique edges≥1,500、edge-bearing runs/tasks≥150/15；材料门
固定为 duplicate occurrence fraction≥0.25、task TV≥0.05、run TV≥0.10。ordered classification 明确区分多轴材料
reweighting、仅 run 轴、只有 duplication、零 duplication 与 gate fail，后项不得 rescue 前项。即使最高档通过，也只
是固定 MLE snapshot 的结构测量，不证明 mle-traj raw tree 缺失、predictor effect、search utility、因果性或一般方法
novelty。协议与边界见 `phase1/实验记录/2026-08-28/TreeLinearizationWeight_887结果前预注册.md`。
冻结协议 SHA-256 为 `95b49fd50b75dd16fd9eefbb34557da35daa52fcecc35fce45ac89948a697feb`；真实 aggregate
运行前，本地生产器/独立复算器及相邻回归共 `19 passed`。

## 0HA. 2026-08-28 mle-traj 的 true-sibling 缺口暂列未决，禁止由 canonical linearization 外推 raw release

最新公开数据卡同时给出两项事实：canonical agent tables 把 13 个 MLEvolve physical runs 线性化为 189 条
root-to-leaf branches；但 gated raw layout 又列出每个 run 的 `trajectory.json`、`paths/path_###.json`、逐版本代码和
`tree_summary.json`。因此只能说其**主分析表是线性化表示**，不能在未获授权、未审计 raw tree 前断言该 release
无法恢复真实 parent/sibling，或据此声称我方是首个/唯一 true-sibling MLE 数据集。

直接竞争状态固定为 `UNRESOLVED_GATED_RAW_TREE_RECOVERABILITY`。若以后取得正常访问，必须先锁 revision/license/hash，
按 13 个 physical runs 而非 189 paths 去重，结果盲重建 `(run,parent,children)` 并审计 sibling completeness；资格不足只报
结构，不运行 transfer。当前仍可由现有证据支持的差异是：我方更大的 physical-run decision population、显式
run/component/config/time 隔离、outcome-blind accrual+closure、同池 predictor 横评，以及 missingness/noise/
pair-weighting/query-init-execution cost 联合账本。不得把“公开 card 未说明”写成对方最终论文或 raw release 明确没有。
详见 `phase1/实验记录/2026-08-28/MLE直接数据竞品_MLAgent_OpenMLE_mletraj_防撞审计.md`。

## 0GZ. 2026-08-28 Evidence Index 的一般方法 novelty 关闭，MLE-specific 实证边界保留

最新一手核验确认 BetterBench（NeurIPS 2024 D&B）已给出 46 项 benchmark 生命周期质量框架；BenchmarkCards
（NeurIPS 2025 D&B）已同时发布 Markdown 与 machine-readable JSON；ReproEvalCard（ACL 2026）已固定多阶段 LLM
pipeline 的 prompts/judge/snapshot/intermediate-trace 最低复现材料；Auto-BenchmarkCard（AAAI 2026 Demo）又已覆盖自动
抽取与事实验证。2026-08 的 contamination-detectability 预印本也明确要求把 non-rejection 与 power/validity gates 同报。
因此“首个 machine-readable benchmark card/evidence index”“首个 audit checklist/failure contract”“一般 contamination
certificate”全部关闭。

Evidence Index v8 只定位为本项目的可执行发布机制，不单独冒充算法或 reporting-standard 创新。仍可守的正贡献来自其
绑定的 MLE-specific 实证：真实 sibling fragments、physical-run/component/config/time 隔离、outcome-blind accrual 与
closure、连续外部分数的 gap/noise、failure/missingness、endpoint reuse/pair weighting、成本账本以及表示限定的完整
release→future temporal-overlap certificate。正式写作应把上述三类标准作为上位 related work，并逐字段说明我方额外的
provenance/estimand 约束。arXiv:2607.25589 当前已 withdrawn in full 且要求旧版本不得引用，不能拿其旧摘要作证据。
详见 `phase1/实验记录/2026-08-28/BenchmarkCards_ReproEvalCard_证据索引防撞审计.md`。

## 0GY. 2026-08-28 Evidence Index v8 三档映射与独立验证已在结果前实现

完整 release r2 的 producer A 尚未落结果文件时，已把 v8 的机器协议、builder 与不 import builder 的独立 verifier
实现并冻结。协议 `phase1/decision_corpus_evidence_index_v8_protocol_v1.json` SHA-256=
`a463a6e7ede5bb9b46dbe6081ae46d26d6c2e8410e858acf9d022c642633deda`，固定继承 v7 的 14 entries、已知
双轴 split certificate、完整 release package 的唯一输出路径，以及 ZERO/LOW/GATE_FAIL 三档 ordered status；任何
manifest、关键 assertion、安全回执、旧失败史或 classification↔primary-link↔gate 关系漂移均拒绝构建。

三档 synthetic chain、缺文件、预测值访问、独立 classification 漂移、删关键 assertion、改结果依赖 claim 和协议
hash 漂移共 `11` 个 v8 测试，加 packager/v7 回归共 `30` 项待最终提交前复跑。当前没有生成 v8 正式 index，也没有
读取 full-release aggregate；prospective label/outcome/prediction、GPU/API/model-fit/base-update=`false/false/false/0/0/0/0`。

## 0GX. 2026-08-28 三个直接 MLE 数据竞品关闭 trajectory-dataset 泛化主张

最新公开材料显示，ML-Agent 已在 9 个 MLE tasks 上收集 10,000 条执行轨迹并做 Qwen2.5-7B SFT/step-wise PPO；
Frontis-MA1/OpenMLE 又公开 26,259 条、4,891 task names 的 SFT traces，并把 Draft/Improve/Debug/Crossover operator
learning 接到长程 evolution；mle-traj-v1/v3 则已有约 15k 个逐版本 human/agent code nodes、held-out scores、
state/action/intent 标签与 forest view。故“首个/最大 MLE trajectory dataset”“首个逐节点分数/图结构”“首个
execution-grounded MLE learning/cost”全部关闭，不得再进入标题、摘要或贡献点。

仍可守且应升为论文中心的是 **true-sibling decision benchmark**：mle-traj 的 agent MLEvolve 部分只来自 13 个
physical runs 并线性化为 189 branches，人类 forest 还混入构造的 fork/code-sim edges；我方保留真实 search parent、
siblings 与 choice fragments，在同一 frozen decision pool 横评独立 execution-free critics，并联合审计 physical-run/
config/time transport、outcome-blind closure、query/init/execution cost、regrade noise 和 pair-induced weighting。
closure 后应把 true-sibling 与 linearized parent-child/cross-run 作为预注册 sensitivity 同报，但不得用于 rescue primary。
详见 `phase1/实验记录/2026-08-28/MLE直接数据竞品_MLAgent_OpenMLE_mletraj_防撞审计.md`。本轮只读公开资料，
prospective truth/prediction/GPU/API/model-fit/base-update=`false/false/0/0/0/0`。

## 0GW. 2026-08-28 完整 release 审计的结果盲发布封装已冻结

在 r2 尚未产生或读取任何 full-release aggregate/link/classification 时，进一步冻结 compact publication package：
协议 SHA-256=`ba6a1f6e44458e65b7042fcfd6e84e95e2e2b6cec0c7d0bb494ad7e0924da2d7`，固定 audit source commit=
`8bf95124175a7ba7f388ac547b31be05916651f5`、snapshot=`887491a...`、formal/postflight/deployment 三个 roots、
旧失败 formal/deployment 两个 roots，以及唯一 repo 输出路径。三档 evidence-index status 逐字节复用 v8 预注册：
ZERO→`PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960`，LOW_WITH_EXCEPTIONS→
`PROVISIONAL_QUALIFIED_TEMPORAL_SPLIT_EVIDENCE_STACK_AWAITING_FIRST960`，其余→
`TEMPORAL_SPLIT_EVIDENCE_STACK_GATE_FAIL`；gate fail 优先，strict sensitivity 不得 rescue primary。

packager 只有在三份 SHA256 manifest 全量成员与内容复核、producer/formal verifier/postflight verifier 各 A/B
逐字节一致、postflight=formal verifier、旧 rc=`124/1` 且旧 producer result 不存在、全部 security/population/source
binding 精确成立时，才原子写 aggregate-only 六文件包；任何漂移直接失败且不留半包。packager SHA-256=
`48bc593957462356738f67f25a76fdd395dab40968f7a9e8bfabe77caf7849c7`，结果盲 synthetic focused=`8 passed`。
当前 r2 正式 full tests=`1269 passed, 47 warnings` 后仍在 producer A；未读取 full-release result，prospective
label/outcome/prediction、raw archive、GPU/API/model-fit/base-update=`false/false/false/false/0/0/0/0`。

## 0GV. 2026-08-28 完整 v11 release→435-run future 审计首轮资源失败；r2 结果前冻结

为补 0GU “历史侧只覆盖 critic-train endpoints”的边界，已冻结一个更强但仍仅属 benchmark-integrity 的
population expansion：完整、可逐字节重建的 v11 release（16,012 endpoints / 667 physical runs / 25 tasks）对
同一 `887491a...` future（11,906 endpoints / 435 runs / 34 tasks）。表示、候选 join、primary/strict 阈值与
完整性门逐字复用 `python_token_identifier_erased_v1`、17/20、19/20；任务/run 不作 candidate prefilter。

结果前明确披露：固定 5,519-endpoint critic-train 子集到该 future 的 primary links=0 已知，因此本轮是严格人口
扩张，不冒充独立发现。ordered classification 固定为 `ZERO_IDENTIFIER_ERASED_RELEASE_LINKS` →
`LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS` → `RELEASE_SPLIT_INTEGRITY_GATE_FAIL`；strict
sensitivity 不得 rescue primary。producer A/B、独立 verifier A/B、256×256 brute-force 控制和 immutable failure
receipt 为硬门。首轮协议 SHA-256=`22f2d4f4853c11398429c40f91f952711ee2003bc27bec7c977726c82f0771ea`、
source commit=`ed3d2941d047e5f88a527f244ebcdc6c6cea4e43`。fresh Linux focused/full 完成后，producer A 在
固定 `timeout 1800s` 处以 rc=`124` 终止；deployment rc=`1`、stderr=`0 bytes`、`producer_a.json` 未创建。
这是 pre-science resource-envelope underestimate，不是科学 gate/classification；失败 roots 与 `FAILED_RC` 永久保留，
没有读取任何 full-release aggregate/link/classification。

结果前 resource revision r2 只把每命令 timeout `1800→5400s`，人口、输入哈希、表示、阈值、六门、分类与
A/B/postflight 全部不变；新协议 SHA-256=`52390b9a78893775db70a85dbda8e98132363cbb997e7006eab0646e9c0f73b3`，
并逐字段绑定旧失败史；focused=`19 passed`。新轮只能用公开新 commit、fresh worktrees 与全新 roots，从头执行；
若 5,400 秒仍失败则停止扩 timeout，先做结果盲性能工程。当前仍未读取任何 full-release similarity result；prospective
outcome/prediction、raw senior archive、GPU/API/model-fit/base-update=`false/false/false/0/0/0/0`。详见
`phase1/实验记录/2026-08-28/HistoricalRelease_887_v1资源护栏修正_结果前冻结.md`。

## 0GU. 2026-08-28 435-run 双轴 split-integrity certificate 正式签发

结果前协议 SHA-256=`779ac3f1...37ef5da`，formal source commit=`25efd3a9237e93177e3c8c91b8f73169a70d4213`。
同一 snapshot `887491a...`、同一 `python_token_identifier_erased_v1` 表示和 0.85/0.95 阈值下，证书分类为
**`PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE`**，七个 certificate gates 全部通过：

- future 内部 11,906 endpoints 中 11,894 可 fingerprint。0.85 下 11,421 个高相似 links 全部在同一
  physical run：parent-child/sibling/same-run-other=`5713/235/5473`，跨 run same/cross-task=`0/0`；
  0.95 下 4,068 links，跨 run 仍为 0。
- 固定历史 v11 critic-train 5,519 endpoints /333 runs 到 435-run future，0.85 下精确检查
  6,172,443 个 candidates，links=`0`，same/cross-task=`0/0`；0.95 下仍为 0。历史/future coverage=
  `1.0/0.9989921048210986`。该项是已知 404-run 零链接结论的顺序 +31-run 外延，不冒充全新独立发现。

两项输入各自 producer/verifier A/B 与结果前冻结的 independent postflight 均通过；证书 builder/verifier A/B 也各自
逐字节一致，独立 verifier 不 import builder。证书 formal focused/full=`7/1260 passed`，full 有 47 warnings；四个
原始 formal/postflight 清单和两个 Git 安全包重新绑定。certificate/independent SHA-256=
`b44035bd...ccca5c` / `45dc560b...af944`，formal manifest=`a7e6aeb9...a7161`。raw corpus/archive/identity、
prospective outcome/prediction values 未读，GPU/API/model-fit/base-update=`0/0/0/0`。

这是当前最强的 D&B benchmark-integrity 正资产：高相似性大量存在但严格 lineage-local，且固定历史 critic-train→future
未发现高相似链接。只能按固定 syntactic representation/threshold 声明；不证明 semantic clone/pretraining
contamination absence，不覆盖 12 个不可 fingerprint endpoints 或全部可能历史来源，也不提供 predictor effect。
当前 435/960、closure=false，最终 first-960+closure 后必须原协议重跑。结果包：
`phase1/results/split_integrity_certificate_887_20260828_25efd3a/`。

## 0GT. 2026-08-28 task-balance v2 在 887 正式 KILL；v3 仅锁定下一未见 successor

task-balance v2 的首轮是 Python 环境 pre-science failure；修复环境后的正式轮 focused/full=`4/1238 passed` 后按原规则
在 task universe `30→34` 处 KILL，没有生成 forward result 或 balance classification。独立 postflight 验证 added/removed
tasks=`4/0`，同一 887 不得用事后 padding rescue。

v3 只把“新增 task 显式 baseline-zero、禁止删除/负增量/换 dominant task”写成未来协议；旧 v2 默认行为逐字节保留。
激活人口只能是公开 commit 后自动观测到的最早 887 successor，禁止调用者传 snapshot、人工跳过或在 887 重跑。
精确运行中的 latch SHA-256=`4afef04396684844e3755e7769b420c5a42e7ded8f50395122f974e454381598`，已公开于
commit=`440ff2961b2e42ff7becea727ca5641cc3f13ccb`；10 秒轮询、六小时上限。v1/v2 启动均因漏载代理导致
GitHub fetch `rc=128`，发生在 protocol/LATEST 读取前并保留失败根；v3 仅修复环境加载后启动。当前仍是
`887491a...`、candidate 为空。正式 runner 已公开，只有 latch+transition+WL+receipt-only common support 全部闭合后才执行；
CPU-only，outcome/prediction value/GPU/API/model-fit/base-update=`false/false/0/0/0/0`。

v3 后于 `2026-08-28T12:05:57Z` 按固定六小时边界正常 `TIMEOUT_RC=124`；最后一次仍是 887，且无
`FAILED_RC/candidate/READY/COMPLETE`。在新 successor 尚未出现时，续接协议只允许在以下证据同时成立后启动新固定 root：
当前 `LATEST`、mtime 最新 snapshot directory、transition/WL/receipt state，以及从旧 monitor 最后时间起三条 support
日志出现的唯一 snapshot identity 必须全部仍为 887。续接脚本必须先公开、从 exact git object 启动、写 source hash 与
continuity receipt；科学 cap、debt、task-expansion、classification 和禁止 rescue 规则不变。续接尚未产生 candidate 或
balance classification。

续接已由公开 commit `6b3a7ba626798cd4bf15147eef3da90293e98158` 的 exact git object 上线，script SHA-256=
`8900896df4a13861dd53dd3d9b6de8c20d9b9d499fe1063c07b33ccd9ce814b8`。`2026-08-28T13:47:37Z` 时
PID=`4061250`、lock held、candidate/READY/COMPLETE/FAILED/TIMEOUT=`false/false/false/none/none`；continuity receipt
六项均为 887。该 exact push 的 fresh Linux focused/full=`13/1424 passed`，full 有 47 warnings，凭据命中=`0/0`，
manifest SHA-256=`b979e874e7823660e30689f88e8ff1260e1ccf194fe3e4159e22d2e77efa2de8`。仍没有新的结构分类。

## 0GS. 2026-08-27 COTA 已直接覆盖同前缀 pairwise continuation advisor；方法 novelty 关闭

最新公开的 [COTA / *Don't Solve, Just Compare*（arXiv:2608.21027v1）](https://arxiv.org/abs/2608.21027)
已经在 exact-prefix state 上改变 branch action、交还同一 frozen actor、以 downstream return 估计 `Q^pi(s,a)`，并用
Qwen2.5-0.5B 的 A/B/T comparator、双输入顺序一致性和 `K/R` winner-count gate 做非绑定 runtime intervention；
WebShop/ALFWorld/tau3-Retail 的 3 actors × 3 environments 均报告正收益。它实质覆盖“同状态两候选谁更可能通向更好
结果”“小模型只比较不求解也能指导强 actor”“pairwise comparator 接运行时 gate”三类一般方法主张，而非仅标题相似。

该边界必须与本文件 0BT/0BY 联合解释，不能误写成 COTA 才首次覆盖程序比较器。Co-Reyes et al. 的
[Guided Evolution（arXiv:2402.05821）](https://arxiv.org/abs/2402.05821) 已在线训练二元 ML-program discriminator，
以 PAM/PAM-RT 比较 mutated child 与 parent、拒绝预测较差且尚未执行的候选，并在 Hero/AutoRL 报告约 3.7×/4×
搜索加速；CPRD/BoN 理论又已关闭“pair construction 决定 deployment distribution/estimand”的一般概念首创。
COTA 的新增直接重叠是把该范式推进到 exact-prefix、actor-conditioned continuation 与 agent runtime intervention。
因此 comparator、跳过执行、在线 gate 和 pair-distribution 原理均只能作 related work；我方可主张的是这些已知问题在
完整 Python MLE solution distribution 上的 run-clean、结果盲、连续分数领域实证与可重建 benchmark，不是通用首创。

因此从本节起，以上三类主张以及 A/B/T、双顺序一致性均不得作为我方 novelty；学长此前提出的 future-potential
扩展也只能称 MLE 领域复现/压力测试，不能称一般方法首创。当前不恢复已关闭的 `K>=1` lookahead、未来潜力标注或
控制器实验。clean 0.6B→8B scaling 若以后确认，也只定位为 MLE 完整程序 decision distribution 上的 capacity/transport
证据，不包装成 tiny-advisor 方法。

仍可守的论文边界是 Decision Corpus + Predictor Benchmark + Audit Protocol：完整 Python candidate program、pristine
连续外部分数、真实同-parent choice fragment、physical-run/comparison-component/experiment-config 隔离、gap/regrade
noise、missingness、endpoint/pair graph、query/init/execution cost 和结果盲时间前瞻 closure。尤其必须区分：COTA 的
actor-conditioned continuation return 与我方 canonical candidate 自身即时 external grade 是不同 estimand，不能都写成
“future potential”。该直接竞品反而强化“pair construction determines the deployment estimand”的组织原则，但 0BY 已明确该原则本身
不是我方理论或概念 novelty。详见
`phase1/实验记录/2026-08-27/COTA_同前缀比较器_最新防Scoop与主张收紧.md`。本轮只读公开文献，prospective
truth/prediction/GPU/API/model-fit/base-update=`false/false/0/0/0/0`。

## 0GR. 2026-08-27 config-v2 已形成可 cherry-pick 的真实 producer 自动接入补丁；仍未部署

学长最新 `dojo-reproduce@61459c0a1248900079dafed7c505afa87e476b40` 上已制作默认关闭的 upstream patch：
`phase1/upstream_patches/0001-Add-prospective-config-v2-producer-hook-18-tests.patch`，SHA-256=
`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`。启用后，resolved config 保存完成、
`env_variables.json` 与 task/solver 构造之前，自动写单-run `producer.config_v2.jsonl`；它只含公开字段和
prompt-sensitive solver/config hashes，不读取环境 dump、archive、journal、outcome、grade、label 或 prediction。
开关默认关闭；release 缺失、混合 operator client、凭据形状、非法 run identity/timeout、hash/schema 异常、竞争写入
均 fail closed。checkpoint/resume 仅可复用逐字节相同的既有 sidecar，任何配置变化都不覆盖。

fresh Linux 正式验证：focused=`19 passed in 0.26s`，full=`84 passed, 1 skipped, 26 warnings in 32.69s`；
与现有独立 v2 exporter 的 128 个合法变体 row/bytes 全等，4 个非法变体两边共同拒绝；secret filename/blob=`0/0`，
GPU/API/outcome/label 访问=`0/0/false/false`。formal root=
`/research/d7/spc/yzyang4/config-v2-producer-hook/verify_fa2151b_v4`，manifest hash=
`fbb9536c760c9a14ba9e7da044d1f32fe7f748ff54298f27fb1951bbe743c2b0`。v1/v2/v3 的环境失败史保留，正式引用 v4。

随后用 metadata-only 规则冻结原 run root 中 mtime 最新的 20 个 regular `dojo_config.json`，在不打开 env/journal/
submission/grade/Cards/pairs/tar/outcome/prediction 的条件下做历史 schema-only smoke：20/20 candidate/reference row 与
canonical bytes 一致，覆盖 7 tasks、2 clients、2 个 solver fingerprints、9 strata，顶层 schema=1；credential-before-parse
通过、forbidden opens=0、sidecars written=0。rows SHA-256=
`fd8982cf75099f71b73d1d5b2ad3e955a89d81efbae941e94705981216ed9e5e`，formal manifest=
`80c8ab4b9ef5c23693aad00c7db75e81d81fd18f7339f65d6dff67e86003c47e`。这只排除 synthetic-vs-real config shape
不兼容，不把历史 runs 回填成 outcome-before provenance，也不证明新 prompt/config 已在生产使用。

当前裁决仍是 `PATCH_VERIFIED_NOT_DEPLOYED`：没有直接修改学长分支，也尚未观察到下一批真实 sidecar，故 0825/更早
archives 不得回填，clean scaling GPU 重训仍未获授权。学长 review/cherry-pick 后必须从下一批 producer 显式设
`DOJO_CONFIG_V2_SIDECAR=1` 与公开 `DOJO_GENERATOR_RELEASE`；只有真实 sidecar 与 source/expected-run receipt 完整
组合、outcome-blind support gate 通过后，才另报模型×数据×seed×GPU·时矩阵。详见
`phase1/实验记录/2026-08-27/SeniorConfigSidecar_v2_生产自动接入补丁.md`。

## 0GQ. 2026-08-27 opportunity-yield 404-run 外延正式 NO-GO

结果前公开冻结 commit=`7b9ddf64efcbf75107e3bdc7846d7467454ddc90`，固定 ad0b；producer/verifier A/B、
focused/full=`12/1225 passed`、exact-path 与凭据门全部通过。科学门为 E1/E5 PASS、E2/E3/E4 FAIL：360/380/400/404
持续反转，但最大单 drop attribution=`1.0617531614480789`；31 个 task deletion 中 30 个保留，删除 dominant OSIC 后
pair-HHI 差=`-0.0018797549643278927`；yield fraction 对 pair-HHI=`0.5991375958702558`，对 run→pair TV 仅
`0.44105064109821923`。因此正式裁决为 `ROBUST_OPPORTUNITY_YIELD_CLAIM_NO_GO`。

只保留“run-level coverage 与 pair-micro task weight 持续背离”的描述性诊断；撤回在 provisional404 上“非单批次稳健、
且 yield 对两个集中度指标均为主要机制”的表述。不得以 E1、30/31、pair max share 下降或单个分解指标 rescue。该审计支持
同时发布 task-macro、pair-micro、drop leverage 与层级 provenance，但不是 predictor/method/search-utility 正结果。同一 snapshot
不再调 baseline、门或删除规则；closure 后按原协议重跑。正式包：
`phase1/results/structural_weight_extension_ad0b_20260827_2dbd964/`。

## 0GP. 2026-08-27 opportunity-yield 404-run 时序外延已结果前冻结

404-run ad0b 的 counts 与 dominant pair-task share=`0.2947295423023578` 已知，不作为新发现。尚未读取的
HHI 轨迹、Shapley decomposition 与 drop/task deletion 已冻结为外延审计：完整 1..404，headline extension=
360/380/400/404；沿用旧 G2 的单 drop attribution `<0.5`，task deletion≥80%且 dominant deletion 保留，
yield 对 pair-HHI 与 run→pair TV 正增量均≥50%。旧 339-run G2=`0.9641733656841007` 失败；只有新 E2 真正
通过才可升级为“非单批次 artifact”，其他门不得 rescue。

provisional chronology 可能受晚到 run 重排，故旧 7cda first339 与 ad0b 重建 first339 只报告 sensitivity，不假定
逐字节相同，也不称严格 held-out append extension。CPU-only；label/outcome/prediction/effect 不读，closure 后原协议重跑。
查重边界：PALOMA/MixEval-X 已覆盖 domain/task mixture，informative-cluster-size 理论已覆盖 cluster/individual estimand，
ABC 已覆盖 agent benchmark validity；这里只主张 MLE search-tree opportunity-yield 的版本化实例与机器审计，不写首次。
预注册：`phase1/实验记录/2026-08-27/First960_结构权重时序外延404_结果前冻结.md`。

## 0GO. 2026-08-27 0825 outcome-blind 摄取、Target-300 进度与 identifier-erased formal 完成

0825 的 12/12 个 archives 已由 append-only intake 提交，transactions=`86→98`，最终 settle poll 为
`archives=246 ready=0 transactions=98 outcomes_read=false`；immutable snapshot=`ad0b624d...5dedb0e`。
provisional first-960 从 366 runs / 10,683 endpoints / 2,755 pairs / 30 tasks 增至
404 / 11,310 / 2,884 / 31，净增 `+38/+627/+129/+1`，当前 404/960、尚差 556、closure=false。
dominant pair-task share 从 `0.308529945553539` 降至 `0.2947295423023578`（-1.3800403251181204 pp），
但仍高于 25% cap，结构 balance gate 未通过。该批没有 `*.config_v2.jsonl` sidecar，不能用于 exact-stratum
scaling 确认或触发 GPU 重训。

target-300 固定 runner 在 5×300 秒 quiescent gate 后完成：64→129 runs、21→41 archives、21 tasks、
remaining=171；previous exact prefix survived，boundary archive/closure anchor 均不存在。独立 verifier=
`PASS_COLLECTING_TRUTH_UNREAD`，truth support 未计算，replay 未授权。该人口与 first-960 estimand 不同，不得混池，
达到 300 也不会自动授权 effect/replay。结果包：
`phase1/results/score_channel_target300_progress_ad0b_20260827_ab59a01/`。

0GN 的 identifier-erased audit 从预注册 commit=`065d0b56...a913f2` 在 ad0b snapshot 正式完成。历史侧
5,519 endpoints /333 runs 全覆盖；前瞻侧 11,299/11,310 可 fingerprint，coverage=
`0.999027409372237`。Jaccard≥0.85 下 exact candidate checks=`5,923,921`，near-duplicate links=`0`；
same/cross-task=`0/0`、affected endpoints=`0/0`、components=`0`，0.95 sensitivity 亦为 0。65,536-pair
brute-force control、六个 gate、producer/verifier A/B、独立 24-payload recheck 全通过；focused/full=
`29/1212 passed`，forbidden/credential=`0/0`。这是更强的 train→future syntactic-independence 正资产，仍不证明
semantic/pretraining contamination absence，也不提供 predictor effect；first-960+closure 后必须原协议重跑。
结果包：`phase1/results/historical_train_future_identifier_erased_overlap_ad0b_20260827_065d0b5/`。

## 0GN. 2026-08-27 historical train ↔ first-960 identifier-erased overlap 已结果前预注册

0GL 的 lexical audit 明确不能排除 identifier-renamed clones。新审计在任何真实相似度前固定更激进表示：Python tokenizer
删除 comment/layout，hard keyword/operator 保留，其他 NAME→`<IDENT>`，number/string→固定 token；继续使用 token
5-gram、BLAKE2b-128、minimum 20 distinct shingles、0.85 primary / 0.95 strict 和 256×256 brute-force control。

历史人口仍为 5,519 endpoints，前瞻仍为 chronological first-960 prefix；不按 task/run 过滤 candidates。通过门固定为两侧
coverage≥0.99、prospective affected≤1%、cross-task affected≤0.5%、无 size≥10 且跨≥3 tasks component，并要求
producer/verifier 全 aggregates/digests 一致。任一失败不得改表示、阈值、人口或 snapshot rescue。

12 项 synthetic/adversarial tests 已在不读取真实结果时通过：alpha-renaming+literal-change 正控 Jaccard=1、结构无关负控
低于 0.85、两个独立 tokenizer/shingler 一致、prefix join 与 brute force 一致、hash-seed 无关。相关工作已覆盖 code
dedup 与 identifier abstraction，因此本项只定位为 run-aware MLE-agent benchmark-integrity extension，不主张新 clone
detector 或 semantic equivalence。真实 formal 尚未运行；当前仍 closure=false，最终 first-960+closure 后必须原协议重跑。
预注册：`phase1/实验记录/2026-08-27/HistoricalTrain_First960_IdentifierErasedOverlap_v1_结果前预注册.md`。

## 0GM. 2026-08-27 archive alias 显式处置完成，公开 monitor 与 outcome-blind 摄取链恢复

0GL 末尾的 8 个固定 source-path aliases 已完成独立处置。8/8 alias 与各自 canonical committed transaction 逐字节
相同，合计 183,409,093 bytes；固定 reason=`ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION` 写入 observation ledger
后，transactions 仍为 86，SHA-256=`a8a44574...2160`，snapshot=`8579d7cd...d9248`，first-960 暂定人口仍为
366 runs / 10,683 endpoints / 2,755 pairs。fresh post-verifier 和 partition verifier 通过；禁读 `open/openat=0`，
label/outcome/prediction value/utility 未读取，tar members 未解包。

formal-v1 的实质步骤已完成，但 broad filename gate 把 Git status 的 6 次 `newfstatat` 元数据检查误报为禁读；该根
保持无 `COMPLETE`。可引用完成件是独立 postflight-v2，manifest=`1fa3c81c...3a8625`。公开 alias-bound monitor
commit=`bc362dfe...b6ee0` 在 fresh Linux 通过 focused/full=`32/1196 passed`，提交凭据扫描=`0/0`。live poll 0
通过且 snapshot/transactions 不变；observed archive paths 从 234 增至 246，但 `ready=0`，所以只能说新增 12 路径
进入稳定性观察，不能说已有新 run。transition snapshot chain 已从 8579 state 恢复；WL/receipt/config 与 successor
supervisor 仍 live。未知 content alias 继续 fail-closed；本修复不提供 predictor effect。

结果包：`phase1/results/archive_content_alias_disposition_8579_20260827_9b7640a/`；结果前协议：
`phase1/实验记录/2026-08-26/Archive_Content_Alias_Disposition_v1_结果前预注册.md`。

## 0GL. 2026-08-26 historical v11 train ↔ provisional first-960 lexical independence formal 全门通过

0GK 的结果前协议已从公开 source commit=`f9c6de27afd933d9ceee04e67acbd51d25947798` 在 immutable
snapshot=`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248` 上正式执行。历史侧 5,519/5,519
train endpoints 可 fingerprint；前瞻侧 10,674/10,683 可 fingerprint，coverage=`0.9991575400168492`。

固定 token 5-gram+BLAKE2b-128、minimum 20 distinct shingles、Jaccard≥0.85 下，exact candidate checks=`2,880`，
near-duplicate pairs=`0`，same-task/cross-task=`0/0`，两侧 affected endpoints=`0/0`，components=`0`；0.95 strict
同样为 0。256×256 共 65,536 对 brute-force 控制一致，六个预注册门全部通过。producer A/B、non-importing verifier
A/B 各自逐字节一致，focused/full=`14/1182 passed`，禁读路径/凭据命中=`0/0`。formal/recheck manifest SHA-256=
`8b4dc3aef2ada8f848362f049517511bd2658d847f5911f32435206c48c55730` /
`91e368c6e81e2dd3eb19791f1ed509697bcc29d67fb7c389ee0c34416d6c3713`。

这是当前最干净的新增 D&B benchmark-integrity 正资产：在结果前固定的 lexical 定义下，历史 critic-train code 与
chronological future prefix 没有高相似链接。边界不变：它不证明 semantic/identifier-renamed/pretraining contamination
absence，不提供 predictor effect；当前只有 366/960、closure=false，最终 first-960+独立 closure 后必须原协议重跑。
结果包：`phase1/results/historical_train_future_fuzzy_overlap_8579_20260826_f9c6de2/`。

同日生产侧另出现 8 个新 source paths 与既有 `0824/` basenames/size/mtime 对齐，旧 intake 因首个 content SHA 已存在于
transaction registry 而 fail-closed。这不是新语料或模型结果。修复只允许对固定 8 路径做 hash-bound 显式 alias
disposition；未知重复仍 fail-closed，且应用前后必须证明 transaction/run/snapshot 不变。完整 8/8 byte identity 尚未在
本节声明，须以单独 pre/post independent verifier 的完成件为准。

## 0GK. 2026-08-26 historical v11 train ↔ first-960 fuzzy overlap 已结果前预注册

0GJ 只证明 prospective prefix 内部的高 lexical 相似代码严格局限于同一 run，不能排除历史 critic train code 与未来
评测 code 近重复。新 bipartite 审计把历史侧冻结为 v11 b0/b1/b2 的全部 `intask_split=train`：5,816 rows、
5,519 unique endpoints、333 physical runs、23 tasks；三份 pair normalized-LF SHA 与 305,750,663-byte historical
cards SHA 均写入 schema。历史 JSON 中虽含回顾性 label/observation 字段，审计只使用 identity/run/task/parent/code，
只主张这些字段未用于计算，不能声称历史文件未打开。

在任何真实 historical↔prospective similarity 前，表示继续冻结为 token 5-gram+BLAKE2b-128、Jaccard 0.85 primary/
0.95 strict、minimum 20 distinct shingles，并加 fail-closed dependency contract。成功门为两侧 coverage 各≥0.99、
prospective affected≤1%、cross-task prospective affected≤0.5%、无 size≥10 且跨≥3 tasks component，以及固定
256×256 subset 的 exact brute-force 一致。失败不得换阈值、删 task/run 或用 strict/subset rescue。

producer 与不 import 新 producer 的 verifier 已通过 14 项 synthetic/exhaustive/adversarial tests；真实 candidate、edge、
component 与 gate 尚未计算。正式件只能在公开 source commit 的 fresh no-smudge Linux worktree 中生成；前瞻
label/outcome/prediction/effect 保持零访问，CPU-only。即使通过，也只支持 train→future lexical overlap 较低，不证明
semantic/pretraining contamination absence 或 predictor effect；first-960+closure 后必须重跑。预注册：
`phase1/实验记录/2026-08-26/HistoricalTrain_First960_FuzzyOverlap_v1_结果前预注册.md`。

## 0GJ. 2026-08-26 first-960 token-shingle 近重复审计 formal 全门通过

现有 clone 资产只覆盖 raw/token/AST 规范化后的 exact fingerprint，明确不能排除 fuzzy/语义近重复。新审计不把
代码去重包装成方法 novelty：代码重复会夸大模型评测已有直接先例，The Stack 也已采用 5-token shingles 与 Jaccard
复核。新增贡献边界仅是 outcome-blind MLE-agent chronological cohort 中按 sibling/parent-child/same-run/cross-run/
cross-task 分层的结构实证与机器协议。

在读取任何真实相似度前，primary 固定为去注释/格式、归一化 number/string 但保留 identifier/operator 的 token
5-gram set，128-bit BLAKE2b shingle，exact prefix-filter join 后以整数算术判定 Jaccard≥`17/20=0.85`；`19/20=0.95`
只作更严格并列表，不能 rescue primary。长度不足 20 个 distinct shingles 的端点不删除，计为 coverage failure。
成功门固定为 fingerprint coverage≥0.99、跨 run affected endpoint fraction≤0.01、跨任务≤0.005、无 size≥10 且
跨≥3 tasks 的 fuzzy component，并要求 384-document deterministic subset 与 brute force 完全一致。任一门失败不改阈值。

审计只允许读取 snapshot-bound `eligible_blind_manifest`、identity-only runs 与 intake/accumulator summaries；不输出
code/card/run/task 值，不读取 label/outcome/prediction，不计算 predictor effect。独立 verifier 不 import producer，
并用另一种 prefix-posting 枚举重算全部 edge digest。

正式 source commit=`cb368f95c5374fd2ab7448455b3ba3af054d02ec` 在 snapshot=`8579d7cd...d9248` 上全门通过：
366 runs、10,683 endpoints 中 10,674 可 fingerprint，coverage=`0.9991575400168492`。0.85 门下 61,070 个候选
exact check 后有 7,069 个 near-duplicate pairs，全部局限在同一 physical run：parent-child/sibling/same-run-other=
`4078/50/2941`，cross-run same-task/cross-task=`0/0`；0.95 门下 2,758 pairs，跨 run 仍为 0。五项预注册门、
384-doc brute force、producer/verifier A/B 均通过；focused/full=`13/1163 passed`，forbidden/credential hits=`0/0`。
结果包：`phase1/results/prospective_fuzzy_code_clone_audit_8579_20260826_cb368f9/`。

可用正结论是“高相似代码确实大量存在，但在固定 lexical 定义下呈严格 lineage-local，而非跨 run 复制”；仍不能
外推为语义唯一、变量重命名 clone 不存在或 predictor 无泄漏。当前 366/960 只是 provisional，closure 后必须原协议
重跑。预注册与结果：`phase1/实验记录/2026-08-26/First960_FuzzyCodeCloneAudit_v1_结果前预注册.md`。

## 0GI. 2026-08-26 ABC crosswalk v2 清洁迁移 formal 全门通过

ABC crosswalk v1 的 24 项人工判断只保留为 hash-pinned 文本/status 模板；其 catalog 中 v6、两项 coverage、guard v1
及各自 independent 共 6 个 evidence IDs 全部移除，旧 evidence artifacts 不得打开。v2 加入 v7、receipt-only support、
taint registry、structural trajectory、opportunity-yield audit、task-balance structural-only v2 的 11 个 clean IDs，最终
items/evidence=`24/29`。

迁移未升级任何人工判断：PASS_LOCAL/PARTIAL/INHERITED_UPSTREAM/NOT_APPLICABLE 仍固定 `9/9/5/1`；机器
verifier 只认证 schema、状态约束、引用闭包与 SHA-256，不做 semantic certification 或 aggregate compliance score。

正式件已从公开 source commit=`c97371d7433b808933624b706a848a644991139c` 的 fresh no-smudge Linux worktree
通过：builder/verifier A/B 均逐字节一致，focused=`11 passed, 1 skipped`，full=`1144 passed, 1 skipped,
47 warnings`；production trace 只允许并记录 24 次 source v1 template opens，removed evidence、prediction pair/value、
label/outcome 路径命中为 0，credential hits=0，GPU/API/model-fit/base-update=`0/0/0/0`。crosswalk/independent
SHA-256=`65cbf6cf...1487ee` / `242ef697...5dd06`，formal manifest=`1552c911...ffcef`。结果包：
`phase1/results/agentic_benchmark_checklist_crosswalk_v2_20260826_c97371d/`。它恢复的是 clean checklist evidence
provenance，不是 predictor 效果或 D&B 合规总分。预注册与结果记录：
`phase1/实验记录/2026-08-26/ABCCrosswalkV2_清洁证据迁移预注册.md`。

## 0GH. 2026-08-26 Decision Corpus evidence index v7 从未污染 v5 重建；formal 全门通过

0GF/0GG 的污染传播还使 Decision Corpus Evidence Index v6 与 ABC crosswalk v1 的受影响机器指针失效。v7 不修补
v6，而从 normalized-LF SHA-256=`4bff2b9f...7a1627` 的最后未受影响 v5 重建；formal file trace 明确禁止打开 v6、
withdrawn coverage matrices、task-balance v1/forward v1 与 crosswalk v1。旧 artifacts 全部保留为 historical-withdrawn。

新增五项 clean replacement：provenance registry、receipt-only 2,755-pair common support、structural atlas+trajectory、
closure-time opportunity-yield audit、task-balance structural-only v2。预冻结机器规模为 14 entries、37 JSON artifacts、
3 bound files、434 assertions。允许主张只到
receipt-certified support、结构 weighting shift、interpretation contract 和“debt improved but uncleared”；orientation/tie/
margin、accuracy/effect/utility、robust magnitude、producer compliance、causal effect 与 v1 provenance repair 均禁止。

正式件已从公开 source commit=`a83bebfdb8dcf59bea21a1b84269b2e87bf7a02e` 的 fresh no-smudge Linux
worktree 通过：builder/verifier A/B 均逐字节一致，focused=`10 passed, 1 skipped`，full=`1127 passed, 1 skipped,
47 warnings`；生产 trace forbidden-path hits=0，credential hits=0，GPU/API/model-fit/base-update=`0/0/0/0`。
index/independent SHA-256=`d8cc9c60...31674` / `b0bcd321...1d128`，formal manifest=
`608c0a4f...cbbbe1`。结果包：`phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/`。
这恢复的是 clean machine evidence stack，不新增 predictor effect；下一步只允许从该正式包重建 ABC crosswalk v2。
预注册与结果记录：
`phase1/实验记录/2026-08-26/DecisionCorpusEvidenceIndexV7_清洁证据栈预注册.md`。

## 0GG. 2026-08-26 prediction-matrix 污染已传播到 task-balance v1；structural-only v2 正式预注册

0GF 的撤回链继续向下审计后确认：旧 task-balance guard v1 直接从已撤回 matrix 读取逐任务 pair counts；其 forward v1
又同时绑定该 guard 与后续 value-reading coverage matrix。因此 0FX/0GD 的 v1 artifacts 虽然算术未被证明错误，但不能再
作为“first-960 + closure 前严格零 prediction-value access”证据。ABC crosswalk 中指向 matrix/guard 的 evidence pointers
与 Decision Corpus Evidence Index v6 matrix 项同步降级；其他独立结构证据不受影响。机器污染登记为
`phase1/prediction_matrix_downstream_taint_registry_v1.json`。所有旧文件保留、不删除、不覆盖。

替代 v2 已在任何 formal promotion 前冻结。基线只读 independent structural gate、snapshot-bound accumulator summary 与
summary 内 SHA-256 绑定的 first-960 ledger；forward 对基线/当前两套 summary+ledger 重新验证，并用 0GF 的 receipt-only
independent receipt 交叉确认当前 canonical pair 总数。任何 prediction pair/value/coverage matrix、label/outcome/raw archive/
effect 表均禁止作为输入。producer A/B、non-importing verifier A/B、ledger 重计、chronology、file trace、credential scan 与
fresh Linux focused/full 都是硬门。

v1 的 657→645 已为操作者所知，所以 v2 明确是 provenance repair，不是 blind numerical discovery；即使复现，也不能
追溯恢复 v1 合规性。协议与预注册记录：

formal v2 已从公开 commit `1b9b8365f1b2067c9ebb27c20d29b6844bc79f3a` 的 fresh no-smudge Linux worktree
全量通过：focused/full=`4/1113 passed`，guard/forward producer A/B 与 non-importing verifier A/B 均逐字节一致，
postformal verifier A/B 又与 formal verifier 完全相同；forbidden-open/credential hits=`0/0`。纯结构链独立恢复
baseline/current pairs=`2635/2755`、债务=`657/645`、delta=`-12`、current OSIC share=
`0.308529945553539`；25% cap 及即时动作遵从仍失败。guard/forward independent SHA-256 分别为
`62f5fa00...15310c` / `00f8fec2...102146`，formal/postformal manifest 为 `b1405cd4...005135` /
`8b90eab9...cb0166`。这恢复相应结构算术主张，不恢复 v1 provenance，也不提供 predictor effect。

公开结果 commit=`b90429ddc817c72bae81eadd32f444174326babb` 在 fresh public post-push no-smudge worktree
再次通过 focused/full=`8/1117 passed`、结果包 inner manifest=`12/12`、检出前后 `git clean=true`；post-push
manifest=`5d645f21aa9fe61f88c90c350e75bf3f8acfb5680c7c5d232e18c1943e39fcb4`。首次 broad credential grep
把自己的 scan-output 文件纳入输入，故该自引用 diagnostic 不作为安全证据；独立 postcheck 排除 scanner 自身输出后
credential hits=`0`。这只认证公开可复现性，不新增科学主张。

- `phase1/task_balance_structural_only_protocol_v2.json`；
- `phase1/results/task_balance_structural_only_v2_8579_20260826_1b9b836/README.md`；
- `phase1/实验记录/2026-08-26/TaskBalance_预测矩阵污染传播与StructuralOnlyV2预注册.md`。

## 0GF. 2026-08-26 旧 prediction coverage matrix 因预闭包聚合预测值撤回；替代协议先行冻结

代码审计确认旧 `prediction_escrow_coverage_matrix.py` 打开两套 pair prediction 文件、解析 margin/selected，并计算
tie/non-tie、activation 与 effect-eligibility 聚合；其 `prediction_values_aggregated=false` attestation 按字面为假。
诊断中还显示过少量 prediction-derived aggregate。没有读取 label/grade/outcome/accuracy/search utility，也没有据此改变
frozen scorer、activation、模型、threshold、task/subset、停止规则或 hypothesis；但 0FT/0FU/0FV 及后续 matrix 不能再称
符合“first-960 + closure 前零 prediction-value audit access”。Decision Corpus Evidence Index v6 的相关第十项同步降级为
historical-withdrawn。旧 artifacts 保留作撤回链，不删除、不覆盖，其 orientation/tie/eligibility 数字禁止迁入新结果。

替代协议已在正式运行前冻结：只读取 promoted states、independent receipts、记录的 verifier commands，并只对 artifact
summary 与 frozen verifier source bytes 做 SHA-256；绝不打开 pair files 或解析 summary 内容。成功主张最多是
`RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT`：两套 frozen verifier contracts 对同一 immutable snapshot 各自重建
同一 canonical sibling-pair population，receipt/command/summary/source 全链绑定且 pair counts 相同。“count 相同”单独
不充分；不得声称新审计重开了 identity/orientation，也不得报告 margin、tie/non-tie、activation/eligibility 或 prediction
distribution。producer A/B、非 import verifier A/B、file-strace、credential scan 和原子 state promotion 均为硬门。
预注册 commit=`9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f` 的 fresh Linux focused/full=
`19/1104 passed`。真实 `8579` 正式件通过：2,755 structural pairs 为
`INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED`，producer A/B 与非 import verifier A/B 各自逐字节一致；
file-strace 的 prediction-pair/outcome-path opens=`0/0`，prediction values accessed/aggregates=`false/[]`，且没有重开
pair identity/orientation。formal manifest / receipt / independent SHA-256 分别为 `179a511d...35d995` /
`3b2d0200...721263` / `24a7ff75...cb012e`。

其前置 WL exact monitor replay 也通过 focused/full=`22/1094 passed`，producer 与 one-shot current artifact 逐字相同，
manifest=`ba152f61...8e121d`。新 WL / receipt-only monitors PID=`2374019/2374760` 已上线，transition PID=`2320379`
保持；两个旧 WL/value-reading coverage monitors 经精确 cmdline 核验后 TERM，历史 artifacts 全保留。该结果恢复的是合规
common-support integrity 资产，不恢复旧 orientation/tie/eligibility 主张，也不提供 predictor effect。直接记录：

公开结果 commit=`6d6e24828d525a04c8f209bae2debc47e2d01df5` 又在 fresh detached Linux worktree 通过
checked-in inner manifest、focused/full=`24/1109 passed`；post-push receipt manifest=
`9c1770ca6be9264d13b4358ac7b6d45b8dfed53b944fe27166960d2b991c301f`。这只复核公开可复现性，不新增
prediction/effect 主张。

- `phase1/prediction_receipt_common_support_protocol_v1.json`；
- `phase1/results/prediction_receipt_common_support_8579_20260826_9f2cbe9/README.md`；
- `phase1/实验记录/2026-08-26/PredictionEscrowCoverage_预测值访问事故与ReceiptOnly替代预注册.md`。

## 0GE. 2026-08-26 provisional first-960 membership 非单调；prediction escrow chain 已结果盲修复并部署

0GD 的 chronology 勘误还有一个达到 960 后才会显现的直接后果：append-only source registry 不推出 chronological
`first-960` membership append-only。迟上传但冻结时间更早的 run 可以进入 rank `<960` 并挤出旧 tail；旧 WL append
verifier 与 transition producer/verifier 的 prior-support-subset 条件会把这种合法 churn 误判为失败。若新增 run 排在
960 之后、prefix 完全不变，旧 WL verifier 还会因“not a growing append”误拒绝。

结果前冻结的修复不改 frozen scorer、activation、模型、prediction、三字段排序、first-960 estimand 或 closure。每代
artifact 仍绑定不可变 snapshot；跨代改查 source set containment + sequence subsequence + row identity、共同预测逐字段
相同，以及所有 prior/current-only rows 是否分别由 rank≥960 的 displaced run / rank<960 的 entering run 精确解释。
transition 若发生 removal，current producer/verifier 不传 legacy prior，再由原 independent scorer verifier 与新的 chain
verifier 双重核验。closure 前 support gate 明确是 provisional、可因 churn 反转，不能触发揭盲。

合成 append/stasis/insertion-displacement 与篡改反例全部通过；旧 WL verifier 在同一合法 churn fixture 上按预期失败。
真实 `d748→8579` shadow 为 362→366 runs、added/removed=`4/0`、common/current-only pairs=`2728/27`。source formal
focused/full=`24/1089 passed`，双 receipt 一致；deployable monitor replay focused/full=`25/1090 passed`，producer、原
independent scorer verifier 与 chain verifier 全部 rc=0；不传 legacy prior 的 2,755-row `pairs.jsonl` 与旧 `8579`
artifact 逐字相同。两份 formal manifest hash 分别为 `62f90ef5...d16d6b3` / `06b0aaeb...758179e0`。

公开结果 commit=`9db2d9f965b342853bd1ce944dd84051f898ccc9` 的 fresh post-push worktree 再通过 focused/full=
`11/1093 passed` 与公开包原 7-entry manifest；post-push formal manifest hash=`0d267216...1ef146`。该复现只认证
公开可复现性，不新增 effect 或真实 churn 主张。

首次 full-suite launcher 未锁 BLAS 线程，在登录节点扩到约 28 CPU 后主动 TERM；只有 staging `FAILURE`、无
`COMPLETE`。v2 锁定六类线程变量为 1 后通过，首次失败不计证据。旧 transition monitor 的精确 cmdline 核验后已
TERM，全部历史 artifact 保留；churn-safe monitor PID=`2320379` 从同一 `8579` summary SHA 接管，300 秒×72 polls，
首轮 `no_change`。当前真实区间 removed=0，因此禁止写“真实 churn 已通过”；该事实须等自然 accrual 首次 removal receipt。
outcome/effect/GPU/API/base-update=`未读/未计算/0/0/0`。直接证据：

- `phase1/provisional_first960_snapshot_chain_protocol_v1.json`；
- `phase1/results/provisional_first960_snapshot_chain_f21a76c_20260826/README.md`；
- `phase1/实验记录/2026-08-26/First960_暂定集合churn与PredictionEscrow完整性_正式裁决.md`。

## 0GD. 2026-08-26 冻结 task-balance guard 首次前瞻记账精确；债务改善但 cap 与遵从仍失败

> **provenance 勘误：** 本节原 v1 artifacts 依赖 value-reading matrix，已按 0GG 撤回其严格零 prediction-value
> 合规性；相同算术已由 0GG structural-only v2 独立恢复。以下 v1 过程仅作历史审计链。

把 0FX 在 `7cda` outcome 前冻结的 25% dominant-task pair-share guard 应用于后续 `8579` structural exact-common
inventory。新增 27 runs / 120 pairs，其中 27 个 OSIC、93 个非 OSIC；旧整数 envelope 精确给出
`657 + 3*27 - 93 = 645`，独立按 current per-task counts 复算也是 645，故债务净减 12。作为非预注册 descriptive
secondary，pair-HHI 从 `0.1357471491993994` 降至 `0.13322920543739974`，run→pair TV 从
`0.337082500713674` 降至 `0.32785794333204404`。

两个失败边界不能省略：OSIC share=`0.308529945553539`，25% cap 仍失败；且 debt 清零前新增了 27 个 OSIC
pairs，所以旧 guard 的“暂避 OSIC”即时动作明确没有遵守。自然摄取不是随机干预，因此只允许称 frozen accounting
forward check 精确、结构债务有所改善；禁止称 guard 导致改善、producer compliance、predictor effect 或 search utility。
HHI/TV 也不能救回 cap failure。

chronology 首轮因错误要求 ledger bytes 为前缀而 fail-closed。正式诊断为：339 个旧 run_id 全部保留，旧顺序是 366-run
序列的 subsequence，同 run_id 行完全不变；只是 2 个按冻结时间全序更早的新 run 插入旧 provisional tail 前。因此正确
append-only invariant 是 set containment + sequence subsequence + row identity，不是文件 byte prefix；首次失败已保留。

source commit=`76bdaad398da675aa62614260d63a019594f172c`；fresh Linux focused/full=
`15 passed in 0.22s` / `1080 passed, 47 warnings in 73.13s`，producer/verifier 各双跑并与仓库 artifacts 逐字节相同，
formal `SHA256SUMS` hash=`688f8b4f...eb45721`。另保留 runner matcher 冲突与 Python 3.11/3.13 普通 float sum
末位不一致两次 formal 失败；后者用 `math.fsum` 真修复，没有放宽比较。truth/prediction/raw archive read=
`false/false/false`，GPU/API/model-fit/base-update=`0/0/0/0`。直接证据：

- `phase1/results/task_balance_guard_forward_8579_20260826/README.md`；
- `phase1/results/task_balance_guard_forward_8579_formal_20260826/README.md`；
- `phase1/实验记录/2026-08-26/First960_任务均衡护栏前瞻核验_结果.md`。

## 0GC. 2026-08-26 outcome 前冻结两级 opportunity-yield 聚合影响审计；不改写既有 primary

在 first-960 closure 与任何 prospective outcome/prediction-value 揭盲前，正式冻结 closure-time aggregation audit。
它把容易混淆的 `run → informative pair` 分成两级：eligible runs `R_t` 先产生 truth/evaluability 过滤前的 structural
exact-common pairs `S_t`，再保留最终 informative/evaluable pairs `I_t`。对应 structural opportunity yield
`Y_t=S_t/R_t` 与 informative retention `E_t=I_t/S_t`，任务权重必须逐项满足
`q_t=p_tY_t/E_p[Y]` 和 `r_t=q_tE_t/E_q[E]`。

closure 后，每个冻结 arm 和 paired contrast 必须并列报告 informative-pair、structural-pair、run-weighted-task 与
uniform-task 四种点估计，并把 pair→run 的实际变化精确分成 structural-yield component 与 informative-filter component。
每段和总变化同时报告 `range(task metric) * TV(task weights)` 的 sharp worst-case bound；bound 不是 observed/expected
bias，更不是 predictor effect。pair-vs-run sign flip 只作描述，精确零固定为 `ON_BOUNDARY`。

entry gate 要求 first-960 + 独立 closure、冻结 arm/contrast registry、exact common support，且 cohort 中每个任务同时具有
structural 与 informative pairs；否则必须返回 `NOT_IDENTIFIABLE_FULL_TASK_UNIVERSE`，不得删除零支持任务继续。该审计不
supersede generic estimand headline、scaling/component-breadth primary、truth/support/effect gate 或 inference；任何 alternate
weighting、decomposition、subgroup 或 sign flip 都不能挽救失败 primary。

理论边界已主动收紧：informative cluster size、cluster-weighted 与 individual-weighted estimand 的区别已有 Williamson et
al. (2003) 与 Kahan et al. (2023) 等先例，不主张 size-biased weighting 恒等式本身新颖。本地贡献仅限真实 MLE-agent
chronological search 中 decision-opportunity yield 对衍生 sibling-pair benchmark task mix 的 outcome-blind 证据，以及结果前
冻结的两级机器审计。

contract/source commit=`49a9e7c6...86cff3` / `f97026221e099c11fa1ca8f2c13a95c389bea743`；fresh Linux
focused/full=`17 passed in 0.24s` / `1064 passed, 47 warnings in 77.09s`，18/18 independent checks PASS，verifier
A/B 逐字节一致；formal `SHA256SUMS` 文件自身 SHA-256=`60711365...86cff95`。prospective truth/prediction/raw archive
read=`false/false/false`，accuracy/effect/search utility 未计算，GPU/API/model-fit/base-update=`0/0/0/0`。直接证据：

GitHub 公开结果包 commit=`bad6ec5428c62b6a213b0d75fa0d1e58d858b5d4` 又经 fresh detached Linux
post-push 复现：focused/full=`20 passed in 0.42s` / `1067 passed, 47 warnings in 72.20s`，inner manifest 全部
通过，verifier 双跑与仓库 receipt 三者逐字节一致；post-push `SHA256SUMS` 文件自身 SHA-256=
`06832278...3ee246`。该复现仍只认证公开可复现性，不新增 effect 主张。

- `phase1/contracts/OPPORTUNITY_YIELD_AGGREGATION_AUDIT_V1.md`；
- `phase1/results/opportunity_yield_aggregation_audit_v1_20260826/README.md`；
- `phase1/results/opportunity_yield_aggregation_audit_postpush_bad6ec5_20260826/README.md`；
- `phase1/实验记录/2026-08-26/OpportunityYield_两级聚合影响审计冻结.md`。

## 0GB. 2026-08-26 时序分解确认 opportunity yield 内生重写 pair benchmark；幅度受单批次影响

对固定 `7cda` snapshot 的 first-240→first-339 做结果前冻结、outcome-blind 的完整时间序与机制分解。run-HHI 变化为
`-0.007095167549882084`，pair-HHI 从 `0.08303759912408124` 升至 `0.1357471491993994`；run→pair TV 从
`0.2750745424635` 升至 `0.337082500713674`。反转在 260/280/300/320/339 共 5/5 个晚期检查点成立，30/30 个
leave-one-task-out 以及删除 pair-dominant OSIC 后仍成立。

固定 Shapley 分解中，task-specific opportunity-yield 变化解释 pair-HHI 正向增量的 `0.6446576519060645`、TV 增量的
`0.5951060527094302`，两者均超过预注册 50% 门，因此可称 yield heterogeneity 是主要机制。但无单批次 artifact 门失败：
0820 OSIC 的 5-run drop attribution=`0.9641733656841007`；删除后 pair-HHI 增量仍为正但只剩
`0.001888405775504004`。故唯一允许 headline 是“**反转符号可泛化，幅度对批次敏感**”，禁止写成幅度广泛稳定。

这把 0FZ 的端点图谱推进为时间持续性与机制证据：真实搜索树产生 decision opportunities 的速率会内生改变 pair-micro 的
任务混合。它强化 task-macro/parent-macro headline、pair-micro sensitivity 与 drop-level leverage 披露，但不提供 predictor
accuracy、模型优越性或 search utility。正式源码 commit=`57561d8...`，producer/verifier 各双跑逐字节一致，Linux
focused/full=`5/1047 passed`，exact-path forbidden opens=`0`，GPU/API/base update=`0/0/0`。直接证据：

数学上 `q_t=p_tY_t/E_p[Y]`，且 `TV(p_run,p_pair)` 正好等于 pairing 对任意 `[0,1]` task-level metric 可造成的最大
run-weighted→pair-weighted 聚合偏移。当前 `TV=0.337082500713674`，因此结构上的 sharp worst-case headline leverage 为
33.71 pp；这不是已观察 accuracy 差或 expected bias，closure 后必须用真实 task vector 另算实际偏移。

- `phase1/results/structural_weight_trajectory_7cda_20260826/README.md`；
- `phase1/实验记录/2026-08-26/First960_结构权重时序分解_结果.md`。
- `phase1/实验记录/2026-08-26/OpportunityYield_重加权恒等式与影响上界.md`。

## 0GA. 2026-08-25 outcome 前冻结统一 estimand panel；不改写任何既有实验 primary

结构图谱证明不同聚合会产生相反的 task-mixture 趋势，因此通用 predictor benchmark 第一行在 closure 前冻结为
`task_macro_parent_macro_pair_accuracy`：pair credit 先在 physical decision parent 内平均，再在 task 内平均 parent，
最后 tasks 等权。必须并列且不得 rescue 的三行是 task-pair macro、task→run→parent→pair macro 和 pair micro；所有 arm
要求 exact common pair support，并先在 pair 上求差后用同一 hierarchy 聚合。

该 panel 只控制 generic paper reporting，不 supersede 既有契约：clean scaling 的 task-macro pair primary、component
breadth 的 task-macro parent-macro primary，以及各自 truth/support/effect/bootstrap 均保持原 authority。任一旧 primary
失败时，alternate aggregation、truth channel 或 subgroup 都不能救回。generic inference 固定为 20,000 次 task
bootstrap（seed `20260901`）+ LOTO，并强制 physical-run clustered sensitivity；pair-i.i.d. CI 禁止。

contract / independent SHA-256=`4f394d0e...7adea` / `fcb74182...426de`；源码 commit=`1763030...`，fresh Linux
focused/full=`5/1040 passed`，verifier A/B 逐字节一致，正式 `SHA256SUMS` hash=`cd198c5f...3d402`；
truth/prediction read、GPU/API/model fit/base-LLM update=`false/false/0/0/0/0`。直接证据：

- `phase1/contracts/DECISION_PREDICTOR_ESTIMAND_PANEL_V1.md`；
- `phase1/results/decision_predictor_estimand_panel_v1_20260825/README.md`；
- `phase1/实验记录/2026-08-25/DecisionPredictorEstimandPanel_结果前冻结.md`。

## 0FZ. 2026-08-25 结构依赖图谱确认 pair weighting 会逆转语料均衡趋势

对固定 `7cda` snapshot 的 accumulator summary 与 independent structural gate 做结果盲双实现复算。first-240→当前
339 runs / 30 tasks 时，run-weighted 最大任务占比从 `0.1083333333` 降至 `0.0914454277`、inverse-HHI 描述性
多样性从 `17.8660` 升至 `20.4595`；但 pair-weighted 最大占比从 `0.1714990746` 升至
`0.3123339658`、inverse-HHI 从 `12.0427` 降至 `7.3666`。当前 run→pair task-distribution TV=
`0.3370825007`，pair 主导任务相对其自身 run share 放大 `5.0419625915` 倍。这证明“新增 runs 更均衡”不等于
pair-micro benchmark 的任务权重更均衡。

2,635 pairs 来自 2,593 decision-parent groups；超出 one-pair-per-parent baseline 的只有 42 pairs（占
`0.0159392789`），所以当前集中度主要不是 sibling 组合爆炸，而是任务/run 的 endpoint 与 decision-parent yield 不同。
由此 closure 后的主要 estimand 固定为 task-macro + task bootstrap/LOTO；run-macro/run-clustered 与 pair-micro 只作
次级视图。inverse-HHI 只称描述性多样性，绝非统计 ESS；该结果也不是 predictor accuracy 或方法优越性。

正式 commit=`b8ea5f7...`，focused/full=`7/1033 passed`，producer/verifier 各双跑逐字节一致；atlas / independent
SHA-256=`1c3e5c34...b1a5` / `634c5784...150f`，正式 `SHA256SUMS` hash=`17f41f52...d221d`，
credential filename/content/forbidden-open hits=`0/0/0`。四个未接纳尝试（测试范围、BLAS 超卖、hash-seed 末位差、
文件名护栏）均保留。直接证据：

- `phase1/results/structural_dependency_atlas_7cda_20260825/README.md`；
- `phase1/实验记录/2026-08-25/First960_结构依赖图谱与estimand裁决.md`。

## 0FY. 2026-08-25 ABC 交叉审计把 D&B 主张收紧为“衍生 decision benchmark 的本地增量”

NeurIPS D&B 2025 的 Agentic Benchmark Checklist（ABC，arXiv:2507.02825v5）已经直接评过上游
MLE-bench：其 O.i.1、T.2--T.10、R.1--R.12 的既有评价不能重复计为本项目贡献；T.1 的工具版本缺口和 R.13 的
trivial-agent 缺口也不能靠引用上游消失。新增 24 项人工 crosswalk 严格区分 9 个 `PASS_LOCAL`、9 个 `PARTIAL`、
5 个 `INHERITED_UPSTREAM` 和 1 个 `NOT_APPLICABLE`，且禁止把四类状态二值化为合规总分。

独立 verifier 只验证项目项集、保守状态锁和 24 个本地证据文件的 normalized-LF SHA-256，不认证人工语义。crosswalk /
independent SHA-256 分别为 `fb622cd1...79b1b` / `6fadb5c6...b174b`；prospective outcome / prediction aggregate /
GPU/API=`false/false/0`。当前最关键的真实缺口是：producer 环境/config-v2 尚未在真实批次 outcome-before 部署、
first-960 仍未闭合和发布、prospective clustered effect 表仍被封存。

防 scoop 边界同步收紧：Aletheia（2601.12186）已覆盖 execution-grounded code verifier scaling/recipe/covariate
shift；Agent Psychometrics（2604.00594）已覆盖 unseen task/benchmark/LLM-scaffold 的 task-level performance
prediction。因此不得声称“首个 code verifier”或“首个 agent performance predictor”。可守住的单位是同一真实
MLE-agent 搜索、同一 parent/预算/上下文中的 physical-run sibling decision，加上 run-clean、结果盲时间外确认、
common support、label/coverage/cost audit 与不可变可重建发布。直接证据：

- `phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825/README.md`；
- `phase1/实验记录/2026-08-25/AgenticBenchmarkChecklist_交叉审计与主张收紧.md`。

## 0FX. 2026-08-25 first-960 当前有 657-pair 任务均衡债务；摄取改用逐任务前瞻护栏

> **provenance 勘误：** 本节原 guard v1 直接读取已撤回 matrix，故旧“仅结构 metadata”表述不成立；657-pair
> 算术已由 0GG structural-only v2 从 accumulator+ledger+independent gate 重新建立。

固定结构门要求任一任务的 canonical sibling-pair share 不超过 0.25。snapshot `7cdaefcf...` 的 2,635 pairs 中，
OSIC 有 823 个，占 `0.31233396584440226`，因此当前未通过。令未来非 OSIC / OSIC pairs 分别为 `x/y`，精确整数
包络为 `x >= 657 + 3*y`：若暂不新增 OSIC，至少须观察到 657 个非 OSIC pairs；之后每新增 1 个 OSIC pair，累计
至少配 3 个非 OSIC pairs。

657 只解除当前 OSIC 债务。达到该点时总数为 3,292、每任务上限为 823；仍须对所有任务同时执行
`4*(current_t+future_t) <= current_total+sum_future_all_tasks`，避免把新增量堆到另一个任务。producer 应暂时避开
OSIC、轮换其他任务，并在每个稳定 snapshot 按实际 canonical pairs 重算。pair yield 不固定，所以 657 绝不能写成
raw-run 配额。

该护栏仅使用结构 metadata，不读 outcome/prediction aggregate；不删除、重排或排除已进入的 run，不改变 chronological
first-960 membership，也不是提前停止门。guard/independent SHA-256 分别为 `fd87246b...51b0` /
`7feaf1a7...760d`。直接证据：

- `phase1/results/task_balance_accrual_guard_7cda_20260825/README.md`；
- `phase1/实验记录/2026-08-25/First960_任务均衡摄取护栏.md`。

## 0FW. 2026-08-25 post-baseline 90 个归档裁决已形成 outcome-blind 完整拒收台账

observer metadata 在 snapshot `7cdaefcf...` 时把 218 个 source archives 精确、互斥且完备地分成 128 个 sealed
baseline、78 个 accepted archive transactions、12 个 structural rejections 和 0 个 pending。由此 post-baseline
归档拒收率为 `12/90 = 0.13333333333333333`；12 个拒收中 11 个是任务身份元数据问题（`11/12 =
0.9166666666666666`），另 1 个没有 checkpoint journal。

更关键的是，出现拒收的 6 个竞赛全部也至少出现过一次 accepted archive transaction（6/6）。这证明结构有效性是
archive-level、随批次变化的属性：不能用 task whitelist/blacklist 替代逐归档 credential-first 门控。该结论强化
Decision Corpus / D&B 的 audit-protocol 贡献；它不估计 producer metadata 修改的因果效果，也不说明被拒收归档的模型质量
更差。

partition/partition-independent/ledger/ledger-independent receipt SHA-256 分别为 `aa161d4c...f07c` /
`ffa0974d...b82e` / `b194b1bc...ad03` / `1281797c...7a60`；12 个 registry 均与相邻 diagnostic receipt 逐哈希绑定，
0819 外部安全 registry 已以逐字节相同版本
发布进仓库。outcome/prediction aggregate/GPU/API=`false/false/0/0`。直接证据：

- `phase1/results/structural_rejection_ledger_v1_20260825/README.md`；
- `phase1/results/prospective_structural_rejection_20260821/README.md`；
- `phase1/实验记录/2026-08-25/Prospective0823_最终结构资产与拒收台账.md`。

## 0FV. 2026-08-25 7cda 七臂同池扩至 2,635 pairs；transition 仍不解锁 effect

0823 六个归档最终为 4 accepted / 2 rejected。相对 f109，语料增加 11 runs、204 endpoints、46 canonical sibling
pairs 和 1 task；当前为 339 eligible physical runs、10,196 endpoints、2,635 pairs、30 tasks，其中 334 runs 有 finite
decision。exact-code unique fraction=`0.9970576696743821`，21 个 duplicate groups 全部局限于同一 run，跨 run/task
duplicate groups 均为 0。

在该最终 snapshot 上，WL 四臂与 transition 三臂各覆盖同一组 2,635 pairs、334 runs、30 tasks；独立 canonical
identity 得到 intersection=union=2,635、IoU=1.0、left/right 同向=2,635。activation 交叉表为 463 个双 activation
后、507 个仅 WL activation 后、1,665 个双 support-only。transition strict-effect-eligible 只有 399 pairs、52 runs、
17 tasks，状态仍为 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`；不得读取 effect。

matrix SHA-256=`be63fbe0...f6b7`；formal focused/full=`10/1002 passed`，`SHA256SUMS` 文件自身 SHA-256=
`f67c1eca...1a26`，credential filename/content hits=`0/0`。这是未来 paired benchmark 的正面 common-support 资产，
不是 accuracy、方法优越性、runtime/cost、search utility 或 first-960 closure。直接证据：

- `phase1/results/prospective_0823_batch_postflight_20260825_6299865/README.md`；
- `phase1/results/prediction_escrow_coverage_7cda_20260825_6299865/README.md`；
- `phase1/实验记录/2026-08-25/Prospective0823_最终结构资产与拒收台账.md`。

## 0FU. 2026-08-25 七臂同池结构结果已进入 Decision Corpus v6 机器索引；仍无 effect unlock

新增 `decision_corpus_evidence_index_v6`，在 v5 的 9 项 evidence stack 后加入第 10 项
`prediction_escrow_common_support`。它绑定 GitHub 可访问、与 formal 逐字节相同的 f109 coverage matrix 与独立复核，
把“七臂共享 2,589 个 canonical structural pair identities”升级为机器契约；同时强制保留 417/507/1,665 的双
activation 交叉表、transition missing-parent null 和 363 strict-effect-eligible pairs，禁止把 common pair universe
写成 common strict-effect population。

正式 commit=`3182b75...`；v2 fresh-worktree 为 `991 passed, 1 skipped, 47 warnings in 71.75s`，builder/verifier
各自 A/B 逐字节一致。index 包含 10 entries / 28 artifacts / 3 bound files / 362 assertions，SHA-256=
`0ee7d885...f9d1`；formal `SHA256SUMS` 文件自身 SHA-256=`784271eb...0680`。outcome read / prediction aggregate /
GPU/API=`false/false/0`，credential filename/content hits=`0/0`。

GitHub 发布 commit=`2735d1b...` 后的第二个 fresh worktree 进一步为 focused/full=`8/992 passed`，从固定源码
重建的 index 与 independent receipt 均和仓库版本逐字节相同；post-push `SHA256SUMS` hash=
`f29728ef...5663`，credential hits 仍为 `0/0`。

首次 formal 因未限制 BLAS 线程导致约 2,892% CPU，在 14% 测试进度主动中止；builder/verifier 尚未运行，失败根目录
原样封存，`SHA256SUMS` hash=`379754b3...c947`。v2 固定所有数值库为单线程后通过。该正结果只消除未来 paired
benchmark 的 pair-pool 混杂，不提供 predictor accuracy、方法优越性、runtime/cost、search utility、first-960 closure
或 transition gate 通过结论。详见：

- `phase1/results/decision_corpus_evidence_index_v6_20260825/README.md`；
- `phase1/实验记录/2026-08-25/DecisionCorpusEvidenceIndex_v6_七臂同池机器证据.md`。

## 0FT. 2026-08-25 f109 七臂 prediction escrow 已证明逐 pair 同池；效果仍未知且 transition 支持不足

在 outcome-blind `f109` 上，WL 四臂与 transition 三臂各有 2,589 structural pairs、324 个有 pair 的 runs、29 tasks；
独立 canonical unordered identity 显示 intersection=union=2,589、IoU=1.0、同向 left/right=2,589，mapping
SHA-256=`e0131368...392f`。这是可做未来 paired comparison 的正面 benchmark 资产，消除了方法间 pair-pool 混杂；
但它没有读取 truth，也没有 accuracy、方法优越性、search utility 或 runtime/cost 结论。

两套 activation 不同，必须保留交叉表：417 pairs 同时在两者 activation 后，507 仅在 WL activation 后、transition
仍为 support-only，1,665 在两者 support-only。transition 只有 363 个 `strict_effect_eligible` pairs，45 runs、16 tasks；
仍因 pairs<1,500、runs<150、dominant task share=`0.29476584`>0.25 而
`TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`，禁止提前揭盲。正式 commit=`2c5626d...`，focused/full=
`10/975 passed`；formal `SHA256SUMS` 自身 SHA-256=`e5006577...e7c7`。6 个失败尝试无覆盖保留，失败/复验 registry
hash=`dff24b09...8f6e`。详见：

- `phase1/实验记录/2026-08-25/PredictionEscrowCoverage_f109_七臂同池结构矩阵.md`。

## 0FS. 2026-08-25 future config sidecar v2 已补 prompt 指纹与批次原子导出；尚未部署真实 producer

现有 v1/历史 `config_sha256` 只覆盖 client、hardware 与两个时间限制，无法区分学长 `b80c056` 的 system/user prompt
拆分。新增 future-only v2：从未归档 producer `dojo_config.json` 去掉恰好两个 run-specific 路径字段后，对完整 resolved
solver canonical JSON 计算 SHA；config stratum 同时纳入 generator release，consumer 再与 source manifest 的逐 run
`producer_commit` 组合成 producer stratum。mixed operator clients、credential-shaped raw config、symlink、篡改与缺覆盖均
fail closed。

本地 v1+v2=`19 passed, 1 Windows symlink skipped`；fresh Linux commit=`a6776be...` 为 `20 passed`，receipt
`SHA256SUMS` hash=`93bde54b...8a3b`。当时状态为 `V2_HANDOFF_READY_NOT_DEPLOYED`：没有真实 next-batch sidecar，
0823 archives 禁止事后回填为 prompt A/B 或 exact-stratum 证据。详见：

随后新增 4/8-seed batch wrapper：所有显式未归档 config 先全量校验，再检查重复 run ID、按 run_id 排序并通过
exclusive temp + `fsync` + atomic replace 一次写出；任一坏 row 整批零输出。commit=`f4099ad...` 的 fresh Linux
focused/full=`17/1000 passed`，receipt `SHA256SUMS` hash=`ceb4959c...31b5`，credential hits=`0/0`。正式状态仍为
`V2_BATCH_EXPORTER_READY_NOT_DEPLOYED`，因为 `real_producer_sidecar_observed=false`；工具通过不等于生产已部署。

集成报告 commit=`aa91322...` 的 fresh Linux 全套另为 `984 passed, 47 warnings in 75.33s`，postpush receipt
`SHA256SUMS` hash=`943f787d...7e26`；这 984 包含 coverage 975-test 基线与 v2 新增的 9 个测试。

- `phase1/contracts/SENIOR_EXPERIMENT_CONFIG_MANIFEST_V2.md`；
- `phase1/实验记录/2026-08-25/SeniorConfigSidecar_v2_prompt指纹交付.md`；
- `phase1/实验记录/2026-08-25/SeniorConfigSidecar_v2_批次原子导出器.md`。

## 0FR. 2026-08-25 target-300 改为 5×300s 多归档静默触发；覆盖 0FP 的 immediate-monitor 状态

0FP 的 ancestor-safe immediate monitor 在 f109 未变、formal 未启动、outcome 未读时封存，stop receipt
`SHA256SUMS` hash=`af128285...c4f6`。替代 PID=`1986763` 绑定 exact science commit `ab59a01...`，要求新 snapshot
连续 5 轮、每轮 300 秒完全相同后才运行一次 target formal；snapshot 继续变化则计数清零。当前已连续 6 轮仍为 f109，
`outcomes_read=false`。这只避免同一批多 archive 到达时先封中间 receipt，不改变 target/overshoot/closure/truth 契约。
详见：

- `phase1/实验记录/2026-08-25/Target300_多归档静默触发部署收据.md`。

## 0FQ. 2026-08-25 学长 0823 六归档仅完成预摄取观察；新 producer stratum 尚不可归因

连续 intake 在 metadata 层观察到 archive 总数从 212 增至 218；新增 `0823` 六个归档、共约 146 MB，当前均为
pending，未进入 snapshot。它们的最晚文件 mtime 为香港时间 `2026-08-25 00:16:28`；固定门同时要求 mtime age≥
21,600 秒、至少 3 次观察和稳定跨度≥600 秒，因此在 bytes 不再变化时最早约 `06:16:28 +08:00` 才可逐个处理。
截至本节写入，first-960 仍为 `f109` 的 328/960，target-300 仍为 53/300，outcome 未读。

学长同日 `dojo-reproduce@b80c056` 把 AIRA/AIDE operator 的静态 system policy 与动态 user context 正式分离，发生在归档
mtime 前约 55 分钟；但 0823 目录只有 tar 文件，没有 outcome 前 config sidecar。归档 mtime 不是 run 启动时间，不能据此
断言这些 runs 使用或未使用 `b80c056`。所以若结构摄取通过，它们可按固定时间序进入自然前瞻 corpus，却不能作为
exact-stratum scaling confirmation、prompt A/B 或 producer-config 因果证据；后两者仍要求 0FD 的 outcome 前 sidecar。
详见：

- `phase1/实验记录/2026-08-25/Prospective0823_六归档预摄取观察与producer边界.md`。

## 0FP. 2026-08-25 target-300 ancestor-safe monitor 已部署；首次交接失败完整保留

commit `ab59a01...` 推送后，旧 `795e3da` monitor 在 `f109` 未变、未看到 trigger、未启动 formal runner、未读 outcome
的状态下停止并封存，receipt `SHA256SUMS` 自身 SHA-256=`1857ec8b...4847`。首次交接在停止旧 PID 后因错误假定旧目录
已有 `runner_sha256.txt` sidecar 而 fail closed；没有隐藏或覆盖，failure history 已进入不可变收据。恢复脚本从旧 runner
本体现场计算哈希、复核半成品边界后启动新 PID=`1985359`。

新 monitor 绑定 exact commit `ab59a01...`，runner/monitor/launcher SHA-256 分别为
`c6f6ed7a...660e` / `02fd9081...36b0` / `00f62349...2048`；首轮仍为 `f109` no-change。runner 继续建立 exact
detached worktree，但允许发布分支为其 descendant，因此今后的 docs-only push 不再要求轮换。truth/effect/GPU/API=
未打开/空/0/0。详见：

- `phase1/实验记录/2026-08-25/Target300_ancestor-safe_monitor部署与失败恢复.md`。

## 0FO. 2026-08-25 H200 jobs 11410/11411 均触发 24h TIMEOUT；仅封存调度事实

继 11408 后，学长 H200 exploratory jobs `11410/11411` 也分别在 `1-00:00:17` / `1-00:00:09`
触发顶层 `TIMEOUT`；节点为 `projgpu6`（2 GPUs）/`projgpu13`（4 GPUs）。两份 terminal receipt 与总 monitor
receipt 已逐文件复验并递归只读；`logs/metrics/outcomes/checkpoints_read=false`，没有打开训练日志、指标、预测、
checkpoint 或共享 output，也没有模型效果结论。三份 `SHA256SUMS` 自身 SHA-256 分别为
`e7e20059...a607`、`e75befc7...4d56`、`740f8f1b...824a6`。这不改变 0FD：这些 test-touched、映射未冻结的
exploratory jobs 不能升级为 clean scaling confirmation。详见：

- `phase1/实验记录/2026-08-25/H200_11410_11411_TIMEOUT_调度收据.md`。

## 0FN. 2026-08-24 target-300 runner 去除脆弱的 exact branch-head 耦合

target cohort runner 仍在调用者绑定的 exact control commit 上建立 detached worktree并检查 HEAD，但发布证明由“fork
branch HEAD 必须永远等于 control commit”修正为“control commit 必须是当前 fork branch 的 ancestor”。这避免纯文档
push 让已运行 monitor 在下批到达后无科学理由地失败，同时仍拒绝未发布/被 force-push 删除的 commit，也不会使用
descendant 的新代码。新增攻击测试锁住 ancestor proof + exact worktree proof。`5d44361` monitor 已在新快照前封存，
替代 `795e3da` monitor 首轮仍停在 `f109ac...`，outcome/effect/GPU/API=未读/空/0/0。详见：

- `phase1/实验记录/2026-08-24/Target300_monitor_exact_head耦合修正.md`。

## 0FM. 2026-08-24 GitHub LFS fresh clone 可逐字节重建 v11；发布可访问性 PASS

在不复用本地/集群主仓库 LFS cache 的隔离 fresh clone 中，从 GitHub fork 的 `phase1-value-critic` 精确拉取
v11 registry 的 29 个 immutable batches（303,226,677 bytes / 16,012 rows），随后统一 rebuild 得到
305,750,663 bytes / 16,012 rows / SHA-256=
`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`，与 release descriptor 逐项一致；
secret-shape count=0，临时 clone/payload 已安全清理，formal manifest 与只读复验通过。这证明学长可直接通过 GitHub
LFS+`rebuild_corpus.sh` 获取 v11，不依赖我们的 big-data storage。

边界不变：v4/v5 仍不可从已发布 batches 逐字节恢复；0812 仍因 temporal-blind labels 明确 withheld；0821/0822
prospective intake 也尚未成为公开脱敏 batch。不得把本 PASS 外推为这些版本已发布。正式证据见：

- `phase1/实验记录/2026-08-24/CorpusLFS_v11_全新克隆逐字节重建.md`；
- `/research/d7/spc/yzyang4/corpus-lfs-freshclone-audit/5d44361-v11-v1`。

## 0FL. 2026-08-24 target-300 首次闭合到 component-breadth prediction escrow 已自动接力

dual-truth runner 原本已把 component-breadth prediction escrow 设为首次 outcome read 的硬前驱，但闭合锚出现后仍
依赖人工运行。现部署单次、identity-only closure hook：只监视固定只读
`FIRST_CLOSED_COHORT_ANCHOR.json`，严格校验 target≥300、完整 boundary-archive 闭合及 truth/outcome=false 后，运行
冻结的 9-arm/36-fit CPU prediction runner；不运行 dual-truth、不自动揭盲、不重试或另选 cohort。monitor/runner
SHA-256 分别为 `aa62ca...d23d` / `257373...7d97`，首轮仍是 no-anchor，GPU/API=0/0。该完善只消除人工漏步，
不是效果结果；first-960 与 target-300 仍不得混池。详见：

- `phase1/实验记录/2026-08-24/Target300_首次闭合预测接力_部署收据.md`。

## 0FK. 2026-08-24 WL/graph 已追加到 f109；finite-decision run 口径修正后仍 NO_UNLOCK

固定 `031edb3` 四臂 WL/graph prediction escrow 已从 0819 的 6,471 endpoints / 249 runs / 1,665 pairs
结果盲追加到 `f109ac...` 的 9,992 / 328 / 2,589；新增 3,521 endpoints、79 endpoint-bearing runs、924 pairs，
旧 rows 逐字段不变。producer/verifier 分别耗时 17:43.80/16:38.10，四臂独立最大差均为 0；18,328 条 trace
禁区命中=0、network=0、11,316,324 bytes 凭据扫描 matches=0，manifest 复验和只读权限通过。

追加后发现旧 gate verifier 把所有 strict endpoint-bearing runs（79）当成预注册的 finite-decision runs。独立解析证明
其中只有 76 个实际贡献至少一个 strict sibling pair。修复 commit `c29bcde...` 现把 `runs/tasks` 从 pair rows 统计，
并另保留 `endpoint_runs/endpoint_tasks`；endpoint-only run 攻击测试通过。fresh Linux focused/full=
`20/964 passed`，corrected verifier 双跑逐字节一致，非 import parser 精确复算。

修正后的 strict 支持为 3,521 endpoints / 79 endpoint runs / **76 finite-decision runs** / 924 pairs / 17 tasks；
主导 `osic-pulmonary-fibrosis-progression`=545/924=`0.5898268398268398`。因此 tasks 门通过，但
pairs、runs、dominant 三门失败；最低 pair/run 缺口为 576/74，若 dominant count 固定，需再增加 1,256 个非主导
pairs 才能到 0.25。正式状态仍 `NO_EFFECT_UNLOCK`，first-960 也只有 328/960 且无 closure；outcome/effect/GPU/API=
未读/空/0/0。不得删 OSIC、改 gate、改 activation 或与 target-300 混池。详见：

- `phase1/实验记录/2026-08-24/WLGraph_f109追加与finite-decision-run门修正_正式裁决.md`；
- prediction root `/research/d7/spc/yzyang4/wl-graph-escrow-current/5826ef7-f109ac928ed0-v1`；
- corrected receipt `/research/d7/spc/yzyang4/prepush-wl-finite-decision-run-gate/c29bcde-v1`。

## 0FJ. 2026-08-24 学长 H200 job 11408 触发 24h TIMEOUT；只封存调度事实

job `11408` 的顶层 scheduler 状态为 `TIMEOUT`，elapsed=`1-00:00:01`，2 GPUs on `projgpu39`；这不是正常
完成，也没有模型效果含义。由于它是 `/bin/bash` interactive allocation，尚无逐 job launcher/seed/model/data/output
映射，本轮只封存 scheduler metadata，未打开日志或 metric、未挑 checkpoint、未复制共享 output。正式 v3 receipt
manifest/只读复验通过，`outcomes_read=false`、`metrics_read=false`。11410/11411 当时仍运行；后续同样只在退出后
按真实映射保全，不把 test-touched exploratory checkpoint 升级为 clean confirmation。详见：

- `phase1/实验记录/2026-08-24/H200_11408_TIMEOUT_调度收据.md`；
- `/research/d7/spc/yzyang4/h200-exploratory-preservation/scheduler-11408-timeout-20260824-v3`。

## 0FI. 2026-08-24 transition 任务集中度显著改善，但预注册门仍未通过

对 0FH 的同一固定旧/新 escrow 产物补做了**结果后、仅结构、描述性**任务均衡审计。两套不共享解析实现
（Python stdlib JSON 与 `jq-1.7`）对 task-count TSV 逐字节一致：旧 `79701f...` 的 222 个 eligible pairs 中，
主导任务 `tensorflow-speech-recognition-challenge` 为 107 个，占 `0.481981981981982`；新 `f109ac...` 的
363 个 eligible pairs 中该任务仍为 107 个，占 `0.29476584022038566`。因此 0822 新增的 141 个 eligible pairs、
17 个 eligible runs、5 个 eligible tasks 没有增加旧主导任务，集中度绝对下降
`0.18721614176159632`（exact=`5029/26862`）。

这是支持自然时间外语料正在扩宽的正面结构证据，但**不是预测效果或通过门槛**：当前 `0.29476584022038566>0.25`，
正式状态仍是 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`。若且仅若主导计数保持 107 不变，至少再增加
65 个非主导 eligible pairs 才能到达 0.25；旧快照对应条件缺口为 206。这个 65 是确定性算术，不是生产预测、
功效保证或改变任务生产分布的授权。1,500 pairs 与 150 runs 两门也仍 FAIL，不得提前揭盲。

首次 v1 wrapper 因宽泛 `sk-...` 扫描把 `protocol` 字段中、前一字符为字母的普通子串误报为两份凭据文件，已在
未写 `COMPLETE` 的状态 fail closed 并封存；redacted classifier 仅记录字段路径/类型/长度/哈希，边界感知高置信扫描为
0。全新 v2 从固定输入重跑，forbidden/credential hits=`0/0`，递归只读；趋势产物也独立封存。两轮均
`outcomes_read=false`、effect metrics=`[]`、GPU/API=`0/0`。证据与边界见：

- `phase1/实验记录/2026-08-24/TransitionFutureEscrow_任务集中度趋势_结构审计.md`；
- 当前单点只读产物
  `/research/d7/spc/yzyang4/transition-task-balance-audit/17f0b27-f109-v2`；
- 旧→新趋势只读产物
  `/research/d7/spc/yzyang4/transition-task-balance-trend/17f0b27-797-f109-v1`。

## 0FH. 2026-08-24 transition future escrow 已补齐 0822；任务广度门首次通过，仍 NO_UNLOCK

固定 first-960 scorer 已随 74 个 accepted transactions 完整前滚到 snapshot `f109ac...`：registry 覆盖
9,992 eligible endpoints / 328 scoreable runs / 29 tasks，`labels_read=false`、`label_vault_opened=false`。
独立 transition prediction escrow monitor 此前在 `2026-08-23T03:58:28Z` 正常完成 145 polls，最后停在
`79701f...`，因此 0822 入库后存在 prediction asset 滞后而不是语料丢失。现以原 science commit `7458f09...`、
原 monitor control `ca8e000...` 和逐字节相同脚本 SHA-256=
`52df665581b31986bb9db0cb79458e69194d1e7398cbabcd409b6670c5ded154` 结果盲续接到 `f109ac...`；旧
2,426 rows 逐字段存活，producer/不 import producer 的 verifier 均返回 0，2,589 个总 pair 的 future margin
独立复算最大差=0，forbidden-path/credential hits=0/0，产物递归只读。

结构支持从旧 strict/eligible/runs/tasks=`254/222/28/11` 前滚为 `417/363/45/16`。因此预注册的
minimum-15-tasks 门首次 PASS，parent-source coverage=`0.8776978417266187` 继续 PASS，endpoint/run/code
overlap 三门继续 PASS；但 1,500 eligible pairs、150 runs 与 dominant task share≤0.25 三门仍 FAIL。正式状态保持
`TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`，effect metrics 为空，prospective outcomes/GPU/API=
`未读/0/0`。这是一项正向的结构支持进展，不是 transition critic 效果、accuracy 或 search gain；不得因 task 门已过
而提前揭盲。summary SHA-256=`da62681ed53835de40a9a3dda583e589e05aef7c5bd1d602cc556b78c851d5cf`，
证据与边界见：

- `phase1/实验记录/2026-08-24/TransitionFutureEscrow_0822补齐与任务门进展_正式裁决.md`；
- 远端只读产物
  `/research/d7/spc/yzyang4/transition-future-escrow/7458f09-append/20260824T111032Z_f109ac928ed0`。

## 0FG. 2026-08-24 0822 双结构拒收完成；摄取恢复，两个冻结人口仍保持 outcome-blind

0822 新观察的 8 个 archive 已全部 settled：6 个完整进入 append-only intake，另 2 个按各自精确 bytes 拒收。
`multi-modal-gesture-recognition-8seeds.tar.gz` 的 4/4 checkpoint journal 均没有可识别 competition identity；
`AI4Code-8seeds.tar.gz` 则是另一种结构失败：4 个 discovered run roots 全部只有 live journal、checkpoint journal=0。
后者暴露并修复了旧 auditor 对“0/0 journals 全通过”的 vacuous-success 表述；现在没有 checkpoint 的 archive 使用独立
`ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS` reason，不能再冒充 task-identity audit pass。两类拒收都不从文件名补 task、
不读取 live journal、env、code/stdout/grade/metric/prediction/outcome，也不做部分 salvage。

恢复控制 commit=`5d0baaddca14ce6db53a43ed1976b85a8b24c9f3`。其 fresh Linux prepush focused/full=
`28/960 passed`，postpush focused=`28 passed`；连续 monitor 已在该 exact clean commit 上连续两轮打印
`archives=212, baseline=128, ready=0, rejected=10, transactions=74, outcomes_read=false`，watchdog 同时存活。
当前 first-960 snapshot=`f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708`：
328/960 provisional physical runs、9,992 endpoints、2,589 structural pairs、29 tasks，closure 尚未提供，
`label_vault_opened=false`，没有 frozen population 或 accuracy。

独立 target-300 identity cohort 已在同一 control commit 上正式双跑到 53/300：17 accepted archives、16 tasks、
remaining=247；旧 33-run/11-archive 前缀精确存活，20 个 settled-prefix archives 中 3 个为结构拒收。
producer×2/verifier×2 逐字节一致，focused/full=`11/960 passed`，formal `SHA256SUMS` 自身 SHA-256=
`7285cc3b6b91bbfdb390d79d37c103d19f2e426628f5c5b32a4ac980d4d8ce65`，全部 manifest 条目复验通过。
状态仍是 `FUTURE_COHORT_COLLECTING`；label/score/outcome/raw payload、truth support、prediction effect 与 replay
均未打开/未计算/未授权。53/300 只是合法数据进展，不是正效果，也不能与 first-960 混池。详见：

- `phase1/实验记录/2026-08-24/Prospective0822_双结构拒收与摄取恢复_正式裁决.md`；
- `phase1/results/prospective_structural_rejection_20260824/`；
- `phase1/results/prospective_structural_rejection_ai4code_20260824/`。

## 0FF. 2026-08-24 task-relative raw-gap critic 正式 NO_UNLOCK；同池方法线关闭

为检验 official-five-decimal raw grade 除了 truth support 外能否改善 critic 训练，新增一个严格限定的
retrospective dev-only 资格实验。固定 component-clean train/dev 为 4,689/551 pairs、28/25 tasks、127/41
comparison components、1,473/246 released parent/groups；结果前 structure-only 审计确认 pair/endpoint overlap=0，
每个 task 的 train gap Q75 严格为正，outer test/future truth/GPU/API/model fit=`未打开/未打开/0/0/0`。

唯一 primary candidate 是 task-relative `gap_weighted_bt`：权重先按 train-only task Q75 标度并 clip 到 `[0.25,4]`，
再 task 内均值归一为 1，避免把 task 总质量变化混入 gap 强度。除同特征同训练行 `binary_bt` 外，另设
`gap_permuted_bt`：保留每 task 完全相同的权重 multiset，但按 outcome-independent hash 排序循环置换 pair↔weight，
用来排除任意非均匀加权/正则化解释；`gap_ridge` 只作 non-rescuing diagnostic。primary 聚合固定为
pair→released parent/group→task；只有 true-gap 对 binary 的 delta≥+0.015 且 CI/LOTO/正 task 门全过，并且对
permuted control 的 delta>0 且 CI/LOTO/正 task 门也全过，才可申请另名 future prediction escrow。当前 dev baseline
已经看过，故即使 PASS 也不称 frozen/future confirmation、方法首创、search utility 或 neural RM 改善；失败后禁止同池
改 Q75/clip/阈值/超参。graded feedback、preference intensity、adaptive margins 与数据加权已有直接先例，本线不申
“首次利用分差”。机器合同与结果前记录：

置换本身的 fit 前审计确认 28-task 权重 multiset 全部精确不变，全局原/置换权重 Pearson=
`0.0001798458547192397`、task median Pearson=`-0.031632580629732544`，model fit 仍为 0。

- `phase1/critic_gap_aware_qualification_v1.json`；
- `phase1/实验记录/2026-08-24/GapAwareCritic_TrainDev资格实验_结果前冻结.md`。

首次冻结 commit `959764b22880d797b08a48f70654ff320b2b7d54` 的 precommit focused/full 为 20/955；fresh
formal 在任何真实 fit 前因 producer/verifier 把合法 dev `intask_split="dev"` 误断言成 `"train"` 而 fail-closed。
失败 root `critic-gap-aware-qualification/959764b-v1` 原样保留；没有 producer artifact、Cards JSON parse、模型预测
或 dev aggregate，真实 fit/GPU/API/future truth=`0/0/0/未打开`。只允许修正 role-specific schema 与 synthetic
fixture，机器合同、输入、臂、门槛和 estimand 不变；新 commit/new root 必须从头运行。

唯一工程修复 commit=`b79717b3956a1b546943708a4c62e65841ffb663` 已在 fresh no-smudge worktree 从头正式运行。
focused/full=`20/955 passed`；producer×2 与不 import producer 的 source-refit verifier×2 均逐字节一致，最大数值差=0，
正式 post-audit 全部 SHA 与 credential 门通过。支持门为 25 tasks、246 released parent/groups、dominant parent share=
`0.0975609756097561`，全部通过。

科学裁决为 **`RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK`**。headline parent→task macro accuracy 为 binary=
`0.5102786098859761`、gap-weighted=`0.5289167039832994`、gap-permuted=`0.5324983224925042`。true-gap 相对
binary 点差虽为 `+0.01863809409732331`，但 task-bootstrap CI=`[-0.02676049343489505,0.066027790932867]`，
正任务仅 12/25=`0.48`；相对置换负控反而为 `-0.0035816185092047113`，CI=
`[-0.04433344970163935,0.0395666585234688]`，LOTO 最小值也为负。因此不能把改善归因于 gap 信息，ridge、micro、
gap-weighted utility 或 Draft/Improve subgroup 均不得 rescue；本 dev 上禁止再调 Q75/clip/阈值/超参，也不建立 future
gap-aware escrow。

postflight 还保留了一次错误假设审计：v1 错把所有 released groups 都要求为 physical siblings，按预期失败；语义分层
v2 独立确认 Improve train/dev=`1787/257` 全部是同-run lineage siblings，而 Draft=`2902/294` 是既有 synthetic
cross-run released groups。train/dev 共享 8 个 Draft parent groups（139/29 rows），Improve 共享为 0；因此本结果只能称
component-clean mixed estimand，不能称 Draft-parent-novel。完整证据见：

- `phase1/实验记录/2026-08-24/GapAwareCritic_TrainDev资格实验_正式裁决.md`；
- `phase1/results/critic_gap_aware_qualification_20260824_b79717b/`。

## 0FE. 2026-08-24 future component-breadth prediction/evaluation escrow 已 exact-commit 冻结；效果未知

旧等 pair 预算 breadth 仍是 `RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK`：accuracy 点效应虽为
`+0.0332204391514186` 且三 seed/全部 LOTO 同向，task-bootstrap CI 仍跨 0；不得同池追加 seed 或换 endpoint
rescue。本轮只把该线索变成一次合法的独立 future hypothesis，并在任何 future truth 前冻结 prediction escrow。

新机器合同已完成 pre-truth review、等待 exact-commit 冻结（最终 commit 以本节后续回执为准）：逐字节复用
旧 component-clean train/Cards、`broad/concentrated/random × seeds 20260823/24/25`、每臂每 seed 2,353 pairs、
固定 char-TFIDF/LR；9 份真实 unordered-pair selection SHA 已由 structure-only preflight 重建并写入合同。future
population 锁为当前 score-channel identity-closed target-300 cohort 的 eligible physical siblings，prediction 必须先于
truth，后续只 join 原 dual-truth SHA lottery 的 selected parents，不允许结果后重选。

official-five-decimal raw grade 是 revised high-resolution primary；旧 `y_norm` 只作描述性 sensitivity，不能形成第二个
confirmatory/replication 主张，log-loss/random 同样只作 non-rescuing diagnostics。primary effect 前必须满足 raw
non-tied parents≥200、实际 contributing runs≥150、tasks≥50、dominant task share≤0.20；随后还需 point≥+0.02、
三 nuisance seeds 全正、task-bootstrap CI low>0、LOTO 全正。tasks≥50 只是 analyzability floor，不是 power gate。

prediction producer、独立 source-refit verifier、post-truth evaluator、不 import evaluator 的独立 outcome verifier 及
三阶段手动 CPU runner 已实现。scientific commit=`e1093d8007449954c4561611c2ff381c55f7abe8`；fresh no-smudge
exact-commit 联合 focused=`61 passed, 2 warnings`，完整 phase1=`935 passed, 35 warnings`，不可变复验
`SHA256SUMS` 自身 SHA-256=`6011cbad9072cad8861aca95304906173b494db189118cba50050f6a026b9f30`。
release-only commit=`d416c741dcfa8178699bd2027ab4bcc7154ef5f7` 已只把 prediction/truth runner 绑定回 scientific commit；
其 fresh Linux 静态验收=`26 passed`，回执 `SHA256SUMS` 自身 SHA-256=
`8f2d18365239ef859232e12e51e5296d42c9fac006c3a832bcfcea3004ba83aa`。evaluation runner 仍以全零值 inert，必须等
prediction/dual-truth 两个不可变 bundle 真实产生后再另行绑定。所有科学 Python
子进程使用 `env -i` allowlist，不继承 provider credential。真实训练源 structure-only 为 4,689 pairs/28 tasks/127
components/430 runs，9 臂 receipt 全过、model fit=0。当前 collecting 33-run receipt 真实负控 rc=2，training/vault/score
forbidden open=0；故尚无 future accuracy 或正结果。该 supporting hypothesis 不取代 first-960 critic confirmation，也不把
300-run support cohort 写成已获批的 mechanism-effect experiment；不申 diversity/sampling 方法 novelty。即使为正，
estimand 也只是两个预声明 curation policy 的差异，不能归因于 component/run breadth 单独因果作用。证据：

连续 intake monitor 仍健康。`2026-08-23T17:40Z` 只在 metadata 层观察到 archive 总数由 204 增至 212；截至
`17:55Z` 仍为 `ready=0, transactions=68, outcomes_read=false`，所以这 8 个 archive 尚未过 6 小时稳定门、尚未入 intake，
也没有改变 33/300 formal cohort。不得把“已观察到”写成“已入库”。

- `phase1/critic_component_breadth_future_escrow_v1.json`；
- `phase1/critic_component_breadth_future_evaluation_v1.json`；
- `phase1/scripts/run_critic_component_breadth_future_escrow_20260824.sh`；
- `phase1/scripts/run_critic_component_breadth_future_evaluation_20260824.sh`；
- `phase1/verify_critic_component_breadth_future_evaluation.py`；
- `phase1/实验记录/2026-08-24/ComponentBreadth_FuturePredictionEscrow_预注册与实现.md`。

## 0FD. 2026-08-24 H200 结果保全与 next-batch config sidecar handoff 就绪；均非效果

学长已推送的 `dojo-reproduce@62964aa` 三份 H200 launcher 与当前 scheduler jobs 只能作 exploratory：三个 job
实际 WorkDir 是学长 `/research/d2/gds/zzchen2/...`，逐 job commit/launcher 尚未绑定；已推送 trainer 又把 outer test
周期性用于 checkpoint eval。新增 handoff 要求先内容盲保存完整 checkpoint/log/scheduler/data/code/environment，禁止
事后补 prediction/ledger 或把 test-touched checkpoint 改称 frozen；clean confirmation 仍须另起 dev-only
`Qwen3-Base {0.6,1.7,4,8}B × seeds {6,7}` 8-run matrix，并另获 GPU 预算批准。

同时给学长准备了下一批 archive 的 `senior-experiment-config-manifest-v1` sidecar 交接与 synthetic schema example；
Linux 现有攻击测试 11/11。sidecar 必须由 producer 在 outcome 前从启动 config 导出，当前 33-run cohort 禁止回填；
真实 expected/source/config inputs 尚不存在，故状态只能是 `HANDOFF_READY_NOT_DEPLOYED`，不能称
`CONFIG_PROVENANCE_VERIFIED` 或 interaction support。两项均 GPU/API/future truth=0/0/false。证据：

- `phase1/实验记录/2026-08-24/H200_CleanConfirmation_结果保全Handoff.md`；
- `phase1/实验记录/2026-08-24/SeniorConfigSidecar_下一批Handoff.md`；
- `phase1/examples/senior_experiment_config_manifest_v1.example.jsonl`。

## 0FC. 2026-08-23 coarse-label/tie 直接先例关闭理论首创；MLE transform audit 仍是 D&B 正资产

新增一手防 scoop 核查确认三条直接边界：ICML 2025 *Reward Modeling with Ordinal Feedback* 已从理论与实验说明
粗粒度 binary feedback 会丢失 fine-grained/tie 信息；ACL 2023 *Ties Matter* 已系统证明 tie 处理会改变 metric
meta-evaluation 并提出 tie-aware pairwise accuracy/calibration；ALT 2026 *Ranking Items from Discrete Ratings* 更直接把粗
ratings 表述为有序 bins、bin 内 ordering 不可辨识。因此“clipping/离散化损失排序”“ties 影响 rank metric”“细反馈
更有信息”都不能申理论、metric 或 RM 方法首创。

可守住的正贡献收紧为 MLE-specific 实证与 release contract：旧真实 search-tree cohort 在结果前双实现审计中，
official-five-decimal raw grade 为 157/158 non-tied，而我方 medal-threshold `y_norm` 仅 10/158 non-tied，形成
147 parents / 16 tasks 的 transform-induced alias；这不是官方 grader 缺陷，也不是整个 v11 critic label 污染。
future 双 truth 继续按同一 selected parents 并列报告 raw/normalized status，绝不以 raw 覆盖 normalized。当前定向检索
仍未发现直接同时覆盖 MLE-agent physical siblings、external-vs-self-report channel、structural→truth→overlap 漏斗和
temporal 双 truth closure 的工作；该交集可作 D&B 测量/完整性贡献，不作 first-ever 理论或算法主张。详情更新于：

- `phase1/实验记录/2026-08-23/RawGrade_MeasurementContract_直接相关工作边界.md`。

## 0FB. 2026-08-23 双 truth 闭合交付链已 exact-commit 验证；production truth 仍未打开

为避免 300-run identity cohort 闭合后漏跑 raw-grade 并行估计量，新增**仅手动触发**的 CPU runner，固定执行：
closed-identity guard → 原 `y_norm` producer×2/verifier×2 → official-five-decimal raw-grade producer×2/verifier×2 →
双状态并列回执。raw extension 必须逐字节复用 base `selected_parents.jsonl` 并独立重建 SHA lottery；任何 cohort、
protocol、producer/verifier、grader、selection、replica、grid、file-open 或凭据检查不一致均 fail closed。runner 不接入
连续 intake watchdog，不含 `sbatch/srun/API`，无论两门结果如何都写死 replay unauthorized。

控制 commit=`b108fb8d4d9c04d52ccae1d71d6e3d8d867820b6`。fresh no-smudge Linux 复验的聚焦/完整测试为
23/23、880/880（33 warnings）；用当前 33-run collecting receipt 做真实负控时 rc=1，明确打印
`CLOSED_COHORT_GUARD_FAIL_BEFORE_TRUTH_OPEN`，file trace 中 `label_vault` 打开数=0。commit 文件名/高置信内容
凭据扫描=0/0，worktree 前后 clean；不可变远端 `SHA256SUMS` 自身 SHA-256=
`5bf3b4dbd414e88d3696acb1a25ebb09924536a610ccbb1b236a05f2b0198b31`。

第一次 overlay 验收的科学测试已通过、collecting guard 也已拒绝，但外层审计复现“多份 strace 的 `grep -c` 返回
多行零”包装错误，故该目录保留为失败回执且不计正式证据；v2 改为合并命中后 `wc -l`，随后 overlay 与上述
exact-commit 复验均通过。两次都未打开 production truth、GPU/API/model fit/base-LLM update 均为 0。

这项结果只消除闭合时的执行歧义，不是正效果。当前动作仍是继续结果盲 intake；达到 300 runs 后先生成 closed
identity receipt，再人工调用该 runner。只有某个 estimand 自己的冻结支持门通过，才可另备 replay matrix、orientation、
power 与 GPU-hour 请求，并再次交用户批准；不得由另一门覆盖或反转。证据：

- `phase1/scripts/run_score_channel_future_dual_truth_20260823.sh`；
- `phase1/results/score_channel_future_dual_truth_runner_20260823_b108fb8/`；
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureDualTruthRunner_闭合交付链.md`。

## 0FA. 2026-08-23 等 pair 预算 breadth 正式裁决：有线索但未过门，NO_UNLOCK

结果前冻结的 exact commit `21186e036b41b35c087fd3cb02e99a88b241a4ed` formal 已完成。聚焦/完整测试为
8/8、874/874（33 warnings）；producer×2 与独立 source-refit verifier×2 均逐字节一致，最大数值差为 0。
held-out test/prospective/score-channel truth 均未打开，pair orientation 未参与选择，GPU/API/base-LLM update=
`0/0/0`，每个实现 9 个唯一 CPU fits。

固定每 task 50% pair 预算后，broad−concentrated 的 task-macro accuracy=`+0.0332204391514186`，三 seed
均为正、全部 LOTO 为正且点效应过 `+0.02` 门，但 task-bootstrap 95% CI=
`[-0.010859355050261277,0.07987928182598769]`，故 top-1 正门失败。log-loss 点差=
`-0.006769727559589795`，CI=`[-0.025437665186368662,0.010856041904946215]`，三 seed 中一 seed
反向且未达到 `-0.01`，proper-score 正门也失败。random 与 broad 的 log-loss 分别为
`0.6765865607703202/0.6773594555405009`，说明结果不支持 broad 是独特最优策略；最多是“过度集中可能有害”的
候选机制。正式状态为 `RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK`，不得追加同池 seeds、换 endpoint 或以
accuracy 单独 rescue。下一次合法检验只能是结果前冻结的新独立 corpus/future cohort 复现。

旧 exact launcher 同样有已解释的 live `run.log` completion-suffix packaging mismatch：40 项中其余 39 项全过，
外层审计确认 root 未被改写。修正后的 launcher 已在上一节共享四文件 overlay 中通过 16/16 与 874/874；不重跑
本次科学结果。证据：

- `phase1/results/critic_component_breadth_equal_budget_20260823_21186e0/`；
- `phase1/实验记录/2026-08-23/等Pair预算_Component广度_v1正式裁决.md`。

## 0EZ. 2026-08-23 component-clean 数据曲线正式裁决：同向但不足，NO_UNLOCK

exact scientific commit `eb1e1f5847584106b8daba30b75ee5459520c6c4` 的 fresh no-smudge formal 已完成。
聚焦/完整测试为 8/8、866/866（33 warnings）；producer×2 与独立 source-refit verifier×2 均逐字节一致，
source-refit 最大数值差为 0。访问声明为 held-out test/prospective/score-channel truth 均未打开，GPU/API/
base-LLM update=`0/0/0`，producer 与 verifier 各 10 个唯一 CPU fits。

25/50/75/100% 的 seed-mean task-macro log loss 分别为
`0.6816094159627339/0.6826620147808903/0.6755762240399482/0.6739468803314009`；full−mean-quarter=
`-0.007662535631333114`，task-bootstrap 95% CI=`[-0.038109760581376086,0.026746893869806762]`。
三个 seed 的 proper-score contrast 均为负且全部 LOTO 为负，但曲线不单调、CI 跨 0、`-0.01` 效应门未过。
accuracy 点差=`-0.008026070149419494`，CI=`[-0.07052702433385415,0.05604648899548043]`，top-1
所有正门失败。因此正式状态为 `RETROSPECTIVE_DEV_DATA_SCALING_NO_UNLOCK`：只能说固定 cheap critic 上有小的
同向 proper-score 信号，不能称稳定 data scaling、正突破或继续生产 runs 的充分因果依据，也不能以 accuracy rescue。

原 launcher 在生成 `SHA256SUMS` 后才把四行 completion suffix 写入 live `run.log`，故内部校验 38 项中仅
`run.log` 由空文件哈希变为最终 163 bytes；其余 37 项全过。独立 post-hash 审计确认精确 suffix、source 顺序、
root 未被审计改写，状态为 `ALL_SCIENTIFIC_AND_PRECOMPLETION_ARTIFACT_HASHES_PASS_RUNLOG_SUFFIX_EXPLAINED`。
该 packaging 缺陷如实保留；后续 launcher 排除 live `run.log`，待进程退出后由外层 receipt 单独哈希，不重跑科学
结果。修正后的四文件 overlay 已通过聚焦 16/16、完整 874/874（33 warnings）及 credential shape scan 0/0。
证据：

- `phase1/results/critic_component_data_learning_curve_20260823_eb1e1f5/`；
- `phase1/实验记录/2026-08-23/ComponentClean数据学习曲线_v1正式裁决.md`。

## 0EY. 2026-08-23 等 pair 预算的 component/run 广度实验已结果前冻结；尚未拟合

为区分“更多 pair”与“更多独立 runs/components”，在任何 arm dev metric 前完成 structure-only feasibility：固定
每 task 50% train pair 预算，`broad/concentrated/random × seeds 20260823/24/25` 每臂每 seed 均为 2,353
pairs；broad=127 components/429 runs，concentrated=53 components/223--224 runs，差 +74 components 和
+205/+206/+205 runs，25 个 dev tasks 中 24 个三 seed 均 structurally informative。feasibility SHA-256=
`773db70feb0872039af326fc19121254db26d106bb44e5081fc4f54b99a608b6`。

固定同一 char-TFIDF/LR、全部 25-task dev primary、task bootstrap+LOTO；proper-score 门为三 seed 全负、point
`≤-0.01`、CI high<0、LOTO 全负，top-1 门为三 seed 全正、point `≥+0.02`、CI low>0、LOTO 全正。
random 仅 descriptive，不能 rescue。producer×2+独立 source-refit verifier×2，每实现 9 次单线程 CPU fit；
GPU/API/base-LLM update=0/0/0。合同 SHA-256=
`1dc28d105922741d0c6a8263d9b2ebd2566d1a28de3dec1eb8f490116f7e6316`。即使正面也只允许 MLE
retrospective component-clean 数据采样结论，不称 scaling law、方法 novelty、frozen/future confirmation 或 search
utility。producer/verifier 的真实输入 structure-only 输出逐字节一致（共同 SHA-256=
`380a33b814527fd9bc3fdfc8f6f0bebba774076f7275850752e6e98e139f0c6b`），没有调用 fit/decision；隔离
no-smudge overlay 的聚焦/完整测试为 8/8、874/874（33 warnings），凭据扫描 0/0。证据：

- `phase1/critic_component_breadth_equal_budget_v1.json`；
- `phase1/实验记录/2026-08-23/等Pair预算_Component广度_v1结果前冻结.md`。

## 0EX. 2026-08-23 数据曲线首次 formal 启动在 fit 前失败；只修 launcher cwd

exact commit `18518fd54a0d9b2cde6fb951d0bf7c2fe4e1ae79` 的 fresh worktree 与 input SHA 均完成，但 launcher
没有切换到 repo cwd，随后相对路径 `py_compile` 找不到源码并 fail closed。失败发生在 focused/full tests 与任何
TF-IDF/LR fit 前；失败 root 原样保留，禁止续跑或复用。唯一允许修复为在 scientific action 前增加 `cd "$repo"`；
机器 contract SHA、数据、fractions、seeds、模型、estimands 与 gates 全不变，新 commit/新 root 从头运行。

## 0EW. 2026-08-23 component-clean 数据学习曲线已结果前冻结；尚未运行

为直接回答“学长继续增加独立 runs 是否可能提高 critic”，新增 outer-train-only CPU 诊断：固定复用
component-clean train/dev 与同池 char-TFIDF，在 pair-component 单位按三种事前 hash 顺序构造 25/50/75/100%
nested support curve。train=`4,689 pairs / 28 tasks / 127 components`，dev=`551 / 25 / 41`；test pair path、test
prediction、prospective vault 与 score-channel truth 均不进入 CLI。Cards 整包会解析，但只引用
id/code/run/task/config 投影，raw grade 不作特征或选择信号。

primary 是 dev task-macro binary log loss，secondary 是 task-macro accuracy；strong proper-score/top-1 门分别冻结
单调性、三 selection seeds 同方向、效应下限、task-bootstrap CI 与 LOTO。full-dev accuracy endpoint 已知，故无论结果
如何都只算 retrospective dev evidence，不得称 frozen confirmation、search utility、neural scaling 或方法 novelty。
机器协议 SHA-256=`a7c6bca3e430580c4a178d89694e90658a5496b8a1775a967221b7dc32d3c9da`；远端合成
正/负控与攻击测试 8/8，real effects 尚未读取，GPU/API/base-LLM update=`0/0/0`。证据：

- `phase1/critic_component_data_learning_curve_v1.json`；
- `phase1/实验记录/2026-08-23/ComponentClean数据学习曲线_v1结果前冻结.md`。

## 0EV. 2026-08-23 confidence--cost exact-commit 回归通过；仍没有真实效果

scientific commit `72129bb2a0ad98ae075bdea3f0ef2269c9ead345` 在 fresh no-smudge worktree 上通过 focused
32/32（4.52s）与完整 `phase1/tests` 858/858（86.31s，33 warnings）；changed-file credential filename/content
hits 0/0，worktree clean。机器契约 SHA-256 仍为
`00ba64a222ae793c3f5d196ee754f0af9e2f01986ad85ed78c11b6f570da665b`。第一次 full-suite 尝试因漏设数值库
线程上限而约 31 核过度并行，已中断且不计证据；正式重跑固定 `OMP/OpenBLAS/MKL/NumExpr=1`，persistent log
SHA-256=`773c11ecb3cf7a111a44ef195f15f43df5efad29e487ed6b5ade5130f341952f`。

docs-only correction `56a32caf2099b0b3f0b14975cdf0bcee958cf069` 已补回项目内部 selective 负前身及 ICLR 2026
proper-score claim boundary，不改机器协议或 scientific code。real future truth/GPU/API/model fit=`false/0/0/0`；
正式状态仍是 `ANALYZER_READY_EFFECT_ASSETS_PENDING`。证据：

- `phase1/results/critic_scaling_confidence_cost_extension_20260823_72129bb/`；
- `phase1/实验记录/2026-08-23/CriticConfidenceCost_防Scoop与二级扩展冻结.md`。

## 0EU. 2026-08-23 confidence--cost 的内部前身已补回；selective 不得冒充新突破

0ET 后的扩大历史搜索重新定位到 8 月 14 日 `selective_execution_v11_retrospective_discovery_v1`，它是当前
cost--regret 子分析的直接内部前身，而非泛 related work。旧 exact-two 1,520-parent committee 在 20% policy 上
task-macro=`0.5575913930507589`、CI=`[0.4780537058575693,0.6436459274377935]`，正式
`SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK`；相同 count 的 outcome-independent unanimous subset 反而更高，margin
enrichment 未支持。

因此 0ET 的 selective 部分降为：只在 primary clean scaling 本来就会生成的 future 8B one-shot scores 上，零额外
推理确认更强 critic 是否改变旧负边界；它不是新方法、新方向或当前正结果。研究者已看过旧完整 risk--coverage curve，
未来结果只能称新 cohort/new model confirmation，不能称相对全部历史 outcome blind。真正新增的测量轴是 dev-only
proper-score scaling。此次补记不改机器 hash、50% target、coverage grid、estimand 或 gates，避免因旧结果重调协议；
real effect 仍为零。

## 0ET. 2026-08-23 clean scaling 的 confidence--cost 二级扩展已结果前冻结；不构成新效果

一手防 scoop 审计确认 CAMEL 已覆盖低置信 preference 判断调用更贵 reflection，Calibrated Preference Learning 已把
RM calibration 定义为独立于 top-1 的质量维度，GenRM scaling 又已系统覆盖 Qwen3 `0.6B--14B`；ICLR 2026
*The Alignment Auditor* 也已比较 1B→8B reward-model accuracy/Brier/ECE/identifiability。因此不申
calibration/abstention/RM-scaling/proper-score-scaling 方法 novelty；只保留 MLE physical sibling 上 proper score 与
真实候选执行次数--regret 的 benchmark/deployment 证据。

新增二级机器契约 SHA-256=`00ba64a222ae793c3f5d196ee754f0af9e2f01986ad85ed78c11b6f570da665b`，绑定
0EP primary contract、同一 lock/test bundle/9-predictor matrix。dev-only 无截距 scalar temperature 在 test 前锁定；
primary 为 task-macro log loss/Brier，selective headline 固定 50% target：高置信 pair 执行一个 endpoint、低置信执行
两个，报告 realized saving、accepted error 与 task-normalized gap regret。secondary 永远不能 rescue primary FAIL，
结果后不得换 coverage。

producer/verifier 不互相 import；7/7 扩展合成/攻击测试、32/32 与 primary 联合测试通过，其中同步更新派生 manifest 的
summary 篡改仍被 source reconstruction 拒绝。当前 real future truth/GPU/API/model fit=`false/0/0/0`，状态仅为
`ANALYZER_READY_EFFECT_ASSETS_PENDING`；fresh exact-commit 全回归与凭据扫描待 commit 后写 receipt。证据：

- `phase1/critic_scaling_confidence_cost_extension_v1.json`；
- `phase1/contracts/CRITIC_SCALING_CONFIDENCE_COST_EXTENSION_V1.md`；
- `phase1/实验记录/2026-08-23/CriticConfidenceCost_防Scoop与二级扩展冻结.md`。

## 0ES. 2026-08-23 source-binding 不再由 materializer 自证；独立 verifier 已就绪

新增 `verify_critic_scaling_confirmation_materialization.py`，不 import producer，独立重建 pairs/Cards→truth 的
component/pair identity、oriented utility 和 support，并从 upstream one-shot output/ledger + checkpoint manifest 逐 pair
重建 normalized predictions。focused 18/18；其中对抗测试在篡改 prediction 后同步更新 derived hash，独立 verifier 仍能
从 source 发现并拒绝。与 scaling analyzer/endpoint tests 联合为 28/28。集群 fresh no-smudge exact code commit
`2a49d4cf...` 独立打印 full 851/851（33 warnings）、secret scan 0/0、worktree clean，没有复用 0ER 的 848 数字。
当前仍只完成合成验证，real future truth/GPU/API/model fit=`false/0/0/0`。证据：

- `phase1/verify_critic_scaling_confirmation_materialization.py`；
- `phase1/results/critic_scaling_materialization_verifier_20260823_2a49d4c/`；
- `phase1/实验记录/2026-08-23/CleanScalingMaterializer_独立SourceBinding复核.md`。

## 0ER. 2026-08-23 clean scaling 的盲态交付链已补齐；真实效果仍为零访问

新增 `critic_scaling_confirmation_materializer.py`，把未来 dedicated pairs/Cards、0004 endpoint receipts 和已规范化
baseline 严格接到 0EP 的 frozen analyzer。truth 阶段以 raw sibling/run/lineage/单 budget 和任务 grade direction 做
fail-closed，按 parent graph 的 maximal connected components 零丢弃生成 canonical component/pair IDs；model 阶段同时
绑定 truth/lock、pairs/Cards、checkpoint artifact manifest、one-shot output/ledger 以及 test 前锁定的两条路径身份；bundle
阶段拒绝 symlink/path escape、矩阵缺失和任一 hash/rows/ledger 不一致。

纯合成 adversarial tests 15/15，既有 scaling+endpoint 联合测试 10/10，合成最终 bundle 可被 frozen analyzer 接受；
集群 fresh no-smudge exact commit `81a09d53...` focused 25/25、full phase1 848/848（33 warnings），secret scan
0/0、worktree clean；本机缺 `scipy/sklearn` 的 collection 失败未冒充通过。正式状态为
`MATERIALIZER_READY_SYNTHETIC_ONLY_REAL_TRUTH_FORBIDDEN`：real future truth/GPU/API/model fit=`false/0/0/0`，因此这只是
把未来确认做成一次性、可审计交付，不是新的 scaling 效果。证据：

- `phase1/contracts/CRITIC_SCALING_CONFIRMATION_MATERIALIZATION_V1.md`；
- `phase1/results/critic_scaling_materializer_20260823_81a09d5/`；
- `phase1/实验记录/2026-08-23/CleanScalingMaterializer_盲态交付桥与一次性加固.md`。

## 0EQ. 2026-08-23 clean scaling 的 endpoint-score 交付缺口已闭合；效果资产仍待未来

0EP 契约要求逐 pair better/worse scalar scores，原 one-shot evaluator 只保存 margin，无法认证共享 endpoint
一致性或 component utility。新增 upstream patch `0004-Emit-endpoint-score-receipts.patch`，SHA-256=
`237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`；它只保留同一次前向已计算的两个
endpoint scores，由二者计算 margin，并在写盘前检查 finite/count/difference，不改模型、输入、推理或 accuracy。

在 senior `ac008af8...` fresh no-smudge worktree 上，0001/2/3/4 顺序 apply-check/apply 全过；新文件 5/5，
既定 8 个 confirmation 文件 36/36（46.79s），compile/shell/diff 检查通过。整个 senior test 目录的扩大尝试在
collection 阶段因环境缺 `dojo`/`litellm` 停止，0 tests failed，故不记作完整通过。当前正式状态仍为
`ENDPOINT_RECEIPT_OVERLAY_READY_EFFECT_ASSETS_PENDING`：没有 future cohort、dev-only checkpoint matrix、逐 pair
bundle/ledger 时不能生成效果或提交 GPU。证据：

- `phase1/upstream_patches/0004-Emit-endpoint-score-receipts.patch`；
- `phase1/results/senior_endpoint_score_overlay_20260823_ac008af/`；
- `phase1/实验记录/2026-08-23/SeniorEndpointScoreOverlay_交付与边界.md`。

## 0EP. 2026-08-23 clean critic scaling 独立确认接口冻结；checkpoint 方向版本边界纠正

历史 `greater_is_better=false` bug 不再是学长最新代码的活跃阻断：Git history 显示 `d44f4b0`（0820）已把
`eval_pair_accuracy` 的方向修为 `true`，`dojo-reproduce@ac008af8...` 仍正确。0813/0814 旧报告只描述当时 commit；
0P/3.11 等更早“最新仍错误”的措辞已由本节覆盖。当前真实阻断是旧 outer test 被每 10 steps 当作 eval、缺
dev-only one-shot test 链、历史训练完整性不一，以及没有逐 pair predictions/checkpoint manifests。

为把 0BW/0820 的探索性 value scaling 变成可确认资产，已冻结 `critic-scaling-confirmation-contract-v1`：Qwen3-Base
`{0.6,1.7,4,8}B × seeds {6,7}`、同池 train-only char-TFIDF、primary canonical sibling、10,000 次 task
bootstrap。容量 scaling、8B 超基线、component utility conversion 三层分开；支持门为至少 20 tasks/300
components、最大任务 pair share≤0.20。每个 seed 的 8B−0.6B 也必须为正，禁止仅靠两 seed 平均掩盖不稳定。

producer 与不 import producer 的 verifier 已实现 test 前 lock、完整训练/dev-only checkpoint 选择、exact matrix、
一次性 ledger、endpoint-score 一致、component 连通、task/run CI、LOTO 与逐 component gain 的 fail-closed 检查；
冻结契约 SHA-256=`579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568`。本地 7 个
正控/负控/攻击/哈希种子/独立复核测试通过。当前仍是 `CONTRACT_READY_ASSETS_PENDING`，GPU/API/model fit/future
truth=0/0/0/false；没有新 checkpoint/逐 pair bundle 前不得生成效果结论或提交训练。scientific commit
`186ab1800973972b8066c7a706bd06f92c8d124a` 的 fresh no-smudge worktree 已通过聚焦 7/7、完整
830/830（33 warnings）、凭据扫描 0/0 且 clean；测试前的 remote alias/proxy/env/LFS 阻断与测试后的零命中
`grep` pipefail 均在 receipt 中独立保留，未伪装成科学失败或静默删除。

证据：

- `phase1/contracts/CRITIC_SCALING_CONFIRMATION_V1.md`；
- `phase1/critic_scaling_confirmation_contract_v1.json`；
- `phase1/critic_scaling_confirmation_analysis.py`；
- `phase1/verify_critic_scaling_confirmation_analysis.py`；
- `phase1/results/critic_scaling_confirmation_contract_20260823_186ab18/`；
- `phase1/实验记录/2026-08-23/CleanCriticScaling_独立确认契约与checkpoint版本纠正.md`。

## 0EO. 2026-08-23 comparison-component cost--utility 正式复核完成；强正主张关闭

确定性修复 commit `e3cffbb6ec041e9de73efe6e112f1bd9859f6e69` 的 fresh exact-commit 聚焦/完整测试为
14/14、823/823（33 warnings），凭据扫描 0/0；formal producer A/B 与独立 verifier A/B 均逐字节一致。verifier
重建 1,482 pairs、806 comparison components、156 task/subset rows；summary/receipt SHA-256 分别为
`f740fb03bb5743b5cba381940ec64407c789aef15dbfe8c71ece4c16967b6e91` /
`517e08fd2473f3db74ccd84b41d3ccc62a3fe4cb40648e14486e9c1c4eeb7005`。GPU/API/model fit/future truth open=
0/0/0/false。

冻结 test 支持=931 pairs、550 parent groups、559 components、28 tasks。task-macro unweighted accuracy=
`0.5757982662586206`、CI=`[0.5079348813388992,0.6404919021264853]`；raw-gap-weighted accuracy=
`0.5834551030090183`、CI=`[0.4949686656930697,0.6693520122240301]`；加权减普通=
`+0.007656836750397718`、CI=`[-0.05766129409784135,0.0672026866373468]`。component gain capture=
`0.07315959014998666`、CI=`[-0.21575761078478997,0.31604557521269605]`，top-1=
`0.5150856085082018`、CI=`[0.433768152581631,0.5925650841558566]`。支持两门通过，两个 primary effect 门均失败，
正式状态为 `VALID_NO_STRONG_COMPONENT_COST_UTILITY_POSITIVE`。

Improve secondary 的 gap-weighted CI 下界虽略高于 0.5，但 component gain 跨 0；Draft 与 merged primary 不支持，
不得以 subgroup 替换 primary。query p95 48.958ms vs execution p50 199.627s 的成本优势仍成立，但“弱 accuracy
隐藏强高价值决策能力”在该冻结 baseline/test 上关闭；同池不得改权重、筛 task/component 或调阈值。该结果保留为
D&B 的 accuracy≠utility 机制证据，正资源回到新 physical runs 的前瞻 score-channel 与 clean scaling/calibration。
证据：

- `phase1/results/tfidf_retrospective_component_utility_20260823_e3cffbb/`；
- `phase1/实验记录/2026-08-23/TFIDF_ComponentCostUtility_正式裁决.md`。

## 0EN. 2026-08-23 V2 首次正式运行复现门失败（随后由 0EO 修复并重跑）

V2 commit `db7069db570523ac740b920202e37abb6493bc02` 已通过 13/13 聚焦与 822/822 全测试。初始 launcher
因用文件路径启动导致 `phase1` import 失败，0.22s 时退出、Cards 未开；改成 `python -m` 的新目录后两个 producer
均完成，但产物不逐字节一致，独立 verifier 以 `V2 component rows differ` 拒绝。A/B summary 有 82 个末位数值差异，
max abs=`3.552713678800501e-15`，40 个 component rows 与 37 个 task CSV rows 不同。虽然两个未认证 producer
打印相同分类状态，该状态一律作废，不能作为科学结果。

根因是 V1 通用 solver 从无序 endpoint `set` 构造 utility mean；不同 Python hash seed 改变浮点累加顺序。修复仅在
producer/verifier 各自实现中显式排序 endpoint，不改 protocol、input、component partition、estimand、bootstrap、
threshold 或 gate；新增两个独立 `PYTHONHASHSEED` 子进程逐字节一致回归，聚焦测试现为 14/14。再次正式运行必须
先形成新 commit/push 并在 fresh exact commit 全测。证据：

- `phase1/results/tfidf_retrospective_component_v2_invalid_attempt_20260823/`；
- `phase1/实验记录/2026-08-23/TFIDF_ComponentCostUtility_V1失败与V2冻结.md`。

## 0EM. 2026-08-23 cost--utility V1 结构性 INVALID；V2 零丢弃 component 协议已在 aggregate 前冻结

0EL 的 exact commit `cd8254567d5234fef215acb40acb0b569e44516e` 已先通过 fresh-worktree 聚焦/全套
`9/9`、`818/818`（33 warnings）及凭据扫描 0/0。正式 producer 五个输入 SHA 全部正确，但在 6.71s、max RSS
1,382,116 KiB 时因 `parent margin graph is disconnected` fail-closed；没有创建 producer artifact 目录，没有输出
raw-gap/utility/gate aggregate，第二跑和 verifier 未启动。历史 released Cards bytes 已打开，故不能再称 outcome bytes
unread；但研究者在 V2 冻结前没有看到任何 utility aggregate。future/prospective truth 仍未开，GPU/API/model fit=0。

结构-only 诊断固定为 1,482 pairs、796 parent groups，其中 786 连通、10 个各有两个分量；test 为 550 groups、
9 个断连。语义合并不改变结构，mixed-semantics parent=0。V1 的 no-partial-salvage 因而触发，永久记为
`V1_INVALID_STRUCTURAL_GRAPH_ASSUMPTION`，禁止只报 786 个 complete parents。

V2 唯一修复是零丢弃地把每个 parent graph 拆为最大连通 **logged comparison component**：全部 pair 恰好分配一次，
共 806 components，test=559。它不填补断连组件间 score offset，也不冒充完整 physical parent choice set。两个
primary 保持 task 内 raw-gap-weighted pair accuracy 与 component oracle-gain capture；正门固定为 test≥20 tasks、
≥300 components、两者 task-bootstrap 95% CI 下界严格高于 0.5/0，并通过全部结构/方向/hash/cost 门。当前 V2
双实现与 13 个合成/攻击测试已完成；正式 aggregate 必须先 commit/push，再在 fresh exact commit 全测。证据：

- `phase1/results/tfidf_retrospective_utility_v1_invalid_20260823/`；
- `phase1/tfidf_retrospective_component_utility_protocol_v2.json`；
- `phase1/实验记录/2026-08-23/TFIDF_ComponentCostUtility_V1失败与V2冻结.md`。

## 0EL. 2026-08-23 TF-IDF retrospective cost--utility 结果前冻结（随后由 0EM 裁决 V1 INVALID）

为区分“57.14% 普通 pair accuracy”与真实搜索价值，固定复用 component-clean char-TFIDF 的 931-row test
per-pair margin、released Cards raw grade 和已独立认证的 init/query cost，不重训、不换 pool、不筛 task。两个
primary estimand 是 task 内 raw-gap-weighted pair accuracy（随机基线 0.5）与 task 内 parent oracle-gain capture
（uniform-random candidate 基线 0），均在 task 内先聚合再 task-macro，绝不跨 task 混合 raw-grade 单位。

结果前主门固定为 test≥20 tasks、≥300 complete parents、两个 task-bootstrap 95% CI 下界分别严格高于 0.5/0，
以及全部 identity/orientation/parent-graph/cost 门通过。test 普通 accuracy 已被看过，所以即使 PASS 也只能称
`retrospective_accuracy_touched_component_clean_test` 机制证据，不能称 frozen confirmation 或 live-search causal
speedup；失败后禁止换 gap transform、task/pair pool、阈值或聚类单位。当前只完成协议与双实现，真实 raw-gap/
parent utility/gate 仍未读取，future/prospective truth 保持封存，GPU/API/model fit=0/0/0。9 个合成/攻击测试已在
本地通过；正式运行必须先 commit/push 冻结并在 fresh exact commit 全测通过。直接协议：

- `phase1/tfidf_retrospective_utility_protocol_v1.json`；
- `phase1/实验记录/2026-08-23/TFIDF_RetrospectiveCostUtility_结果前冻结.md`。

## 0EK. 2026-08-23 source×config provenance 组合层完成；真实 manifest 与交互支持仍待未来数据

0EJ 的 metadata 阻断已收窄为机器可执行接口：新增 future-only
`senior-experiment-config-manifest-v1`，复用既有 source manifest 的 archive/batch/commit 身份绑定，并逐 run 追加
公开 `client`、结果前 `generator_release`、`hardware`、`time_limit`、`execution_timeout` 与既有
`experiment_stratum_sha256`。validator 独立重算 source mapping、强制已验证 source receipt 和两个 manifest
精确覆盖同一 frozen-run 集，不读取 archive payload/Cards/pairs/outcome。`generator_release=unknown` 允许保存诚实
provenance，但强制 `interaction_metadata_complete=false`，不得用于交互结论。

远端 exact base `04b1be9fe88776be4531ce6c82130d4927b4cb45` 上，source+config 聚焦攻击测试=
`21 passed in 0.18s`，完整 `phase1/tests`=`809 passed, 33 warnings in 51.65s`，文件名/内容凭据扫描=`0/0`。
首次 full suite 因未固定数值线程而在登录节点展开约 30 线程，约 17% 时主动中止、此前 0 failure；失败日志保留且
不算通过。固定 OMP/OpenBLAS/MKL/NumExpr=1 后从头重跑得到上述 809/809。GPU/API/model fit/base-LLM update/
future-truth open=`0/0/0/0/false`。

当前只有 contract，没有真实 producer config manifest，故正式状态为
`CONTRACT_IMPLEMENTED_REAL_MANIFEST_PENDING`；不能写成 capability×generator 已可识别，更不能据此开 GPU。当前
204 archives 没有 0822 新 drop，33/300 score-channel cohort、truth vault 与 intake monitor 均保持不变，禁止事后
回填该 sidecar。证据：

- `phase1/contracts/SENIOR_EXPERIMENT_CONFIG_MANIFEST_V1.md`；
- `phase1/results/senior_experiment_config_contract_20260823/`；
- `phase1/实验记录/2026-08-23/SeniorConfigProvenanceOverlay_交付.md`。

## 0EJ. 2026-08-23 pairwise/execution-free/trained code critic 宽首创关闭；MLE clean frontier 成为最窄正方向

新核查的 [Reward-Free Evolving Agents via Pairwise Validator](https://arxiv.org/abs/2607.14408) 已把 frozen LLM
pairwise validator 接入 GEPA、ADRS 与 ShinkaEvolve，在代码 substrate 上同时覆盖 accept/reject gate 与 parent
selection，并报告 Qwen3-8B 代码演化结果。因此“首次用 pairwise critic/judge 引导代码搜索、gate 或 parent selection”
全部关闭；0EA global→local 五臂继续只作 D&B 机制消融，不能升级为训练方法 novelty。

不能把竞品总括成“仍须执行全部候选”：其 prompt 路径消费 parent/child train-minibatch outputs，prompt-side 普通
validator/Elo 的分析调用量约为 full-reward baseline 的 1.7×/2.4×；但代码纯 `Direct` arm 不使用 reward，已经覆盖
source-code pairwise judge。因此可防守缺口只能收紧为：以历史 pristine execution grade 离线监督、在 query time 不读
stdout/submission/runtime/exit status 的 **learned critic**，相对同输入 training-free validator 是否形成随容量改善的
calibration/cost–utility frontier，并迁移到时间更晚/不同 generator 候选。区别是 trained surrogate vs frozen judge，
不是“首次 execution-free 比较”。

进一步一手核查又确认 [Steer, Don't Solve](https://arxiv.org/abs/2606.21811) 已训练 8B critic 给 frozen code agent
intra-trajectory feedback，报告跨 unseen agents 迁移、trained-vs-untrained 正结果与 30--92× teacher-cost reduction；
[RewardCode](https://openreview.net/forum?id=zpsYG8fYc8) 已训练 execution-validated general code RM；
[More Convincing, Not More Correct](https://arxiv.org/abs/2607.05904) 也在代码 best-of-N 复现 reference-free judge 的
correctness 偏离。因此 trained critic、跨 agent transfer、code-RM scaling、cost Pareto 与 judge 不可靠性的宽首创均
关闭。0EJ 只保留 MLE-agent physical sibling 上的 clean scaling/calibration/temporal transfer/noise/cost frontier，
作为 D&B benchmark 机制证据，不作 critic 方法论文。

对 current 11 份 accepted `source_provenance.json` 的结果盲 schema-only 双跑确认：33 records、0 parse errors、单一
schema，但 client/model/generator/hardware/time-limit/execution-timeout 六类字段全部为 0/11；output SHA-256=
`caa59456c864f07770e73fcb4a7fe5565c93bb7519b44b2faa873aafa1905589`。故 33/300 cohort 不能事后承担 capability×generator
交互分析，仍只服务 score-channel；交互矩阵必须另冻 credential-safe config-provenance sidecar，不能回填当前协议。

候选确认顺序固定为 S0 provenance/identity/cost 闭合（0 GPU）→S1 一次性 clean capability curve→S2 结果前锁定的
tabular search utility→S3 单 pivot live A/B。frozen LLM judge 若读取 outputs，只能作 post-execution comparator；与
critic 同列的 execution-free arm 必须使用相同执行前输入。旧 2,087-row test-touched checkpoint 继续禁用；当前
33/300 future cohort、truth 封存、门槛与 intake monitor 均不变。exact 模型×seed 矩阵、G0 与 GPU·时未闭合，故
GPU/API/model fit 仍为 0，不授权提交。详情：

- `phase1/实验记录/2026-08-23/ExecutionFreeCritic_直接竞品与正方向重定位.md`。
- `phase1/results/future_provenance_schema_only_20260823/`。

## 0EI. 2026-08-23 33-run receipt 已 push 并通过 exact-commit 验证；长期 intake 仍结果盲

聚合收据、raw-grade 直接相关工作边界与方向更新已以 commit
`c2c0ed5ac49bcf467900332c89e7573664b1f6d6` push。fresh detached no-smudge worktree 对 committed receipts
先逐项验 SHA，再运行聚焦/完整测试=`33/33`、`798/798`（33 warnings）；commit 文件名/高置信内容凭据扫描=`0/0`，
future truth、raw archive payload、code view、score、replay outcome 均未打开，GPU/API/model fit/base-LLM update=
`0/0/0/0`。不可变验证 manifest SHA-256=
`5479593dfdd6a539a2547d139c054241f63f8a759dfa47e06e50385b0a19e318`；证据：

- `phase1/results/score_channel_future_progress_20260823/`。

连续 intake child 每 5 分钟轮询、单周期约 12 小时；另挂 fail-closed watchdog，只有 child 明确打印 normal
`COMPLETE` 才可重启，未知结构、显式 FAIL_CLOSED、PID 漂移或异常死亡一律停止。watchdog 最多 20 次正常重启（约
10 天），不自动运行 truth gate 或 replay。activation receipt manifest SHA-256=
`4ffb5a2e4e242a776c0c2d44707d9c717e875698bc16dfa2cf379c9877535057`。首版 receipt 因 grep 返回逐文件计数而按整数门
失败，失败目录保留并标记 `FAILED_RC=1`；v2 改成纯数字汇总后通过，未读科学数据。当前仍是 33/300；没有新 ready
archive 时不得重复 formal receipt。

Raw-grade 主张同时收紧：v11 predictor builder 原本直接使用 `label.graded`，所以 147-parent alias 不是整个 predictor
benchmark 的标签污染，只属于 score-channel 自定义 `normalize_graded` truth-support 链。允许主张 score-channel
可辨识性修复与双 truth release contract；禁止写成“修复全部 critic 训练标签”。

## 0EH. 2026-08-23 0821 初始 12 archive 已全 settle；future cohort 为 33/300，truth 继续封存

结果盲连续 intake 已处理初始 12 archives：11 accepted、Plant 精确结构拒收 1，无 partial salvage。最新 commit
`78c44ac841b22b8b0f0cf1eb32214a7a79187de5` 的 formal identity producer×2/verifier×2 逐字节一致：selected
physical runs/tasks/accepted archives=`33/11/11`，remaining=`267`，status=`FUTURE_COHORT_COLLECTING`；此前 8-run
prefix exact survived，settled prefix=12、pending head=null。聚焦/完整测试=11/11、798/798（33 warnings），forbidden
open 与两类凭据扫描均为 0。summary/verification/remote-manifest SHA-256 分别为
`780126c257ceae38a830c9d8215fbf7a7ce6776987ba683a967d774d13488600` /
`1e9630e043b05f1c673885205d8060b883443eaa4276699cae7508c2811b3c77` /
`92632f3599f920a6154ce5bf47fa6fee7414ffb7fb0502a852148727986760ce`。

label vault/raw archive/code/score/replay outcome 仍未开，双 truth gate 不运行；连续 monitor 继续等待新 archive。按学长
约 60 physical runs/day 的生产计划，单纯算术下界约 4.45 个生产日，但实际 accepted rate、上传节奏和结构拒收会延长，
不得承诺日历完成时间。证据：

- `phase1/results/score_channel_future_identifiability_freeze_20260823/formal_identity_cohort_78c44ac_first_0821/`；
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureIdentifiabilityCohort_结果前冻结.md`。

## 0EG. 2026-08-23 future raw-grade support extension 已结果前冻结；仍未打开 future truth

0EF 的 material alias gate 通过后，已在 current future identity cohort 闭合和 label-vault open 前冻结并行 extension。
它必须逐字节复用原 `score-channel-future-truth-support-v1` selected parents，同时独立重建 cohort/clique/SHA lottery；
只在完全相同 sibling sets 上聚合 official five-decimal `graded` support。原 `y_norm` status 原样保留，不得覆盖或反转。

raw support 沿用原四门：non-tied parents≥80、tasks≥8、dominant task share≤0.25、selected physical runs≥60；raw
metric 跨 task 不同量纲，禁止跨任务 gap bins。PASS 只允许准备另名 replay matrix/orientation/power/GPU-hour request，
仍需用户批准且不能自动 launch；KILL 则停止 raw-grade replay 请求。extension 协议 SHA-256=
`4b13814ad53758d21e7f7b531ede5b9a63fd244c7e305833d0513eb77195c8c0`。producer 与不导入任一 producer 的 verifier
均已实现；7 个聚焦/攻击测试覆盖 base-KILL/raw-PASS、字节确定性、off-grid、candidate reuse、结果篡改、实现独立与
协议 bytes。冻结 commit `78c44ac841b22b8b0f0cf1eb32214a7a79187de5` 已 push；fresh detached no-smudge
worktree 上联合聚焦 22/22、完整 `phase1/tests` 798/798（33 warnings），commit 文件名/内容凭据扫描 0/0，future
truth open=false。不可变验证 manifest SHA-256=
`6e8666d5f3dc61b27b526590a692b02e007151bebbb0500adb3ebf9bcfec75f3`。证据：

- `phase1/score_channel_future_raw_grade_support_protocol_v1.json`；
- `phase1/score_channel_future_raw_grade_support.py`；
- `phase1/verify_score_channel_future_raw_grade_support.py`；
- `phase1/results/score_channel_future_raw_grade_freeze_20260823/`；
- `phase1/实验记录/2026-08-23/RawGrade_MeasurementContract_直接相关工作边界.md`；
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureRawGradeSupport_结果前冻结.md`。

直接相关工作边界：NAS predictor suite 已以 raw validation performance 的 rank correlation 与下游 search 为标准，
BRP-NAS 也早有 binary relation predictor；MLE-bench 官方则分别提供 raw score、thresholds 与 medal flags，并未定义
我方连续 clipping。因此不得主张 pairwise/ranking 或 clipping 数学首创，也不得把 147-parent alias 归咎于官方 grader。
可守住的是 MLE search-tree 上的实证 transform audit、可辨识漏斗与前瞻双 truth contract。

## 0EF. 2026-08-23 `y_norm` 大规模裁平 truth ordering；future raw-grade 并行支持估计量必须结果前追加

结果前 commit `5e3ebcd571676cd55188bf22ad7265b34b7dc1b8` 之后，旧 158-parent cohort 的正式双实现审计确认：
官方五位小数 `graded` 为 157 non-tied / 1 tied，而 `y_norm` 为 10 non-tied / 148 tied；147 个 parent、16 个任务
属于“raw 可区分但 `y_norm` 并列”，反向不可能情形为 0。148 个 normalized ties 中 128 个全为 0、20 个全为 1、
0 个 interior；320 个 grade 全部落在官方五位小数网格。冻结的 material gate（alias parents≥16 且 tasks≥4）两项
均通过，独立 verifier 状态为 `VERIFIED_TRUTH_ALIASING_AUDIT`。

三个旧 common-channel parents 在 raw truth 下全部可区分，但 external/stdout 的描述性 top-1 credit 都为 1.0，
delta=0；样本只有 3，不能写通道效果结论。旧 primary/KILL 不反转，unrounded score 仍不可恢复。该结果只授权在
current future vault 打开前冻结一个**另名、并行**的 official raw-grade truth-support estimand；原 `y_norm` gate 必须
原样计算和报告，raw extension 不自动授权 replay/GPU/effect claim。正式 analysis/verification SHA-256 分别为
`38788c89ca8231428482d9bea1a43e5a641eda7a6efa26dec89eb6499e594ba5` /
`4b56b9e2e3cb9c52f390dd92b3877f818ef7b2edecc27cde919c06a09fb22789`；future truth forbidden-open、文件名与内容
凭据扫描均为 0。证据：

- `phase1/results/score_channel_truth_aliasing_audit_20260823/`；
- `phase1/实验记录/2026-08-23/ScoreChannel_TruthAliasing_结果前冻结.md`。

## 0EE. 2026-08-23 raw-grade alias 审计的结果前冻结（由 0EF 更新）

固定 MLE-bench commit `507f92e1138bb6e40dac5c6ee7a6758e6424bf97` 的 `Grader.__call__` 会先执行
`round(score, 5)`；我方 `normalize_graded` 又按 medal thresholds 变换并裁到 `[0,1]`。因此旧 cohort 的 148/158
`y_norm`-tied parents 可能混合官方五位小数同分与我方 clipping alias。冻结前只知道旧 aggregate，不知道 raw
`graded` informative/alias/common-credit 结果；当前 future truth vault 未开。

新 post-hoc 协议在完全相同 158 parents / 320 candidates 上固定比较 raw `graded` 与 `y_norm` ordering support，
并把 normalized ties 分为 all-zero/all-one/interior。material gate 固定为 alias parents≥16 且 tasks≥4；通过只允许
在 future vault 打开前另名追加 raw-grade truth-support estimand，同时保留原 `y_norm` gate，不授权 replay 或 effect
主张。旧 machine verdict 永不反转，unrounded score 不声称可恢复。协议 SHA-256=
`b917182570fd3484b87457b9185d5220eef3bc5fdda5030e847897a3c7f052cd`；producer/verifier 双实现与 5 个合成测试已完成，
结果前 commit+push 与 fresh exact-commit 测试已完成；正式结果见 0EF。冻结证据：

- `phase1/score_channel_truth_aliasing_protocol_v1.json`；
- `phase1/score_channel_truth_aliasing.py`；
- `phase1/verify_score_channel_truth_aliasing.py`；
- `phase1/实验记录/2026-08-23/ScoreChannel_TruthAliasing_结果前冻结.md`。

## 0ED. 2026-08-23 0821 Plant 精确结构拒收已冻结；前两笔 cohort transaction 不变

连续 intake 已先提交 `ranzcr` 与 `tgs` 共 8 个 accepted physical runs；随后 0821 Plant archive 在 task-identity
门 fail closed，未提交新 transaction、未读 outcome。精确绑定 size=`119572767`、mtime_ns=
`1787408006000000000`、archive SHA-256=`5213f40cb0246d927b5e825943232a8f6e2bf0eba7c7d7005a13740ba0a67b20`。
固定 auditor 双跑逐字节一致：4/4 checkpoint journals 的 competition identity cardinality 都为 0；raw journal
先做 credential-shape scan，env/live-event、task 值、代码、stdout、grade、metric、prediction 与 outcome 均未读
或未输出。只对这一个精确 archive bytes 整包拒收，不从文件名推断 task、不部分 salvage。

audit/builder 聚焦测试分别 1/1、5/5，registry 双构建逐字节一致；diagnostic/registry SHA-256 分别为
`8277d6dfe0651d88179735d8e2088d2de1cf329e9c2720272804833b65d226fc` /
`7c16889eb5ec57b1ca391b4171a997ad0fcd35d076ad6b34fddb53b556e35e6e`。下一步只允许在 clean control commit
同时绑定全部历史 registry 与本 registry 后恢复剩余 0821 CPU intake；scientific commit、稳定性门与 frozen
truth/cohort 协议不变，GPU/API/model fit 仍为 0。证据：

- `phase1/results/prospective_structural_rejection_20260823/`；
- `phase1/实验记录/2026-08-23/Prospective0821_Plant结构拒收与摄取恢复.md`。

## 0EC. 2026-08-23 evaluator-channel 宽泛首创已关闭；artifact-vs-self-report 前瞻 estimand 保留

最新强相关检索发现 `AuditRepairBench`（arXiv:2605.04624v1）已经在 agent repair 中明确研究 evaluator-channel
ranking instability，并以 paired execution、固定 final evaluator 和 selector-input channel blocking 为核心。因此
“首个 evaluator-channel/coupling benchmark”及“首个 paired channel intervention”均不得再主张。该稿已于
2026-07-24 因作者确认实验设计/评估重大有效性问题而撤回；其数值不能当可靠事实，但概念先例与风险不能忽略。

它没有覆盖当前精确 estimand：同一 MLE candidate、同一短执行下，pristine evaluator 读取 `submission.csv` 的外部
分数与 agent stdout self-report 的 paired discriminative support，也没有 physical-run/tree、coverage、cost/noise 和
append-only temporal contract。同期 AutoResearchEval（arXiv:2608.14905v2）强调 process annotation 与 artifact
visibility，但同样不做这组固定预算通道对照。因此 0DY/0DZ 主线不变，正面主张收缩为“MLE execution feedback
并非同质 scalar；artifact-grounded channel 的 execution cliff 可被前瞻审计，并在只改变 selector-visible channel、
保持 final evaluator 不变的 replay 中检验”。详情：

- `phase1/实验记录/2026-08-23/ScoreChannel_直接竞品与撤稿边界.md`。

## 0EB. 2026-08-23 Rehearse 关闭执行前 memory/controller 首创；score-channel 前瞻主线不变

新核查的 Rehearse（arXiv:2607.27687v1，2026-07-30）直接覆盖 same-baseline autoresearch proposal 的执行前
pairwise 判断、候选相关 outcome memory 和固定 training-run budget 下的端到端收益。其 296 个主 pair 是一边改善、
另一边 crash/timeout/invalid/non-improvement；无记忆主 pair selective accuracy=79.5%，深层从 82.8% 降至
56.9%，focused memory 恢复到 83.5%；三 loops、五 seed、合计 4,000 training runs 得到正 endpoint。它又明确以
FOREAGENT 为 completed-solution 最近先例。因此 history retrieval、Predict-then-Execute 与 `confidence cliff`
术语均不得再申方法 novelty；0EA global→local 仍只作 D&B mechanism ablation。

这不覆盖 0DZ/0DO 的当前主线：Rehearse 没有研究同一短时执行后的 pristine submission artifact 与 stdout 自报通道，
也没有我方 physical sibling/run-clean/noise/cost/append-only temporal contract。v11 的 16,012-card schema-only 审计
又确认 release 中没有 authentic `analysis/plan/hypothesis/implementation` 字段；高置信 credential hits=0、
parse errors=0、cards SHA-256=`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`。
因此不为追随 Rehearse 事后生成 rationale 或启动 API。若未来做 failure→worked→viable-sibling 难度阶梯，必须先有
结果前保存的真实 rationale 并另立同信息/同模型预注册。详情：

- `phase1/实验记录/2026-08-23/Rehearse_直接竞品与主线边界.md`。

## 0EA. 2026-08-23 global→local 正假设收紧：部分 scaling 可迁移，直接 local 训练才丢失；五臂语义已冻结、effect 阻断

对学长 0820 已公开表做 post-hoc shape audit：value seed 6/7 的 0.6B→14B Final 分别 +7.69/+6.55 pp；
seed-7 value checkpoint→filtered local 同样无严格反转、端点 +4.38 pp。直接 local-only 的 0.6B→8B Best/Final
则为 -0.73/-1.04 pp，秩相关均为 0。故当前最积极且准确的候选机制是“global supervision 的 capacity signal
可部分 zero-shot 迁移，但 naive local optimization 过拟合并擦除 scaling”，而不是“global 完全不迁移”。这些数值
仍只有两/一 seed、outer-test touched、共享 endpoint，只能生成假设，不能作确认结果。

同时 0DU 四臂有假正风险：local-only 为匹配 staged token budget 会重复小 local pool，旧结果已显示第二 epoch
严重过拟合；staged 胜出可能只是 unique rows 替代重复 update。故 0DU 的四臂候选由本节覆盖，改为结果前五臂：
`L1` 一遍 local、`Lbudget` 重复 local、`Gbudget` 重复 global、真实 `G→L`、以及 global pair orientation 按
`sha256(20260823|card_id)` endpoint 全序替换的 `Ghash→L`。hash control 保持相同 endpoints/order/tokens/steps
和传递一致性，但移除真实 quality label；原 interleaved schedule arm 删除，因为其方法 novelty 已关闭且不能排除
上述混杂。

要写“真实 global supervision 可迁移”，除原 `G→L−Lbudget`、`G→L−Gbudget`、TF-IDF 门外，还必须
`G→L−Ghash→L` task-CI 下界>0；若 `L1>Lbudget`，还须 `G→L−L1` task-CI 下界>0。否则只能降格为
unique-data regularization 或避免 local overtraining。当前这仍是
`REVISED_CANDIDATE_PROTOCOL_IDENTITY_G0_BUDGET_BLOCKED`，0 GPU/API/model fit；五臂机器协议、具体模型与精确
GPU·时尚未获批，不得提交。五臂语义机器合同 SHA-256=
`3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9`；其中模型、token budget 与 GPU·时
显式为 null，不能误作 effect 授权。hash orientation producer/非导入式 verifier 已通过 15 个合同测试；在学长旧
global train 的 14,206 rows / 39 tasks 上双跑逐字节一致，overlay SHA-256=
`55ced63f9ea41adcd57c2067cb70fcfa3d430ba7171d89ae6f697e79396a2849`，高置信凭据形状、输出 outcome 字段与
grade-derived commitment 均为 0；交换真实 orientation 或改 outcome 元数据后仍逐字节不变。未提交 overlay 在远端
`74ffb87...` 隔离克隆上又通过 25 个聚焦测试及完整 783 个 `phase1/tests`。首版曾写 outcome-sensitive 的完整源行
承诺，旧 SHA `3f80cd...` 已在提交前撤回且从未进入 effect。该 smoke
只证明真实 schema 可实现，旧数据 test-touched，仍无 effect。详情：

- `phase1/global_local_calibration_candidate_protocol_v2.json`；
- `phase1/global_pair_hash_orientation_control.py`；
- `phase1/verify_global_pair_hash_orientation_control.py`；
- `phase1/实验记录/2026-08-23/GlobalLocalScaling_趋势复核与负控修正.md`。
- `phase1/results/senior_scaling_shape_audit_20260823/`。
- `phase1/results/global_hash_orientation_control_smoke_20260823/`。

## 0DZ. 2026-08-23 future truth-support 资格门已实现并独立复核；仍等待身份 cohort 闭合

0DY 冻结的结果后资格门现已实现，但没有提前打开生产 label。producer 先要求 identity cohort 精确状态为
`FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD` 且绑定 cohort summary SHA；未闭合时在访问 `label_vault.jsonl`
之前 fail closed。闭合后 parent eligibility 只看至少两个 finite `graded` structural siblings，每 physical run 按
`sha256(20260813|run_id|parent_id)` 最多取 2 个；之后才聚合 `y_norm` gap。缺失 `y_norm` 记 truth-unavailable，
不删除 parent 后重选；selected-parent 文件不写 `graded/y_norm/gap/winner`。

独立 verifier 不导入 producer，重新验证 intake hash/security、完整 sibling clique、SHA lottery、gap bins、task/run
balance 与四个固定 gate。精确门边界、差 1 即 KILL、缺失 truth 不重选、三 parent 只取二、collecting 时不读 vault、
双跑逐字节一致和篡改拒绝共 8 项聚焦测试通过。GitHub commit
`9a4df02cd1f76cd6c62657d457ea5c4274ff1c38` 的远端 fresh no-smudge 验收为 `8 passed in 0.37s`，全量
`766 passed, 33 warnings in 75.37s`；敏感文件名计数 0。三次只发生在验证包装层的失败（环境初始化顺序、误收集
历史脚本、遗漏 BLAS 线程限制）均已记录，未运行 production truth analysis。当前仍是 0DY 的 collecting 状态；
生产 label/outcome、GPU、API 与 scientific model fit 均为 0，绝不把工程 PASS 写成机制正结果。

闭合前再审计发现旧独立 verifier 没有自行重建 cohort archive/order/boundary，且 producer script SHA 只验格式。
现已在 production truth 未读时补齐完整 archive、累计 run、boundary、drop membership、flow 和 manifest 复核，并
把声明 SHA 对照实际 producer 文件；新增的 rehashed-boundary 与假 script-SHA 攻击测试均拒绝。加固后 truth 聚焦
10/10，与 Ghash 联合远端聚焦 25/25、完整 `phase1/tests` 783/783；不改冻结协议、样本、门槛或 outcome。证据：

- `phase1/score_channel_future_truth_support.py`；
- `phase1/verify_score_channel_future_truth_support.py`；
- `phase1/results/score_channel_future_truth_support_gate_20260823/`；
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureTruthSupportGate_实现与验证.md`。

## 0DY. 2026-08-23 新 temporal truth-support cohort 已在 0821 intake 前冻结；只开 CPU 资格门

0DX 证明旧 120s cohort 的 paired discriminative support=0 后，在 0821 任一 intake/label vault 产生前冻结新
`score-channel-future-identifiability-cohort-v1`。冻结时连续监控为 archives=204、baseline=128、ready=0、
transactions=57，`intakes/0821-*`=0；未打开 12 个 0821 archive payload、label、grade、code 或 stdout。初始 12 个
archive 的 path/size/mtime 逐项绑定，之后按 `(mtime_ns, relative_path)` 只追加；cohort 在累计至少 300 个 accepted
unique physical runs 时纳入完整 boundary archive 后关闭，structural rejection 不计入且不得部分 salvage。关闭条件只用
identity/count，不看 label。

每 run 仍按 outcome-independent SHA lottery 最多取 2 个、seed=20260813；parent eligibility 只要求至少两个 finite
structural siblings，不用 score magnitude。冻结后才计算 exact non-tie (`range(y_norm)>1e-12`) 及固定 gap bins。只有
non-tied parents≥80、覆盖≥8 tasks、dominant non-tied task≤25%、selected physical runs≥60 四门全过，才允许提交**新的
GPU 设计申请**；本协议本身不授权 replay。即使四门过，120s 外部分历史支持太低，仍须先做功效/成本论证；若用 pilot
选 cap，pilot 与 confirmation cohort 必须物理 run 隔离。当前 GPU/API/model fit=0。证据：

- `phase1/score_channel_future_identifiability_protocol_v1.json`；
- protocol SHA-256=`54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d`；
- `phase1/实验记录/2026-08-23/ScoreChannel_FutureIdentifiabilityCohort_结果前冻结.md`。

identity-only 闭合状态机已在 commit `53ce46f0be18f725987e6d0ce4d72df54ca8c0a9` formal 运行：它只开
`LATEST/SHA256SUMS/transactions/observations/intake summary/archive manifest/source provenance`，遇到首个未决
archive 即停，拒绝包计 0 runs，跨 300 时才纳入完整 boundary archive；不打开 tar、blind code、label vault、score
目录或 outcome。producer×2、非导入式 verifier×2 一致，文件访问审计 forbidden open=0，fresh no-smudge 回归为
`758 passed, 33 warnings in 55.55s`。最早稳定门随后已精确跨过；固定 `74ffb87...` 的 append-only formal 更新纳入
ranzcr+tgs 两个完整 archive，共 8 unique physical runs / 2 tasks，remaining=292，旧 0-run 前缀精确存活；producer×2、
verifier×2 一致，forbidden open 与两类凭据扫描仍为 0，truth/outcome 未打开。第一次 wrapper 因把包装目录而非其
`producer_a/` 传给 previous-dir 而 rc=2；失败时只有一笔事务，随后 tgs 正常追加，retry 重新封住两笔状态后成功，
不得声称两次 transaction SHA 相同。这个 `COLLECTING` 状态不是 effect 结果，不能解释成机制失败或成功。完整回执：
`phase1/results/score_channel_future_identifiability_freeze_20260823/formal_identity_cohort_53ce46f/` 与
`phase1/results/score_channel_future_identifiability_freeze_20260823/formal_identity_cohort_74ffb87_first_0821/`。

## 0DX. 2026-08-23 score-channel 旧 cohort 的辨识支持为零；正方法路线关闭，保留 D&B 漏斗资产

0DW 的 post-hoc availability 分解已在冻结 commit `ab062e1a41c483a87f6d30213b35b8ba88689cb6`
producer×2、非导入式 verifier×2 逐字节一致完成。320 candidates 的联合状态为 both=7、external-only=8、
stdout-only=85、neither=220；external/stdout/hybrid mean ranking regret 全为 0，但这**不是通道完美**。直接从
hash-bound label vault 重建的独立 truth-support audit（commit
`c1a19cf1b69ebdabf0c4d60b010c448c56210a02`）证明：158 parents 中 148=`0.9367088607594937`
真值全并列，只有 10 个可辨识；13/17 tasks 全部 parent 都并列。external 在 10 个 non-tied parent 上任意可用=0、
comparative=0；stdout 任意可用=3、comparative=1。原 primary 的 6 common cards / 3 parents **3/3 真值全并列**，
non-tied common parent=0，因此旧 `1.0 vs 1.0, delta=0` 是 vacuous tie credit。

正式预注册机器状态 `SCORE_CHANNEL_MECHANISM_KILL` 不回写篡改；科学解释追加纠正为
`DISCRIMINATIVE_COMMON_SUPPORT_ZERO`：它不能作为 external=stdout、external 有害或更强 evaluator 无效的证据。
availability secondary 也不能救正结果：external−stdout total-regret mean=
`-0.00006231927410509466`，run CI=`[-0.009615384615384616,0.00931010760618107]`、task CI=
`[-0.00024212570430995738,0.0]`；hybrid−stdout 精确为 0。其 158→10→external 0 / stdout 1→paired 0 的
**identifiability funnel** 是新的 D&B/integrity 资产，而不是方法收益。

selection 只要求“至少两个 finite graded siblings”、未要求 truth variation，是原协议漏掉的辨识门。selective labels、
positivity/overlap 和 missing-score ranking 都已有成熟文献，因此漏斗不得申统计方法首创；可防守贡献仅是把
truth-informativeness 与 evaluator availability 的联合支持在真实 MLE sibling decisions 上物化并发布。旧 120s
score-channel 不再作为正方法路线重跑；任何新 replay 必须先在全新 temporal cohort 结果前冻结 truth-informative
定义、task/run balance 与最低有效 parent 数，再做功效/成本门并另行申请精确 GPU 预算。当前 GPU/API/model fit=0。
证据：

- `phase1/results/score_channel_grounding_availability_20260823/README.md`；
- `phase1/实验记录/2026-08-23/ScoreChannel_GroundingAvailability_正式结果与真值支持纠正.md`；
- `phase1/audit_score_channel_truth_support.py`。

## 0DW. 2026-08-23 grounding-gap 直接竞品关闭 score-channel 宽首创；主线收窄为可用性×条件价值

一手全文审计发现 arXiv:2607.25152v1（2026-07-27）已经在固定 agent/tool/task 下操纵 evaluator information
channel：54 个 T1 cycles 中 agent 100% 自称改进、56% oracle delta≤0；强 in-band judge 仍未弥合差距，独立
out-of-band world-state gate 与 sign-only 变体给出正面结果。因此“首次发现 self-report/ground truth gap”“首次
out-of-band evaluator”“首次证明扩大 judge 不够”“external evaluator beats self-report”全部关闭，不能再作方法或
概念 novelty。该稿虽是 single-task、3 repetitions/arm×6 cycles 的 preliminary pilot，公开时间戳仍必须尊重。

可防守差异是对方三臂产生 independent rollouts、oracle 每轮可见且 out-of-band 只接受 positive delta；我方冻结实验在
真实 MLE search 中比较同一 120 秒、同一 sibling candidates 的 keyed numeric stdout 与 pristine numeric score，并把
scoreable artifact 的选择性缺失、silent candidates、run/task dependence、成本与 temporal freeze 一并作为 estimand。
故 score-channel replay 不撤销，但只作 D&B 的 domain-specific external-validity measurement。headline 收窄为
**grounding availability × conditional sibling-selection value**：grounded feedback 有价值却并非总可用。必须同时报告
联合覆盖、共同覆盖 ranking、silent-candidate regret 分解和 cluster-robust uncertainty；只报共同覆盖准确率不合格。

时间线纠正：旧 320-replay 的 primary aggregate KILL（finite external=15、keyed stdout=92、both=7、共同覆盖
6 cards/3 parents、delta=0）在本 secondary protocol 冻结前已经公开于仓库报告。因此 availability×regret 分解只能是
**post-hoc descriptive analysis**，不得称结果盲、前瞻确认或新 hypothesis test；它不改 primary KILL。协议冻结时未打开
raw result shards/label vault，但这不消除既有 aggregate knowledge。GPU/API/model fit=0。详情：

- `phase1/实验记录/2026-08-23/ScoreChannel_GroundingGap_直接竞品与边界重裁决.md`。
- `phase1/score_channel_grounding_availability_protocol_v1.json`。
- `phase1/实验记录/2026-08-23/ScoreChannel_GroundingAvailability_结果后冻结.md`。

## 0DV. 2026-08-23 学长 mixed `ac008af` 生成配方已后验逐字节恢复；其余 GPU 门不变

0DS 的“提交时无生成命令/收据”仍成立，但“配方不可恢复”已撤回。对三份输入全部 6 种顺序、固定 seed=7、
`n_samples=15000`、decision=1,500、global=0..7,500 step 750、local=`13,500-global` 冻结 66-candidate grid；恰有
一个候选与 target 的 15,875 条 parsed records 全顺序相等：输入依次为 batch value / decision / hardware-time
global value，weights=`8/1/1`，sample counts=`12,000/1,500/1,500`，保留完整 decision test。独立重放得到
6,625,497 bytes 与 target SHA-256
`7792a7da4119bb607cf76628fcdde19923898651ac734ff6afffb0732883cf6e`。随后在 Linux 精确 senior `ac008af8...`
worktree 直接调用原 builder 两次，两次 rows/bytes/SHA 都与 target 相同，且彼此 byte-identical。

唯一性只对冻结 66-grid 成立；原 builder 双跑提供命令到 artifact 的直接验证。本次完整读取历史 pair records（包括
`gap_raw` 等 pair-construction metadata），但未开 Cards/code/raw grade/prospective outcome/model output；GPU/API/model
fit 均为 0。该正面资产只解除 recipe-reconstruction 阻断；test-touched、physical-experiment identity、Cards LFS 404、
launcher typo 与 prompt/mixture/offload 多旋钮混杂仍在，因此 mixed GPU 门和当前 score-channel 主线均不变。证据：

- `phase1/results/senior_mixed_recipe_recovery_20260823/README.md`；
- `phase1/实验记录/2026-08-23/SeniorMixed_ac008af_生成配方逐字节恢复.md`。

## 0DU. 2026-08-23 global value→local decision 的方法首创关闭；保留计算量匹配的 MLE 机制确认

一手反 scoop 审计确认：SP-PRM/Free Process Rewards 已覆盖 outcome→process，ReST-MCTS*/AgentRM 已从树或最终
outcome 产生中间 value，HAF-RM 已做 hybrid granularity supervision，AgentPRM/DataPRM 已覆盖 agent/data-analysis
PRM，FOREAGENT 与 AI Research Preference Models 已覆盖 MLE candidate preference 和执行加速。因此“先 global
value、再 local decision 校准”不得申通用方法首创；简单 mixed/staged training 本身不足以撑方法论文。

仍保留的窄正面命题是同一 Qwen critic 在精确 physical-experiment identity 下的 estimand transfer：global value
scaling 是否能迁移到真实 logged sibling decision，若不能，固定 optimizer-token budget 的 local calibration 能否恢复。
四臂候选协议固定为 local-only、global-only、global→local staged 和逐字节同池 interleaved control；按 H1 transfer、
H2 schedule 的层级门裁决，不允许结果后改比例/模型/子集。该协议当前为
`FROZEN_CANDIDATE_PROTOCOL_IDENTITY_AND_BUDGET_BLOCKED`：0 runs / 0 GPU·h；只有 provenance、全新
experiment-closed split、G0 wall-time 和精确预算另行获批后才可申请。它只作 D&B mechanism ablation，不改变严格
前瞻 score-channel 主线。详情：

- `phase1/实验记录/2026-08-23/GlobalValue到LocalDecision_防Scoop与机制协议.md`。

## 0DT. 2026-08-23 `ac008af` clean overlay 兼容；producer provenance 验收器就绪

三份 clean-confirmation 补丁已在学长精确 `ac008af8...` fresh no-smudge worktree 顺序通过：三次
`git apply --check`、Python/shell compile、`git diff --check` 和 8 个聚焦测试文件，打印
`35 passed in 47.38s`。因此无需重写 harness；但该结果只证明工程兼容，不解除 mixed effect 门。

新增 independent producer provenance contract，要求 frozen expected-run manifest 全覆盖并逐 run 精确绑定
`task/source_date/batch_id/archive_path/archive_sha256/producer_commit`；校验器核对 schema、task/date、SHA、
路径安全，并只扫 tar header 要求唯一匹配 journal。link/device/FIFO、重复/缺失 journal、symlink、额外/遗漏 run 均
fail closed，不打开 member payload。新旧相关测试本地/远端均为 `23 passed`。当前尚无真实 producer manifest，
0811/0812 leaf 与 0730/0809 异常 archive 也未替换，故状态是
`OVERLAY_COMPATIBLE_PROVENANCE_CONTRACT_READY_EFFECT_BLOCKED`，GPU job 仍须为 0。证据：

- `phase1/contracts/SENIOR_SOURCE_PROVENANCE_MANIFEST_V1.md`；
- `phase1/results/senior_source_provenance_contract_20260823/README.md`；
- `phase1/实验记录/2026-08-23/SeniorProvenance契约与ac008af_Overlay验收.md`。

## 0DS. 2026-08-23 学长 mixed `ac008af` 结果盲预飞：数据有正面结构，但训练协议与复现门阻断

对学长 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69` 的四份 pair LFS 对象、mixed launcher
与训练源代码完成 outcome-blind 审计；没有打开 Cards/code/grade、prospective outcome 或模型输出，GPU/API/model
fit 均为 0。Mixed 共 15,875 rows、39 tasks，train/test=`14,715/1,160`，endpoint=`9,620/1,705` 且 overlap=0；
unordered duplicate/self-pair 均为 0，test 最大任务 share=`0.09051724137931035`。这些是可保留的正面结构事实。

但 mixed test 与旧 merged-decision 的 1,160 条 test 在顺序和 multiset 上逐 pair 完全相同；训练代码又把 test pool
直接作为每 10 steps 的 eval dataset，并按 `eval_pair_accuracy` 记录 best checkpoint。它没有进入梯度，但已经
test-touched，不能作 one-shot frozen confirmation。当前 launcher 还引用不存在的
`decision_value_mixed_pairs_filtered_runsplit.jsonl`；真实文件名不同，直接运行会失败。真实 mixed 输出名在 `src/`
与 `docs/` 中零引用，builder command/seed/weights/receipt 在提交时未记录；0DV 已在冻结网格中后验唯一恢复配方并用
原 builder 逐字节验证，但生成时 receipt 仍缺失。train 的 13,312/14,715=
`0.9046551138294258` 为 value rows。Cards LFS 对象 `5e0f380...`（779,146,574 bytes）从 fresh checkout 拉取返回
GitHub LFS 404。该 commit 还同时改变 prompt、mixture 与 ZeRO offload，无法隔离科学旋钮。

正式裁决=`EXPLORATORY_ONLY_PROTOCOL_AND_REPRODUCIBILITY_BLOCKED`。这不撤回 0BW 的 value scaling 探索信号，
但当前 mixed launcher 不得提交 GPU。解锁必须先完成 0CR 的 producer-side immutable source-batch manifest 与异常
archive 替换，再固定 mixed 生成收据、experiment-closed train/dev/全新 frozen、dev-only checkpoint 选择、one-shot
test、单旋钮提交和 fresh-clone LFS 验证；随后先报 dev-only G0 与精确 GPU·时，获批后再跑。直接证据：

- `phase1/results/senior_mixed_ac008af_audit_20260823/README.md`；
- `phase1/实验记录/2026-08-23/SeniorMixed_ac008af_结果盲预飞审计.md`。

## 0DR. 2026-08-22 0820 首包已摄取；LMSYS task identity 结构失败已精确拒收

`0820` 首个 `cdiscount` archive 已在固定 scientific commit 下提交，实际新增 4 个 eligible physical runs、
71 endpoints 与 19 structural pairs；累计为 253 runs、6,542 endpoints、1,684 pairs、26 tasks，dominant
run-task/pair-task share 分别为 `0.10276679841897234`/`0.16508313539192399`。outcome、label vault 与 scorer
prediction 均未被 accumulator 打开。

随后精确 archive `0820/lmsys-chatbot-arena-8seeds.tar.gz` 两次 intake 均在 task identity 门 fail closed。冻结 auditor
双跑逐字节一致：4/4 checkpoint journals 的 competition identity cardinality 都为 0；raw journal 先过凭据扫描，
env/live-event member、identity 值、代码、stdout、grade、metric 与 outcome 均未读/未输出。故整包按固定 reason
code 拒收，不从文件名补 task、不部分 salvage。diagnostic/registry SHA-256 分别为
`c71a3a7e952e693fb715d34dd82bc71c7a53ccb0285f2bfa06680d5dbbc09728` /
`766a4fa678a4cb9ae55fdb460ae94b5f1be93ce2040b64ed7e48c13260f9aebd`。

下一步只允许在 clean control commit 上绑定全部旧 registry 与本 registry，恢复 0820 剩余 archive 的 CPU-only
连续摄取及 label-free transition escrow append。scientific commit、activation、estimand、稳定性门与 frozen scorer
不变；transaction 未真正提交前不得把剩余 archive 算作入库。证据：

- `phase1/results/prospective_structural_rejection_20260822/README.md`；
- `phase1/实验记录/2026-08-22/Prospective0820_LMSYS结构拒收与摄取恢复.md`。

## 0DQ. 2026-08-22 max-step 正关联是 sequential-feedback 线索，不是新 selector

0DP 后的 post-result、label-unused 结构审计绑定 S2 v2 train SHA
`e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1`：2,109/2,109 source groups
内 candidate step 均唯一，且全部同 depth、同 operator；1,662 组 step 连续、447 组不连续。聚焦测试 2/2；Linux
正式只读输入双跑逐字节一致，output SHA-256=
`74df0fe8bf3fbeeb38f0fda3d3a406c46c1df0fea9fd8c9826bf888d263e2b17`。统计没有使用 winner 值，且不新增任何
outcome slicing。

AIRA canonical MCTS 在同 leaf 的 child loop 中逐个执行 `generate -> task.step_task -> parse -> journal append`，
之后才生成下一个；默认 `simple_memory` 又把已有 valid node 的 analysis/validation metric 给后续 operator。因此
0DP 的 max-step 正关联与 within-expansion sequential feedback 一致，但 run-level exact collector commit/config 未绑定，
不能作因果归因；它也不是从同时存在的 unexecuted batch 中免费选择。

更直接地，arXiv:2605.28224 已把该机制形式化为 cross-sibling within-expansion memory / Raw Sibling，并在 beam、
MCTS 与多个 tool-use tasks 上实验；效果高度异质。故 memory/MCTS 方法首创关闭。该发现只保留为 D&B 的
sequential-feedback confound 与未来 MLE-domain randomized replication 候选；本轮不提交 GPU/API，不改变严格前瞻
score-channel 主线。证据：

- `phase1/实验记录/2026-08-22/SourceChoiceMaxStep_时序语义与Memory防Scoop审计.md`。

## 0DP. 2026-08-22 固定 TF-IDF source-choice OOF 正式关闭；step control 留作机制审计线索

控制 commit `11b7f23d2d91bc412c3a2e0c8cd7d6a23fbb5baf` 的固定 char-TFIDF 已在 2,109 groups、
5,739 candidates、23 tasks、275 physical runs 上完成 task-LOTO 与 run-grouped 5-fold。task-LOTO 的
task-macro delta=`0.04882368496193506`，但 task-cluster CI=
`[-0.002818580653200905, 0.10637780689695644]`，exact sign=`12+/11-/0`、`p=0.5`；micro
delta=`0.0014341238025448724`，run-cluster CI 也跨 0。run-OOF 的 task-macro delta=
`0.051900194601970095`、task CI 为正，但 micro delta=`0.014236399762715573` 的 run-cluster CI=
`[-0.010765587398163913, 0.042475689286202156]`。故冻结的 cross-task 与 run-only gates 均失败，正式
verdict=`NO_NARROW_POSITIVE`。

producer×2、独立 verifier×2 与有理数 exact-sign audit×2 均逐字节复现；summary SHA-256=
`4e5da9a357f7675f34928713604d82abf73d41bdcd348297a802ac68c3bf8fcf`。exact audit 保持 verdict 不变；
forbidden frozen/vault path、credential、worktree drift 与正式 stderr 均为 0，产物只读。按结果前合同，不激活
recovery-provenance sensitivity 或 frozen/extension escrow；不得换模型、阈值、任务或子集 rescue。

预注册的 `max_step_then_min_sha` control 单独呈现跨任务正关联：task-macro delta=
`0.03755268823459413`，task CI=`[0.003178139904469143, 0.07802102179810541]`，sign=
`17+/5-/1`、`p=0.00845026969909668`；但 micro/run-cluster CI 跨 0，且完整 parent children 的
decision-time simultaneous availability 尚未证明。它只作为 D&B/integrity 的 temporal/logging-mechanism 线索，
不得称为 deployable selector。活跃正方向仍是 0DO 的严格前瞻 score-channel 与 benchmark/integrity 容器。证据：

- `phase1/实验记录/2026-08-22/SourceChoiceOOF_TFIDF_v1正式裁决.md`。

## 0DO. 2026-08-22 RPM 关闭 child-selection / future-potential 首创，主线收缩到严格 D&B 与评分通道

正式 OOF 裁决前的防 scoop 审计发现 *AI Research Preference Models*（arXiv:2608.13940v1，2026-08-14）比
FOREAGENT 更
直接：它在 AIRA-dojo 中每步从同一 parent 生成 `N=15` 个未执行 child，再由 inference-only 或 agentic RPM 选择一个
执行。20 个公开 AIRS-Bench 文本/表格任务、10 seeds、24h H200 的端到端结果从 No-RPM `0.684` 提高到
`0.711/0.729`；达到基线 24h 分数只需 `14.88/15.50` 小时。task-stratified improvement-probability CI 下界也严格
高于 0.5。其离线 1,000 sibling pairs 直接以“节点子树最高 test score”为标签，并报告强 LLM、context、reasoning、
ensemble 与 pilot 的正趋势。因此以下首创全部关闭：AIRA-dojo 未执行 child preference、candidate preference 带来系统
加速、用 subtree-best/future-potential 作为新标签、以及简单加大 judge/context/pilot 的方法 novelty。

论文同时承认离线数据来自旧 greedy runs、存在 off-policy 与 subtree-max 机会偏差；删除 gap<0.01 near-ties；主结果
只覆盖 child creation，final-node selection 未可靠超过 highest-validation，并明确把 parent selection 留作 future work。
这不授权我方自动重开 parent/lookahead：当前 source-choice 标签是 status-certified selection outcome、不是最终任务质量；
正在运行的固定 TF-IDF OOF 仍按原门完成，NO 即关闭，不换模型/子集 rescue。即使 GO，也必须依次通过 exact-sign、
recovery-provenance、sealed frozen/temporal replication 和预算等价 utility bridge 才能讨论方法增量。

当前可防守主线进一步收缩为：（1）真实 logged decision topology、failure/unknown-preserving、candidate/run/task 依赖、
run-clean+temporal frozen、噪声/覆盖/query-init 成本与撤回链构成的 D&B/integrity benchmark；（2）机制 commit 后新
physical runs 上的 score-channel 前瞻复现，研究同一短时执行预算内 pristine 外部分、stdout 与选择性可观测性。
RPM/FOREAGENT 证明 candidate preference 有用；我们的贡献必须回答这些结论在更严格 estimand 与审计契约下还能保留
多少，而不能再声称发明 preference mechanism。时间线限定：审计开始时第一生产者 stdout 已出现暂定 NO，但第二
复算、独立 verifier 和 exact-sign audit 均未完成；因此不能称为完全结果盲，且没有据此修改任何运行中协议。详细一手
核查：

- `phase1/实验记录/2026-08-22/AIResearchPreferenceModels_直接竞品与路线重裁决.md`。

## 0DN. 2026-08-22 FOREAGENT 关闭“首次执行前 preference”，但强化严格 benchmark 边界

结果前防 scoop 审计发现 ACL 2026 Highlight 的 FOREAGENT（arXiv:2601.05930）是直接竞品：它已经定义
Data-centric Solution Preference，发布 26 tasks / 895 solutions / 18,438 pairs，并把 LLM pairwise prediction
接入 Predict-then-Verify，报告 61.5% accuracy、5 tasks x 3 runs 的 6x acceleration 与 +6% Beat Ratio。因此“首次
执行前比较两个 MLE 解”“首次用预测减少执行”“首次 MLE preference corpus”全部关闭；只做离线 predictor accuracy
也不构成方法 novelty。

但官方 commit `c4d52cf99bd870d830b456ac7c0684aec1aef375` 的 `group.py` 明确对每任务 solution pool 使用
`itertools.combinations` 枚举所有组合，并过滤 invalid submission/缺 score；论文也说明 syntax/runtime crash 被过滤。
同一 solution 因而反复进入多个 pair，18,438 不是独立决策数。其 within/cross-trajectory 分析把“不同 run 或不同
task”合为 cross；公开 report 实现给出 record/task point means，未实现 candidate/run-cluster uncertainty。该差异不
否定 FOREAGENT。其公开 Parquet 的只读结构复核进一步得到 18,361 unique pairs 只由 895 solution paths 构成，
solution pair-degree median/max=49/49。该证据把我们的可防守贡献收紧为：真实 parent/source choice set、
candidate/run/task dependency、
execution-cliff/unknown-preserving 标签、run-clean + temporal frozen、query/init 成本和前瞻 utility bridge。

当前固定 TF-IDF OOF 继续运行，因为它问的是上述真实 source unit 上的 task-LOTO/run-OOF 廉价信号；其结果仍须按
原 gate 裁决。GO 后先过 recovery-provenance sensitivity，再生成 label-free frozen/extension escrow；NO 后不得改模型/
追子集。即使 GO，FOREAGENT 已有系统收益，故最终方法主张仍必须补预算等价的真实 source-selection replay，离线
accuracy 不能替代。证据与逐轴对照：

- `phase1/实验记录/2026-08-22/SourceChoice_FOREAGENT_直接竞品与边界修正.md`。

## 0DM. 2026-08-22 source-choice S2 v2 operator-proxy 修复正式通过

控制 commit `3ceb99f8030fb196d2abc388e277b11dbd1bc571` 按 0DL 的唯一允许 diff，把 raw operator
case-insensitive 地规范化为固定 `Draft/Improve` 枚举。3,000 groups / 8,027 candidates、winner、candidate
SHA 字典序、完整 code bytes、step/depth、role 与 cluster metadata 全部不变；train/frozen/extension 分别规范化
697/192/10 个小写值，输出未知或小写 operator=0。`provenance/source_journal_sha256` 各删除 8,027 次，model
blocked fields=0；frozen/extension winner fields=0/0，vault 未读。

producer×2 和不 import producer 的 verifier×2 逐字节一致；focused=`20 passed`，完整 phase1 tests=
`706 passed, 25 warnings`。forbidden scientific/vault path、credential filename/content、worktree drift、repro diff、
正式可写文件均为 0。正式状态 `SOURCE_CHOICE_DECISION_VIEW_V2_READY`，只读目录：
`/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2`。

这只恢复 model-view integrity，不含 predictor accuracy 或 search utility。0DL 的 v1 四份 LFS 文件继续封锁，不得因
v2 通过而使用。下一步只允许：（1）以 v2 train SHA
`e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1` 另立 train-only task-LOTO/run-OOF
协议；（2）把 v2 作为新 immutable LFS 目录发布。frozen/extension vault 在模型族和选择规则冻结前继续不读。证据：

- `phase1/results/source_choice_decision_view_v2_20260822_3ceb99f/README.md`；
- `phase1/实验记录/2026-08-22/SourceChoiceDecisionView_S2v2正式裁决.md`。

## 0DL. 2026-08-21 source-choice S2 v1 因 operator 大小写代理泄漏撤回

S2 v1 在任何模型拟合、frozen label 打开或 frozen score 之前的 train-only 模型预检中发现第二层重建代理：
候选 `operator` 同时出现 `Improve` 与 `improve`。全 3,000 groups / 8,027 candidates 中，小写
`improve` 恰有 899 个，与 S1v2 的 899 个 `journal_recovered` candidates 总数完全相等；train 中小写
`improve`=697 slots / 0 winners，而大写 `Improve`=4,949 slots / 2,071 winners。故删除显式
`provenance/source_journal_sha256` 后，大小写仍可无损恢复同一 post-selection provenance proxy。

该发现不是 predictor 结果：模型拟合=0、GPU/API=0、frozen/extension winner vault 未读。数组顺序另经审计为
candidate SHA 字典序；first/last/min-SHA/max-SHA accuracy=0.390232337601/0.411095305832/
0.390232337601/0.411095305832，接近 exact uniform expected=0.400178014652，未见同类位置捷径。

因此 0DK 的四份 immutable v1 JSONL 保留为可复核失败产物，但状态改为
`SOURCE_CHOICE_DECISION_VIEW_V1_MODEL_BLOCKED`，不得训练、评分或作为 benchmark release。下一步只允许新协议/新目录
生成 v2：将 case-insensitive `draft/improve` 规范化到固定枚举 `Draft/Improve`，其他 operator fail closed；除该字段外
group、candidate、winner、顺序与 code bytes 必须逐项不变。v2 还必须显式验证小写值为 0、operator/provenance
contingency 被消除、producer/verifier 独立一致，之后才能重开 train-only OOF。直接证据：

- `phase1/results/source_choice_decision_view_operator_proxy_audit_20260821/README.md`；
- `phase1/实验记录/2026-08-21/SourceChoiceDecisionView_S2v1_operator代理泄漏与撤回.md`。

## 0DK. 2026-08-21 source-choice decision-time view 正式通过

控制 commit `fd5c3ee0fdfffe399088e2e3a4394598264239a6` 在不改 0DJ 的 3,000 groups、8,027 candidates、
winner、顺序与 code bytes 的条件下，完成 exact-field decision-time projection。每个 candidate 的
`provenance/source_journal_sha256` 均被结构化删除，removed count 各为 8,027，模型对象 blocked fields=0；
`role/run_id_sha256/parent_id_sha256` 分离到 cluster manifest。train winner fields=2,109，frozen/extension=0/0，
真实 vault 未读。

producer x2 与不 import producer 的 verifier x2 逐字节一致；focused=`18 passed`，完整 phase tests=
`704 passed, 25 warnings`。forbidden scientific/vault path、credential filename/content、worktree drift 与正式可写
文件均为 0。正式状态 `SOURCE_CHOICE_DECISION_VIEW_READY`，0DJ 的 release blocker 已在 schema 层解决，而不是靠
文档要求用户忽略泄漏字段。

该结果只授权两类后续：（1）秘密/hash 复核后的 immutable S2 role files + cluster manifest Git LFS 发布；（2）另立
结果前协议的 train-only OOF baseline。它不含 predictor accuracy、frozen score、search utility 或算法 novelty；原始
S1v2 provenance-rich view 仍不得训练/分发，frozen/extension vault 在模型族与选择规则冻结前继续不读。score-channel
prospective gate、first-960/strict-future 与 Qwen checkpoint 约束不变。直接证据：

- `phase1/results/source_choice_decision_view_v1_20260821_fd5c3ee/README.md`；
- `phase1/实验记录/2026-08-21/SourceChoiceDecisionView_S2正式裁决.md`。

## 0DJ. 2026-08-21 source-choice S1v2 物化通过，但原始模型视图因 provenance 泄漏封锁

控制 commit `5d6de6eddad30cef46c5803d8810f835c3f58c4f` 的 v2 已正式物化并封存 3,000 个
answerability-conditioned source groups、8,027 个 candidate slots；train/frozen/extension=
2,109/778/113 groups，899 个候选从 169 个 credential-safe 且 status-bound journals 恢复。frozen/extension
公开 winner 字段均为 0，train/frozen parent/run overlap 均为 0。producer x2、独立 verifier x2 均逐字节一致；
focused=`14 passed`，完整 phase tests=`695 passed, 25 warnings`，forbidden path/credential/worktree drift 均为 0。

但 materialization success 不等于 release readiness。任何模型或 frozen score 之前的 train-only 后验字段审计发现，
5,042 个 `card` candidates 含全部 2,109 个 winners，而 697 个 `journal_recovered` candidates 的 wins=0；496 个
groups 混合两类。仅用 provenance 过滤就把 uniform expected top-1 人为提高
`0.039746120009281544`，固定 min-hash control 也提高 `0.034613560929350404`。这是 post-selection
observability 泄漏，不能作为 decision-time signal。

因此原始 v2 只作为内部、provenance-rich 审计原料，状态为
`SOURCE_CHOICE_RAW_MATERIALIZATION_VERIFIED_MODEL_VIEW_BLOCKED`；不得训练、评分或通过 LFS 发布。下一步只授权
CPU-only exact-field decision-time projection，结构化删除 `provenance/source_journal_sha256`，分离模型输入与聚类
metadata，并让独立 verifier/sealed evaluator 拒绝 extra fields。投影通过前 frozen/extension vault 继续未读，GPU/API
均为 0；score-channel prospective gate、first-960/strict-future 与 Qwen checkpoint 约束不变。直接证据：

- `phase1/results/source_choice_benchmark_materialization_v2_20260821_5d6de6e/README.md`；
- `phase1/实验记录/2026-08-21/SourceChoiceBenchmark_S1v2正式裁决与输入泄漏封锁.md`。

## 0DI. 2026-08-21 source-choice benchmark 物化支持正式通过

控制 commit `efbda542e69484bc93b0b36fcda10d37712cc674` 把 0DG 的 answerability census 与旧正式
construction census 做 SHA/role/task/run/parent/source-size 闭合，只问 certified winner 是否同时具备完整的
candidate-code 引用。没有重新读取 raw archive/journal、code bytes、numeric grade、gap、旧模型结果、prospective
outcome 或 first-960。

3,001 个 status-certified winners 中 3,000 个可物化，coverage=`0.9996667777407531`；相对全部 3,252 parents
的 rate=`0.922509225092251`。train 2,109/2,109、frozen 778/778 均完整，extension 为 113/114；唯一缺口不插补。
共 8,027 candidate slots，1,521/3,000 groups 的 source size≥3，share=`0.507`。23 个任务均有覆盖，20 个任务
至少 20 groups；dominant-task share=`0.20066666666666666`。train/frozen parent 与 physical-run overlap 均为 0。

13 个冻结材料门全部通过，`materialization_s1_authorized=true`。producer×2、独立 verifier×2 逐字节一致；
focused=`7 passed`，完整 phase tests=`686 passed, 25 warnings`；forbidden path、秘密、worktree drift 与正式可写
文件均为 0。

这只授权 S1 生成 **answerability-conditioned** train inputs 与 sealed frozen evaluator。当前措辞必须是
`candidate_code_reference_complete`：S1 仍须逐条重验 code hash 与 context；不得声称整个 v11 是 complete
choice-set dataset，也不得称为 listwise 方法、predictor/search utility、prospective effect 或算法 novelty。0CP
strict-future/first-960 与 GPU 批准门均不改变。直接证据：

- `phase1/results/source_choice_materialization_support_v1_20260821_efbda54/README.md`；
- `phase1/实验记录/2026-08-21/SourceChoiceMaterialization_S0正式裁决.md`。

## 0DH. 2026-08-21 source-answerability 九项证据索引正式通过

控制 commit `fff9e9fb937390142b059818dde3c593ece144a8` 的 evidence index v5 逐项继承 v4 八项，并把
0DG 作为第九个独立 `source_decision_answerability` estimand 接入。新增合同直接绑定 3,252-row parent CSV、
23-row task CSV、summary、独立 verifier 与 producer manifest；CSV 的 normalized hash、精确 header、行数和
等宽性都由独立实现核验。

正式 index 含 9 entries、26 个 JSON artifacts、3 个 bound files 与 305 条 assertions；normalized SHA-256=
`4bff2b9fa48f2b530de886ab6b799011e8c4aa48ed378cdee0959c8b087a1627`。机器可核验的新正资产是
published/status-aware unique-winner answerability=2,344/3,252 与 3,001/3,252，新增 657，最终 rate=
`0.9228167281672817`。

builder×2 与独立 verifier×2 逐字节一致；正式 focused=`7 passed, 1 skipped`，完整 phase tests=
`678 passed, 1 skipped, 25 warnings`，回传产物后 checked-output gate=`8 passed`。秘密、worktree drift 与正式
可写文件均为 0。

该项仍只是 release answerability，不是 predictor accuracy、search utility、完整 numeric total order 或 prospective
effect；传递关系不是 logged comparisons，identity-unavailable parents 未插补。v5 仍为 `AWAITING_FIRST960`，
不改变 0CP strict-future、first-960/closure 或 GPU 批准门。直接证据：

- `phase1/results/decision_corpus_evidence_index_v5_20260821/README.md`；
- `phase1/实验记录/2026-08-21/DecisionCorpusEvidenceIndex_v5_正式裁决.md`。

## 0DG. 2026-08-21 failure-aware partial order 把 source-winner answerability 提升至 92.28%

控制 commit `e9f6f69ebb1364e14bd97ce0a140be6579977f33` 对固定 3,252 个真实 source choice sets
做了结果前冻结审计。只组合已发布的 finite-finite orientation 与 provenance-bound validity edges；仅当一个
candidate 在 DAG 传递闭包中可达 source set 的所有其他 candidate，才记唯一 source winner 可认证。没有读取
code/obs、numeric grade、gap、prospective outcome 或 first-960。

published graph 单独认证 2,344/3,252=`0.7207872078720787` 个 source winners；status-aware graph
认证 3,001/3,252=`0.9228167281672817`，新增 657 个、绝对 gain=
`0.20202952029520296`，恢复原未回答缺口的 `0.723568281938326`。train/frozen gain=
`0.21631051024858264/0.17751479289940827`；14 个支持任务中 11 个为正，dominant added-winner task
share=`0.2800608828006088`。八项预注册材料门全部通过。

只保留 `EXECUTION_ERROR` 的强敏感性仍新增 649 个，winner rate=`0.9203567035670357`、gain=
`0.19956949569495694`，train/frozen 与 task breadth/concentration 的全部门也通过。producer×2 与独立
verifier×2 均逐字节一致；focused=`5 passed`，完整 phase tests=`671 passed, 25 warnings`，forbidden path、
秘密、worktree 漂移与正式可写文件均为 0。

允许主张的是当前 release 的 source-level answerability 正资产，不是 critic 准确率、search utility、完整数值
total order 或算法 novelty；传递推断关系绝不能写成 logged comparisons。最终仍有 251 个 parent 未回答，其中
149 个 source identity 不可恢复。下一步只把它作为独立 estimand 接入 machine-verifiable evidence index；不改变
0CP strict-future、first-960/closure 或 GPU 批准门。直接证据：

- `phase1/results/source_decision_answerability_v1_20260821_e9f6f69/README.md`；
- `phase1/实验记录/2026-08-21/SourceDecisionAnswerability_v1正式裁决.md`。

## 0DF. 2026-08-21 operator-conditioned retention 的支持门失败；S1 不执行

控制 commit `bfdadfade59b69a2c93af0a86e074b13792824c4` 对固定 3,252-parent source-opportunity 表与
16,012-card v11 做了结果盲身份/支持审计。parent-card join=3,049/3,252=
`0.9375768757687577`，presence/context mismatch 均为 0；train/frozen physical-run 与 parent overlap 也均为
0。分析没有使用 retention 值、child count、pair orientation、numeric grade、code/obs 或 prospective outcome。

68 个 task×operator 单元中，只有 9 个单元分别达到冻结的 train parents≥20、frozen parents≥10、train
runs≥5、frozen runs≥3。进一步要求同一任务的 `Debug` 与 `Improve` 都合格后，只剩 3 个任务、6 个单元，低于
预注册的 8 tasks/16 cells；支持 frozen parents 的 dominant-task share=`0.6814404432132964`，也高于 0.25。
正式状态为 `INSUFFICIENT_OPERATOR_CONDITIONED_RETENTION_SUPPORT`，
`s1_effect_analysis_authorized=false`。不得降低 run/parent/task 门、筛任务或读取这 3 个任务的分层 retention 追救。

这不是 operator 方法效果为负，而是当前 v11 无法支撑该非因果 transport estimand。更早 0AM 已因同 parent
mixed operators=0 关闭因果 operator effect；本轮又关闭了“跨 parent 但 run-robust”的免费重分析。后续若需要该轴，
只能等待自然新增 frozen runs 或另立有预算 ledger 的前瞻生产干预，不能占用 0CP strict-future 主线。

producer×2 与不 import producer 的 verifier×2 均逐字节一致；focused=`5 passed`，完整 phase tests=
`666 passed, 25 warnings`，forbidden scientific path、秘密扫描、worktree 漂移与正式可写文件均为 0。首次 commit
`60a4f61...` 在第一张 card 因把 canonical `task` 对象误当字符串而于任何 cell 统计前 fail-closed；只修正为
`task.name` 并增加 schema 反例，协议、输入与阈值不变，旧失败目录保留。直接证据：

- `phase1/results/operator_conditioned_retention_support_s0_20260821_bfdadfa/README.md`；
- `phase1/实验记录/2026-08-21/OperatorConditionedRetention_S0正式裁决.md`。

## 0DE. 2026-08-21 failure-aware 八项证据索引正式通过

控制 commit `832947a6d7bf43da57dcb3702bb713a3b226e47e` 的 evidence index v4 已逐项继承 v3 七项，并把
0DD 显式偏序作为第八个独立 estimand 接入。正式 index 含 8 entries、23 个 JSON artifacts、1 个直接绑定的
2,079-line edge JSONL 与 240 条 assertions；normalized SHA-256=
`80450de3528fcaf2dc5edb5f54109ba30189f81e66c5715fbe755012d5de391b`。

新增合同同时验证 edge hash、line count、逐行 JSON、formal manifest、summary 与独立 verifier，因此“2,079 条显式
validity edges”不再只是报告数字。旧七项的顺序、artifact、assertion、claim 和边界均未修改。允许主张 failure-aware
partial order 已作为可机器核验资产发布；仍禁止 numeric-quality total order、complete choice set、MAR、
predictor/search utility、prospective effect、算法 novelty 与 first/only。整体状态继续 `AWAITING_FIRST960`。

builder×2/verifier×2 逐字节一致；focused=`6 passed, 1 skipped`，完整 phase tests=
`660 passed, 1 skipped, 25 warnings`；skip 仅因控制 commit 运行时 formal v4 尚未回传。worktree 与秘密扫描均为 0，
正式目录只读。直接证据：

- `phase1/results/decision_corpus_evidence_index_v4_20260821/README.md`；
- `phase1/实验记录/2026-08-21/DecisionCorpusEvidenceIndex_v4_正式裁决.md`。

## 0DD. 2026-08-21 status-certified partial order 已导出为 2,079 条显式边

控制 commit `c9bfc21c1e8428787caf4e70db404a18990910bc` 已把 0DC 的 aggregate relation audit 补全为可分发的
child-ID edge manifest：902 个 certified invalid children 与同 parent finite endpoints 构成 2,079 条唯一
`VALIDITY_DOMINANCE` edges，覆盖 1,498 个 valid children、658 parents 和 14 tasks。三份 v11 b0 pair 文件只用于
endpoint identity union；orientation direction、gap、numeric score、code 和 prospective outcome 均不用于边生成。
独立 verifier 从固定输入逐条重构，差为 0。

更窄的 `EXECUTION_ERROR`-only 压力测试删除全部 `OFFICIAL_GRADE_ABSENT` 后仍保留 2,060 edges；coverage=
`0.815684264479754`、gain=`0.21117375704766786`、gap recovery=`0.5339554173146708`，train/frozen gain=
`0.22004357298474944/0.18819351975144252`。14 个支持任务中 11 个为正，dominant share=
`0.1883495145631068`，原全部材料门仍通过。因此 headline 不依赖 grade-absent 类别。

这仍只是 provenance-bound validity partial order，不是 numeric-quality total order，也不证明 complete choice set、MAR、
predictor/search utility 或算法 novelty。producer×2/verifier×2 逐字节一致；focused=`5 passed`，完整 phase tests=
`654 passed, 25 warnings`，forbidden path、秘密与 worktree 审计为 0。直接证据：

- `phase1/results/status_certified_edge_manifest_v1_20260821_c9bfc21/README.md`；
- `phase1/实验记录/2026-08-21/StatusCertifiedEdgeManifest_v1_正式裁决.md`。

## 0DC. 2026-08-21 status-certified partial order 恢复 53.9% 的关系缺口

控制 commit `82e1be5839506556e0edde5cd240e1918e2eed66` 在结果前固定两份 metadata SHA、关系定义和九个
材料门。只将同 parent finite child 对精确恢复的 `EXECUTION_ERROR`/`OFFICIAL_GRADE_ABSENT` child 组成
validity-dominance relation；unknown、未注册 missing slot、invalid-invalid 和未发布 finite-finite 关系保持 unresolved。

正式状态=`VERIFIED_MATERIAL_STATUS_CERTIFIED_RELATION_RECOVERY`：902 个 certified invalid children 新增 2,079 条
关系，使 source-level certified coverage 从 5,897/9,755=`0.6045105074320861` 提升到 7,976/9,755=
`0.8176319835981548`，绝对 gain=`0.2131214761660687`，恢复原关系缺口的
`0.5388802488335925`。train/frozen gain=`0.22235838779956427/0.18819351975144252`；14 个支持任务中 11 个
为正，dominant task share=`0.18759018759018758`。全部预注册门通过。

这是强 D&B 数据资产但不是算法 novelty：NAS-Bench-101 已把 invalid architecture 记最差，constrained BO 已有
feasibility/objective 分解。允许主张的是 natural MLE-agent sibling 上 provenance-bound、unknown-preserving 的
failure-aware partial-order release。禁止把 `C(n,2)` 写成实际 comparison log、把 validity 写成 missing numeric score，
也禁止 complete choice set、MAR、predictor/search utility 或 first/only；仍有 1,779 relations unresolved。

producer×2/verifier×2 逐字节一致，独立重建差=0；focused=`5 passed`，完整 phase tests=`649 passed,
25 warnings`，forbidden path、秘密扫描、worktree 漂移和可写文件均为 0。回传的 54 个 manifest payload 全部匹配。
直接证据：

- `phase1/results/status_certified_partial_order_v1_20260821_82e1be5/README.md`；
- `phase1/实验记录/2026-08-21/StatusCertifiedPartialOrder_v1_正式裁决.md`。

## 0DB. 2026-08-21 observability-aware 七项证据索引正式通过

控制 commit `ce5c558509b1f481f9e9df1212d9f00c3cf00bce` 的 evidence index v3 已把 0DA 漏斗作为独立
`decision_observability` estimand 接入统一 release contract，同时逐项继承且不改写 v2 六项。正式 index 共 7 个
entries、20 份哈希绑定 JSON artifact、181 项 dotted assertions；index normalized SHA-256=
`424f06b161086972fedf55d5e8e06e22d92c21e1558a04b2dd6c55e3cb637b49`。

机器可核验的正结论是：3,252-parent census 的 child-slot loss=`0.14612676056338025`，declared pair-capacity
loss=`0.3851358277806253`，组合放大=`2.6356283154144×`；source/finite/published pair capacity 或 edge 数为
9,755/5,998/5,897。该条目把 source opportunity、task-conditioned retention 与 observability denominator 连接成
可发布的数据合同，而不是散落在报告中的手工数字。

全部边界同时进入 schema：`C(n,2)` 不是真实 agent comparison log；全部 parents 仍有 finite/published decision，
禁止“决策点消失”；不恢复完整 choice set、不假定 MAR、不证明 predictor/search utility 或 prospective effect。
builder×2/verifier×2 逐字节一致；完整 phase tests=`643 passed, 1 skipped, 25 warnings`，秘密扫描、worktree 漂移、
prospective outcome read 与正式可写文件均为 0。回传的 30 个 payload 文件全部通过远端 `SHA256SUMS`。

直接证据：

- `phase1/results/decision_corpus_evidence_index_v3_20260821/README.md`；
- `phase1/实验记录/2026-08-21/DecisionCorpusEvidenceIndex_v3_正式裁决.md`。

## 0DA. 2026-08-21 decision observability funnel 正式通过：14.6% child loss 放大为 38.5% pair-capacity loss

结果前 commit `1b8a7b94f7175823763ef866e0dde2ce202828b7` 对固定 3,252-parent source 表完成完整 release census。
source-declared child slots=9,088，raw/finite=7,760，child loss=`0.14612676056338025`；对应的 undirected
`C(n,2)` pair capacity 从 9,755 降至 5,998，loss=`0.3851358277806253`，比 child loss多
`0.23900906721724502`，组合放大=`2.6356283154144×`。finite capacity 中实际发布 5,897 unique edges，
coverage=`0.9831610536845615`；三段 loss 为 source→raw 3,757、raw→finite 0、finite→published 101。

全部六个冻结门通过，状态=`VERIFIED_MATERIAL_COMBINATORIAL_DECISION_ATTRITION`：14 个 tasks 达到 source
pair capacity≥100，12 个显示 pair loss>child loss，train/frozen roles 也都通过。producer×2/verifier×2 逐字节
一致，独立重建差=0；focused=`6 passed`，完整 phase tests=`638 passed, 25 warnings`，forbidden path、秘密扫描
与 writable files 均为 0。

允许的正主张是：在当前 release 中，source-level candidate-slot censoring 会非线性压缩可观察 sibling comparison
resolution；只报 retained pairs 会掩盖真实 decision denominator。必须同时保留两个限制：全部 3,252 parents 仍有
至少两个 finite candidates 与一条 published edge，所以不是“38.5% 决策点消失”；9,755 是 declared structural
capacity，不是真实 agent comparisons，也不恢复完整 labeled choice set。1,328 parent-level missing slots 与先前
996 distinct target identities 分母不同，不得混算。

该结果把 0CX 的 task-conditioned retention 和 0CW 的 identity/status registry 连接成可成图的 D&B 正资产，
但不是 predictor/search utility，不改变 strict-future、first-960/closure 或 Qwen 预算门。直接证据：

- `phase1/results/decision_observability_funnel_v1_20260821_1b8a7b9/README.md`；
- `phase1/实验记录/2026-08-21/DecisionObservabilityFunnel_v1_正式裁决.md`。

## 0CZ. 2026-08-21 CEB 已覆盖流式无未来反馈；temporal escrow 只作完整性贡献

一手原文复核发现，[Critic Experience Bank](https://arxiv.org/abs/2607.12397) 已明确在 action 执行前输出
confidence，按 stream order 处理 frozen actions，并在整条 trajectory 评分后才把反馈加入 bank，以阻断 future
feedback；还做了 selective execution。其累计曲线平均 5 个 random stream orders。因此“执行前 critic”“流式无
未来反馈”“冻结 critic + 历史执行经验”“选择性执行”均不得再申方法 novelty。

我方仍保留的窄差异是验证合同而非算法首创：scorer 在远端 activation 前冻结；只接收真实
`generation_started_at_utc` 严格晚于 activation 的新 physical runs；单位为自然 same-parent MLE programs；连续
标签来自 pristine evaluator；prediction 先 append-only 托管，再等 outcome vault；同时强制 parent coverage、
endpoint/run/code closure、source novelty、syscall 零接触和独立重建。CEB 则在已收集 action substrate 上按随机
stream orders 回放，并让 retrieval bank 随轨迹增长。

所以 0CP future escrow 继续，因它仍是 0CN retrospective candidate 的唯一可信 out-of-time 检验；但即使未来
positive，也只能写 prospectively escrowed MLE-domain evidence / benchmark integrity，不能写 novel temporal
critic protocol。AIRA_2 的 HCE 又进一步关闭“外部隐藏评估”宽 novelty。当前不向已激活 cohort 偷加 CEB memory
arm。直接记录：

- `phase1/实验记录/2026-08-21/TemporalEscrow_CEB直接先例与Novelty边界.md`。

## 0CY. 2026-08-21 source retention 的 run-cluster 压力测试支持不足

commit `fa5d65507bd6bab76b7bfaeda04584fae21b78c9` 对 0CX 做了结果后、明确标注的 cluster 强度攻击：
先在 `(role,task,physical-run)` 内平均 parents，再让 runs 等权；推断原定为 task×run hierarchical bootstrap。
固定的 v1 15-task universe 中只有 9 个任务达到 train≥5、frozen≥3 distinct runs，低于预注册至少 10 个任务，
故正式状态为 `INSUFFICIENT_RUN_CLUSTER_TASK_SUPPORT`，不能宣称 run-cluster robust，也不得结果后降门追救。

支持合格的九任务 run-equal train→frozen Spearman rho=`0.7`，train-defined tertile 的 frozen
high-minus-low=`0.1973544973544974`，方向没有反转；但这两项只作描述性证据。冻结程序在支持门失败后没有运行
permutation、hierarchical bootstrap 或 LOTO，因此不能声称显著。6 个未过门任务中 5 个只有 1–2 个 frozen
physical runs，另一个 train 只有 3 个 runs；瓶颈是 frozen run 支持而非 parent 行数。

因此 0CX 的 parent-equal task-conditioned transport 仍按原结果前协议成立，但正文必须附上本轮 limitation，不能
升级为 cluster-robust。唯一干净解锁方式是等待自然新增、outcome-blind 的 frozen-role physical runs，在新 temporal
escrow 中独立确认；不得按本轮数值挑任务或改门。producer×2/verifier×2 一致，focused=`5 passed`，完整
phase tests=`632 passed, 25 warnings`，独立重建差、forbidden path 与秘密扫描均为 0，正式产物只读。

直接证据：

- `phase1/results/source_retention_run_cluster_v1_20260821_fa5d655/README.md`；
- `phase1/实验记录/2026-08-21/SourceRetention_RunClusterRobustness_v1_正式裁决.md`。

## 0CX. 2026-08-21 source retention 的任务结构跨 disjoint-run roles 正式复现

commit `d21166fb344c0645ed1e31ea6bc7e7487e441e6f` 在既有 3,252-parent source completeness 表上完成
结果前冻结的 train→frozen transport audit。15 个事前支持合格任务（train parents≥30、frozen parents≥15）
中，task-equal finite source-retention profile 的 Spearman rho=`0.8151043256715026`，100,000 次双侧置换
`p=0.0005999940000599994`，20,000 次 paired-task bootstrap 95% CI=
`[0.5368038356525456,0.9594112875401973]`。15 个 leave-one-task-out rho 全正，最小=
`0.779067271041392`；parent-present-only sensitivity rho=`0.8295238095238096`。train 定义的 top/bottom
tertiles 在 frozen 上 task-equal retention 相差 `+0.21714885427161656`。全部六个预注册门通过，正式状态为
`VERIFIED_TASK_CONDITIONED_SOURCE_RETENTION_TRANSPORT`。

因此可新增一个严格正面的数据结论：当前发布管线的 source retention 不是跨任务可交换的单一缺失率，而是能在
物理 run 无交集的 train/frozen roles 间复现的 task-conditioned profile。结合 902 个已恢复 missing statuses 中
893 个为 execution error，可把论文资源主张收紧为 **failure-censored、task-stratified MLE decision corpus**，并要求
benchmark 按任务同时报告 retention/coverage；这不是 predictor 方法收益。

producer×2 与不 import producer 的 verifier×2 逐字节一致，独立重建差为 0；focused=`6 passed`，完整
phase tests=`627 passed, 25 warnings`，forbidden scientific path、文件名/内容秘密扫描均为 0，正式产物只读。
首次 commit `6739948...` 只因 `/tmp` runner 未设置 worktree `PYTHONPATH` 在 module import 前失败，没有
summary 或科学结果；失败目录保留。正式运行不读取 code、分数大小、pair orientation、prospective outcome，
GPU/API/base-LLM update 均为 0。

仍禁止 missing-at-random、task 因果效应、完整 choice set、缺失数值 outcome、predictor/search utility、跨 agent
迁移及 first/only。该结果强化 Decision Corpus / D&B 主线，不改变 strict-future transition escrow、first-960/
closure 或 clean Qwen G0/G1 预算门。直接证据：

- `phase1/results/source_retention_transport_v1_20260821_d21166f/README.md`；
- `phase1/实验记录/2026-08-21/SourceRetentionTransport_v1_正式裁决.md`。

## 0CW. 2026-08-21 source-aware 六项证据索引正式通过

commit `8da197b89ebe513df0516cf71186c068078bf67b` 的 v2 evidence index 已完成双 builder、双独立 verifier 与
全套测试，正式状态为 `INDEPENDENTLY_VERIFIED_SOURCE_AWARE_EVIDENCE_INDEX`。它把 v1 五项扩为六个互异
estimands：decision corpus、source opportunity、label repeatability、normalized clone、deployment cost、
prospective gate；共绑定 18 份 artifact 与 136 个 JSON assertions。index normalized SHA-256=
`fdb77b4458c4342a0fa62c860ed7141478e38a1dc5c26ac369e70ba961ff5c02`。

新增正资产是 source-aware release contract：870 个 source-incomplete parents 中 721 个可精确恢复 missing
identity（rate=`0.828735632183908`）；996 个 missing identities 中 902 个恢复 journal status
（rate=`0.9056224899598394`），其中 893 个 execution error、9 个 official grade absent，94 个仍 unknown。
因此允许主张 labeled sibling fragment + high-coverage parent-linked missing identity/status registry；完整 source
choice set、MAR、missing numeric outcome 与 censor-aware utility 仍明确禁止。全套测试=`620 passed, 1 skipped,
25 warnings`，秘密扫描 0，prospective outcome read=0；本地与 Linux verifier 逐字节一致。

该结果强化 D&B 数据/审计容器，不是 predictor 方法或 prospective effect。first-960/closure、strict-future
transition escrow 与 clean Qwen G0/G1 预算门均不改变。直接证据：

- `phase1/results/decision_corpus_evidence_index_v2_20260821/README.md`；
- `phase1/实验记录/2026-08-21/DecisionCorpusEvidenceIndex_v2_正式裁决.md`。

## 0CV. 2026-08-21 G0 共享 Pro6000 调度资格通过；容量与精确预算仍待

0CH 的“当前账号无 Pro6000 QoS”已被更精确的只读审计取代：`projgpu39` 同时属于共享 `gpu_24h`，该
partition 允许当前账号已有的 `gpu` QoS。原失败还混入节点 Slurm memory=`1M` 与模板 `--mem=128G` 的资源
不相容。共享模板固定 `gpu_24h/gpu`、12 CPU、`mem=0`，其余 Qwen3-1.7B/2×PRO6000/16K/seed6/10-step/
train-dev-only 科学矩阵和全部输入哈希不变。

commit `a99bf8a...` 的正式隔离审计为 focused 11 passed、全部 phase 616 passed / 25 warnings；
`sbatch --test-only` 返回虚拟 job `11321`，随后 ID 查询失败且当前用户 queue before/after/diff 都为空，故真实
jobs/GPU/API/test reads/outcomes 仍全为 0。共享 association 与资源白名单已写进 preflight，漂移即拒绝。当前
两张卡被另一用户占用到调度器估计的 `2026-08-22T18:22:07`；更重要的是，实际 G0 的精确上限仍未获用户批准：
1 run、2 GPUs、2 小时、最多 4 GPU·h。因此状态是
`SHARED_SCHEDULER_ELIGIBLE_CAPACITY_AND_BUDGET_PENDING`，不得把资格检查当提交授权。直接证据：

- `phase1/results/critic_component_g0_shared_scheduler_20260821_a99bf8a/README.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_G0共享调度资格与预算门.md`。

## 0CU. 2026-08-21 M-DESIGN 关闭 edit-gain 方法 novelty；开放式决策资源边界保留

新增的一手查重发现，[M-DESIGN](https://arxiv.org/abs/2507.15336) 已被 ICML 2026 接收，并在 22 个图数据集、
67,760 个 GNN 模型上构造 modification-gain graph，用一跳 edit-effect、动态任务相似度与 predictive planner
指导后续模型修改；官方实现和知识库均已发布。因此不得再声称首次提出修改--增益图、父子 edit predictor、
跨任务修改收益复用或用预测 gain 指导 AutoML 搜索；当前 68 维 transition arm 即使 strict-future 为正，也只是
已知 edit-effect 思路在自然 MLE-agent 决策上的迁移检验，不是方法首创。

仍可守的正面差异是测量与资源：我方单位为开放式 Python code、真实 physical run 中自然同-parent sibling、
pristine execution score、source/failure/missing registry、run/exact-config/component closure、gap/regrade noise、
query/init/execution cost 与 outcome-before-prediction 的严格时间外托管；M-DESIGN 则是固定结构化 GNN design
space 与可重复查询模型库。这个直接先例强化 NAS-Bench-style 叙事，但把贡献严格限定为开放式 MLE deployment
distribution 的可审计数据实例与压力测试。不得在已见 5,240 pairs 上修改 transition 特征/模型追救；下一效果线
仍只有 clean Qwen scaling 和已冻结 strict-future transport。直接记录：

- `phase1/实验记录/2026-08-21/M-DESIGN修改增益图_防Scoop与正面边界.md`。

## 0CT. 2026-08-21 strict-future 连续安全摄取 monitor 已激活

为避免新 senior archives 到达后只被 metadata monitor 发现而没有进入前瞻快照，commit
`c06222fc00a3af898c5637fdb74cff85505a6505` 新增连续摄取 monitor。它不改变 scientific runner：仍精确使用
`90842c49dbd73d41d405a5ecdad2224ee447b375`，绑定 0814--0819 全部结构拒收 registry，含 Plant 0819
registry SHA=`0dc58a4f2b2770f615b4ebf6d077c25ec7866d0f0ad72a2cc2f312d8d4f1d503`。固定每 300 秒观察、145 polls；
archive 至少 21,600 秒 age、三次 observation、间隔至少 300 秒且 stable span 至少 600 秒才可进入
credential-first intake。未知结构/身份异常立即 fail closed；env/live-event member、outcome 与 label vault 不读。

本地/集群脚本 SHA-256 都是 `79f7f40ab5a2a030e103bc374f368efe64498fb1b96dd0a790dc66c6d9c34138`，相关
测试 19/19 通过。正式首轮为 `archives=183, baseline=128, ready=0, rejected=6, transactions=49,
outcomes_read=false`；PID=`1271112`，日志为
`/research/d7/spc/yzyang4/prospective_decision_v1/logs/continuous_intake_monitor_20260821.log`。它只做 CPU
append-only 摄取，GPU/API/base-LLM update=0；已有 transition escrow monitor 会在 `LATEST` 变化后追加冻结预测。

直接回执：`phase1/results/prospective_continuous_intake_monitor_20260821_c06222f/README.md`。

## 0CS. 2026-08-21 Meta Kaggle exact-parent human-fork S0b 身份门失败；路线关闭

0CQ 的 TraceML join 失败不否定 human-fork estimand，但公开 TraceML 已经覆盖 human trajectory/fork graph，故新路线
不能再主张“首个 human fork 数据集”。保留的窄突破候选是：从官方每日 Meta Kaggle snapshot 直接用
`Kernels.ForkParentKernelVersionId` 恢复精确 fork parent，并要求 child first-version 的
`KernelVersions.ParentScriptVersionId` 一致；`KernelVersionKernelSources` 只代表 notebook input dependency，明确禁止
把它当 fork edge。若 exact-parent sibling 支持过门，再另立结果盲 S1，测试冻结 AIRA transition scorer 或轻量
human-fork scorer 能否预测外部 hidden private outcome；即使为正也只是 cross-domain transfer extension，不替代
0CP strict-future AIRA 主线。

S0a 只下载并 SHA 绑定 `Kernels.csv`、`KernelVersions.csv`、`Submissions.csv`，连同已绑定的 Competitions 与两个
source-link tables；只读 header，不打开 submission score rows。S0b 只读 fork/version/competition identity，要求
direct-parent 一致率≥0.95，并在 fixed one-pair-per-parent 后有 pairs≥500、parents≥100、completed competitions≥20、
dominant competition≤0.20。任一门失败即关闭；过门也必须在读取 `Submissions` 任何 data row 或 notebook code 前另立
S1。新增下载约 7.3GB，CPU/network-only、GPU/API=0。直接协议：

第一次 acquisition attempt 在新表下载前因 Kaggle CLI 清单 CRLF 与逐字节 metadata guard 不兼容而 fail closed；
只产生公开 listing/metadata receipt，CSV data rows=0。重试只保留 raw 清单并生成去 `\r` 的 normalized 副本做
固定行与 before/after 比较，所有科学输入、关系定义、门槛和 snapshot 不变；新 receipt 目录与旧 attempt 分离。

修正后 S0a 正式通过：下载前后 raw/normalized listing 分别 byte-identical，六张 CSV 共 8,216,765,816 bytes 与
metadata 全部 SHA 绑定，required headers 完整；receipt 两类秘密扫描为 0。outcome table 仍只读 header、data rows=0。

commit `64ec81945b19f232968391a0b10d0772b9895641` 的 S0b producer×2 与不 import producer 的 verifier×2
已经完成，双方各自 byte-identical；focused=`7 passed`、全部 phase tests=`611 passed, 25 warnings`，formal
manifest、只读、forbidden-path、network 与秘密扫描全过。正式状态是 `IDENTITY_UNAVAILABLE`：1,946,556 条
Kernels 中有 391,175 explicit-fork rows，748 malformed 后的 390,427 条 parsed edges 全部无法让 child
`FirstKernelVersionId` row 的 `ParentScriptVersionId` 与 `ForkParentKernelVersionId` 一致，agreement=`0.0`；
362,922 条 child first-version 也不是 VersionNumber 1，580,333 个所需 version IDs 中缺 42,361 个。因此
base-valid edges、parents 与 canonical pairs 都是 0，S1/S2 按原门禁止执行。

这只说明公开、过滤后的 Meta Kaggle snapshot 不能识别冻结的 dual-field exact-parent estimand；不说明 human-fork
future potential 不存在。不得结果后删除一致性门、使用 dependency table 代理 fork、筛联结成功子集或打开 private
score/code 追救。S0b outcome rows/code/model fit/GPU/API 仍全为 0。直接证据：

第一次 S0b formal attempt 在 worktree materialization 阶段因无关历史 LFS pointer 的 server object 404 停止；
tests 和真实 CSV rows 均未开始。重试只按既有正式 runner 增加 `GIT_LFS_SKIP_SMUDGE=1`，不改 source blobs、输入、
关系定义、门槛或输出协议，旧 partial worktree 不复用。

- `phase1/meta_kaggle_exact_parent_s0a_input_manifest.json`；
- `phase1/results/meta_kaggle_exact_parent_s0a_20260821_1211700/README.md`；
- `phase1/实验记录/2026-08-21/MetaKaggleHumanForkExactParent_S0a正式裁决与S0b实现预检.md`。

- `phase1/results/meta_kaggle_exact_parent_s0b_20260821_64ec819/README.md`；
- `phase1/实验记录/2026-08-21/MetaKaggleHumanForkExactParent_S0b正式裁决与路线关闭.md`。

- `phase1/meta_kaggle_exact_parent_s0_protocol_v1.json`；
- `phase1/实验记录/2026-08-21/MetaKaggleHumanForkExactParent_S0预注册与输入绑定.md`。

## 0CR. 2026-08-21 真实 batch 身份恢复 S0 正式裁决：支持规模通过，provenance 身份不可用

commit `a466888246ec606816486c164fbf24b7e4da7114` 的 V3 producer×2 与不 import producer 的 verifier×2
均完成并 byte-identical；13 个 focused tests、604 个 phase tests、完整 manifest、只读与秘密扫描全部通过。
正式状态是 `IDENTITY_UNAVAILABLE`，因此 S1 train-only 效果阶段禁止执行；没有读取 grade、pair orientation、code
或 frozen-test 效果，GPU/API/model fit=0。

146 个固定归档含 675 个 checkpoint journal headers。676 个匿名 runs 中 636 个唯一连接、32 个多 batch 歧义、
8 个缺失；13,520 个 pair 中 1,058 个因 endpoint 身份不完整而不可识别。身份完整部分 cross-true-batch=0、task
mismatch=0，但协议禁止结果后过滤。两个 source archive 也被原门拒绝。8 个 missing runs 全属 leaf；0811/0812
的 leaf tar 分别与同日 tabular tar 逐字节相同，header 实际也是 tabular runs。32 个 ambiguous runs 来自完整 run
basename 跨归档/日期复用，launch date 不能唯一恢复 source batch。解锁必须由学长发布不可变的
`run_id -> source-date,batch-id` provenance manifest、修正 leaf tar，并给出两个异常 tabular tar 的规范替代；不得
用 config/date/family 代理猜测。

正面结构事实是九项**支持规模门全部通过**：描述性 experiment-closed train=6,885 pairs/80 experiments，dev=
1,429 pairs/17 experiments，15 tasks，dominant dev share=0.135759，12 个 dev tasks 各有至少 20 pairs，train/dev
experiment overlap=0。原始 test 的 87 个 experiments 中 49 个与 train role、11 个与 dev role 重叠，说明旧 run
split 不等于 experiment-closed split；这不是标签泄漏指控，也不能替代身份门。直接证据：

- `phase1/results/senior_augmented_true_batch_identity_support_20260821_a466888/README.md`；
- `phase1/实验记录/2026-08-21/SeniorAugmented真实Batch身份恢复_S0正式裁决与Source修复清单.md`。

### 工程纠错链（保留）

为判断学长 augmented scaling 是否能接受真正的 experiment-closed train-only 复核，新增一个 outcome-blind S0：
从学长固定 commit 的 21 个 source 日期目录中只流式读取 tar header path，不提取、不读取任何 member payload，
把匿名 run ID 精确连接到原 producer 使用的 `(source-date, batch-directory)`。旧 pair 文件没有 batch path，过去的
same-family/date 只能支持 `LIKELY`；本轮禁止继续用它或 config 代理。

S0 必须同时满足所有 run 唯一命中、所有 pair 同真实 batch、archive/path 错误为 0、原始 test 不参与角色分配，
并由固定 task-stratified 20% batch dev 规则获得 dev≥400、≥8 tasks、dominant≤0.35、≥6 个 task 各有 20 pairs、
train≥2,000 与 train/dev experiment 零交集，才允许另立 train-only CPU 效果预注册。否则按身份或支持失败关闭，
不得修改来源目录、batch 定义、hash domain、切分比例或阈值追救。当前未读取 grade/orientation/code/frozen-test
效果，GPU/API/model fit=0。直接协议：

第一次正式尝试 `7f01946...` 在 producer 1 后因解析缺陷停止，未运行 verifier、未进入效果：正则第一组实际只
捕获 `_seed_...` 之前的 batch 前缀，却被实现当成完整 source run basename，因而产生伪造的 676/676 missing。
V1 同时暴露两个 source archive scan errors；header 复核存在原协议明确拒绝的 link 类成员，因此 V2 不放宽 archive
门、不缩小 inventory。V2 在任何有效支持结果前只把第一组纠正为完整 `..._seed_N_id_HASH` basename，并新增
producer/verifier 真实路径反例。日期、输入、batch 定义、split/hash/20% 规则和所有阈值均未改变。
同时让独立 verifier 对被拒绝归档重建规范错误行，而不是先于身份裁决退出；错误仍计入原门且绝不忽略。

`a70232a...` 的 V2 producer 两遍已一致并产生非零结构支持，但 verifier 在成功重建 rejected archive 错误行后，
仍对该错误行访问 `run_batches`，以 `KeyError` 退出；故 V2 没有正式科学裁决、未进入效果。V3 在再次正式运行前
只加固 verifier：rejected rows 留在 error gate 但不进入 join；独立逐字段重建整份 summary；显式绑定 source
commit，并加入失败注入。已看到的 V2 outcome-blind 结构数已披露，但 V3 不改变任何日期、输入、identity/batch/
split/阈值规则；V3 双 verifier 已完成，正式裁决以上述结果为准。

- `phase1/实验记录/2026-08-21/SeniorAugmented真实Batch身份恢复_S0预注册.md`。

## 0CQ. 2026-08-21 TraceML human-fork S1 identity 门失败；该外部路线关闭

在不改变 0CP AIRA strict-future 主线的前提下，新增一个外部 extension：只用 TraceML 固定 revision 的 human
canonical `fork` siblings，测试冻结 transition scorer 能否从 fork 起点判断哪个 child kernel 最终取得更好的
best-private score。它对应“node may lead to a better solution”，但 human forks 不是 agent search candidates；即使
为正也只能称 cross-domain human-fork future-potential transfer。

协议在 graph support、score 值和 raw notebook 内容读取前冻结。S0 先绑定 graph SHA/schema；S1 必须通过
task-unseen≥20、parents≥100、finite non-tie eventual pairs≥500、dominant≤0.20 与 identity/depth 门；不过门则不下载
2.9GB raw code。S2 才做 credential 隔离、code-cell-only 转换和三套 exact-code overlap；S3 才用 `7458f09...`
scorer 一次性评分。禁止重训、调参、改标签/子集或把外部结果回填 0CP。GPU/API=0。直接协议：

S0 已在预注册后完成：固定 revision HEAD 与 9 个文件 SHA 绑定，Parquet 仅读 schema/footer，required fields 全部
存在，raw archive 未下载。footer 为 174,558 nodes / 3,995,719 edges / 2,721 trees / 4,847 kernels；尚未计算
fork/support 数。发现 card 的 134 competitions 与固定 manifest 的 141 entries 不一致；S1 必须逐 graph comp 做唯一
direction join 并报告 unused entries，不能按 card 猜测裁剪。S0 状态为
`S0_PASS_WITH_MANIFEST_CARD_COUNT_DISCREPANCY_REQUIRING_S1_CHECK`。

S1 已从精确 commit=`bae0802895214851983fa99eee784e651648d384` 正式运行并由不 import producer 的实现独立
重建。两次 producer 与两次 verifier 分别 byte-identical，focused=9 passed、全部 phase tests=591 passed / 25
warnings，52-entry manifest、forbidden-path、credential、权限门均通过。正式状态是
`IDENTITY_OR_JOIN_AMBIGUOUS`：134 个 graph competitions 都能唯一匹配 141-entry manifest（7 个 unused entries
精确列出），但 174,558 nodes 中有 4,674 个 node→kernel same-comp join mismatch、906 个 node→tree same-comp
join mismatch；409 个 canonical fork 中另有 6 个 parent/child tree-comp mismatch，只有 403 个通过局部结构。
因此 `identity_and_direction=false`，按预注册没有打开 `best_private_score`/`score_public`，support/effect 均为空，
2.9GB raw archive 未下载，S2/S3 永久不执行。不得事后过滤 6 个 fork、忽略全图 join 或改 gate 追救。

官方固定 builder 本身没有在 materialization 时断言 node/kernel comp 一致，并把 weak component 的 tree comp 取自
primary root；这能解释错误为何可进入公开 parquet，但不能把 join 变成可识别 estimand。此结果只作为外部数据审计
失败案例保留，不构成方法负结论，也不回填 0CP AIRA strict-future 托管。正式 producer RSS=455,716KB，高于预估
<100MB，实际仍为只读 CPU、GPU/API=0；该资源估计偏差已如实记录。

- `phase1/traceml_human_fork_future_protocol_v1.json`；
- `phase1/traceml_human_fork_s0_input_manifest.json`；
- `phase1/results/traceml_human_fork_s1_20260821_bae0802/README.md`；
- `phase1/实验记录/2026-08-21/TraceMLHumanForkFuture_S1正式裁决.md`。

## 0CP. 2026-08-21 transition future escrow 已正式激活；只等待严格未来新 runs

冻结 scorer 已从 source commit `7458f0969b92a258ea0e495bbbee282aa12b748e` 正式激活，自动远端时间边界为
`2026-08-21T07:05:03.916471Z`。model producer×2/verifier×2、activation×1/verifier×2、initial escrow
producer×2/verifier×2 与 prior append replay producer/verifier 全部通过；17 个阶段 rc 均为 0，训练 reference 与
future margin 的独立复算最大差均为 0.0，1,665 个既有 pair 在 append replay 中逐字段完全存活。23 个 focused
tests 与 582 个 phase tests 通过；prospective forbidden-path syscall hits=0，三类 credential scan=0，226-entry
manifest 全验，正式目录 writable files=0。

初始 snapshot=`83ab1d6...d5c047` 的 1,665 pairs 全部早于 activation，因此 support-only=1,665、strict=0、
eligible=0，状态按协议为 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`。这是正确的初始状态，不是效果失败；
本轮读取 prospective outcome=0、effect metrics=0、GPU/API=0。只有 generation start **严格晚于**上述时间边界的
新 physical runs 才能进入 future cohort，且仍须通过 1,500 pairs / 150 runs / 15 tasks / dominant≤0.25 /
parent coverage≥0.80 与三类 source-overlap 零门后才可揭盲。

更早 source commit `921769f...` 的 attempt 永久标记为
`INVALID_FORBIDDEN_METADATA_CONTACT_NOT_PROMOTED`：其科学复算虽返回 0，但五处 source binding 的全仓库
`git status` 在 trace 中产生 80 次 `.env`/regrade/score 路径元数据接触；没有读取文件内容或效果值，但已违反零接触
契约，故无 conclusion、无 COMPLETE、旧 activation 不使用。新 commit 只核对协议登记 source blobs，并由新增
反例测试与正式 trace=0 共同验证。直接证据：

- `phase1/results/transition_future_escrow_20260821_7458f09/README.md`；
- `phase1/实验记录/2026-08-21/TreeTransitionFutureEscrow_正式激活与初始托管.md`；
- 远端只读全量产物 `/research/d7/spc/yzyang4/transition-future-escrow/7458f09-v1`。

## 0CO. 2026-08-21 transition future escrow 支持审计完成，当前无可揭盲 future 样本

0CN 的接近门槛信号只允许原样冻结为 outcome-blind extension。commit `4b6b997...` 的 producer×2 与不 import
producer 的 verifier×2 已在 frozen snapshot `83ab1d6...d5c047` 上逐字段一致。249 runs / 6,471 cards /
1,665 sibling pairs 中，1,412 pairs 有同 run 父代码，coverage=`0.848048048048048`；其中 1,134 pairs 对实际
train+dev 模型闭包满足 endpoint ID、physical run、三张代码 SHA 均无重叠。最大 covered-pair task share=
`0.18838526912181303`。这证明结构与任务分布足以支持未来设计，但不是未来效果样本。

整个 current support 仍有 579 card IDs / 579 code SHAs 落入模型实际使用的 5,612-card 闭包，run overlap=0，
因此正式状态为 `CURRENT_SUPPORT_NOT_SOURCE_INDEPENDENT`。早先把当前 6,471 cards 对整个 31,742-card 容器比较
得到的 2,330/2,321 不是模型使用口径，已被正式审计取代。当前 snapshot 全部早于未来 activation，strict future
inventory 仍为 0；effect metrics、vault/score registry 读取与 API/GPU 均为 0，current support 永久只作工程
支持，不得混入 future effect validation。

已冻结的未来协议要求：实现 commit 后自动 activation；只接收 generation-start 严格晚于 activation 的 run；
full-fit 三臂和全部参数沿用 `e8eb25c...`，primary 仅 combined−child；先锁 predictions，再等既有 first-960+
closure。严格支持门为 1,500 parent-covered/source-novel pairs、150 runs、15 tasks、dominant≤0.25、parent
coverage≥0.80；训练/future endpoint/run/code overlap 必须逐 pair 为 0。未来只有 paired run/task/parent 三类 CI
全部>0、combined chance CI 全部>0.5 与 LOTO 全正才允许 positive。当前尚未激活，outcome vault 未读，
GPU/API=0。支持审计 10 个 focused tests 与 574 个 phase tests 通过，syscall 禁止路径与凭据扫描均为 0；封存
wrapper 的零匹配 `grep`/`pipefail` erratum 已原样保留，发生于四次科学计算结束后且未重跑结果。直接证据：

- `phase1/results/transition_future_support_audit_20260821_4b6b997/README.md`；
- `phase1/实验记录/2026-08-21/TreeTransitionFutureEscrow_当前支持独立性正式审计.md`；
- `phase1/实验记录/2026-08-21/TreeTransitionFutureEscrow_冻结扩展预注册.md`。

## 0CN. 2026-08-21 parent-relative transition OOF：方向良好但正式 no-unlock

结果前冻结的 68 维 child+transition arm 已完成 5,240-pair、28-task、152-parent-closed-supercomponent OOF。
merged task-macro 从 0.529716 到 0.546841，paired delta=+0.017125，task CI=
[-0.000013,+0.035410]；pair delta=+0.011832，parent CI=[-0.003403,+0.027366]。canonical Improve
task delta=+0.036159，task CI=[+0.003552,+0.069032]，但 parent delta=+0.023973 的 CI=
[-0.001487,+0.049611]；Draft delta 较小且两类 CI 均跨 0。merged 28 个 LOTO 点估计全正且 combined
chance gate 全过，但冻结的 paired task+parent 双门未全过，正式状态为
`NO_ROBUST_TRANSITION_GAIN_VERIFIED`，`positive_claim_allowed=false`。

四次 full refit 逐字段一致，51-entry manifest、11 个空 diff/stderr、568 个 phase tests、权限与安全门全过。
因此可以诚实称“父相对 edit-shape 给出接近门槛、跨任务方向一致的 future-validation candidate”，不能称稳健方法
突破。禁止在同一 5,240 pairs 上改 features/model/门追救。唯一可保留的正向动作是另立结果盲协议，把当前 arm
原样锁定为 future scorer escrow extension；不得改变 first-960 primary 或回填本次正式裁决。直接证据：

- `phase1/results/critic_transition_static_oof_20260821_e8eb25c/README.md`；
- `phase1/实验记录/2026-08-21/TreeTransitionStatic_父相对编辑表征_正式裁决.md`。

## 0CM. 2026-08-21 静态信号来源 parent-closed OOF 正式裁决

0CK 的 5,240-pair / 28-task / 152-supercomponent 正式运行已完成。producer×2 与不 import producer 的
full-refit verifier×2 精确一致，40-entry manifest 全过、7 个 diff/stderr 为空、目录不可写；focused/phase
tests 为 8/558 passed，安全扫描为 0。正式状态是
`STATIC_SOURCE_OOF_INDEPENDENTLY_VERIFIED_NO_NARROW_POSITIVE`。

code-only task-macro=0.529716，task CI=[0.497905,0.566335]；parent point=0.520420，parent
CI=[0.503049,0.537910]。code−lineage 的 task/parent paired delta 为 +0.008391/+0.014790，CI 分别
[-0.031204,+0.047777]/[-0.008262,+0.037835]，LOTO 最小点估计 −0.003203。code−all 的 task/parent
delta 为 −0.004693/−0.008015，CI 分别 [-0.018386,+0.011119]/[-0.020497,+0.004262]；冻结的非劣门也失败。
因此不能声称 code-only 信号独立于 lineage shortcut，也不得把旧同池静态结果解释成代码理解。

all-static 的 task/parent chance CI 下界仍高于 0.5，只支持“parent closure 后仍有弱联合静态信号”的描述，
不识别其来源。该审计作为 Predictor Benchmark 的诚实 ablation 保留，并关闭同一语料上的 code/lineage 追调。
读取结果前已冻结的 `TreeTransitionStatic` 仍可按其独立 Draft/Improve 门执行一次；失败即关闭手工 transition
特征。直接证据：

- `phase1/results/critic_static_source_oof_20260821_208e381/README.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_静态信号来源_componentOOF_v2正式裁决.md`。

## 0CL. 2026-08-21 Draft 父上下文重叠已独立确认

结果盲结构预检发现的 split-unit 问题已经从 commit=`ecb81cdf730961bd01799faeeb0bd60281537984`
完成 producer×2 与不 import producer 的 verifier×2。四次重建确定性一致，5 个合成/反例测试通过，封存
manifest 31/31 通过且目录不可写。固定 component split 的 outer-train/test **endpoint-run overlap=0**，但有
80 个共享 `(task,parent)` 上下文，影响 outer-train 1,917 rows 与 test 305 rows；把 parent card run 计入上下文
后 run overlap=80，受影响 endpoints 的 exact-code overlap 仍为 0。

该问题严格局限于 synthetic cross-run Draft：305 个受影响 test rows 全为 Draft，占 Draft test 305/314；
Improve/canonical raw sibling 的 shared parents=0。由此允许的正面 D&B 结论是：**cross-run pair construction
can defeat an endpoint-run split by reusing ancestor context**。不得笼统称整个 sibling test 泄漏，也不得由结构
重叠推断 static champion 高分的因果来源。旧 Draft 数字改标 parent-context-overlap extension；Improve 不撤回；
未来 parent-novel Draft 必须按 relational parent closure 切分，parent-reuse deployment 必须单列 estimand。

直接证据：

- `phase1/results/component_parent_context_audit_20260821_ecb81cd/README.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_Draft父上下文重叠_发现与复核计划.md`。

## 0CK. 2026-08-21 静态信号来源 component-OOF 审计已冻结（已由 0CM 裁决）

0CJ 只证明 code+lineage 的 pooled/task-conditioned GBM 在已见 component test 上略高于 chance；尚不能排除
该信号主要来自 `depth/step/n_siblings` 搜索位置捷径。为避免再次查看 frozen test，已在任何新 OOF margin 前
冻结一个只用 outer-train train+dev=5,240 pairs、28 tasks 的 5-fold OOF 来源审计。结果盲结构预检发现原 168
个 pair components 虽然 endpoint/run 不交叉，却有 16 个 `(task,parent)` 跨 component；v1 因而在任何模型 fit
前关闭。v2 不删 row，而是把共享 parent 的 components 传递闭包为 152 个 parent-closed supercomponents，再以
它们为不可分 fold unit。固定比较相同 pooled GBM 的 `code-only` 31 维、`lineage-only` 3 维和 `all-static` 34
维；不输入
task ID、不调参、不选 champion、不读 test/TF-IDF/semantic/prospective outcome。

窄正面门同时要求 code arm 的 task/parent chance CI 下界>0.5、code−lineage 两类 paired CI 下界>0、
code−all 两类 CI 下界≥−0.01、任一 task 删除后 code−lineage task-macro delta 仍>0，以及 random/orientation、
component isolation、反对称和 producer×2/verifier×2 全过。即使通过，也只能说明已观察 static signal 不可由
三个 lineage 特征解释，不得申“理解代码”、因果机制、frozen/prospective/search gain 或方法 novelty。正式运行从
精确 commit=`208e38135c0dc10d8430095a41c8008c063ff8a0` 启动；结果前状态曾为
`STATIC_SOURCE_PARENT_CLOSED_OOF_FORMAL_RUN_IN_PROGRESS_NO_OUTCOME_READ`。正式结果与边界已由 0CM 覆盖。
CPU-only、0 GPU·h、0 API。直接协议：

- `phase1/实验记录/2026-08-21/CleanDirectDecision_静态信号来源_componentOOF_预注册.md`。
- `phase1/实验记录/2026-08-21/CleanDirectDecision_静态信号来源_componentOOF_v1结构失败与v2修订.md`。

## 0CJ. 2026-08-21 Component 同池静态 suite：便宜结构信号可学，但不强于 TF-IDF

结果前冻结的 component train/dev/test=`4689/551/931` CPU-only suite 已完成 producer×2 与不 import
producer 的 full-refit verifier×2。dev task-macro 唯一选择 `static_gbm_task`；其 retrospective test micro=
`0.560687432867884`、task macro=`0.5585685275472433`，task-clustered 95% CI=
`[0.500809682553181,0.6176416031350442]`、parent-clustered CI=
`[0.5228966986155484,0.5984075062159282]`，覆盖 931/931、ties=0。pooled GBM 也同时通过两个 chance gate；
这支持“冻结同池中存在可由廉价 code/lineage 特征学到的信号”，但它是 retrospective benchmark baseline，
不证明 task-unseen 泛化、时间外确认、search utility 或方法 novelty。

预注册的强主张门失败。champion 相对固定同池 TF-IDF 的 pair-micro delta=
`-0.010741138560687433`，parent-clustered CI=`[-0.06271933251042952,0.04004332013926007]`；task-macro
delta=`-0.01722973871137726`，task-clustered CI=`[-0.11177361183157879,0.09201062529949726]`。Draft
delta=`+0.050955414012738856`，Improve delta=`-0.04213938411669368`，且每个 leave-one-task-out 点估计
都为负。因此禁止写“静态可解释特征稳定强于字符文本”，也不得在已见 test 上追调；正式状态为
`STATIC_SUITE_INDEPENDENTLY_VERIFIED_NO_STRONG_ADVANTAGE`。

独立 verifier 的逐 pair、task、parent 与 summary 最大绝对差均为 0.0；两次 producer、两次 verifier
均 byte-identical。封存清单 35/35 哈希通过且文件集合精确，六个 diff/stderr 均为 0 bytes，目录 mode=555、
可写文件=0、安全扫描=0；显式单线程后验全回归为 550 passed / 25 warnings。该结果只补齐 Predictor Benchmark
的 cheap structured baseline；first-960/closure、WL extension、outcome vault 与 G0/G1 资格门均不变。直接证据：

- `phase1/results/critic_component_static_suite_20260821_76c1b49/README.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_component同池静态suite_正式裁决.md`。

## 0CI. 2026-08-21 Component 同池静态 suite 结果前冻结（已由 0CJ 裁决）

在任何新 static prediction/test metric 前，已冻结 component train/dev/test=`4689/551/931` 的 CPU-only suite：
六个单特征负载、pooled static-LR/GBM，以及只对已见 task 有效的 task-interaction LR/conditioned GBM。所有特征
只来自候选 code 与 decision-time lineage `depth/step/n_siblings`；明确禁止 `obs`、grade、gap、self-report、
runtime、stdout、`parent_val` 和 held-out fit。线性 margin 丢弃截距；GBM 固定用
`0.5*(decision(d,task)-decision(-d,task))`，先天保证 order antisymmetry。

四个 learned arms 全部报告；唯一 dev champion 按 dev task-macro 选择，精确平局按 pooled-LR→pooled-GBM→
task-LR→task-GBM。test 上预先固定 task/parent clustered CI、Draft/Improve、paired TF-IDF delta、LOTO 和 tie/
coverage；只有 champion 的 task/parent CI 都高于 0.5，且相对已锁定 TF-IDF 的两类 paired CI 下界都>0、两语义
delta≥-0.01、所有 leave-one-task-out 不翻负，才允许写“可解释静态特征稳定强于字符文本”。否则只作诚实 baseline
表。该测试已是 retrospective，不改变 G0/G1 gate、first-960 primary/WL extension 或论文 novelty。结果前状态为
`COMPONENT_STATIC_SUITE_PREREGISTERED_NOT_RUN`；正式结果与边界已由 0CJ 覆盖。直接协议：

- `phase1/实验记录/2026-08-21/CleanDirectDecision_component同池静态suite_预注册.md`。

## 0CH. 2026-08-21 G0 输入与运行包静态全过；当前账号无 Pro6000 QoS，未提交

component-split critic G0 的工程歧义已在任何 GPU 结果前消除。旧 confirmatory launcher 虽写了 dev-only
契约，却没有把预注册的固定 10 optimizer steps 传给 Trainer；补丁
`0002-Allow-fixed-step-critic-budget-calibration.patch` 已加入 fail-closed `max_steps`、cosine 与 warmup 入口；
`0003-Record-critic-wall-clock-receipts.patch` 再加入不改变优化的五事件 timing callback。在 senior
`baf6bdd...` + 三补丁 detached overlay 上形成干净 commit `51c7f48...`，聚焦测试 15/15。同时把此前隐含在
固定源码默认值中的 `head_frac=0.25`、`eval_on_start=false` 显式冻结；结果出来后不得改。

Qwen3-1.7B-Base 已锁定 revision `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`。CPU-only 独立预检重新哈希
train/dev/Cards 与模型 10 个文件共 3,452,692,285 bytes，离线 config/tokenizer 加载和训练源码哈希全部通过；
状态为 `G0_STATIC_ASSETS_PASS`。固定运行包要求 2 张可见 Pro6000、96GB 级显存、bf16 ZeRO-3、16384 context、
seed 6、有效 pair batch 128、10 steps、仅 step 10 一次完整 dev eval；验收器要求唯一 `checkpoint-10`、唯一
dev eval、`launch/step1/step10/dev/end` 单调墙钟事件、有限指标、两张不同 GPU UUID、完整遥测和零 test-path
痕迹。它不接受 test 参数，也不自提交。

当前用户 `yzyang4` 只有 account/QoS=`gpu/gpu`。2026-08-21T01:28:59Z 对 `zliang_gpu` 显式与默认
`sbatch --test-only` 均返回 `Invalid qos specification`，队列为 0；因此没有 GPU job，也没有 dev accuracy。
当前状态是 `G0_ENGINEERING_READY_BUT_NOT_SUBMITTABLE_BY_CURRENT_ACCOUNT`，不是模型正结果。只有同时满足
“精确 1 run、2×Pro6000、2h hard cap=最多 4 GPU·h 获明确批准”和“学长授权账号提交或管理员授予 QoS”后
才能运行；G1 仍须看 G0 实测吞吐后另报预算、另行批准。直接证据：

- `phase1/results/critic_component_g0_static_preflight_20260821/`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_G0静态预检与调度阻塞.md`；
- `phase1/scripts/critic_component_g0_worker_20260821.sh`；
- `phase1/verify_critic_component_g0.py`。

## 0CG. 2026-08-21 Component split 的方法 novelty 关闭；仅保留 MLE-specific 协议证据

防 scoop 复核发现，connected-component 作为关系数据的不可分 split unit 已有直接先例。2026-06 的 Refnd
明确从 proximity graph 的 connected components 出发，要求每个 component 整体进入 train 或 evaluation；更早的
graph-benchmark leakage 工作也已指出随机切 edge 会把 component 路径留在 train，从而泄露 held-out edge label。
通用工具中的 non-overlapping group split 亦早已标准化。因此不得把 pair-component split、transitive grouping、
零跨组 overlap 或“关系决定 split unit”申作方法首创。

可保留的贡献是窄而实证的：真实 MLE-agent Draft pair 跨 physical run，使普通 run sampler 删除 485/5,240 个
outer-train pairs，且 485 个全为 Draft，导致 dev Draft 仅 74；固定 component split 在不改 seed/fraction/支持门的
条件下做到零删 pair、零 Card/run/pair overlap，并恢复 294/257 的 Draft/Improve dev。这是 Decision Corpus 的
data-integrity failure case、可复现协议和审计资产，不是主方法。G0/G1 仍只能贡献 critic capacity 轴；论文主线、
first-960/closure 和 outcome vault 均不变。直接边界记录：

- `phase1/实验记录/2026-08-21/CleanDirectDecision_component拆分_防Scoop边界.md`。

## 0CF. 2026-08-21 Component 同池 TF-IDF 固定 Qwen 门槛；廉价信号仍显著但不强

component train/dev/test=`4689/551/931` 上的固定 train-only char-TFIDF 已完成 producer×2 与不 import
producer 的 full-refit verifier×2；逐对 margin、模型 receipt 和全部统计最大差均为 0.0。正式 retrospective test
为 532/931=`0.5714285714285714`，task macro=`0.5757982662586206`；task-clustered 95% CI=
`[0.5066135214563272,0.6409030224715225]`、parent-clustered CI=
`[0.5322425162766734,0.6111639404566828]`，均高于 0.5。Draft/Improve micro=
`0.5796178343949044` / `0.5672609400324149`，没有单一语义崩塌。

这说明同池便宜文本信号真实但只到约 57%；它把未来 Qwen 的对照从错位的旧 59.90% 固定为逐对可配对的
57.1429%。同时 dev micro=`0.604355716878403`，比 test 高 `0.03292714544983155`，所以 dev 只能选 checkpoint，
不得当 test 代理；G1 仍须一次性 test、task/parent clustered paired delta 和两 seed。相对用全部 5,240 outer-train
pairs 拟合的旧 pooled 0.58324，本次低 `0.011815252416756183`，不能解释为算法退化或进步，因为 551 dev pairs
被严格留出。

第一次正式 baseline 在任何 accuracy 输出前被反对称门截停：分类器 `decision_function` 错把截距放进 pair
margin。v2 按 Bradley--Terry 定义改为 `coef·(x_better-x_worse)`，阈值不放宽；拟合截距保留审计但不进入
margin。该工程失败与修复均留档。当前状态仍只是 `G0_PROPOSAL_READY_NOT_SUBMITTED`；明确批准前无 GPU job。
论文主线、first-960/closure 与未来 outcome vault 均不变。直接证据：

- `phase1/results/critic_component_tfidf_20260821_a6075d1/README.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_component同池TFIDF_v2正式裁决.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_component同池TFIDF_v1失败与v2修正.md`。

## 0CE. 2026-08-21 Pair-component split 修复跨-run Draft 的 dev 塌缩；只解锁 GPU 校准提案

clean direct-decision scaling 的第一版 physical-run sampler 按预注册失败：train/dev/test=`4532/223/931`，
dev 虽覆盖 28 tasks 且零泄漏，但 Draft 仅 74；总 dev `<300`、Draft `<100` 两门失败，485 个跨界 pair 全为
Draft。原因不是模型 outcome，而是跨-run Draft edge 在独立 run 抽样下以约 `p^2` 进入 dev，并以约
`2p(1-p)` 跨界删除。原 split 正式关闭，未放宽 seed、fraction 或阈值。

结果揭晓后另立的 pair-graph connected-component v2 保持 seed=`20260821`、target=`1/10` 和所有旧门不变；
以 outer-train pair graph 的 168 个不可分 components 为 split unit，动态规划按 task 选择 41 个 dev components。
producer×2、非 import verifier×2 与结构 gate×2 全部 byte-identical，10/10 tests；得到 train/dev/test=
`4689/551/931`，outer-train 5240 对零丢失。dev 为 Draft/Improve=`294/257`、25 tasks、dominant=
81/551=`0.147005444646098`；train/dev/test Card、physical-run、unordered-pair overlap 全为 0，十个固定门全过。

该结果是明确的数据协议正进展：普通 group split 在跨-run preference graph 上会改变语义 mixture，而 component
split 同时保住 pair 和零泄漏。但它不含模型 accuracy，不证明 Qwen scaling 或 search utility。状态仅为
`COMPONENT_SPLIT_ELIGIBLE_FOR_G0_PROPOSAL`：G0 仍是 1 个 Qwen3-1.7B、seed 6、2×96GB Pro6000、固定 10 steps、
hard cap 4 GPU·h、绝不读 held-out test；在明确 GPU 批准前不得提交。论文中心仍是 Decision Corpus + Predictor
Benchmark + first-960/closure。直接证据：

- `phase1/results/critic_decision_component_split_20260821_305355e/README.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_component拆分_v2正式裁决.md`；
- `phase1/实验记录/2026-08-21/CleanDirectDecision_component拆分_v1失败裁决与v2预注册.md`。

## 0CD. 2026-08-21 Semantic Mixture 点估计为正但稳定性门失败；路线正式关闭

exact-config v2 在固定 5,240 train / 931 test 上完成 producer×2 与独立 full-refit verifier×2。fixed
semantic mix 相对 pooled 的 merged micro 从 `0.5832438238453276` 升至 `0.6004296455424275`，delta=
`+0.017185821697099923`；task macro 从 `0.5743054636618959` 升至 `0.5845981187534576`，delta=
`+0.010292655091561631`。Draft/Improve micro delta 也分别为 `+0.019108280254777066` / `+0.01620745542949753`。

但 task-clustered 95% CI=`[-0.020432976223223577,+0.04351597259972664]`、parent-clustered micro-delta
CI=`[-0.003174687247780468,+0.037353489626701986]` 均跨零；23 个 supported tasks 仅 10 positive / 9 zero /
4 negative，positive fraction=`0.43478260869565216`。六个固定效果门只过 4 个，正式状态为
`DISCOVERY_NO_UNLOCK`。不得改 0.5 权重、任务、子集或单追 Draft/Improve，也不解锁 future arm。

结果揭晓前已由 commit `9a5b163...` 冻结 parent-multiplicity 条件消歧：Draft/Improve 训练平均 pairs/parent 相差
`18.253591360440673` 倍；只有 v2 unlock 才运行。当前触发失败，故状态为
`NOT_RUN_PARENT_WEIGHT_DISAMBIGUATION_NOT_TRIGGERED`，不以 parent-equal 追救。APLOT、PaTaRM、correlated RM
与 Themis 又关闭了 adaptive-margin、pairwise→pointwise、setwise context 和 code-RM scaling 的宽方法首创。

semantic routing 当前路线关闭；这不削弱 exact-config 数据修复与可复现资产。论文中心仍是 Decision Corpus +
Predictor Benchmark + first-960/closure。下一模型支持候选是 clean direct-decision Qwen scaling，但必须使用 0BW
的 dev/frozen 补丁，并在精确矩阵和总 GPU·时获批前不提交。直接证据：

- `phase1/results/decision_semantic_mixture_v2_20260821_c5d2cf7/README.md`；
- `phase1/实验记录/2026-08-21/DecisionSemanticMixture_v2正式裁决.md`；
- `phase1/实验记录/2026-08-21/DecisionSemanticMixture_parent权重机制消歧_条件预注册.md`；
- `phase1/实验记录/2026-08-21/RewardObjective与ChoiceContext_防Scoop增补.md`。

## 0CC. 2026-08-21 Decision Semantic Mixture 通过 exact-config 支持门；只作非首创 discovery baseline

v1 在任何模型拟合前因 pair 内 execution config 不一致而 INVALID。结果盲 v2 support gate 随后按事前固定的
`(task,client,hardware,time_limit,execution_timeout)` 精确过滤并通过全部 10 个门：merged 保留 5,240 train /
931 test，Draft 3,196/314，Improve 2,044/617；test 覆盖 28 tasks，23 个任务至少 10 pairs，dominant=
100/931=`0.10741138560687433`。剔除的 385/6,556=`0.0587248322147651` 全部是 Draft hardware mismatch；
Improve 不变。eligible train/test endpoint 与 physical-run overlap 均为 0，filtered union/config/task 完整性全过。

producer×2 与独立 verifier×2 逐字节相同，11/11 focused tests、安全扫描和 SHA manifest 均通过；GPU/API/model
fit/checkpoint/prospective outcome read 全为 0。三个 filtered 文件的 SHA、bytes 与精确计数已绑定进 v2 source；
按原预注册只允许运行不变的 char-TFIDF、pooled/Draft/Improve 三 heads、固定 0.5 mix 和 20k 双 bootstrap，不能
改权重、任务或子集。当前状态是 `V2_MODEL_INPUTS_BOUND_NOT_RUN`，仍为已见旧 test 的 retrospective discovery。

防 scoop 核查同时确认 domain/task/context router、specialist/MoE reward model 与异质 preference mixture 已有
直接先例（Domain Robust RM、DMoERM、ArmoRM、MiCRo、PrefMoE 等）。所以即使 v2 过效果门，也只能作为
MLE-agent Draft/Improve construction semantics 的 benchmark diagnostic 和 future exact-stratum 候选 baseline，
不得申方法首创或替代 first-960+closure。直接证据：

- `phase1/results/decision_semantic_exact_config_support_20260821_21a4d4e/README.md`；
- `phase1/实验记录/2026-08-21/DecisionSemanticMixture_v2支持门裁决与输入绑定.md`；
- `phase1/实验记录/2026-08-21/DecisionSemanticRouting_防Scoop边界.md`。

## 0CB. 2026-08-21 TraceML 公开 paired 表不能通过 direct-sibling 外部资格门

固定 TraceML revision `61faec6...17e96` 与 source commit `517c95c...2fe2` 的 outcome-free 审计完成。
189/189 branch keys 可归并为官方声明的 13 个 physical runs；1,026 state / 837 action rows 无 identity/join
缺失。但 837 条 path-edge rows 中只有 537 条 depth `+1`，其余 **300** 条跳过 1--4 层；去重后的 583 条
path adjacency 因而不能唯一解释为 direct parent-child edge。按事前规则，mapping=
`IDENTITY_OR_JOIN_AMBIGUOUS`、`canonical_direct_sibling_pairs=null`，score 与 overlap 阶段均未读，冻结 scorer
不允许运行。

即使违规放宽为 path adjacency，诊断出的 167 pairs 也只覆盖 3 tasks，dominant task=117/167=
`0.7005988023952096`，且公开 `raw_code_path` 覆盖 0/643 original nodes；会独立失败固定的 4-task、≤0.50 与
code-coverage 门。producer/verifier 各双跑逐字节一致，独立验证全部通过，聚焦测试 12/12；GPU/API/LLM
update 均为 0。

这只支持窄主张：固定公开 TraceML paired tables 不能实例化我方 physical-run-clean direct same-parent sibling
协议，我方 249 runs / 1,665 canonical pairs / 26 tasks 的结构 benchmark 不被其公开表直接替代。它不证明 gated
MLE-Traj-v1 raw tree 无 sibling，也不恢复任何“首个轨迹/树数据集”宽主张。当前 primary、first-960/closure、
WL extension 与 outcome vault 均不变。直接证据：

- `phase1/results/traceml_external_structure_eligibility_20260821_517c95c/README.md`；
- `phase1/实验记录/2026-08-21/TraceML外部结构资格审计_v1_裁决.md`。

## 0CA. 2026-08-21 0819 安全摄取闭合；结构支持增强但 WL 严格未来样本仍为零

固定 0819 八包最终为 7 committed / 1 rejected。Plant 包不是按文件名猜任务后勉强 salvage：credential-first
双审计发现 4/4 checkpoint journals 的 task-identity cardinality 均为 0，env 与 live-event journal 未读，故按
精确 archive SHA 结构性拒收。其余七包闭合后 snapshot=`83ab1d6...d5c047`；独立结构门得到 49 transactions、
249 eligible physical runs、6,471 endpoints、1,665 canonical sibling pairs、26 tasks。248 runs 有 finite
decision，dominant pair task=278/1,665=`0.16696696696696697`；精确代码 unique fraction=
`0.9979910369340133`，9 个重复组均不跨 run/task。0819 本身增加 26 runs / 828 endpoints / 192 pairs /
7 tasks。pair/run/task/balance 门已过，但 first-960 尚差 711 runs，accrual 未闭合，vault 仍不允许打开。

同一 snapshot 的冻结 WL 四臂增量托管完成。producer 与不 import producer 的 verifier 分别对 6,471 endpoints /
1,665 pairs 计算和独立重建，四臂最大绝对差全部为 0.0；旧 5,643 endpoints / 223 runs / 1,473 pairs 的每行
逐字段不变，新增量精确为 828 / 26 / 192。两份 syscall trace 共 18,094 行，禁读路径命中 0；9 个目标文件共
7,484,849 bytes 的 credential-shape matches=0。

必须保留的勘误：0819 是 activation 后才完成投递/摄取的批次，但 physical runs 的
`generation_started_at_utc` 早于 `2026-08-20T05:20:27.656860Z`。因此 249 runs / 1,665 pairs 全部仍是
`outcome_unread_support_only`，strict post-activation=0。原预注册文档“activation 后首批候选 physical runs”
若被理解为生成时间则错误；时间规则不改、不回填、不借上传时间追认。当前仍无 accuracy、CI、search utility 或
方法效果正结论，只有更强的结构/复现资产。直接证据：

- `phase1/results/prospective_0819_intake_wl_escrow_20260821/README.md`；
- `phase1/实验记录/2026-08-21/Prospective0819_安全摄取结构门与WL增量托管_裁决.md`。

## 0BZ. 2026-08-21 TraceML 是直接 D&B 竞品；宽轨迹数据 novelty 关闭

新发现的公开 `MLE-Traj-v1` / `TraceML` 是 NeurIPS 2026 E&D double-blind 直接竞品。前者在 7 个 Kaggle
tasks 上发布 422 human trajectories、11 Codex runs、13 MLEvolve physical runs（线性化为 189 branches）、
15,572 code versions 与逐版本 grader score；后者扩到 134 tasks，但新增 127 tasks 为 humans-only，agent
paired split 仍来自上述 7 tasks，并另有 7 个 planning-skill Codex runs。因此“首个 MLE trajectory/per-node
score/tree dataset”“首次比较 human 与 MLE agent planning”全部关闭。

当前可守边界不是和它比总 version 数，而是 agent search-time 的真实同-parent sibling decision：physical-run
clean、canonical choice fragment、source missing/failure、gap/regrade、endpoint reuse、query/init/execution cost，
以及 outcome-blind first-960 + closure。公开 card 尚不能证明其 predictor split 或我方这些契约缺失，正式论文
必须等其终稿后逐项复核，不能写未证实的负面比较。

它同时提供一个有价值但未启动的外部 replication 机会：只有获得 gated raw MLEvolve code 的正常授权，且按
13 个 physical runs 而非 189 paths 去重后达到预固定的 8 runs / 4 tasks / 150 finite sibling pairs / dominant
share<=0.50、并确认与我方 code/run 零 overlap，才一次性运行既有冻结 scorer；否则只做结构描述。当前 primary、
WL extension、first-960/closure 与 outcome vault 均不变。直接记录：

- `phase1/实验记录/2026-08-21/TraceML与MLE-Traj-v1_直接竞品边界.md`。

## 0BY. 2026-08-21 pair-construction 的泛化理论 novelty 关闭；改为 CPRD 的 MLE 实证化

进一步一手核查发现，ICML 2026 的 *What Does Preference Learning Recover from Pairwise Comparison Data?*
已经从 triplet distribution 定义 conditional preference distribution（CPRD）与 comparison distribution，证明
BT 目标在后者上的投影含义，并把有限样本可学性归结为 margin 与 connectivity。其 2026-05 follow-up
*Reward Learning from Best-of-N Preference Data* 又把候选集大小、base distribution、margin/connectivity tradeoff
和任意 target test distribution 明确联系起来。RewardBench 2 也已实证比较 benchmark accuracy 与下游 BoN/PPO
的相关性及 on/off-policy 依赖。

因此 0BX 的 **benchmark construction determines the deployment estimand** 只能作为论文组织原则和待复核实证命题，
不能申理论/概念首创；“首次指出 pair 分布影响 RM”“首次连接 benchmark 与部署”“首次研究 comparison graph”均关闭。
当前可守的正面贡献进一步收窄为：把 CPRD/margin/connectivity 的一般理论落到真实 MLE-agent physical-run sibling
上，并同时发布连续 pristine execution score、source missing registry、run-clean split、gap/regrade、endpoint reuse、
query/init/execution cost 和结果盲 first-960+closure。PairGraphIntervention 作为早期领域实证但 universal-inflation
确认门失败，必须诚实报告；不得因理论先例改写为已确认正效果。

正向机会不是再造一个 rank loss，而是用该理论组织现有资产：自然 sibling 是 deployment comparison distribution，
FOREAGENT/global pair 是不同的 comparison distribution；gap 对应 margin，pair graph/reuse 对应 connectivity，未来
first-960 检验同一冻结 scorer 在时间外 deployment distribution 上是否可 transport。当前 primary、WL 单列
extension、outcome vault 与停止门均不变，不新增 arm。直接记录：

- `phase1/实验记录/2026-08-21/CPRD_PairDistribution_防Scoop与主张二次收紧.md`。

## 0BX. 2026-08-21 agent RM 与 AutoML ranking 直接先例补齐；核心改写为 deployment-estimand benchmark

新增一手核查覆盖 Plan-RewardBench、AgentRewardBench、ExeVRM/ExeVR-53K 与 AutoML Ranking Trick。通用
trajectory preference benchmark、专家标注的 web-agent evaluator benchmark、execution-grounded 大规模 RM
语料/模型，以及 rank target + NDCG/MRR + MCTS 集成均已有直接先例。因此“首个 agent RM benchmark”、
“首次用执行轨迹训练 evaluator”、“首次把 AutoML 选择写成排序”与“首次用 listwise/rank metric”全部禁止。

这些工作仍未等价覆盖：MLE program-search physical run 中自然发生的同-parent **labeled sibling fragment**、
连续 pristine Kaggle score、run-clean 隔离、gap/noise/cost/missingness，以及结果盲时间外确认。论文中心进一步
收窄为 **benchmark construction determines the deployment estimand**：全局/合成 preference pair 上的准确率，
不能自动外推到 agent 当时面对的局部 sibling 分布。0BY 已确认这不是新的泛化理论主张；FOREAGENT 与我方已
锁定的 gap、pair graph 与复用差异只能作为 MLE 领域实证，不再把“训练出最强 RM”当唯一成败标准。

当前 first-960 primary、WL 单列 extension、960-run + accrual closure 和 outcome vault 均不变。NDCG/MRR、
parent-macro top-1 等只作为 choice-fragment secondary reporting，不申方法 novelty；Ranking Trick 若要成为新
baseline，必须先做 train-only 资格门并另立严格 post-activation future cohort，禁止事后加入当前 cohort。
直接记录：

- `phase1/实验记录/2026-08-21/AgentRM与AutoMLRanking_防Scoop及主张收紧.md`。

## 0BW. 2026-08-21 学长 0820 scaling 是更强探索信号；确认协议补丁已在最新 base 通过

学长 `dojo-reproduce@baf6bdd...` 已补齐 outcome 文档。experiment 内 value pair 的两 seed final mean 随
Qwen3 0.6B/1.7B/4B/8B 为 58.64%/60.67%/62.01%/64.68%，final loss 同时单调下降；8B 两 seed 均超过
同数据 TF-IDF=61.18%，均值优势 3.50 pp。这是目前最清楚的 critic capacity/scaling 探索信号，优于一周前的
“各规模约 0.55”状态。但 decision zero-shot transfer 只有单 seed 的 56.25%/56.25%/59.06%/59.38%，8B 仍低于
TF-IDF=59.90%。旧结果还使用周期性 outer-test eval、含 708 条跨 exact config 的 full-train pairs、共享 endpoint，
部分大模型未正常结束；`92a9651` 时 checkpoint 方向设置错误。因此不得把旧 checkpoint/test 曲线升级为确认性结果。

已在精确 base `baf6bdd...` 形成新的 cherry-pick 补丁：exact-stratum/batch provenance、canonical raw sibling 与
synthetic/contracted pair semantics 分栏、outer-train→physical-run-disjoint dev、dedicated immutable frozen test、
训练期拒绝 test、dev accuracy 正向 checkpoint 选择，以及哈希锁定的 one-shot test ledger/逐 pair margin 回执。
旧 combined pair 迁移时必须同时产出 frozen-test 文件，且 Card/physical-run train-test overlap=0；不允许静默丢弃。
Windows 的无 torch 协议测试 24/24；远端 Python 3.11.15、PyTorch 2.11.0、Transformers 4.57.1 下 33/33，
TrainingArguments 契约与 clean worktree 均通过。补丁只服务 future exact-stratum 数据；未启动 GPU/API。

该支持线不改变当前论文中心：Decision Corpus + Predictor Benchmark + first-960/closure 时间外确认。0Z 已证明
旧 decision test 与 b0/b1/b2 是同一 2,087-row multiset，故旧 4B/8B checkpoint 的 frozen scoring 继续正式关闭；
不得再定位或运行，也不能以“只推理”洗白 test-touched checkpoint。补丁只允许用于 future exact-stratum 数据和
全新未触碰 frozen cohort。任何重训矩阵仍须先给总 runs/GPU·时并获批。直接证据：

- `phase1/upstream_patches/0001-Harden-critic-confirmation-protocol.patch`；
- `phase1/results/senior_critic_confirmation_protocol_20260821/README.md`；
- `phase1/实验记录/2026-08-21/SeniorAugmentedScaling_0820结果审计与确认协议交付.md`。

## 0BV. 2026-08-20 直接竞品再收紧：AutoML pre-rollout value 与 ML-agent RM benchmark 已有

一手核查补入三个直接边界。I-MCTS 已在 agentic AutoML 的 MCTS 中分析 parent/sibling results、用 LLM value
model 在完整 rollout 前评分节点，并把估计 reward 过渡到真实 performance；ML-Tool-Bench 已用 61 tools /
15 Kaggle tabular tasks 建立 ML-agent planning benchmark，并报告 LLM state scoring 不一致会拖累 tree search；
CUARewardBench 已在 10 software categories / 7 agent architectures 上系统评估 step/trajectory ORM/PRM。

因此“首次在 MLE 树中执行前 value guidance”“首次发现 ML-agent tree evaluator 不稳定”“首个 agent RM
benchmark”全部禁止。仍未被这些公开设定等价替代的窄边界，是完整 Python MLE candidate 的结构有效同-parent
**labeled sibling fragment**、physical-run-clean split、连续 hidden-score gap/noise、query/init/execution 成本与
结果盲时间外确认。
这不是无人做过的证明，论文不得用 first/only，只能逐项列出可复核差异。当前 WL 配置、primary 与未来门均不变，
不增加 arm 或启动新实验。直接记录：

- `phase1/实验记录/2026-08-20/IMCTS_MLToolBench_CUARewardBench_防scoop补充.md`。

## 0BU. 2026-08-20 WL graph 前瞻预测托管已独立复核；当前 1,473 pairs 全为支持集

自动 activation receipt 已在 `2026-08-20T05:20:27.656860Z` 绑定 commit `031edb3...`、协议、独立验证
bundle 与 source blobs。固定 snapshot `88cb791...170c8` 上，producer 完成 5,643 endpoints / 223 runs /
25 tasks / 1,473 canonical sibling pairs 的四臂预测；不 import producer 的 verifier 独立重建并复算，四臂最大
绝对分数差均为 0.0。四臂全覆盖且 ties=0；AST/token/raw graph 路径分别覆盖 5,488/150/5 endpoints，
159 个触发预固定 node cap。

当前所有 run 都早于 activation，因此 223 runs / 1,473 pairs 全部为 `outcome_unread_support_only`，strict
post-activation pairs=0；本轮没有 accuracy、CI、search utility 或任何效果结论。producer/verifier syscall
禁读 content opens=0、metadata observations=0，credential-shape matches=0，GPU/API/base-LLM update 均为 0。

这完成 graph/multi-view baseline 的可审计预测基础设施，不改变其 baseline-only 定位。继续 append-only 摄取；
只有真正 activation 后生成的 cohort 达到预注册 1,500 pairs / 150 decision runs / 15 tasks / dominant≤0.25，
才一次性比较完整多视图 arm 与既有 char-TFIDF。直接证据：

- `phase1/results/prospective_wl_graph_escrow_20260820_031edb3/README.md`；
- `phase1/实验记录/2026-08-20/WLGraph前瞻预测_v1_完成与独立复核.md`。

## 0BT. 2026-08-20 更直接防 scoop：graph binary predictor 引导 ML program search 已有工作

一手核查发现 Co-Reyes et al. 的 Guided Evolution 已把多类 ML program 编成统一 DAG，在线训练二元
better/worse graph predictor，并用 PAM/PAM-RT 比较 mutated child 与 parent、拒绝预测较差候选；论文还报告
Hero/AutoRL 搜索加速与 noisy-oracle/GNN 消融。ICML 2024 GRAF 也已证明便宜 graph features 可成为强 NAS
predictor。因此“graph program critic”“binary predictor 跳过执行”“predictor-guided mutation”全部关闭为算法
novelty；当前 WL/AST extension 无论效果如何都只是 benchmark baseline completeness。

仍可守边界是 LLM MLE-agent 完整 Python solution 的真实 physical-run sibling 决策资源，以及 run-clean、连续
external score、gap/noise/cost/missingness 和 outcome-unread first-960 confirmation。若未来做 end-to-end search，
PAM-RT 必须作为已知 baseline；可问的是它能否迁移到长代码、LLM operator 与强近平局，而非重命名 heuristic。
当前四臂、primary、first-960+closure 均不变，不新增 arm。直接记录：

- `phase1/实验记录/2026-08-20/GuidedEvolution_GraphPredictor_防scoop增补.md`。

## 0BS. 2026-08-20 FLORA 原版不可等价搬运，但 lineage 省略理由失败；适配 extension 需预冻结

commit `fa7468f...` 在任何前瞻结构重算前固定官方源码 commit/SHA、七项 literal semantic mapping 和无可调阈值的
pair non-degeneracy 判据。producer/verifier 各双跑逐字节一致；Linux focused `7 passed`、全套 `462 passed`，
四份 trace 对禁读路径有 4 次 `newfstatat` metadata observation、0 次 content open，first-960 outcome 保持封存。

原版 FLORA/Agentic Predictor workflow DAG 在 v11 7,760 endpoints 和前瞻 5,643 endpoints 上 literal-equivalent
fraction 均为 0：candidate program 与 search lineage 不能冒充 internal agent-call graph、node prompt/operator
implementation/global workflow code。另一方面，v11 5,897/5,897 pairs 与前瞻 1,473/1,473 pairs 的
`op/depth/n_siblings` 相同、`step` 全部不同，exact candidate code 也全部不同。因此“lineage 全恒定，所以可省略
graph family”的强理由失败；但这不证明 step/graph 有预测力，step 可能只是顺序偏差，且当前 `static_lr` 已包含它。

下一步只能把 candidate-code AST/token graph + global code + lineage 做成单列 outcome-unread extension，固定
`step-only` 负控和 view ablations 后再到 future cohort 检验；不得用 v11 frozen/current first-960 outcome 调结构。
原 primary、first-960 + closure 和五项正资产索引均不变。直接证据：

- `phase1/results/flora_transfer_invariance_v1_20260820_fa7468f/README.md`；
- `phase1/实验记录/2026-08-20/FLORA迁移不变性审计_v1_固定协议.md`；
- `phase1/实验记录/2026-08-20/FLORA迁移不变性审计_v1_裁决.md`。

## 0BR. 2026-08-20 五项正资产证据索引已独立复核；release 仍等 first-960

新增 `decision_corpus_evidence_index_v1`，不制造联合总分，而把五个互异 estimands 分开绑定：decision corpus
结构、label repeatability、normalized clone、deployment cost、prospective gate。真实 index 含 5 entries/
15 个无重复 artifact paths，SHA=`cfbe749f84114a633d902a358f8ef8243c4c4fe71433961c94e18494ca93769d`；
不 import producer 的 verifier 逐文件核 SHA 和 106 项 JSON 断言。本地/Linux 输出逐字节一致；Linux 定向 7/7、
phase1 全套 455/455。

这形成当前最强的正面 D&B 叙事骨架：真实 sibling/run-clean 资源、0.96586 次序复测一致性、token/AST 覆盖内
零跨 run 浅层 clone、约 4,048–6,037× execution/query 成本分离，以及仍 outcome-blind 的 223/960 前瞻门。
但索引状态固定为 `PROVISIONAL_EVIDENCE_STACK_AWAITING_FIRST960`；五项 estimand 不合并，AST 强门失败、
成本不等于准确率、prospective outcome 未知均由机器断言保留。`release_complete=false`，first-960 + closure
前不得升级为完成的 benchmark release。直接证据：

- `phase1/results/decision_corpus_evidence_index_v1_20260820/README.md`；
- `phase1/实验记录/2026-08-20/DecisionCorpusEvidenceIndex_v1_裁决.md`。

## 0BQ. 2026-08-20 部署成本正门双跑通过：在线查询相对执行便宜约 4,048–6,037 倍

结果前 commit `c800345...` 冻结的 v2 已正式完成：A/B 各 3 models×3 fits×256 measured pairs，共 18 fits/
4,608 online queries；两份 producer 均为 `DEPLOYMENT_COST_ADVANTAGE_SUPPORTED`，两份不 import producer
的 verifier 均通过，跨运行 comparator 为 `CROSS_RUN_STABILITY_VERIFIED`。clean preflight 为定向 9/9、
phase1 全套 448/448；正式用时 51 分 31 秒，未触发 2 小时停止门。

1,498 个 frozen b0 pairs 的 execution coverage=`1.0`，ideal-parallel p50=`199.62654004304204` 秒。
static-LR、static-GBM、TF-IDF-LR 的 A/B query p50 依次为 `40.909126/41.00444`、
`49.3092785/49.0379345`、`33.925568/33.0667115` ms；execution/query-p50 比值覆盖
`4048.4579396764457`–`6037.084759488165`。最坏 query p95 只占 execution p50
`0.05797248618597878%`，通过≤1% 门；init p50=`98.586651793`–`155.037595478` 秒，六格 break-even
均为 1 pair，并通过≤10×execution p50 门。最大 A/B query/init ratio 分别为
`1.025973447646888`/`1.0901214467517888`；0 warning、0 tie、antisymmetry=1，decision digest 跨 trial/A-B
一致。

这是数据/benchmark 的正成本资产，不是 accuracy 或方法 novelty：未算 frozen accuracy，未打开 prospective
vault，GPU/API=0；不得与旧 accuracy 事后拼成联合收益，也不证明实际搜索 wall-clock 或最终分数一定提升。
完整收据与裁决：

- `phase1/results/deployment_cost_attestation_v2_20260820_c800345/README.md`；
- `phase1/实验记录/2026-08-20/DeploymentCostAttestation_v2_裁决.md`。

## 0BP. 2026-08-20 v1 因 16.161918904708 小时投影工程停止；v2 在线单对协议已结果前冻结

v1 只完成 A/static-LR 的 1/15 trials，首个 trial 显示 30 次 full-cohort 端到端 batch 会把 A/B 投影推至
`16.161918904708` 小时，超过事前 2 小时停止门；已 fail closed，partial 不可作论文成本数字。这不是正成本门
失败，而是辅助 batch estimand 与资源估计错误。旧 suite 缓存式毫秒值仍不得替代端到端部署计时。

v2 保持同一 v11 b0 输入、三个模型、单核 CPU、execution 分母、A/B、独立 verifier 与全部正门，只删除并不对应
在线 selector 的 30 次 1,498-pair batch 重复。每个 A/B × model 固定 3 次初始化、10 次 single warmup、同一
seed 事前抽取的 256 个 canonical pairs；共 18 fits / 4,608 measured online queries。query 必须包含 feature/
TF-IDF transform；sample batch 仅核对逐对 digest 与 exact antisymmetry，不计时。GPU=0、API=0、hard wall=2h。
直接证据：

- `phase1/实验记录/2026-08-20/DeploymentCostAttestation_v1_工程停止.md`；
- `phase1/实验记录/2026-08-20/DeploymentCostAttestation_v2_在线单对预注册.md`。

## 0BO. 2026-08-20 部署成本证明已结果前冻结；旧“七百万倍”正式撤回

Decision-Corpus Audit 仍缺一份单独的 deployment cost attestation。当前只允许在 v11 b0 run-clean train 和
orientation-free frozen endpoint manifest 上，对 static-LR、static-GBM、TF-IDF-LR 做 CPU 单线程重复计时；
不算 frozen accuracy，不读 prospective vault，不把 hard-coded LLM/RM latency 混入。固定 5 次初始化、5 次
warmup、30 次 batch 与 128 个逐对查询，并做 A/B 独立执行和不 import producer 的复核。正成本门为三个模型
各自 single-query p95≤理想并行 pair-execution p50 的 1%，且 init p50≤10 个该执行中位数。

旧 `REVIEW_PACKET.md` 的 `561077ms / 4.8ms = 七百万倍` 是算术错误；程序打印为
`116891.041666666671517`。后续 `suite_v9.csv` 单次值之比为 `103153.864310954057146`，也缺重复和硬件绑定。
两者均不得正式引用或与旧 accuracy 拼成联合收益。直接协议：

- `phase1/实验记录/2026-08-20/DeploymentCostAttestation_v1_预注册与执行前检查.md`。

## 0BN. 2026-08-20 防 scoop 纠偏：predictor/GNN/multi-view 已非 novelty，决策资源窄边界仍开放

新增一手文献核查确认，FLORA-Bench 已发布 600k workflow-task pairs 并用 GNN 预测 agent workflow binary
performance；ICLR 2026 Agentic Predictor 已联合 graph/code/prompt 与跨域无监督预训练；GLOW 已融合 graph-LLM
与 GNN；AgentSwift 已把 value model、uncertainty-guided MCTS 用于 agent design search。因此“NAS 式 agent
predictor”“graph/multi-view encoder”“用 predictor 省执行”均正式关闭为 novelty，只能作 baseline。

这些工作预测的是 agent workflow/configuration × task，不是一次 MLE program-search physical run 中同 parent
候选代码的连续 hidden-score 次序。当前可守边界收窄为：带 missing registry 的 MLE labeled sibling-fragment
decision resource，绑定 physical run/operator/evaluator，显式审计 endpoint reuse、pair graph、gap/noise/
query-init cost，并在结果盲
first-960 + closure 上 prospective confirmation。不得写 first/only，只能逐项列可核差异。

最终 benchmark 需要补 FLORA-style graph/multi-view family baseline，或给出不能等价迁移的可复核理由；但不得
偷加进已激活的 first-960 primary scorer。任何实现只能作为 outcome-unread 的单列 extension 或新 future cohort，
且 TGCA 已失败，禁止在同一 OOF 继续换 graph heuristic 追正结果。直接审计：

- `phase1/实验记录/2026-08-20/FLORA_AgenticPredictor_GLOW_防scoop增补.md`。

## 0BM. 2026-08-20 AST 缺口诊断：失败并非简单包装；150/155 的 token 指纹仍全唯一

0BL 的 aggregate AST coverage 失败后、读取任何失败代码/身份/类别前，commit `31aee5a...` 固定 outcome-blind
post-hoc 诊断，且声明不得补救原 strong gate。双跑 receipt 逐字节一致，SHA=
`cde16b78f5df01dde4ec579a6111d97610699d4d52e93b2a388dc7b39cb7a744`；禁读路径/credential shape 均为 0，
Linux 全套 `439 passed in 38.16s`。

155 个直接 AST 失败分布在 19 runs/8 anonymous tasks，匿名 task counts=`[82,62,3,3,2,1,1,1]`，说明缺失集中。
仅 dedent、删 Markdown fence、删 `%`/`!` cell-command、固定组合与 union 均恢复 0/155，不能把缺口归因于这些
表面包装。正面上，失败子集中的 150 个仍可 tokenizer fingerprint，且 150/150 唯一、跨 physical run=0、跨
task=0；另外 5 个 tokenizer 也失败，保持未知。

因此 0BL 的 token 主结论得到失败子集审计支持，但原 AST coverage 强门仍为 **false**，不得改阈值。可写主张
仍是 99.91% tokenizer 覆盖上的零跨 run/跨任务浅层 clone，以及 97.25% 可解析子集上的 AST 一致证据；不能
升级为全语料或语义唯一。0BK 的 first-960 + closure 门不变。直接证据：

- `phase1/results/prospective_ast_failure_diagnostic_20260820_31aee5a/README.md`；
- `phase1/实验记录/2026-08-20/ProspectiveAST失败诊断_v1_固定协议.md`。

## 0BL. 2026-08-20 最新正资产结果：浅层规范化后仍无跨 run/跨任务 clone；强门因 AST 覆盖未过

结果前 commit `e121452...` 固定 raw、token-literal、AST-literal 与 diagnostic AST-skeleton 四个口径，并把
两种主规范化 coverage≥0.99、跨 run/跨任务重复端点比例和大模板组写入强门。基于 0BK 同一 frozen snapshot
的双跑 receipt 逐字节一致，SHA=`9d85a642928385bac099b46ce36d24f5d8e24434a7b5076dc6b83ea8810656be`；五项
accumulator 交叉核验全过，禁读路径/credential shape 均为 0，Linux 全套 `437 passed in 35.58s`。

5,638/5,643 端点通过 tokenizer；去注释/换行并归一化数字和字符串后 unique=5,573/5,638，跨 physical run
重复端点=0、跨 task=0。5,488/5,643 可由 Python 3.11 AST 解析；归一化 literal/位置属性后
unique=5,423/5,488，跨 run=0、跨 task=0；更激进 skeleton 的跨 run/跨 task 也均为 0。由此可将 0BJ 的
“无跨 run 逐字节复制”加强为：在 99.91% tokenizer 覆盖上，没有只靠注释、格式或字面量变化形成的跨 run/
跨任务 exact clone；在 97.25% 可解析子集上 AST 证据一致。

预注册强门仍判 **失败**，因为 AST coverage=`0.9725323409533936 < 0.99`（155 个失败端点），不得事后降门或
宣称全语料无规范化 clone。该结果是 D&B 数据资产正证据，不是 critic/method 效果，也不排除 fuzzy/语义近重复。
后续只允许将失败原因做 outcome-blind post-hoc sensitivity；0BK 的 223/960 与 closure 约束完全不变。
直接证据：

- `phase1/results/prospective_code_clone_audit_20260820_e121452/README.md`；
- `phase1/实验记录/2026-08-20/ProspectiveCodeCloneAudit_v1_预注册.md`。

## 0BK. 2026-08-20 协议纠偏：确认 cohort 仍是 first-960 + closure；撤回“只差 27 pairs”

结果前功效附录明确把 first-240 保留为 pilot、唯一确认 cohort 固定为按预注册全序排列的 first-960，并要求
独立于 outcome 的 accrual-closure receipt；近期没有正式预注册 supersede。0BI/0BJ 的结构计数正确，但把
1,500-pair 支持门误当成停止门，因此“只差 27 pairs 即可揭盲”正式撤回。纠偏时 label/outcome/scorer
prediction 均未打开。

commit `757ced0...` 的独立 verifier v5 在 CLI 锁死 first-960 与 1,500/150/15/0.25 阈值，按
`(generation_started_at_utc, source_sha256, run_id)` 自行排序并区分 all-eligible/provisional-first960；closure
还必须 provided、all scheduled archives uploaded、outcomes unread 且 accumulator identity frozen。真实 snapshot
双跑逐字节一致，receipt SHA=`9d12e2a8cac555a9eef6743169d0b922c2840b1e6d9c20996662e1910b65e875`；
禁读路径和 credential shape 均为 0，Linux 全套 `435 passed in 36.26s`。

准确状态：223/960 confirmatory runs（差 737），1,473/1,500 structural pairs（差 27），222 finite-decision
runs、25 pair tasks、dominant share=`0.1887304820095044`；closure 未提供。因此状态为
`CONFIRMATORY_COHORT_COLLECTING`、`vault_open_allowed=false`。0BJ 的高决策覆盖、低 exact-code 冗余等正资产
结论继续有效，但作用域是当前 `provisional_first960_prefix`，不是完成的确认集。

v4 虽纠正了 run stop，却因 verifier 内全仓库 `git status` 对 forbidden path 产生 54 次 metadata stat；未读
内容仍按零接触标准作废。v5 改为只核对 verifier 自身 Git blob 后全新重跑。继续 append-only 摄取；first-960
与 closure 之前不得自动冻结或揭盲。直接证据：

- `phase1/results/prospective_confirmatory_gate_correction_20260820_757ced0/README.md`；
- `phase1/实验记录/2026-08-20/Prospective确认门_first960与closure纠偏_v5.md`。

## 0BJ. 2026-08-20 最新正资产结果：前瞻 cohort 高决策覆盖、低逐字节冗余，仍不揭盲

在 0BI 的 frozen snapshot 上，commit `98956a8...` 的 outcome-blind verifier v3 不 import 生产 accumulator，
从 42 份登记后的 blind manifests 独立重建 sibling pairs；两次 clean run 收据逐字节一致，SHA=
`82bd8747f85b78c7e17429dcf20695fd0e85a9ec213edaa1787b6e035b7b51f9`，八项 accumulator 交叉核验全过。
收据绑定完整 Git commit、Python 3.11.15、四项门槛和 `randomness_used=false`；两份 strace 禁读模式命中 0，
credential shape 命中 0，Linux 全套 `435 passed in 35.57s`。

当前 223 eligible runs 中 222 个有 finite sibling decision（coverage=`0.9955156950672646`），25/25 tasks 有
pair support；最大任务 share=`0.1887304820095044`，effective pair tasks=`11.095236634194983`。5,643 endpoints
中 5,631 个 exact-code SHA 唯一（fraction=`0.9978734715576821`）；8 个重复组全部限制在同一 physical run/
同一 task，跨 run=0、跨 task=0。该结果支持 D&B 数据资产“不是无决策 run、跨 run 逐字节复制或单任务堆量”
的正面主张，但不构成 critic 效果；最稀疏任务仅 1 pair，exact SHA 也不排除语义近重复，必须同步披露。

结构门仍只有 pair 数未过：`1473 < 1500`，差 27；`vault_open_allowed=false`。继续等待 append-only 新归档；
跨门后只先冻结 exact cohort 与版本收据，不得自动揭盲。v2 的浮点非确定性和缺少 commit/environment 绑定两次
自审失败均已撤回，只有 v3 为当前正式证据。直接证据：

- `phase1/results/prospective_structural_asset_quality_20260820_98956a8/README.md`；
- `phase1/实验记录/2026-08-20/Prospective结构资产质量审计_v3.md`。

## 0BI. 2026-08-20 0818 安全摄取完成；结构门仅 pair 数未过，仍差 27

0818 新增 8 个 append-only 归档，在固定 6 小时稳定窗后逐包处理；7 包形成不可变 transaction。
`multi-modal-gesture-recognition-8seeds.tar.gz` 在生产 intake fail-closed。credential-first 独立 auditor
双跑逐字节一致，4/4 checkpoint journals 的 task identity cardinality 均为 0；因此按精确
path/size/mtime/SHA 整包结构拒收，未按文件名补 task、未打开 env/live-event journal 或 outcome。

最终快照 `88cb791...170c8` 累计 42 transactions、249 physical runs / 223 eligible runs、25 tasks、
5,643 eligible endpoints 与 1,473 structural sibling pairs。相对 0817 完成快照，精确增量为
+7 transactions、+26 eligible runs、+2 tasks、+1,219 endpoints、+257 pairs。最大 pair-task share=
`0.1887304820095044`，exact-code unique=5,631/5,643。

commit `ea438c50...` 的独立 verifier 不 import 生产 accumulator，从 42 份登记后的 blind manifest 自行按
`(task, run, parent)` 重建 sibling 组合；真实快照双跑逐字节一致，收据 SHA=
`af494085faded657d3486f75c6b7ce7b39ae25d00e69a7d5cd405a2a769894b7`。它得到 222 finite-decision runs、
25 tasks、1,473 pairs，八项交叉计数均与 accumulator 一致；两份 strace 的 label/outcome/frozen/score
禁读路径命中均为 0。

旧 first-960 结构门要求至少 1,500 pairs、150 finite-decision runs、15 tasks、最大 pair-task share≤0.25。
当前后三项通过，只有 `1473 < 1500`，程序复算仍差 27。因此状态保持
`STRUCTURAL_GATE_NOT_YET_MET` / `PROSPECTIVE_COHORT_COLLECTING`，`vault_open_allowed=false`；不得为抢先看
正结果提前开 label vault。6 小时监控继续处理未来新归档；跨门后先冻结精确 cohort 与版本收据，再按既有
一次性协议评估。0BH 的 E2-A 关闭裁决和当前 D&B benchmark / future-only exact-stratum 主线均不变。
直接证据：

- `phase1/results/prospective_structural_rejection_20260820/README.md`；
- `phase1/results/prospective_structural_rejection_20260820/intake_completion_summary.json`；
- `phase1/实验记录/2026-08-20/Prospective0818_安全摄取与结构门复核.md`。

## 0BH. 2026-08-19 E2-A 六任务 warm 资格门失败；1200 秒边界不稳定，formal 关闭

安全 cache 修复后的新 root `balanced-e2a-warm-smoke-0ee657a-a1` 在 source commit
`0ee657a14a9bba0ddf58670f177e9e103c33720a` 完成完整 Linux/preflight/cache 双哈希门后，按冻结的
4+2 chunks 提交首批四个任务（array job `11232`）。spaceship、spooky、US-patent 的
capability/producer/verifier/safety rc 全零；TPS-May 在固定 1200 秒处返回 timeout，producer rc=3。
monitor 随即 fail closed，第二批 Nomad/Essay 未提交；实际为 4 candidate executions、0 API、0 retry，
D_search/D_val/D_test、label、score 和 scientific outcome 均未打开。follow-up 明确记录
`formal_not_launched=true`，formal root 不存在。

该 TPS 候选与 0BG 中成功运行逐字节相同，code SHA 均为
`b3e02d2f3e2452395a08e2df53f64cad1ed0242a280e200dfee8d9a821f4163f`；两次还使用同一不可变 public
data gate、同一 container、同一 `gpu27`、6 CPU/1 GPU 和四任务并发。第一次 candidate wall 为
`1119.5009202449583` 秒并产生 artifact；本次为 `1200.2556150490418` 秒、return code 143、无 artifact。
代码只固定了 sklearn split seed，LightGBM GPU 参数未显式设置其 seed/deterministic 选项；两次 early-stop
轨迹也不同。因而“1200 秒工程边界对该冻结候选不可重复”是直接证据；具体漂移来自 GPU 数值非确定性、
早停随机性还是瞬时负载则未被单独识别，不得把推断写成已证明根因。

预注册要求新 warm 六任务从零 6/6 且 0 retry，任一失败不得只补失败 task、不得自动 formal。因此本次
E2-A formal **关闭且不补跑**；既不把 3/4 工程通过解释成正结果，也不把 TPS timeout 解释成方法负结果。
若未来重开，必须另立预注册并重新批准 timeout/算力矩阵或改成显式 runtime-censoring estimand，不能沿用
本次授权悄然提高 timeout。0AJ 的评分通道确认性 KILL 与 0AO 的旧 frozen-checkpoint 污染裁决均保持不变，
不得重开；当前工作返回 NAS-Bench-style 数据/benchmark 主线与 future-only exact-stratum 时间外推。直接证据：

- `phase1/实验记录/2026-08-19/BalancedContinuation_E2A_1200秒边界不稳定_执行审计.md`；
- `phase1/results/balanced_continuation_e2a_warm_timeout_20260819_0ee657a/README.md`。

## 0BG. 2026-08-19 E2-A warm 第二次工程失败；安全等价缓存修复已结果前冻结

commit `81e05352...` 的统一 1200 秒六任务 warm 已按 4+2 QOS chunks 完成。前五个固定任务的
capability/producer/verifier/safety rc 全零；TPS-May 用时 `1119.5009202449583` 秒并生成合法 artifact，
因此 0BF 的统一 timeout 修复达到其工程目的。第六个 Essay 候选在 `11.917737385025248` 秒退出：冻结代码
调用 `microsoft/deberta-v3-base`，镜像内 PyTorch `2.5.1+cu124` 与 Transformers `4.57.6` 的组合因
CVE-2025-32434 安全门拒绝读取旧 `pytorch_model.bin`。这不是候选质量、评分或方法失败。monitor 和自动
接力均 fail closed；正式实验未提交，D_search/D_val/标签/outcome 均未打开，失败 run 不与修复 run 拼接。

共享 HF cache 已含另一 revision 的 `model.safetensors`。在 PyTorch `2.11.0+cu128` 下以
`weights_only=True` 安全加载原 bin，并逐 tensor 对照 safetensors：210/210 keys、shape、dtype 与 bitwise
value 全部相同，共 `185537893` elements / `371075786` tensor bytes；bin/safe SHA 分别为
`691d48a...b5e33` / `57cbd0c...c34e`。等价 receipt SHA=
`2156d53785303a4f203682e7c0eba7c9123ae63fe6f397d5473eee4444d25c01`。

结果前允许的唯一修复是：复制共享 cache 到新的 E2 专用根，在 main snapshot 删除旧 bin link、接入上述
逐位等价 safetensors；对整个 cache 的每个文件、目录和相对 symlink 建 SHA manifest，全部设为只读，并把
cache path、manifest SHA 和 payload SHA 写入 v2 real contract。提交前必须全量重哈希；每个 worker/独立
verifier 再核验路径与双 SHA。任务、parent/sibling、代码、split、scorer、operator、1200 秒 timeout、矩阵与
GPU/API 预算全部不变。新的 warm 必须六任务从零全跑 6/6，不能只补 Essay；通过后才允许 formal。直接审计：

首次修复 launcher `...5b78119-a1` 在任何 Slurm submission 前因 cache verifier 早于 `cd source_root`
而 import 失败；0 GPU/API/execution，失败 root 保留。只允许调整 launcher 工作目录顺序后另立新 root。

- `phase1/实验记录/2026-08-19/BalancedContinuation_E2A_HF缓存安全修复预注册.md`。

## 0BF. 2026-08-19 E2-A warm 工程门一次失败；统一 1200 秒修复已结果前冻结

commit `e86fe8e...` 的首个 QOS-safe warm chunk 在 job `11212` 上提交四个任务；spaceship、spooky、
US-patent 三项 rc 全零，TPS-May 的冻结代码在 600.2500644080574 秒统一上限处终止，producer rc=3，
未生成 submission。monitor 按协议停止，第二个 2-task chunk 未提交；D_search/D_val/标签与 scientific
outcome 均未打开，正式 60-rollout 实验未启动。失败 run 保留，不拼接进后续修复 run。

诊断仅查看 public candidate stdout：该冻结程序是 5-fold LightGBM 后再做一次全量训练，600 秒完成前三折
并进入第四折，因此 900 秒仍有较大再次截断风险。允许的唯一协议修复是把**所有六个任务**的 execution
timeout 统一改为 1200 秒，不删 TPS、不换 parent/sibling、不做 task-specific timeout。warm 仍为固定六项、
0 API、4+2 顺序 QOS chunks，hard cap=2 GPU·h；正式矩阵仍为 60 rollouts / 120 candidate executions /
60 Qwen calls、3+12 顺序 chunks，保守预计 `13.581222464241607 GPU·h`，candidate hard cap=40 GPU·h，
Slurm wall=75 分钟。只有新的六任务 warm 6/6 rc 全零才允许正式提交。直接审计：

- `phase1/实验记录/2026-08-19/BalancedContinuation_E2A_warm_timeout修复预注册.md`。

## 0BE. 2026-08-19 活跃正方法资格门：E2-A 六任务 matched continuation 支持通过

在 0BD 的三-client 生产支持门失败后，不降低原矩阵门槛，也不恢复已关闭的多保真/early-trace 路线。
E1-Q 的两任务 label-feasibility 正结果被扩展为 outcome-blind 六任务资格审计：固定任务为 spaceship、
TPS-May、spooky、US-patent、Nomad 和 learning-agency；按 seed `20260819` 对 train-only exact-two parent
作 SHA 排序，每 run 至多一个 parent，每任务冻结四个。

producer 与不 import producer 的 verifier 各自重扫 16,012 cards、三份 frozen endpoint identity、hold、两份
E1/E1-Q selection receipt 和六份 public train/description。结果为 24 parents / 24 distinct physical runs /
48 unique siblings；逐任务 eligible run=`10/27/29/10/12/10`，frozen endpoint/run 与 prior-run overlap 均为 0。
verifier 双跑逐字节一致。support SHA=`7ffb23a7577640ef61730d214f7cccd6b3c202b07356a864885b41b46ec98ac0`，
verification SHA=`c6bab92ef381c73b77c184e273eed1b444e701c9b3cf67b5cefccb72bfd65ea0`。

TPS-Dec 因极小类别未通过结果前的每层至少 20 行资格门，未降门；Nomad 以纯 CSV、12-run 支持和可独立实现的
双列 mean-RMSLE 替代。下一步只允许完成六任务 split/scorer/worker 工程门和 13 项 preflight。冻结正式矩阵为
48 broad K=1 + 12 calibration repeat = 60 rollouts / 120 candidate executions / 60 Qwen API calls；原始 E1-Q
折算 `10.247889130908273 GPU·h`、600 秒 hard cap `20 GPU·h` 已被 0BF 的无分数 warm timeout 工程修复覆盖。
任何 GPU/API 动作前必须双实现评分器与 public-only
smoke 全过；E2-A 本身不训练 critic、不构成方法收益。直接证据：

- `phase1/实验记录/2026-08-19/BalancedContinuation_E2A_六任务支持门预注册.md`；
- `phase1/results/balanced_continuation_e2a_support_20260819_733d25e/README.md`。

## 0BD. 2026-08-19 最新结果：12-run 三 client 平衡生产支持门失败，禁止原矩阵放大

0BC 只证明单一 task/seed 生产链可运行。下一步固定 3 clients×2 tasks×2 seeds=12 physical runs，任务为
spooky/spaceship，seeds=1402/1403；每 run step=4、execution timeout=300 秒、run cap=1800 秒。
按 task×seed 分成 4 个 stratum shard jobs，每个在同一 3090 上按冻结轮换顺序跑三 client；每 shard
2.25 小时，Slurm 硬上限 9 GPU·h。成功路径 72 次 operator calls，抽取重试协议上限 144，另加三次
one-token probe。

本 pilot 不比较 client score、不训练 critic、不计算 winner。完整性必须 12/12；支持 GO 还要求每 client
至少 2 个 run 有 valid 非根节点、总 valid 节点≥18、真实 finite sibling pairs≥6、每 client≥1 pair 且
最大 client pair share≤0.60。失败不降门；通过也只授权另立更大平衡 acquisition。

四个 shard jobs `11198/11199/11200/11201` 均 `COMPLETED 0:0`，12/12 physical runs、48/48 journal
rows、12/12 rc=0，resolved/final config、checkpoint、search/journal、env dump=0 等完整性检查全部通过；
总计 9,373 GPU 秒（2.6036111111111113 GPU·h）。但冻结支持门为 **0/5 通过**：

- valid-run 数 DeepSeek/Qwen/GLM=`4/0/3`；
- valid 非根节点=`7/0/4`，总数 11<18；
- finite same-parent sibling pairs=`3/0/0`，总数 3<6；
- Qwen 与 GLM 均无 pair，DeepSeek pair share=1.0>0.60。

因此裁决为 `INSUFFICIENT_BALANCED_PILOT_SUPPORT`：不得直接放大该三 client 矩阵，也不得把 12 个工程
完成当成 12 个有效解。Qwen 的 4 个 run 均结构完成但 valid 节点为 0；这是生产支持瓶颈，不是 client
score 排名。独立 verifier 双跑逐字节一致，SHA=
`7527ef2dec44aff2c4bebeca8a9f4749f11532f3c9b40f20314f3b33809dbd04`；未读取分数、未计算 winner。
直接证据：

- `phase1/实验记录/2026-08-19/BalancedClientPilot_v1_预注册与长实验预检.md`。
- `phase1/results/balanced_client_pilot_20260819_79bc2bb/README.md`。

## 0BC. 2026-08-19 最新结果：三 client 平衡生产 smoke a3 工程门通过

a3 在 source/control `f989b622...` 上 Linux 全套 `403 passed in 36.10s`；DeepSeek/Qwen/GLM 三个普通
Slurm jobs `11189/11190/11191` 均 `COMPLETED 0:0`，elapsed 依次 513/432/165 秒。独立 verifier 连跑
两次逐字节一致：3 physical runs、6 journal rows，resolved 与 final config 的四 operator client 均精确，
checkpoint state 与 search export/journal 一致，env dump=0，`score_fields_read=false`。verification SHA=
`1fbe1464ad47346bf1a8e5e086c62053f70d21c5c07a701069d777610340c658`。

这是首个真实三 generator、同 task/seed/budget 的可用生产单元，但不是效果结论。Qwen 行结构上通过且 rc=0，
日志却显示最终没有 valid solution；因此后续 12-run pilot 必须逐 client 报 valid-submission/failure rate，
不能把 job completion 当解题成功。直接证据：

- `phase1/results/balanced_client_smoke_20260819_f989b62/README.md`。

## 0BB. 2026-08-19 已关闭执行：a2 暴露原生 Slurm array/submitit 不兼容，a3 改普通作业

a2 的 Linux 全套 `402 passed`、三家 provider probe、同一 source/control commit、三行 resolved-config 四
operator 核验均通过；但三个 worker 都在 solver/operator 实例化前由 `get_slurm_id()` 失败：代码在检测到
`SLURM_ARRAY_JOB_ID` 后调用 submitit `JobEnvironment()`，而这些是原生 `sbatch --array` 作业，不带 submitit
上下文。三行均 `FAILED 1:0`，没有生成调用或效果读数，a2 只作工程失败记录。

a3 保持全部科学矩阵与硬预算不变，仅把一个 3-row native array 改为三个普通 Slurm jobs，显式传固定 client
index，使 AIRA 使用已有的 `SLURM_JOB_ID` 分支；不修改 AIRA 实验逻辑。新增测试禁止 array 环境变量重新进入
worker。a3 仍须三行全部通过 0AZ 原门，a1/a2/a3 不拼接。

## 0BA. 2026-08-19 已关闭执行：三 client smoke a1 fail-closed，a2 固定同一 source/control commit

a1 的 provider probes 与 Linux 全套 `400 passed` 均通过，但正式 worker 的 resolved-config 门在任何 Qwen
生成调用前发现：预注册目标为 `qwen3-coder-flash`，旧 source pin `4029f626...` 的 `litellm_gen2` 实际仍为
`qwen-max-latest`。Qwen 行因此 `FAILED 1:0`；DeepSeek/GLM 行在发现三行 source contract 不一致后被取消。
a1 只保留为工程失败记录，不读、不报告 score，不进入任何效果或生产支持计数。

a2 保持 0AZ 的 3 clients×1 task×1 seed、step=2、timeout 与资源预算完全不变；唯一修复是 source 与
control 都锁到同一个新的 immutable commit，并新增测试把三个生产 client YAML 与 probe matrix 逐项绑定。
仍须三行全部通过原成功门，才允许另立 12-run pilot；不得把 a1/a2 拼接。

## 0AZ. 2026-08-19 活跃工程门：三 client 平衡生产 smoke

0AY 后不从旧数据降门，改为 outcome 前显式平衡 client。第一阶段仅提交 3 clients×1 task×1 seed 的 2-step
生产 smoke：DeepSeek v4 Flash、Qwen3 Coder Flash、GLM-5；其余 MCTS/operator/task/seed/硬件/timeout
完全固定。3×1 GPU、Slurm 硬上限 1.5 GPU·h，预计 6–12 次正式 API 调用；先各做一次 one-token probe。

三行都必须由 resolved config 与最终产物证明四个 operator 确实切到目标 client，journal 恰有 2 steps，且
无 env dump，才允许另立 12-run 平衡 pilot。任一失败停止，不把 smoke 的 grade/score 当效果。a1 的旧
source pin 已被 0BA 的 resolved-config 门否决；a2 强制 source/control 同一 commit。直接预注册：

- `phase1/实验记录/2026-08-19/BalancedClientProductionSmoke_v1_预注册与长实验预检.md`。

## 0AY. 2026-08-19 最新覆盖：cross-client transfer 被共享 support 阻塞，效果不运行

结果前 commit `2e7ea07fc7ff5dfe476e6b6d8bfcf8877ff91adb` 固定 exact-stratum 与支持门；远端
Linux `399 passed in 35.11s`，producer 双跑和独立 verifier 双跑一致。11,946 train pairs 中有 11,030
个同 client、同 exact `(task, hardware, time_limit, execution_timeout)` pairs；所有 client 的跨 client
exact-code overlap pair 均为 0。

但每个 held-out test stratum 要求其他 client 提供≥50 pairs/≥2 clients 后，0 个 client 同时通过预注册的
test≥200 pairs/4 tasks/15 runs、train≥1,000 pairs/3 clients、dominant task≤0.50。最接近的
`deepseek-v4-pro` 是 415 test pairs/4 tasks/14 runs/922 train pairs，`qwen3.5-397b-a17b` 是
442/4/14/895；正式 eligible pool 为空。按协议不运行 LOSO 效果、不降门或挑 client。

这不证明 critic 无法跨 generator 泛化，而是证明现有 generator×task×environment 联合覆盖不可识别该命题。
未来数据生产应显式平衡共享 task×environment×client 矩阵；这同时服务 future exact-stratum clean scaling 与
cross-generator OOD benchmark。summary SHA=`43405484450ffea994ba69ef06b45c7c8e9db9962a8bda5e84327cf10513bb94`。
直接证据：

- `phase1/results/cross_client_transfer_support_20260819/README.md`；
- `phase1/实验记录/2026-08-19/CrossClientTransferSupport_v1_裁决.md`。

## 0AX. 2026-08-19 活跃支持门：critic 跨 generator/client 的迁移支持

在 future exact-stratum cohort 尚未新增时，允许一次 outcome-blind LOSO 结构支持审计。它只使用 augmented
`intask_split=train`，不区分 pair 胜负，不读 frozen test/vault。pair 必须同 client 且 exact
`(task, hardware, time_limit, execution_timeout)`；每个 held-out client 的 test stratum 必须在其他 client 中有
≥50 pairs/≥2 clients，client 级还须满足 test≥200 pairs/4 tasks/15 runs、train≥1,000 pairs/3 clients、
dominant task≤0.50；全局≥6 clients/3,000 test pairs 才解锁另立的 char-TFIDF/static LOSO 效果预注册。

该问题不同于 0AU 已关闭的“pair 两端 client identity 直接泄漏标签”：这里检验的是从其他 generator 学到的代码
质量信号能否迁移到完全未见的 generator。若支持门失败则不训练、不降门；若通过也不恢复 0AP 的旧 scaling
claim。直接预注册：

- `phase1/实验记录/2026-08-19/CrossClientTransferSupport_v1_预注册与执行前检查.md`。

## 0AW. 2026-08-19 最新覆盖：0812 temporal predictions 已冻结，标签继续封存

结果前 commit `37fa0f0d12bbee09772b5b051038810bca540f8a` 固定输入、scorer、denylist 与成功门；
远端 Linux `396 passed in 38.32s`，producer 双跑逐字节一致，独立数值 verifier 双跑一致。正式冻结
805 endpoints / 57 runs / 9 tasks / 103 sibling pairs；pre-cutoff endpoint ID 与 exact-code overlap 均为 0，
两个 arm 均全覆盖且无 ties。独立实现对 `static_lr`/`char_tfidf_lr` 的最大绝对分数差均为 0.0。

summary SHA=`c8f9d06dc3df8ca01b9e9bc65383fc14a0469163d93f1b87d5ccae79dd222c0b`，endpoint scores
SHA=`753ccabc54d787bba875bef7e161a6f48e0c2752236c6c0c95f332bd0349fc72`，pair predictions
SHA=`656bc5547a1e066f7c2b39f163fc49a40304518d4e3c24dfe8731a58ceacdf64`。程序不接受 vault 参数，
系统调用 trace 的 `label_vault.jsonl` open=0，`label_vault_read=false`、`accuracy_computed=false`。

因此这是可审计的预测资产，不是效果结果。0812 label vault 继续封存；只有未来 clean checkpoints 也在未知
标签下冻结预测后，才允许另立 one-shot unseal 协议。当前不得打开标签、挑 checkpoint 或把 103 pairs 当作
论文独立确认集。直接证据：

- `phase1/results/temporal_prediction_escrow_20260819/README.md`；
- `phase1/实验记录/2026-08-19/TemporalPredictionEscrow_v1_完成与独立验证.md`。

## 0AV. 2026-08-19 活跃工程实验：0812 temporal prediction escrow

在不消耗标签资产的前提下，允许已于 2026-08-13 22:19 UTC 激活固定的 `static_lr`/`char_tfidf_lr`，对
0812 temporal blind 的 805 endpoints / 103 sibling pairs 生成 prediction escrow。固定矩阵为 1 bundle ×
2 arms，0 GPU/API；只写 endpoint score、左右 margin/selection 和 SHA，不计算 accuracy，不打开 label vault。

成功门是 805/57/9/103 全覆盖、pre-cutoff endpoint ID 与 exact-code overlap=0、全 finite、producer 双跑一致、
独立 scorer 重算差≤1e-12、系统调用 trace 的 vault open=0。它只为未来 clean checkpoints 的共同一次性评测
保留可审计基线，不是新的效果主张。直接预注册：

- `phase1/实验记录/2026-08-19/TemporalPredictionEscrow_v1_预注册与执行前检查.md`。

## 0AU. 2026-08-19 最新覆盖：value pairs 全部同 client，generator-identity 强解释关闭

结果前 commit `3048d2236031e3f9b11305d98996c69f7cc053fd` 固定了 5-fold physical-run OOF 与六个
支持门；Linux 全套 `393 passed in 35.10s`，producer 双跑逐字节一致，独立 verifier 两次重建一致。summary
SHA=`59e607e5f62973d515780d8f5881cb69aa47011b5b569242df04292b0bf11cfe`。

augmented train 数据含 31,742 cards / 676 runs / 28 tasks / 11 clients / 11,946 pairs，client 缺失 run=0；
11,946/11,946 pairs 均为 same-client，cross-client 和 cross-client/same-environment 都是 0。OOF same-client
虽有 5,318 pairs / 28 tasks，但两个强制 cross-client 门失败，状态为
`INSUFFICIENT_GENERATOR_SHORTCUT_SUPPORT`；不启动 client-prior/TF-IDF/static 效果实验。

这排除“pair 两端 generator identity 直接给出标签”的强解释，不排除同-client run style、搜索阶段或模板捷径。
下一步仍是 future exact-stratum cohort；0812 temporal vault 继续封存，只允许先冻结 prediction escrow，不因
当前支持门失败而打开标签。直接证据：

- `phase1/results/generator_shortcut_support_20260819/README.md`；
- `phase1/实验记录/2026-08-19/GeneratorShortcutSupport_v1_裁决.md`。

## 0AT. 2026-08-19 活跃支持门：generator/client shortcut 结果盲审计

future exact-stratum clean-scaling 仍是确认性模型路线；在等待时间更晚新 cohort 时，新增长实验前的 0-GPU
结构资格门，检验学长提出的 value-pair 可学习性是否有足够 client 支持可被严格审计。它只读 augmented
`intask_split==train` 的 endpoint identity 与配置元数据，不读 test/frozen/0812 temporal vault，不计算 accuracy。

固定 5-fold physical-run OOF，分别数 same-client、cross-client 及 cross-client/same-environment pool；只有
known-client≥4,000、两个主 OOF pool 各≥400/6 tasks、且至少两个 client 有≥80 pairs/2 tasks 时，才允许后续
client-prior/char-TFIDF/static 效果实验。后续效果门也已在结果前冻结；失败不换 pool、client、fold 或阈值。
直接预注册：

- `phase1/实验记录/2026-08-19/GeneratorShortcutSupport_v1_预注册与执行前检查.md`。

## 0AS. 2026-08-19 最新覆盖：FML-Bench 关闭 adaptive-switch/跨 agent 策略 novelty

2026-05 的 [FML-Bench](https://arxiv.org/abs/2605.17373) 已在 18 个 ML research tasks 上统一 execution
infrastructure，比较六类 agent strategy、定义 12 个 process metrics，并用 validation stagnation 触发
greedy→multi-branch 的 AdaptiveSearch 得到正结果；[官方仓库](https://github.com/qrzou/FML-bench) 已公开七个
agent 与 runner。因此“首个 strategy/infrastructure 解耦 benchmark”“复杂树不一定优于 greedy”“process dynamics
解释表现”及 stagnation-triggered adaptive switching 均不得作为我们的 novelty，旧相关方法线关闭。

尚未被其直接覆盖、也更符合现有资产的是 NAS-Bench-style 的大规模真实 MLE-agent search-tree **数据集与 predictor
benchmark**：physical-run-clean split、真实 sibling decision、init/query cost、noise ceiling、coverage/missingness、
版本化 provenance 与 exact execution-stratum receipts。QLASS 已覆盖一般 stepwise Q/PRM，Stratified GRPO 已使用
cross-stratum bias 叙事；我们也不得泛称首创 tree critic 或 stratification。

正路线进一步收窄为：future exact-stratum cohort → train-only dev 选 checkpoint → frozen test 一次性评分 →
pair accuracy + 真实 sibling selection utility + init/query cost。若 clean scaling 仍约 0.55，则只把 capability boundary
作为 D&B 结果，不改门救正。直接证据：

- `phase1/实验记录/2026-08-19/RelatedWork_FMLBench与StratifiedSearch_防Scoop裁决.md`。

## 0AR. 2026-08-19 最新覆盖：future-only exact-stratum producer/verifier 补丁完成

针对 0AQ 的 batch-content mixing，已在学长精确 base
`92a9651f2e13a9e43623235b82c07c19721bc2ee` 上形成未推送到对方分支的可 cherry-pick 补丁。detached
implementation commit=`50b37a355931351c1d8a57b615ff20c44d445b2e`，patch SHA256=
`9f1445ae331846a4748cf82a41bebec7fd19fc28d28b4d8821c9f9333fa20f0a`，在零改动 base 上
`git apply --check` 通过，6 个新增 focused tests=`6 passed in 0.15s`。远端 Linux 又独立完成 apply、py_compile 与
同一组测试=`6 passed in 0.23s`，日志 SHA=`06af079da5b3c0b1f9aa5cf142acd46ad661205debc9b6d4a8454e4004164327`。

补丁在 shuffle/cap 前按 exact task+execution config 分层，保留 per-task cap；run 内混配 fail closed；每条 pair
携带 stratum 与 batch-content receipt；producer 解析前 credential scan，concat 前由不 import producer 的 verifier
逐条验收。学长 base 自带 legacy subtree test 已有 `5 failed, 1 passed in 0.18s`，补丁没有新增这类失败，也没有
借机修改 node-value eligibility 这个额外旋钮。

该补丁只服务时间更晚新 cohort。0AP/0AQ 的旧 scaling 裁决不变，708 条旧 mismatch 不可过滤后追认。直接证据：

- `phase1/upstream_patches/0001-Enforce-exact-experiment-strata-6-focused-tests-pass.patch`；
- `phase1/results/senior_exact_stratum_patch_verify_20260819/README.md`；
- `phase1/实验记录/2026-08-19/SeniorExactExperimentStratumPatch_交付.md`。

## 0AQ. 2026-08-19 最新覆盖：708 个跨配置 pair 定位为 batch-content mixing

结果前 commit `5b9f285c2f1a62bf82a2820346da26be96e3570c` 固定了匿名结构诊断。远端
`391 passed in 34.88s`，producer 双跑逐字节一致，独立 verifier 两次一致；summary SHA=
`7c141bd6b74ee1f3aa6e60459d272da34edb99a1f6734508510d8d75c04ccc76`。

9,001 full-train pairs 中有 708 个跨 config，share=`0.07865792689701144`，覆盖 8 tasks / 71 runs /
16 config transitions。708/708 均处于同一固定正则解析的 run-family 与同一天，0 个 run ID 解析失败；最大任务只占
`0.269774011299435`，最大 transition 只占 `0.1384180790960452`。按冻结规则归因为
`BATCH_CONTENT_MIXING_LIKELY`，并与学长 builder“batch 内按 task 组合、未按 config 分层”的代码相符。旧 pair
没有 batch-path 字段，因此不得把 `LIKELY` 升级为直接观察到的 batch identity。

0AP 的 `INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT` 保持不变；不得过滤 708 条后追认当前 scaling。下一步只实现
future-only exact `(task, client, hardware, time_limit, execution_timeout)` stratum producer/verifier contract，
并等待时间更晚新 cohort 重新冻结 learning curve。直接证据：

- `phase1/results/senior_augmented_pair_mismatch_20260819/README.md`；
- `phase1/实验记录/2026-08-19/SeniorAugmentedPairMismatchProvenance_v1_裁决.md`。

## 0AP. 2026-08-19 最新覆盖：train-only dev 支持充足，但跨配置配对触发冻结 KILL

结果前 commit `af51c8cefae81faeeafa34a673282949e99ad042` 固定 physical-run-clean train/dev、四层
nested curve 和 11 个资格门。远端完整测试 `390 passed in 35.43s`，producer 双跑逐字节一致，summary SHA=
`7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8`；独立 verifier 两次通过。

学长 augmented 数据的原始结构为 11,946 train pairs / 1,574 test pairs，split inconsistency=0；148 个 frozen-test
runs 均未进入 train/dev。固定哈希划分得到 626 dev pairs / 23 tasks 与 9,001 full-train pairs / 26 tasks；四层
训练规模 1,118 / 3,061 / 5,798 / 9,001 严格递增，dev 最大任务占比仅
`0.16932907348242812`。样本量、任务覆盖与 test 隔离门均通过。

但 dev same-experiment share=`0.9808306709265175`，full-train share 仅
`0.9213420731029885`，后者低于结果前固定的 0.95。正式状态因此为
`INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT`；不启动确认性 TF-IDF curve，不事后降门或筛 pair。下一步只做
outcome-blind mismatch 来源定位，并把 exact experiment-stratum pairing 写成未来新 cohort 的 producer/verifier
契约。当前数据最多作探索性诊断，不能修补后追认为 scaling 确认。直接证据：

- `phase1/results/senior_augmented_train_dev_support_20260819/README.md`；
- `phase1/实验记录/2026-08-19/SeniorAugmentedTrainDevSupport_v1_裁决.md`。

## 0AO. 2026-08-19 最新覆盖：学长 augmented scaling 仅为探索性，frozen test 已被反复 eval

`myfork/dojo-reproduce` 最新 commit `92a9651f2e13a9e43623235b82c07c19721bc2ee` 标题称
`exp level split shows scaling effect`，但提交内没有新增 outcome 文档、逐 run/seed CSV、日志/checkpoint receipt
或 one-shot test receipt。代码确认 `intask_split=="test"` 没有进入梯度 training pool；然而它被直接设为 Trainer
`eval_dataset`，augmented launcher 每 10 optimizer steps 读取一次，因此不再是未触碰 final test。

另一个确定 bug 是 `metric_for_best_model="eval_pair_accuracy"` 配合 `greater_is_better=False` 与
`save_strategy="best"`：磁盘“best”语义方向反了；`load_best_model_at_end=False` 又使 final 内存权重与唯一保留
checkpoint 可能不一致。当前 launcher 实际只激活 8B，不能从该 commit 本身复核 model-size scaling matrix。

裁决为 `EXPLORATORY_SCALING_CLAIM_AWAITING_ARTIFACTS_AND_CLEAN_EVAL`。这不是“test 进了梯度”的指控，但现有
test-touched checkpoint/曲线不能作为确认性 frozen-test 结果。修复路线固定为：train runs 内另建 physical-run-clean
dev、周期 eval 只读 dev、accuracy 方向改正、dev 固定 checkpoint 后单独一次 test-only evaluator；任何 0.6B--8B
GPU 矩阵仍需另报预算并批准。GPU 前可先做 0 成本的 train-only dev support/light-predictor scaling 审计。直接证据：

- `phase1/实验记录/2026-08-19/SeniorAugmentedScaling_接入审计与无泄漏修复协议.md`；
- senior commit `92a9651f2e13a9e43623235b82c07c19721bc2ee` 的 `bradley_terry.py`、
  `bradley_terry_config.py` 与 `train_aug_reward.sh`。

## 0AN. 2026-08-19 最新覆盖：确定性 failure precheck 无净收益，静态 contract 路线关闭

结果前 commit `863a3b0c33784a00da7e6cc3614e5b8d65df5a1e` 固定了无学习 AST/artifact-writer rule 与
494 unique-parent train-only pairs。远端完整测试 `389 passed in 36.84s`，producer 双跑逐字节一致，
summary SHA=`3b738ea56f11b80cc40375bd669cd4fd78310f1baade3679ec75bb1c73547b54`；独立 verifier 两次通过。

规则仅 catch 1/494 failures=`0.0020242914979757085`，同时 false-reject 1/494 successes=
`0.0020242914979757085`，paired net=0.0，task/run-clustered paired-net CI 都为 `[0.0,0.0]`，且只覆盖
一个 12-pair 小任务。failure catch、任务覆盖、paired-net 三个冻结门失败，状态为
`INSUFFICIENT_DETERMINISTIC_PRECHECK_FEASIBILITY`。旧 494 对上不得增加 sink、改规则或筛任务救活。

正面但非方法性的机制边界是：真实 execution failures 几乎都已通过语法和表面 submission-writer contract，难点是
execution-semantic，而不是可由廉价静态 lint 消除。当前仍没有解锁的新方法实验；继续以安全 corpus extension、
decision-faithful benchmark 和明确的 missingness/failure-memory 数据资产为主。直接证据：

- `phase1/results/deterministic_failure_precheck_20260819/README.md`；
- `phase1/实验记录/2026-08-19/DeterministicFailurePrecheck_v1_裁决.md`。

## 0AM. 2026-08-19 最新覆盖：现有语料无 sibling 内 operator 支持，随机化自然实验路线关闭

对 35 个 append-only transactions 的 outcome-blind 结构审计已经完成。结果前 commit
`1740d513b7ea2fc497c3906ca80771b52bdef91c`；远端完整测试 `387 passed in 31.57s`，producer 双跑
逐字节一致，summary SHA=`ce611700a9afa5a9f543f57992ef3b1033bbfa20198d8e78dc4d2759561ca0d5`，不 import
producer 的 verifier 两次均通过。

197 runs / 23 tasks / 4,424 endpoints 的边际 operator 覆盖很广：Debug=2,034、Improve=1,998、Draft=392；
但 3,229 个 nonroot parents 中 mixed-operator parent 恰为 0，mixed tasks=0、exact-two mixed parent=0。
因此冻结的 parent-support 门失败，状态为 `INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT`。这意味着现有自然语料
不能识别 parent-matched operator effect；不得用跨 parent 的边际差异冒充 sibling 因果比较。

主动 child-level operator assignment 仍可能作为未来新生产干预，但它不是当前数据的免费扩展，且没有获得本轮
授权。它必须另有真实 scheduler event stream、displaced-slot ledger、预注册和预算批准。当前继续 D&B
data/benchmark 主线，并只在既有 train-only failure benchmark 上做明确标为 retrospective 的确定性预检
feasibility；任何正结果仍需时间更晚的新 cohort 一次性确认。直接证据：

- `phase1/results/prospective_operator_support_20260819/README.md`；
- `phase1/实验记录/2026-08-19/ProspectiveOperatorSupport_v1_裁决.md`。

## 0AL. 2026-08-19 最新覆盖：Probe-First 正方法关闭；正式为 INVALID，事后诊断亦为 QUALITY_KILL

本节晚于 0AK。四个 replay shards 11160/11161/11162/11163 全部 `COMPLETED 0:0`，16/16 固定 index
完整；实际 replay allocation 为 2,603 GPU 秒=`0.723055555555556` GPU·h，连同 generation 共
25,731 GPU 秒=`7.1475` GPU·h，低于批准 12 GPU·h。冻结 primary validator 给出 coverage `4->4`、gain=0、
contract probe=4/8、full-valid `6->4`、paired quality=4，K0/K1/K2 失败、K3 通过，点裁决为
`QUALITY_KILL`。

但冻结 primary 的 V2 数值门虽正确使用 `paired_full_scores>=4`，输出键名仍硬编码成
`quality_pairs_at_least_3`；独立 verifier 正确写 `...at_least_4`，因此按预注册在比较 gates 时 fail-closed。
正式状态必须保持 **`INVALID_INDEPENDENT_VERIFIER`**，不得把事后修复追认为确认性结果。单列的 schema-only
post-outcome diagnostic 不改任何科学 scalar，只重命名该键；冻结独立 verifier 随后完成 30 次唯一 artifact
regrade，与 primary 的 verdict、gates 和 summary 全部一致，仍为 `QUALITY_KILL`。这只说明 verifier bug 没有
遮住正结果：naive prompt-only artifact contract 不提高 120 秒 coverage，且 full validity 更差。该方法线关闭，
不得调 prompt/任务/阈值救活；论文只保留其固定分母失败与工程审计记录。

0817 新语料是 post-freeze corpus extension。7 个合法 archives 已提交，标称 52 runs；LMSYS 包因 8/8 journals
均无 task identity fail-closed。credential-safe auditor 双跑逐字节一致，整包按精确 path/size/mtime/SHA 拒收，
不从文件名补 task。当前 registry=35 transactions，outcome-blind inventory 为 197 eligible physical runs、23 tasks、
4,424 endpoints、1,216 structural sibling pairs，最大 run/pair task share 分别为
`0.1116751269035533/0.15789473684210525`。旧 first-960 确认门要求 1,500 pairs，仍差 284；不得提前开 vault。

当前不再有已解锁的正方法实验。近期最可守路线回到 D&B 数据/benchmark 主线：完成 0817 安全扩展、版本化 corpus，
再对既有冻结而未读 outcome 的 benchmark 资格门做 CPU 审计；任何新的 GPU/API 方法矩阵仍需另行给出预算并批准。
直接证据：

- `phase1/results/probe_contract_ab_v2_result_20260819/README.md`；
- `phase1/results/prospective_structural_rejection_20260819/README.md`；
- `phase1/results/prospective_structural_rejection_20260819/intake_completion_summary.json`；
- `phase1/实验记录/2026-08-19/ProbeContractAB_V2正式无效与事后诊断.md`；
- `phase1/实验记录/2026-08-19/Prospective0817_LMSYS_TaskIdentityFailClosed.md`；
- `phase1/实验记录/2026-08-19/夜间正面突破路线与防Scoop_20260819.md`。

## 0AK. 2026-08-19 最新覆盖：恢复已冻结 Probe-First A/B；16 个 generation 不重跑

本节晚于 0AJ。score-channel 预注册 KILL 后，当前正方法重新限定为全新 task×seed 的 original-vs-contract
因果 A/B。审计发现 8 月 13 日冻结的 V2 并非“尚未执行”：generation job 10686 已在 commit
`a013eaa124a17c183e58f28494d4908f96389941` 完成 16/16 entries、`COMPLETED 0:0`，但 detached watcher
在 generation 完成前消失，故从未提交 replay、从未产生 grader outcome。禁止重新调用 API 或重新生成候选。

在新的 clean detached worktree 上，冻结 source SHA 全部匹配；Linux 聚焦测试 12 passed，worker、主 validator、
独立 verifier self-test 全 PASS。generation manifest 双重重建与原文件逐字节一致，SHA=
`096afbf6b1ca5779c7adf6dafea69a6e9ba431697c79245398d2a6a0d8babfe1`；固定同一 input path 后 replay manifest
双重重建逐字节一致，16 rows、SHA=
`83b57794db2f7205801db217b260175736d108d7cb92d1c29a3bc6dd8d42e3fb`。16/16 AST 通过，contract static
为 7/8；第八个失败仍进入冻结分母，不换 task/prompt/code。

首次 16-element `%4` array 在 Slurm `test-only` 被 QOSMaxSubmitJobPerUserLimit 拒绝，GPU jobs=0、outcome=0。
只修正 scheduler topology 为四个顺序 shard jobs 11160/11161/11162/11163，每 job 固定四个 index、1×RTX3090、
`01:20:00`，总 scheduler hard cap 19,200 GPU 秒=`5.333333333333` GPU·h，API=0。连同 generation 实际
23,128 GPU 秒，总上限 42,328 秒=`11.757777777778` GPU·h，仍低于原批准 12 GPU·h 872 秒。四 job 已启动，
双验证 watcher 活跃；当前状态 `RUNNING_FROZEN_PROBE_AB_REPLAY_NO_OUTCOME_READ`。直接证据：
`phase1/实验记录/2026-08-19/ProbeContractAB_V2恢复预检与启动.md`。

## 0AJ. 2026-08-19 最新覆盖：320/320 confirmatory replay 完整，但评分通道优越性预注册 KILL

本节晚于 0AI。四个 frozen shards 均在批准 TimeLimit 内 `COMPLETED 0:0`，320/320 replay 完整；执行后
17/17 数据覆盖、approval/orientation/selection/replay/result SHA、frozen analyzer 与不导入 producer 的
独立 verifier 全部通过。故这是有效的确认性负裁决，不是基础设施失败或预算内不完整。

120 秒下 finite external score 只有 15/320，keyed stdout self-report 为 92/320，两通道同时存在 7/320；
严格同 parent common support 最终只有 6 cards / 3 parents / 3 physical runs / 3 tasks。三个 parent 上两通道
tie-aware top-1 credit 均为 1.0，delta=0.0，run/task clustered 95% CI 均为 `[0.0,0.0]`，run sign
informative=0、双侧 p=1.0。预注册的方向、run-CI 下界和 sign-test 门均失败，状态必须写为
`SCORE_CHANNEL_MECHANISM_KILL`，`method_positive_claim_allowed=false`。禁止重开 cap/parser/subset 后把
available-case 结果包装为确认性正结论。

保留下来的新科学资产是描述性的 **execution cliff / selective observability**：在固定 120 秒真实 sibling
replay 上，external evaluator 通道并非质量差，而是极少产生可观测分数，使“比较两个 evaluator 谁更会排序”
本身缺乏支持。它可以进入数据集/benchmark 的 coverage 与 missingness 诊断，但不能声称确认了 external
score 优于 self-report。直接证据：
`phase1/results/score_channel_replay_execution_20260818/README.md` 与 `completion_summary.json`。

学长 0817 的 8 个新 archive 在本结果冻结后到达，只能作为 post-freeze corpus extension；不得回填上述
cohort。摄取必须继续使用 credential-first、env-member-never-read、append-only 的冻结 intake，并独立标记。

## 0AI. 2026-08-18 最新覆盖：confirmatory replay 已启动；仍保持结果盲

本节晚于 0AH。结果盲 preflight 报告 commit
`b1797dea6003d4790319d873133c97357297b36b` 已推到共享分支，远端完整依赖环境为
`384 passed in 33.84s`、rc=0；随后同一 dry-count/test-only/secret/active-job 门再次通过。正式 jobs
11127/11128/11129/11130 已在 gpu27 启动，对应 frozen 100/85/78/57 candidates，worker/approval/coverage SHA
均未改变。

首次状态检查在结果行=0 时发现 Slurm 把 shard 3 的 `01:53:40` 向上取整为 `01:54:00`。为不超过批准硬上限，
job 11130 未取消、未重启，TimeLimit 原地**降低**为 `01:53:00`。因此四片当前理论上限为 38,340 秒，加历史
20 秒共 38,360 秒，较 38,400 秒上限留 40 秒；不得再沿用 preflight 的 38,380 秒作为实际 Slurm 上限。
amendment SHA=`ba02fd171469b8b185754dcddfd17bd8fcfd4bc2bcfad69af68d6b4f7ee92147`。

当前状态严格为 `RUNNING_CONFIRMATORY_REPLAY_NO_OUTCOME_READ`：监控只看 state/rc/行数，不读取通道分数、
label value 或科学效果。四片完整后才运行 frozen analyzer；若墙钟内不完整，则报告预算内不完整，不扩预算、
不改 analyzer。直接证据：`phase1/results/score_channel_replay_execution_20260818/README.md`。

## 0AH. 2026-08-18 最新覆盖：17/17 数据门与执行前预检通过；尚未提交 GPU

本节晚于 0AG。用户接受 9 个 Kaggle 规则后，官方 prepare 全部 rc=0；完整数据覆盖 verifier 双跑逐字节
一致，17/17 tasks、320/320 candidates、0 missing，receipt SHA=
`dd986c78a2f7f411ce16a1f1b757b7b8a77140aff99a36c9a311f7b81eeb8181`。因此 0AE 的数据阻塞已解除，但
available-case 74-candidate 结果仍从未运行，也不得回补为 headline。

旧 approval 继续作废；新 approval SHA=
`b107075810e5af0da084be087cfa70740cd846d198a155116a061599e3057e09`，绑定 frozen replay、worker commit
`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`、完整 data root、container 与 pristine grader。四片 dry-count
双跑一致为 100/85/78/57，Slurm `test-only` 4/4 通过，结果行仍为 0。此前 fail-closed 共用 20 GPU 秒；本轮
四片墙钟固定 38,380 秒，二者合计恰为 38,400 秒原批准上限。RTX3090 兼容性由同容器 jobs 10850/10851
在 gpu27 的 rc=0 历史实证支持；仍排除 `projgpu7,projgpu8,projgpu33,gpu36,gpu38`。

当前状态严格为 `PRECHECK_PASS_NO_SUBMISSION`，真实 GPU job=0、outcome/label value 未读。13 项长实验预检、
job script SHA 与“test-only 编号不是提交”说明见
`phase1/results/score_channel_replay_resume_preflight_20260818/README.md`。只有该报告冻结并再次通过同一预检后，
才允许以显式 submit 模式提交四片；任一 SHA、覆盖、预算、队列或 secret 门改变均停止。

## 0AG. 2026-08-18 最新覆盖：第二轮防 scoop 收窄 novelty；设计门可达但不保证 GO

本节晚于 0AF。检索到 2026-07 的 *Progress Mirage*（arXiv:2607.25152）已经在固定 agent/tool 的 54 个
long-running cycles 中直接比较 self-verdict 与外部 world-state oracle；因此“首次证明外部 grounded evaluator
优于 self-evaluation”以及“更大 judge 不能代替外部评估”均已被覆盖，禁止再作为本项目的宽泛 novelty。
2026-05 的 *Auto Research with Specialist Agents*（2605.05724）进一步证明 evaluator-owned outcome 可以驱动
自动研究闭环；CCTS（2602.03132）则用 external fitness 学 concept-guided parent selection。它们分别占据外部测量
闭环与正向 parent-selection method 的邻近位置。

当前仍可守、但必须精确写的边界是：**真实 MLE-agent 搜索树内，同一 parent 的真实 sibling 在同一 120 秒
执行下，同时产生 in-band keyed stdout self-report 与 out-of-band pristine `submission.csv` 分数时，两通道对
frozen true quality 的 tie-aware top-1 决策价值、选择性缺失和 execution-cliff 结构**；再加 run-clean 聚类、
query/init 成本、噪声与覆盖审计、时间前瞻复现。不得把贡献泛化成一般 self-evaluation bias。withdrawn 的
AuditRepairBench（2605.04624）曾使用“evaluator-channel ranking instability”近似措辞，但作者已明确因重大实验
设计/评估问题撤稿；它只能作为措辞重叠警示，不作为有效实证基线。

outcome-blind sign sensitivity 也已核对：冻结 analyzer 使用 run 内 parent delta 均值的双侧 exact sign test。
发现集 5 个 informative runs 全正仍只有 `p=0.0625`；6/6 全正才有 `p=0.03125`。在 31/47/63/94 个
informative runs 时，最少正 run 分别为 22/31/40/57，对应 analyzer exact p 分别为
`0.029449373483657837/0.03998605682605216/0.04295654552438921/0.04945006525317994`。因此 94-run
结构使 sign 门可达，但实际 common coverage、tie 数与 run-bootstrap CI 未知，不能写成已具备 80% power 或 GO
保证。直接证据：`phase1/实验记录/2026-08-18/ScoreChannel_第二轮防Scoop与设计敏感性.md`。

## 0AF. 2026-08-18 最新覆盖：冻结 replay cohort 的结构支持通过；不解除数据阻塞

本节晚于 0AE。等待 9 个 Kaggle 规则解锁期间，对 `selection_a` 做了完全 outcome-blind 的结构支持审计；
它不打开 label vault、candidate code、replay manifest 或 replay outcome，也不计算科学效果指标。真实冻结 cohort
覆盖 17 tasks / 94 physical runs / 158 selected parents / 320 candidates，320/320 candidate IDs 唯一、跨 parent
重复 membership=0。最大候选任务为 tgs-salt 48/320=`0.15`，最大 parent 任务 24/158=
`0.1518987341772152`，最大 run 任务 12/94=`0.1276595744680851`；候选任务 HHI effective number=
`11.015490533562822`。因此未来结果不是预先由单一任务结构性支配，这是新增的正面 cohort-quality 资产。

边界必须同时保留：support 不均匀，cassava 与 google-quest 各只有 1 run/2 candidates，whale 只有 2 runs/4
candidates；所以不得声称 17 个任务都能单独稳定估计，也不得取消预注册的 run-cluster primary、task-cluster
secondary 和 task LOTO。该审计更不替代科学 replay：0AE 的 9 tasks / 246 candidates 数据门仍然阻塞，74-candidate
available-case 子集仍禁止作为确认结果。

实现 commit=`e0c5bcd6f9813afa7ced410d8f6b8d19da9edba5`；producer 双跑、独立 verifier 双跑均逐字节一致，
完整 suite=`384 passed in 32.19s`。audit SHA=`82613e1cca4ce1f5b7370a8d5dc7e4d6ab3dbdbdb74ee137c9b9da728ec81b0a`，
independent receipt SHA=`657b94eb51664aa8236622d1e932007b0de319f4b52802763c36bdf67d997528`。直接证据：

- `phase1/results/score_channel_cohort_support_20260818/README.md`；
- `phase1/results/score_channel_cohort_support_20260818/support_summary.json`；
- `phase1/score_channel_cohort_support.py`；
- `phase1/verify_score_channel_cohort_support.py`。

## 0AE. 2026-08-18 最新覆盖：正式 replay 被完整数据门阻塞；没有科学 outcome

本节晚于 0AD。用户批准的 320×120s×4-shard 矩阵尚未产生任何候选结果。五个 fail-closed GPU jobs
`11105–11108,11111` 分别在 module import 或逐任务 public-data 门失败，结果总行数=0；Slurm 实际耗时
5+4+4+4+3=20 秒=`0.005555555555555556 GPU·h`。approval SHA=`d34354dd...` 已因数据根不完整明确作废，
不得复用；未来预算必须从 38,400 秒扣除这 20 秒。

17 个 selected tasks 的 public/private 双门审计表明：dog-breed 自动 prepare 成功后，当前完整覆盖仅
8 tasks / 74 candidates；其余 9 tasks / 246 candidates 全部被 Kaggle“账号尚未接受竞赛规则”阻塞，
无其他失败类别。因此禁止把可运行的 74-candidate 子集替代确认性 headline。需要账号所有者接受 9 个规则，
或由学长提供同版本 prepared 数据，之后重新做全内容冻结、签发新 approval，再恢复 replay。

新的 outcome-blind 数据覆盖 verifier commit=`6c287d4d73758da03fd3f00e5cbc0aea6635e9b0`，要求 frozen
manifest 每个 task 的 public/private 均非空；远端完整 `381 passed in 31.28s`，真实双 receipt 逐字节一致，
SHA=`31545ae2ee318a9c0466c517a0a96d332fd0d0e0bd2f6577ccf09d04216b9774`。Kaggle traceback 中 9 条
cookie-bearing headers 已整行脱敏，cookie/credential 残留文件均为 0，原日志不发布。直接证据：

- `phase1/results/score_channel_replay_preflight_20260818/README.md`；
- `phase1/results/score_channel_replay_preflight_20260818/data_coverage_summary.json`；
- `phase1/verify_score_channel_replay_data_coverage.py`。

## 0AD. 2026-08-18 最新覆盖：前瞻 run/parent/replay/orientation 已冻结，等待精确 GPU 批准

本节晚于 0AC。用户结果盲要求立即冻结，将固定终点从 `2026-08-18T09:56:30Z` 修订为
`2026-08-18T04:35:35Z`；amendment SHA=`f3a808cee873d78e70d4fca0ebac9c745c157cc63511a12a0263522f988a5d43`，
明确记录 28 intakes、outcomes 未读、GPU/API=0。不得把本 cohort 描述为原 12 小时窗口自然结束。

双重 run gate 与独立 verifier 一致：177 个 post-mechanism physical runs、19 tasks，最大任务
26/177=`0.14689265536723164`，门通过。固定 SHA lottery 从 486 个合格 parent 选出 158 个 parent、320 个候选；
replay manifest 固定 120 秒、4 shard、同 physical run 不跨 shard，总上限
`10.666666666666666 GPU·h`。run/parent/replay 均双生成逐字节一致且由独立实现重建。

orientation 首次因缺少 NYC taxi 任务正确 fail-closed；在任何 replay outcome 产生前，以固定公开 MLE-bench
leaderboard 补入 lower-is-better 方向并双重独立验证。最终 17 selected tasks 的 orientation receipt SHA=
`81c9684741cb166bf1b4e2d7cb91ed0c8742c5040945b44d22f1c61f18baf85a`。当前总状态严格停在
`SCORE_CHANNEL_FREEZE_COMPLETE_APPROVAL_PENDING`：GPU job=0、`replay_submission_authorized=false`。

下一步只允许用户明确批准精确矩阵 `320 candidates × 120s × 4 shards`、上限
`10.666666666666666 GPU·h` 后签发 approval receipt，并使用已冻结 worker commit
`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`。未经批准不得提交。直接证据：

- `phase1/results/score_channel_freeze_20260818/README.md`；
- `phase1/results/score_channel_freeze_20260818/freeze_receipt.json`。

## 0AC. 2026-08-18 最新覆盖：前瞻门已具余量；正式 replay 执行与确认分析结果前冻结

本节晚于 0AB。唯一主实验仍是 score-channel 的时间前瞻复现；固定窗口尚未结束，正式 GPU replay
仍未获授权，任何 replay outcome 尚未产生。

1. 0816 除已精确拒收的 plant archive 外，其余 6 个 archive 均由固定 intake 合约提交为不可变 transaction，
   archive 标称合计 40 个 seed journals；当前 registry 共 28 个 intakes。监控日志持续声明
   `outcomes_read=false`，并固定在 `2026-08-18T09:56:30Z` 收口，不因已超过 150-run 门而提前停止。
2. 窗口结束后的自动链只做 CPU 双冻结：先独立重建 run eligibility，通过 150-run 与任务占比门后，再双重生成并
   验证 parent selection、120 秒 replay manifest、四个确定性 shard 和精确 GPU·时上界。它在
   `REPLAY_MANIFEST_FROZEN_APPROVAL_PENDING` 停止，不生成批准收据、不提交 GPU。
3. 正式 worker、confirmatory analyzer 与不导入 producer 的独立 verifier 已在 outcome 前实现并冻结。worker
   要求用户批准收据精确绑定四 shard、replay 数/GPU 上界、worker commit、container size/mtime、pristine
   grader SHA、data root、online-HF、API=0 与底座更新=false；每 candidate fresh workspace、120 秒固定 cap、
   append+fsync 可恢复，基础设施重试等待计入总 wall。结果不保存 raw code/stdout/stderr/grader 文本。
4. 唯一 headline 预注册为同 parent、同 120 秒、同时有 finite pristine `sub_score` 与 keyed `stdout_val` 的共同
   候选集上，两个通道各自 tie-aware top-1 预测 frozen `y_norm` 的逐 parent credit 差。primary 为 run-clustered
   CI，secondary 为 task-clustered；另有 run-level exact sign 与 task LOTO。点估计不正即 KILL；只有正点估计、
   run-sign `p<0.05`、run-CI 下界大于 0、所有 task LOTO 大于 -0.10 才 GO。
5. 精确冻结 commit `ca3bb7315078f2c4bed99fa4c33d93c2f353d670` 已在 detached remote worktree 通过
   `py_compile`、连续两次 11/11 聚焦测试和完整 `373 passed in 37.33s`；worktree clean，日志 SHA 为
   `f912026...`。因此只允许把该 commit 写入未来 approval 的 `worker_source_commit`。旧 HCE、多保真、probe、
   Qwen checkpoint 或 failure-length 支线均不因此恢复。
6. 0815/0816 新任务不能在结果后手工猜 metric 方向。已在 outcome/replay 前用 MLE-bench commit
   `507f92e1138bb6e40dac5c6ee7a6758e6424bf97` 的公开 leaderboard 顺序核对 10 个近期任务并冻结逐文件 SHA：
   dog-breed 与 ventilator 为 lower-is-better，其余 8 个为 higher-is-better；与旧 registry 重叠的 3 个任务方向
   全部一致。独立验证双跑逐字节一致，receipt SHA=`f1e5c614...` 且 `outcomes_read=false`。正式 orientation
   receipt 只能由冻结 producer 从旧 registry 与该补充表合并，再由不导入 producer 的 verifier 重建；缺失任务、
   source 冲突、selection SHA 改变或 receipt SHA 不符均 fail-closed。实现 commit `2f264757...` 已通过连续两次
   3/3 聚焦测试和完整 `376 passed in 30.33s`；post-freeze CPU chain 已等待固定窗口收口，不生成 approval。

直接证据：

- `phase1/实验记录/2026-08-18/ScoreChannel_ReplayWorker_v1_执行前冻结.md`；
- `phase1/实验记录/2026-08-18/ScoreChannel_ProspectiveAnalysis_v1_预注册.md`；
- `phase1/score_channel_replay_worker.py`；
- `phase1/score_channel_prospective_analysis.py`；
- `phase1/verify_score_channel_prospective_analysis.py`。
- `phase1/results/score_channel_execution_freeze_20260818/README.md`。
- `phase1/score_channel_metric_orientation_supplement_20260818.json`。
- `phase1/results/score_channel_metric_orientation_20260818/README.md`。
- `phase1/score_channel_orientation_receipt.py`；
- `phase1/verify_score_channel_orientation_receipt.py`。

## 0AB. 2026-08-18 最新覆盖：0816 新语料 fail-closed；failure-length 异质性关闭

本节晚于 0AA。唯一主实验仍是前瞻 score-channel 复现；正式 replay 未授权，outcome/label vault 未读。

1. 0816 新到 7 个 archives、最多 48 个 seed-runs。第一个
   `plant-pathology-2021-fgvc8-8seeds.tar.gz` 在生产 intake 的唯一 task identity 门 fail-closed，未提交
   transaction。结果前 commit `5ee342f549311ece7bc111ddd0cb7ff08b740210` 冻结只读结构诊断：raw journal
   先做 credential scan，不读 env/live-event，不输出 task identity、代码、stdout 或 grade。正式双跑 SHA
   `a0a86696...` 一致、完整测试 362 passed；16 个 checkpoint journals 中 8 个 cardinality=1、8 个=0。
   因而按 archive SHA `859f6ca0...` 整包结构性拒收，不从文件名猜 task、不部分 salvage。第三份 append-only
   registry 只增加这一精确绑定；其余归档继续按固定 12 小时窗口入库。
2. failure-mechanism × length 异质性按结果前 commit
   `acf63075237e1e2f9ceb925a81fde6d95f295ccd` 正式双跑逐字节一致，结果 SHA `d85ec8a4...`，完整测试
   360 passed。494 pairs 上整体 raw-byte longer-success credit=`0.4493927125506073`；四个合格类别 range
   `0.11340275445078934<0.15`，task-stratified permutation `p=0.4312956870431296>0.01`。裁决为
   **INSUFFICIENT_FAILURE_MECHANISM_LENGTH_HETEROGENEITY**；不翻转方向、不重组类别、不进入 utility。
3. 0AA 第 5 项 prospective length v1 在任何新 cohort outcome 被读取前标记为
   **VOID_SPECIFICATION_ERROR**：旧 LOTO 的 length-only LR 使用截断后字符数、`log1p` 和训练侧拟合系数，
   commit `990be2a` 却冻结成 raw UTF-8 bytes 固定“更长为成功”，不是同一 scorer。若继续必须另立 v2，先用旧
   494 对冻结完整模型收据，再对时间上更晚的新 cohort 一次性确认。
4. 正面资产没有回退：run-clean corpus、691-node evaluator-verified failure taxonomy、494-pair code-free
   parent-matched failure-risk benchmark 与安全 append-only intake 都保留。当前最有价值的正结论机会仍是：先让
   新语料补足 150-run gate，再 outcome-blind 冻结 parent/replay 清单，最后向用户报告精确 replay/GPU·时申请。

直接证据：

- `phase1/results/prospective_structural_rejection_20260818/README.md`；
- `phase1/results/failure_mechanism_length_heterogeneity_20260818/README.md`；
- `phase1/实验记录/2026-08-18/FailureMechanism_LengthHeterogeneity_v1_裁决.md`；
- `phase1/实验记录/2026-08-18/ScoreChannel_近期防Scoop更新.md`。

近期防 scoop 更新没有发现覆盖“真实 sibling + 同时可见两通道 + run-clean 聚类 + 时间前瞻复现”的直接工作；
AIRA_2 是最近底座，Critic Experience Bank（2607.12397）和 Failure as a Process（2607.09510）分别覆盖
经验 critic 与时间性 failure。故 novelty 必须写成选择性可观测执行反馈下的评分通道 benchmark/机制，而不能
泛称首次 external evaluation、failure process、experience critic 或 missing-feedback optimization。

## 0AA. 2026-08-17 最新覆盖：494 对 failure-risk benchmark 通过，静态 learned controller 关闭

本节晚于 0Z；唯一主实验仍是 138/150 的前瞻 score-channel 复现，正式 replay 未授权、outcome 未读。

1. 在 560/691 structured failure-memory 基础上，结果前 commit
   `526e3ad6c0d444f22d3fee99f9ab5506d7a06c39` 冻结 parent-matched 支持审计。691/691 failure code 均在
   full-journal credential scan 后找回；每 parent 只保留一个 failure，并匹配同 parent、同 physical run、不同
   code SHA 的 retained success sibling，得到 494/494 unique-parent pairs / 13 tasks / 126 runs。8 tasks 各至少
   20 pairs，dominant=134/494=`0.27125506072874495`，frozen-run overlap=0、identical-code-only=0、credential=0。
   双跑 SHA=`77b81f8d...`，完整测试 354 passed。因此允许发布 train-only evaluator-verified failure-risk
   benchmark，这是新增的正面数据资产。
2. 结果前 commit `11a866bd8e734afd977b9acfef4d1c1d5115e043` 冻结不调参的 char-TFIDF+LR，对 13 tasks
   做 LOTO；只输入 code，不输入 task/diagnostic/failure category/grade/frozen code。正式双跑一致，完整测试
   356 passed。TF-IDF micro=`0.5242914979757085`，task-CI `[0.48885059790758445,0.5851563704084254]`；
   相对 length LR 差 `-0.04453441295546556`，CI 跨 0，所有正门失败。因此 learned static-code controller v1
   关闭，不换 n-gram/截断/阈值追正数，不做 search utility 实验。
3. 预指定 length-only LR 得到 `0.5688259109311741`、task-CI
   `[0.5209636505871054,0.6253654998528029]`。这只是探索性、低容量 execution-risk association；当前协议没有
   给它独立确认门。可在未来全新 cohort 到达前冻结 length-only scorer 再确认，但不得打开现有 frozen b0/b1/b2
   追认，也不得把它写成已提高搜索 utility。
4. 当前正面论文资产因此是：run-clean 搜索树 corpus + source opportunity/retention/status contracts + 691-node
   安全 failure taxonomy + 494-pair parent-matched failure-risk benchmark。方法层仍以 score-channel 前瞻复现为
   唯一主实验；纯结构 LOTO、Qwen frozen checkpoint、TF-IDF failure controller 均已诚实关闭。
5. commit `990be2a5bbdd40b203d802ae2a0273a7b14c957b` 已在任何新 cohort outcome 被读取前冻结 length-only
   前瞻确认：必须先封存 score-channel 150-run cohort，再按时间取之后最早的 150 个 eligible unique parents；
   规则固定为 UTF-8 code bytes 较长者预测 retained-success。它是 CPU-only 的 informative-censoring 支持审计，
   当前状态 `FROZEN_NOT_STARTED`，不替代主实验；未满固定样本不看中间 accuracy，失败后不换长度定义重试。
6. commit `486e245927ac717e589ff7c9923e029c177d8b26` 已把同一 494 对发布成 code-free registry。正式双跑
   SHA=`ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747`，完整测试 358 passed，
   structural verifier 通过；每行只含 parent/run/task、endpoint identity、failure category 与 SHA，不含 raw code、
   diagnostic 或 grade。它增强 benchmark 的可下载/可审计性，但不新增方法效果主张。

直接证据：

- `phase1/results/failure_risk_pair_support_20260817/README.md`；
- `phase1/results/failure_risk_controller_loto_20260817/README.md`；
- `phase1/实验记录/2026-08-17/FailureRiskPairSupport_v1_预注册与执行前检查.md`；
- `phase1/实验记录/2026-08-17/FailureRiskController_LOTO_v1_裁决.md`。
- `phase1/实验记录/2026-08-17/FailureCensor_LengthRule_前瞻确认预注册.md`。
- `phase1/results/failure_risk_pair_registry_20260817/README.md`。

## 0Z. 2026-08-17 最新覆盖：failure memory 通过；纯结构 LOTO 与学长 frozen checkpoint 关闭

本节晚于 0Y，并覆盖 0Y 的“下一资格门”以及 0X 第 2 项的 Qwen 4B/8B 支持实验。唯一主实验仍是
150 个新 physical runs 的前瞻 score-channel 复现；当前 138/150、正式 replay 未授权、outcome 未读。

1. 结果前冻结的 train-only failure taxonomy 在 691 个 execution-error nodes 上得到 691/691 refind、
   691/691 非空 diagnostic、560/691=`0.8104196816208393` structured failures，覆盖 12 tasks；dominant
   structured task=128/560=`0.22857142857142856`，credential target SHA=0。主要类别为 schema/shape 318、
   library API/attribute 104、timeout 81、dependency/import 36；contract-related 两类为
   324/691=`0.46888567293777134`。producer 双跑逐字节一致；不 import producer 的 verifier 在完整
   `349 passed in 29.35s` 后独立复核通过。因此允许“evaluator-verified failure-memory 数据资产”主张，
   不允许 contract/controller 方法收益主张。
2. 去任务名、列名、description 与 score 的 20-task contract LOTO 没有过冻结门：same-type nearest credit=0.50
   （阈值 0.55），100,000 次标签置换 `p=0.13867861321386787`；image=0.5714、NLP=0.6667、tabular=0。
   虽有 14 个不同邻居、最大 retrieval mass=0.15，且 18/20 query 能连到至少 5 条成功经验，仍必须裁决为
   `INSUFFICIENT_TASK_HELDOUT_RETRIEVAL_SUPPORT`。不得结果后加列名/description 救 v1，也不得启动 S/C/M 三臂。
3. 学长 `dojo-reproduce` commit `7372b4eddc7dcadd84bf72edcce1daabb81d575c` 的 16K Qwen 报告保留为探索性
   证据：decision→decision final mean=50.97%，value→decision=51.35%，value→value seed-7=59.48%，无稳定
   scale effect。但其 `decision_pairs_runsplit` test 2,087 行与我们的 frozen b0/b1/b2 2,087 行逐行 multiset
   完全相同，并在训练中每 10 steps 被评估；配置还把 `eval_pair_accuracy` 与 `greater_is_better=False` 组合。
   因而 0X 曾允许的 4B/8B one-shot frozen scoring 正式撤回，checkpoint 不具备冻结确认资格。
4. 学长新 `build_cards.py` 直接解析 `env_variables.json` 取 HARDWARE，不符合 tarball scan/redact-before-parse
   安全规则，不得进入我们的 ingestion。学长提出的 RL 也不自动恢复：底座 LLM 不做微调/RL-finetune，旧
   TD/RL/HCE/多保真仍关闭。
5. 等待前瞻 12 runs 时，唯一可继续的正方法资格路线是新的 **train-only learned failure-risk controller**：
   先冻结 credential-safe code 提取、run/task-heldout split、成功负例、AUROC/AP/calibration 与固定预算 utility
   estimand；它必须是轻量控制器，不改底座、operator、任务或预算。没有预注册与支持门前不提交 GPU。

直接证据：

- `phase1/results/source_opportunity_failure_taxonomy_v11_20260817/README.md`；
- `phase1/results/contract_loto_retrieval_support_20260817/README.md`；
- `phase1/实验记录/2026-08-17/TrainOnlyFailureTaxonomy_v1_裁决.md`；
- `phase1/实验记录/2026-08-17/ContractLOTO_RetrievalSupport_v1_裁决.md`；
- `phase1/实验记录/2026-08-17/SeniorQwenCheckpoint_冻结测试污染与方向裁决.md`。

## 0Y. 2026-08-17 并行正面资产：经验支持与 public artifact contract 通过资格审计

本节晚于 0X，但**不改变**唯一主实验、138/150 gate、冻结 replay 或预算授权。它只更新在等待新 physical
runs 时允许做的 CPU 数据资产路线。

1. 整 run 排除 2,087 个 frozen decision rows 涉及的 92 physical runs 后，历史池仍有 12,316 cards / 575
   runs / 25 tasks；frozen endpoint、physical run、非空代码 SHA overlap 均为 0。每 run 有 575 个最优 finite
   `y_norm` success episodes；22/22 frozen tasks 有同任务 memory，21/22 至少 5 个。因此只支持 seen-task
   baseline，不支持 unseen-task 或因果收益。
2. 训练侧 769 个 missing sibling identities 恢复 699 个状态，其中 691 execution errors、8 grade absent；
   当前 registry 没有可行动诊断。广义 fixed-weight learned/self-evolving harness novelty 因 Argus、Gome 和
   retrieval-agent 直接邻近工作而关闭；可防守边界只剩 MLE pristine evaluator + selective missingness +
   source-opportunity provenance 的组合。
3. 结果前 commit `1dac61cf71c58e89dd084380165e48b4f1438a43` 冻结 public artifact-contract 审计。
   25 tasks 中 20 个有 public contract/description；coverage 在预检时已见，只作描述。尚未看的门以 19 个
   schema signatures、dominant share=0.10、三类 width buckets 全出现而通过；双跑 SHA 一致，完整测试
   `342 passed in 46.47s`。结果后去列名仍有 17 signatures，但 16/20 为两列，故只允许“列语义/类型非平凡”，
   不允许“所有任务宽结构不同”。缺失 5 个 image tasks 不得从 private 补齐。
4. 当前允许的下一步只有 outcome-blind contract fingerprint、task-held-out retrieval support 与凭据安全的
   train-only failure taxonomy。`标准 / contract / contract+memory` 三臂仍未授权；必须先等 score-channel
   主实验确认、支持门与功效分析，再给用户确切矩阵/run 数/GPU·时审批。

直接证据：

- `phase1/results/experience_memory_support_v11_20260817/README.md`；
- `phase1/results/public_artifact_contract_support_20260817/README.md`；
- `phase1/实验记录/2026-08-17/EvaluatorVerifiedExperienceMemory_支持与防scoop审计.md`；
- `phase1/实验记录/2026-08-17/PublicArtifactContractSupport_裁决.md`。

## 0X. 2026-08-17 最新状态：评分通道仍是唯一主实验，前瞻 run gate 达到 138/150

本节晚于 0W，并按项目级方向决定覆盖 0W 及更早小节中关于“当前主线/下一实验”的措辞。论文容器保持为
MLE-agent 搜索树的 NAS-Bench-style 数据集与系统性 predictor study；当前活跃科学问题是 execution cliff 与
评分通道。冻结发现集上，pristine 外部 `submission.csv` 分数相对 stdout self-report 的正效应仍只是机制候选，
不能写成已确认、已加速或可外推到 silent candidates。

1. **唯一主实验**仍是机制 commit 后至少 150 个新 physical runs 的前瞻 score-channel 复现：同一 120 秒、
   共同候选上的 `sub_score - stdout_val` tie-aware top-1；约 690 replays、17--23 GPU·h。它必须同时满足
   预注册资格门、任务占比门和用户对确切矩阵/预算的批准；当前保持 `NOT SUBMITTED`，禁止 optional stopping。
   22 个安全 intake 已得到 138 个唯一 physical journals；138/138 的 root creation time
   都严格晚于机制 commit，覆盖 16 tasks，dominant task=`19/138=0.13768115942028986`。因此时间与任务占比门满足，
   但距 150-run 固定门仍差 12；label vault 未读，finite-sibling parent 资格尚未冻结，不能提前开跑。最新
   控制 commit `7a4c3ee95cbdf719882b901bac9f910ebb1cb9c8` 保留冻结 scientific commit
   `90842c49dbd73d41d405a5ecdad2224ee447b375`；两个结构拒收 registry 分别不可变并按序验证，相关单测
   13/13 通过。一个缺失 task identity 的 0814 tweet 包已按完整 SHA 和不可变收据结构性拒收，不从文件名
   猜 task，也没有生成科学 transaction。门状态仍为
   `RUN_GATE_WAIT`，replay 未获授权。0815 新到的 7 个归档中 6 个正式提交为 38 个合格 run；另一个
   text-normalization 包的 8/8 journals 全缺 competition ID，已按第二份独立不可变 registry 精确拒收。
   outcome-blind producer 双跑逐字节一致，独立 verifier 重建同样的 138-run 台账；直接证据见
   `phase1/results/score_channel_prospective_eligibility_20260817_7a4c3ee/README.md`。
   commit `5f56b3b64594c6128adfed57fcb9981caf4951b6` 又提前冻结了 150-run 门后的 trusted parent selector、
   不导入 producer 的独立 selector verifier、label-free replay materializer 与第二个独立 verifier；远端完整
   `phase1/tests` 为 335 passed。该合成验收中的拒绝路径在刻意不存在的 intake root 前先行拒绝，真实 vault 未读、
   GPU/API 均为 0。这只关闭未来手工挑 parent/shard 的审计缺口，不改变 138/150 或授权状态。
2. **立即支持实验**只允许复用学长在旧 validation 上事先锁定的 Qwen3-4B/8B checkpoint，对 v11 frozen
   b0/b1/b2 各一次评分。不得重训、不得看 frozen 后挑 checkpoint；extension 单列。当前 evaluator 已就绪，
   但仓库尚缺两条 checkpoint 的绝对路径、训练配置与锁定收据，因此不得猜路径开 GPU。
3. 0U--0W 建立的 labeled-fragment、source-opportunity identity 与 failure-status registry 保留为重要数据资产：
   721/870 incomplete parents 可恢复 sibling identity，902/996 missing identities 可恢复 journal status，其中
   893/902 为 execution error。这些结果限定 benchmark estimand，但不取代评分通道确认。
4. 预注册 hurdle baseline 已完成确定性复跑与独立复核，裁决为
   `VERIFIED_FAILURE_CENSORED_MECHANISM_ONLY`。构造门通过，但 frozen 上 hurdle TF-IDF 相对 quality-only 的
   scoreability 增量仅 `+0.0200`，task-CI `[-0.0505,+0.0884]`；utility 增量 `-0.00135`，task-CI
   `[-0.01527,+0.01785]`。`method_positive_claim_allowed=false`，不得把它升级成方法主线。
5. first-960 critic confirmation、Probe-First/E1 continuation、随机日志接入、旧 HCE/TD/RL、多保真三臂和已关闭
   critic 变体均不是当前主实验；只有新的明确预注册、资格门与预算批准才能重开。已经 outcome-blind 运行的语料
   intake monitor 可继续记录元数据，但不得读取 outcome 或据其改方法。

直接证据：

- `phase1/results/source_opportunity_hurdle_v11_20260815_c89c5bd/README.md`；
- `phase1/results/score_channel_prospective_eligibility_20260815/README.md`；
- `phase1/results/score_channel_prospective_eligibility_20260816_df00f26/README.md`；
- `phase1/results/score_channel_prospective_eligibility_20260817_7a4c3ee/README.md`；
- `phase1/results/score_channel_freeze_gate_20260815_5f56b3b/README.md`；
- `phase1/实验记录/2026-08-15/ScoreChannel_正面主张与防scoop审计.md`；
- `phase1/实验记录/2026-08-15/SourceOpportunityHurdleBaseline_预注册与执行前检查.md`；
- `phase1/实验记录/2026-08-13/评分通道前瞻复现_预算与预注册草案.md`；
- `phase1/README_8B.md`。

## 0W. 2026-08-15 最新覆盖：90.56% missing identities 找回 node，99.00% 为 execution error

本节晚于 0V。稳定主线进一步收敛为 physical-run-clean、decision-local 的 MLE-agent **failure-censored
source-opportunity benchmark** 与 first-960 prospective confirmation；完整 labeled choice-set、missing-at-random
和通用 critic 方法收益仍不允许，旧 HCE、多保真、probe、TD/RL 与已关闭变体均不恢复。

1. 结果前冻结的 `source-opportunity-journal-status-v1` 在精确 commit
   `42cb6b1ac0575f26350b72519b3d558aab5a084a` 上扫描八个预定 allowlisted roots；不读 tar 其他 member、env、
   numeric grade、code/stdout、pair orientation 或 first-960。producer 与不 import producer 的 verifier 一致裁决
   `VERIFIED_HIGH_COVERAGE_MISSING_STATUS_REGISTRY`。
2. 996 个已恢复 missing sibling identities 中，902 个唯一绑定 source journal node，recovery=
   `0.9056224899598394`，source collision=0、journal parent mismatch=0。train/frozen/extension coverage 分别为
   `0.9089726918075423/0.8888888888888888/1.0`。
3. 902 个 recovered nodes 中，893 个为 `EXECUTION_ERROR`，9 个为 exit-0 但 `OFFICIAL_GRADE_ABSENT`；execution
   error share=`0.9900221729490022`。因此有限 labeled fragment 的主导缺口不是任意抽样，而是执行失败引起的
   informative censoring；剩余 94 个 targets 保持 `SOURCE_JOURNAL_NOT_FOUND`，不得外推类别。
4. 远端聚焦测试 `7 passed in 0.16s`，完整 `phase1/tests` 为 `299 passed in 26.21s`；producer/verifier 分别
   311.49/274.61 秒，产物高置信凭据命中 0。首次 `a1` 在结果前因 byte-identical journal copies 的路径 hash
   被误判为冲突而 fail-closed；新增回归测试后，`a2` 按 source SHA 折叠副本。
5. 正面论文主张改为：发布真实 MLE-agent source opportunity、retained label 与 failure-censor status 的分层数据契约，
   并证明只在成功候选内做 pair ranking 改变了部署 estimand。下一方法门只能是预注册的 feasibility→quality 两阶段
   baseline 与同预算 prospective utility；hurdle 原语本身不申新，方法收益未验证前仍以数据/benchmark 贡献为主。

直接证据：
- `phase1/results/source_opportunity_journal_status_v11_20260815_42cb6b1/README.md`；
- `phase1/实验记录/2026-08-15/SourceOpportunityJournalStatus_预注册与执行前检查.md`。

## 0V. 2026-08-15 最新覆盖：82.87% source-incomplete parents 可恢复完整 sibling 身份

本节晚于 0U。稳定主线现为 physical-run-clean、decision-local 的 MLE-agent **labeled-fragment benchmark +
显式 source-opportunity identity registry** 与 first-960 prospective confirmation；完整 labeled choice-set 主张仍撤回，
旧 HCE、多保真、probe、TD/RL 与已关闭 critic 变体均不恢复。

1. 结果前冻结的 `source-opportunity-identity-recovery-v1` 在精确 commit
   `3faf0013ff34f8a6f4c33ac99b0431b5ef394580` 上运行。producer 与不 import producer 的独立 verifier
   一致裁决 `VERIFIED_HIGH_COVERAGE_SOURCE_IDENTITY_RECOVERY`；远端聚焦测试 `6 passed in 0.13s`，完整
   `phase1/tests` 为 `292 passed in 36.39s`，产物高置信凭据命中为 0。
2. 870 个 source-incomplete parents 中，721 个能由 parent `children_ids` 精确恢复全部缺失 sibling 身份，
   parent-equal recovery=`0.828735632183908`；train=`0.8180451127819549`、
   frozen=`0.8556701030927835`、extension=`1.0`，均通过预注册门。共恢复 996 个 missing child IDs。
3. 2,328 个 source-complete、非 orphan 正控全部精确对齐。149 个不可恢复 incomplete parents 恰好全部是
   orphan parent cards；非 orphan 不可恢复数为 0。这把边界从不透明过滤收缩为一个明确、可机读的 orphan
   provenance 缺口。
4. 允许的新资产仅是 identity registry：对可恢复 parent 发布 source sibling IDs、retained/missing 标志与
   `missing_status=UNKNOWN`、`missing_outcome=UNKNOWN`。它不证明 missing-at-random，不恢复执行/评分/剪枝原因，
   也不允许把 fragment 内 predictor utility 写成完整 choice-set utility。
5. 下一门是 journal-level status recovery：在读取任何 tar member 前先做路径 allowlist、流式凭据红删与 archive
   hash 固定，再判断 996 个 missing identities 中有多少能绑定 generation/execution/evaluation receipts。没有该证据，
   不训练 censor-aware 模型，也不猜缺失机制。

直接证据：
- `phase1/results/source_opportunity_identity_recovery_v11_20260815_3faf001/README.md`；
- `phase1/实验记录/2026-08-15/SourceOpportunityIdentityRecovery_预注册与执行前检查.md`。

## 0U. 2026-08-15 最新覆盖：撤回完整 choice-set 主张，发布单位改为 labeled sibling fragment

本节晚于 0T。稳定主线仍是 physical-run-clean、decision-local 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation，但 **`choice-set-faithful` / 完整 source choice set 主张已撤回**；旧 HCE、
多保真、probe、TD/RL 与已关闭的 critic 变体均不恢复。

1. 结果前冻结的 `raw-choice-set-completeness-v1` 在精确 commit
   `6610618a89c91bd2dbea2ea5be05e8acaac11e94` 上审计 v11 的 16,012 cards、5,897 b0 pairs 与
   3,252 parents。producer 与不 import producer 的独立 verifier 一致裁决
   `VERIFIED_LABELED_SIBLING_FRAGMENT_BOUNDARY`；远端聚焦测试 `11 passed in 0.21s`，完整
   `phase1/tests` 为 `286 passed in 24.95s`，输入与产物高置信凭据命中均为 0。
2. 结构完整性没有失败：所有 parent 的发布端点均为同 run/task/parent 的 finite retained direct children；发布
   `set_size` 均等于 finite retained child 数；有 parent card 时其 `children_ids` 均包含所有 retained children。
   因此 b0 可称 **结构有效的带标签兄弟片段**，但不可称完整 source opportunity set。
3. source retention 未全过：train 仅 1,628/2,293 parents 保留完整 source set，frozen 为 651/845，extension
   为 103/114；对应 parent-equal mean retention 为
   `0.8885485280818947/0.9140433925049315/0.9678362573099415`。train 另有 10 个 source size>5 parents，
   不能用旧生成上限作默认解释。
4. 当前 pair/top-1 结果的 estimand 统一改写为 **published labeled fragment 内的决策风险**。在恢复 source
   identities、缺失状态与可识别的 missingness 证据前，不得把它外推成 agent 当时面对的完整候选集效用；first-960
   scorer 保持冻结，但最终解释也必须遵守这一边界。
5. 下一正面突破门改为 outcome-blind source-opportunity recovery：只用 lineage/source journal provenance
   衡量能否恢复完整 sibling identities、失败/未评分状态与 inclusion mechanism。它若通过，将形成比当前 pair
   文件更强的 censor-aware MLE decision resource；若不通过，诚实保留 fragment benchmark，不再使用完整候选集措辞。

直接证据：
- `phase1/results/raw_choice_set_completeness_v11_20260815_6610618/README.md`；
- `phase1/实验记录/2026-08-14/RawChoiceSetCompleteness_预注册.md`；
- `phase1/实验记录/2026-08-15/RawChoiceSetCompleteness_执行前检查.md`。

## 0T. 2026-08-14 最新覆盖：scheduler receipt 内部闭环通过，生产真实性门仍关闭

本节晚于 0S。稳定主线仍是 physical-run-clean、choice-set-faithful 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation；随机兄弟日志仍是未接入生产的 gated interventional resource。

1. commit `6a68c7dd7cdcf2fe5faf25017b3ef8bcb3a1d4b5` 新增不 import assignment producer 的
   scheduler receipt verifier。它先通过独立 assignment verifier 重建 frozen assignment，再从 canonical eligible-set
   receipts 重做 SHA-256 top-m 无放回随机化，要求 selected parent 集合、receipt hash 与 `m/n` propensity 全部精确。
2. committed budget receipt 必须绑定 assignment manifest/summary；每个 assignment ID 一对一替换一个唯一标准
   production slot 并占用一个唯一 randomized slot。若 assignment 数为 `|A|`，强制
   `B_standard_after=B_before-|A|`、`B_randomized_after=|A|`、`B_total_after=B_before`；任何重复、漂移、
   outcome-bearing key、凭据形状、非 canonical JSON 或时间逆序均 fail-closed。
3. 精确 commit 的全新 Linux worktree 中，相关测试 `19 passed in 0.39s`，完整 `phase1/tests` 为
   `275 passed in 25.48s`；安全扫描可疑文件名 0、高置信凭据 0，下载后 5 文件 hash mismatch=0。Windows 本地
   完整套件的两项失败均来自既有测试缺 SciPy，Linux 全套通过排除了本轮回归。
4. 本轮没有伪造生产 true flag。通过只允许写
   `upstream_selection_probability_reconstructed_from_declared_eligible_sets=true`、
   `committed_budget_decrement_internally_consistent=true` 与 `budget_conserved_within_receipt=true`；同时强制
   `eligible_stream_completeness_verified=false`、`external_scheduler_receipt_authenticity_verified=false`、
   `upstream_selection_probability_verified_by_assignment=false`、`actual_production_budget_decrement_verified=false`、
   `production_activation_authorized=false`、`causal_claim_allowed=false`。
5. 下一门必须来自真实 scheduler：只读 append-only eligible-event stream、连续 sequence/window 完整性、实际预算
   transaction 与 pre-outcome sealing。未经与学长共同确认生产接口和机会成本，不得接入其日常语料生产；E1 批准
   不自动授权该 sidecar，E2/E3 仍关闭。

直接证据：

- `phase1/results/scheduler_receipt_verifier_20260814_6a68c7d/README.md`；
- `phase1/verify_randomized_sibling_production_receipts.py`；
- `phase1/tests/test_randomized_sibling_production_receipts.py`；
- `phase1/实验记录/2026-08-14/RandomizedSiblingLogging_v1_设计冻结.md`。

## 0S. 2026-08-14 最新覆盖：随机兄弟日志契约通过合成验收，生产接入仍未授权

本节晚于 0R。稳定主线仍是 physical-run-clean、choice-set-faithful 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation；E1-Q 仍只是标签可行性支线，E2/E3 仍关闭，也没有切回旧 HCE、多保真或 probe。

1. 近期防 scoop 审计进一步确认：AgentRM、ReLoc、DataPRM、CePRM、PRO-Step 与 UATS 已覆盖 MCTS/agent
   状态价值、同 parent revision/sibling 监督、环境感知过程奖励和不确定性预算分配等原语。因此 tree critic、
   sibling pair、listwise、hurdle 或 uncertainty 本身均不申新。可防守的正面资产收缩为真实 MLE 场景下
   physical provenance + exact choice set + outcome-blind randomized intervention + cost/propensity 审计。
2. commit `59b5b8c698c6d687510cc184034d887619324243` 冻结 Randomized Sibling Logging v1：输入只允许
   parent/sibling 身份与哈希、上游选择概率声明、receipt hash 和 displaced-slot 声明；禁止 code、score、label、
   execution status 等 outcome-bearing 字段。Broad 层每 sibling K=1；task-fixed calibration 层 K=2；兄弟顺序与
   rollout seed 独立哈希随机化，并写出严格 propensity。
3. 精确 commit 的全新 Linux worktree 中，聚焦测试 `25 passed in 1.04s`，全部 `phase1/tests` 为
   `263 passed in 27.85s`。独立 verifier 不导入 producer，逐项重建 6 parents、2 tasks、16 rollout jobs 与
   16 candidate-execution slots，裁决 `VERIFIED_OUTCOME_BLIND_RANDOMIZED_SIBLING_ASSIGNMENT`；产物 outcome=0，
   远端可疑文件名与高置信凭据命中均为 0，下载后 16 个文件 hash mismatch=0。
4. 该验收明确不是生产闭环：`actual_production_budget_decrement_verified=false`、
   `upstream_selection_probability_verified_by_assignment=false`。只有生产 scheduler 独立签名真实被替换 slot、
   真正扣减日常预算并记录上游 propensity 后，才可称 budget-neutral interventional logging。未经与学长共同确认，
   不得接入其约 60 runs/day 的生产，也不得宣称因果效果或方法收益。
5. 第一轮远端验收在测试前暴露既有 LFS 404；坏 run 保留。对应 1,119,807-byte 对象经 43-member tar 流式扫描
   （可疑名 0、高置信凭据 0）、OID 校验后仅补传既有对象；集群对精确 commit/path 重新 fetch 并重算完整 SHA，
   状态 `VERIFIED_REMOTE_LFS_OBJECT`。这修复仓库可获取性，不改变任何科学结果。
6. prospective monitor 截至 `2026-08-14T11:09:48Z` 仍为 128 baseline、0 ready transaction、0 outcome read；
   学长 `dojo-reproduce` 仍为 `2cb6f0c57790407cae84070d3eb475da3cbe9597`。在新 archive 到达前不读取或调参。

直接证据：

- `phase1/results/randomized_sibling_logging_contract_20260814_59b5b8c/README.md`；
- `phase1/实验记录/2026-08-14/RandomizedSiblingLogging_v1_设计冻结.md`；
- `phase1/实验记录/2026-08-14/最新直接竞品与正面突破_防scoop审计.md`；
- `phase1/实验记录/2026-08-14/LFS对象_a96e41b_补传审计.md`。

## 0R. 2026-08-14 最新覆盖：E1-Q 标签可行、label repeatability v2 入主线，方法收益仍未解锁

本节晚于 0Q。稳定主线仍是 physical-run-clean、choice-set-faithful 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation；没有切回旧 HCE、多保真或 probe。Balanced continuation 只是 gated 支线。

1. 0Q 的 Qwen smoke fail 后来被定位为 task-type validator bug：accuracy 任务的 boolean submission 被错误强制
   为 float。immutable artifacts 在 0 新执行/API/GPU 下重验为 2/2 合规。随后另立 fresh-anchor E1-Q，固定
   `qwen3-coder-flash`、one-shot/0 retry、两任务各一新 anchor、两 sibling、K=2、H=1，并排除旧 E1 runs 与
   frozen b0/b1/b2 overlap；这改变 operator policy，不能追认旧 DeepSeek E1。
2. E1-Q 在 source commit `0d1ca6fd948d24f23d4abecc3298d8ff6ef53974` 完成两阶段 8/8 rollout、
   16/16 candidate processes、8/8 operator calls，retry/analyze/D_test read 均为 0。complete-coverage 前
   `sealed_values_opened=false`，之后一次性打开 16 receipts；独立 archive verifier 重算 8 rollout、4 sibling、
   2 task 和 summary，summary SHA=`f98ee3d663fab2d1085ec9cefcf14c36d17e15b966ba45eb90ef538f49f92d11`。
3. 两任务的 sibling winner 在两次 replicate 中均一致（2/2），四个 balanced `V_1` labels 非退化，按预注册裁决
   为 `E1Q_LABEL_FEASIBILITY_OBSERVED`。但只有 2/8 positive gains、0/8 达 `0.01` practical delta；实际
   candidate 成本 `1.3663852174544364 GPU·h`。因此这是 label-design feasibility 正结果，不是 continuation
   方法收益。
4. compact collection 漏了预注册要求的 execution-status 明细，未改写原 collection；status-only reporting
   repair 从已过独立 worker verifier 的 receipts 导出：warm=6 ok+2 execution_error，continuation=6 ok+
   1 execution_error+1 timeout，两阶段均 6/8 artifact 被 D_search/D_val 评分。它支持未来把 validity 与
   conditional gain 分开设计，但不证明 hurdle critic 有效。`primary_gate_claim_allowed=false`、
   `e2_e3_unlocked=false` 不变。
5. 旧 `noise_ceiling.py` 的 node bootstrap 实际没使用 resampled nodes；original single 与 repeat mean 也不可交换，
   所以旧 `0.9923/0.9578` 不再作 release-grade ceiling headline。预先冻结的 v2 在 commit `4e3bebe` 通过
   4 项聚焦和全部 256 项远端测试；独立 verifier 重建三种 retry sensitivity、PAVA、九个 v11 transport 与
   2,000 次 task bootstrap。
6. v2 在 207 cards/10 tasks/3,017 pairs 上的 original-vs-first-regrade raw agreement=
   `0.9658601259529334`，task-cluster CI=`[0.9438143714671886,0.9913402891372938]`。frozen b0 transported
   repeat agreement=`0.9134305309964227`，CI=`[0.8353851659068688,0.9494041168867747]`；对称独立误差
   模型量=`0.9488254145489123`，CI=`[0.8571329199113228,0.9682215874512448]`。但 measured-task pair
   coverage 只有 `0.732977303070761`，必须写明 10→22 task extrapolation，不能称全任务 empirical ceiling。
7. 相邻领域已明确覆盖 candidate-set sampling 导致 metric/模型排名反转（推荐系统）和 NAS predictor 的
   rank/search-utility/query-cost 比较；因此统计原理本身不申新。可防守核心收缩为真实 MLE-agent 的 physical run、
   parent choice set、effective support、gap/noise/cost 与 prospective boundary 的可执行审计标准。v11 audit 已验证
   九个 pair sets；frozen b0 为 1,498 pairs/845 parents/92 runs/22 tasks，train--frozen 四层 overlap 全为 0。
8. prospective monitor 仍健康但没有 activation 后新 archive：128 baseline、0 ready transaction、outcomes
   unread。学长 `dojo-reproduce` 最新仍为 `2cb6f0c`；其 checkpoint direction bug 尚需在下一轮训练前修复。

直接证据：

- `phase1/results/balanced_continuation_e1q_20260814_0d1ca6f/README.md`；
- `phase1/results/label_repeatability_v2_20260814_4e3bebe/README.md`；
- `phase1/results/decision_corpus_audit_v11_20260814/README.md`；
- `phase1/实验记录/2026-08-14/ChoiceSetFidelity_当前主张边界.md`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_E1Q_裁决.md`；
- `phase1/实验记录/2026-08-14/LabelRepeatabilityAttestation_v2_裁决.md`。

## 0Q. 2026-08-14 最新覆盖：Qwen 执行门与 selective-execution 二次路线均关闭

本节晚于 0P。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；没有切回旧 HCE、多保真或 probe。

1. fresh-anchor Qwen execution-only smoke 在 commit `d89311a` 的新 root 上完成 2 个真实候选执行、0 次
   operator API 调用、0 次 frozen/first-960 读取。tabular 通过 public submission shape；spaceship 虽进程
   rc=0，但 boolean prediction 无法按 float 解析。冻结门要求 2/2，正式状态为
   `VERIFIED_QWEN_EXECUTION_SMOKE_FAIL`，因此 Qwen E1-Q 不得启动、不得换 prompt/model/cap 或补样本追认。
2. 随后冻结 `selective_execution_v11_retrospective_discovery_v1`，只在既有 v11 train-run OOF 的 1,520 个
   exact-two parents 上问：char-TFIDF、static LR 与 frozen head 三者一致且高置信时只执行共同 winner，
   其余执行两个，能否形成安全 cost--risk 点。协议明确承认 FOREAGENT、CIPHER、AgentSwift、CORA 与
   selective-code literature 已覆盖原语；本轮即使为正也只能是 benchmark operating point。
3. 科学 commit `7a1562a4506f17d713467956c797fb0d3226a8c5` 的 producer 与不 import producer 的 verifier 一致裁决
   `SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK`：selected=293 / runs=129 / tasks=22；候选数节省
   `0.09638157894736842`，但 micro/run/task accuracy 仅
   `0.5494880546075085/0.5572152868664496/0.5575913930507589`，run/task CI 均跨 0.5；相对 matched
   char-margin 的 task delta `+0.03502779307071244`，CI=`[-0.05286426757718625,0.13190540852024105]`。
4. q=0.05 的 65-parent/18-task 描述点不满足冻结 support/节省门；margin 在 unanimous pool 内相对 CRC
   subset 也没有富集，故禁止改 q、删 task 或换 vote 集合救活。本路线关闭，不进入 first-960 sidecar。
5. 首次 postflight 因仍在追加的 `run.log` 被放进 manifest 而哈希失败；坏 manifest 原样保留。commit
   `98065c85c1900c6b1ba1e0632204ab8ad63d44db` 只修日志关闭顺序；postflight repair 没有重跑 producer/
   verifier，独立科学裁决不变。
6. 学长 branch 最新 `2cb6f0c` 把 best metric 改成 `eval_pair_accuracy`，却保留
   `greater_is_better=False` 与 `save_strategy="best"`；这会反向选择后续 checkpoint。该 bug 晚于 0812 日志，
   不能追溯解释既有 1.7B--8B 结果；下一轮训练前应单独修成 `True` 并做 best-checkpoint smoke。

直接证据：

- `phase1/results/balanced_continuation_qwen_execution_smoke_20260814_d89311a_a2/VERDICT.md`；
- `phase1/results/selective_execution_v11_20260814_7a1562a45/README.md`；
- `phase1/实验记录/2026-08-14/SelectiveExecution_回顾性发现裁决.md`；
- `phase1/实验记录/2026-08-14/学长DecisionTrainer_checkpoint方向审计.md`。

## 0P. 2026-08-14 最新覆盖：真实 E1 方法结果作废；Qwen 备选过门但 production DeepSeek 仍关闭

本节晚于 0O。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；balanced continuation 仍是 gated 支线，**没有得到正方法结论，也不是负方法结论**。

1. 冻结 E1 在 source commit `e59a759d99dd490b6f8a0011c66dd7c772307b28` 完成 8 个 rollout、
   16 次 candidate attempt、14 次实际 candidate process、8 次 operator API 调用；retry/analyze/D_test
   读取均为 0。候选累计墙钟为 `2047.6709687478572` 秒，即 `0.5687974913188492` GPU·时；537 条顶层
   manifest 记录逐一重算均匹配。collection 的独立 verifier 不 import producer，重建了 8 rollout、
   4 sibling、2 task 行。
2. 该 collection 的零分、tie 和 `0/8` positive gain **全部撤回为不可解释**。首个确定根因是 scorer
   接口不一致：public `sample_submission.csv` 覆盖 `D_search ∪ D_val`，而 v1 scorer 错误要求提交 ID
   恰好等于其中一个 private 10% 子集。干净 commit `f352b013c67fb1b98b17391ba32711faaa780367` 的
   零执行重放把有效提交从 `0/16` 修正到 `6/16`，但这 6 个全是 warm artifact；continuation 仍为
   `0/8`，因此可配对 rollout 为 0。
3. 第二个确定根因是 operator 完整脚本失败：8 个 continuation 调用全部恰好达到 8192 completion-token
   上限；失败谱系为 2 个 `invalid_format`、2 个 `SyntaxError`、4 个 `NameError`。旧 extractor 可能从
   截断响应中取最后一个短代码块，且旧 run 只保留 response SHA、没有可恢复的原始响应，故不能事后补算。
4. scorer 与完整脚本 gate 已修复，并以 mode-0600 raw response 做 hash binding。先验 Qwen 备选探针恰好
   调用 2 次、0 GPU、0 candidate execution：两任务均 `finish_reason=stop`，分别输出 172/104 行、
   1579/1014 completion tokens，状态 `PASS_OPERATOR_ONLY_GATE`。但冻结 E1 的 production operator 是
   DeepSeek，不能用 Qwen 结果宣称原路径已修好。
5. 因此另立 production-matched 两调用门，精确复用 `deepseek-v4-flash`、temperature=0.6、top_p=0.95、
   max=8192、system role 与 180 秒 timeout。spaceship 返回 178 行完整代码并通过；tabular 再次达到
   8192 tokens、`finish_reason=length`，只在 `reasoning_content` 留下未闭合输出，最终状态为
   `FAIL_PRODUCTION_MODEL_OPERATOR_GATE`。原 production path 保持关闭；Qwen 只能作为未来**新 operator
   contract** 的候选，不能追认旧 E1。
6. 因此 `primary_gate_claim_allowed=false`、`e2_e3_unlocked=false`。原 E1 已消耗预算不能被 probe 覆盖；
   任何真实 rerun 都是新的 GPU/API 实验。若换 Qwen，还同时改变 operator policy；必须使用新 run root、
   新预注册和未被本轮 D_val 揭盲影响的 fresh scientific anchors，不能沿用旧批准自动启动。
7. 复现审计发现两个既有 LFS 结果对象曾只有 pointer、GitHub 返回 404：681687-byte fixed-scorer tar 与
   17145534-byte frozen-embedding tar。两者在补传前分别完成 tar 路径、链接、文件名与内容凭据扫描，
   unsafe/name/content hits 均为 0；只补传这两个既有对象后，集群端按 commit 重新 fetch 的 SHA-256 分别为
   `80a21f8d05d52fd602edd61c0e2538c3b18910ca92cefb24ca6040ad4937d379` 与
   `096a3581bfce48c83019f3440e88089d4b8a4dd0a768224493f892941a3d64f7`。语料契约不变：未来只上传
   不可变 batch 一次，merged corpus 仍由 release descriptor + `rebuild_corpus.sh` 逐字节重建。

直接证据：

- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/README.md`；
- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/adapter_replay_f352b01.json`；
- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/operator_probe_summary_1fc6031.json`；
- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/deepseek_production_probe_summary_9146d82.json`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_E1_裁决.md`。

## 0O. 2026-08-14 最新覆盖：Linux real-adapter mock 关门，E1 获批但仍受 preflight 约束

本节晚于 0N；稳定主线和 balanced-continuation 的 gated 地位不变。

1. 精确 commit `eb2e693b2e1cca931148c504c68239b203b82731` 在干净 Linux worktree 通过 36 项聚焦测试、
   157 项完整 `phase1/tests` 和 13/13 preflight。正式 0-GPU mock 为 1 rollout、2 candidate、2 D_search、
   2 D_val sealer、1 operator process，retry/analyze/API/GPU/Slurm 均为 0。
2. 不 import mock producer 的 verifier 报告 `VERIFIED_ZERO_GPU_REAL_ADAPTER_MOCK`：visible D_val fields=0、
   D_test rows read=0、实际 sealed mode=0600；archive SHA-256 为
   `a58c86a10540b40daecebc118fe8179db9c6dde6b2e516c20ef67ceab56836a5`。
3. 该结果只关闭 synthetic process/receipt boundary，不证明 production container capability isolation，也不证明
   balanced label 或 search utility。此前四次 remote/env/LFS/import/post-scan 失败全部保留，未被成功 run 覆盖。
4. 用户已明确批准既有 E1：2 tasks × 1 anchor/task × B=2 × K=2 × H=1 = 8 rollout jobs、16 real
   candidate executions、预计 3.24 GPU·时。批准不等于立即提交：真实 80/10/10 split、public-only executor、
   D_search/D_val 隔离、真实 assignment 与 13 项 preflight 必须先全部 PASS；E2/E3 未获批准。

直接证据：
- `phase1/results/balanced_real_adapter_mock_20260814_eb2e693/`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_RealAdapter_接口审计.md`。

## 0N. 2026-08-14 最新覆盖：真实 adapter 边界已冻结，执行实现仍待完成

本节晚于 0M。稳定主线与 balanced-continuation 的 gated 地位均不变；本轮是 0-GPU/0-API 接口审计，
不是方法正结果。

1. 当前 MCTS 路径会生成多个 child、自动 debug、调用 analyze，并在抽取失败时重试；它不能满足每个
   transition 恰好一次 operator call、一次执行、零重试的 equal-K 干预，真实 adapter 必须绕开该路径。
2. 当前 `MLEBenchTask.step_task` 默认在进程内读取完整 private answers；旧 HCE 又是 50/25/25，且把
   `dval_score` 放入 orchestrator 可见的 `AUX_EVAL_INFO`。它不能通过改 config 变成当前 80/10/10、
   D_search-only visible、D_val mode-0600 sealed、D_test never-read 的 full-locked 契约。
3. `balanced_continuation_real_contract.py` 已冻结 worker、public execution、D_search、sealed D_val、visible
   step 与 operator request/response 的 exact-key schema、SHA identity、finite-number、POSIX path、
   one-call/no-retry 和 credential fail-closed 规则。新增 12 项接口测试；连同 assignment/worker 测试共
   34 项通过。
4. 当前尚未实现真实 public-only executor、80/10/10 split、隔离的 D_search scorer/D_val sealer 与独立
   collection verifier。下一步仅做 0-GPU mock adapter 端到端烟测；E1 的 8 jobs/16 real executions/
   预计 3.24 GPU·时仍需明确批准，不得因 schema 测试通过而自动启动。

直接证据：
- `phase1/balanced_continuation_real_contract.py`；
- `phase1/tests/test_balanced_continuation_real_contract.py`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_RealAdapter_接口审计.md`。

## 0M. 2026-08-14 最新覆盖：balanced-continuation 完整 synthetic worker E0 关门

本节晚于 0L。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；balanced continuation 仍只是 gated 方法扩展，没有变成论文已证实正结果。

1. 在精确 commit `f7b75a5b7d353116a0ecb0ca94ed3e7ca9870585` 的干净远端 worktree，22 项聚焦测试、
   全部 143 项 `phase1/tests` 和 13/13 preflight 均通过。正式 E0 随后完成 24 个 rollout、72 次 synthetic
   candidate attempts、48 次 continuation operator calls；24 个 workspace 路径和 token 均唯一，retry 与
   replacement 均为 0。
2. assignment 由不 import producer 的 verifier 独立重建；每个 rollout 又由独立 worker verifier 重验代码链、
   operator、outcome、backend receipt 与 workspace；collection verifier 验 exact-K、完整 block、总执行数和
   workspace 唯一性；最后 452 个文件逐一重算 SHA，mismatch=0。
3. checkpoint/resume 现为 fail-closed：PENDING 没有完整 durable receipt 时禁止自动重跑；有 receipt 时也必须在
   继续花费前重验全部既往代码/receipt/workspace 链。回归测试覆盖 durable promotion、ambiguous pending、语义篡改、
   workspace collision、NaN/Inf、timeout/invalid 与 duplicate token。
4. 本轮 GPU=0、API=0、没有读 frozen cohort、label vault 或科学 outcome。synthetic utility 只用于工程分支覆盖，
   其均值不得进入论文结果或方法收益叙事。当前 production worker 仍未实现真实 aira-dojo backend 与 pristine
   evaluator adapter，因此真实 E1/E2 仍未启动，原预算审批门不变。
5. 第一次远端启动在创建 worktree/实验目录之前因 `env_setup.sh` 与 Bash nounset 不兼容而失败；修复为先 source
   再启用 nounset 后重跑。该失败已与成功证据一并归档，没有被从记录中删除。

直接证据：
- `phase1/results/balanced_worker_e0_20260814_f7b75a5/README.md`；
- `phase1/results/balanced_worker_e0_20260814_f7b75a5/verification_summary.json`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_E0Worker_裁决.md`。

## 0L. 2026-08-14 最新覆盖：版本化 corpus 契约与 equal-K E0 已独立复核

本节晚于 0K。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；没有切回旧 HCE、多保真或 probe，也没有把工程通过写成方法正结果。

1. 学长确认的 LFS 契约已实现为 append-only batch registry + release-specific prefix lock +
   release-specific serialization protocol + 输出 rows/bytes/SHA 三元门。v6–v11 已在远端从 fork
   LFS materialize，并与保留的原始 merged files 逐字节 `cmp` 全部通过；最终实现 commit 为
   `73fd5f6a927e8deeb07d84372e1ba87fb7d2b3c5`。
2. v4/v5 继续标记不可恢复：历史 8,607/9,323 行与现存 prefix 8,579/9,433 行不符，首次 LFS
   发布前同名 batch 已被替换，且没有原 merged 备份。不得制造假 release 或声称任意旧版均已复现。
3. 直接用最新 transformer 重放 v9 虽仍为 14,323 行，却改变 744,500 bytes；因此后续版本发布
   必须同时冻结 batch、顺序、变换协议和输出 hash，不能只看行数。
4. equal-K outcome-blind E0 已在精确 commit `4ff44dd` 通过 34 项测试、13/13 preflight、producer、
   不 import producer 的独立 verifier 与确定性 replay：4 anchors、3 siblings、K=2、H=2、24 jobs，
   assignment manifest SHA=`122628cc49f92a22aeb9acbdacee3ea18828b10edabc665d655c8aa930e5a726`。
   这是 0-GPU/0-API 工程证据，不是方法收益；真实 E1/E2 仍受已记录预算门约束，尚未启动。
5. LFS pull 错 remote、当前协议漂移、临时目录缺失、v11 taxonomy 漏项和 v10 helper 漏 `cd` 等失败
   均已保留日志；只有修复后通过 exact hash/`cmp` 的结果进入裁决。

直接证据：

- `phase1/实验记录/2026-08-14/CorpusLFS_版本化逐字节重建_裁决.md`
- `phase1/results/corpus_release_contract_20260814_73fd5f6/summary.json`
- `phase1/results/balanced_manifest_e0_20260814_4ff44dd/README.md`

## 0K. 2026-08-14 最新覆盖：equal-K continuation 正方法转为 outcome-blind 工程实现

本节晚于 0J；稳定主线不变，balanced continuation 是 gated 方法扩展，真实 GPU/API 长跑尚未启动。

1. 最新原始论文查重确认：rollout-tree return/Q 聚合（RTMC）、adaptive branch rollout（PaTR/TRACE）、
   off-policy tree-search correction、OCBA-MCTS 与 fixed-budget BAI 均已有直接先例。不能把 equal sampling、
   future return 或 budget allocation 单独写成 novelty。
2. 可防守组合收缩为：真实 MLE program-search 节点 + physical-run provenance + historical behavior-policy label
   对 matched equal-K interventional label + fresh workspace/pristine evaluator + 不微调底座的轻量 continuation
   critic + 相同真实执行预算下的 D_val utility。
3. `V_H^π` 明确定义为已执行节点在固定 continuation policy/horizon 下的 future best utility 期望；这是
   post-execution expansion decision，不与“尚未执行 sibling 先跑谁”的 pre-execution benchmark 混称。
4. 直接 FIFO/BFS 被否决：它不保证 sibling 获得 equal compute；当前 Python interpreter 只重启 process、不清空
   working directory，候选可留下 cache/model/temp 文件，必须每个 rollout 独立 fresh workspace。
5. outcome-blind assignment producer 与不 import producer 的 verifier 已实现；blocked schedule 保证每个 sibling
   exactly K、每个 replicate block 含全部 siblings、inclusion probability=1、order probability=1/B，并在 JSON
   parse 前拒绝 credential shape。当前 synthetic tests 通过，尚未证明真实方法有效。
6. 真实矩阵已先给预算：E1 为 8 jobs/16 candidate executions/预计 3.24 GPU·时；E2 为 72/216/43.76；
   E3 候选为 384/768/155.58。按硬门，先完成 worker/workspace/evaluator smoke；没有新批准不启动 E1/E2 长跑，
   E3 更不预授权。
7. 0809 LFS object 已从全新集群 clone 端到端 pull：commit `8b38d9a`、1,940 行、56,424,624 bytes、SHA
   `133500c0fd731201bde35f44598ada17430684ed2b762326ae006101722a3094`，不依赖 big-data-storage。

直接证据：
- `phase1/实验记录/2026-08-14/BalancedContinuation_可识别正方法与查重.md`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_真实实验预算门.md`；
- `phase1/balanced_continuation_manifest.py`；
- `phase1/verify_balanced_continuation_manifest.py`；
- `phase1/results/corpus_lfs_audit_20260814/fresh_pull_receipt.json`。

## 0J. 2026-08-14 最新覆盖：历史 policy 自然实验失效；LFS 发布真源纠偏

本节晚于 0I；稳定主线仍是 run-clean、decision-local 数据集/benchmark 与 first-960 前瞻确认，未切回
HCE、多保真或 probe。

1. 0802–0804 MCTS 对 0805 “sequential/no-selection” 的历史自然实验正式判
   **`HISTORICAL_POLICY_AUDIT_INVALID_NO_CAUSAL_CLAIM`**。冻结实现通过 28 项测试和全部 13 项预检后，
   因一个非 root 节点 `parents=[]` fail closed；另有 archive 超过预注册 member byte cap。正式结果未产生，
   grade/outcome 未读。
2. 两臂在正式结果前已知底座、timeout、children、总时限和 commit 不同；提交历史也没有可追溯的
   sequential selection 实现。因此旧 fragment 两任务“0.73 对 0.56”撤回为 confounded exploratory，
   不进论文主张。下一可识别实验必须是显式 matched fixed-sibling/equal-K continuation 新采集。
3. 学长确认的语料发布真源是 Git LFS 中每批只上传一次的不可变 card batch，由对应版本 manifest/
   `rebuild_corpus.sh` 重建；合并语料不得继续作为反复上传的真源。审计发现该设计直到 commit `da27852`
   才实际落地：v4/v5 提交本身没有对应 LFS objects，现存分批按旧顺序分别得到 8,579/9,433 行，与历史
   记录 8,607/9,323 不同。因此不得宣称当前 Git 可逐字节复原 legacy v4/v5。
4. 当前 manifest 引用的 `cards_senior_0809.jsonl` 在远端是 1,940 行、1,940 个唯一 ID、0 credential shape，
   SHA-256=`133500c0fd731201bde35f44598ada17430684ed2b762326ae006101722a3094`，但此前未被 Git 跟踪。
   本轮只补这个 immutable batch 的 LFS pointer/object，不新增合并 corpus object；legacy 缺口明确保留。

直接证据：
- `phase1/实验记录/2026-08-14/SearchPolicyEndogeneity_历史协议审计_裁决.md`；
- `phase1/results/search_policy_contract_audit_invalid_20260814/diagnostic_summary.json`；
- `phase1/实验记录/2026-08-14/CorpusLFS_发布契约审计.md`；
- `phase1/results/corpus_lfs_audit_20260814/summary.json`。

## 0I. 2026-08-14 最新覆盖：prospective 收样、累积与原子评分完整盲链通过影子回放

本节晚于 0H；主线没有变成旧多保真/HCE/probe，仍是 run-clean、decision-local 数据集/benchmark 与
first-960 前瞻确认。

1. v11 的 16,012 个历史 endpoints 已生成 `(card_id, exact-code SHA-256)` denylist；唯一 code SHA 为
   15,912 个，producer SHA 为
   `2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6`。不 import producer 的 verifier
   从 hash-locked cards 逐行重建完全一致；正式远端 23 项测试通过。
2. denylist SHA/行数现为 intake 与 scorer 的源码常量，公开 CLI 不能自报覆盖；旧 667-run denylist 继续保留。
   新 manifest 还必须满足 `run_id == journal:<source_sha256>`，endpoint ID 与 exact code 两层 overlap 均为 0。
3. 最终 0812 全量影子回放在 commit `ca86739ed992d11a11d652dcbcb2e85394308532` 通过：远端测试
   28/28 通过；60 roots 中 57 个
   checkpoint runs、3 个 live-only、1,304 endpoints、286 structural pairs、9 tasks。它们全部早于激活，
   eligible=0；env/live-event 未读、raw journal 未落盘、源 archive 前后 SHA 一致、两层历史 overlap=0。
   intake summary SHA 为
   `9e3e9b3df34e07d792baf77401c2cf9292b0aaacdabd59c64feb22b4b1e0bdc6`。
4. `prospective_accumulator_v1` 已实现并在同一真实 schema 上复放：它从 hash-locked registry 逐批重验 archive、
   source/run/endpoint identity、历史端点与 exact-code denylist、结构 pair 重建，并拒绝跨批重复 source/run/endpoint。
   当前状态为 `PROSPECTIVE_COHORT_COLLECTING`，summary SHA 为
   `f2cbefa765b90c8c432a1ecb2467ce235ce7051cfaa0e7cbb22c3cc4c776d13c`；`label_vault_opened=false`，
   outcome/prediction 打开列表均为空。
5. first-240/first-960 在生产关闭前只能是 provisional。只有独立于 outcome 的生产关闭凭据明确
   `all_scheduled_runs_uploaded=true` 且 `outcomes_read=false`，并绑定当时 registry SHA，才可冻结身份；这避免晚上传的
   更早 run 改写所谓 first-960。关闭时不足 960 就诚实记为不完整，不能后补或按效果停止。
6. 该回放只证明工程链适配真实 tar schema，不是 prospective 正结果，未计算任何 scorer-vs-grade metric，
   label vault 未复制或打开。目前 senior 目录最新仍为 0812；metadata-only monitor 继续运行。
7. 语料版本发布固定为：Git LFS 只存不可变分批文件，每个上传一次；在有 LFS 的环境 pull 后由统一 manifest
   驱动 `rebuild_corpus.sh`，再核对行数与 SHA。不得把每版合并语料重复上传，也不得绕开 manifest 手拼版本。
8. 固定 scorer 原子编排与跨批 score registry 已在 commit
   `4b12c8f80abee4fafcacf8bc8268f9344ead7b61` 完成。远端 33/33 相关测试通过，其中包含真实冻结 bundle 对
   synthetic 非空 prospective manifest 的端到端推理；随后 0812 最终 shadow 得到
   `NO_ELIGIBLE_ENDPOINTS` 与 `PROSPECTIVE_SCORE_REGISTRY_VERIFIED`。单批事务和 registry 的 `strace` 中
   `label_vault.jsonl` 文件系统调用都为 0。score transaction summary SHA 为
   `237313bc7a9a015b0dcfcbda1c70546d4572024b3a04cd2d9a3f1fe407f5ff5f`，registry validation summary SHA 为
   `4a74e0fb6ad85a39581d4d62e4cad4ca3ca7ec5772b565eab7ebf84558049722`。
9. 第一次远端工程预检因 `critic` venv 没有 pytest 而在 intake 前 fail-closed；无正式 artifact。重跑改用同时含
   pytest/sklearn 的 `exp` venv，失败日志与成功日志均保留。至此新 drop 到达后的固定评分链没有人工补步骤；
   没有新 drop 时仍不读标签、不在同一 OOF 上启动新一轮追参/GPU 方法实验。

直接依据：

- `phase1/results/fixed_decision_scorer_v11_20260814/precutoff_endpoint_independent_verify.json`；
- `phase1/results/prospective_intake_shadow_0812_v4_20260814/README.md`；
- `phase1/results/prospective_accumulator_shadow_0812_v1_20260814/README.md`；
- `phase1/results/prospective_score_pipeline_shadow_0812_v1_20260814/README.md`；
- `phase1/实验记录/2026-08-14/ProspectiveIntake_预注册.md`；
- `phase1/实验记录/2026-08-14/ProspectiveAccumulator_预注册.md`；
- `phase1/实验记录/2026-08-14/ProspectiveScoringRegistry_预注册.md`。

## 0H. 2026-08-14 最新覆盖：TGCA 经独立复核关闭，盲测继续封存

本节晚于 0G；稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与前瞻复核。

1. `tgca_v11_train_oof_discovery_v1` 已完成 13 项预检、5-fold producer 和不导入 producer 的完整重拟合
   verifier；正式状态为 **`VERIFIED_TGCA_DISCOVERY_NO_UNLOCK`**，最大 refit score 差为 0，所有完整性门通过，
   `frozen_read=false`、`temporal_vault_read=false`。
2. TGCA 相对 sibling-only 的微平均 utility/top-1 仅为
   `+0.010310682590593189/+0.004426737494466578`；run/task clustered 区间均跨 0，支持任务中 utility
   非负仅 `11/20=0.55`。相对 uniform cross-run 的 utility 为 `-0.00639610796665303`。三个预注册效果门
   全部失败，0812 vault 不解封。
3. 操纵检查明确成功：114 个 fold×task 图中，TGCA 把平均 components 从 `80.45614035087719` 降至
   `5.780701754385965`，最大分量占比升至 `0.934134980605146`，正代数连通度图为 `101/114`；因此不能把
   NO_UNLOCK 归因于“没有把图连起来”。关闭本实现，不在同一 OOF 改 ratio/选边/任务/门。
4. 学长的规模实验文档已定位到 `myfork/dojo-reproduce` commit `5f071ec`：旧 1,303-pair validation 上
   1.5B--8B 没有单调规模收益，Qwen3 base final 均值约 55%，1:1 混入 value pairs 下降。它是独立旧口径，
   不替代本项目 run-clean OOF。该分支更新 commit `2cb6f0c` 仍把
   `metric_for_best_model=eval_pair_accuracy` 与 `greater_is_better=false` 并置；修复前的新 checkpoint
   不能按“best accuracy”解释。
5. 接下来资源只回到固定 scorer 的 first-960 prospective cohort、新 source-journal provenance 与 benchmark
   发布物。gap/parent-normalized loss 已被 learning-to-rank/NAS top-centered 文献覆盖；若补做只能在新验证
   证据上作为强 baseline，不作为 novelty，也不在当前 OOF 追参。

直接依据：

- `phase1/实验记录/2026-08-14/TGCA_裁决.md`；
- `phase1/results/tgca_v11_20260814/independent_verify.json`；
- `phase1/results/tgca_v11_20260814/summary.json`。

## 0G. 2026-08-14 最新覆盖：短 run 改变 pair 产率，盲态扩为固定 first-960

本节晚于 0F；没有读取 activation 后 outcome 或论文 frozen pairs，稳定主线不变。

1. 学长 0812 drop 已先安全提取并脱敏：10 个唯一 archive（另 1 个 leaf 文件被 SHA 与包内根目录共同证明为
   tabular 错包重复）、60 个 env 的 512 个字段脱敏、原始 credential 残留 0；57 journals 产出 805 cards、
   9 tasks，所有 grade/y_norm finite，和 v11 的 ID/exact-code overlap 均为 0。
2. 旧 `step <= previous_step` run heuristic 在 0812 得到直接反例：两个 ranzcr journal 的有标签 steps 分别为
   1–2 与 6–7，被静默合并为同一 segment。source-journal truth 是 57 runs，heuristic 只有 56；无 source split，
   所以该例是保守合并而非泄漏证据。新 batch 改为 flatten 前显式 run ID，旧 heuristic 不再是 source truth。
3. 0812 已在不打印、不用于 metric 的条件下封成 `temporal_blind_0812_v1`：805 endpoints、57 runs、9 tasks，
   但只有 103 个 structural sibling pairs、7 个 pair-support tasks。它明确是 pre-activation analyst-blind holdout，
   不是 prospective cohort；TGCA 配方与 prediction 冻结前不得解封 label vault。
4. 103/57=1.8070175438596492 pairs/run，说明短 run 机制下 first-240 约只有 433.6842105263158 pairs，原
   1,500-pair 支持门大概率不足。outcome 前 append-only 附录因此保留 first-240 为必报 pilot、禁止中途看
   outcome，并固定 first-960 为确认 cohort；门槛、scorer、estimand 和任务约束均不变，960 前停产则记不完整。
5. v11 source-journal provenance backfill 已完成：在可追溯的 14,339/16,012 cards（89.5515863102673%）中，
   覆盖 587 个旧 heuristic runs、592 个唯一 source journals；发现 5 个 heuristic run 各自合并了两个真实
   journals，但 **0 个 source journal 被拆成多个 heuristic runs**，card-source collision 也为 0。因此当前证据
   没有发现这种边界错误造成跨 split 泄漏；它造成的是保守合并、run 数少计与 cluster 过粗。另有 1 个旧
   journal 命中 credential 形状并在 JSON 解析前跳过；1,673 张未追溯 cards 仍明确记为未知，不能外推成全量证明。

直接依据：

- `phase1/实验记录/2026-08-14/ProspectiveDecisionConfirmation_功效修正附录_预注册.md`；
- `phase1/results/temporal_blind_0812_v1/seal.json`；
- `phase1/results/temporal_blind_0812_v1/source_truth_audit.json`；
- `phase1/results/v11_source_provenance_audit_20260814/summary.json`。

## 0F. 2026-08-14 最新覆盖：固定 scorer 已激活，前瞻 first-240 开始计时

本节晚于 0E；稳定论文主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark，旧 HCE、
多保真、TD/RL 与 probe 不恢复为主线。

1. `prospective_decision_v1` 已在 commit `41d638b1c8154415d523d8f22bbd10b7ae5b48be` 正式完成
   13 项预检、producer、独立重拟合 verifier 与原子激活。固定 scorer 是 v11 train-only 上的 `static_lr` 与
   `char_tfidf_lr`；独立 verifier 的所有数组与 5,499×2 reference scores 最大差均为 0。
2. 激活时刻固定为 `2026-08-13T22:19:17.348021Z`（北京时间 2026-08-14 06:19:17）；模型 bundle
   SHA-256 为 `c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23`。v11 的 667
   physical runs 在 denylist 中；只有 generation start 严格晚于激活时刻的 run 才可进入 first-240。
3. 学长最新 `mle/0812` 的 11 个 archive 已被发现，但其源文件时间均早于激活；它们只可作为下一版历史语料，
   不计入前瞻 cohort。导入前必须先隔离提取并脱敏，禁止直接读取原始 tar 内容。
4. first-240 固定排序、支持门、pair-graph interaction 与真实 top-1/utility 门均保持预注册，不按 outcome 停止，
   不改 scorer、不筛任务、不打开论文 frozen。通用“pair distribution/graph matters”已有明确文献先例；本文可守
   novelty 是真实 MLE sibling decision graph、physical-run provenance、estimand transport、搜索 utility 与前瞻复核。
5. 唯一允许继续预注册的正方法候选是 `Target-Graph Connected Augmentation`：只在 outer-train 内加入同 task、
   gap-matched、跨 physical-run 的桥接边，并以等边数 sibling 重权与 uniform-crossrun 为控制；必须在未见 run 的
   真实 sibling top-1/utility 上过门。若失败即关闭，不在同一 OOF 调阈值或换任务。

直接依据：

- `phase1/results/fixed_decision_scorer_v11_20260814/README.md`；
- `phase1/results/fixed_decision_scorer_v11_20260814/freeze_receipt.json`；
- `phase1/实验记录/2026-08-14/PairGraph_文献边界与正方法候选.md`。

## 0E. 2026-08-14 最新覆盖：pairing 统一膨胀未确认，保留 predictor×graph 排序反转

本节晚于 0D；稳定论文伞仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark。

1. `pairgraph_v11_train_oof_descriptive_v1` 在 3,921/4,263 common-support sibling rows、20 tasks 和
   196,949 个有限非平局跨 run pairs 上完成；producer 与独立 verifier 一致为
   `VERIFIED_PAIRGRAPH_EFFECT_NOT_SUPPORTED`，所有完整性门通过，`frozen_read=false`。
2. char-TFIDF 的 task-macro 为 sibling=`0.5284907717433142`、task/fold-matched uniform cross-run=
   `0.5814158858170438`、再匹配固定 gap bins=`0.5478674917657668`。total 点估计 +0.052925114073729684，
   但 task CI=[-0.04418436017058699,0.15460114273445769]；gap component +0.03354839405127704，CI
   也轻微跨零。四臂只有 2 臂点估计为正、0 臂 CI 下界为正，故关闭“全局 pairing 普遍抬高所有 critic”强主张。
3. 保留明确标注为 outcome 后描述的 rank reversal：sibling task-macro 上 static LR=0.5389068809808808
   高于 char-TFIDF=0.5284907717433142；uniform cross-run 上 char-TFIDF=0.5814158858170438，而 static LR=
   0.49652226450484627。pair graph 不只是统一难度旋钮，而与 predictor family 和 task 强交互。
4. 因此 benchmark 主张收紧为：不同 pair graph 的 headline accuracy 不是可直接横比的同一 estimand；发布物
   必须同时报告真实 sibling graph、task weighting、固定 gap transport、run-clean provenance 与 top-1/utility。
   同一 train OOF 上不改门、不筛正任务、不再做新阈值。确认性复现只用协议冻结后的新 physical runs 与事先
   冻结 scorer，论文 frozen 继续封存。

直接依据：

- `phase1/实验记录/2026-08-14/PairGraphIntervention_裁决.md`；
- `phase1/results/pairgraph_v11_20260814/independent_verify.json`。

## 0D. 2026-08-14 最新覆盖：异构低容量方法关闭，转 pair-graph benchmark intervention

本节晚于 0C；稳定论文伞不变，且不恢复旧多保真/HCE/probe 主线。

1. `heterogeneous_oof_v11_discovery_v1` 已在精确相同的 4,263 train-only pairs、333 physical runs、
   23 tasks 与 inherited five outer folds 上完成；不导入 producer 的 verifier 重新拟合全部模型后裁决
   `VERIFIED_DISCOVERY_NO_UNLOCK_NO_ENSEMBLE`，`frozen_read=false`。
2. char-TFIDF 是最强 arm：pair=`0.5219329110954727`、complete-parent top-1=`0.4674634794156706`、
   parent-equal gap utility=`0.5310468507329235`。pair 的 run/task macro 95% CI 均高于 0.5，说明代码文本
   有弱信号；但 20 个支持任务只有 11 个不低于随机，且相对 anchor 的 top-1/utility task-clustered CI
   均跨零，不能升级为稳健 decision critic。
3. char-TFIDF 与 anchor disagreement=`0.4468684025334272`，oracle-union top-1=`0.6715360779105799`；
   但 oracle 不可部署，而预注册 nested gate 因任务一致性和 utility task-CI 失败。禁止同一 OOF stacking、
   事后改权重或用 equal-rank secondary 替代 primary。
4. 当前 sparse patch、global frozen linear、task-conditioned/top-centered linear 与 static/char-TFIDF ensemble
   低容量方法线一并关闭；论文 frozen 继续封存。下一步转数据/benchmark 的 **pair-graph intervention**：
   固定同一 OOF endpoint 分数和 endpoint universe，只改变全局随机、gap-matched、真实 sibling 三种 pair
   graph，定量分解表观准确率中由 gap 分布与真实决策拓扑造成的膨胀。先只用 train OOF 做描述性审计，
   不把它冒充新 critic 或 prospective search utility。

直接依据：

- `phase1/实验记录/2026-08-14/HeterogeneousRunOOF_裁决.md`；
- `phase1/results/heterogeneous_oof_v11_20260814/independent_verify.json`。

## 0C. 2026-08-14 最新覆盖：task-conditioned/top-centered 关闭，转 exact-same-pool 异构审计

本节晚于 0B；稳定论文伞不变。

1. 预注册 `task_topcenter_v11_discovery_v1` 已完成 5-fold physical-run OOF，并由不导入 producer 的
   verifier 独立重建。裁决为 `VERIFIED_DISCOVERY_NO_UNLOCK`，`frozen_read=false`。
2. 主模型 pair=`0.5066854327938072`、complete-parent top-1=`0.45108455068614434`、
   parent-equal gap utility=`0.5125829562017966`。相对 fixed global head 的 top-1/utility 微平均增量只有
   `0.00398406374501992` / `0.002076308434788266`，run/task clustered CI 全部跨零；任务一致性也未过门。
3. 2×2 消融没有给 task residual 稳健支持；top-centered objective 只有小而不一致的变化。因此关闭当前
   task-conditioned linear 实现，不扩大正则网格、不按任务翻转、不读 frozen。
4. 下一步按 0B 已冻结的条件，只做 exact-same-pool、同一 outer physical-run folds 的 char-TFIDF/static
   train-only OOF 与 error-complementarity 审计。互补性标准须在结果前固定；只有通过才实现严格 nested
   ensemble，不能在同一 OOF 行上训练并报告 meta-head。

直接依据：

- `phase1/实验记录/2026-08-14/TaskTopCentered_RunOOF_裁决.md`；
- `phase1/results/task_topcenter_v11_20260814/independent_verify.json`。

## 0B. 2026-08-14 最新覆盖：global frozen head 关闭，转 task-conditioned parent objective

本节晚于 0A 并覆盖其中“Parent-Conditioned Patch / Action Critic 是当前首选方法候选”的下一步措辞；
稳定论文伞仍不变。

1. Sparse parent patch discovery 已正式 `NO_UNLOCK`：patch 相对 whole-code pair accuracy 为负，关闭固定
   line-diff 实现，不读 frozen。
2. 随后按学长“0.5B 多卡换长 context”的建议完成正式训练期 gate：Qwen2.5-0.5B、8,192 tokens、
   5,499 endpoints、4×RTX3090 frozen extraction、5-fold physical-run OOF、单一 global linear head。
   独立 verifier 裁决 `VERIFIED_DISCOVERY_NO_UNLOCK`：pair=0.5038705、complete-parent top-1=0.4471005、
   parent-equal gap utility=0.5105066；run/task CI 都包含 0.5；`frozen_read=false`。
3. 这只关闭 fixed `mean+last + global linear`，不关闭 embedding 资产。描述性 per-task accuracy 高度异质，
   下一候选是 outcome 后另立协议的 **task-conditioned parent-level top-centered/listwise head**；正则和混合只能在
   inner physical-run folds 选择，outer run OOF 裁决，不得按已见任务结果手工翻转或挑任务。
4. 若 same-pool OOF 证明 frozen/char-TFIDF/static predictor errors 互补，再做严格 nested ensemble；不允许在
   同一 OOF 行上训练并报告 meta-head。listwise/top-centered losses 与异构 predictor ensemble 在 NAS 已有先例，
   所以它们是正方法 baseline，不是单独 novelty。
5. 新协议通过前继续封存 `decision_frozen_v11_b*`。完整可共享结果（含 174 embedding chunks）在
   `phase1/results/frozen_embed_v11_20260814_f339eb9/`；Git LFS 归档 SHA-256 为
   `096a3581bfce48c83019f3440e88089d4b8a4dd0a768224493f892941a3d64f7`。

直接依据：

- `phase1/实验记录/2026-08-14/Frozen05B8192_RunOOF_裁决.md`；
- `phase1/results/frozen_embed_v11_20260814_f339eb9/independent_verify.json`。

## 0A. 2026-08-14 覆盖裁决：回到真实决策 benchmark，Probe Contract 降为支线

本节晚于下方所有 08-13 裁决并覆盖其中“当前唯一主实验/活跃方法主线”的措辞。

1. 稳定论文伞仍是 **run-clean、NAS-Bench-style 的 MLE-agent 搜索树数据集与真实 sibling
   决策 benchmark**。旧 HCE/TD/RL/多保真三臂不恢复。
2. Progressive Artifact Contract / Probe-First 与 early-fidelity 相邻；它只保留为 gated 支线，
   不能再冒充稳定主线。V2 job `10686` 只完成 16/16 generation，自动 replay 已在 outcome 前停掉；
   因而没有 A/B 质量或固定预算收益结论。
3. 当前首选方法候选改为 **Parent-Conditioned Patch / Action Critic**：不再独立判断完整 child code，
   而是在相同 parent 下判断候选 edit/action 的相对改进。即时 b0 先用 run-clean sibling 数据裁决；
   budget-conditioned future value 只能在相同 continuation policy 或显式 right-censoring 下扩展，
   禁止重新使用历史 MCTS 的 subtree maximum 当无偏标签。
4. 文献边界已收紧：SWE-bench 的 Guided Search Strategies 已有 learned action-value + one-step
   lookahead；BAVT 已有 residual relative progress + budget conditioning。因此“action-value critic”
   本身不构成 novelty。允许的差异只能落在 MLE patch/action 表示、run-clean/censor-aware 标签、
   不微调底座与真实 fixed-budget utility，以及本数据基准的系统测量。
5. 第一闸是零 GPU、outcome 前冻结的 sparse patch CPU discovery。只有 train-run OOF 同时通过效果、
   双聚类稳健性、任务一致性与完整性门，脚本才允许读取 b0 frozen 文件；否则关闭 sparse patch
   实现，不把工程 timeout 或旧 lookahead 负面偷换成方法结论。

直接依据：

- `phase1/实验记录/2026-08-14/ParentPatchCritic_文献边界与路线.md`；
- `phase1/实验记录/2026-08-14/ParentPatchCritic_CPU发现门_预注册.md`。

## 0. 8 月 13 日晚间覆盖裁决（优先级最高）

### 0.1 21:20 后的最新覆盖：关闭 identity SPT，保留 Probe-First 因果线

本小节晚于 0 节后续文字并覆盖其中“下一步”措辞：

1. Scoreable Prediction Tap 的冻结 job `10648` 已真实完成 18/18 executions（3×RTX3090，
   `00:45:53`）。主 verifier 与独立 raw verifier 一致为 **`INCONCLUSIVE`**：baseline evaluable=2/6，
   probe-by-120=2/6，语义等价=2/2，latency pairs=2，中位相对提前仅
   `0.04135151374612629`。不启动 v11 176-pair 扩展。
2. 机制诊断表明 identity wrapper 只能在候选已有 `.predict*` call 时截获，而这些 call 通常位于昂贵训练之后、
   submission 写盘之前；它不能主动创造早期 fidelity。因此 SPT 只保留为 measurement/baseline，不再是核心方法。
3. Probe-First original-vs-contract A/B job `10637` 的 12 个 generation entry 都 `rc=0`，但 manifest builder
   错把每个 run 必然不同的 `solver.exp_name/checkpoint_path` 当作科学配置漂移，parent `FAILED 1:0`，replay
   未启动。按冻结规则该批保持 **`INVALID`**，不能解释方法输赢或修后追认。
4. validator 已收窄为只忽略上述两个 run-identity 字段，并增加“真正改变 `step_limit` 仍必须失败”的回归门。
   活跃正方法仍是 **Probe-First/Progressive Artifact Contract**，但下一批必须全新任务、全新 seed、重新冻结；
   headline 是 coverage、full-quality safety、observability/ranking regret 与固定预算 best-final，而非 prompt
   compliance。
5. 文献审计已撤回“没有 3/5 close baseline”：ArchPilot 是 3/5 close baseline，后续必须实测
   ArchPilot-style low-fidelity rewrite、FOREAGENT/最强 critic、Probe-First 与 full execution。仍未发现 4/5
   direct scoop，但若没有端到端 search utility，仅靠 artifact contract 不足以构成顶会方法贡献。

最新直接证据新增：

- `phase1/实验记录/2026-08-13/SPT_标签盲机制pilot裁决.md`；
- `phase1/实验记录/2026-08-13/probe_contract_ab_safety_v1无效运行裁决.md`；
- `phase1/实验记录/2026-08-13/SPT_文献防scoop审计.md`。

本节发生在本文后续各节之后，**覆盖**后文“当前唯一主实验”和后续顺序中的旧措辞。论文伞形定位仍是
NAS-Bench-style 的 MLE-agent 搜索树 benchmark；当前方法主线已经进一步收敛为：
**Anytime MLE Search under Selectively Observable Execution Feedback**，首个主动干预是
schema/probe-first artifact contract。旧 HCE、TD/RL、多保真三臂和继续扩大静态 critic 均不是当前路线。

变化来自同日已经冻结的证据链，而不是按文件名回退：

1. late-artifact pilot 中 6 个预先冻结的 fresh-120-silent 候选到 600 秒仍为 0 个 stable artifact；
2. 冻结 100 sibling sets 的完美 120 秒 hindsight oracle 有 0.512644 的理论 headroom，但现有
   censor-aware race 的 optimistic avoidable tail 只有 0.026163；瓶颈不是继续调 observed selector，
   而是高价值候选在决策时刻不可评分；
3. schema/probe V1 对两个预先冻结任务一次生成、一次连续 replay，最终只有 1/2 probes 和
   1/2 full transitions 通过，按预注册规则正式为 **FAIL**；成功任务证明基础 contract 可实现，失败任务
   在任何 artifact 前触发通用 sklearn API 错误，因此不能宣称跨任务稳定可行；
4. KompeteAI 已覆盖 reduced-epoch logs 预测和 MLE pipeline 加速，delayed-feedback BAI、failure-aware
   BO 与 early termination 也已有先例；SandMLE 还使用了 valid-output milestone。因此 novelty 不能写成
   “首个 early metric/valid artifact/early stop”，而必须落在真实自由形态 MLE sibling、候选特异且不可变
   的 artifact contract、host/pristine provenance、选择性可观测 regret 分解及固定预算搜索因果收益；
5. 独立新任务/新 seed 的 V2 已按 outcome 前冻结规则正式 **PASS**：Spaceship 与 Tweet 均为
   `root→valid draft`，host 在 12.542975/11.046629 秒捕获 probe，且两者都在 600 秒内出现 full transition；
   主验证器与不导入主实现、重新调用 pristine grader 的独立验证器一致为 probes=2/2、full=2/2。
   这只证明 prompt-only contract 的工程可行性，不证明 coverage、排序、质量非劣或搜索收益。

V1 结果不得回填或同任务修补；V2 也不得在这两个任务上继续调 prompt。V2 的 PASS 现在只授权在
**全新任务、全新 seed**上设计小规模独立因果 A/B：标准 draft 与只增加 artifact contract 的 draft 使用
相同 conditional-debug、API/GPU/grader 和停止预算，先裁决 time-to-first-scoreable artifact、120 秒 coverage、
失败率与 full quality。两个 V2 draft 都首次执行成功、没有触发 debug，因此不得把 V2 写成 debug 有效性证据；
- 150-run 评分通道确认保持 `NOT SUBMITTED`，保留为 benchmark 机制确认资产，但不再阻塞上述低成本
  operator feasibility gate，也不得用旧数据替代前瞻确认。

最新直接证据：

- `phase1/实验记录/2026-08-13/schema_probe_smoke_v1裁决.md`；
- `phase1/实验记录/2026-08-13/schema_probe_repair_v2裁决.md`；
- `phase1/实验记录/2026-08-13/Anytime可观测性主张_20260813.md`；
- `phase1/实验记录/2026-08-13/late-artifact连续轨迹_pilot裁决.md`；
- `phase1/实验记录/2026-08-13/anytime_oracle_headroom_探索性上界.md`。

## 1. 审计截面

- 我方分析基线：`fork/phase1-value-critic@96b7b01a3563db10dec82d2aff1becfad2eab1db`
  （本轮 Qwen/K2 验收与 schema-first 预检开始前的干净截面）
- 学长分支：`fork/dojo-reproduce@2cb6f0c57790407cae84070d3eb475da3cbe9597`
- 最新发布语料：v11，16,012 cards / 667 physical runs / 25 tasks；15,991 finite，21 quarantine。
- 论文冻结决策集：b0/b1/b2 分别 1,498 / 323 / 265 对；v10 与 v11 逐字相同。
- 扩展评测集：b0/b1/b2 分别 136 / 39 / 30 对，必须与 headline 分开报告。

本裁决直接对应以下最新证据链，发生冲突时按日期和明确的撤回/预注册关系解释，而不是按文件名猜：

- `phase1/实验记录/2026-08-12/剂量响应曲线_首版.md`；
- `phase1/实验记录/2026-08-13/评分通道严格配对_审计.md`；
- `phase1/实验记录/2026-08-13/评分通道前瞻复现_预算与预注册草案.md`；
- `phase1/实验记录/2026-08-13/v10冻结决策集与训练增量验收.md`；
- `phase1/实验记录/2026-08-13/学长0811入库_v11验收.md`；
- `phase1/实验记录/2026-08-13/artifact_first_cascade_探索性预注册.md`；
- `phase1/实验记录/2026-08-13/artifact_first_cascade_探索性裁决.md`；
- `phase1/实验记录/2026-08-13/parent_certified_improvement_回顾性预注册.md`；
- `phase1/实验记录/2026-08-13/parent_certified_improvement_探索性裁决.md`；
- `phase1/实验记录/2026-08-13/120秒评分可观测性_机制预注册.md`；
- `phase1/实验记录/2026-08-13/120秒评分可观测性_探索性裁决.md`；
- `phase1/实验记录/2026-08-13/选择性可观测反馈_正面突破路线.md`；
- `phase1/实验记录/2026-08-13/anytime_oracle_headroom_探索性上界.md`；
- `phase1/实验记录/2026-08-13/FOREAGENT官方pair图_外部审计预注册.md`；
- `phase1/实验记录/2026-08-13/FOREAGENT官方pair图_外部审计裁决.md`；
- `phase1/实验记录/2026-08-13/FOREAGENT官方alignment全量审计_预注册.md`；
- `phase1/实验记录/2026-08-13/late-artifact连续轨迹_pilot裁决.md`；
- `phase1/实验记录/2026-08-13/连续fidelity轨迹_watcher_smoke冻结说明.md`；
- `phase1/实验记录/2026-08-13/学长checkpoint方向与QwenK2语料验收.md`；
- 学长分支 `src/mle_critic/docs/outcomes/0812/DECISION_MODEL_SIZE_EXPERIMENTS.md`。

## 2. 最近两周的路线更替

### 7 月 30 日—8 月 2 日：跨生成器/版本与 lookahead（已被后续审计降格）

早期报告把跨生成器、静默版本升级和 lookahead 作为主角。8 月 3 日以后证明：

- “静默版本升级导致塌陷”被同版本独立批次对照推翻，真实混杂是 batch/run；
- 旧 in-task 0.776 含 endpoint 与树碎片泄漏，最终 run-clean L1 为 0.6493；
- 44% orphan cards 使所谓 tree split 实为 fragment split；99.7% in-task test pairs 与训练共享物理 run；
- K≥1 的 RM 优势在 run-clean 决策集不复现；预算条件化 flip 效应也关闭。

因此这些结果只能作为方法学历史、数据 provenance 与 benchmark 挑战背景，不能恢复为当前方法主线。

### 8 月 8—10 日：NAS-style 数据基准（当前论文伞形定位，仍有效）

稳定定位是“MLE-agent 搜索树的 NAS-Bench + 系统性 predictor study”：

- 运行级干净切分、query/init 成本分账、覆盖率列、噪声上界和泄漏修复是核心资产；
- 在真实 sibling 决策点，静态特征、TF-IDF、1.5B RM、LLM judge/PBE 协议均接近随机；
- 学长 Qwen2.5/Qwen3 1.5B—8B 的旧 decision 验证约 0.52—0.56，未见规模单调收益；
- 但学长的旧日志使用 1,303-pair validation，不等同于当前冻结 1,498/323/265 三档，不能直接作为最终表。

该定位是论文容器，不等于必须写成纯负结果；当前最有希望的正机制见下一节。

### 8 月 12—13 日：真实决策的执行悬崖与评分通道（当前活跃科学主线）

冻结 100 sibling sets / 230 candidates / 52 physical runs 的冷启动 replay 显示：

- 30 秒 stdout 接近随机；120 秒 stdout 仍明显弱于完整执行；
- 120 秒能产 `submission.csv` 的候选，其 pristine 外部分是有用的早期信号；
- 最严格的同 parent、同候选、同 120 秒共同覆盖比较：external sub top-1=0.9167，
  stdout top-1=0.7083，配对差 +0.2083；run-CI [+0.0769,+0.3810]，task-CI
  [+0.0690,+0.4667]；24 sets / 15 runs / 9 tasks；
- 但只有 5 个 run 有非零方向，全部为正，双侧 exact sign p=0.0625。

允许的当前主张是：**pristine 外部评分通道是最强的正向前瞻机制候选**。不能写成已经确认，
不能从共同覆盖子集外推到全部候选，也不能说已经带来实用加速。

在同一冻结发现集上，coverage-complete 的 `artifact_score_then_stdout` 探索性 cascade 相对
`stdout_only` 提高 +0.0700，但未达到预注册 +0.08、run-CI 下界严格大于 0 和 sign p<0.05
三道门，裁决为 **BORDERLINE**。机制分解揭示了更重要的约束：

- 在同样观察到 artifact 的条件下，使用其 pristine 分数相对只看 artifact 是否存在提高
  +0.1447；run-CI [+0.0717,+0.2241]，task-CI [+0.0541,+0.2510]；
- 但“及时产生 artifact”本身相对 stdout 降低 -0.0747；run-CI
  [-0.1385,-0.0182]，task-CI [-0.1604,-0.0059]；
- 因而 artifact 可观测性是选择性缺失（MNAR）的候选机制：分数值有用，单纯把“能及时产物”
  当质量信号会造成偏差。该分解已由不导入主脚本的独立实现复核，但仍属于同一发现集。

## 3. 当前唯一主实验

### 3.1 前瞻通道复现

预注册 commit 为 `a18c285`，机制发现 commit 为 `4c964f8`（2026-08-13 05:31 +08:00）。

- 只接纳机制 commit 之后产生、且未进入旧 100 sets 的新 physical runs；
- 至少 150 runs，dominant task ≤25%；每 run 固定最多 2 个合格 parent；
- 主比较固定为同一 120 秒、共同候选上的 `sub_score - stdout_val` tie-aware top-1；
- 预计约 690 replay，17—23 GPU·h，4×1 GPU 时墙钟约 4.3—5.8 小时；
- 无 optional stopping，不按任务、hard/easy 或 parser 子集替换 headline。

截至本文件写入时，服务器最新 0811 archives 的时间均早于机制 commit；v11 虽在 05:48 入库，
但“晚入库”不等于“前瞻生成”。**严格合格确认 run 数为 0，实验 NOT SUBMITTED。**

### 3.2 立即可做的支持实验（不重训）

复用学长 0812 的最佳 Qwen3-4B/8B checkpoint，对 v11 三份冻结文件逐 pair 打分：

- headline：`decision_frozen_v11_b0.jsonl`；
- secondary：b1、b2；
- extension 只单列；
- 保存逐 pair 预测、checkpoint、commit、seed、命令，按 task/run 聚类；
- 目的仅是检验旧约 0.55 是否受容量/context 限制，不挑 best checkpoint 冒充 test 泛化。

现有 checkpoint 在学长环境，当前仓库只有日志和 outcome 文档；先交付严格 evaluator，不能伪称已完成。

### 3.3 已完成的短验证：选择性评分通道

在不改动上述唯一确认性主实验的前提下，只允许一次冻结、无调参的回顾性规则验证：默认使用
`stdout_only`；仅当 parent 有部署时允许访问的历史 pristine 搜索分数，且 120 秒 artifact 严格优于
parent 时，才用该改善证书覆盖 stdout。parent 缺失或无改善时回退 stdout。该实验用于检验
“以 incumbent 为锚点能否缓解 MNAR”，不得把旧 `graded` 当作线上 test 标签，也不得在同一
100-set 发现集上继续搜索阈值或策略网格。

该冻结规则已一次性执行并由不导入主脚本的独立实现复核：证书支持仅 24 sets / 14 runs / 7 tasks；
parent-certified top-1=0.5683，stdout-only=0.5383，差 +0.0300；run-CI
[-0.0235,+0.0833]，task-CI [-0.0114,+0.0735]，run sign p=0.6875。相对 naive cascade
为 -0.0400；尽管 run/task bootstrap CI 均低于 0，只有 4 个 informative runs，run sign p=0.125，
不能宣称独立确认更差。该规则未过 +0.08、双聚类 CI 与 run sign 门，裁决为
**BORDERLINE**。因此此候选关闭，不进入前瞻确认，也不得在旧 100 sets 上改 margin、阈值或回退规则。

### 3.4 已完成的机制可行性审计（不是 selector）

只用执行前代码与任务身份预测“120 秒时是否有 finite pristine 外部分”，不把最终质量、stdout、
artifact 分数或 parent 比较用作特征。主模型使用 physical-run 分组的五折 OOF，task/run 双聚类
推断，另做五个 split-seed 敏感性与 whole-task leave-one-out。它只回答可观测性 propensity 是否
可建模；即使达到 GO-FEASIBLE，也不能声称搜索收益，只允许在新的 discovery/validation split
开发显式删失模型。旧 100-set selector 规则仍保持关闭。

冻结审计已一次性完成并由独立实现复核，裁决为 **BORDERLINE**：主模型 AUC=0.8629，run/task
CI=[0.7602,0.9483]/[0.6951,0.9606]，5 个 split seeds 的 median/min AUC=0.8572/0.8444；
但 task-only AUC=0.8642，主模型相对 task-only 的 Brier gain 仅 +0.0072，run/task CI 均跨 0。
whole-task LOTO AUC=0.6676，task-bootstrap CI=[0.4554,0.8388]。因此可观测性在现有任务内高度稳定，
但没有证据证明代码模型优于任务先验或能可靠迁移到新任务。该结果不授权直接开发通用 propensity
selector；若继续，只能在新 split 上做 task-conditional 模型，对未见任务 abstain，并独立认证。

### 3.5 已完成的连续轨迹 watcher smoke（基础设施，不是科学实验）

冻结 validator 已一次性给出 **PASS**：job `10591` 在 1×RTX3090 上完成 2 cards × 30/60/120 秒，
共 6 条 records、1 个 stable artifact、0 个 racy copies、1 个 finite pristine grade。存活进程 checkpoint
的最大定时偏差为 0.000156 秒，最大 capture lag 为 0.000506 秒；另一个候选在 83.510392 秒自然退出，
按协议在 120 秒档记录真实退出时刻。worker/validator/job 均 rc=0，原子事务、hash/size、grader 隔离、
process-group 清理与无残留进程门全部通过。两个 card 的 coverage/score 不得作为论文结果；该 PASS
只授权把 watcher 用作机制冻结后新语料的被动仪器，扩大采集仍需冻结新 run/task 分区与总预算。

失败历史保留：job `10590` 因把登录节点本地 `/tmp` 工作树误当作 compute-shared 路径，在候选启动前
1 秒失败；另一次登录节点 compute-only NVIDIA 文件检查在提交前停止。二者均无科学结果、未进入样本。

### 3.6 已完成的一次性方法可行性诊断：Selective Feedback Racing

在仍不修改旧 100 sets 规则网格的前提下，允许最后一次无阈值、无训练的机制诊断：120 秒时只淘汰
“已有 finite pristine 分数且被另一 observed candidate 严格支配”的候选；所有 silent/unscored 候选
一律 abstain/继续。最终目标是保留 full-run winner，因此将保守 abstention 相对 `observed_only` 的贡献，
以及 observed 分数排序相对“同样保留所有 missing、仅在 observed 内随机”的结构匹配基线分开报告。

输入 SHA、100 sets / 230 cards 总体、run/task-macro bootstrap、资源 accounting 和裁决门均在 outcome
前冻结；不 import 主脚本的 verifier 已逐 set 复核。裁决为 **BORDERLINE**：winner survival=0.9800，
run/task-macro CI=[0.9712,1.0000]/[0.9561,1.0000]；相对严格 structured random +0.1413，双 CI
均在 0 以上，run sign p=0.000519，确认 observed score value 有稳定价值。策略淘汰 44/230=19.13%
cards，却只覆盖 3.36% 历史 full runtime；optimistic avoidable tail=2.62%，restart ratio=1.0250。
相对 observed-only 仅 +0.0900、5 informative runs、双侧 p=0.0625。故统一 120 秒 censor-aware race
没有实用成本杠杆，关闭旧 100 sets 上全部后续调参。

### 3.7 已完成的 late-artifact 路线裁决 pilot（不是论文效果实验）

只回答昂贵 fresh-120-silent 候选在同一进程继续到 600 秒时，是否会转为 finite pristine score。冻结
选择规则从 115 个“fresh 120 秒无分数且历史 full runtime≥600 秒”的候选中按固定 SHA 顺序贪心选择
6 cards / 6 tasks / 6 physical runs；不读取 final grade、stdout、代码内容或成绩。每 card 单次 continuous
执行，checkpoints=30/60/120/240/360/480/600；1×3090，候选执行上限 1.00 GPU·h，0 API。

manifest SHA=`f535116e51dc7a03a65aa6df4b4621812367eea201f16aeb8d83d21bc398bbe1`，已经从锁定 raw
inputs 独立重建并逐字节一致。validator 在 GPU outcome 前冻结，区分真正新 artifact hash 与早期 artifact
仅在后续 grader recovery；≥2 个不同任务 late conversion 才保留 `TaskHazard`，0 个才转向
`schema-first operator`，1 个或 grader-recovery ambiguity 为 `INCONCLUSIVE`。完整性门失败则 INVALID。

job `10592` 已在 1×RTX3090 上完成，42 records、原 validator、fresh-directory 重验证和不 import 主
validator 的 raw verifier 均一致：stable artifacts=0、finite grades=0、late conversions=0、grader
recoveries=0，裁决为 **SCHEMA-FIRST-CANDIDATE**。其中只有 2/6 候选实际存活到 600 秒并被预算终止，
另外 4/6 在约 5.0/7.8/36.0/91.8 秒自然以 `rc=1` 退出；故允许关闭“统一晚等”作为近期方法投资，
但不允许宣称总体 late-conversion rate 为 0。`TaskHazard` 路线按冻结门关闭，转向候选特异的
schema/probe-first artifact contract。

### 3.8 已完成的 hindsight oracle headroom（探索性上界，不是 speedup）

冻结 v9 的 100 sets / 230 cards 上，120 秒 observed/missing 分别为 86/144；历史完整 runtime median
分别为 86.2466/1323.1667 秒，68/100 sets 的全部 final winner 在 120 秒仍 missing。当前 censor-aware
race 的 optimistic avoidable tail 仅 0.026163；偷看最终 `graded` 的不可实现 perfect-score-at-120 oracle
为 0.512644。两份实现从锁定 raw input 独立重算一致。

该结果只证明改善早期 score coverage 有理论成本空间，并把方法优先级从“继续调 120 秒 selector”转向
“让昂贵候选更早产生候选特异的 pristine-scoreable artifact”。禁止声称已节省 51.26% GPU，禁止据此
在旧 100 sets 上选时间阈值或策略。当前科学问题可概括为 **Anytime MLE Search under Selectively
Observable Execution Feedback**。late-artifact pilot 已把实现路线裁决到 schema/probe-first；oracle 仍只是
不可实现上界，不是效果基线或已实现的加速。

### 3.9 已完成的 FOREAGENT 官方 pair 图外部审计（CPU 描述，不是模型对决）

官方 Hugging Face 自动转换 parquet 已锁为 8,456,690 bytes、SHA256=`79363b7e...0b5f`，只含
18,361 行 pair paths/scores/ranking，不含官方逐 pair judge prediction。审计固定报告 unique solutions、
组合复用、pair-graph coverage、同 trajectory 比例、预注册 gap 桶，以及和我方真实 sibling b0 在全部/
common tasks 的 pair-weighted 与 task-macro 描述。

首次结构预检在 outcome 写盘前发现我方 b0 有 1,499 行，其中恰有 1 行 `gap_raw=NaN`；这与既有
1,498 finite headline 计数一致。冻结处理是明确记录并排除该行后再算 gap，负 gap 仍 fail-closed；
此次失败没有产生 audit JSON/CSV，也没有读取任何分布 aggregate。

独立复核通过，裁决为 **PAIRING-MISMATCH VERIFIED**：官方 `gap<1e-2` share=0.096400，我方=0.501335；
限制到 14 个同名 common tasks 后为 0.121988 vs 0.496975，task-macro 为 0.218633 vs 0.439512，
12/14 tasks 方向一致。官方 895 solutions 的每任务 pair graph coverage median=0.995918，每 solution
组合复用 median=49 次，仅 0.158651 pairs 同 trajectory。该结果直接确认“全局穷举 pair”和 agent
真实 sibling decision 是不同评测分布，但 parquet 不含官方 predictions，不能单独声称 gap 导致 61.5%。

同时修正 8 月 12 日 PBE 文档：旧 `qwen-max + description-derived unverified report + 非 COT + code
截断` 只能保留为该配置的历史结果；“报告未执行验证无关紧要”已撤回，不得再称直接裁决 FOREAGENT。
官方 executed reports 覆盖旧 300-pair 样本中的 211 pairs / 14 tasks；官方还公开 DeepSeek/GPT 三次逐
pair alignments，优先冻结并直接重算原模型的 gap 曲线，无需先花 API 重跑 Qwen。

### 3.10 FOREAGENT 官方 alignment v1 结构中止与 v2 结果

已锁定官方 26 tasks × 2 models × 3 releases 共 156 文件的固定 manifest；compact primitive-field
JSONL 共 110,620 records，SHA256=`480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe`。
v1 在写任何 accuracy/gap summary 前按完整网格门中止：DeepSeek 三次运行在 26/26 tasks 内 pair grid
完全一致；GPT run 1 在 6 tasks 合计少 8 pairs，而 run 2/3 完整。另确认 26 个 DeepSeek run-1 文件的
`log_index` 全 null，但 pair key/ordinal 唯一；Google QUEST 有 49 个含 NaN score 的 pairs，在六个文件
中对称存在。v1 结果目录为空，不允许补述任何性能结论。

v2 已在读取真实性能汇总前另立预注册：DeepSeek 完整三轮网格继续作 primary；GPT 仅在每 task 三轮
固定交集上作 replication，逐 task 报 union/intersection/排除数且比例必须 `>=0.99`；不计算跨模型
paired accuracy difference。非法 prediction 对 finite non-tie 按错误计入，禁止 complete-case 删除；
ties/nonfinite 对称隔离。raw-gap、task-internal quartile/decile、task bootstrap 与原 primary 裁决门不变。
主实现与不 import 主实现的 verifier 一致通过，但冻结裁决为 **INSUFFICIENT-SUPPORT**，不得事后改门：
DeepSeek overall task-macro=0.606698，最低任务内 gap 四分位=0.533655，最高减最低=+0.116730，
task-paired CI=[0.039283,0.196048]；GPT 对应为 0.580067、0.530522、+0.089750，差值
CI=[0.015195,0.163951]。效应门本身满足，但只有 22/26 tasks 的最低/最高四分位各至少 20 pairs，低于
冻结的 24-task 支持门；DeepSeek prediction index 在 55,167 个有限非平局 records 上覆盖 100%，但
confidence 仅覆盖 89.3614%，冻结的 joint-coverage 门也失败。该结果只能作为强描述性、双模型一致的
正向线索，不能升级为预注册确认；同一数据上禁止另开 v3 删门“修成显著”。

同时纠正 parquet 与 alignment 的版本边界：按 task 与发布物四位 solution id 对齐后，两者共同 18,270
pairs，alignment-only=168、parquet-only=91，而不是同一网格简单少 77 行；共同网格的 score 也来自不同
重评分版本，18,221 个双方均可定 winner 的 pairs 中有 5,068 个 winner 不同。因此 3.9 的结果只描述
锁定 parquet 的 pairing distribution，不能当作本节 alignment predictions 的精确 label/gap 网格。

### 3.11 Qwen/K2 exploratory 扩展与学长 checkpoint 配置审计

未进入 v11 的 Q01–Q08、K2a/K2b 共 40 个 manifest runs 已通过物理完整性与标签可用性双门：36 个
物理完整，4 个失败/取消；36 个完整 run 中 7 个没有任何 finite 外部分，最终只有 29 runs / 91 cards /
7 tasks 进入隔离的 exploratory extension。v11 保持不动；内部合并版为 16,103 cards / 696 runs，v11
是逐字节前缀，扩展与 v11 ID 交集为 0。独立 verifier 和第二次全量确定性重建均 PASS。

沿用原冻结 hold 与 v11 split universe 后，新语料只新增 1 个 b0 training pair，b1/b2 与 extension 均
新增 0；三份 frozen 文件和 v11 逐字节一致，冻结节点进入训练为 0。因此这批数据不授权 RM 重训或
“监督量显著增长”的结论；它揭示 run/card 数不能替代 clean sibling decision 支持数。

学长最新分支把 `metric_for_best_model` 从 `eval_loss` 改成 `eval_pair_accuracy`，但保留
`greater_is_better=False` 与 `save_strategy=best`。Transformers 4.49.0 官方实现会用 `np.less`，即把
更低的 accuracy 当成更优并保存。最新配置启动的 run 必须先修复再解释；0812 outcome 使用较早的
`eval_loss + greater_is_better=false`，不能事后把旧约 0.55 结果也归因于该新 bug。

这批 Qwen/K2 数据均早于评分通道机制冻结，角色只能是 exploratory/train，不能进入 3.1 的前瞻确认。

## 4. 已关闭或仅历史的方向

- **旧 HCE 三臂**：50/25/25 + 标签子采样 proxy，不符合当前 80/10/10、time-fidelity、
  full-locked 契约；6 月结果仅作历史，不继续补跑。
- **coverage-aware escalation**：120 秒后 restart/full=0.9850，resume/full=0.9312；实用成本失败。
- **critic top-2 silent routing**：有 Pareto 点，但相对 random 无显著增益，不能归因于 critic。
- **early-trace ranker**：预注册 KILL，0.6100 vs random expected 0.6433。
- **conformal risk-certificate stop**：0 次有效接受，restart/full=0.9850，预注册 KILL。
- **K≥1 potential/lookahead 作为现行 critic 的正面方法**：run-clean 不复现；8B 只能作一次防守性复核。
- **TD/RL 控制器**：不是当前主线。现有历史 journal 未通过 Prompt 0.5 的严格资格门；
  不启动 6—15 GPU·h 控制器实验。未随本次路线提交归档的探索性计数不作为论文证据。
- **把 v10/v11 当确认集**：禁止；它们源数据早于机制冻结。

## 5. 正面突破的分层路径

1. **近期最稳**：前瞻确认评分通道机制；这是数据论文可引用的正结果。
2. **近期方法化候选**：parent-certified 与执行前可观测性预测均以 **BORDERLINE** 关闭。新数据上
   若继续，必须显式记录 time-to-artifact 的删失过程和条件分数；现有结果只支持 task-conditional
   propensity，并要求对未见任务 abstain。连续 watcher smoke 已 PASS；首个低容量候选固定为
   `TaskHazard × ScoreValue`：任务级生存曲线决定等待时间，artifact 出现后才使用 pristine 分数。
   Selective Feedback Racing 进一步以 **BORDERLINE** 证明 observed score 排序稳定、但安全淘汰的只是
   便宜候选。下一裁决问题变为 silent 候选在 120 秒之后是否会转为可评分；有明显 conversion 才继续
   `TaskHazard`，否则升级 `schema-first operator`。采用独立 validation/certification；不能把“是否及时
   产物”直接当质量，也不能在旧 100 sets 上继续搜索 selector、margin 或阈值。
3. **当前已过工程门、待因果检验的 operator 候选**：让 agent 在固定早期预算内先产候选特异、
   schema-valid、可由 pristine grader 评分的 cheap probe，再在同一进程继续 full。V2 在两个新任务上
   已正式 PASS，但没有 original-prompt 对照。下一步只允许全新任务/seed 的标准 prompt vs contract prompt
   小规模 A/B；先要求 120 秒 coverage 提升、失败率不升和 full quality 无方向性损害，再冻结多候选固定预算
   搜索实验。它改变 operator/prompt，不能冒充只改评估旋钮。
4. **系统候选**：checkpoint/resume + 异步 successive halving，目标是把 continuation/full 从
   0.9312 实际压低；先做执行器可恢复性 smoke，再谈搜索收益。
5. **长期基准贡献**：持续增加独立 run 和任务平衡，发布 run-aware、gap/noise-aware、
   cost-aware 的 predictor benchmark 与完整撤回记录。

## 6. 每次继续工作前的顺序

1. 先看本文件和同日最新实验记录；
2. 检查是否有更新的 dated report/commit 明确 supersede 本文件；
3. 只读核对代码、输入 SHA、冻结集和资格门；
4. 短 CPU 审计可直接做；长 GPU/API 实验先给矩阵、总 run/replay 与 GPU·h；
5. 新结果无论正负都写入 dated report，并在这里更新活跃/关闭状态。
