# Failure-mechanism × length heterogeneity v1

预注册 commit：`acf63075237e1e2f9ceb925a81fde6d95f295ccd`。正式 producer 双跑逐字节一致，
结果 SHA256=`d85ec8a42a09160e19c71961f419b59108034f293f02a0722b839a24d9915377`；完整测试
`360 passed in 31.02s`。

固定 494 pairs / 13 tasks / 126 physical runs 上，raw UTF-8 bytes 的整体“更长者是 retained success”
credit=`0.4493927125506073`。满足至少 30 pairs 的类别有 4 个；最高为
`DATA_SCHEMA_SHAPE_TYPE=0.4672489082969432`，最低为
`RESOURCE_TIMEOUT=0.35384615384615387`，range=`0.11340275445078934`，未达到冻结的 0.15 门。
task-stratified 100,000 次置换 `p=0.4312956870431296`，未达到 0.01 门；hash 负控
`p=0.34448655513444865`。

裁决为 **INSUFFICIENT_FAILURE_MECHANISM_LENGTH_HETEROGENEITY**。不得按结果翻转方向、合并类别或降低门槛；
不得声称 failure mechanism 决定长度规则，也不得开展 search utility 实验。
