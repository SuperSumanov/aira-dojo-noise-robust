# Decision-Corpus Audit Protocol v2：lineage 闭包与 parent-complete core 预注册

日期：2026-08-29。性质：历史 v11 结构审计；CPU-only、aggregate-only。它不读取 first-960/Target-300
prospective truth/prediction，不计算 accuracy、scaling 或 search utility，也不发布 row identity。

## 1. GCCV

- **Goal**：直接用 Card `lineage.parent_id` 复核 v1 所称的 true sibling，判断九个 v11 decision sets 是否真由
  declared parent 的直接 children 构成；同时给出一个 parent-present、task/run/split 闭包完整的严格 core 与确定性
  quarantine 规则。
- **Context**：v1 已认证 endpoint 同 physical run、可映射 parent 不跨 run、同 budget train/frozen 在 pair、endpoint、
  parent ID、run 四层零交叉。但 v1 producer/verifier 都没有读取 Card lineage，故 `all_rows_true_physical_siblings=true`
  只能解释为 run-map consistency，不能独立证明 direct sibling。
- **Constraints**：固定 v11 Cards、run map、九个 pair files 及 v1 producer/verifier artifact 的 normalized-LF SHA；只使用
  endpoint/parent/task/run/split/budget 与 lineage parent，不使用 pair orientation、gap、grade、label、prediction、accuracy
  或 utility。四类 taxonomy、quarantine rule、硬门和支持门均在 lineage readout 前冻结。
- **Verification**：producer 与不 import producer 的 verifier 各自重读所有输入；双跑逐字节一致；synthetic tests 注入
  wrong parent、orphan parent、cross-run、split overlap、duplicate/reverse、hash drift 与结果字段泄漏。

机器协议：`phase1/decision_corpus_lineage_audit_v2.json`。冻结时已知 v1 的 set counts、breadth、mapped-parent
choice-set counts 与四层 overlap；尚未见 lineage parent match、四类 relation counts、strict-core counts/support/
concentration/fingerprint 或 strict-core referenced-run overlap。

## 2. 固定 relation taxonomy

每行完整且互斥地进入：

1. `parent_present_verified_direct_sibling`：两个 endpoint 的 `lineage.parent_id` 都等于 declared parent，parent Card
   存在，三者同 task、同 physical run、partition 一致；
2. `lineage_verified_orphan_parent_sibling`：两个 endpoint 的 lineage 都指向 declared parent，endpoint 同 task/run，
   但 parent Card 被裁剪；
3. `same_run_declared_context_non_sibling`：endpoint 同 task/run，但 lineage 不能证明二者是 declared parent 的 children；
4. `cross_run_declared_context`：endpoint 或可见 parent context 跨 physical run。

严格 curated core 只保留第 1 类；其余全部 quarantine。第 2 类仍可作为“lineage 可证但 parent 内容缺失”的 supporting
tier，不混入要求 parent context 的 predictor benchmark。

## 3. 固定裁决门

15 个 hard integrity gates 要求输入与 v1 dependency 精确、Card/run map 一致、taxonomy exhaustive、strict core 的
direct-child/task/run/split 闭包成立、同 budget train/frozen 在 unordered pair、endpoint、parent、referenced run 四层
零交叉、零 duplicate/orientation conflict、v1 counts/overlap 精确复现，且输出不含 row identities。

六个 train/frozen primary sets 另要求 strict-core 的 pair retention≥4/5，task/run/endpoint retention≥3/4，最大单 task/
run pair share≤3/5、1/5。extension 只描述，不 rescue primary。分类顺序固定为：integrity fail；全 rows parent-present
direct；全 rows lineage-direct 且 parent-complete core 过门；quarantine 后 core 过门；limited support。

## 4. 13 项运行前检查

1. 方向入口：已读 `phase1/CURRENT_DIRECTION.md` 顶部，当前唯一主线为 Decision Corpus + Predictor Benchmark +
   Audit Protocol。
