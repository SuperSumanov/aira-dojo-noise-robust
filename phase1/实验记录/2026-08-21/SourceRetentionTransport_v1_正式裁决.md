# Source Retention Transport v1：正式裁决

日期：2026-08-21。正式代码 commit：`d21166fb344c0645ed1e31ea6bc7e7487e441e6f`。
状态：`VERIFIED_TASK_CONDITIONED_SOURCE_RETENTION_TRANSPORT`。

## 核心结果

唯一输入是先前独立复核的 3,252-parent `per_parent.csv`，SHA-256=
`75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`。train/frozen/extension 分别有
2,293/845/114 parents，来自 333/92/15 个 physical runs。正式分析只用 train 定义 task profile，并在
physical-run 无交集的 frozen role 一次性验证；extension 不进入 headline。

15 个任务通过事前固定的支持门（train parents≥30、frozen parents≥15）：

- train→frozen task-equal finite source-retention Spearman rho=`0.8151043256715026`；
- 100,000 次 task-label 双侧置换 `p=0.0005999940000599994`；
- 20,000 次 paired-task bootstrap 95% CI=`[0.5368038356525456,0.9594112875401973]`，有效率=1.0；
- 15 个 leave-one-task-out rho 全正，最小=`0.779067271041392`；
- parent card 存在时的敏感性 rho=`0.8295238095238096`；raw retention 敏感性与 primary rho 相同；
- train 定义的 top/bottom tertiles 在 frozen 上 task-equal mean retention 为
  `0.9970588235294118` / `0.7799099692577952`，差=`+0.21714885427161656`。该差是预指定解释量，
  不是额外挑出的解锁门。

六个冻结门全部通过。允许的正主张是：在当前 AIRA 数据生成/发布管线中，source retention 具有可跨
disjoint-run release roles 复现的 task-conditioned structure；将所有任务汇成一个缺失率会掩盖稳定异质性。
结合先前 902 个已恢复 missing statuses 中 893 个 execution errors，这支持发布一个 failure-censored、
task-stratified decision resource，并把 per-task retention/coverage 设为 benchmark 必报项。

## 完整性与失败链

- producer×2 的全部 artifact 逐字节一致；
- 不 import producer 的 verifier×2 逐字节一致，独立重建最大差=0；
- focused tests=`6 passed`；全套 `phase1/tests`=`627 passed, 25 warnings in 65.21s`；
- forbidden scientific path hits=0；文件名与高置信内容秘密扫描均为 0；可写文件=0；
- producer summary SHA-256=`1342681eea0d33925bdd018b4c42cb93df6a3b0449d4652d687f46a50a187879`；
- producer manifest SHA-256=`6eafca0883d1cad943907679fbb01e6bcbabb9c47f8439bda63ceacbe52366dc`；
- 全量 formal `SHA256SUMS` 文件 SHA-256=
  `1fc7459dfa15080c0b6a06992466e6f00b372119de5878e842f1d9795533541c`；
- 远端只读完整产物：
  `/research/d7/spc/yzyang4/source-retention-transport/d21166f-v1`。

首次 commit `6739948...` 的 runner 在 focused tests 后、producer module import 前因未设置 worktree
`PYTHONPATH` 失败；没有 artifact、summary、task profile 或统计量。失败目录原样保留。修复只显式绑定
`PYTHONPATH=${worktree}`，没有改输入、分母、metric、支持门、seed、重复数、裁决阈值或科学源码；正式新
commit/新 worktree/新目录从头运行。

## 不允许外推

本实验只读 parent/task/run identity、source-declared size 与 finite availability bit；没有读取 code、numeric
outcome、better/worse、gap、prediction 或 prospective vault。它不证明 missing-at-random 的反面在个体层成立，
只证明缺失率不可跨任务交换；也不证明 task 的因果作用、完整 source choice set、缺失候选的数值质量、
censor-aware selector/search utility、跨 agent 迁移或方法 novelty。GPU=0、API=0、底座更新=0。

该结论是 Decision Corpus 数据/测量贡献，不改变 first-960/closure、strict-future transition escrow 或 clean
Qwen scaling 的既定门。
