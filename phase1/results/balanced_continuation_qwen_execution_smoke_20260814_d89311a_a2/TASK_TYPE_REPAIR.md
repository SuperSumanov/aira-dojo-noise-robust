# Qwen execution smoke：任务类型纠错结果

旧 `VERDICT.md` 与旧 verification 原样保留，但其 `1/2` 工程门已被新证据覆盖：旧验证器把
`spaceship-titanic` 官方允许的布尔 `Transported` 列误当成必须可由 `float()` 解析。

在 commit `047420c498f673ae6e302a60b1f099c1845f6f2a` 上，远端 9 项专门测试通过；不 import smoke
producer 的 repair verifier 对两个旧 immutable artifacts 重新核验，状态为
`VERIFIED_QWEN_EXECUTION_SMOKE_PASS_TASK_TYPE_REPAIR`。修正结果为 2/2：spaceship 1,562 行严格布尔，
tabular 159,998 行 `[0,1]` 有限浮点。新增 candidate executions=0、API=0、GPU=0、标签/outcome 读取均为 0。

repair receipt SHA-256：
`40a7f793a70d30b12ace25a8b929caf6c009df98ce045b7b50ff4bac1df05ecf`。

这只恢复 fresh-anchor E1-Q 的准备与预检资格；它不是 continuation quality、balanced label 或 search
utility 的正结果。旧 1/2 记录不删除，以保留错误发现与纠正链。
