# Balanced Continuation：E1 后正面突破路线与 scoop 复核

日期：2026-08-14。检索边界：截至当日公开论文与本仓库最近两周记录。结论不是“无人做过”的证明；
它只记录本次可复核检索中找到的最邻近工作和因此仍可防守的最小主张。

## 1. 先给结论

“训练一个 value critic，再用它给 MCTS/rollout 分预算”已经高度拥挤，不能作为本项目的独立 novelty。
最值得继续的正面组合是：

1. **policy-indexed、matched equal-K 的 MLE continuation 干预数据/benchmark**；
2. 把 continuation 结果分解为“能否产生有效下一解”与“有效时能提高多少”的
   **hurdle/distributional option-value critic**；
3. 不微调底座 LLM，只训轻量 head，并在完全相同真实执行预算下验证 downstream utility；
4. 与 historical behavior-policy subtree label 做同端点、同任务的可靠性和 transport 对照。

其中第 1 项是最稳的 D&B/Resources 贡献，第 2 项只有在 fresh interventional labels 上过门后才升级为方法贡献。
公式或 hurdle model 本身都不是新发明；可防守性来自真实 MLE program-search、干预标签、physical provenance、
完整成本与 fixed-budget utility 的组合。

## 2. 最邻近论文与已被覆盖的主张

