# TF-IDF cost--utility：V1 结构失败与 V2 结果前修复

日期：2026-08-23。V1 状态：`V1_INVALID_STRUCTURAL_GRAPH_ASSUMPTION`。V2 状态：
`FROZEN_AFTER_V1_STRUCTURAL_FAILURE_BEFORE_AGGREGATE_UTILITY_OBSERVATION`。

## V1 实际发生了什么

V1 commit `cd8254567d5234fef215acb40acb0b569e44516e` 在远端 fresh no-smudge worktree 通过 9/9
聚焦测试、818/818 全测试（33 warnings，70.06s）和 0/0 凭据扫描。五个正式输入 SHA 与协议完全一致。
第一个 producer 读取 released historical Cards 后，在任何 summary/per-pair/per-parent artifact 写出前以
`parent margin graph is disconnected` 中止；elapsed=6.71s，max RSS=1,382,116 KiB。第二 producer 和两个 verifier
均未运行，失败目录原样保留。future/prospective truth、GPU、API、model fit、base-LLM update 均为 0。

必须明确：历史 Cards bytes 已被程序打开，且程序在内存中先构建了逐 pair gap 后才遇到 graph exception；但没有
任何 grade、gap、utility 或 gate 数值被打印/落盘/返回给研究者。因此 V2 不能写成“grade bytes 从未打开”，只能写成
“在任何 aggregate utility 被观察前，由纯结构失败触发的协议修复”。

## 结构诊断与为何不能 complete-case

只读冻结 per-pair 文件、不读取 grade 的双分组诊断得到：1,482 pairs、796 parent groups；786 连通，10 个恰有
两个分量。dev 为 246 groups（1 断连），test 为 550 groups（9 断连）。Draft/Improve 合并前后完全相同，
mixed-semantics parent=0。若直接丢掉 10 个 parent，会违反 V1 的 no partial salvage，也会形成 outcome 前未声明的
complete-case estimand；因此 V1 只能 INVALID，不能报“剩余 98.74% parent”的结果。

## V2 唯一修复

V2 不丢任何 row、不填补断连分量之间不可识别的 score offset。它把每个
`(split, task, parent, semantics)` 无向 pair graph 确定性拆为最大连通 comparison components，按最小 endpoint
排序，并由完整 endpoint 集合哈希生成 component ID。全部 1,482 pair 必须恰好分配一次，得到 806 components；
test 固定为 559。这个单元只称 **logged comparison component**，不冒充完整 physical parent choice set。

两个 primary estimand 保持不变的统计含义：task 内 raw-gap-weighted pair accuracy，以及 task 内 component
oracle-gain capture；随机基线分别为 0.5/0。V2 正门是 test≥20 tasks、≥300 components、两个 task-bootstrap
95% CI 下界分别严格高于 0.5/0，再加全部结构/方向/hash/cost 门。50,000 bootstrap、seed、subsets 和成本输入均
不变。失败后不得丢 component、改 gap transform、筛 task 或只报其中一个 primary。

producer 复用已冻结 V1 的通用输入/grade/bootstrap函数，但 component partition 与 aggregation 新实现；独立 verifier
不 import producer，使用原独立 verifier 的输入读取和数值原语，另写 DFS partition、component solver、metrics、CSV、
manifest 与 gate 重算。新增攻击测试必须覆盖断连 parent 零丢弃、structure receipt 篡改和同步更新 manifest 后的
component utility 篡改。

直接证据：

- `phase1/results/tfidf_retrospective_utility_v1_invalid_20260823/`；
- `phase1/tfidf_retrospective_component_utility_protocol_v2.json`；
- `phase1/tfidf_retrospective_component_utility_audit.py`；
- `phase1/verify_tfidf_retrospective_component_utility_audit.py`。

## V2 首次执行的复现性中止

V2 exact commit `db7069db570523ac740b920202e37abb6493bc02` 的首次 launcher 在 import 阶段因文件路径启动
方式错误而退出，Cards 未开。改成 `python -m` 的全新目录后两个 producer 完成，但产物不逐字节一致，独立 verifier
以 `V2 component rows differ` 拒绝。差异只在浮点末位：summary 82 个数值字段，max abs=
`3.552713678800501e-15`；40 个 component rows、37 个 task CSV rows 不同。根因是通用 solver 对 endpoint `set`
无排序求均值，受进程 hash seed 影响。

因此两个 producer 即使打印相同状态也全部无效，不作结果。修复只在 producer/verifier 各自 solver 中把 endpoints
排序，不改协议、输入、component 定义、估计量、bootstrap 或 gate；新增 `PYTHONHASHSEED=11/29` 两个独立进程
逐字节一致测试。修复后本地聚焦测试 14/14；必须再次 commit/push 与 exact-commit 全测后才能重跑。
