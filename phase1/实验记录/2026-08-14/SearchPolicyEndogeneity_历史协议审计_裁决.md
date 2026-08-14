# Search-policy endogeneity：历史协议审计裁决

日期：2026-08-14。协议：`search_policy_contract_audit_v1`。

裁决：**`HISTORICAL_POLICY_AUDIT_INVALID_NO_CAUSAL_CLAIM`**。

## 1. 正式运行事实

冻结 commit `d6b1e388e79ada7f5045a56235844902d2431357` 的远端正式运行通过全部 13 项预检和
28 项测试，固定 inventory 为 MCTS 14 个 archive、0805 候选臂 8 个 archive。producer 随后在读取结构时
以 `AuditError: non-root parent contract violated`、退出码 1 fail closed；正式结果目录没有产生，未读取
grade、metric outcome、frozen pair、代码或 env。

安全诊断只输出 schema：首个异常来自 MCTS/0802 的 `denoising-dirty-documents` seed 4，journal SHA-256
为 `70a6b991754274f477aa52fb27659a3197696c8642beffd30ec6e899084d9266`；step 21 为非 root 却有
`parents=[]`。该 archive 的六个 complete runs 共 180 个非 root 节点，其中一个违反契约。继续安全枚举时另有
archive 超过预注册的 64 MiB allowlisted-member 上限。按事前规则，两处均不在看见数据后放宽。

## 2. 即使修结构也不能恢复因果解释

正式结果之前已锁定的 nomad 样本公平契约差异为：

| 字段 | 0802 MCTS 样本 | 0805 候选样本 |
|---|---:|---:|
| 底座 | `deepseek-v4-flash` | `qwen3.5-397b-a17b` |
| execution/interpreter timeout | 14,400 s | 4,800 s |
| children/expansion | 5 | 2 |
| total time limit | 86,400 s | 82,800 s |
| source commit | 不同 | 不同 |

prompt SHA 与 temperature 相同不能抵消这些关键差异。进一步检查两个配置对应 commit 之间的 MCTS 实现，
没有找到可追溯的 `selection_mode` 或 sequential/no-selection 改动；现有 solver 仍按 UCT 选择叶节点。因此
0805 的 policy 标签本身也缺少已提交源码证据，可能来自未提交 patch 或口头批次命名，不能当自然实验。

## 3. 撤回与保留

- 撤回 `amplifier_test.py` 在两个任务、fragment 身份上得到的“0.73 对 0.56”因果表述；它只能保留为
  已知 confounded 的探索性历史，不进摘要、主表、正面结果或 power calculation。
- 不把 producer 异常写成 `NO_EFFECT`；这是协议无效，不是效应为零。
- 不继续在 0802–0805 上换阈值、加大 member cap 或筛掉异常 run 来挖漂亮结构数。
- 可保留的科学问题是：adaptive search 会不会让 branch-value label 同时编码候选质量和分配给它的计算量；
  但当前历史数据不能回答。

## 4. 下一步可识别设计

重新采集一个显式、版本化的 matched intervention：同一 parent 先生成固定 `B` 个 siblings，再在完全相同的
model、prompt、operator eligibility、数据、硬件、单次 timeout 与总预算下，为每个 sibling 分配相同 `K`
个 continuation replicates。记录 assignment probability、停止原因、实际 wall/GPU/API cost 和每个 replicate
的 source identity。标签固定为同预算 continuation return 的均值、方差与 best-of-K；在 fresh physical runs
比较 immediate score、historical adaptive subtree max 与 balanced-K label 的 test-retest、run/task-held-out
ranking 及 fixed-budget top-1/regret。

这只是数据/评估干预候选；在配置矩阵、run 数和 GPU·时预算获批前，不启动长或贵采集。

直接证据：`phase1/results/search_policy_contract_audit_invalid_20260814/`。
