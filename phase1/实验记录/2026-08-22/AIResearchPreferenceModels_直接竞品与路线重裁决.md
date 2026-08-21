# AI Research Preference Models：直接竞品与路线重裁决

日期：2026-08-22。状态：正式裁决前 related-work 审计。时间线必须如实保留：开始本审计时，第一生产者的 stdout
已经出现暂定 `NO_NARROW_POSITIVE`；第二生产者尚在拟合，producer diff、独立 verifier 与 exact-sign audit 均未完成，
所以该值不作为正式结果。本记录不读取 frozen/extension label vault，不修改正在运行的 TF-IDF 模型、split、阈值或
裁决门；竞品边界按论文一手证据裁决，不以该暂定值为条件。不得把本记录称为“完全结果盲”。

## 结论先行

*AI Research Preference Models*（RPM，arXiv:2608.13940v1，2026-08-14）是比 FOREAGENT 更直接的同题工作。
它已经在 AIRA-dojo 中实现“同一 parent 生成多个未执行 child，再由 preference model 选择一个执行”，并用真实
24 小时端到端实验证明了平均分与达到固定表现所需时间的改善。它的离线标签还是“候选子树中的最高 test score”，
与“哪个节点更可能通向未来更好解”的表述直接重叠。因此以下 novelty 表述立即关闭：

- 首次在 AIRA-dojo 中对未执行 child 做 preference selection；
- 首次证明 MLE-agent candidate preference 能提高端到端分数或减少达到固定分数的执行预算；
- 首次用搜索历史、代码或小规模 pilot 判断候选未来潜力；
- 把 subtree-best / future-potential label 本身作为本项目的方法 novelty。

这项发现不等于本项目失去论文价值，但把路线进一步压到两条可防守主轴：

1. **D&B / integrity**：真实 logged decision unit、失败与 unknown 不删除、candidate/run/task 依赖、run-clean 与
   temporal frozen、噪声/覆盖/query-init 成本及撤回链；
2. **评分通道的前瞻机制**：在相同短时执行预算下，pristine 外部 `submission.csv` 分数相对 stdout self-report 的
   信息增益、选择性可观测性和 execution cliff。RPM 的 agentic pilot 与此相邻，但没有替代该测量问题。

RPM 明确把 parent selection 留作 future work。这是一个真实边界，但不能据此把当前 source-choice OOF 包装成已解决的
parent-selection 方法：当前标签是 status-certified source-selection outcome，不是最终任务质量；而且只有原冻结门通过、
再经 frozen/temporal 前瞻复制和预算等价 utility bridge，才可能形成方法主张。

## 一手论文核查

固定对象：

- arXiv 摘要与 v1 HTML：https://arxiv.org/abs/2608.13940 ，
  https://arxiv.org/html/2608.13940v1 ；
- 提交时间：2026-08-14；34 页，v1。

为后续可复现 baseline 另锁定 `https://arxiv.org/src/2608.13940v1`：下载源包为 1,257,333 bytes，SHA-256=
`5140d8a7169e29114f8acc29b1bfc9ae85b162b0a3ed71a5d93e36daf3fa004c`；其中
`sections/appendices/inference_only.tex` 为 15,492 bytes，SHA-256=
`b36dfabfaf39587bb0c361adc648575d8847efc157427a7f4ca8f74dc7e6d3ed`，包含 baseline/optimized prompt 原文。
当前 HTML 转换页没有渲染两段 prompt 正文，故未来若做 RPM transfer baseline 必须绑定上述 source receipt，不能凭
本报告概述重写 prompt。此处只固定公开控制材料，没有运行模型或打开我方 labels。

### 在线主实验

论文在 AIRA-dojo 的 child-creation 阶段，每步从同一 parent 独立生成 `N=15` 个未执行候选，经 pairwise knockout
选一个执行。No-RPM 对照在这 15 个候选中均匀随机选择，因而与 vanilla AIRA-dojo 在期望上对应。operator 与 RPM
都使用 Qwen3.6-27B；20 个公开 AIRS-Bench 文本/表格任务，每任务单张 H200、24 小时、10 seeds，并接入 HCE。

论文报告平均 normalized score：No-RPM `0.684`、inference-only RPM `0.711`、agentic RPM `0.729`；validation/test
oracle 为 `0.748/0.759`。达到 No-RPM 的 24 小时分数所需时间分别为 `14.88/15.50` 小时。task-stratified bootstrap
下，两个 RPM 相对 No-RPM 的 improvement probability 为 `0.5923/0.5913`，95% CI 下界 `0.5066/0.5018`。
这已经是本项目若想申 child-selection 系统收益时必须正面对比的强 baseline，而不是只在 related work 列名。

inference-only 并非真正零墙钟成本：论文 limitations 报告每个 24 小时 run 的自托管 Qwen 推理累计 `0.660` 小时；
扣除后 23.34 小时处 normalized score 为 `0.708`，相对原 `0.711` 小幅下降。agentic RPM 使用同环境的 H200 sandbox
做小规模 pilot，论文明确承认其早期轨迹因逐步计算开销而更慢。

### 离线数据与标签

