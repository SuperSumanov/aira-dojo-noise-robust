# Prospective 原子评分与 score registry：0812 影子复放

日期：2026-08-14。协议：`prospective_drop_scoring_v1`。冻结代码 commit：
`4b12c8f80abee4fafcacf8bc8268f9344ead7b61`。

## 裁决

正式工程状态为 **`PROSPECTIVE_SCORE_PIPELINE_SHADOW_PASS`**。

- 远端 `exp` venv 的 33 项相关测试全部通过；其中 synthetic 非空测试实际加载冻结 bundle，对两个未来端点完成
  static LR 与 char-TFIDF LR 推理，并逐 endpoint 复核 score CSV 与 intake manifest 的身份。
- 最终 commit 上重新生成的 0812 intake 仍是 57 个 checkpoint physical runs、3 个 live-only、1,304 个端点、
  286 个结构 sibling pairs；全部早于激活，eligible=0。
- 单批事务因此诚实返回 `NO_ELIGIBLE_ENDPOINTS`，没有制造空 prediction 文件；跨批 validator 返回
  `PROSPECTIVE_SCORE_REGISTRY_VERIFIED`，登记 10 个 source archives 与 57 个 physical runs。
- `strace -f -e trace=file` 分别包围 score-drop 与 registry validator；两份 trace 中
  `label_vault.jsonl` 的文件系统调用计数均为 0。summary 也记录 `label_vault_opened=false`、outcome 列表为空。

这只证明新批次到达后可在不知道 outcome 的条件下自动收样、固定评分并登记，不是 critic 效果结果。

## 关键哈希

- 最终 intake summary：`209bb4e9d352e081b88d91bb477ebb88068636b343b3bdf09815498781bd40e6`
- score transaction summary：`237313bc7a9a015b0dcfcbda1c70546d4572024b3a04cd2d9a3f1fe407f5ff5f`
- append-only score registry：`37bb6bf4e7cb42e67101e1d3358f77e1b1bed4914b068a78debf0822c70f8ac0`
- registry validation summary：`4a74e0fb6ad85a39581d4d62e4cad4ca3ca7ec5772b565eab7ebf84558049722`
- score index：`a4aa12e8b224a144f0d22b3ba8c5664c03c93fd168661f7182e1a1473afc1152`

## 失败链与归档边界

第一次远端预检误用有 sklearn 但没有 pytest 的 `critic` venv，在测试收集前退出；它发生在 intake/scoring 前，
没有正式产物。`preflight_failure.txt` 原样保留。成功重跑使用同时具备 pytest 与 sklearn 的 `exp` venv，完整日志为
`run.txt`。

本目录只复制 summary、hash registry/index 与日志。没有复制 intake 的 `label_vault.jsonl`、端点代码、结构 pair
明细或 strace 全量路径日志；完整封存产物仍留在远端实验根。
