# Qwen execution-only smoke 裁决

日期：2026-08-14。原执行源码：`d89311a8bf49b787bcd8c712554d010b49131f5c`；独立重验源码：`a6e964b52ead98de0fdac49904f88308e5910eb1`。

## 裁决

状态为 **`VERIFIED_QWEN_EXECUTION_SMOKE_FAIL`**。冻结门要求两个任务都通过，实际为
`1/2`，因此 fresh-anchor E1-Q 不得启动。不得重试失败样本、换 prompt、换模型、延长
上限或删除失败任务。Qwen 生产路径仍由 passing-smoke receipt 强制 fail-close；当前
失败 receipt 不能用于准备实验。

这不是方法效果结论。该 smoke 只验证先前已生成的两个 Qwen 回复能否在真实
public-only 容器内形成合法提交；没有读取或报告任何外部分数、增益、D_search、D_val、
D_test 或 first-960/prospective outcome。

## 已执行事实

- Slurm 任务：2 个，均 `COMPLETED 0:0`；候选执行 2 次；API 调用 0 次；自动重试 0 次。
- 调度器分配时长合计 642 秒，即 0.17833333333333334 GPU·时；候选进程 wall time
  合计 416.31548192497576 秒，即 0.11564318942360438 GPU·时。
- `spaceship-titanic`：进程正常退出并写出 artifact，但预测值不可解析，submission
  shape gate 失败（`unparseable_prediction`）。
- `tabular-playground-series-may-2022`：submission shape gate 通过，159,998 行，列为
  `id,target`。
- 两个任务均为 public data read-only、private path 未挂载；D_search/D_val/D_test 读取数
  都为 0；`external_score_or_gain_reported=false`。

## 验证器修复边界

首次独立 verifier 错把进程命令放在 `candidate_process.json` 中查找，而真实 worker
把命令哈希锁在 `candidate_intent.json`；这导致 verifier 在形成 PASS/FAIL receipt 前
错误退出。修复只读取既有产物、补齐 intent/process/hash/shape 的独立重建，零 GPU、
零候选执行、零 API。修复后的 verifier 在 3 个测试通过后对原始产物重验，正式确认
上述失败；它没有改变任何候选代码、submission 或门槛。

## 关键哈希

- 独立 verification receipt：
  `ecb514030f827a46218dfc2fe5e466f5f9013e6b8e18e9d3bd07bd4897cbc54b`
- index 0 summary：
  `e9c137153099293ac7fa2a45bad3d642052114ef0289d0bf683f6baf8cdb0283`
- index 1 summary：
  `6981f5b56aea6b38e409a0df2a4229d8b8de6ddd60e7160fae4088de7ecda7c3`

远端原始根保持 append-only：
`/research/d7/spc/yzyang4/balanced-e1q-exec-smoke-d89311a-a2`。
