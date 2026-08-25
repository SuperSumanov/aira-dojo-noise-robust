# Agentic Benchmark Checklist 交叉审计与主张收紧

日期：2026-08-25

状态：`HUMAN_ASSESSMENT_WITH_HASH_BOUND_EVIDENCE_AWAITING_FIRST960`

## 1. 本轮为什么值得做

[Agentic Benchmark Checklist（ABC）](https://arxiv.org/html/2507.02825) 是 NeurIPS D&B
2025 的 agent benchmark 严谨性框架，分为 outcome validity、task validity 和 reporting。它已经直接评过
MLE-bench：论文把 O.i.1、T.2--T.10、R.1--R.12 评为满足，把 T.1（prompt 未指定 Python/PyTorch
版本）和 R.13（没有 trivial agent）评为不满足。

所以我们不能把 MLE-bench 的既有严谨性当作 Decision Corpus 的新贡献。我们的增量必须落在这个衍生 benchmark
特有的问题上：真实搜索树的 physical-run 身份、同一决策点 sibling 口径、run-clean/时间外切分、结果盲摄取、
choice-set 缺失、结构拒收、方法同池、标签重复性、query/init/execution 成本和聚类推断。

## 2. 交叉审计口径

机器文件：

- `phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825/crosswalk.json`；
- `phase1/results/agentic_benchmark_checklist_crosswalk_v1_20260825/independent_verification.json`。

24 项保持四种不可互换的状态：

| 状态 | 数量 | 含义 |
|---|---:|---|
| `PASS_LOCAL` | 9 | 衍生 benchmark 有本地、哈希绑定证据 |
| `PARTIAL` | 9 | 已有一部分控制，但关键条件尚未闭合 |
| `INHERITED_UPSTREAM` | 5 | 只继承 MLE-bench/Kaggle，不算本地贡献 |
| `NOT_APPLICABLE` | 1 | ABC 原项目与 predictor benchmark 的对象不同 |

不汇总“合规分数”。把 partial、继承项或 N/A 二值化后求均值会制造虚假的高分，也掩盖 first-960 未闭合这一
事实。独立验证器只验证 24 项全集、保守状态锁、证据路径及 24 个本地文件的 LF 归一化 SHA-256；它明确不认证
人工语义判断。

## 3. 已经成立的本地正资产

九个 `PASS_LOCAL` 是 T.5、R.2、R.4--R.9、R.11：

1. **结果盲与隔离契约**：first-960 在 closure 前不读 grade/outcome/orientation；已有 pair 是同预算、真实
   physical-run siblings，train/frozen 按 run 隔离。
2. **开放 harness**：重建、审计、prediction escrow、独立 verifier 和攻击测试均在公开仓库中。
3. **append-only 更新机制**：不可变 batches、credential-first 摄取、逐 archive fail-closed 拒收与确定性重建。
4. **构念与对象清楚**：对象是独立 critic/predictor 在候选执行前排序同一决策点 siblings；不是底座 agent
   微调，也不能把 post-execution self-report 当免费 predictor。
5. **缺陷发现与解释边界**：run 泄漏、fragmentary choice set、跨 run clone、结构拒收、任务集中度和方法异池均有
   显式审计；机器 evidence index 禁止把结构覆盖写成 accuracy、effect 或 search utility。
6. **缺陷影响可量化**：当前 7cda snapshot 的七臂共享 2,635 个 canonical pairs、334 个 finite-decision runs、
   30 tasks，左右方向反转为 0；post-baseline 90 个 archive decisions 中 12 个被结构拒收；任务均衡债务有逐任务
   整数护栏；choice observability、标签重复性、clone 和部署成本另有独立收据。

这些是数据集/审计协议的正结果，不是 critic accuracy 的正结果。这个区分反而使 D&B 叙事更可信。

## 4. 仍不能打勾的关键项

九个 `PARTIAL` 中最重要的是：

- **T.1/T.6 producer 可复现性**：future config-v2 已能对完整 resolved solver 做 prompt-sensitive 指纹，但真实
  producer 尚未部署；历史 archive 也缺完整 Python/PyTorch/环境版本。0823 数据不得事后回填为 exact stratum。
- **T.2/T.3 API 依赖**：CPU predictor 可离线复现，但 LLM judge 与 producer 依赖 provider；最终公开 harness
  仍需冻结 outage/status 语义，禁止失败时悄悄删 pair 或换模型。
- **T.10 完整漏洞审计**：已发现并修复多类问题，但闭合 first-960 的最终 post-closure audit 尚未发生。
- **R.1 发布**：v11 可由 Git LFS 重建；first-960 仍只有 339/960，不能称 prospective release 已公开。
- **R.3 contamination**：run 泄漏和代码 clone 有控制，但公开 Kaggle 任务可能进入底座预训练，无法证明 task secrecy。
- **R.10/R.12 最终报告**：已有 retrospective clustered CI 与 random/static 基线；prospective 同池表必须等
  first-960 + closure 后只跑一次。

R.13 保持 `NOT_APPLICABLE`：原 checklist 要求 do-nothing agent；predictor benchmark 的正确类比是
orientation-independent random predictor。我们会把 random 设为强制 sanity baseline，但不把类比伪装成 literal PASS。

## 5. 防 scoop 后的主张边界

两篇近作进一步关闭了宽泛方法 novelty：

- [Aletheia](https://arxiv.org/abs/2601.12186) 已系统研究 execution-grounded code verifier 的训练/推理
  scaling、recipe 组件与跨 policy/covariate shift；“更干净地做 code verifier scaling”本身不够新。
- [Agent Psychometrics](https://arxiv.org/abs/2604.00594) 已预测 unseen task、unseen benchmark 及 unseen
  LLM-scaffold 组合的 task-level agent 成败；“低成本预测 agent performance”也不能作为宽泛首创。

我们仍有可守住的不同单位：**同一次真实 MLE-agent 搜索中、同一 parent/预算/上下文下的 sibling candidate
decision**。它既不是 Aletheia 的独立 code response verifier，也不是 Agent Psychometrics 的 task-level success
prediction。主张应收紧为：

> An auditable decision corpus and predictor benchmark for execution-free, within-search candidate selection in ML
> engineering agents, with physical-run isolation, outcome-blind temporal confirmation, common-support evaluation,
> label/coverage/cost audits, and an immutable rebuildable release.

不能声称“首个 code verifier”“首个 agent performance predictor”或“已证明 learned critic 加速搜索”。

## 6. 下一步裁决

1. 继续 outcome-blind first-960 摄取；按实际 canonical pair 产量执行所有任务同时均衡约束，不以 raw runs 代替。
2. 推动学长把 config-v2 sidecar 在下一批真实 producer 上 outcome-before 部署；这直接补 T.1/T.6，也是 clean scaling
   confirmation 的必要条件。
3. closure 前只允许完善 prediction escrow、共同支持、发布和审计资产，不读效果、不调门、不挑任务。
4. first-960 + 独立 closure 后，一次性运行冻结的 common-support predictor 表、task/run clustered uncertainty、
   noise/missingness sensitivity 与部署成本连接。
5. 若 prospective learned critic 仍无优势，论文仍可作为“高审计强度 decision corpus + 系统 predictor benchmark”投
   D&B；若 clean scaling 或某一冻结臂出现稳定正增益，则升级为方法与数据双贡献。

本轮 GPU/API/base-model updates=`0/0/0`，prospective outcomes/prediction aggregate=`未读/未聚合`。
