# Clean critic scaling：独立确认契约与 checkpoint 版本纠正

日期：2026-08-23。结果状态：`CONTRACT_READY_ASSETS_PENDING`。GPU/API/model fit/future score-channel truth=
`0/0/0/false`。

## 1. 先纠正一处版本边界

`greater_is_better=false` 的 checkpoint 方向 bug 是历史事实，但不是学长当前分支的仍存 bug。Git history 显示
`d44f4b0347154417ee5adc7a3b5b59ddd22ccb2c`（2026-08-20）已把
`metric_for_best_model=eval_pair_accuracy` 对应的方向修为 `true`；最新审计的
`ac008af8b907d319b694f26b0ba9cf4053b3bf69` 仍为 `true`。更早 0813/0814 报告描述的是当时 commit，保留作
历史，不得再写“最新代码尚需修方向”。

当前真实阻断是：旧 outer test 每 10 steps 被当作 eval、缺独立 dev-only one-shot test 链、部分历史训练未完整结束，
且没有逐 pair predictions/checkpoint manifests 可做 task/run/component 聚类复核。因此探索性 scaling 信号仍有价值，
但不能追认为 frozen confirmation。

## 2. 本次完成的正向工程

冻结 `critic-scaling-confirmation-contract-v1`：Qwen3-Base 0.6/1.7/4/8B × seeds 6/7，同池 train-only
char-TFIDF，primary canonical sibling，10,000 次 task bootstrap。容量 scaling、8B 超基线与 component utility
conversion 分三层独立裁决；支持门固定为至少 20 tasks/300 components、最大任务 share≤0.20。

实现 fail-closed producer 与不 import producer 的 verifier。它们要求 test 前 lock、完整训练与 dev-only checkpoint
选择、8 个 checkpoint 精确 matrix、一次性 ledger、逐 pair endpoint scores、连通 comparison component、全 predictor
同池；验证 task/run CI、两 seed、LOTO 与 component gain。旧 test-touched checkpoint 被 schema 明确禁止。

合成正控、负控与攻击测试覆盖：强 scaling 三层全过、有效负结果、margin 篡改、第二次 test attempt、缺失 matrix、
cross-run primary、不同 `PYTHONHASHSEED` 字节一致、独立 verifier 重建与 summary 篡改拒绝。当前聚焦测试为 7/7；
远端 exact-commit 全套验证仍须在提交后完成。

## 3. 科学边界与下一步

这份契约不是新结果，也不授权训练。它把当前最强的正向资产——学长的 experiment-internal value scaling——变成
下一轮可以一次性独立认证的接口。只有学长后续保留新 checkpoint manifests、逐 pair predictions 和 one-shot ledger，
并先形成新的 run-clean frozen cohort，才可申请 GPU 预算并运行。

直接证据：

- `phase1/critic_scaling_confirmation_contract_v1.json`；
- `phase1/contracts/CRITIC_SCALING_CONFIRMATION_V1.md`；
- `phase1/critic_scaling_confirmation_analysis.py`；
- `phase1/verify_critic_scaling_confirmation_analysis.py`；
- `phase1/tests/test_critic_scaling_confirmation_analysis.py`。
