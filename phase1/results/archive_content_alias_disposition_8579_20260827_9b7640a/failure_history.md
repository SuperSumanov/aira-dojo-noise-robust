# 失败历史

- `formal-9b7640a-v1`：实质处置、pre verifier、runner、post verifier 和 partition verifier 均已完成；最终 trace gate
  使用文件名正则，把 Git status 的 6 次 `newfstatat` 元数据检查当成禁读命中。该目录保持无 `COMPLETE`，未删除、未
  覆盖，并写入 `FAILURE_POSTFLIGHT_TRACE_FILTER_v1.txt`。
- postflight-v2 首先逐文件核验 v1 原始 19 个产物，再把 6 条 broad hits 单独保存；三份 v1 trace 的实际禁读
  `open/openat` 均为 0。它在 fresh root 中重新运行 applied-state independent verifier 和 partition verifier 后才生成
  `COMPLETE`。
- public post-push v1 的 focused tests 已通过，但完整测试未限制 BLAS/OpenMP 线程，在第 309 项停滞并出现约 31 个 CPU
  线程过度并发。精确核验 cmdline 后只终止该次自有测试进程，v1 保持无 `COMPLETE`；v2 固定全部数值线程池为 1，
  通过 focused/full=`32/1196 passed`。
- intake deployment v1/v2 都在执行 initialize 前的 lock probe 失败：先是重定向语法错误，继而是只读 fd 上申请独占锁。
  两个失败根均保留 `FAILED_RC`、无 `COMPLETE`，production state 未被修改。v3 使用不截断的读写 fd 完成 lock probe，
  initialize 与 poll 0 均通过。

因此，不能把 formal-v1 改称成功，也不能删除失败目录；可引用的完成证据是
`/research/d7/spc/yzyang4/archive-content-alias/postflight-9b7640a-v2`。
