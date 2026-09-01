# Decision Corpus 论文蓝图（2026-09-02）

> 当前稿件入口。服从 `CURRENT_DIRECTION.md` 与 Evidence Index v10；旧 `paper.tex` 的
> “Decodable but Not Usable”、HCE、多保真、Probe、score-channel 与 lookahead 叙事均为历史材料，不能复制进新稿。
> 本文件是写作蓝图，不授权揭盲、GPU、API 或模型训练。

英文正文初稿入口为 `PAPER_DRAFT_DECISION_CORPUS_20260902.md`。该稿已展开 Abstract、Sections 1--8 与
internal evidence routing；prospective common-support 与 clean scaling 仍是显式 sealed/conditional slot，不能提前填值。

## 1. 论文定位

**主投容器**：NeurIPS Datasets & Benchmarks。

**工作标题**：

> **Decision Corpus: Auditing Predictors for ML-Engineering Agent Search Trees**

**一句话 thesis**：

> Evaluating a critic for ML-engineering search is not ordinary pairwise classification: the estimand is induced by a
> partially observed, execution-costly search tree, and credible conclusions require physical-run isolation,
> choice-fragment accounting, pair-weight auditing, cost/noise receipts, and outcome-blind temporal confirmation.

**论文形态**：NAS-Bench-style 数据资产 + 系统 predictor study + 可执行 audit protocol。不是新的 reward-model
训练算法，也不是新的 agent policy；clean scaling 若确认，是这套 benchmark 上的一项强实证发现。

## 2. 摘要草稿 v0.1（结果槽位尚未揭盲）

> ML-engineering agents generate alternative programs but must execute and train them to observe solution quality. A
> cheap pre-execution predictor could allocate this budget, yet reported predictor performance is easily confounded by
> linearized trajectories, physical-run leakage, incomplete choice sets, pair-induced reweighting, label noise, and
> post-execution signals presented as free baselines. We introduce **Decision Corpus**, a rebuildable benchmark of
> provenance-bound sibling decision fragments from real AIRA-dojo searches, paired with a common-support predictor suite
> and a machine-verifiable audit protocol. The historical v11 release contains 8,107 audited direct-sibling rows under
> recorded parent pointers; its parent-present strict core retains 7,579 rows, with zero same-budget train/frozen overlap
> in pairs, endpoints, parents, or referenced physical runs. An independently regraded ten-task subset reaches 96.6%
> raw and 98.0% task-macro ordering agreement, while lightweight predictor queries are 4,048--6,037 times cheaper than
> median candidate execution under a pinned CPU protocol. We further show that balancing physical runs need not balance
> decision pairs: opportunity-yield heterogeneity reverses the temporal direction of run-level and pair-level task
> concentration. A sealed chronological cohort currently contains 517 eligible runs; its fixed scorer preserves all 494
> prior runs after 23 additions, and labels and predictions remain hidden until the preregistered first-960 closure.
> **[CLOSURE SLOT: one-shot common-pool predictor table.] [OPTIONAL CONFIRMATION SLOT: clean 0.6B-to-8B scaling.]**
> Decision Corpus turns critic evaluation for ML-agent search into a versioned, cost-aware, leakage-resistant measurement
> problem and releases the data, reconstruction manifests, withdrawal ledger, and independent verifiers needed to audit it.

摘要中的前瞻句在 closure 前只能保留为内部占位；正式投稿不得出现未揭盲效果、accuracy 或 utility。

## 3. 三项当前可守贡献

### C1. Decision Corpus：真实 search decision 的发布单位

- 发布 provenance-bound sibling **fragments**，保留 physical run、recorded parent、decision parent、endpoint、budget、
  split 与 comparison-component；不把 root-to-leaf path adjacency 冒充 choice。
- 外部 pristine continuous grade、status-certified validity partial order 与 missing-source registry 分开发布；不把
  validity dominance 冒充完整 numeric total order。
