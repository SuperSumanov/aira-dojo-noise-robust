# Gap-aware critic：train/dev 资格实验（结果前冻结）

> 结果更新：固定协议已在工程修复 commit `b79717b3956a1b546943708a4c62e65841ffb663` 上正式完成，裁决为
> `RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK`。本文件保留结果前合同；正式结果与完整失败链见
> `GapAwareCritic_TrainDev资格实验_正式裁决.md`。

## 裁决边界

本实验只回答一个窄问题：在完全相同的 component-clean train/dev、代码特征与线性 critic 下，
把官方 raw-grade 分差作为**训练样本强度**，能否改善真实 sibling decision 的排序。它不是新方法
首创，也不读取 outer test、未来 cohort 或 score-channel truth；即使通过，也只能申请一个另名的
future prediction escrow，不能改写已经冻结的 future primary，更不自动授权 GPU replay。

直接相关工作已经覆盖 ordinal/graded feedback、preference intensity、adaptive reward margins、
gap/data weighting 与 listwise/pairwise ranking。因此可防守贡献只能是 MLE-agent decision corpus 上的
严格实证和可复现合同，而不是“首次利用分差”。直接边界包括：

- [*Reward Modeling with Ordinal Feedback: Wisdom of the Crowd*](https://proceedings.mlr.press/v267/liu25az.html)（ICML 2025）；
- [*Reward Learning From Preference With Ties*](https://arxiv.org/abs/2410.05328)；
- [*DORM: Preference Data Weights Optimization for Reward Modeling*](https://aclanthology.org/2025.findings-emnlp.1237/)（Findings of EMNLP 2025）；
- [*What Makes LLMs Effective Sequential Recommenders?*](https://aclanthology.org/2026.acl-long.656/)（ACL 2026，adaptive reward margins）；
- [*Explanation Quality Assessment as Ranking with Listwise Rewards*](https://aclanthology.org/2026.findings-acl.1800/)（Findings of ACL 2026）。

## 结果前结构审计

任何 model fit 前，固定输入的纯结构审计得到：

- train：4,689 pairs、28 tasks、127 comparison components、1,473 parents、4,095 endpoints；
- dev：551 pairs、25 tasks、41 components、246 parents、626 endpoints；
- train/dev unordered pair 与 endpoint overlap 均为 0；
- train/dev 每个 task 的 `gap_raw` 0.75 quantile 均严格为正；
- outer test、future truth、API、GPU、model fit 访问/调用均为 0。

## 固定矩阵

四臂共享 train-only char-TFIDF（`char_wb` 3--5 gram，30k features，`min_df=3`）与 endpoint-score
形式，margin 不使用 classifier intercept：

1. `binary_bt`：当前 mirrored hard-label logistic baseline；
2. `gap_weighted_bt`：唯一 primary candidate。每个 train task 用其 train-only gap Q75 标度，权重
   `clip(gap/Q75, 0.25, 4)`，再在 task 内除以均值，保证每个 task 的总训练质量不因加权改变；
3. `gap_permuted_bt`：每个 task 保留与 true-gap 臂逐字节相同的权重 multiset，只按
   `sha256(20260902|unordered_pair_identity)` 排序后循环移动一位，破坏“该 pair↔其真实 gap”的对应；
   它是强制机制负控，排除任意非均匀加权/正则化解释；
4. `gap_ridge`：拟合 `signed log1p(gap/Q75)` 的无截距 sparse Ridge，仅作机制诊断，不能 rescue。

置换负控也在任何 fit 前做了 structure-only 审计：28 个 task 的权重 multiset 全部精确不变；全局原权重与
置换权重 Pearson=`0.0001798458547192397`，task Pearson 的 min/median/max 分别为
`-0.2392657791965035/-0.031632580629732544/0.5787767360472819`，相同数值权重占
`0.10961825549157603`（主要来自 clip 后重复值）。该审计读取 train gap，但没有读取 dev outcome、outer test
或 future truth，model fit/GPU/API=`0/0/0`。

## 固定推断与停止规则

primary 必须同时通过 dev 上 `gap_weighted_bt - binary_bt` 与
`gap_weighted_bt - gap_permuted_bt` 两个 task-macro logged-parent/group-macro unweighted pair accuracy
对比。顺序固定为 pair→released decision parent/group→task；Improve 的 parent 是物理 lineage parent，
跨 run Draft 保留 release 中的 parent/group 身份，不把它冒充物理 parent。task paired bootstrap 20,000 次，
seed `20260901`。只有同时满足：

- support：≥20 tasks、≥200 parents、dominant-task parent share≤0.20、train/dev pair/endpoint overlap=0；
- point delta≥+0.015；
- task-bootstrap 95% CI lower>0；
- leave-one-task-out 最小 delta>0；
- 正 delta 的 task 占比≥0.60；
- 对置换负控的 point>0、task-bootstrap lower>0、LOTO min>0、正 task 占比≥0.60；

才记为 `RETROSPECTIVE_DEV_GAP_AWARE_QUALIFIED_FOR_FUTURE`。任何 weighted utility、micro、
Draft/Improve subgroup 或 `gap_ridge` 都不能 rescue。失败后禁止在同一 dev pool 上改权重、clip、Q75、
阈值或超参数重试。

机器合同：`phase1/critic_gap_aware_qualification_v1.json`。资源上限为每实现 4 个单线程 CPU fit，
GPU/API/base-LLM update=`0/0/0`。

## 首次 formal 工程失败（效果未读）

结果前冻结 commit `959764b22880d797b08a48f70654ff320b2b7d54` 的隔离预提交测试为
20/20 focused、955/955 full。fresh no-smudge formal 在 input hash 和 20/955 测试后、第一次 fit 前
fail-closed：producer/verifier 都把 dev 的合法 `intask_split="dev"` 错写为必须等于 `"train"`，因此
`read_pairs(dev)` 立即报 `invalid component-clean receipt in dev`。失败 root
`/research/d7/spc/yzyang4/critic-gap-aware-qualification/959764b-v1` 原样保留。

这次尝试没有创建 producer artifact，没有 Cards JSON parse、TF-IDF fit、四臂预测或 dev aggregate；runner 的
输入身份步骤仅逐字节 hash 了固定 Cards/train/dev/contract。outer test/future truth/API/GPU/base-LLM update 均为
`未打开/未打开/0/0/0`，真实 critic fit=0。唯一允许修复是让 train/dev 分别要求自身 role，并把 synthetic dev
fixture 改为真实 schema；合同、输入、四臂、权重、阈值、聚合、bootstrap 和 claim 全部不变。修复后必须新
commit、新 fresh worktree、新 output root 从头运行。
