# Failure memory / execution risk：防 scoop 与正面边界审计

日期：2026-08-17。目的：在 691-node taxonomy、494 parent-matched pairs 和静态 LOTO 结果之后，检查相邻
工作是否已经覆盖“失败预测 / execution feedback / verifier reward”本身。本文不改变 score-channel 主实验。

## 直接邻近工作

| 工作 | 已覆盖的核心 | 对我们的约束 |
|---|---|---|
| [CompCoder (2022)](https://arxiv.org/abs/2203.05132) | 用 compiler feedback 联合训练 code generator 与 compilability discriminator，并以 RL 提升可编译率 | “训练执行/编译判别器并用于筛选”早已不是新原语；而且它会更新 generator，违反我们不微调底座的边界 |
| [RethinkMCTS (2024)](https://arxiv.org/abs/2409.09584) | 在 code MCTS 中执行候选，把细粒度 execution feedback 转成 verbal feedback，再 rethink/refine | “MCTS + 执行反馈 + 错误修复”不新；我们的区别只能是运行前成本/缺失机制与真实 MLE sibling 数据契约 |
| [Agent-RLVR (2025)](https://arxiv.org/abs/2506.11425) | 单元测试验证 trajectory、错误 guidance、RLVR，并训练 test-time reward model | “verified failure trajectory memory / guidance / RM”不新；且其底座 RL 不在本项目范围 |
| [Strained Coherence (2026)](https://arxiv.org/abs/2606.07889) | 用大模型 judge 读取完整 coding-agent trajectory，检测行动前已意识到的风险，并预测失败 | “pre-failure signal”表述已被占用；其 substrate 是 think trajectory、检测很晚，我们不能泛称首个 pre-failure detector |
| [Failure as a Process (2026)](https://arxiv.org/abs/2607.09510) | 1,794 条完整 CLI agent trajectories / 63k steps 的人工 failure onset、演化与恢复 taxonomy | 大规模 agent failure taxonomy 已有；我们的 691-node 机械 taxonomy 只能按 MLE search/source-opportunity 粒度定位 |
| [DHRCL (2026)](https://arxiv.org/abs/2607.26457) | 将 syntax、execution、unit-test、structure 组成分层 dense reward/curriculum，训练 Code LLM | “executability 是层级 reward”不新，且其目标是底座 RL；不能把两阶段 feasibility→quality 当作原语创新 |
| [Verifiable Process Rewards (2026)](https://arxiv.org/abs/2605.10325) | 用 symbolic/algorithmic oracle 构造 dense turn-level verifiable rewards，并分析 verifier reliability | “verified process supervision”大类已很拥挤；MLE 开放数据任务缺少 step oracle，正是我们不能直接套用它的原因 |

### Benchmark-level 补充

- [AgentRx (2026)](https://arxiv.org/abs/2602.02475) 已发布 115 条跨域失败 trajectory、critical-step 与 failure
  category 标注，并做自动诊断；“带 taxonomy 的 agent failure benchmark”不是空白。
- [StateMAS / MARS (2026)](https://arxiv.org/abs/2607.29055) 已发布 1,310 条可 replay 的 multi-agent failure
  trajectories，并用 diagnosis-guided MCTS repair；“failure dataset + MCTS repair”也不是我们的 novelty。
- [Detecting Silent Failures (2025)](https://arxiv.org/abs/2511.04032) 已构建 4,275/894 条 multi-agent
  trajectory benchmark 并比较 supervised/semi-supervised detector；不能用数据规模或 failure classifier 泛称首创。
- [AgentSearchBench (2026)](https://arxiv.org/abs/2604.22436) 已以近 10,000 个现实 agents 研究
  execution-grounded retrieval/reranking，并显示 description similarity 与真实 execution performance 有缺口；这也
  佐证我们 contract LOTO 的负结果应保留，而不是靠 semantic retrieval 叙事跳过 execution confirmation。

## 裁决

以下 novelty 表述关闭：

- 首个 code execution failure predictor / compilability discriminator；
- 首个用执行反馈改善 MCTS/code agent；
- 首个 coding-agent failure taxonomy 或 pre-failure signal；
- 首个 verified memory、process reward 或 feasibility→quality 分层。

当前可防守的正面边界是这些元素的**数据与估计组合**，不是单个方法原语：

1. 真实 MLE-agent 搜索树，而不是函数级编译、SWE issue 或 Terminal-Bench trajectory；
2. source opportunity → retained labeled fragment → missing identity → execution-censor status 的逐层可机读契约；
3. 同一 parent / physical run 内的 494 个 retained-success vs execution-failure 对，且 frozen run overlap=0；
4. 691-node credential-safe 机械 failure family 与完整撤回链；
5. 不更新底座 LLM，并诚实显示跨任务静态 TF-IDF 只有 0.524、不能泛化为可用 controller。

这最适合作为 NAS-Bench-style MLE search data/benchmark 的一章：现有 benchmark 只发布成功候选或 terminal
score 时，会把真实 choice set 变成 failure-censored fragment；我们的数据契约允许研究者明确选择 estimand。
它不是“我们已解决失败预测”。

## 下一步边界

- 可做：为 494 对增加不含原始代码的不可变 pair identity/hash registry 与独立 verifier；在 release card 中声明
  source access、安全过滤、缺失与 frozen 边界；把 length-only 0.5688 只列为未来新 cohort 假设。
- 暂不做：打开 frozen b0/b1/b2 追认 length signal；换模型/特征救 TF-IDF；启动 RL/底座微调；在无预算批准下
  做搜索 utility 长实验。
- 主线优先级不变：先等 score-channel 150-run gate 的 12 个新 physical runs，再按已批矩阵申请正式 replay。
