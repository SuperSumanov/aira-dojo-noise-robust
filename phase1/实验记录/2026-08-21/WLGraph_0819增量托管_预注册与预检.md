# WLGraph 0819 增量托管：预注册与预检

日期：2026-08-21。状态：`COMPLETED_SUPPORT_ONLY_INDEPENDENTLY_VERIFIED`。

## 目的与边界

0819 是自动 activation receipt（`2026-08-20T05:20:27.656860Z`）后首批完成投递/摄取的候选
physical runs；结果后核对证明这些 runs 的实际生成开始时间仍早于 activation，见末尾勘误。待固定八包
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

## Intake 实际路径、一次控制方案撤回与 Plant 恢复预注册

冻结旧 intake 依次正常提交 `ranzcr`、`multi-modal`、`alaska2`、`uw-madison` 与 `AI4Code`；其中此前
只作为 fail-closed 备用分支准备的 `multi-modal` 结构恢复并未触发。此时 ledger 为 5 committed、
3 pending、0 rejected。曾据此预备“八包正常完成后安全终止空轮询 monitor”的 direct handoff，但它在
部署前已被新证据否定，未在远端启动：下一包 `plant-pathology-2021-fgvc8-8seeds.tar.gz` 的冻结 intake
实际以 `journal must identify exactly one competition` fail-closed。直接接力脚本随即撤回，不得用于这批
数据，也没有产生或读取任何效果结果。

实际失败已绑定到：archive SHA256=
`f583a74a3e828d45a22de11158d79ab5ed33c51dd58933b076b48dc191e7ed4d`、size=109,828,866、
mtime_ns=1,787,238,813,000,000,000；旧 monitor log SHA256=
`0327c63cf454ae800a03136b4d1a9c3a6ee7b50b8824daabfe03ed0126f3cf3f`，失败 attempt log SHA256=
`e8aa85bbd981efd3b789787520bde22022b6273b0bf77e9601f31c158ef1b6e6`。在读取任何效果 outcome 前，
改为固定 Plant 专用恢复：

1. 先证明该精确 Plant archive 仍是 observer ledger 中第一个 ready 且 unresolved 的对象；
2. 用既有 credential-first 审计独立运行两次：只读 checkpoint journal，原始字节先做 credential-shape
   扫描，永不读 `env_variables.json` 或 live event journal，不输出 competition 值、代码、stdout、分数；
3. 只有至少一个 journal 的 competition cardinality 不等于 1 时，才能生成绑定该 archive 与审计 receipt
   的单条 structural-rejection registry；审计/registry 两次必须逐字节一致；
4. continuation 仍用冻结 scientific commit `90842c49...`，仅追加这一个不可变 rejection registry，
   处理剩余 archive，并要求固定八包 manifest 全部 resolved 且源 archive 全量哈希一致；
5. structural gate 对同一 `LATEST` 运行两次、逐字节一致；只有新的
   `PLANT_RECOVERY_AND_0819_BATCH_VERIFIED ... outcomes_read=false` marker 才能触发 WL escrow。

该恢复仍为 0 GPU·h、0 API、0 base-LLM update；预计 5--15 分钟，hard wait 30 分钟。WL producer 与
verifier 维持各 10--15 分钟。任一日志、archive、first-ready、凭据、审计、registry、batch、`LATEST`、
双跑一致性或 trace 门不符即 fail-closed。

## 结果后勘误与完成状态

固定八包最终为 7 committed / 1 rejected；Plant 的 4/4 checkpoint journals 均没有唯一 task identity，
所以精确结构性拒收。最终 snapshot=`83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047`，
结构门与 WL append 均独立复核通过。

本文件开头“activation 后首批候选 physical runs”只能指投递/摄取顺序，不能指预注册的生成时间口径。固定
scorer 按 `generation_started_at_utc > activated_at_utc` 分类后，新增 26 runs / 192 pairs 与累计 249 runs /
1,665 pairs 全部仍为 `outcome_unread_support_only`；strict post-activation runs/pairs 均为 0。该零值不能通过
改用上传时间、移动 activation 或放宽严格大于来修补。producer/verifier 最大绝对差均为 0.0，旧行逐字段不变，
禁读路径命中与 credential-shape matches 均为 0；没有计算任何效果指标。
