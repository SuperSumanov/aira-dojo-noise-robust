# Probe-First Artifact Contract A/B V2：恢复预检与启动

日期：2026-08-19  
当前状态：`RUNNING_FROZEN_PROBE_AB_REPLAY_NO_OUTCOME_READ`

## 1. 恢复边界

原 V2 generation job 10686 已在 2026-08-13 完成 16/16 entries，Slurm 为 `COMPLETED 0:0`、elapsed
`01:36:22`、4×RTX3090。旧 detached watcher 只记录到运行 1:15，随后消失；generation 自身继续完成并写出
16 status、16 stdout、16 stderr 与 generation manifest，但 replay manifest、replay、primary result 和
independent result 均不存在。因此本次只允许恢复 frozen replay，不重新调用 API、不重新生成候选、不替换
静态失败的 contract arm。

冻结科学 commit=`a013eaa124a17c183e58f28494d4908f96389941`。旧工作树已有后续未提交修改，故没有清理或覆盖它；另建 clean
detached worktree `/research/d7/spc/yzyang4/worktrees/probe_ab_resume_a013eaa`，并逐项核对原 prereg 记录的
worker/builder/extractor/validator/prompt SHA。

## 2. 结果盲恢复预检

- Linux 原环境聚焦测试：12 passed；
- primary validator self-test：PASS；
- schema worker self-test：PASS；
- independent verifier self-test：PASS；
- generation job/status/stdout/stderr：1 job + 16/16 + 16/16 + 16/16；
- generation manifest 双重重建并与原文件逐字节一致，SHA=
  `096afbf6b1ca5779c7adf6dafea69a6e9ba431697c79245398d2a6a0d8babfe1`；
- 首次 replay 双建改变了嵌入的 generation-manifest **路径**，因此正确停止；固定同一个原始 input path 后，
  两份 replay manifest 逐字节一致，16 rows，SHA=
  `83b57794db2f7205801db217b260175736d108d7cb92d1c29a3bc6dd8d42e3fb`；
- 16/16 leaf Python AST 可解析；contract static gate=7/8，未通过者保留在分母；
- prereg/resume 文件名 secret count=0、内容 secret count=0；
- 本恢复 API=0、底座更新=0，candidate 不见 grader/private labels。

本地 Windows worker self-test 曾因临时目录 copy 返回 `PermissionError` 失败；相同冻结 SHA 在目标 Linux 环境
PASS。因此它记录为跨平台测试限制，不作为科学结果或远端阻塞。

## 3. 调度修正与精确预算

原 replay 脚本为 `--array=0-15%4`。2026-08-19 的 Slurm `test-only` 将 array 的 16 个元素计入
QOS submit limit，返回 `QOSMaxSubmitJobPerUserLimit`；编号 11156--11159 是后续四个 shard 的 test-only receipt，
均不是 GPU job。失败时实际提交 job=0、replay index=0、outcome=0。

科学矩阵不变，只把 scheduler topology 改为四个 job，每个顺序执行四个 index：

| shard/job | frozen indices | GPU | TimeLimit |
|---|---|---:|---:|
| 0 / 11160 | 0, 4, 8, 12 | 1×RTX3090 | 01:20:00 |
| 1 / 11161 | 1, 5, 9, 13 | 1×RTX3090 | 01:20:00 |
| 2 / 11162 | 2, 6, 10, 14 | 1×RTX3090 | 01:20:00 |
| 3 / 11163 | 3, 7, 11, 15 | 1×RTX3090 | 01:20:00 |

replay hard cap=19,200 GPU 秒=`5.333333333333` GPU·h；generation 实际 allocation=23,128 GPU 秒=
`6.424444444444` GPU·h；合计 42,328 秒=`11.757777777778` GPU·h，较原批准 12 GPU·h 留 872 秒。
candidate replay 仍是 16×600 秒，上限 `2.666666666667` GPU·h。没有新增 API 调用。

四个实际 jobs 已在 gpu27 启动，detached watcher 只在四 job 全部 `COMPLETED 0:0`、16 index 完整、commit/
manifest SHA 不变后运行冻结 primary validator 和不导入主实现的 independent verifier。任一失败均写 INVALID，
不自动重提、不扩预算、不补任务。
