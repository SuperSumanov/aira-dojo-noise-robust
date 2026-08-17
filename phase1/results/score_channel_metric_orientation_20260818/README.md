# Result-blind metric-orientation supplement

状态：`VERIFIED_RESULT_BLIND_METRIC_ORIENTATIONS`。

在任何正式 replay outcome 产生前，独立脚本从 MLE-bench commit
`507f92e1138bb6e40dac5c6ee7a6758e6424bf97` 重新读取 10 个近期任务的公开 leaderboard，逐项复核：

- leaderboard 文件 SHA 与行数；
- `Grader.is_lower_better`；
- 固定 orientation=`-1 if lower_is_better else +1`；
- `grade_helpers.py` 与 `data.py` 的 source SHA。

独立验证连续运行两次，产物逐字节相同；receipt SHA-256 均为
`f1e5c6141d27c36fd5ead510631e1cef15297c0838efe8b37c3c7437dcab5c67`，且明确记录
`outcomes_read=false`。它只冻结指标方向来源，不生成候选 score、不打开 label vault，也不批准 GPU replay。

正式 selection 收口后，只允许将旧 `task_orientation.json` 与
`score_channel_metric_orientation_supplement_20260818.json` 合并；任一 selected task 缺失或重叠方向不一致即
fail-closed。

## Selection 后自动收口实现

- producer/no-import verifier commit：`2f2647575edd63c60bf1e76ba4a5cbc9176c56c0`；
- detached remote worktree：`/research/d7/spc/yzyang4/wt_scorechannel_orientation_2f26475_nosmudge`；
- 聚焦测试连续两次均为 `3 passed`；完整 suite 为 `376 passed in 30.33s`；worktree clean；
- 测试日志 SHA-256：`d417bdfd8c671ef64621a45f5035ebf39da6bdc59ff36eabc97bd22f4f859ab0`；
- post-freeze CPU chain PID：`341067`；它先等待 run/parent/replay 双冻结，不生成 approval、不提交 GPU。

该 commit 只作为 orientation receipt 的 source commit；正式 replay worker 仍固定使用已单独验证的
`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`。
