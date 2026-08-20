# WLGraph 0819 增量托管：预注册与预检

日期：2026-08-21。状态：`PREREGISTERED_INTAKE_IN_PROGRESS`。

## 目的与边界

0819 是自动 activation receipt（`2026-08-20T05:20:27.656860Z`）后首批候选 physical runs。待固定八包
通过冻结 intake、批次闭合和双重 structural gate 后，对该不可变 snapshot 续写既有 WL graph prediction escrow。
这一步只封存预测，不读取 prospective outcome，不计算 accuracy、regret 或任何效果指标。

科学对象完全冻结：source commit=`031edb34400781ca026bc9833ac7f850312ffb1c`，四臂仍为
`step_only_lr`、`wl_graph_lr`、`wl_graph_static_lr`、`wl_graph_static_tfidf_lr`，bundle SHA256=
`df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e`，activation receipt SHA256=
`0139670acc49c961e38e6851d0416d1e5bfa1c318024b50330c15d51823112fb`。不得增加 arm、重拟合、挑
checkpoint 或打开 outcome。

## 预固定验证

1. 只接受本次监督器启动后写入的、绑定固定八包 manifest 的新鲜 completion marker；
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

## Intake 实际路径与直接接力补充预注册

冻结旧 intake 已正常提交 `ranzcr`、`multi-modal`、`alaska2` 与 `uw-madison`；其中此前只作为
fail-closed 备用分支准备的 `multi-modal` 结构恢复并未触发。旧 monitor 的控制循环没有“固定批次全部
resolved 后提前退出”的条件，即使八包全部持久化也会继续空轮询约四小时；原恢复监督器在“旧 monitor
正常结束且无需恢复”分支又不会发出 WL 下游要求的 marker。该问题只属于控制流，不改变 archive、
observer ledger、snapshot、scorer 或资格门。

因此在读取任何效果 outcome 前固定直接接力：

1. 对 SHA256=`d0c0ac148d4277cb11df4a13e5a23f29f57a043772d83423aa606ee1f996f017` 的精确八包
   manifest 轮询 `--require-resolved`；等待阶段不解释 archive payload；
2. 仅在八包全部已有 committed/rejected disposition 后，非阻塞取得同一个 `runner.lock`，锁内再次做
   全源 archive SHA256 校验并绑定 `LATEST`；
3. 锁内复核旧 monitor PID 的脚本与 commit 身份，只向该 PID 发送 `SIGTERM`，等待确认退出后释放锁；
   不使用强杀，不停止任何 intake transaction；
4. 对同一 snapshot 用固定门槛运行 structural gate 两次，JSON 必须逐字节相同；门返回
   `COLLECTING` 是合法结构结果，不等于效果失败；
5. 只有新的 `DIRECT_0819_BATCH_HANDOFF_VERIFIED ... outcomes_read=false` marker 可触发冻结 WL
   producer、独立 verifier 和 append verifier。旧 recovery 路径保持兼容，但两条路径不得共同提升产物。

该补充仍为 0 GPU·h、0 API、0 base-LLM update；预计接力本身少于 5 分钟，WL producer 与 verifier
维持各 10--15 分钟。任一 PID、锁、manifest/hash、ledger、`LATEST`、双跑一致性或 trace 门不符即
fail-closed。
