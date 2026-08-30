# Outcome-Blind 887 v5 续接预注册

日期：2026-08-30
状态：`FROZEN_BEFORE_V5_RESTART`

## 1. 触发原因

2026-08-30 的纯结构复核发现，连续 intake 的 PID 已退出，2026-08-29 v4 guard 留下 `FAILED_RC=1`。这不是
snapshot、sidecar 或科学结果故障：旧 intake 日志最后一行精确为正常完成 145 个 poll 且
`outcomes_read=false`；v4 guard 的最后一行停在 poll 71，仍为 baseline
`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`，transition、receipt、config、
Target-300、WL 与 task-balance 均为 healthy。下一轮 guard 检查已自然退出的 intake PID 时才以 RC=1 终止。

复核时 `LATEST` 仍为 887，config-v2 sidecar 文件名计数为 0，Target-522 selection/candidate/READY/COMPLETE/
FAILED 均未出现；四个 Target-522 结构 monitor 仍持锁运行。旧 transition、receipt、WL、config-v8 与 Target-300
均按固定 baseline 正常到时退出、锁已释放。前瞻 label、outcome、prediction value、accuracy 与 utility 均未读取。

## 2. 唯一允许的 v5 续接

本次只恢复既有冻结协议的元数据覆盖，不改变 cohort、scorer、门或 estimand：

1. 先绑定旧 intake 正常完成、旧 guard RC1/poll71、固定 baseline、无 sidecar/候选、旧 PID 已死与锁已释放；
2. 以原 `bc362dfe...` control 和 `90842c49...` scientific commit 重启 credential-first append-only intake；
3. 在原 state root 上续接 transition、prediction receipt、WL、Target-300 identity monitor，并新建 config-v2 v9
   文件名探针；所有脚本及三个 state 文件均绑定精确 SHA-256；
4. 只有五条支持链都写出新的 start 行、PID live、锁 held 后，才启动 2026-08-30 v5 六小时 guard；
5. guard 只读取 PID、只读锁、`LATEST`、marker 名、文件名计数、哈希和明确带
   `outcomes_read=false` 的结构汇总。若出现唯一 successor，只写 identity handoff；若发现 config-v2，只写元数据并停在
   redaction/review 前；任何重复、哈希漂移、异常 marker 或进程失败均 fail-closed。

固定资源为 CPU metadata polling 与既有固定 CPU scorer；GPU/API/model-fit/base-update=`0/0/0/0`。intake 保留
145×300 秒，transition/receipt/WL/config 为 72×300 秒，Target-300 保留原 144×300 秒，guard 为 72 个 300 秒间隔。

## 3. 冻结实现

- `phase1/scripts/renew_outcome_blind_monitors_887_20260830_v5.sh`
- `phase1/scripts/guard_outcome_blind_continuity_887_20260830_v5.sh`
- `phase1/tests/test_outcome_blind_monitor_renewal_20260830.py`

每个脚本内置 13 项 preflight，执行时必须从公开 exact commit 自校验。部署前须通过 Bash syntax、focused test、
完整 `phase1/tests`、credential filename/blob scan；部署后须留下子进程首轮、锁、命令、manifest 和
`prospective_values_read=false` 回执。任何失败不得覆盖旧 root，只能保留证据后另立版本。
