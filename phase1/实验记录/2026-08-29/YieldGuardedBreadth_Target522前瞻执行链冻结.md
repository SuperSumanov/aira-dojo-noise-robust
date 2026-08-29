# Yield-Guarded Breadth：Target-522 前瞻执行链冻结

日期：2026-08-29
状态：`IMPLEMENTATION_FROZEN_BEFORE_TARGET522_CANDIDATE`
科学结果：尚无；本文只记录结果前实现、测试与边界。

## 1. 问题与角色

在一次完整 endpoint execution 才返回绝对 grade 的设定下，只有同一 sibling group 中两个被执行的 endpoint
才能闭合一个 pair label。当前问题不是提高已训练 critic 的 accuracy，而是：在相同 endpoint execution budget 下，是否存在
一条只读预执行拓扑、同时满足下列固定条件的 nested acquisition trajectory：

1. 六个 checkpoint 的闭合 sibling pair 数逐点不低于 exact-B `uniform_edge` 的 256-seed median；
2. 整条 trajectory 的闭合 pair 积分不低于 baseline median；
3. task/run breadth 分别至少为 baseline trajectory median 的 `6/5`、`11/10`；
4. 末点 parent breadth 至少为 baseline 的 `9/10`；
5. 末点 task/run edge share 分别不超过 `1/3`、`1/10`。

协议 `phase1/yield_guarded_breadth_forward_target522_v1.json` 已于 `2026-08-29T04:38:00Z`、任何
Target-522 candidate identity/count/profile 出现前冻结；SHA-256 为
`ce50247e662137db6172e7b0c4181c68b0c3aed0e968e9b8c89e6653d99f13cf`。它只允许一次自动选中的、相对 snapshot 887
physical-run disjoint increment，不允许人工换 snapshot、混入 baseline、结果后改门或用其他 Target-522 假设 rescue。

## 2. 本次实现

- producer 从固定 selection receipt 重建 baseline/candidate，逐字节重验 append-only run/endpoint ledger，只保留完整新
  physical runs；它逐个绑定 intake summary 中的 `eligible_structural_pairs.jsonl`，并要求这些文件与 blind manifest
  重建出的 sibling clique 完全相等。
- baseline 保留旧 edge-priority，但把两个 endpoint 确定性线性化，并以独立 salt singleton-fill，强制每 seed、每
  checkpoint `selected_endpoints == budget`。
- MILP 只读 unordered endpoint/parent/task/run topology；endpoint、closed-edge、task、run、parent 变量全部为二元，六个
  checkpoint exact-B 且 nested。公开文件只含 aggregate；endpoint witness 只写远端 mode-0600 private 文件。
- verifier 不导入 producer，也不再复用 producer 的 MILP 约束构造器：它独立重建 Target-522 selection、增量 population、
  sibling graph、exact-B baseline 及完整约束矩阵。若有 witness，它直接从 endpoint IDs 重算 induced edges 和全部固定门；若
  producer 声称 infeasible，则第二套编码必须也返回 infeasible，否则 fail closed。
- formal runner 绑定公开 exact commit 及 protocol/producer/verifier/test/runner SHA，fresh detached worktree 中先跑 focused
  和 full tests，再要求 producer A/B、private witness A/B、verifier A/B 各角色逐字节相同，并用 `strace` 排除 forbidden
  path 与 network access。
- 六小时 monitor 在 start 时要求 `candidate.tsv/READY/COMPLETE` 均不存在；等待阶段只测试 marker existence，不读取候选
  内容。只有 selection `COMPLETE` 后才验证其 SHA256SUMS 并调用唯一 hash-bound runner。

## 3. 结果前结构证据

`2026-08-29T05:17:47Z` 的独立 metadata-only 检查：

