# Decision Predictor Estimand Panel v1

本目录在 first-960 closure 与任何 prospective effect 之前冻结通用 predictor benchmark 的汇总面板。结构图谱已经证明
run、endpoint、pair 三种权重会产生相反的任务均衡趋势，因此不能等 accuracy 出现后再选择 headline。

Generic benchmark 第一行固定为 `task_macro_parent_macro_pair_accuracy`：先在同一 physical decision parent 内平均
informative canonical sibling-pair credits，再在 task 内平均 parents，最后 tasks 等权。必须同时报告且不得 rescue 的三行
是 task-pair macro、task→run→parent→pair macro 和 pair micro。

这个面板不改写既有实验：

- scaling confirmation 仍由原冻结 task-macro pair primary 裁决；
- component-breadth 仍由原冻结 task-macro parent-macro primary 裁决；
- truth、support gate、effect floor 和 experiment-specific bootstrap 均以各自原契约为准；
- 任一原 primary 失败，面板其他行、task subgroup 或 truth channel 都不能救回。

所有 arm contrast 要求 exact common pair support，先在 pair 上求差再按同一 hierarchy 聚合。Generic inference 固定为
20,000 次 task bootstrap（seed `20260901`）+ 全部 LOTO，另给 physical-run clustered sensitivity；pair-i.i.d. CI 禁止
进入 headline。

机器 contract SHA-256=`4f394d0e0437992eb9d3e5f3aa56f83df86ffcbda68a752ebada4e306bf7adea`；独立 receipt
SHA-256=`fcb74182271d186993538a6d6517fe45e7f8ae6e6f2ccd1eaf5975ea559426de`。fresh Linux
focused/full=`5 passed in 0.13s` / `1040 passed, 47 warnings in 78.58s`，verifier A/B 逐字节一致；正式
`SHA256SUMS` hash=`cd198c5f55af5af299c66b06b0c1d2a6447701539dbaa688d2b9b575b723d402`。

本冻结只验证 schema、hash 与显式 authority firewall，不认证统计语义，也没有读取 prospective
truth/prediction values。credential filename/content/forbidden-open hits=`0/0/0`；GPU/API/model-fit/base-LLM
updates=`0/0/0/0`。
