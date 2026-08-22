# Score-channel 最新直接竞品与撤稿边界

日期：2026-08-23。状态：`RELATED_WORK_SCOPE_NARROWED_MAINLINE_UNCHANGED`。本记录只使用论文原始页面和原始
预印本，不启动模型、GPU、API，也不读取 future cohort outcome。

## 1. AuditRepairBench 关闭宽泛首创，但不是当前 estimand

`AuditRepairBench: A Paired-Execution Trace Corpus for Evaluator-Channel Ranking Instability in Agent Repair`
（arXiv:2605.04624v1，2026-05-06）已经明确提出 evaluator-channel ranking instability，并在 agent repair 中保持
task/candidate/final evaluator 固定，只阻断 selector 可见的 evaluator-derived path。其 v1 声称 576,000 registered
cells、96,000 executed traces，并用 channel surgery、screening 与 rank displacement 研究 evaluator-to-selector coupling。

因此以下主张已不可用：

- “首个研究 evaluator channel 对 agent selection 的影响”；
- “首个用 paired execution / channel blocking 研究 agent ranking instability”；
- “只要不同 feedback channel 改变排序就构成方法 novelty”。

但 arXiv 当前页明确标记该稿已撤回；作者在 2026-07-24 的 v2 说明“实验设计和评估存在影响主要结论有效性的重大
问题”。我们不能把 v1 数值当可靠已确认结论，也不能因撤稿假装它不存在。它是最近概念先例和风险警告。

当前 score-channel estimand 与它仍有可核差异：我方不是在多个 agent repair 系统上检测 evaluator-to-selector 的代码
路径，而是在同一 MLE candidate、同一短执行上比较两个自然产生的评分通道——外部 pristine evaluator 对
`submission.csv` 的评分与 agent stdout self-report——并绑定 physical run、执行时长、coverage、噪声上界和
append-only temporal cohort。未来 replay 若获批，也必须只改变 selector 可见的评分通道，保持 candidate、runner、
预算和最终 evaluator 不变。

原始来源：

- https://arxiv.org/abs/2605.04624
- https://arxiv.org/pdf/2605.04624v1

## 2. AutoResearchEval 是 artifact/process 邻居，不是通道对照

`How Do Agents Fail on AutoResearch`（arXiv:2608.14905v2，2026-08-19）发布 100 个 frontier research tasks、
8 个 harness-model 组合和 800 条 trajectory，强调 process-level annotation、intermediate artifact visibility 与缺少
metacognitive checking loop。它加强“只看最终分数不够、应审计过程与 artifact”的动机，但没有在固定 candidate/
预算下比较 pristine submission score 与 stdout self-report，也没有我方 MLE physical-tree 的 temporal/noise/cost
contract。

原始来源：https://arxiv.org/abs/2608.14905

## 3. 对正面论文主张的约束

当前最可守的正面表述不是发明“evaluator channel”，而是：

> 在真实 MLE-agent 搜索树中，执行反馈不是一个同质 scalar。对同一短执行，artifact-grounded external score 与
> agent-declared stdout score 的可用性和判别力可能存在可复现的 execution cliff；一个时间隔离、物理 run-clean、
> 成本与噪声可审计的数据资源能够定位该 cliff，并检验只改变 selection-visible channel 是否改善预算内搜索。

这仍只是待前瞻复现的机制假设。只有 0DY/0DZ future cohort 的固定 truth-support 门通过，且随后另行批准的 replay
保持最终 evaluator 不变、只改变 selector-visible channel，才允许写机制正结果。若 gate 不过，则保留为严谨的
benchmark/measurement 资产，不把撤稿邻居的宽主张改名重发。
