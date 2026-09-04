# TOFFEE-30K 直接邻居与 Decision Corpus 边界

日期：2026-09-05。性质：最新防 scoop 核验与论文定位收紧，不是模型效果实验。

## 原始来源确认了什么

[TOFFEE](https://arxiv.org/abs/2607.06233) 于 2026-07-07 首次提交、2026-08-10 更新 v3，已作为
VLDB 2026 demo 发表。论文与[官方仓库](https://github.com/wang0702/toffee)明确包含：

- 在真实异构数据环境中执行每个候选步骤的 MCTS trajectory explorer；
- 跨任务 prefix DAG 复用；
- 按工具、模型档位、历史长度、reasoning effort 和剩余预算选择配置的 learned cost model；
- 根据置信区间调 branching width、从执行反馈在线更新的 contextual bandit；
- 30K 条公开多轮轨迹，供 SFT 或 ICL 使用；论文报告初步下游增益。

[DataPRM](https://arxiv.org/abs/2604.24198) 已在 agentic data analysis 上做环境交互式 process reward model，
构造 8K 以上训练实例并报告 Best-of-N 与 RL 收益。[KompeteAI](https://arxiv.org/abs/2508.10177) 已在 MLE
pipeline generation 中用 early-stage metrics 做 predictive scoring/accelerated debugging，并报告 6.9 倍加速。

另有 2026-09-02 刚提交的
[Discriminative World Models for Web Agents](https://arxiv.org/abs/2609.02885)。其公开摘要明确写明 branching
WebArena Go-Browse 数据的每个决策点都有多个 alternative actions 及 resulting states，并报告 held-out state matching、
PRM-style action ranking 与 WebArena-Lite 端到端选择收益。这关闭了通用“首次 alternative-bearing agent decision
dataset/首次利用分支结果训练动作选择”的宽主张。

因此以下说法关闭：首次 data-agent MCTS 轨迹生产、首次公开大规模 data-agent trajectory corpus、首次跨任务
prefix reuse、首次 learned budget/model router、首次 data-analysis PRM、首次 MLE predictive scoring 或执行加速，
以及首次通用 agent 多备选分支数据/分支结果选择器。

## 仍然可守的差异

TOFFEE 官方 release 说明每个 sample 保留一条完整 multi-turn trajectory，包括 reasoning、tool calls、outputs 和
tool metadata。该公开说明没有声称 release 包含搜索期间未进入最终轨迹的 sibling alternatives、rejected branches 或
可重建的 choice sets。这只能支持“公开 artifact 未展示”的判断，不能推断作者内部从未记录这些数据。

Decision Corpus 的目标不是 SFT 轨迹库，也不再以“有多个分支”本身申新，而是对 MLE 程序搜索决策进行离线、
可审计复现：

1. 保存 parent/child/sibling 关系和候选代码，使同一决策点的 alternatives 能形成 canonical pair/choice set；
2. 绑定 physical run、task、generator/operator、执行配置和外部 evaluator；
3. 按 physical run 隔离，并使用结果盲的时间外 prediction escrow/frozen cohort；
4. 联合报告连续执行分数、gap/regrade noise ceiling、failure/missingness、endpoint reuse/pair dependence；
5. 分开核算 predictor initialization、query 与真实 execution cost；
6. 用同一 corpus 比较静态、文本、embedding、RM 和 LLM judge，而不是只提供 SFT 示例。

现有数据不能称“完整搜索树”：已知 parent pruning/orphan cards 必须作为 missingness 审计发布。可守措辞是
**alternative-bearing multi-branch decision records**，并逐 snapshot 报告 choice-set completeness，而不是把 fragment
或 path 补写成完整树。

## 对正方向实验的影响

TOFFEE 的存在提高了“轨迹数据有用”的外部可信度，但也意味着单纯规模和 MCTS 来源不够。最近的实证必须回答它没有
回答的 benchmark 问题：在固定 generator 和昂贵 execution-label 账下，critic 能否在未见 physical runs 的真实 sibling
决策上泛化，以及监督关系复用能否提高这种局部决策能力。

因此实验顺序保持：

1. 新归档按 credential-first、稳定期、独立 verifier 正式摄取，更新 outcome-blind 结构支持；
2. G0 只测真实训练成本，不用其开发结果选模型；
3. 同版本来源和 experiment-closed 门通过后，做 G-reuse-to-L 对 Lbudget 的跨 seed、同 valid-token 主比较；
4. P-to-L 只能作为同预算挑战臂，不能包装成 pointwise/pairwise 首创；
5. 最终 untouched cohort 同时报 local decision、calibration、cost 与 task/run-clustered inference。

论文 related-work 表应新增 TOFFEE 一行，并机器核验以下列是否公开：alternative candidates、choice-set identity、
physical run、external continuous score、regrade、cost split、prediction escrow。未知写 unknown，不把未看到写成 absent。