- [CodeTree](https://arxiv.org/abs/2411.04329) 已在代码生成树中用 execution feedback 与 LLM feedback 指导
  ranking、termination 和 expansion；“代码树 + feedback critic”不新。
- [AgentSwift](https://arxiv.org/abs/2506.06017) 已训练 agent-performance value model，并用 uncertainty-guided
  hierarchical MCTS 加速搜索；“预测值 + 不确定性 MCTS”不新。
- [RTMC](https://arxiv.org/abs/2604.11037)、[PaTR](https://arxiv.org/abs/2607.15610) 与
  [TRACE](https://arxiv.org/abs/2606.11119) 已分别覆盖 rollout-tree return/Q 聚合、agent trajectory 自适应分支、
  prefix conditional-success 与预算分配。
- [IGRPO](https://arxiv.org/abs/2607.06223) 进一步按 node-level information gain 分配 tree rollout，并与
  policy optimization 结合。它与我们不微调底座的约束不同，但使“自适应 rollout allocation”更不能单独申新。
- [General AgentBench](https://arxiv.org/abs/2602.18998) 已系统比较 sequential/parallel test-time scaling，并把
  verification gap 识别为并行扩展失效原因；“更多 rollout 未必更好”也已有公开 benchmark 证据。
- 既有 OCBA-MCTS、fixed-budget BAI、EET、Semantic Early-Stopping 与 KompeteAI 继续覆盖方差感知分配、
  固定预算 best-arm、agent early termination、迭代停止和 MLE early-metric 预测。

本轮没有找到同时满足以下全部条件的公开资源：真实开放式 MLE 代码节点、physical-run-clean provenance、
对同一 sibling 做 fresh-workspace matched equal-K continuation、外部 pristine evaluator、重复估计方差、
并发布 historical-vs-interventional label transport 与 fixed-budget search utility。这个“组合缺口”可写，
但在投稿前必须持续更新检索，不能写成绝对的“first ever”。

## 3. E1 暴露出的新设计事实：value 必须带 operator policy 下标

Qwen strict-script probe 为 2/2 合规；production-matched DeepSeek 只有 1/2，tabular 再次在 8192 tokens
截断。两者没有执行代码，不能比较 solution quality，却足以说明生成一个可执行 continuation 的概率依赖
operator/model/config。于是 `V_H` 不能被当成节点的固有属性，必须写成：

\[
V_H^{\pi,\kappa}(c)=\mathbb{E}\left[\max_{1\le h\le H}U(Y_h)
\mid c,\pi_{\mathrm{op}},\kappa_{\mathrm{exec}}\right],
\]

其中 `π_op` 包含 model、prompt、temperature、top-p、token cap、action rule；`κ_exec` 包含硬件、timeout、
workspace 与 evaluator contract。数据发布必须绑定这两个 hash。换 DeepSeek→Qwen 不是“修 parser”，而是换了
estimand；旧 labels 不能无条件混训或比较。

## 4. 首选轻量方法：Hurdle Continuation Critic

对已执行节点 `c`，先预测下一固定 continuation 是否产生可评分有效解 `Z`，再预测有效条件下的正增益：

\[
\mathrm{VOI}(c)=
\frac{P(Z=1\mid x_c,\pi)\;\mathbb{E}[(U(Y)-U(c))_+\mid Z=1,x_c,\pi]}
{\mathbb{E}[\mathrm{cost}\mid x_c,\pi]}.
\]

输入只用 decision 时已知状态：task description、当前完整 code、当前 D_search score、execution status、
terminal/error、runtime、operator action 与剩余预算。这里 runtime/stdout 是**合法 post-execution state**；它们曾从
pre-execution predictor suite 移除，不能把两个 decision regime 混为一谈。模型固定为 frozen embedding/char-TFIDF
+ 低容量 logistic/quantile heads，不微调底座 LLM。

必须比较：task/action-only hurdle、current score、monolithic expected-value head、historical-subtree head、
balanced-label hurdle head 与不可部署 oracle。primary 指标是 fresh parent top-1、parent-equal utility、Brier/
calibration 和相同真实执行预算下 best-score/regret；run/task 双聚类与逐任务方向均必报。

这个分解有获得正结果的合理机制：普通 RM 把 invalid/timeout、无提升和大幅提升揉成一个高度零膨胀目标；
validity 往往由错误类型和执行状态决定，而 conditional gain 更依赖代码与 task。若两头确实学到不同信号，
组合可能比 monolithic head 稳；若 validity 只等于 task prior 或 conditional gain 仍接近随机，则立即关闭。

## 5. 不允许从旧 E1 直接做的事

- 旧 8 个 continuation 全被 adapter 失败污染，不能用作 hurdle 训练样本或方法负例；
- Qwen/DeepSeek 的 2×2 conformance 只测格式，不测 code quality，不能报模型胜率；
- 旧 anchors 的 D_val 已在 post-hoc 诊断中打开，只能用于工程回归，不能再作 fresh scientific effect；
- 不对 DeepSeek 继续关 thinking、加 token、改温度或重试来追一个 PASS；
- 不在 historical subtree OOF 上继续搜索新阈值/ensemble，把 behavior-policy allocation 当因果标签。

## 6. 下一道可执行门

若要继续支线，正确顺序是：

1. 冻结一个**新的 Qwen operator contract**，明确它改变了 `π_op`；
2. 先在本轮两个**旧 warm states** 上执行已 hash-bound 的 Qwen responses：2 candidate executions、
   0 new generation calls，600 秒硬 cap 下最多 `0.333333333333333` GPU·时；由于旧 D_val 已揭开，
   它只验证脚本真的运行并产合法 submission，绝不报告 gain；
3. smoke 通过后，再提出 fresh-anchor E1-Q 的 8 jobs/16 candidate executions/8 API calls；600 秒硬 cap 对应
   candidate 部分最多 `2.66666666666667` GPU·时，实际还需另列 evaluator/API/调度开销；
4. 只有 E1-Q 产生完整 paired outcomes，才据有效率与方差重新设计 E2 power，不机械沿用旧 43.76 GPU·时表；
5. E2 同时采 monolithic 与 hurdle 所需字段，但模型开发仍在 physical-run outer folds 内，最终用全新 runs 确认。

第 2、3 步都是新 GPU 实验，当前文档只给矩阵，不构成自动授权。主线的 first-960 metadata monitor 与固定
scorer 继续独立运行；不能为支线改 prospective cohort 的冻结规则。