- immutable batch + manifest + deterministic rebuild；历史 v6--v11 与前瞻 append-only snapshot 各有 SHA 和撤回链。
- 当前不声称完整 choice set，也不声称 recorded parent 是 semantic/causal ground truth。

### C2. Predictor Benchmark：同池、成本感知、时间外确认

- random、静态特征、TF-IDF、冻结嵌入、独立 reward model、LLM judge 等 family 在 exact common support 上比较。
- 每个模型同时报告 initialization、online query、candidate execution 成本；self-report 明确标为 post-execution signal。
- headline 同时给 pair-micro、task-macro、parent/run 聚合、coverage/tie/missingness、clustered uncertainty 与 LOTO。
- historical development 与 first-960 temporal confirmation 分离；checkpoint 只能由 train-run dev 选择，frozen cohort
  closure 后一次揭盲。
- **当前缺口**：最终 prospective predictor table 尚未揭盲，不能把本贡献写成“critic 已提升搜索”。

### C3. Audit Protocol：搜索分布会改变 benchmark estimand

- physical-run、endpoint、parent、component 与时间轴零交集门；token/AST clone 与 complete-release→future overlap
  certificate 另列适用范围。
- noise/regrade、choice observability、status partial order、source missingness、query/init/execution cost 与 pair graph
  weighting 使用独立 receipts。
- outcome-blind append-only intake、prediction escrow、one-time closure anchor、producer/verifier A/B、read-only root、
  file/network/credential trace 与 claim withdrawal ledger。
- 实证发现不是一般统计定理：在当前 MLE search corpus 中，task-specific decision-opportunity yield 会使 run-level
  与 pair-level任务权重沿相反方向变化，因此 pair-micro 不能自动代表“均衡采集”。

## 4. 若确认才可加入的第四项

### C4（conditional）. Clean critic capacity scaling

只有同时满足以下条件才进入摘要/贡献列表：

1. 新真实 producer 在 outcome 前生成 canonical config-v2 sidecar；旧 archive 不回填。
2. exact generator/config stratum，train/dev/frozen physical-run 零交集。
3. `Qwen3 Base 0.6B/4B/8B × seeds 6/7` 六个训练 run 只改变模型规模；context、steps、optimizer、prompt、
   checkpoint rule、scorer 与预算一致。
4. checkpoint 由 train-run dev 选择，untouched frozen cohort 只评一次。
5. 两个 seed 的 `8B−0.6B` 均为正，且 task/run 聚类区间、task-macro、LOTO 与 dominant-task deletion 不矛盾。

若任一条件不满足，scaling 只留在探索性附录或 future work，不阻塞 C1--C3 的 D&B 论文。

## 5. 正文结构

### 1 Introduction

- 先讲执行成本：候选质量只有运行程序后才可见，critic 的决策价值发生在执行前。
- 再讲 measurement gap：trajectory dataset 不自动等于 decision benchmark；pair 行也不自动独立同分布。
- 用三项贡献收束；不在 introduction 宣称 first/only/largest。

### 2 Related Work

四组相邻工作必须分别处理：

1. **MLE trajectories / actor learning**：ML-Agent、OpenMLE/Frontis-MA1、mle-traj。它们关闭“首个/最大 MLE
   trajectory”与 operator/actor-learning novelty；我方差异是 decision-time predictor measurement 与 audit contract。
2. **Tree/reward-model search**：AgentRM、Step-Level Q-Value Models、ReLoc、SELA。它们关闭“首次从树训练 critic”
   “首次 sibling/parent RM”“首次 critic-guided code search”。
3. **NAS predictors/benchmarks**：How Powerful are Performance Predictors in NAS?、NAS-Bench-Suite-Zero、
   NAS-Bench-360。借鉴 init/query accounting、跨任务 predictor suite 与 dataset-first 论文形态。
4. **Benchmark reporting**：Agentic Benchmark Checklist、BetterBench、BenchmarkCards、ReproEvalCard。Evidence Index
   是在真实 MLE search distribution 上落实这些原则，不是通用 card/checklist 的发明。

### 3 From Search Trees to Decision Corpus

