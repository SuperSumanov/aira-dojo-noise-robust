# Prospective confirmatory gate 协议纠偏（v5）

## 纠偏原因

此前 v3 structural verifier 正确重建了当前 223 个 eligible runs 的 1,473 个 sibling pairs，也正确给出了
outcome-blind 资产质量指标；但它错误地把“至少 1,500 pairs / 150 finite-decision runs / 15 tasks / dominant
share≤0.25”四项**支持门**当成了确认 cohort 的停止门，并遗漏了结果前功效附录已经固定的：

1. 唯一确认 cohort 是按 `(generation_started_at_utc, source_sha256, physical_run_id)` 排序的 first 960；
2. first 240 只作必报 pilot，不能用于确认性裁决；
3. 即使达到 960，也必须先有独立于 outcome 的 accrual-closure receipt，声明所有计划归档已上传且
   `outcomes_read=false`，随后才能冻结 identity；
4. 四项结构支持门只在 frozen first-960 内裁决，不能替代 960-run 停止规则。

没有找到任何晚于该功效附录、在 outcome 前显式 supersede 上述规则的预注册。因此“只差 27 pairs 即可揭盲”
正式撤回。纠偏发生在任何 label/outcome/scorer prediction 被打开之前，现有标签资产没有被消耗。

## v5 固定与独立结果

- source commit：`757ced0b2d36d8b105b5d25f23df577ac2bc07e6`
- protocol：`prospective_structural_gate_independent_verifier_v5`
- snapshot：`88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`
- receipt SHA256：`9d12e2a8cac555a9eef6743169d0b922c2840b1e6d9c20996662e1910b65e875`

v5 在 CLI 层锁死 960/1,500/150/15/0.25 五项阈值，不能通过参数降低；独立按预注册全序重建 first-960
前缀，并与 accumulator 的 all-eligible 和 provisional-first960 计数、任务 pair counts 分别交叉核验。当前结果：

- confirmatory runs：223/960，尚差 737；
- structural pairs：1,473/1,500，尚差 27；
- finite-decision runs：222/150，通过支持下限；
- pair-support tasks：25/15，通过支持下限；
- dominant pair-task share：`0.1887304820095044 <= 0.25`；
- accumulator status：`PROSPECTIVE_COHORT_COLLECTING`；
- accrual closure：未提供；
- 最终状态：`CONFIRMATORY_COHORT_COLLECTING`，`vault_open_allowed=false`。

按学长理想 60 runs/day 的生产速度，737 个剩余 runs 对应 `12.283333333333333` 个理想生产日；这只是吞吐 ETA，
不授权按 pair 数提前停产，也不假设每天所有 runs 均 eligible。

## 安全与失败链

两次 clean detached run 的 v5 收据逐字节一致；禁读路径访问模式命中 0，credential shape 命中 0。定向测试
`1 passed in 0.09s`，Linux 全套 `435 passed in 36.26s`。

v4 的科学计数已经得到 223/960，但其 verifier 内部用全仓库 `git status` 做 source cleanliness 检查，导致 trace
对 frozen/regrade 文件名发生 54 次 metadata `stat`。未读取这些文件内容，但按本项目“禁读路径零接触”标准，
v4 仍作废。v5 改为只核对当前 verifier 文件的 committed Git blob 与 worktree blob，不遍历仓库，随后从新
worktree 与新输出目录完整重跑。

## 保留的正资产结论

v3 报告的 222/223 finite-decision run coverage、25/25 task pair coverage、99.78734715576821% exact-code
unique、跨 run/跨 task exact duplicate group 均为 0，仍是当前 provisional first-960 prefix 的有效
outcome-blind 数据质量描述。撤回的是“确认门只差 27 pairs”，不是这些结构资产数字，也不是语料已积累的价值。
