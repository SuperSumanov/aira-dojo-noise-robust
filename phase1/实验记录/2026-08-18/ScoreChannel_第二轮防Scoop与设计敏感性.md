# Score-channel 第二轮防 scoop 与设计敏感性（2026-08-18）

状态：`NOVELTY_NARROWED_DESIGN_GATE_REACHABLE_NOT_POWER_GUARANTEED`。本轮只读取公开一手论文页、冻结
selection 的结构收据和已冻结 analyzer 代码；没有读取 prospective label/outcome、candidate code 或 replay
manifest，GPU/API=0。

## 1. 新发现的最强邻近工作

### 1.1 已覆盖宽泛 self-evaluation bias 主张

*When Do Agent Loops Mistake Stagnation for Progress?*（2026-07，arXiv:2607.25152）固定 agent 与 tool
surface，只改变 gating evaluator 的信息通道，在 54 个 long-running cycles 上比较 self-verdict、in-band judge
和隔离的 world-state oracle。论文报告 self-report 退化为 accept-all，并明确把差异归因于 evaluator grounding。

一手来源：https://arxiv.org/abs/2607.25152

裁决：以下表述已被 scoop，禁止使用：

- “我们首次发现 agent 自报分不可靠”；
- “我们首次证明外部 grounded evaluator 优于 self-evaluation”；
- “我们首次证明更大 in-band judge 不能替代外部评估”。

它没有 MLE competition、真实 search-tree siblings、同一 capped execution 的 `stdout`/`submission.csv` 双通道、
候选 top-1 决策或 temporal cohort，因此没有直接覆盖本文的窄 estimand。

### 1.2 外部 evaluator 驱动自动研究闭环已是正向先例

*Auto Research with Specialist Agents Develops Effective and Non-Trivial Training Recipes*（2026-05，
arXiv:2605.05724）以 evaluator-owned outcomes 驱动 proposal–measure–revise，包含 1,197 个 headline trials 和
600 个 control trials，并报告三个任务上的正向改进。

一手来源：https://arxiv.org/abs/2605.05724

裁决：不能声称“首次让外部 evaluator 参与 auto-research”。它默认外部测量可用，不比较同一执行的 in-band
self-report 与 out-of-band artifact score，也不分析选择性缺失/通道价值；它反而支持本文为何要把 evaluator
channel 当作系统设计变量。

### 1.3 parent-selection 正方法已有强邻居

*Contrastive Concept-Tree Search for LLM-Assisted Algorithm Discovery*（2026-02，arXiv:2602.03132）使用
external objective，学习 high/low-performing programs 的 concept likelihood ratio 来重加权 parent selection，
并报告相对 Greedy、k-elites、Uniform 的搜索效率提升。

一手来源：https://arxiv.org/abs/2602.03132

裁决：不能把“external fitness 引导 parent selection”写成 novelty；若未来做控制器，CCTS 必须列为强基线/相关
方法。当前主线并不是发明新 parent selector，而是测量在 MLE execution cliff 下哪一种实际可见评分通道能支持
可信选择。

### 1.4 两个边界工作

- RankEF（arXiv:2408.13976）用执行反馈训练 APPS code ranker，在 inference 时不执行候选；它会微调模型，任务、
  estimand 和成本边界都不同，但必须放入 execution-feedback ranking related work。
- AuditRepairBench（arXiv:2605.04624）曾提出 paired-execution trace corpus 和 evaluator-channel ranking
  instability；当前 arXiv 页面明确说明作者因影响主要结论有效性的重大实验设计/评估问题撤稿。它只能作为近似
  术语与审计设计的警示，不能当作可靠实证证据，也不能据此夸大我们的领先。

一手来源：https://arxiv.org/abs/2408.13976 ，https://arxiv.org/abs/2605.04624

## 2. 当前可守的精确 novelty

论文主张应收窄成：

> 在真实 MLE-agent 搜索树中，对同一 parent 的真实 siblings 做同一 120 秒 capped execution；仅在两个通道
> 同时有限时，比较 in-band keyed stdout self-report 与 out-of-band pristine `submission.csv` evaluator score
> 对 frozen true quality 的 tie-aware top-1 决策价值，并量化 execution cliff 导致的选择性通道覆盖。该比较
> 使用 run-clean 时间前瞻 cohort、physical-run 聚类推断、task stress、query/init 成本和完整泄漏/噪声审计。

这一表述的贡献不是一般性的“外部评估更好”，而是：

1. **决策单位**：真实 sibling parent，而非独立生成答案或完整 agent cycle；
2. **公平反事实**：同一候选、同一 cap、同一 execution，只改变用于选择的评分通道；
3. **选择性可观测性**：artifact 可能不存在，stdout 也可能不 keyed，明确报告共同覆盖而非把缺失当失败；
4. **数据基础设施**：run-clean tree corpus、冻结 temporal cohort、双 verifier、成本/噪声/覆盖/撤回链；
5. **可操作结果**：若前瞻 GO，直接支持可插拔 pristine evaluator contract；若未 GO，则保留 D&B benchmark
   与边界结论，不回头调 cap/任务/selector 追正数。

## 3. outcome-blind 设计敏感性

冻结 analyzer 的 sign 门是：每个 physical run 先平均 parent delta，去除绝对值不超过 `1e-12` 的 ties，再对
positive/negative 做双侧 exact binomial test。对 informative run 数 `n`，正向拒绝所需最小 positive 数为：

| informative runs | 最小 positive runs | 比例 | exact two-sided p |
|---:|---:|---:|---:|
| 5 | 不可达 | — | 全正仍为 0.0625 |
| 6 | 6 | 1.0 | 0.03125 |
| 15 | 12 | 0.8 | 0.03515625 |
| 31 | 22 | 0.7096774193548387 | 0.029449373483657837 |
| 47 | 31 | 0.6595744680851063 | 0.03998605682605216 |
| 63 | 40 | 0.6349206349206349 | 0.04295654552438921 |
| 94 | 57 | 0.6063829787234043 | 0.04945006525317994 |

精确计算与冻结 analyzer 相同：`2 * BinomCDF(min(positive,negative); n, 0.5)`，再截到 1。发现集 sign
`p=0.0625` 正是 5/5 informative runs 全正；这解释了为什么 discovery 的两个 cluster CI 均正而 sign 仍未过。

裁决边界：94 个结构 run 让 sign 门**可达**，但这不是 power 保证。正式 replay 后的 common-channel runs、tie
率、每 run parent 数和 delta 分布尚未知；GO 还要求 run-cluster bootstrap lower>0 和所有 task LOTO>-0.10。
因此不得根据本表提前声称 80% power，也不得因将来 common coverage 低而修改 sign 门。

## 4. 下一步不变

1. 先由账号所有者解锁 9 个 Kaggle 规则，或取得同版本完整 prepared 数据；
2. 完整数据门双验证后签发新 approval receipt，恢复冻结 320-candidate replay；
3. 只运行一次预注册 analyzer；
4. 若 GO，再把可插拔 pristine evaluator contract 作为正向 harness 扩展；若 BORDERLINE/KILL，如实裁决，
   不把已看到 outcome 的 cohort 用于发明新 selector。
