# Senior endpoint-score overlay：交付与边界

日期：2026-08-23。状态：`ENDPOINT_RECEIPT_OVERLAY_READY_EFFECT_ASSETS_PENDING`。GPU/API/model fit/future
truth=`0/0/0/false`。

## 为什么需要这一步

clean scaling v1 要求每条 pair 保留 better/worse endpoint scalar scores：只有这样才能验证同一 endpoint 在多个 pair
中的分数一致性，并在连通 comparison component 内做 top-1/regret/gain capture。原 clean-confirmation evaluator
只保存 margin，虽然足够算 pair accuracy，却不足以独立认证 utility。

## 只改 receipt，不改预测

新增 `0004-Emit-endpoint-score-receipts.patch`，必须在既有 0001/0002/0003 后应用。它把 evaluator 已经一次前向得到的
`(better_score,worse_score)` 保留，margin 仍由二者相减；写盘前检查数量、有限值与差值一致。没有改模型、tokenization、
checkpoint、batch、排序、标签、推理次数或 accuracy 定义。

patch SHA-256=`237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`。在精确 senior
`ac008af8b907d319b694f26b0ba9cf4053b3bf69` 的 fresh no-smudge worktree，四份 patch 顺序 apply-check/apply
通过；新文件 5/5，既定 8 个 confirmation 测试文件 36/36（46.79s），compile/shell/diff 检查通过。

整个 senior test 目录额外尝试在 collection 阶段因当前环境缺 `dojo` 和 `litellm` 停止，0 tests failed；该扩大尝试
不计为通过，也不影响已有 36 项相关验证。

## 边界

这只闭合 model-side receipt 缺口，不产生 scaling 结果。仍需 future cohort、dev-only checkpoint matrix、TF-IDF
同池分数、truth/bundle materialization 与一次性 ledgers；任何 GPU 仍须另报预算获批。

证据：

- `phase1/upstream_patches/0004-Emit-endpoint-score-receipts.patch`；
- `phase1/results/senior_endpoint_score_overlay_20260823_ac008af/`；
- `phase1/contracts/CRITIC_SCALING_CONFIRMATION_V1.md`。
