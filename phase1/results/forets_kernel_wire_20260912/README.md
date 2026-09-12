# Fresh-gateway定向排障回执

2026-09-12。仅固定标记程序，无模型/API/任务数据读取/历史候选重跑；原镜像gpu28。

| 作业 | 固定重建次数 | ready/marker | 通道可观察性 | Slurm allocation秒 |
| --- | --- | --- | --- | --- |
| 13161 | 32 | 32/32 | 无效：只有loaded，generic jupyter CLI换进程丢hook | 114 |
| 13164 | 32 | 32/32 | 有效：每次connect/incoming/匹配reply均可见 | 101 |

总0.059722222222222225GPUh。修正版启动同一已安装kernel_gateway模块以保留被动hook；不改原MLE镜像或冻结source。
13164握手中位数0.06950959388632327秒、最大0.07649853709153831秒。所有成功连接的session-match为false，
说明缺少URL session_id并不必然导致失败；不能由此完全排除其与竞态的交互。
两组都只说明此定向条件下未复现，没有修复生产故障/证明故障率，不继续增加循环追故障。
原Space25日志中的ZMQ non-socket在超时与清理之后，不能当先行根因。

- 首版source commit316667d0e5bbac31f7d286c3f847c966170de4f6；修正版c22250b39ea94eef3ee5addab9e74db3e6963eef。
- 两组使用生产source tree e07cb8c61bca347c61bb8253c84eda826b1add6a的client/server类；独立bootstrap修订有启动时序局限。
- 首版回执SHA463c7f4cafc3842affd83b8ab5baea373b12e0a05d96bfa1da5654686cb391f6。
- 修正版回执SHA0b2b236e2623546116674d2b2553439b167fbdc6cf1a401c56c9ee90488ac6a7。
- 原远端root分别为/research/d7/spc/yzyang4/forets-kernel-wire-20260912-joepk5ej和forets-kernel-wire-20260912-qSZRVKYS。

诊断按首次故障停止，不是故障率对照；旧12-kernel测试只复用一台gateway，不等同这里每次重建。
生产13156两项KernelReadinessError仍原样保留。本轮同时推进首池未执行候选补齐，见FORETS_POOL_COMPLETION_PLAN_20260912.md。