- 数据生产、archive taxonomy 与 credential-first intake。
- physical run → endpoint → decision parent → sibling relation。
- finite numeric orientation、status-certified partial order、unknown relation 三者分开。
- historical release、chronological prospective cohort、prediction escrow 与 closure。
- 数据许可、Kaggle task access、隐私与去标识化。

### 4 Benchmark Tasks and Predictors

- estimand panel；pair-micro 不是唯一 headline。
- predictor family、train/dev/frozen 与 common-support join。
- 初始化、query、execution 成本定义。
- frozen one-shot protocol；所有结果按 seed/run/task 报告。

### 5 Audit Findings

- run leakage 与 lineage reconstruction；historical v11 strict core。
- label repeatability/noise ceiling 的假设边界。
- source/choice observability 与 status partial order。
- pair-induced task weighting 与 opportunity-yield mechanism。
- exact/fuzzy clone、temporal overlap 与未覆盖的 semantic/pretraining contamination。
- archive-granular gate 的 support-preserving certificate。

### 6 Predictor Benchmark Results

- 先放同池历史开发表，再放 first-960 one-shot confirmation。
- 按 accuracy/calibration/coverage/cost 四轴解释，不用单个 pooled accuracy 排名。
- clean scaling 只有通过 C4 条件才进入本节主表。

### 7 Limitations, Governance, and Release

- incomplete choice fragments、public Kaggle task secrecy、producer/config history、任务异质性、未证 semantic clone。
- claim ledger、失败运行、撤回链、raw-vs-public artifact 边界。
- 不微调/RL-finetune agent 底座；独立 critic 与 agent policy 的外部效度边界。

## 6. 主表与主图

Table 1--3 的可粘贴正文草稿、caption 与 evidence routing 已写入
`phase1/PAPER_TABLES_1_3_DRAFT_20260902.md`；该文件不授权填入任何 prospective outcome。

| 编号 | 内容 | 当前状态 | 绑定证据 |
|---|---|---|---|
| Table 1 | 与 ML-Agent/OpenMLE/mle-traj/NAS predictor benchmark 的单位与协议比较 | 可写；raw mle-traj tree recoverability 保持 unknown | 2026-08-28 直接竞品审计 |
| Table 2 | Corpus statistics：historical strict core + sealed prospective structural support | 可写结构值；不得写 prospective outcome；v11 schema 已逐字段闭合 | Evidence Index v10 entries 1, 14, 19 + v11 schema inventory |
| Table 3 | Audit findings 与适用范围/失败门 | 可写 | Evidence Index v10 全 20 distinct entries |
| Table 4 | Exact-common-support predictor benchmark：accuracy/calibration/coverage/init/query | **等待 first-960 closure** | prospective gate + prediction receipts |
| Table 5 | 0.6B/4B/8B × 2 seeds clean scaling | **等待 sidecar、GPU 审批与训练** | C4 条件 |
| Figure 1 | archive→run→endpoint→parent→pair + vault/escrow/closure 流程图 | 可画 |
| Figure 2 | run-level 与 pair-level task weight 随时间反转；标注单 drop 高 leverage | PNG/SVG/receipt 已完成且双次渲染逐字节一致 | structural_weighting_shift |
| Figure 3 | predictor quality--query cost Pareto，execution p50 作参照 | 等 Table 4；成本轴已完成 | deployment_cost |
| Figure 4 | historical→prospective transport 与 scaling curve | 等 closure/C4 | prospective gate |

## 7. 已核验的正文数字与精确边界

