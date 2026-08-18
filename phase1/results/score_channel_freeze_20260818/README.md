# Score-channel prospective freeze（2026-08-18）

状态：`SCORE_CHANNEL_FREEZE_COMPLETE_APPROVAL_PENDING`。正式 replay 尚未授权，GPU job=0，API=0，
底座更新=false，replay outcome 未产生也未读取。

## Outcome-blind 窗口修订

用户明确要求立即冻结，因此固定终点由 `2026-08-18T09:56:30Z` 修订为
`2026-08-18T04:35:35Z`。修订发生时记录 28 个 immutable intakes，并明确写入
`outcomes_read=false`、GPU/API=0；amendment SHA-256 为
`f3a808cee873d78e70d4fca0ebac9c745c157cc63511a12a0263522f988a5d43`。原终点及修订原因均保留，
不得把该 cohort 描述成原 12 小时窗口自然结束。

## 双重冻结结果

- run gate：177 个 post-mechanism physical runs、19 tasks；最大任务为
  `ranzcr-clip-catheter-line-classification`，26/177=`0.14689265536723164`，低于 0.25 门。
- parent selection：486 个合格 parent；固定 SHA lottery 每 run 最多取 2 个，得到 158 个 parent、320 个候选。
- replay manifest：320 个候选均固定 120 秒、4 个确定性 shard、同一 physical run 不跨 shard；精确上界
  `10.666666666666666 GPU·h`。
- orientation：被选 parent 覆盖 17 tasks；producer 双跑逐字节一致，独立 verifier 双跑一致；receipt SHA-256
  `81c9684741cb166bf1b4e2d7cb91ed0c8742c5040945b44d22f1c61f18baf85a`。

run、parent、replay 和 orientation 四段均由双 producer 重建并逐字节比较，再由不导入对应 producer 的实现
独立重建。选择 commit 的完整 suite 为 `378 passed in 32.71s`；补全 orientation source 后的完整 suite 为
`378 passed in 31.54s`。全部精确 SHA 见 `freeze_receipt.json`。

## 失败与修复审计

第一次 parent freeze 正确地 fail-closed：旧 selector 把合格 physical run 内、但不属于时间前瞻结构视图的
677 条 vault 记录也视为致命异常。结果盲诊断显示 4,205 条匹配 vault 记录中无重复；1,961 个真正结构 child
全部有 `eligible_by_start_time=true` 的 vault 行，缺失为 0。修复后 producer 与独立 verifier 均先验证全局身份、
布尔资格和去重，再忽略不合格且未被结构边引用的记录；若不合格记录被结构边引用，回归测试仍 fail-closed。
修复 commit=`ba809ac0c524ed5f1e488695eab339c0bdd1ec6d`。

第一次 orientation freeze 又因缺少 `new-york-city-taxi-fare-prediction` 而 fail-closed。未读任何 replay outcome，
从固定 MLE-bench commit 的公开 leaderboard 双探针确认：1,485 行、文件 SHA-256
`54c294495d43f0ed48992fe6412862f334cfe3b2cced9b978b40639bdc5ba072`、lower-is-better=true。补入后完整
11-task source 的独立验证 receipt SHA-256 为
`2ab029daf7d074a9e96fb93b5d8a07bc3736146fb7f6e901459a44cb80986346`。

## 下一道不可越过的门

只有用户明确批准精确矩阵 `320 candidates × 120s × 4 shards`、上限
`10.666666666666666 GPU·h`，并签发绑定 frozen manifest、worker commit、容器与 pristine grader 的 approval
receipt 后，才能提交 replay。当前产物本身明确写有 `replay_submission_authorized=false`。
