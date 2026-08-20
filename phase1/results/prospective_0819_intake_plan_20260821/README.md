# 0819 outcome-blind 摄取计划（结果前固定）

- 输入固定为 `archive_manifest.json` 中 8 个归档的 path / size / mtime / SHA256。
- 固定稳定门：age >= 21600 秒、至少 3 次间隔观察、stable span >= 600 秒。
- 逐包处理，任何 intake 异常立即 fail closed；不按文件名补 task identity。
- 已知高风险包只有在“恰为队首 ready archive”、credential-first task-identity 双审计逐字节一致、
  `outcomes_read=false` 且精确文件身份仍一致时，才允许产生一份新的不可变拒收 registry。
- 续跑时 8 个归档必须各自精确绑定为 committed 或 rejected；否则批次不完成。
- 本计划只扩展 first-960 的 outcome-unread 结构前缀，不改变 960-run + accrual closure 停止规则。
- 资源：CPU only；GPU=0，API=0，底座模型更新=0。
