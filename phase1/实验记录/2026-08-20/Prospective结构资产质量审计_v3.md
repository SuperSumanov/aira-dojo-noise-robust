# Prospective 结构资产质量审计 v3：高决策覆盖、低逐字节冗余，标签继续封存

> **后续协议纠偏：** 本文资产质量数字保留；confirmatory unlock 解释由
> `Prospective确认门_first960与closure纠偏_v5.md` 覆盖。当前是 223/960 runs，closure 未提供，并非只差
> 27 pairs。

## 问题与边界

在等待 first-1500-pair 前瞻门的同时，对当前 frozen snapshot 做一次 outcome-blind 数据资产审计。目标是验证
“语料是否已经形成真实决策支持，而不是由无决策 run、跨 run 复制或单任务堆量形成”。本审计不评估 predictor，
不读取 label/outcome/scorer prediction，也不改变 1,500-pair 门槛。

## 独立实现与结果

commit `98956a8e963324591f7b5fd95e02fec29c93c731` 的 verifier v3 不 import 生产 accumulator；它重读 42 份
已登记 blind manifest，自行按 `(task, run, parent)` 重建 1,473 个 sibling pairs，并对生产 accumulator 做八项
交叉核验。基于 snapshot `88cb791...170c8` 的两次 clean run 收据逐字节一致，SHA 为
`82bd8747f85b78c7e17429dcf20695fd0e85a9ec213edaa1787b6e035b7b51f9`。

主要 outcome-blind 结果：

- finite-decision runs 222/223，coverage=`0.9955156950672646`；
- pair-support tasks 25/25，最大任务 share=`0.1887304820095044`；
- effective pair tasks=`11.095236634194983`，归一化任务熵=`0.8467037228668219`；
- exact-code unique 5,631/5,643，fraction=`0.9978734715576821`；
- 8 个 exact duplicate groups 全部局限于同一 physical run 和同一 task，跨 run=0、跨 task=0；
- 1,431 个 decision parent groups，decision run 的 pair 数中位数=5。

这可作为 D&B 数据资产的正面证据，但不能写成方法正结果。尤其是最稀疏任务只有 1 pair，且 exact SHA 不排除
语义近重复，均需在论文中作为限制同步报告。

## 完整性与失败链

两份文件访问 trace 的禁读模式命中合计 0，credential shape 扫描 0，`label_vault_opened=false`。定向测试
`1 passed in 0.08s`，远端 clean worktree 全套 `435 passed in 35.57s`。

v2 曾先后暴露浮点末位非确定性和收据缺少 commit/Python 环境绑定；两版均不作为最终论文证据。另有两次发生在
科学计算前的启动失败（严格 shell 选项顺序、system Python 无 pytest），均保留在远端诊断链。v3 新增完整
source/environment/threshold binding 后从全新 worktree 与输出目录重跑通过。

## 裁决

当前结构资产质量证据成立；确认 cohort 为 223/960，pair 支持为 `1473 < 1500`，closure 未提供，
`vault_open_allowed=false`。继续等待 append-only 新归档；first-960 和 closure 均满足后才能冻结 exact cohort，
揭盲仍需一次性预检与用户确认。

完整证据入口：`phase1/results/prospective_structural_asset_quality_20260820_98956a8/README.md`。
