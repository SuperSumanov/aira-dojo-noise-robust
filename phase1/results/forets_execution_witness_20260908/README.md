# ForeTS 每次 task 返回的独立回执（2026-09-08）

## 范围与验证问题

接在 standalone 0005 后的可选 0006，绑定学长 upstream
`54929de4ac92cb1a1a2fd75e31843a223c10c859` 和 base tree
`08d78ba2b0cf71c44cbd9eda34df15ae60049409`。未部署，未修改学长分支。

问题：主候选及其 debug 的 `task.step_task` 返回，是否在 analysis/journal/backprop
之前独立落盘，从而把“任务已返回、后处理失败”与“任务尚未返回/结果未知”区分开？

此前候选 ledger 的 `execution_completed` 在全部后处理/debug 返回后才写。
旧版遇到后处理异常会保留执行意图并禁止自动重跑，但缺少独立 task-return 回执。
不声称此前会自动重复执行，也不将本改动当作完整恢复。

## 改动

- 每次真实 task 调用前先持久化 code、SHA、role、观察到的 interpreter 类和 timeout。
  主调用和 debug 共用批次入口 `remaining_steps` 的调用次数上限，失败尝试也占次数。
- task 返回后立即持久化结构回执，再交给原 analysis/journal/debug。
  整个 task 调用的 monotonic 墙钟耗时与 interpreter 报告的执行时间分开，不用后者替代前者。
- task 抛异常时仅保存异常类、已观察墙钟时间；内部执行信息未知，绝不记作零。
  不保存成绩、终端输出或原始异常文本；代码保留在私有 ledger。
- 实际 interpreter.timeout 必须与原 cfg.execution_timeout 相符；不缩短 timeout。
  旧 schema 不自动混用；未选候选不得执行，未知状态不重试。

候选生成、critic 排名、selector seed、步数与 debug 算法不变；未来 random/critic
两臂应共同接入该回执层。生成和 analysis 仍为已有逻辑，不更新 agent 底座。

## 当前验证

Windows 新增定向测试：15 passed / 1 Linux-only skipped，见 `windows_initial.xml`。
真实 Git index 应用得到 tree `a999d8aaf8e9278e4e1eab57e5e45d2b0f87aa48`，
3 文件、138 新增、5 删除。实际 tree 验证及 Linux 新验证的状态以后续回执为准。
不会重跑此前 69 项再当成新进展；本矩阵仅验证新增 task-return 接线。

Linux 预定最多 300 秒 CPU、零 GPU/付费 API/模型训练，只跑新增定向测试。
一项使用固定源码 PythonInterpreter 的真实子进程执行人工 print 程序，导入路由、
logger/config 注入；其余 task/backend 人工构造。即使通过，也不是完整 Dojo/MLE 评分
或真实任务收益，更不验证外部开发来源。

## 未完成边界

记录的 timeout 是属性观察和一致性检查，不是硬墙钟/GPU·时限制。
原 MCTS 在一个 step 结束后才检查全局时间；原 PythonInterpreter 报告时间不覆盖全部
启动/清理成本，部分超时路径仍未设置 timed_out。保留 reported 字段，不据此声称无超时。
完整费用、SDK 内部重试、critic/analysis 成本、物理 GPU 分配、进程树隔离与完整恢复未验收。
无新模型收益，production_ready=false。严格四fit仍等待实际独立开发来源。
