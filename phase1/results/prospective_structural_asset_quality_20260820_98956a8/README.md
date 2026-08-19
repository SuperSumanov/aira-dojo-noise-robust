# Prospective corpus outcome-blind 结构资产审计（v3）

> **后续协议纠偏（2026-08-20）：** 本页的结构资产数字有效，但“只差 27 pairs”遗漏了结果前固定的
> first-960 停止规则与 accrual closure。正式状态为 223/960、尚差 737 runs，详见
> `phase1/results/prospective_confirmatory_gate_correction_20260820_757ced0/README.md`。本页 v3 receipt 仅作为
> provisional-prefix 资产质量证据，不再作为 confirmatory unlock gate。

本审计只回答“当前前瞻 cohort 是否已经形成一个可用、非明显重复、非单任务主导的决策语料资产”。它不读取
label、grade、outcome、scorer prediction 或 endpoint code，也不构成 critic/方法效果结论。

## 固定输入与复现绑定

- source commit：`98956a8e963324591f7b5fd95e02fec29c93c731`
- verifier protocol：`prospective_structural_gate_independent_verifier_v3`
- frozen snapshot：`88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`
- Python：`3.11.15`；收据内记录了实际 executable、全部四项门槛和 `randomness_used=false`
- 最终收据 SHA256：`82bd8747f85b78c7e17429dcf20695fd0e85a9ec213edaa1787b6e035b7b51f9`

同一 clean detached worktree 下独立运行两次，`receipt_a.json` 与 `receipt_b.json` 逐字节一致。验证器不 import
生产 accumulator，而是从 42 份登记后的 blind manifests 按 `(task, run, parent)` 重新组合 sibling pairs，再与
生产计数做八项交叉核验；八项均通过。

## 可写入 D&B 资产叙事的正结果

- 223 个 eligible physical runs 中，222 个存在 finite sibling decision，run coverage=
  `0.9955156950672646`；共 1,431 个 decision parent groups，每个 decision run 的 pair 数中位数为 5。
- 25/25 个 eligible tasks 都至少有一个结构决策对；最大任务提供 278/1,473 pairs，share=
  `0.1887304820095044`，低于预注册上限 0.25。pair-task HHI=`0.09012876723314295`，对应 effective tasks=
  `11.095236634194983`，归一化熵=`0.8467037228668219`。
- 5,643 个 endpoints 有 5,631 个不同 exact-code SHA，逐字节唯一率=`0.9978734715576821`。8 个重复 SHA
  groups 共多出 12 个 endpoints；跨 physical run 重复组=0，跨 task 重复组=0。
- cohort 覆盖 6 个 intake days；每天都有 finite-decision runs 和多任务 pair support。

这组结果支持一个正面但边界清楚的主张：当前资产不是由无决策 run、跨 run 逐字节复制或单一任务堆量造成的；
它已经具有很高的真实 run 决策覆盖和较广的任务支持。这是数据集/benchmark 贡献，不是“critic 已经有效”。

## 仍未通过的门与限制（本节的旧 gate 解释已被上述纠偏覆盖）

- 当前前缀为 223/960 runs 与 `1473 < 1500` pairs；确认 run stop 尚差 737，且 closure 未提供。
  支持门中的 finite-decision run、task、dominant-share 三项已过；`vault_open_allowed=false`。
- 任务覆盖不等于每任务都足够做推断：支持最少的任务仅 1 pair。论文必须同时报告 per-task support，不能只报
  25/25 coverage 或 effective-task 数。
- exact-code SHA 只能排除逐字节复制，不能排除语义近重复；后续 near-duplicate 审计需另立不看 outcome 的协议。
- “6 个 intake days”是采集支持描述，不证明时间平稳性或 future generalization。

## 安全与测试

- 两份 `strace -f -e trace=file` 对 `label_vault|grade|outcome|blind_scores|score_index|frozen` 的命中均合计为 0。
- 两份收据的 API key/credential shape 扫描为 0；收据不输出 task name、card id 或代码。
- 定向测试：`1 passed in 0.08s`；clean Linux 全套：`435 passed in 35.57s`。
- 完整 trace 留在受控远端，不进入 Git；SHA 和远端位置记录于 `verification_summary.json`。

## 失败与替代链

1. v2 首次双跑暴露浮点聚合受 set iteration 顺序影响，收据末位漂移；该版作废。
2. commit `ea39985...` 固定排序后双跑一致，但自审发现收据未把 Git commit 与 Python 环境写入产物，故 v2
   只作中间审计，不作为论文最终证据。
3. 两次工程预检分别因 `set -u` 早于环境初始化、误用无 pytest 的 system Python 退出；均发生在验证器运行前。
4. v3 在新 commit、新 worktree、新输出目录从零运行并通过上述全部门，只有这一版作为当前正式证据。
