# COTA 同前缀比较器：最新防 scoop 与主张收紧

日期：2026-08-27
性质：公开一手文献核查；不启动实验、不读取前瞻 outcome/prediction、不调用 GPU/API。

## 1. 新出现的直接工作

Jiang et al., *Don't Solve, Just Compare: Tiny Advisors for Runtime Intervention in LLM Agents*,
[arXiv:2608.21027v1](https://arxiv.org/abs/2608.21027)，于 2026-08-21 提交。它提出 COTA：

- 在同一 actor-visible state / exact prefix 上改变 branch-point action；
- 每个 branch 随后交还同一个 frozen actor，以终局 return 估计 actor-conditioned
  `Q^pi(s,a)`；
- 用同前缀 sibling branches 构造 A/B/T pairwise supervision；
- 全参数训练 Qwen2.5-0.5B comparator；
- 推理时对 A/B 与 B/A 两个顺序都判断，只有语义方向一致才接受 winner，tie、顺序不一致、格式错误均不触发 winner；
- 从 `K` 个候选的 winner count 估计 candidate-relative domination rate，并以 `R/K` 门触发非绑定建议，原 actor
  继续负责 replanning 和 execution；
- 在 WebShop、ALFWorld、tau3-Retail 的 3 个 actor × 3 个环境上均报告正收益。论文还把离线 base rollout、
  branch rollout 与 comparator fitting 的 H200 GPU-hour 分开计价。

该工作不是只有“相似标题”。它已经同时覆盖了本项目曾考虑过的三个核心方法命题：同状态 pairwise continuation
比较、弱小 comparator 指导更强 frozen actor，以及 comparator judgment 到在线 intervention 的转换。

### 1.1 与此前已记录先例的联合边界

COTA 不是“二元 ML-program predictor”的首篇工作。本项目在 2026-08-20 已记录 Co-Reyes et al. 的
[Guided Evolution with Binary Discriminators for ML Program Search](https://arxiv.org/abs/2402.05821)：它把 symbolic
optimizer、RL loss、symbolic regression 和 NAS candidates 编为 DAG，在线训练 pairwise discriminator，并用
PAM/PAM-RT 比较 mutated child 与 parent、拒绝预测较差且尚未执行的 candidate；Hero/AutoRL 分别报告约 3.7×/4×
搜索加速。两项工作的直接覆盖应分层理解：

- Guided Evolution 已覆盖 `program pair → binary predictor → skip costly evaluation → guide search`；
- COTA 进一步覆盖 `exact prefix → alternative action → same frozen actor continuation → Q^pi ordering → runtime advice`；
- CPRD/BoN preference-learning 理论已覆盖 comparison distribution、margin/connectivity 与 target deployment
  distribution 的一般关系，因此“pair construction determines deployment estimand”也只能作组织原则，不能作我方
  理论或概念首创。

我方不是在二者之间寻找措辞空隙。剩余贡献必须由 MLE 完整 Python solution、真实 physical-run sibling、连续 pristine
external score、时间前瞻盲态闭合和可重建审计共同成立；缺少这些具体证据时，不得声称新的 comparator 方法。

## 2. 立即关闭的主张

从本记录起，以下表述不得再作为我方 novelty 或正方向：

1. “首次把 agent 决策降为同状态两个候选谁会通向更好结果”；
2. “小 critic 不必会解题，只需比较，即可指导更强 actor”；
3. “pairwise continuation supervision 比 absolute-Q 更适合在线控制”；
4. “A/B/T + 双输入顺序一致性是一种新的 comparator 设计”；
5. “把 sibling comparator 接到运行时 gate/重规划即可构成方法贡献”。

学长此前提出的“给定时间、硬件、agent，比较树中两个节点哪个更可能通向更优解”与 COTA 的
`Q^pi(s,a)` 定义在概念上高度接近。即使迁移到 MLE，也只能称领域复现/压力测试，不能再称一般方法首创。

## 3. 我方仍可守、且更应强化的边界

COTA 不等价覆盖当前论文容器。差异必须写成可核查事实，而不是 first/only：

- **对象不同**：COTA 比较 WebShop click/search、ALFWorld admissible command 与 Retail tool/dialogue action；我方资源是
  MLE 搜索中可执行的完整 Python candidate program 和真实同-parent choice fragment。
- **标签 estimand 不同**：COTA 通过受控 continuation 估计 `Q^pi(s,a)`；我方当前 canonical decision label 是 candidate
  自身 pristine external execution score 的相对次序。二者绝不能混称“future potential”。
- **数据与审计不同**：我方贡献包括 physical-run/comparison-component 隔离、experiment/config provenance、连续 hidden
  score gap 与 regrade noise、missing/source-failure registry、endpoint reuse/pair graph、query/init/execution cost，以及
  append-only、结果盲的时间前瞻 cohort + closure。
- **论文任务不同**：COTA 是正向 runtime-intervention 方法论文；我方应坚持 Decision Corpus + Predictor Benchmark +
  Audit Protocol，研究不同 pair construction 和 aggregation 对 deployment estimand 的影响。

因此 COTA 反而加强了一个已有但非我方首创的组织原则：**pair construction 决定所学习的量**。同 prefix + same continuation actor 的
return pair 学的是 continuation ordering；同 parent 完整程序的即时外部分数学的是 current-solution ordering；global/value
pair 又是第三种 comparison distribution。headline accuracy 不可跨三者直接横比。

## 4. 对当前执行路线的影响

- 不恢复已关闭的 `K>=1` lookahead、未来潜力标注或运行时控制器实验；不为了追 COTA 另开方法线。
- clean 0.6B→8B scaling 仍有价值，但定位只能是：在 MLE 完整程序 decision distribution 上，predictor capacity 是否
  可 transport；不是 pairwise comparator 或 tiny-advisor 方法创新。
- 我方 LLM judge 已做双顺序检查；今后可把 COTA 作为该保守设计的直接 related work，但不得称我方首创。
- 论文 related-work 表必须加入 COTA，并显式区分 `immediate pristine score` 与 `actor-conditioned continuation return`。
- related-work 表还必须把 Guided Evolution 列为更早的 ML-program binary-predictor / execution-skipping 直接先例；
  不得用 COTA 的 2026 日期暗示该一般范式此前不存在。
- first-960/target-300、config-v2 producer 部署、outcome-blind support gate 和 GPU 审批边界均不改变。

## 5. 本轮访问声明

同一轮检索还发现 Chen and Zhang, *No Judgment Without a Reason: Counterfactual Receipts for Versioned AI
Evaluators*, [arXiv:2608.20938v1](https://arxiv.org/abs/2608.20938)。它用 grounds/norms/authority 的反事实替换定义
judgment receipt，并强调 prediction 与 certification 分离。这与我方 byte-level data/checkpoint/provenance receipt
不是同一对象，但关闭任何泛称“首次给 versioned evaluator 加 receipt/认证层”的措辞；我方只能把 receipt 写成工程可复核
机制，不申一般 evaluator-accountability 方法 novelty。ACES（[arXiv:2608.20614](https://arxiv.org/abs/2608.20614)）
又已对固定 model/sandbox/grader 做 paired live Skill Lift；它是相邻的 artifact-evaluation 工作，不直接覆盖 MLE sibling
corpus，但也提醒我们不能把 paired same-harness evaluation 本身写成新概念。

只读取 arXiv 公开页面/HTML 与本地已公开方向文档；未下载或运行其代码，未读取我方 prospective label/outcome/prediction，
未训练模型，GPU/API/base-LLM update=`0/0/0`。
