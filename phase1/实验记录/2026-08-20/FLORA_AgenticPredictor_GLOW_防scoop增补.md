# FLORA / Agentic Predictor / GLOW：2026-08-20 防 scoop 增补

## 检索边界

本次在不改动任何实验结果的前提下，复查 2025–2026 年公开一手论文页与官方仓库。检索不能证明“除此之外没有
工作”；它只用于撤回过宽 novelty，并确定下一版 related-work/baseline 的最低要求。

## 新增必须正视的直接邻居

### FLORA-Bench / FLOW-GNN

[FLORA-Bench](https://arxiv.org/abs/2503.11301) 已明确把 agentic workflow 表示为计算图，用 GNN 预测运行表现，
并以 predictor 代替昂贵执行来引导 workflow optimization。公开论文报告 600k workflow-task pairs、binary
success labels、accuracy 与 ranking utility；图节点是 agent calls，边是信息/依赖流。其公开构造按 task success
rate 去掉 >90% 与 <10% 的任务，并在各 domain 内随机 80/10/10 切分。

因此以下宽主张全部关闭：首次把 agent graph 当性能预测对象、首次构建 agent predictor benchmark、首次用
GNN/predictor 省 agent execution、首次同时报告 accuracy 与 ranking utility。

### Agentic Predictor

[Agentic Predictor（ICLR 2026）](https://arxiv.org/abs/2505.19764) 在 FLORA-Bench 上联合 graph、code、prompt
三视图并做跨域无监督预训练；论文报告总体 prediction accuracy/utility 与 predictor-guided workflow search。
因此“code + graph + text 多视图”“低标签预训练”“lightweight predictor-guided agent search”都不是我方可申
novelty。其对象仍是固定 workflow configuration × task 的成功，而不是一次 MLE program-search run 内同 parent
候选的局部选择。

### GLOW 与 AgentSwift

[GLOW](https://arxiv.org/abs/2512.15751) 已把 graph-oriented LLM 语义特征与 GNN 结构表示融合，在
FLORA-Bench 上做 workflow performance prediction；[AgentSwift](https://arxiv.org/abs/2506.06017) 则以 agent
workflow/components 为层级搜索空间，用 value model 与 uncertainty-guided MCTS 减少真实评估。因此新增一个
GNN、graph-language encoder、uncertainty head 或 value-guided MCTS 都只能是 baseline/方法实现，不能凭组件名
成为论文新意。

## 与我方的可核差异

| 维度 | FLORA 系列 / AgentSwift | 我方当前窄边界 |
|---|---|---|
| 被预测对象 | agent workflow/configuration 在任务上的表现 | MLE agent 一次真实搜索中，同一 parent 下候选代码的相对 hidden score |
| 图语义 | agent calls 与信息流/组件图 | physical search run 的 parent/child/sibling choice set 与 operator provenance |
| 标签 | 主要是 binary task success / workflow aggregate | pristine external evaluator 的连续 competition score、pair orientation 与 gap |
| 数据切分 | domain 内随机 sample split；另报 cross-system/domain | physical-run clean、task/run clustered inference、时间外 prospective first-960 + closure |
| 质量审计 | workflow/task filtering 与重复推理稳定标签 | endpoint reuse、pair graph、gap transport、regrade ceiling、query/init cost、泄漏撤回链 |
| 部署问题 | 选哪种 workflow/configuration | 给定 agent/hardware/time/operator，真实 choice set 中先执行哪个候选 |

这张表不是优越性宣称。FLORA 的规模和现有方法正结果明显强于我方；我方只在 decision-unit fidelity、连续 MLE
评分、physical provenance 与 prospective protocol 上不同。

## 对当前论文和实验的强制影响

1. 论文 novelty 主语必须是 **MLE search decision resource + estimand/audit contract**，不是 predictor/GNN/NAS。
2. related work 必须加入 FLORA-Bench、Agentic Predictor、GLOW、AgentSwift，并和已有 FOREAGENT/AIRA_2 一起
   做 unit/label/split/utility 对照。
3. 最终 benchmark baseline 应覆盖 FLORA-style graph/multi-view family，或给出无法等价迁移的可复核原因；不能
   只用 TF-IDF、static LR、LLM judge 后声称 predictor study 完整。
4. 不能把新 graph scorer 偷加进已经激活的 first-960 primary protocol。若实现，只能作为不读 first-960 outcome
   的预冻结 extension，或使用另一个 future cohort；当前 Qwen frozen-checkpoint extension 也继续单列。
5. 近两周 TGCA 已验证的是 pair-graph training augmentation，不等于 FLORA-style graph encoder；但 TGCA 的失败
   同时说明不能在同一 OOF 上继续换启发式追正结果。
6. 目前最低风险正贡献仍是 Decision-Corpus Audit Protocol 与前瞻确认；方法正结果若重开，必须先写与 FLORA
   family 的非重复 estimand、固定 baseline 矩阵和独立未来评测，不因“GNN 可能有效”直接启动长训练。

## 当前 scoop 裁决

`DIRECT_METHOD_NOVELTY_CLOSED_BUT_DECISION_RESOURCE_BOUNDARY_OPEN`。

没有找到公开工作同时满足：真实 MLE program-search physical runs、同-parent sibling choice sets、连续 pristine
hidden scores、run-clean/时间外 prospective split、gap/noise/cost/endpoint-reuse 联合审计。但这只是本次可见
文献边界，不是“全球首个”的证明；正文应使用可逐项核验的差异，不使用 first/only 声称。

