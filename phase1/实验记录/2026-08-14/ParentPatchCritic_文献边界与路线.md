# Parent-Conditioned Patch / Action Critic：文献边界与正面路线

日期：2026-08-14。本文只使用论文/官方页面的一手来源。结论是：**方向没有被一篇论文完整覆盖，
但泛化的 action-value、relative progress 和 budget conditioning 都已有强先例，不能把这些词本身写成创新。**

## 1. 我们究竟要解决什么

现有 RM 把每个完整 child program 当作独立对象，学习绝对质量；真实搜索决策却是在同一 parent、
同一任务和同一剩余预算下，在若干候选编辑之间选择。拟议模型改为：

\[
Q(p, a, K)=P(\text{在剩余预算 }K\text{ 内获得有意义改进}\mid \text{parent }p,
\text{ patch/action }a).
\]

即时版先学 b0 的 `child - parent` 编辑价值；前瞻版不再用历史 MCTS 下“观察到的子树最大值”，
而要求相同 continuation policy，或把未获得足够 continuation 的样本当 right-censored。

## 2. 强近邻与 scoop 风险

| 工作 | 已经覆盖 | 没有覆盖/与我们不同 | 风险 |
|---|---|---|---|
| [Guided Search Strategies in Non-Serializable Environments](https://arxiv.org/abs/2505.13652) | SWE-bench 上 learned action-value、1-step lookahead、trajectory selection；用 TD(λ) 目标并做端到端搜索 | 非 MLE/Kaggle 候选程序；无我们的 run-clean sibling 数据、pairing/noise 审计；允许大模型策略/critic 训练 | **最高**：禁止声称首个 action-value 或 one-step lookahead |
| [Budget-Aware Value Tree](https://arxiv.org/abs/2603.12634) | training-free residual relative progress；remaining-budget conditioned node selection | 多跳 QA；不是执行昂贵的 MLE code patch；没有真实外部 grader/censoring | 高：禁止声称首个 relative/budget-conditioned value |
| [SWE-Search](https://arxiv.org/abs/2410.20285) | SWE patch tree、LLM Value Agent、MCTS 与迭代 refinement | LLM 自评/hybrid value，不是 run-clean 学习式 MLE patch critic | 中高 |
| [RLTS / Learning to Plan with Tree Search via Deep RL](https://openreview.net/forum?id=IP5kPfDu3w) | 学习 expansion 的 value of computation | 通用规划环境，不是 MLE patch 数据与成本结构 | 中 |
| [FOREAGENT / Predict Before Execute](https://arxiv.org/abs/2601.05930) | MLE 解的执行前成对预测与 Predict-then-Verify | 18,438 个全局扁平对；没有真实 sibling/run/noise/lineage；我方复现已在真实决策点塌缩 | **直接 benchmark 竞品** |
| [MLE-STAR](https://arxiv.org/abs/2506.15692) | 组件级 targeted refinement 与 ablation-guided search | 不学习 parent-patch value，不发布大规模搜索树决策基准 | 中 |
| [ArchPilot](https://openreview.net/forum?id=6rEuy1CXQ1) | MLE proxy evaluation、fidelity-aware search | 重点是低保真执行，不是静态相对 patch critic | 中；也是 Artifact 支线强近邻 |
| [Reasoning as Gradient / Gome](https://openreview.net/forum?id=DSVg7gjyqi) | 结构化诊断→定向更新，挑战树搜索 | 不做候选动作价值预测；但会挑战“为何仍需树/候选排序” | 中 |
| [RETRACE](https://arxiv.org/abs/2608.08950) | SWE patch 的独立 reconstruct-and-verify，报告 Pass@1 提升 | 训练自由的语义验证；不是 MLE 分数/搜索树 action value | 新近邻，需在写作中区分 |
| [Run2Survive](https://arxiv.org/abs/2007.02816) | 用 survival analysis 处理算法运行时删失并做风险感知选择 | 固定算法选择，不是生成式 MLE tree/action | 说明 censoring 本身不是 novelty |

## 3. 可守住的贡献边界

方法不能单独写成“我们提出 action-value critic”。更可信的顶会/D&B 组合是：

1. **数据贡献**：16k+ richly labeled MLE search nodes，物理 run、lineage、operator、外部分数、
   噪声复测和冻结 sibling decision；展示全局 pairing 会把执行前预测夸大到何种程度。
2. **问题修正**：把完整程序 absolute quality 改写为 parent-conditioned patch/action value；
   train/eval 按 parent 和 physical run 计权，避免 pair 数与 tree allocation 伪重复。
3. **标签修正**：即时改进与受控 K-step improvement hazard；历史不足 continuation 为删失，
   不把 “没观察到后代”当负例，不把极值抽样当真值。
4. **方法约束**：底座 LLM 冻结，只训轻量 head；与 absolute RM、FOREAGENT、静态 sparse、
   random、post-execution self-report 在同一 frozen pair pool 比较。
5. **最终证据**：fresh post-freeze physical runs 上的 fixed-budget best-final/regret，而不止离线 accuracy。

如果只能得到离线 pair accuracy 小幅提升、没有 prospective search utility，这仍是数据基准中的新 baseline，
不是足够强的独立方法论文。若 sparse patch gate 为正，再升级 frozen 0.5B/4B/8B 表征；若 sparse gate
为负，只关闭该低容量表示，不能推断非线性 parent×patch 模型必然失败。

## 4. 分阶段执行

1. b0 train-run OOF：hash-TFIDF + 同一线性分类器，对比 whole-code 与 line-diff patch；parent 等权。
2. 只有预注册 discovery 全过才读取 b0 frozen；这一步检验“旧全代码信号失败、局部编辑信号存活”。
3. 若 frozen 通过，构造 parent/patch frozen embedding + 双线性/轻量 head；不微调 backbone。
4. 同时从 0805+ sequential 数据建立 continuation eligibility/censoring 表；不直接训练旧 b1/b2 主张。
5. 新采集时固定每个 parent 的候选数与 K-step continuation policy，保留 parent，记录每次选择概率、
   operator eligibility、visit/停止原因，形成可识别的 prospective confirmation。
