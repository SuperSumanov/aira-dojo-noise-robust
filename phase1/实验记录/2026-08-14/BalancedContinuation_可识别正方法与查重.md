# Balanced continuation：可识别的正方法、查重边界与实现路线

日期：2026-08-14。状态：**工程基础设施可做；真实长实验尚未启动**。稳定论文主线仍是 run-clean、
decision-local 的 MLE-agent search-tree dataset/benchmark 与 first-960 前瞻确认。本方向是解决“树节点能否通向
更优解”的 gated 正方法扩展，不恢复旧多保真/HCE/probe，也不微调底座 LLM。

## 1. 要解决的不是普通 pairwise ranking

当前 benchmark 的 pre-execution critic 问：“两个尚未执行的 sibling code，先执行谁？”新扩展问的是另一个
真实搜索决策：“两个已经执行、当前分数已知的节点，在固定 agent、硬件和后续预算下，继续展开谁更可能得到
更优解？”后者允许使用当前 score，因为这个 score 在 expansion decision 时已经存在；它仍有价值，因为一次
critic query 远便宜于再执行一个完整 MLE continuation。

固定 estimand 为：

\[
V_H^{\pi}(c)=\mathbb{E}_{\omega}\left[\max_{1\le h\le H}U(Y_h)\mid
c,\pi_{\mathrm{cont}},\text{contract}\right],
\]

其中 `c` 是已执行节点，`H` 是固定 continuation horizon，`π_cont` 是冻结的局部 operator policy，`U` 是由
pristine evaluator 计算的 task-oriented utility，`ω` 包括 LLM sampling 和训练随机性。每个 sibling 的 `K`
个独立 rollout 只用于估计同一个 `V_H` 及方差；`K` 不是从结果自适应改变的 budget。

主标签同时保留：每个 rollout 的 best-within-H utility、相对 warm start 的 gain，以及超过预注册 practical
threshold 的概率。绝不以历史 subtree max 直接当 ground truth，因为 adaptive selection 决定了每个分支获得
多少 continuation，max 还随样本数机械上升。

## 2. 为什么不能直接改成 FIFO/BFS

1. BFS/FIFO 只平衡树深，不保证 wall/LLM/operator/execution budget 在 sibling 间严格相等；debug path 会额外消耗
   step，run 截断时尾部 sibling 仍少拿预算。
2. 当前 `PythonInterpreter.run(reset_session=True)` 只重启 Python process；working directory 继续存在。
   `MLEBenchTask.step_task` 删除 submission/solution，但不会清除候选创建的任意 cache/model/temp 文件。同一 run
   顺序执行的 siblings 因而可能有 workspace carry-over。它未必每次发生，但足以破坏独立 continuation 的因果解释。
3. 历史 0805 没有可追溯的 committed sequential implementation，且模型、timeout、children、总时限都不同。

因此一个 assignment 必须对应一个独立 Hydra/Slurm output + fresh workspace。先重执行 warm-start code 一次，再执行
恰好 `H` 次冻结 operator transition；valid node 用 improve，buggy node 用 debug，每步最多一个 operator call。
失败/timeout 计入固定最差返回，不额外补跑。不同 siblings 按 replicate block 随机顺序执行，block 内每个 sibling
恰好一次；所有 siblings 都有同一 `K`。

## 3. 与最近工作的边界

严格查重后，以下通用组件都不能声明为新：

