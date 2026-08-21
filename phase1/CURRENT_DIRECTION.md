# 当前研究方向唯一入口（2026-08-21）

> 本文件按日期与撤回链整理，覆盖最近两周的实验记录与 Git 提交。后续实验先读本文件，
> 不得用更早报告、旧 `AGENTS.md` 摘要或旧 HCE 配置覆盖这里的裁决。

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
