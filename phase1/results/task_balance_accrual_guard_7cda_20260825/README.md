# first-960 任务均衡摄取护栏：7cda snapshot

本目录把 first-960 既有结构门 `maximum_dominant_pair_task_share=0.25` 转成可执行、结果盲的前瞻摄取约束。
输入固定绑定 snapshot
`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1` 的 structural gate 与七臂
common-support matrix；两者 SHA-256 分别为
`ca44845bc0f5feaf5de0e77ec658e4b0cca3f5a451b75b33bb4c63acfc1eccca` 和
`be63fbe02c63c306bb488aa30416de7260e83e4701bdce3ed3f1d8843fd6f6b7`。

当前 2,635 个 canonical sibling pairs 中，OSIC 有 823 个，占
`0.31233396584440226`，尚未通过 25% 上界。令 `x` 为此后新增的非 OSIC pairs，`y` 为新增的 OSIC pairs；
当前 OSIC 约束的精确整数包络为：

```text
x >= 657 + 3*y
```

因此若暂不新增 OSIC pairs，至少需要观察到 657 个新增非 OSIC pairs。此时总数为 3,292，每个任务允许的
pair 上限为 823。657 只解决当前 OSIC 的占比债务，并非单独充分条件；对每个任务 `t` 还必须同时满足：

```text
4 * (current_t + future_t) <= current_total + sum_future_all_tasks
```

摄取应暂时避开 OSIC、轮换其他任务，并在每个稳定 snapshot 依据实际 canonical sibling-pair 产量重算；不能把
657 换算成 raw-run 配额，也不能按预期 yield 记账。该规则不删除或重排已进入的 run，不改变 first-960 的时间序
membership，不是提前停止规则。

`guard.json` SHA-256=
`fd87246bb3656befba27de5a98c88f808ca39e178e7322d27ae9536fe4a751b0`；独立实现复算结果
`independent_verification.json` SHA-256=
`7feaf1a7ad317963bbc6a7169f624a7e91f447424563df480d4765e2cba6760d`。

本目录没有读取 label、grade、outcome、winner orientation 或 prediction values；accuracy/effect/search utility
均未计算，GPU/API 调用为 0。它是 acquisition-integrity 资产，不是 predictor 方法正结果。
