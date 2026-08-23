# Critic confidence--cost：防 scoop 与二级扩展冻结

日期：2026-08-23。状态：`ANALYZER_READY_EFFECT_ASSETS_PENDING`。本轮只做一手 related-work 审计、机器预注册、
合成正负控和独立 verifier；真实 future truth/GPU/API/model fit=`false/0/0/0`，没有产生新的模型效果。

## 1. 防 scoop 裁决

以下一手工作关闭了宽方法主张：

- [CAMEL](https://arxiv.org/abs/2602.20670) 已证明 verdict-token log-probability margin 与 preference 判断正确率相关，并在
  低置信样本上选择性调用更贵的 reflection；“首次对 reward-model 判断做 confidence gating/accuracy--cost
  Pareto”关闭。
- [Calibrated Preference Learning](https://arxiv.org/abs/2605.30447) 已正式区分 label-ranking 的多种 calibration，并在
  RLHF reward models 上发现 calibration 与 benchmark accuracy 强相关但不等价；“首次把 RM calibration 作为超越
  top-1 的指标”关闭。
- [Scaling Laws for Generative Reward Models](https://openreview.net/forum?id=VYLwMvhdXI) 已系统覆盖 Qwen3
  `0.6B--14B` 的 reward-model scale，并发现静态 evaluator gain 不必转化为 downstream rewarder gain；通用
  “RM scaling/规模越大越好”不是 novelty。
- [When In-Distribution Gains Fail](https://arxiv.org/abs/2605.25629) 已把 source-domain fine-tuning 的表示漂移作为
  preference transfer 失败机制，并提出 representation anchoring；若未来 global→local 使用 anchoring，它只能作
  baseline/工程改进，不能作我方方法首创。
- [Pairwise Calibrated Rewards](https://arxiv.org/abs/2506.06298) 已直接研究 pairwise reward calibration，但目标是用
  reward-function 分布表示 annotator pluralism；它不等于我方 deterministic pristine execution outcome，却进一步
  要求我们不能泛称“首次 calibrated pairwise rewards”。

因此本扩展的可守边界只有 **MLE-agent benchmark/deployment estimand**：在 exact physical sibling、pristine
execution grade、query/init/execution 分账和 task-cluster inference 下，容量 gain 是否先出现在 proper scores，以及
confidence 是否能转化为“执行一个或两个候选”的真实执行次数--regret 曲线。不申 calibration、abstention、RM scaling
或 gating 方法 novelty，也不写 `first/only`。

## 2. 结果前冻结内容

机器契约 `critic-scaling-confidence-cost-extension-v1` 的 SHA-256 为
`00ba64a222ae793c3f5d196ee754f0af9e2f01986ad85ed78c11b6f570da665b`，逐字节绑定 primary contract
`579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568`。它不修改 primary accuracy/baseline/
component gates；secondary PASS 永远不能 rescue primary FAIL。

扩展要求 test access 前锁定独立 dev truth 和同一 9 个 predictor 的 endpoint scores；dev/test endpoint、physical run、
unordered pair 三种 overlap 均为零。温度只在 dev 上拟合：median-|margin| 归一化、无截距反对称 scalar beta、固定
`[0,100]` 与 100 次导数二分；test 不参与温度、coverage、checkpoint 或阈值选择。

proper-score primary 为 task-macro log loss 与 Brier；二者都要求规模均值单调不升、两个 seed 的 8B−0.6B 均为负，
且 task-bootstrap CI 上界小于零。TF-IDF 是独立更强门，不能替换 capacity 门。

selective target 在结果前固定为 50%，同时完整报告 25/50/75/100%。每 task 内按绝对 calibrated logit 选高置信 pair；
accepted 只执行一个 endpoint，deferred 执行两个。实际 execution saving 从 realized coverage 计算；grade-gap regret 先在
task 内归一化。正门要求 8B 两 seed 的 half-coverage accepted error 都低于 full pool，task-bootstrap CI 上界小于零，
且相对同 coverage 随机接收的 excess gap-regret CI 上界也小于零。失败后禁止改用 25%/75% 救结果。

## 3. 当前验证与严格边界

producer：`phase1/critic_scaling_confidence_cost_extension.py`；独立 verifier：
`phase1/verify_critic_scaling_confidence_cost_extension.py`，后者不 import producer，而从 primary source bundle 与 dev
lock 重建温度、逐 pair scores、task/coverage metrics、bootstrap、gates 和两个 CSV。

扩展聚焦合成测试 7/7；与 primary analyzer/materializer 联合为 32/32。覆盖：强正控、primary 不成立但 secondary 为正
时禁止 rescue、dev/test endpoint overlap、晚锁、错 checkpoint、缺矩阵、两种 `PYTHONHASHSEED` 逐字节一致，以及
篡改 summary 后同步更新 artifact manifest 仍被 source reconstruction 拒绝。本地尚未把 32/32 冒充完整 suite；完整
fresh-checkout 集群回归与凭据扫描在 commit 后另记 receipt。

当前没有 real dev/test bundle、checkpoint manifest 或 one-shot ledgers，故正式效果状态仍是
`ANALYZER_READY_EFFECT_ASSETS_PENDING`。它不授权训练，也不改变 score-channel future cohort 或 clean scaling 主实验。
