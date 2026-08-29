# Outcome-Blind Continuity：只读锁故障与 Supervisor v2 修复

日期：2026-08-29
状态：`ENGINEERING_FAILURE_IDENTIFIED_BEFORE_CHILD_LAUNCH_FIX_FROZEN`

## 现象与边界

guard v3 于 `2026-08-29T05:37:17Z` 正常完成；其 READY/COMPLETE 存在、FAILED/CONTINUITY_GAP/TIMEOUT
均不存在，最后一轮明确 `outcomes_read=false`。原 supervisor v1 在下一轮 `2026-08-29T05:37:46Z` 以 RC=`65`
fail-closed；`six-hour-structural-guard-20260829-v4` 根目录完全不存在，故没有重复 child、部分启动或科学 readout。
此时 `LATEST` 仍为固定 887，config-v2 sidecar filename count 为 0；intake、Target-522 selection、TaskBalance 及四个
support monitors 仍 live。

## 根因复验

guard v3 完成时执行 `chmod -R a-w`，因此 `guard.lock` 也变为只读。v1 用
`flock -n PATH -c true` 重新以可写方式打开该路径；真实复验返回 `Permission denied` 和 RC=`65`，恰与 supervisor
失败码一致。它不是“锁仍被占用”。对同一 inode 以只读 FD 打开并尝试 nonblocking shared flock 后返回 free；对四个仍 live、
由 monitor 持有 exclusive flock 的锁，同一 shared probe 均返回 held。因而根因是 path-open permission artifact，不是 PID
复用、重复 monitor 或 snapshot 漂移。

## 修复

- guard v4、renewal v4 与新 supervisor v2 统一使用 `lock_is_free()`：只读打开 lock inode，再用 nonblocking shared flock；
  monitor 的 exclusive lock 存在时 shared probe 必然失败，完成且释放时成功，同时不要求 lock 文件可写。
- supervisor v2 绑定旧 v1 source SHA=`8febae8e...337e9`、缓存 guard source SHA=`7c67778b...48a12`、
  `FAILED_RC=65`、最后 baseline status、旧 guard manifest、dead PID、free read-only lock，随后才允许启动修正后的 guard v4。
- renewal 对四个自然完成的 support roots 也用同一 probe，避免下一阶段重复触发权限假失败；新启动 child 仍必须表现为
  exclusive lock held。
- 静态测试明确禁止恢复旧的 `flock -n PATH -c true` 监视模式；真实远端 free/held 两类 inode 已分别复验。

## 科学与安全结论

这是监控编排修复，不是数据或方法结果；不改变 cohort、scorer、WL、Target-522 protocol 或任何停止门。prospective
label/outcome/prediction/accuracy/utility 与 sidecar 内容均未读；GPU/API/model-fit/base-update=`0/0/0/0`。修复必须经公开
commit、post-push tests 与 exact-source deployment 后才可上线。
