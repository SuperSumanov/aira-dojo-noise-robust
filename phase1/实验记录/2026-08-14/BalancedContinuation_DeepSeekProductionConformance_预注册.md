# Balanced Continuation：DeepSeek production-matched operator 合规门（预注册）

日期：2026-08-14。状态：结果前冻结。性质：**恰好 2 次 API、零 GPU、零候选执行的兼容性审计**。

## 为什么必须另立本门

先前的 `PASS_OPERATOR_ONLY_GATE` 使用 `qwen3-coder-flash`；冻结 E1 的真实 operator contract 使用
`deepseek-v4-flash`、temperature=0.6、top_p=0.95。Qwen 的成功只能证明 strict complete-script prompt
存在一个可用实现，不能证明原 production model 已兼容。若直接把 Qwen probe 写成 production repair，
会把“修 prompt”与“换模型”混在一起。

本门不比较两个模型的质量，也不据结果选择最好模型。它只问：在完全匹配原 production model/request
参数的条件下，strict prompt 是否能在两个结构冻结样本上返回可执行前结构合规的完整 replacement script。

## 冻结矩阵

- 样本：沿用 Qwen probe 在 outcome-blind 结构规则下选定的两个 warm artifacts；每任务按 rollout ID
  字典序取第一个 `execution_status=ok` 且有 immutable submission 的 warm rollout；
- model/base URL/temperature/top_p/max output：必须从 production operator 模块导入并逐项断言为
  `deepseek-v4-flash` / endpoint hash / `0.6` / `0.95` / `8192`；
- messages role=`system`，与 production caller 一致；content 非空时取 content，否则取
  `reasoning_content`，与 production caller 一致；
- 2 tasks × 1 request = **2 calls**；SDK retries=0、semantic retries=0；
- GPU jobs=0、candidate executions=0、D_search/D_val/D_test/first-960 reads=0；
- raw response 与 intent 只保存在远端 mode 0600 目录，Git 只进 compact summary。

## 通过门与停止门

每条响应必须同时：`finish_reason=stop`、usage 完整、completion tokens 不等于 8192、且通过既有
single-complete-script gate（恰好一个 Python block、AST 可编译、无 Ellipsis、长度与行数下界、完整 I/O
markers）。两任务 2/2 才是 `PASS_PRODUCTION_MODEL_OPERATOR_GATE`。

任一失败即 `FAIL_PRODUCTION_MODEL_OPERATOR_GATE`；本协议内不重试、不改 prompt、不增 token、不换模型。
无论通过或失败，`method_claim_allowed=false`、`new_gpu_budget_still_required=true`、`e2_e3_unlocked=false`。
若 DeepSeek 失败而未来改用 Qwen，必须把它作为新的 operator contract 和新实验，而不是修复后追认旧 E1。

## 13 项预检映射

1. 旋钮由 summary 记录并与 production 常量逐项绑定；2. synthetic caller 与 exactly-two-call 测试先过；
3. 无训练/测试集，样本规则固定；4. 逐任务 2/2，不报 pooled 均值；5. 两任务同参数；6. raw/intent mode 0600；
7. prompt 只含 public description、旧 code、terminal，凭据形状 fail closed；8. 无 shuffle，API 非确定且不重试；
9. key 仅由远端 mode-600 `.env` 注入，push 双扫；10. production-matched client timeout=180 秒，
总墙钟 cap 8 分钟；
11. 这是工程门，不作功效推断；12. launcher/worker rc 单独原子记录；13. 使用既有结构冻结样本，未来语料不改本门。