- outcome-blind `LATEST=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
- config-v2 sidecar filename count 为 0；
- Target-522 `candidate.tsv/READY/COMPLETE/FAILED_RC/CONTINUITY_GAP/TIMEOUT_RC` 全不存在，monitor PID live；
- intake、TaskBalance v5-r3、continuity supervisor 与 guard v3 均 live；prospective values 未读。

## 4. 测试与失败日志

- 本地无 SciPy 路径：语法、limited-support 双 loader、runner/monitor 静态边界均通过。
- 远端 focused 最终版：`27 passed in 6.16s`。它额外覆盖：
  - producer 与 verifier 两套 exact-B baseline；
  - 两套独立 MILP 编码的 feasible/infeasible status；
  - 261 pairs / 522 endpoints / 261 parents / 87 runs / 36 tasks 的全支持 synthetic graph；
  - private witness mode、公开 identity guard、induced-edge 直接重算；
  - limited-support 在 baseline curve 和 private witness 前停止。
- 最终版 full `phase1/tests`：单线程替代运行 `1624 passed, 47 warnings in 89.91s`，RC=`0`；
  `SHA256SUMS` 文件 SHA-256=`4936e6801eb6810cb3b79de7b3eabb43cdbd894bbb43f734c8035015e41e2d9b`。

失败完整保留：第一次全支持 fixture 把 candidate 累计 task 数写成 36，实际为“36 个新 task + 1 个 baseline task”，因此在
snapshot ledger gate、solver 前失败；只把 fixture 计数改为 37 后原样通过。另一次 SSH 断开后误启两份旧 full suite，发现后
先验证 PID、命令与 cwd，只终止本代理启动的两组进程并保留 overlap receipt；随后又因独立编码已替换旧代码，终止一份 stale
full suite。第一次冻结版 full suite 的开发启动器又遗漏了正式 runner 已有的线程环境限制；核验到该 pytest 只有本次工作目录、
但产生 119 threads、约 30 CPU cores，并停在 13% 超过 9 分钟，因此终止其三个已核验 owned PID，写入
`INTERRUPTED_BY_AGENT_BEFORE_SCIENTIFIC_USE` 回执（SHA-256=`04e90c4186b5b36895a5dd6bc291ea056fe222955a52bf1daaca658d36ae893c`）。
随后才以六项线程上限均为 1 的 exact-source r4 替代；运行时核验为 2 threads，完整通过。上述失败均无科学 readout，不算测试通过。

## 5. Novelty 边界与正方向下一步

防撞结论不变：不能把 constrained graph selection 本身当算法 novelty。最近邻包括：

- ICML 2025/2026 graph label selection：固定预算选 vertices，使其 labels 最适合预测其余 graph labels；
  <https://proceedings.mlr.press/v267/cohen-addad25a.html>，<https://arxiv.org/abs/2605.18623>。
- HodgeRank information maximization：在预算下主动选择 pairwise-comparison edges；
  <https://arxiv.org/abs/1711.05957>。
- NAS predictor system study：同时核算 initialization/query time，并要求 predictor 最终进入 NAS utility 验证；
  <https://arxiv.org/abs/2104.01177>。

本项目可主张的窄差异是 action-observation map：付费动作是执行 tree vertex，观测是 absolute grade；pair supervision 由被选
vertices 诱导出的 sibling clique 自动闭合，而非直接购买一个 edge label。因而 label yield 与 task/run coverage 之间存在
MLE-agent corpus 特有的生产权衡。但只有结构 witness 仍不足以成为方法主线。

下一项最有价值的正面验证应是严格 endpoint-cost-matched 的 downstream label-efficiency：在完全独立的 development folds
上比较 exact-B uniform-edge、balanced greedy 与 yield-guarded selection，由每条 trajectory 诱导训练 pairs，固定 predictor、
初始化、训练步数和 run-disjoint evaluation；报告跨 seed 的 accuracy/calibration/coverage 曲线及每个执行 endpoint 带来的
有效训练 pair。只有该结果在预注册 future cohort 上再确认，才能把结构可行性升级为“更省执行成本地生产有用 critic 数据”。

## 6. 安全与资源

prospective label/outcome/prediction/accuracy/search utility、raw senior archive 与 provider credential 均未读取。聊天中提供的
API key 没有进入命令、日志、文件或 Git。GPU/API/model-fit/base-update=`0/0/0/0`。最终有效测试为单线程；另如上完整披露一份
无效开发 full suite 的短暂多线程失控及主动终止，不能把它写成单 CPU 成功运行。
