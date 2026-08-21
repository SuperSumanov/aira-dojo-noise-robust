# SourceChoice max-step：时序语义与 memory 防 scoop 审计

日期：2026-08-22。状态：`POST_RESULT_EXPLORATORY_MECHANISM_AUDIT`。触发原因是固定 TF-IDF OOF 中
预注册的 `max_step_then_min_sha` control 呈现跨任务正关联；本文只解释这个已见现象的可用性与文献边界，
不把它升级为新的 confirmatory result 或 model rescue。

## 1. 标签未用于统计的结构复核

新增 `phase1/audit_source_choice_step_structure.py`，脚本 SHA-256=
`169615686dc23a3c4d24680e5720bc8bb059ce783b5dd89a72ca3daef42c4eea`。它只对已用于 OOF 的 S2 v2 train
输入做 schema、SHA、step/depth/operator 结构统计；JSON 解析不可避免地读入整行 bytes，但代码从不索引、验证、
复制、比较或统计 `winner_candidate_sha256`。因此它是 **post-result、label-unused**，不能称 outcome-blind。

输入 SHA-256=`e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1`，固定 census=
2,109 groups / 5,739 candidates。完整结果：

- 2,109/2,109 groups 内所有 candidate step 均唯一；
- 2,109/2,109 groups 内 candidate depth 全相同，operator 也全相同；
- 1,662 groups 的 candidate steps 连续，447 groups 不连续；
- group operator 为 38 个 `Draft`、2,071 个 `Improve`；
- source-size 2/3/4/5/7/8/11 的 counts 与正式 OOF 完全一致：
  1,014/884/7/201/1/1/1。

聚焦测试为 `2 passed in 0.13s`，包括改变 winner 后结构统计逐项不变和 SHA/schema fail-closed。Linux 对正式只读
输入连续运行两次，输出逐字节一致，两个 SHA-256 均为
`74df0fe8bf3fbeeb38f0fda3d3a406c46c1df0fea9fd8c9826bf888d263e2b17`。第一次 Linux 调用误把正式目录根当成
数据文件所在目录，因 `FileNotFoundError` 在读取输入前失败；唯一修正是路径加 `view_a/`，脚本和统计未改。

## 2. AIRA 执行顺序意味着 step 不是免费的 pre-execution selector

仓库 initial commit `7747999` 与当前实现的关键顺序一致：`_expand_leaf_and_backprop` 在一个 leaf 上循环创建
children，但每一轮都是：生成一个 child → `task.step_task` 执行 → parse outcome → append journal → step 加一，
之后才生成下一个 child。默认 MLEBench MCTS 配置为 `num_children: 5` 与 `simple_memory`；后者从
`journal.good_nodes` 形成 memory，并包含已有 node 的 analysis 与 validation metric，再传给后续 draft/improve。

因此已观察到的 max-step 关联与“同一 expansion 内较晚生成的 candidate 已处在更丰富的执行反馈上下文”一致；447
个非连续组还表明部分同 parent candidates 之间夹有其他 execution steps。但当前 materialized view 没有给每个 run
绑定 exact collector commit/config，也没有随机化 memory 或位置，所以这只是机制一致性证据，不是 memory 的因果
效应。更重要的是，它不能直接证明 critic 能在执行前从一批同时存在的 unexecuted candidates 中做选择：当前 harness
生成较晚 candidate 之前已经执行并写入了较早 candidate。

## 3. 直接文献已覆盖该机制

2026-05-27 的 [When Does Memory Help Multi-Trajectory Inference for Tool-Use LLM Agents?](https://arxiv.org/abs/2605.28224)
已经把“同一 expansion 中，第 i 个 candidate 条件于更早 siblings 的 action/outcome”形式化为 cross-sibling
within-expansion memory，并称其 interleaved expansion / Raw Sibling；它在 best-of-N、beam、MCTS 和四类 tool-use
benchmark 上做了控制矩阵。其结果不是普遍正向：Raw Sibling 在 KGQA beam 上最强，但 WikiSQL/WikiTQ MCTS 分别
为 `-1.9pp/-2.0pp` 且不显著，KGQA MCTS 则为正。论文据此强调效果依赖 inference method 与任务多样性瓶颈。

所以以下 novelty 关闭：首次提出跨 sibling execution feedback、首次把它接入 MCTS、或首次用 sibling memory 让后续
candidate 改进。VirtualMLE 等 2026 工作也已在具体 MLE 子领域使用 execution → reflection → memory update 闭环。

## 4. 可以保留的正面价值与停止边界

可以保留的结果是：在 23-task 的真实 MLE-agent source groups 中，预注册的 late-step control 呈现跨任务正关联，
而代码结构和 label-unused census 都支持把 step 解释为 homogeneous sibling generation/exposure order。这是
benchmark 必须报告并控制的 **sequential-feedback confound**，也是把数据资源与独立批量 candidate-preference
corpus 区分开的一个正面 D&B 发现。

不能写：memory 因果提升最终分数、自然发展出新能力、可免费替代 critic、search speedup，或新方法。若未来做随机
确认，只能另立固定 task×agent×budget 的 `simple_memory` vs `no_memory` 单旋钮实验，逐 run 绑定 collector commit、
prompt/context bytes、候选执行顺序和外部分；并以 task/run 聚类推断。该实验在已有论文后只能是 MLE-domain
replication/benchmark mechanism，不自动成为论文主线，也未在本轮提交 GPU/API。
