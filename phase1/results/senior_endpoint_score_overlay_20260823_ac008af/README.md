# Senior one-shot endpoint-score overlay 验收

状态：`ENDPOINT_RECEIPT_OVERLAY_READY_EFFECT_ASSETS_PENDING`。本结果只验收 model-side 交付接口，不含模型效果。

## 身份与用途

- upstream base：`ac008af8b907d319b694f26b0ba9cf4053b3bf69`；
- 前三份 clean-confirmation patches 保持原 SHA；
- 新 patch：`0004-Emit-endpoint-score-receipts.patch`，SHA-256=
  `237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`；
- worktree：`/research/d7/spc/yzyang4/worktrees/ac008af_endpoint_overlay_20260823`；
- log：`/research/d7/spc/yzyang4/prospective_decision_v1/endpoint_overlay_ac008af_verify.log`。

第 4 份 patch 不重算或改变预测，只让 evaluator 返回已经得到的 `(better_score, worse_score)`，从同一 tuple 计算
margin，并在写 receipt 前检查有限值、长度和 `margin=better−worse`。这样下游才能验证共享 endpoint 分数一致性并
计算 comparison-component utility；旧 test-touched checkpoint 仍禁止使用。

## 验证

- 四份 patch 顺序 `git apply --check` 与 apply 均通过；
- 新 one-shot 文件 5/5；既定 8 个 confirmation 相关文件 36/36（46.79s）；
- Python compile、launcher shell syntax、`git diff --check` 通过；
- 扩大到整个 senior test 目录时，collection 被环境缺失 `dojo`/`litellm` 阻断；这是无关依赖失败，不记作通过，
  也没有测试失败；
- GPU/API/model fit/future truth：`0/0/0/false`。

当前仍缺新的 dev-only checkpoints、truth/prediction bundle 与 one-shot ledgers，不能运行效果分析或提交 GPU。
