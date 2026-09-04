# G0 job 12377：终态、成本与单一恢复改动

日期：2026-09-05。状态：失败证据已读取；恢复代码待 0-GPU 验证；未授权再次提交。

## 1. 实际终态

Slurm accounting 的 exact row 为：job `12377`，state `FAILED`，exit `1:0`，start
`2026-09-05T02:26:33`，end `2026-09-05T02:28:44`，elapsed `131` 秒，allocated
`gres/gpu=2`。因此本次实际占用为 262 GPU-seconds；加前次已确认 320 GPU-seconds，
累计已分配为 582 GPU-seconds（0.16166666666666665 GPU-hours）。不能按 117 分钟上限计作训练成本。

submission root 中 `slurm-12377.out` 为 0 字节；run root 明确含 `FAILED` 和
`training_exit_status=1`，没有 output、checkpoint、verification、SHA256SUMS 或 COMPLETE。
run archive SHA-256 为
`ab4059d8c892f649222079bf256f7664086cd8701c0d3c53c65b43a3354bc1d5`；submission archive
SHA-256 为 `1a2f524597f13460c3b5431ad18678751b6d91287aef6ca2d04d75c5aefffc9b`。
两份下载后 credential-shape scan 均无命中。

## 2. 根因，不是 GPU/显存结论

preflight 通过并进入 launcher；随后仅 0.02 秒即退出。唯一训练期错误是：
`experiment_env_augmented_data.sh` 在 launcher 顶部被 source，先使用默认路径
`$REPO_ROOT/outputs/augmented_mle_critic` 执行 `mkdir -p`；而 source root 为保证提交时 Git clean 已设只读，
所以 permission denied。首条 telemetry 记录一张 RTX PRO 6000、memory used 0、utilization 0；它不证明
第二张卡缺失，因为 worker 在第一次 5 秒采样完成前已经失败。

因此不能称双卡训练、模型加载、DeepSpeed/NCCL、显存或十步耗时已验证。故障是 launcher 共享环境的
默认输出副作用与只读源码契约冲突。

## 3. 单一恢复改动

只在控制侧 `critic_component_g0_worker_20260821.sh` 中，在调用原 launcher 前设置：

- `MLE_CRITIC_OUTPUT_DIR=$G0_RUN_ROOT/shared-env-output`；
- `MLE_CRITIC_LOG_DIR=$G0_RUN_ROOT/shared-env-logs`；
- 两路径必须事前不存在。

原 `CONFIRM_OUTPUT_DIR=$G0_RUN_ROOT/output`、数据/模型/SHA、双卡、batch、16384 context、seed 6、十步、
cosine、LR、source commit 和 final-only 逻辑都不改。学长 launcher 与 source checkout 不改且继续只读。

## 4. 验证与下一授权边界

先在真实只读 source 上执行 0-GPU smoke：source 原共享环境脚本，但注入上述外部目录；要求只有外部
shared-env-output 被创建，正式 output 仍不存在，source Git 前后 clean/commit/hash 不变。另以源码测试绑定
两 export 位于真实 launcher 调用前。随后用同一原 launcher、真实 train/dev/cards 哈希及固定双进程/16K/十步
参数做 fake-accelerate dry-run：只记录最终 argv，不导入训练代码或模型。两层任一失败都不申请重试。

即使 smoke 通过，也只解决已观察到的第一个故障，不证明后续模型路径。任何新 GPU job 都须以一个全新
submission/result root、不可重试 latch、相同两卡最多 117 分钟说明并重新取得明确授权；本报告本身不提交。
