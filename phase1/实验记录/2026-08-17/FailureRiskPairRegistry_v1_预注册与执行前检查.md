# Failure-risk pair registry v1：预注册与执行前检查

日期：2026-08-17。目标是把已经通过支持门的 494 个 train-only parent-matched pairs 发布成不含原始代码的
不可变 registry；不改变 pair 选择，不做新模型，也不读取 frozen endpoint code 或数值分数。

1. **问题**：能否逐对发布 parent/run/task、failure/success child identity、failure category、source journal SHA
   与 endpoint code SHA，使数据用户能审计 494-pair benchmark，而无需公开潜在敏感原始 code？
2. **锁定输入**：只接受 SHA=`77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1`
   的既有 support summary，以及其中已锁定的 cards/status/taxonomy/frozen-pair inputs。
3. **选择规则**：完全复用既有规则；每 parent 取 child ID 字典序第一的 nonempty failure，再取同 run、不同
   exact-code SHA、child ID 字典序第一的 retained success。不得筛任务、类别或代码长度。
4. **安全**：target journal 完整 blob credential scan 先于解析；任一命中 fail-closed。输出 schema 是固定十个
   string 字段，不含 code、stdout、diagnostic、grade 或 pair orientation。
5. **结构门**：必须恰好 494 unique parents / 13 tasks / 126 physical runs；failure/success child 均唯一，
   endpoint code SHA 不同，credential target SHA=0。
6. **独立性边界**：producer 双跑必须逐字节一致；另一个不 import producer 的 verifier 只独立验证发布 schema、
   digest、identity uniqueness 与聚合一致性。它是 structural verifier，不虚称重新扫描 provenance 的完整独立复核。
7. **资源**：CPU-only，GPU=0、API=0、底座更新=0；预计单次 4--7 分钟，峰值内存低于 4 GiB。
8. **失败条件**：输入 SHA、旧 support contract、credential scan、固定计数或 verifier 任一不符即停止；不得人工
   删除行补齐 494。
9. **输出**：canonical JSONL registry、summary、双跑 SHA、结构 verifier JSON 与完整测试日志；文件只写新路径，
   不覆盖旧结果。
10. **允许主张**：仅允许“494-pair code-free registry 可发布并可结构复核”；不允许方法效果、search utility、
    因果 failure predictor 或跨 agent 泛化。
11. **复现**：产物记录 exact source commit、所有输入 SHA 与命令；完整测试通过后才允许正式运行。
