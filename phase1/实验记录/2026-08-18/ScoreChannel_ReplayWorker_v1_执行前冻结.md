# Score-channel replay worker v1：执行前冻结

状态：`IMPLEMENTED_NOT_AUTHORIZED`。本文件不批准 GPU 作业；正式运行仍需用户对窗口结束后的精确 replay
数、四 shard 矩阵和 GPU·时明确批准。

## 固定契约

1. 只接收 `score-channel-replay-candidate-v1` 的单 shard manifest，完整文件 SHA 必须显式匹配；每行 code
   SHA、task/run/parent、cap=120 与 shard=0..3 均 fail-closed 校验，credential-shaped code 拒绝。
2. 另需不可变 `score-channel-replay-approval-v1` 收据；它绑定 full manifest/summary、四个 shard SHA、精确
   replay 数、cap 上界 GPU·时、4×1 GPU、精确 worker commit、container size/mtime、grader SHA、data root、
   online-HF、API=0、底座更新=false 和用户批准时间。无收据不能执行。
3. 环境固定为 job 10533 同一 singularity、public task bind、online HF cache 与 pristine `mlebench
   grade-sample`；每 candidate fresh workspace，固定 120 秒，不扫 cap。
4. 只保存 parsed `stdout_val/val_how`、pristine `sub_score`、rc/含基础设施重试等待的总 wall、submission/log/grader output 的 bytes 与
   SHA。原始 code、stdout、stderr 和 grader 文本不进入结果；card 仅在进度日志中显示 SHA 前缀。
5. 每 shard 单进程 append-only + fsync，以 `(card_id,cap)` 恢复；既有行必须重新通过 manifest/approval/source
   commit 绑定和完整 schema 校验，extra/duplicate 行 fail-closed。
6. container instant-255 只允许一次固定 20 秒后的基础设施重试；其他失败按结果保留，不挑样重跑。
7. worker 不打开 label vault、不计算效果、不提交作业；分析器与独立 verifier 必须在任何 replay outcome 可见前
   另行冻结。

## 资源与停止条件

- 当前实现/测试：CPU-only，GPU=0，API=0，底座更新=0。
- 正式预算：由 post-monitor replay summary 给出，不使用 690 的心算近似代替。
- 任一 manifest、approval、code、source commit、数据/container/grader 路径或已有 checkpoint 不匹配即停止。
