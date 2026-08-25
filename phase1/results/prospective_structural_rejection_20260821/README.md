# 0819 Plant Pathology 结构拒收收据

本目录把此前只位于集群外部安全 registry 的 0819 Plant Pathology 拒收记录复制为 GitHub 可访问的不可变证据。
两份文件与外部源逐字节相同：registry SHA-256 为
`0dc58a4f2b2770f615b4ebf6d077c25ec7866d0f0ad72a2cc2f312d8d4f1d503`，diagnostic SHA-256 为
`8d05bb39325855ce1d3ed3ac244e3095522c2c0a40fdc6494119e855bc19f2ad`。

四份 checkpoint journal 的任务身份基数均为 0，因此整份 archive 按
`JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE` 拒收。审计先做 credential scan，未读取 `.env`、live event
journal、代码、stdout、grade、metric 或 outcome。
