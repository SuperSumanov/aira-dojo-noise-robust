# Result-blind metric-orientation supplement

状态：`VERIFIED_RESULT_BLIND_METRIC_ORIENTATIONS`。

在任何正式 replay outcome 产生前，独立脚本从 MLE-bench commit
`507f92e1138bb6e40dac5c6ee7a6758e6424bf97` 重新读取 11 个近期任务的公开 leaderboard，逐项复核：

- leaderboard 文件 SHA 与行数；
- `Grader.is_lower_better`；
- 固定 orientation=`-1 if lower_is_better else +1`；
- `grade_helpers.py` 与 `data.py` 的 source SHA。

独立验证连续运行两次，产物逐字节相同；receipt SHA-256 均为
`f1e5c6141d27c36fd5ead510631e1cef15297c0838efe8b37c3c7437dcab5c67`，且明确记录
`outcomes_read=false`。它只冻结指标方向来源，不生成候选 score、不打开 label vault，也不批准 GPU replay。

正式 selection 首次收口后，在任何 replay outcome 产生前发现所选任务还包含
`new-york-city-taxi-fare-prediction`。同一固定 MLE-bench commit 的公开 leaderboard 双探针逐字节一致：
1,485 行，SHA-256=`54c294495d43f0ed48992fe6412862f334cfe3b2cced9b978b40639bdc5ba072`，
`Grader.is_lower_better=true`，故 orientation=`-1`。补充表随后必须再次接受完整独立双验证；此前 10-task
receipt 只保留作追加历史，不再作为正式 selection 的完整 orientation receipt。
更新后的 11-task 独立验证同样双跑逐字节一致，receipt SHA-256=`2ab029daf7d074a9e96fb93b5d8a07bc3736146fb7f6e901459a44cb80986346`，
且仍明确记录 `outcomes_read=false`。

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
