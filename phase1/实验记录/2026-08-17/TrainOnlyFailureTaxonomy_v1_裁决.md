# Train-only Failure Taxonomy v1：裁决

日期：2026-08-17。裁决：`VERIFIED_STRUCTURED_FAILURE_MEMORY_SUPPORT`。

结果前冻结的 691-node taxonomy 在精确 producer commit
`a70cc689bbb88497f14c4358fc899599cd0e15fc` 上双跑逐字节一致，并由不 import producer 的 commit
`c1016b7343a5158ff74e6b2c333c1a517e31f10d` 独立复核。完整测试分别为 346 与 349 passed。

所有资格门通过：refind=691/691，diagnostic=691/691，structured=560/691，structured tasks=12，
dominant structured task=128/560，credential target SHA=0。318 个 schema/shape、104 个 library API/attribute、
81 个 timeout 构成主要失败族；contract-related 两类合计 324/691。

这是一项正面数据资产结论，不是方法效果。下一方法资格问题可以是：只使用 train-only code/contract/failure
family，轻量 controller 能否在 run-clean、task-held-out 协议下预测 execution failure，并在固定预算搜索中减少
无效执行。没有新的预注册、负例构造审计和功效分析前，不启动 GPU 三臂或声称搜索收益。
