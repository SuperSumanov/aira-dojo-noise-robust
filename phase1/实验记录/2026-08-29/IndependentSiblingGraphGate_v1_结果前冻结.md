# Independent Sibling Graph Gate v1：结果前冻结与 budget-variant 碰撞

日期：2026-08-29

状态：senior-0819 crosswalk、strict residual 数量和所有 acquisition curves 未读。

## 1. 为什么 train:b1/b2 不能确认 b0

0IN 的 b0 结果后，原计划是在尚未读取 acquisition curves 的 `train:b1/b2` 上做低预算确认。曲线读取前先做了两个
独立实现的 identity census，结果逐项一致：

| 集合 | pair overlap | endpoint overlap | parent overlap | physical-run overlap |
|---|---:|---:|---:|---:|
| b0–b1 | 848 | 1,307 | 589 | 140 |
| b0–b2 | 677 | 1,024 | 457 | 105 |
| b1–b2 | 690 | 1,042 | 465 | 105 |

b1 总共只有 861 pairs / 1,325 endpoints / 140 runs，b2 只有 692 / 1,044 / 105；所以 b1 的 140/140 runs、
b2 的 105/105 runs 都已经在 b0。它们是高度嵌套的 budget variants，不是新的 physical execution population。
因此不运行 b1/b2 acquisition curves，也不把它们当 replication。

## 2. 下一个结果前资格门

候选改为已发布 quarantine certificate 中的 senior-0819 **train-only verified-direct-sibling core**。已知 aggregate 是
952 train rows；318 条历史 test core 明确禁止进入本轮。候选是否与 v11 b0 重合、剔除后剩多少 pair/run/task，在冻结时
均未读取。

固定 strict residual rule：若 senior train-core row 的任一 endpoint 或 declared parent ID 出现在 v11 b0
`endpoints ∪ parents`，或其 physical run 出现在 v11 b0 runs，就整行剔除。task 可以重合，因为目标是同类 MLE tasks
上的新 physical executions，而不是 leave-task-out transfer。

## 3. 固定门

所有输入、v11 lineage certificate、senior quarantine result/verifier/manifest 和预解析 credential scan receipt 必须精确
SHA 绑定。safe Cards 只能在 scan receipt 确认 remaining hits/private-key markers 都为 0 后解析；原始 senior archives
仍禁止打开。

strict residual 必须同时满足：

- pairs≥500 且保留 train core 的至少 1/2；
- endpoints≥500、parents≥250、physical runs≥75、tasks≥15；
- 最大单 task pair share≤1/3，最大单 run pair share≤1/10；
- 与 v11 b0 的 pair/endpoint/parent/run overlap 全为 0，duplicate/reverse conflict 为 0。

任一 integrity 失败报 `...INTEGRITY_FAIL`；integrity 过而支持不足报 `...LIMITED_SUPPORT`；全过才报
`HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE`。不得结果后改 residual rule、阈值或把 test rows 补进来。

## 4. 结论边界

本轮只是**人口资格门**，不计算 acquisition curve，更不计算 critic accuracy/search utility。即便 FEASIBLE，也必须在看该图
曲线前另冻 label-yield confirmation protocol；即便随后曲线为正，也只是独立历史图上的 resource-allocation extension，
不是 active learning 或 graph acquisition 方法首创。

机器协议：`phase1/historical_independent_sibling_graph_gate_v1.json`。producer 只输出 counts、shares 与不可逆 fingerprints。
独立 verifier 不 import producer，使用此前独立 Card/decision decoder 重建 senior core，并另写 v11 parser、strict residual、
profile、duplicate、fingerprint 与分类逻辑；producer/verifier focused synthetic=`15 passed`。固定 formal runner 将做 exact-SHA
detached worktree、credential-first safe-Cards、producer/verifier 双 seed 逐字节复验、完整测试、file/network trace 与 blob
secret scan；只有 runner 的公开冻结提交完成后才允许 crosswalk readout。GPU/API/model-fit/base-update=`0/0/0/0`，前瞻
first-960/Target-300 值未读。
