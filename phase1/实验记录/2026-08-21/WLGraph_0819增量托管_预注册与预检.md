# WLGraph 0819 增量托管：预注册与预检

日期：2026-08-21。状态：`PREREGISTERED_WAITING_FOR_0819_INTAKE`。

## 目的与边界

0819 是自动 activation receipt（`2026-08-20T05:20:27.656860Z`）后首批候选 physical runs。待固定八包
通过结构恢复、批次闭合和双重 structural gate 后，对该不可变 snapshot 续写既有 WL graph prediction escrow。
这一步只封存预测，不读取 prospective outcome，不计算 accuracy、regret 或任何效果指标。

科学对象完全冻结：source commit=`031edb34400781ca026bc9833ac7f850312ffb1c`，四臂仍为
`step_only_lr`、`wl_graph_lr`、`wl_graph_static_lr`、`wl_graph_static_tfidf_lr`，bundle SHA256=
`df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e`，activation receipt SHA256=
`0139670acc49c961e38e6851d0416d1e5bfa1c318024b50330c15d51823112fb`。不得增加 arm、重拟合、挑
checkpoint 或打开 outcome。

## 预固定验证

1. 只接受恢复监督器本次启动后写入的 `STRUCTURAL_RECOVERY_AND_0819_BATCH_VERIFIED` marker；
2. marker、`LATEST` 与 snapshot 目录必须绑定同一 SHA；
3. producer 与不 import producer 的 verifier 都用冻结的 `031edb3` clean worktree；
4. 两者逐 endpoint 数值最大差必须 `<=1e-12`；
5. 旧 snapshot 的每个 endpoint 与 canonical sibling pair 必须在新 artifact 中逐字段完全不变；
6. source-file hashes、protocol、bundle、bundle summary、bundle verification 与 activation 必须跨快照相同；
7. producer/verifier 均在 `strace trace=file` 下运行，任何 forbidden path 的任何 syscall 观察均失败；
8. 所有新产物做高置信 credential-shape 扫描；
9. append verifier 独立运行两次，JSON 必须逐字节相同；
10. 任一步非零、schema/hash/subset 不符或 `LATEST` 漂移，停止且保留 staging，不提升正式产物。

固定效果资格门仅做 outcome-free 样本量统计：strict post-activation 至少 1,500 pairs、150 runs、15 tasks，
最大 pair-task share `<=0.25`。未过门只表示继续积累，不能降门；过门也不能在 first-960/closure 之前开 outcome。

资源预算：0 GPU·h、0 API、0 base-LLM update。producer 和 verifier 串行各约 10--15 分钟，预计总计
25--40 分钟，分别 hard timeout 2 小时。既有旧 escrow 为 5,643 endpoints / 223 runs / 1,473 pairs，旧
artifact summary SHA256=`ff49cee419a2cc90230fb0dad44058b9e61bb73fd90c38b77509b91b512c13be`。