2. 科学问题：补上 v1 未核验 lineage 的明确 verification gap，不回到 HCE、多保真、Probe 或 lookahead。
3. 输入人口：exact v11 Cards/run map/九 set/v1 artifact，路径、行数与 SHA 写入机器协议。
4. 已见/未见：v1 aggregate 已见；lineage-specific readout 全部声明未见。
5. estimand：历史 structural relation validity 与 parent-complete quarantine feasibility，不是 predictor performance。
6. 唯一变量：只新增 lineage/parent closure；不改变 pair population、budget、split 或模型。
7. 泄漏边界：不访问 prospective vault；历史 pair orientation canonicalize 后只作 identity，结果字段不进入计算。
8. 成本：CPU-only，预计分钟级；GPU·时=0，付费 API=0，模型训练/底座更新=0/0。
9. 统计单位：pair、endpoint、parent、physical run、task/component；所有 retention 用精确整数比。
10. 失败关闭：任一 hash/schema/context/overlap/duplicate 或 verifier mismatch 直接失败，不改门 rescue。
11. 复现：固定 commit、Python、所有 input/source SHA；producer/verifier 双跑与 fresh detached formal。
12. 产物：aggregate JSON、independent verification、preflight、tests、manifest；不生成 row-level filtered file。
13. 安全：不读 raw senior archives，不访问网络于 scientific runner，不写凭据；push 前执行 filename 与 blob secret scan。

## 5. 防 scoop 边界

2026-08-26 的 [TraceML](https://arxiv.org/abs/2608.26086) 已正式公开统一 version-level schema，并明确 MLEvolve
search journal 对每个 version 记录一个 parent、另存 reference edges，再线性化为 root-to-leaf branches；其数据卡还发布
human forest graph。故“首个 MLE tree/parent/graph dataset”不可守。[MLEvolve](https://arxiv.org/abs/2606.06473)
也已形式化 primary generative edges 与 cross-branch reference edges；[ReLoc](https://arxiv.org/abs/2508.07434) 已用
code-revision tree 的 parent/child/sibling preference 训练 reward model并改善搜索。tree、sibling、pairwise RM、filtering
或 graph split 的一般原语均不新。

当前可守的组合贡献只能写成：对自然发生的 MLE-agent decision corpus，同时验证 declared-parent direct-child 关系、
task/physical-run/split 引用闭包、relation strata、完整 quarantine 与双实现 aggregate receipt，并把 parent-complete
sibling curated view 与 lineage-only orphan tier 明确分开。正文不得写 first/only；正式 related-work 还需把 TraceML 的
人类广度与语义标签优势完整承认。

## 6. 当前状态

本文件与机器协议先在结果前完成冻结；population、class definition、retention/concentration 门与分类顺序均未在结果后
改变。正式结果与实现更正链见下节。

## 7. 正式结果（结果后追加）

权威 source commit=`25148420ee457018a1ee3740c4a1c42da830610d`，fresh detached formal root=
`/research/d7/spc/yzyang4/decision-corpus-lineage-audit-v2/formal-2514842-v5`。分类为
**`HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT`**：15/15 hard gates 全过，36 个 support gates
过 35 个。8,107 行全部为 lineage-direct sibling；parent-present strict core=`7579`，orphan-parent tier=`528`，
same-run non-sibling/cross-run=`0/0`。四层同 budget train/frozen overlap、duplicate/reverse 与 row metadata violation 全为 0。

唯一失败门是 `frozen:b2` strict core 最大单 run share=`52/254=26/127=0.20472440944881889`，超过冻结上限
`1/5`，故不得升级总分类。其余五个 primary sets 全部 support 过门；既有 headline `frozen:b0` strict core=
`1424/1498` pairs、`21/22` tasks、`83/92` runs、`1929/2022` endpoints，最大单 run share=
`67/356=0.18820224719101122`。producer/verifier A/B 各自逐字节一致，独立 verifier 不 import producer且逐字段相等；
focused/full=`13/1488 passed`（47 warnings），forbidden opens/network=`0/0`，formal manifest=
`117678f333d2f053e2cc29aa8ca1e34238a39e52df5444bdd491e4d0ea9d36e4`。正式 aggregate-only 包见
`phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842/`。

## 8. 实现更正与撤回链

`formal-170f095-v1` 因输入 root 错误在 scientific readout 前停止；`formal-9628c23-v2/v3` 在 full tests 后发现 parser
把 nested Card task object 整体字符串化，首行 task consistency 失败且无结果。`formal-89689b2-v4` 虽输出完整 receipt，
仍受同一 schema parser 错误影响，其 integrity-fail 结论撤回。生成器源码明确 pair task 来源为
`card["task"]["name"]`；最终 producer/verifier 按这个既有 schema 修复并新增 nested-task 等价测试。协议、人口、taxonomy、
门槛与分类顺序从未改动，v5 为唯一权威 scientific readout。

发布 commit=`7e625c603c8c47f433af2967f66c5a7c4b82ba0f` 的 fresh detached post-push 又完成 package manifest
`16/16`、focused/full=`13/1488 passed` 与 producer/verifier exact replay；forbidden/network/credential=
`0/0/0/0`，post-push manifest=`4fba37aa41c7563d49b9226d80b9ecb814125972507a317992e3d79b1db0daa4`。