| 可引用数字 | 安全表述 | Evidence Index 名称 |
|---|---|---|
| 8,107 rows；7,579 strict core；528 orphan-parent tier | recorded-parent lineage audit；35/36 support gates，不能说全部门通过 | `decision_corpus` |
| same-budget train/frozen pair/endpoint/parent/run overlap 全 0 | historical v11 的固定轴；不代表未知 pretraining decontamination | `decision_corpus` |
| 2,079 status edges；error-only 2,060 | validity partial order，不是 numeric total order | `status_certified_partial_order` |
| 3,001/3,252 source winners answerable | finite orientation + status implication；仍有 unanswered parents | `source_decision_answerability` |
| regrade raw 0.965860；task-macro 0.980181 | 10-task measured subset；transport ceiling 依赖 symmetry/exchangeability | `label_repeatability` |
| predictor query p50 对 execution p50 低 4,048--6,037× | pinned CPU deployment path；不证明 search utility | `deployment_cost` |
| run→pair TV 0.337083；yield 解释 HHI/TV 增量约 0.645/0.595 | 方向持续且 task-deletion robust；幅度被一个 drop 高 leverage | `structural_weighting_shift` |
| 494→517 runs，+23/−0；13,098 endpoints、3,230 pairs 精确保留 | provisional append-only scorer support；未闭合 first-960 | `prospective_wl_snapshot_chain_517` |
| 20 archives / 94 physical runs / 92 eligible runs / 2,558 endpoints 被 archive-granular gate 保留 | deterministic corpus-utility accounting，不是 online effect | `archive_granularity_retention` |
| 14 reject events、7 competitions；6 retained support、1 zero-checkpoint trigger | post-hoc descriptive census；当前观测 last usable support elimination=0 | `archive_rejection_support_census` + derived gate certificate |

注意：13,581 eligible structural endpoints 与 WL 的 13,098 scorer-common-support endpoints 是两个不同口径，正文必须
分栏，严禁合并或互相替代。

## 8. 绝对禁止进入标题、摘要或贡献点的措辞

- “first/largest MLE trajectory dataset”；
- “first reward model trained from a search tree / sibling pairs”；
- “first critic-guided code or MLE search”；
- “complete choice sets”或“recorded parent is semantic ground truth”；
- “no contamination / no semantic clones”；
- “all integrity gates pass”（historical strict core 明确 35/36）；
- “learned critic improves search”或“confirmed scaling”，直到冻结门真正通过；
- 把 self-report 称为 execution-free/free predictor；
- 把 0KW reconstruction 或 Structural Gate Utility Certificate 重复计成独立科学结果。

## 9. 贡献归属

- 学长：真实 physical-run 语料生产与上传、producer 侧工程、0820 探索性 model-size scaling 信号及其训练资产。
- 我方：run-clean/temporal corpus reconstruction、真实 sibling estimand、predictor benchmark、成本/噪声/覆盖/权重/
  clone/撤回审计、outcome-blind escrow/closure、独立 verifier 与论文 benchmark 主张。
- 联合：clean scaling confirmation 的最终 protocol review、资源执行、解释与写作。

## 10. 未来 20 天的写作交付

- D0--D3：锁定本蓝图、Table 1--3、Figure 1--2 storyboards、
  `DATACARD_DECISION_CORPUS_DRAFT_20260902.md`、v11 schema dictionary 与 claim/withdrawal appendix。
- D4--D8：完成 Sections 1--5 初稿；所有数字从 Evidence Index 路由，不从聊天或旧 paper 抄写。
- D7--D14：closure/sidecar 到位后填 Table 4；C4 获批才跑 Table 5。
- D14--D18：Sections 6--7、limitations、ethics/license/data statement、复现说明。
- D18--D20：形成可给学长逐段批注的完整内部稿；未完成实验保留诚实空槽，不用旧负路线填充。

## 11. 单一更新规则

任何新结果进入本蓝图前必须：

1. 先更新 `CURRENT_DIRECTION.md` 的撤回/覆盖链；
2. 在 Evidence Index 中登记为 distinct entry 或明确的 reconstruction，并显式固定
   `counts_as_distinct_claim_evidence`；
3. 写清 exact commit、population、estimand、失败门与 `does_not_prove`；
4. 若是 first-960/Target-522，确认 closure 后才读取允许的 aggregate；
5. 若是训练，先有用户批准的矩阵、单臂 GPU·时、总 GPU·时与 checkpoint/resume 方案。