- [RTMC (2026)](https://arxiv.org/abs/2604.11037) 已把共享状态的 rollout 聚成树，并用 return statistics 构造
  step-level Q/advantage；“从 sibling rollout 聚合 future return”本身已被覆盖。
- [PaTR (2026)](https://arxiv.org/abs/2607.15610) 已用 process scorer 对 agent trajectory 自适应分支/剪枝，且在
  SWE-Bench 报告正收益；“代码 agent + adaptive tree rollout”不是空白。
- [TRACE (2026)](https://arxiv.org/abs/2606.11119) 已在 prefix 层分配 rollout budget，并训练 conditional-success
  predictor；“学习 rollout allocator”不是空白。
- [Dalal et al., NeurIPS 2021](https://openreview.net/forum?id=VjC4uY3_3I) 已分析 tree-search policy 与 pretrained
  value 的分布失配并做 off-policy correction。
- [OCBA-MCTS](https://arxiv.org/abs/2009.12407) 与
  [fixed-budget BAI](https://proceedings.mlr.press/v216/lalitha23a.html) 已覆盖有限预算下的非均匀采样和 best-arm
  identification；equal allocation 或方差感知 allocation 不能单独当 novelty。

可防守的差异只能是组合证据，而不是新发明 MCTS/Q/BAI：

1. 首个面向真实开放式 MLE program-search 节点的 run-clean、physical-provenance continuation benchmark；
2. 实证分离 historical behavior-policy label 与 matched equal-K interventional label；
3. 在不微调底座 LLM 的条件下，用轻量 critic 预测 `V_H`，并在相同真实 MLE execution budget 下验证 search utility；
4. 每个 rollout fresh workspace、外部 pristine D_search/D_val evaluator、完整成本和 assignment probability；
5. 同时发布 pre-execution candidate ranking 与 post-execution continuation allocation 两种不同 decision regime。

这比“新 tree-search 算法”更适合 D&B/Resources：贡献中心是可识别数据、协议、基准与真实固定预算效用。若没有
equal-K label 的可靠性差异和下游 utility 正收益，本方向只能作为 integrity finding，不能冒充方法突破。

## 4. 冻结比较与正结果门

在同一 anchor/sibling universe 上比较：

- `current_score`：只按当前外部 D_search score；
- `UCT/Q`：冻结 aira-dojo 现有选择统计；
- `random`：同 parent 均匀；
- `static+score`、`char-TFIDF+score`、`frozen-embedding+score`：底座冻结，只训轻量 head；
- `historical_subtree_max` 标签训练的同构 head；
- `balanced_VH` 标签训练的同构 head；
- `balanced oracle`：只作上界，不能部署。

三个 primary gates 全部事前固定：

1. **标签可靠性**：balanced replicate halves 的 sibling ranking agreement 相对 historical matched-budget label
   提升，task-clustered 95% CI 下界大于 0；
2. **预测性**：同构 head 用 balanced `V_H` 训练后，在新 physical runs 的 parent top-1/utility 相对
   historical-label head 提升，run/task-clustered CI 均不支持负效应，且至少 70% 支持任务同向；
3. **真实搜索效用**：在完全相同 candidate pool、continuation executions 与 wall cap 下，balanced critic
   相对 `current_score` 和 UCT 的 D_val best-score/regret 至少一个主指标 task-CI 下界大于 0，并报告所有任务。

任一 gate 失败就不改阈值、不筛任务、不在同一 OOF 上重训新 ensemble。first-960 frozen benchmark 不用于该方法
的调参；方法 discovery 只用其 train/prospective-development 部分，最终确认另收 fresh physical runs。

## 5. 已实现的 outcome-blind 地基

`phase1/balanced_continuation_manifest.py` 只接受 exact-schema anchor identities/code hashes 和无 outcome 的
execution contract，生成 deterministic blocked schedule。每个 `(anchor, replicate)` block 含全部 siblings，
inclusion probability 固定为 1，order probability 为 `1/B`，rollout seed/ID/hash 全冻结。输入若含多余 `grade`
等字段会因 exact schema fail closed；credential-shaped bytes 在 JSON parse 前拒绝。

`phase1/verify_balanced_continuation_manifest.py` 不 import producer，独立重算全部 block/order/seed/rollout ID、
artifact SHA、exact-K 与总 executions。当前只完成 assignment/provenance 层；执行 worker、workspace isolation、
pristine evaluator 和真实 smoke 仍需逐门实现，不能把 manifest 通过写成方法有效。
