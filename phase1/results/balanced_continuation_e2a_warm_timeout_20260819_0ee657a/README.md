# E2-A 1200 秒 warm 边界不稳定审计

本目录保存 2026-08-19 E2-A 安全 cache 修复后六任务 warm 的紧凑执行审计。它只比较 public candidate
execution receipts，不含分数、标签、sealed value、API response 或密钥。

- source：`0ee657a14a9bba0ddf58670f177e9e103c33720a`；
- run：`/research/d7/spc/yzyang4/balanced-e2a-warm-smoke-0ee657a-a1`；
- 实际执行：4 candidates，3 ok + 1 TPS timeout，0 API，0 retry；
- 第二批未提交，formal 未启动；
- 同一 TPS code/data/container/node/allocation 的两次 candidate wall 为
  `1119.5009202449583` 与 `1200.2556150490418` 秒；
- 裁决：1200 秒资格边界不可重复，本协议 formal 关闭，不补跑。

`audit.json` 绑定远端原始文件 SHA。该裁决只关闭本次 E2-A 协议；不得写成 continuation 方法的负结果，
也不得把首批 3/4 工程通过写成正方法结果。
