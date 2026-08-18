# 0817 LMSYS task-identity fail-closed 与安全续跑边界

日期：2026-08-19。稳定性门后，0817 前四个 archive 已形成 append-only transactions 29--32；第五个
`lmsys-chatbot-arena-8seeds.tar.gz` 在 frozen intake 的“每个 journal 必须恰好一个 competition identity”门返回
`rc=1`，监控按设计停止。失败前后均未读取 outcome，GPU=0、API=0。

结构错误出现后只复用 0816 已冻结的 credential-safe auditor，不尝试修补 task identity，也不从文件名猜任务。
archive SHA 锁定为 `c73582b32c98cb2ba2731dd867515a8624163998a3b3335a0f21e846ce4a3ffe`；producer
双跑逐字节一致，receipt SHA 为 `2de964ea8bb1d49a084ccfd97f65f408dfd0556499d911dc5cf36a446a321ee1`。
8/8 checkpoint journals 的 identity cardinality 均为 0。raw journal 在 JSON 解析前先做凭据扫描；env 与
live-event members 未读，输出不含 identity 值、代码、stdout、grade 或 metric。

因此整包以 `JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE` 精确拒收；不得部分 salvage。只有把该
archive path/size/mtime/SHA 与诊断 receipt SHA 绑定进新的不可变 registry，并在 clean commit 上验证全部旧
registry SHA 后，才允许 CPU intake 继续处理 0817 剩余 3 个 archive。续跑不改变任何已冻结科学 cohort，且
不得触发 GPU、API 或底座更新。
