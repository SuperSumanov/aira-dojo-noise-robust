# BenchmarkCards / ReproEvalCard：Evidence Index 防撞审计

日期：2026-08-28。性质：只读公开一手材料的 related-work 核验；没有读取 first-960/Target-300 的
label、outcome、prediction、accuracy 或 search utility，没有启动 GPU/API/model fit/base update。

## 1. 直接边界

1. [BetterBench（NeurIPS 2024 D&B）](https://papers.nips.cc/paper_files/paper/2024/file/26889e8359e7ef8a7f5d77457364ca55-Paper-Datasets_and_Benchmarks_Track.pdf)
   已给出覆盖 benchmark 生命周期的 46 项质量评估框架、最低质量 checklist，并评估 24 个 benchmark、维护 living
   repository。故“首次系统 benchmark 质量 checklist/生命周期审计”不能主张。
2. [BenchmarkCards（NeurIPS 2025 D&B）](https://papers.neurips.cc/paper_files/paper/2025/file/76175f4355e2f67cf91be468c8860070-Paper-Datasets_and_Benchmarks_Track.pdf)
   已把 benchmark 的目的、方法、数据、假设和限制标准化，并同时发布 Markdown 与 machine-readable JSON 以接入
   compliance/audit workflow。故“首个 machine-readable benchmark card/index”不能主张。
3. [ReproEvalCard（ACL 2026）](https://aclanthology.org/2026.acl-short.22/)
   已针对多阶段 LLM pipeline 固定 prompts、judge configurations、retrieval snapshots、intermediate traces 等最低
   复现材料，并审计 55 篇论文。故“首个 agent/pipeline evaluation artifact checklist”不能主张。
4. [Auto-BenchmarkCard（AAAI 2026 Demo）](https://ojs.aaai.org/index.php/AAAI/article/view/42352)
   已用多 agent 从论文/Hugging Face/Unitxt 自动抽取 benchmark 描述，并用 atomic entailment 做事实验证。故“首个自动
   生成并验证 benchmark card”不能主张。
5. [When Is Benchmark Contamination Detectable?（arXiv:2608.07914v1）](https://arxiv.org/abs/2608.07914)
   已明确指出 contamination 的 non-rejection 只有与 efficacy、budget 和 validity gates 同报才可解释，并给出
   predeclared planner 与 sample-split certificate。它是 2026-08-08 的预印本，引用时必须标明未审稿；“首次把未检出与
   power/validity contract 绑定”不能主张。

检索还命中 arXiv:2607.25589；其当前 arXiv 页面明确标记 **withdrawn in full / earlier versions should not be cited**，
因此不把旧摘要中的数字或结论作为 related-work 证据。

## 2. 对当前主张的裁决

Evidence Index v8 不是一般性的 card、checklist、自动文档生成或 contamination-detection 新方法。它只能定位为我方
Decision Corpus 的 **machine-verifiable release mechanism**：把每个 MLE-specific estimand、精确输入/哈希、撤回链、
结果盲时间序 cohort、独立 verifier、成本/噪声/pair graph 和 claim boundary 绑定到同一个可重建版本。

因此以下措辞关闭：

- first machine-readable benchmark/evaluation card；
- first evidence index / reproducibility checklist；
- first audit contract that reports failures or non-rejections；
- general contamination-certification framework。

仍可守的正贡献不是容器形式，而是容器中此前 benchmark cards 没有给出的 **MLE search-distribution 实证内容**：

- 真实同-parent sibling fragments，而非把线性 trajectory adjacency 当 choice；
- physical-run、comparison-component、experiment-config 与 chronological split 的联合隔离；
- append-only、outcome-blind accrual、prediction escrow 与独立 closure receipt；
- 连续 pristine external grade 下的 gap/regrade-noise、failure/missingness、endpoint reuse 与 pair-induced task weighting；
- query/init/execution 成本和完整 release→future 的表示限定 temporal-overlap certificate。

## 3. 正面推进方式

论文中应把 BetterBench、BenchmarkCards 与 ReproEvalCard 作为上位 reporting standards；Evidence Index 逐字段映射这些
标准，并突出额外的 MLE-specific provenance/estimand fields。这样能把“我们又发明一张卡”的脆弱 novelty，转换为更强的
可复核主张：**现有 reporting standard 在一个真实 MLE-agent search corpus 上被落实到逐 artifact、逐撤回、逐时间截面的
可执行证据链，并揭示 pair graph/physical run/opportunity yield 会实质改变 predictor benchmark 的测量对象。**

该定位仍不允许把 syntactic zero-link certificate 写成 semantic clone 或未知预训练污染不存在，也不允许在 first-960 +
closure 前写 prospective predictor effect。
