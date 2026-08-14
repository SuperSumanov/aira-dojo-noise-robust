# 最新直接竞品与正面突破：防 scoop 审计

日期：2026-08-14。检索使用公开的一手论文页、官方代码仓库与官方数据卡；它不是“无人做过”的证明，
而是截至本日对可见直接竞品的可复核边界。本文晚于仓库中更早的宽泛 novelty 表述。

## 1. 裁决

论文不能再主张“首个 MLE trajectory dataset”“最大 MLE trajectory dataset”“首次分析 agent search
process”“首次 execution-before-prediction”或“首次用 replay intervention 估计 agent step value”。这些宽主张
分别已被 TraceML/MLE-Traj、EvoTrace、FML-bench、FOREAGENT 和 Causal Agent Replay 覆盖。

当前可防守的最小核心应改写为：

> 面向真实 MLE-agent 搜索决策的、physical-run-clean 且 choice-set-faithful 的 benchmark：保留真实
> sibling graph 与 operator/provenance，显式审计 endpoint reuse、gap、label noise、query/init cost，
> 并以机制冻结后的新 physical runs 做 prospective confirmation。

这是数据与评测协议贡献，不是“我们又收集了一批轨迹”。现有弱 critic 结果也不应被写成纯负结论；正面事实是
常用 global/all-pair 评测与 agent 真正面对的局部 choice set 不是同一 estimand，而且会改变 predictor family 的
排序。正在运行的 policy-indexed matched continuation 只能作为 gated 因果扩展，不能冒充新 causal methodology。

## 2. 直接竞品矩阵

