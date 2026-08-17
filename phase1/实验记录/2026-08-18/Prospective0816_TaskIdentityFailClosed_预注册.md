# 0816 plant-pathology archive task-identity fail-closed：预注册

日期：2026-08-18。第一个稳定新归档在 frozen intake 中因某 checkpoint journal 不能提供恰好一个
`competition_id` 而退出；transaction 未提交，outcome 未读。本审计不修补 task identity，也不从文件名猜 task。

1. 锁定完整 archive SHA 后，只用既有 tar 安全遍历读取 completed checkpoint journal；env/live member 永不读取。
2. 每个 journal raw blob 先做 credential scan，再解析 JSON；只输出 journal SHA、node 数和 task identity
   cardinality，不输出 identity 字符串、code、stdout、grade 或 metric value。
3. 只要任一 journal cardinality 不是 1，整 archive 以
   `JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE` 结构性拒收；不保留“看起来正常”的其他 seed。
4. 旧两份 rejection registry 和各自 SHA 绑定保持不变。runner 新增成对、可重复的 extra registry 参数；
   path/SHA 数量不一致即 fail-closed，避免继续增加固定的 third/fourth 参数。
5. 诊断 producer 双跑必须逐字节一致；完整测试通过后才允许写第三份不可变 registry 并重启剩余时长监控。
6. GPU=0、API=0、底座更新=0；本轮不计算科学指标，不改变 138/150 基线或任务身份定义。
