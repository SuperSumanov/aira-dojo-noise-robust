# Score-channel prospective eligibility：0813 outcome-blind metadata audit

日期：2026-08-15。状态：`VERIFIED_47_RUNS_INSUFFICIENT`。先用
`/research/d7/spc/yzyang4/prospective_decision_v1/observations.json` 建立 archive 元数据上界，再只读取生产链已经
credential-first 脱敏生成的 intake summary 与 `source_provenance.json`。分析侧没有打开 env、raw journal、代码、
stdout、分数或 label vault。

## 固定观察

- baseline seal：128 archives；新增稳定归档：8；monitor transactions：8；
- monitor 连续报告 `outcomes_read=false`、`ready=0`；
- observations SHA-256：
  `1fa399a1a7aeded2729bfbc2c9b07e9e83b312977f57031e8d77fc89d9239665`；
- 8 个 archive 各自已有 immutable archive SHA 与共同 snapshot SHA
  `174a781fc3a62f69182049e538ae5db249af26e495e5b5e4329f4b43f4090782`。

按文件名中冻结的 `Nseeds` 字段，两个独立文本实现先得到 52-run 声明上界；安全 intake 的精确 physical-journal
结果则为：

| quantity | value |
|---|---:|
| archives/tasks | 8 |
| declared seeds upper bound | 52 |
| unique physical journals | 47 |
| post-mechanism journals | 47 |
| tasks | 8 |
| max verified runs for one task | 8 |
| dominant task share | 0.170212765957447 |
| shortfall to 150 | 103 |
| pre-label structural pair/parent opportunities | 334 / 334 |

任务分别为 dog-breed、dogs-vs-cats、learning-agency-lab、random-acts-of-pizza、ranzcr、tweet-sentiment、
ventilator 和 whale；验证 run 数为 8/8/4/4/4/3/8/8。最早和最晚 root creation time 分别为
`2026-08-13T14:21:58.770365Z` 与 `2026-08-14T06:40:50.074029Z`，均严格晚于机制 commit
`4c964f8` 的 `2026-08-12T21:31:21Z`。

两套独立聚合（jq 与 TSV/awk）都得到 47 unique runs / 8 tasks / dominant=8 / shortfall=103。八份
`source_provenance.json` 的 SHA-256 也逐份与对应 intake summary 锁定值一致。每份 intake 均记录：journal raw bytes
在 JSON parse 前完成 credential scan、credential-shaped journals=0、env members read/extracted=false、raw journals
written=false、precutoff endpoint/code overlap=0、label values printed=false、用于 run/endpoint selection=false。

## 严格解释

文件名 `Nseeds` 的 52 比真实 journal 数多 5，证明不能把 archive 名当 run receipt。47 个 run 只通过时间、唯一性和
任务占比三项门；预注册还要求每个入选 parent 有至少两个 finite graded siblings，这一步必须由受信任 selector 在
150-run 门满足后读取 vault 并只输出 parent IDs/资格收据，不能让分析侧现在查看 label。334 个 structural parents
只是 pre-label opportunities，不是 334 个已合格 replay sets。

因此当前仍不能提交 replay、读取 outcome 或放宽 150-run 门。任务占比 17.02% 暂时低于 25%，但新增 cohort 后必须
对最终 150-run 冻结列表重新计算。

现有远端 metadata monitor PID `4087890` 继续每 300 秒 outcome-blind 轮询；新增 archive 必须先完成稳定性、
archive SHA 与 snapshot transaction，再进入相同台账。