| 公开资源 | 已覆盖的范围 | 对我方的直接威胁 | 仍未覆盖的我方窄边界 |
|---|---|---|---|
| [TraceML](https://huggingface.co/datasets/jerryyan/TraceML) / [MLE-Traj v1](https://huggingface.co/datasets/jerryyan/mle-traj-v1) | TraceML 有 134 个 Kaggle competitions、150,997 个 state rows；其中 agent 子集为 1,514 versions，来自 11 个 Codex runs 与 13 个 MLEvolve physical runs，并把后者线性化为 189 branches。数据含 state/action/intent 标签、人类轨迹与图边。 | “首个/最大 MLE 轨迹集”和“轨迹行为 taxonomy”已不可守；把共享 physical run 的 branches 当独立 trajectory 也提醒我们必须直接展示 run-level unit。 | 我方 v11 是 16,012 个 agent cards / 667 physical runs / 25 tasks，目标是实际 sibling decision、run-clean splits、noise/cost/prospective evaluation，不做人类-vs-agent行为 taxonomy。不能据此宣称全球最大，只能逐项报可核数字。 |
| [EvoTrace / EvoReplay](https://arxiv.org/abs/2605.20086) | 四种 evolutionary frameworks、16 tasks、edit taxonomy、盲人工复核，以及 constants/components/model/context 的 replay interventions。 | “代码搜索轨迹诊断”“edit taxonomy”“replay intervention”都不是新点。 | 我方只保留 MLE sibling choice-set、pristine grader、physical provenance、重复 matched continuation 与部署成本的领域组合。 |
| [FML-bench search-dynamics study](https://arxiv.org/abs/2605.17373) | 18 个基础 ML research tasks、10 domains、六个 agents、12 个 process metrics；还给出按 improvement-opportunity density 自适应切换搜索宽度的正方法。 | “比较搜索策略”“稠密/稀疏机会结构”“简单 greedy 可竞争”“按停滞切搜索”均已被明确覆盖。 | 我方不再以 search-policy superiority 为主张；只研究给定已发生 choice set 的评测可识别性、predictor transport 与实际决策 utility。 |
| [FOREAGENT](https://arxiv.org/abs/2601.05930) / [官方仓库](https://github.com/zjunlp/predict-before-execute) | 18,438 个 data-centric solution pairs、verified report、61.5% preference accuracy、predict-then-verify 与端到端 6× convergence claim。 | “执行前比较两个 MLE 解”“implicit execution prior”“用预测减少执行”已被正面覆盖。 | 官方 pair graph 近乎任务内全连接；我方已验证其 `gap<1e-2` share=0.096400，而真实 sibling b0=0.501335，且官方 solution 组合复用 median=49。我们的主张必须是 choice-set fidelity 与 estimand transport，不能只比较 headline accuracy。 |
| [Causal Agent Replay](https://arxiv.org/abs/2606.08275) | 把 agent run 写成 SCM，对步骤施加 do-intervention，在同一 stochastic policy 下向前重跑，并给 contrastive/Shapley effect 与区间。 | “通过向前重跑做 agent causal attribution”已被覆盖。 | balanced continuation 只能说是 MLE 代码节点上的 policy-indexed、fresh-workspace、matched equal-K 数据设计；因果原语不新。 |
| [AIRA_2](https://arxiv.org/abs/2603.26499)、[MLEvolve](https://arxiv.org/abs/2606.06473)、[Gome](https://arxiv.org/abs/2603.01692) | 分别覆盖 hidden consistent evaluation、progressive MCGS/retrospective memory、以及 MLE 的 reasoning-as-gradient 替代树搜。 | 旧 HCE、多保真、MCGS 和“超越树搜索”都不是当前可用 novelty。 | 我方发布的是独立的决策数据/审计协议，并把 operator/evaluator contract 当 label estimand 的组成部分。 |
| [Long-Horizon Agent Trajectory Attribution](https://arxiv.org/abs/2608.06909) | 1,300+ heterogeneous trajectories 的 attribution localization/chain recovery 与 leave-one-out baselines。 | 通用 trajectory attribution benchmark 已继续拥挤。 | 不影响 MLE-specific true sibling choice sets，但要求我们避免“通用 agent attribution”措辞。 |
| [AgentLens](https://arxiv.org/abs/2607.06624) | 对交互式 coding-agent 的完整轨迹做 production-assessed review，把形式验证、LLM 轨迹评语和 side-by-side comparison 合并，并用于 nightly regression evaluation。 | “不只看终局 bit、评估完整 agent trajectory”和“面向生产的轨迹诊断”都不是空白。 | 它评估的是完整 coding-agent run 的可读质量与产品回归，不是 MLE 搜索中同一 parent 下真实候选集的 hidden-score 排序；我方仍应只主张 decision-unit、split/graph/noise/cost audit。 |
| [TML-Bench](https://arxiv.org/abs/2603.05764) | 四个 tabular Kaggle tasks、十个开源 LLM、三个时间预算、每格五次重复；以 agent 不可见标签上的 private-holdout score、成功率与跨 run 变异评估。 | “MLE agent + hidden private evaluator + 时间预算/重复运行”已被明确覆盖，不能把 evaluator isolation 或 time-budget evaluation 单独写成新意。 | 它的单位是完整独立 run，不发布树内 sibling choice set，也不研究 pair-graph estimand 与 physical-run split；这是相邻 benchmark，不是当前核心的直接替代。 |
| [AgentSearchBench](https://arxiv.org/abs/2604.22436) | 对近一万个公开 agents 做 retrieval/reranking，并用 execution-grounded relevance 与轻量 probing 改善 agent 发现。 | “文本相似度不能替代执行表现”“execution-aware probe 改善 reranking”属于已有一般结论。 | 它选择的是给定任务应调用哪个 agent，而非一个 MLE agent 在同一搜索 parent 下生成的代码候选；因此只封闭宽泛的 execution-grounded ranking 措辞。 |

## 3. 当前最强的正面论文结构

### A. Choice-set fidelity，而不是泛化的 pair accuracy

现有 evidence 已形成可写的正面链：

1. 旧 fragment split 使 99.7% in-task test pairs 与训练共享 physical run；run-clean 后 L1 从 0.776 降到
   0.6493，证明物理采样单元不是实现细节；
2. FOREAGENT 官方 pair graph 只有 15.8651% pairs 来自同 trajectory，`gap<1e-2` 比例为 9.6400%；我方
   真实 sibling 分别是同一搜索选择点与 50.1335%；
3. 固定同一 OOF endpoint scores 后，char-TFIDF 在 sibling 与 uniform cross-run 的 task-macro 是
   0.5284907717433142 vs 0.5814158858170438，而 static LR 是 0.5389068809808808 vs
   0.49652226450484627：pair graph 不只平移难度，还会反转 predictor family 排序；
4. 代码重复不是解释：12,383-card 旧截面 raw/AST-skeleton unique 为 99.47%/98.96%，78 个 duplicate
   groups 全在单 run 内，跨 run 为 0；
5. 标签噪声也不是主要解释：独立重评 transported ceiling 在 value/decision distributions 上分别为
   0.9923/0.9578，远高于 run-clean predictor。

因此主表必须以 parent-level choice set 为统计单元，pair 指标只是 secondary；同时报告 physical-run/task
clustered inference、endpoint reuse、gap transport、top-1 与 utility。这个协议本身是正贡献。

### B. Prospective evaluation-channel confirmation

发现集上，同 parent/候选/120 秒共同覆盖比较的 pristine external submission score 相对 stdout top-1 为
`0.9167 vs 0.7083`，paired difference `+0.2083`，run/task CI 均在 0 以上；但 sign test 只有五个 informative
runs、`p=0.0625`。所以它是强正线索而非确认。

当前唯一主确认仍是 mechanism-freeze 后 first-960 physical runs：固定 scorer、denylist、每 run 最多两个 parent、
不按 outcome 停止。若支持门与 task dominance 门通过且效应复现，它会给数据论文一个明确正结果；若失败，仍按
预注册报告，不能改 cohort 或阈值。

### C. Policy-indexed matched continuation

`V_H` 必须写为 `V_H^{pi,kappa}`。当前 E1-Q 的价值是验证真实 MLE 节点能否产生完整 matched repeated
continuation labels；只有完整 E1 后才可按观察方差设计 E2。即使 E1 正，也只能先主张 feasibility 与 label
design；hurdle critic、search utility 和 E2/E3 均不得自动解锁。

## 4. 下一项低风险高价值资产：Decision-Corpus Audit Protocol

不新增 GPU/API 的优先工作是把现有零散审计统一成可复用的 release validator，而不是再挖一个同数据阈值：

1. **physical unit**：source journal/run reconstruction、fragment/orphan、split overlap；
2. **choice-set fidelity**：真实 sibling coverage、全局 pair coverage、pair-graph transport；
3. **effective support**：unique endpoints、endpoint degree/复用、deduplicated pairs、run/task counts；
4. **label quality**：regrade agreement、gap-bucket ceiling、ties/nonfinite quarantine；
5. **deployment contract**：pre/post-execution feature time、query/init cost、operator/evaluator hash；
6. **prospective boundary**：activation time、denylist、append-only intake、optional-stopping prohibition。

输出应是 machine-readable audit card + 独立 verifier + 人类 datasheet。它不声称这些统计思想本身新，但能把
“为什么 18k global pairs 不能替代 1.5k true decisions”变成第三方可运行的 benchmark standard，是当前最稳的
D&B 资产化方向。

## 5. 立即关闭与保持开放

- 关闭：再次训练低容量 sparse/global/task-conditioned/ensemble critic；同一 OOF 上继续调阈值；恢复旧
  HCE/multifidelity/TD；把 E1 工程可行性写成方法收益。
- 保持开放：first-960 正式确认；E1-Q 完整性与 paired label feasibility；Decision-Corpus Audit Protocol；
  学长修正 checkpoint direction 后在冻结 b0/b1/b2 上做一次容量防守性复核。
- 新的付费方法实验：E1-Q 完成前不提出；E2 只能由 E1 的有效率、方差、task support 和成本重新做 power
  calculation，不能沿用旧 43.76 GPU·h 机械启动。

## 6. 2026-08-14 晚间增补：相邻领域边界与新证据

进一步查重确认，candidate-set sampling 改变 metric 与模型相对排序在推荐系统中已有直接理论/实证先例：
[Rendle 2019](https://arxiv.org/abs/1912.02263) 证明 sampled metrics 不保留完整指标的模型排序，甚至期望上也
不保留；[Ihemelandu & Ekstrand 2023](https://arxiv.org/abs/2309.11723) 研究 candidate strategy/size 与
popularity bias；[Dallmann et al. 2021](https://arxiv.org/abs/2107.13045) 比较 uniform/popularity sampling 的
模型排名不一致。NAS 的 [White et al. 2021](https://openreview.net/forum?id=6RB77-6-_oI) 也已系统比较 predictor
rank、search utility、init/query cost。因此 choice-set bias 或 ranking reversal 的统计原理本身不新，我方只能申
真实 MLE-agent physical-run/parent-choice-set 的数据契约、实证与 prospective confirmation。

label-quality 证据也已纠偏：旧 `noise_ceiling.py` 的 bootstrap 无效，single-vs-repeat-mean 反演不可交换。
预注册 v2 改为 original-vs-first-regrade 两个单次测量，3,017 pairs raw agreement=
`0.9658601259529334`，task CI=`[0.9438143714671886,0.9913402891372938]`。frozen b0 的 transported
repeat agreement=`0.9134305309964227`；模型反演量=`0.9488254145489123`，但 measured-task pair share
只有 `0.732977303070761`，必须显式标注任务外推。

E1-Q 随后完整通过：两任务 replicate winner agreement=2/2，故 matched label feasibility 为正；但 2/8
positive gain、0/8 practical gain，warm/continuation 均只有 6/8 scored artifacts。它只让 policy-indexed
continuation label 与 hurdle data design 保持开放，`primary_gate_claim_allowed=false`、`e2_e3_unlocked=false`。