为开发 RPM，论文从另 40 个未公开 image/video/audio AIRS-Bench tasks 的既有 AIRA-dojo runs 中抽取 1,000 个 sibling
pairs，并按 modality 切 development/evaluation。它删除 normalized test gap `<0.01` 的 near-ties；标签是哪个节点的
**subtree 最高 test score** 更高，而不是 immediate score。论文自己指出旧 greedy policy 会优先扩展 early score 高的
节点，使其更有机会得到更高 subtree max，故该离线标签有 off-policy/机会偏差，主张最终依赖端到端结果。

其离线 inference-only 单模型 accuracy 为 `64.66%--67.44%`；三模型 majority vote 为 `68.04%`，LLM arbiter 为
`69.35%`。论文还报告 context、reasoning budget 和 suggestion-pool 扩大均带来更好离线选择表现。由此，单纯再用
更大 LLM、更长 context、prompt optimization、ensemble 或 pilot 做 sibling future ranking，都不能作为本项目的独立
突破点。

### 三个搜索介入点的边界

论文把介入点明确分成 parent selection、child selection 与 final-node selection：

- 主结果只做 child selection；
- Appendix D 在 650 个公开任务 trees / 32,596 candidates 和另一批未公开 multimodal trees 上做 final-node
  selection，整体没有可靠超过 highest-validation 默认；
- limitations 明确写明 parent-selection 留待 future work。

Appendix D 也暴露了“高 beats-rate 可被 ties 主导”的统计陷阱，并补报只在实际改变 test score 时定义的
override-win-rate。这个审计原则与本项目 tie-aware、decision-unit-faithful、聚类不确定性的方向一致，可作为基准设计
动机，而不能误写成我方首创所有 tie-aware 分析。

## 与本项目当前对象的精确区别

| 轴 | RPM | 本项目当前 source-choice / score-channel |
|---|---|---|
| 在线介入点 | 同 parent 新生成的 15 个 child 中选 1 个执行 | source-choice 是 logged source-selection outcome；score-channel 比较同一候选短时执行反馈 |
| 离线标签 | sibling 中 subtree 最高 test score，先删 gap<0.01 | status-certified source winner；失败/unknown 保留，且不等于最终质量 |
| split | 40 个未公开任务按 modality 分 dev/eval；在线另用 20 个公开任务 | task-LOTO、physical-run OOF、sealed frozen 与 strict temporal extension |
| 依赖/选择机制 | 论文承认旧 greedy off-policy 与 subtree-max 机会偏差 | 显式 candidate/run/task identity、真实 choice-set arity、cluster inference 与 provenance sensitivity |
| 成本 | 在线 24h H200；另报 inference latency；agentic pilot 用 H200 | query/init/执行分账；评分通道固定 30/60/120 秒 watcher 与 pristine grader |
| 已有 utility | 20 tasks x 10 seeds 的端到端正结果 | 尚无 source-choice utility；score-channel 前瞻确认仍等待合格新 runs |

上表说明 RPM 在方法效果上领先，不支持贬低它；同时也说明我们的数据/estimand 与它的 1,000-pair开发集并不等价。
论文正文没有报告我们这套 physical-run-heldout、temporal frozen、failure/unknown-preserving 和 dependency-aware
release contract，因此这些仍是可防守的 D&B 增量。这个“未报告”只限 v1 论文正文，不外推为其作者没有内部审计。

## 对当前工作流的裁决

1. 正在运行的 TF-IDF OOF 原样完成。其协议与结果早于本次路线重裁决冻结，禁止因 RPM 的强结果换模型或降门。
2. 若 OOF 为 `NO_NARROW_POSITIVE`，关闭当前 source-choice 方法线；不以“RPM 留下 parent selection”为理由 rescue。
3. 若 OOF 为 GO，仍须依次通过 exact-sign、recovery-provenance、sealed frozen/temporal replication 和预算等价 utility；
   任何一步失败即关闭。只有这条完整链才有资格讨论 parent-selection 增量。
4. 不自动重开旧 K>=1 lookahead、probe/multifidelity、HCE 三臂、TD/RL 或 LLM judge sweep。RPM 已把这些邻近方法的
   baseline 门抬得很高，而不是提供重新追参的理由。
5. 当前最优先确认性实验保持不变：等待机制 commit 后严格合格的新 physical runs，执行已预注册的 score-channel
   前瞻复现。它与 RPM 的关系应写成“测量并校准 selectively observable execution feedback”，而不是再次发明 RPM。
6. 数据论文叙事更新为：RPM/FOREAGENT 已证明 candidate preference 值得研究；本项目检验这些结论在真实 decision
   topology、失败选择、依赖稳健、时间前瞻和成本诚实条件下还能保留多少，并发布可逐项复核的 benchmark。

## 当前仍可能形成正面突破的窄门

- **近期最可信**：score-channel 严格前瞻复现，若在预注册新 runs 上确认 external pristine score 对共同覆盖候选的
  稳定增益，就形成 RPM 未回答的 execution-feedback measurement 正结果。
- **数据基准正贡献**：把 RPM 的 1,000-pair future label 与 FOREAGENT 的全局组合 pair，和我方真实 logged
  source/sibling decisions 放进统一 dependency/censoring/cost audit；该比较须使用各自公开可核验对象，不能凭摘要推断。
- **高风险方法窄门**：parent selection。只在现有固定 OOF 与 sealed temporal chain 全部通过时考虑；否则保持关闭。

因此，此次审计带来的是一次必要的路线收缩，不是正结果本身。它避免我们在投稿时被一篇同作者群、同 harness、已有
大规模端到端正结果的新论文直接击穿 novelty。
