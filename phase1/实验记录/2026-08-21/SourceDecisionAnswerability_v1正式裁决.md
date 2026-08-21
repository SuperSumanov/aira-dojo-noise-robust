# Source Decision Answerability v1：正式裁决

日期：2026-08-21。控制 commit：`e9f6f69ebb1364e14bd97ce0a140be6579977f33`。正式状态：
`VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY`。

## 正结果

对冻结的 3,252 个真实 source choice sets，只使用既有 pair orientation 与 provenance-bound validity
partial order。定义一个 candidate 能经 DAG 传递闭包到达同 source set 中所有其他 candidate 时，唯一 source
winner 才可认证。

published orientations 单独认证 2,344 个 winner（`0.7207872078720787`）；status-aware graph 认证
3,001 个（`0.9228167281672817`），新增 657 个，绝对提升 `0.20202952029520296`，恢复原未回答缺口的
`0.723568281938326`。train/frozen 分别新增 496/150，绝对 gain=
`0.21631051024858264` / `0.17751479289940827`。14 个支持任务中 11 个为正，dominant added-winner
task share=`0.2800608828006088`。八项冻结材料门全部通过。

仅保留 `EXECUTION_ERROR` 的强敏感性仍新增 649 个 winner，最终 rate=
`0.9203567035670357`、gain=`0.19956949569495694`、缺口恢复=
`0.7147577092511013`；train/frozen、task breadth 与 concentration 的全部门仍通过。

## 解释边界

这是 D&B release 的 answerability 正资产：status-aware partial order 使更多自然 sibling 决策点具有可认证答案。
它不是 critic/model 方法结果，也不是完整 total order。传递闭包只表示由已发布关系蕴含的偏序，不得伪装成 agent
实际记录的 comparison；未读取 numeric grade、gap、code/obs、prospective outcome 或 first-960，因此也不支持
search utility、prospective effect、MAR、算法 novelty 或 first/only。

3,001 个已回答后仍有 251 个未回答：149 个 source identity 不可恢复，102 个 identity 可用但关系不足。不得把
分母换成 identity-available parents 来抬高 headline，也不得用数值分数补齐这些 parent。

## 复现与审计

- 两次 producer、两次独立 verifier 输出逐字节一致；独立 verifier 不 import producer；
- `summary.json` SHA-256=`048f18cc2769df4c9cc4836c491c2917b2e8b051a847da20bdce454dd6592326`；
- focused=`5 passed`；完整 phase tests=`671 passed, 25 warnings`；
- forbidden-path、secret、worktree drift、正式可写文件均为 0；GPU=0、API=0、底座更新=0；
- 正式产物：`phase1/results/source_decision_answerability_v1_20260821_e9f6f69/`；
- 远端只读证据：`/research/d7/spc/yzyang4/source-decision-answerability/e9f6f69-v1`。

## 对后续路线的影响

把该 estimand 接入下一版 machine-verifiable evidence index，作为 failure-aware Decision Corpus 的独立 release
contract；不因此改变 strict-future first-960/closure 主线，也不越过 score-channel 或 Qwen GPU 的既有批准门。
