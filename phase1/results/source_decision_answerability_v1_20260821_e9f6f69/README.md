# Source Decision Answerability v1

正式状态：`VERIFIED_MATERIAL_SOURCE_WINNER_ANSWERABILITY_RECOVERY`。控制 commit：
`e9f6f69ebb1364e14bd97ce0a140be6579977f33`。

## 问题与裁决

本轮只把已发布的 finite-finite `better -> worse` orientation 与 status-certified
`valid -> certified-invalid` edges 组成 provenance-bound DAG。对每个冻结的真实 source choice set，仅当某一
candidate 经传递闭包可达集合中其余所有 candidate，才记为“唯一 source winner 可认证”。没有读取 code、
observation、numeric grade、gap、prospective outcome 或 first-960。

在全部 3,252 个 source parents 上，仅靠 published orientations 可认证 2,344 个 winner，rate=
`0.7207872078720787`。加入 validity partial order 后可认证 3,001 个，rate=
`0.9228167281672817`；新增 657 个，绝对 gain=`0.20202952029520296`，恢复原 908 个未回答
parent 中的 `0.723568281938326`。最终 251 个仍不可回答，其中 149 个缺 source identity，另 102 个虽有
identity 但现有关系不足。

role 分层没有显示该结果只来自 train：

| role | parents | published winners | status winners | 新增 | 绝对 gain |
|---|---:|---:|---:|---:|---:|
| train | 2,293 | 1,613 | 2,109 | 496 | `0.21631051024858264` |
| frozen | 845 | 628 | 778 | 150 | `0.17751479289940827` |
| extension | 114 | 103 | 114 | 11 | `0.09649122807017543` |

14 个 task 达到冻结的 source pair capacity≥100，其中 11 个 gain>0；新增 winner 的 dominant-task
share=`0.2800608828006088`。主分析的八项预注册材料门全部通过。

## 强敏感性

删除全部 `OFFICIAL_GRADE_ABSENT` edges、只保留 `EXECUTION_ERROR` 后，仍可认证 2,993/3,252，
比 published baseline 新增 649 个；winner rate=`0.9203567035670357`，绝对 gain=
`0.19956949569495694`，未回答缺口恢复=`0.7147577092511013`。train/frozen gain 分别为
`0.2132577409507196` / `0.17751479289940827`，11 个 supported tasks 为正，dominant share=
`0.28197226502311246`；全部七项强敏感性材料门也通过。因此 headline 不依赖 grade-absent 类别。

## 允许与禁止的主张

允许主张：对当前固定 release，failure-aware partial order 把真实 source-level unique-winner
answerability 从 72.08% 提升到 92.28%，使数据集能直接回答更多 sibling choice sets。

禁止主张：这不是完整数值 total order；传递推断关系不是 logged comparisons；它不证明 MAR、predictor
accuracy、search utility、算法 novelty 或 prospective effect，也不能把 3,001 个可认证 winner 当成 critic
正确选择的次数。

## 完整性

- producer×2 与不 import producer 的 verifier×2 均逐字节一致；
- focused tests=`5 passed`；完整 phase tests=`671 passed, 25 warnings`；
- forbidden scientific path hits、输入/输出秘密命中、worktree 漂移与正式可写文件均为 0；
- 两次正式执行前 runner 失败均已保留：首次为 sparse-worktree 路径绑定，第二次为 frozen pair 的
  canonical null-run schema；两次均在构图/summary 前退出，修复没有改变输入、estimand 或材料门。

关键 SHA-256：

- `summary.json`：`048f18cc2769df4c9cc4836c491c2917b2e8b051a847da20bdce454dd6592326`；
- `per_parent.csv`：`b2488d059ce4fafacc321e98fb4f4e82b5f0b4d4abc86a413d9e6f80da0cb4d4`；
- `per_task.csv`：`7c1669f101706efc76c0894c76f5abc382eb842401141b01037505404d168fb5`；
- `independent_verification.json`：`05e4398e65ba9b19559247cf084359eba0d6ec18753b72dbe6fb8f780e1c845e`；
- 本地回传的远端 `SHA256SUMS`：`9fb4228c5905f951338d21a84ddd2355075b8f5fb04eec72039aaa317b22568b`。

完整只读远端产物：

`/research/d7/spc/yzyang4/source-decision-answerability/e9f6f69-v1`
