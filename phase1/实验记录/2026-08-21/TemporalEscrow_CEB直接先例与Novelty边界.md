# Temporal escrow：CEB 直接先例与 novelty 边界

日期：2026-08-21。作用域：一手文献核查与主张纠偏；prospective outcome read=0，GPU/API/model fit=0。
本记录不改变已激活的 transition future escrow，也不授权新增 arm、metric 或提前揭盲。

## 1. 必须承认的直接碰撞

[Critic Experience Bank（CEB）](https://arxiv.org/abs/2607.12397) 已经明确形式化并实验了以下组合：

- critic 在 action 执行前输出 step-level confidence；
- critic 权重冻结，用先前轨迹的执行反馈作为检索记忆；
- 轨迹按 stream order 处理，且必须等整条轨迹的 actions 全部评分后才把该轨迹加入 bank，论文明确说明这样
  “no future feedback leaks into an online estimate”；
- 在 Mind2Web、AMEX、InterCode-Bash 上报告 ECE/Brier/AUC，并做 replay-based selective execution 与有限
  human-review budget utility；
- Mind2Web 的累计学习曲线对 5 个 random stream orders 取均值和标准差。

因此以下宽主张全部关闭：首次让 agent critic 在执行前预测、首次按流式顺序阻断未来反馈、首次冻结 critic 并从
历史执行经验改善判断、首次做 confidence-based selective execution。此前只把 CEB 当“经验 critic”引用不够，
正文必须在 temporal protocol 段正面比较它。

## 2. 我方仍可核验的窄差异

| 维度 | CEB | 当前 transition future escrow |
| --- | --- | --- |
| 决策单位 | GUI/web/shell trajectory 中的单步 action productivity | MLE program-search physical run 内自然 same-parent siblings 的连续外部分数次序 |
| 数据时间 | 已收集 frozen actions 上的 stream replay；增长曲线平均 5 个随机 stream orders | activation 后才开始生成的 physical runs，按远端 `generation_started_at_utc` 严格入组 |
| 适应机制 | bank 随已完成轨迹增长，critic context 在线变化 | scorer、features、fit rows 和参数在 activation 前全部冻结，future predictions append-only |
| 标签 | reference/reward 或 hindsight LLM pseudo-label；held-out labels 用于评测 | pristine evaluator continuous score；prediction 先托管，outcome vault 后揭 |
| 完整性门 | 论文级 stream-order 无未来反馈 | endpoint/run/code closure、parent coverage、source novelty、真实时间 receipt、syscall 禁读与独立 verifier |
| 贡献类型 | 在线经验 critic 方法与校准/选择性执行效果 | MLE decision benchmark 的严格时间外验证契约；效果仍未知 |

这张表只说明两个 estimand/protocol 不等价，不证明我方 first/only。特别是，“temporal split”“prediction before
outcome”“frozen critic”本身都不是 novelty。可写价值只能是这些约束在自然 MLE sibling、continuous pristine
score、source/failure registry 与真实生成时间上的联合实例化和可审计 release contract。

## 3. 其他直接 benchmark 的边界

- [AgentRewardBench](https://arxiv.org/abs/2504.08942) 收集 1,302 条 web trajectories，并按 51/300 tasks 划
  dev/test；这是 task holdout，不是数据生成后才入组的 temporal escrow。
- [Plan-RewardBench](https://arxiv.org/abs/2604.08178) 用自然 rollout、规则扰动和 minimal-edit negatives 构造
  trajectory preference pairs，并隔离 generator/judge；它不是自然同-parent MLE sibling 的 strict-future cohort。
- [AIRA\_2](https://arxiv.org/abs/2603.26499) 的 HCE 已覆盖固定 train/search/validation 分离、隐藏标签和外部
  evaluator；所以“外部隐藏评估”同样不是我方 novelty。我方 temporal escrow 只能作为 HCE 之外的 predictor
  validation hygiene，而不能冒充新的隐藏验证思想。
- M-DESIGN、Guided Evolution、ReLoc 已分别关闭 edit-effect predictor、predictor-guided mutation 和 revision RM
  的方法首创空间；即使 future transition arm 为正，也只是新的 MLE deployment-domain evidence。

在本次检查的一手工作中没有找到与“真实 generation-time activation + same-parent MLE programs + continuous
pristine score + prediction escrow + source/run/code closure”完全相同的报告；这只是检索边界，绝不是不存在证明，
正文仍不得写 first/only。

## 4. 对当前路线的裁决

1. transition future escrow 保留，因为它仍是把 0CN 的 retrospective near-threshold candidate 变成可信
   out-of-time test 的唯一合法出口；其价值是证据强度，不是 temporal 方法新颖性。
2. 未来若 positive，标题/摘要不能以“novel temporal critic protocol”为主；应写成 Predictor Benchmark 的
   prospectively escrowed validation，并把 CEB 列为最近的 no-future-feedback prior。
3. 不引入 CEB memory arm：当前 future scorer 已激活，结果前扩 arm 会破坏契约；若日后研究经验记忆，必须用
   activation 之后的新 cohort、单独预注册和用户批准的 API/GPU 预算。
4. 当前主线继续等 strict-future runs；在此期间只做 outcome-blind intake、closure 和已有资产的独立压力测试。
