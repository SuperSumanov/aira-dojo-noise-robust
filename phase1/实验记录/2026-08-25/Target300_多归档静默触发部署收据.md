# target-300 多归档静默触发 monitor 部署收据

日期：2026-08-25

状态：`QUIESCENT_MONITOR_RUNNING`

effect/truth/GPU/API：`未打开/未打开/0/0`

## 1. 为什么更换 trigger

ancestor-safe immediate monitor 会在同一批多个 archives 到达时被第一个新 snapshot 立即触发；formal runner 的完整回归
约需一段时间，可能先封出中间 receipt，而剩余 archives 随后才被摄取。它不篡改 target-300 closure，但会制造无必要的
中间 formal 和计算抖动。

因此在 immediate monitor 尚未看到新 snapshot、尚未触发 formal runner 时主动停止，并改成固定静默门：snapshot
必须连续 5 次、每次间隔 300 秒完全相同，才对这一稳定 snapshot 运行一次 target formal。不是按结果停止，也不改变
300 identity target、boundary-archive overshoot、one-time closure anchor 或任何 eligibility 规则。

## 2. 交接收据

被停止的 immediate monitor PID=`1985359`；停止目录：
`/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_ab59a01_immediate_stopped_for_quiescence_v1`。
其 `SHA256SUMS` 自身 SHA-256=
`af128285744799ac5043c6926e6272e99f0d287f7aab462247953303af98c4f6`；记录明确为 f109 no-change、formal 未启动、
outcome/effect 未读/未算。

新 monitor root：
`/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_6794f8a_quiescent_v1`；PID=`1986763`。绑定：

- exact science commit：`ab59a011d945e4a96daf7dbbbc927a59027da077`；
- deploy 时 release head：`6794f8a9ad344a20ce0a54bc8b0fb6fa73257397`；
- runner SHA-256：`c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e`；
- monitor SHA-256：`790bcb5a6d6314e276c30dbc52681219ebd087c6ff11fc1a02e71230f894612f`；
- stable polls=`5`，interval=`300s`。

截至 UTC 2026-08-24 20:13:48，monitor 已连续 6 轮记录 snapshot 仍为 f109，始终
`outcomes_read=false`，进程存活。它会等待 0823 archives 通过固定 intake 稳定门并形成新 snapshot 后，再开始自己的
5-poll 静默计时；不会因为单个文件 mtime 变化就运行 formal。

## 3. 边界

这只是并发/批量到达时的工程完整性修正，不是科学结果。它不把 target-300 变成 first-960，不授权 score-channel
replay/effect，不读取 archive bytes，不使用 GPU/API，也不改变 outcome-blind continuous intake。若新 snapshot 在静默
窗口继续变化，计数必须清零重来，不能选某个看起来更有利的中间 snapshot。
