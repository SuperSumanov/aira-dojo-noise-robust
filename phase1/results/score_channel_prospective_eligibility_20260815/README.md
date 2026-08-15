# Score-channel prospective eligibility：0813 outcome-blind metadata audit

日期：2026-08-15。状态：`INSUFFICIENT_METADATA_UPPER_BOUND`。本页只审计
`/research/d7/spc/yzyang4/prospective_decision_v1/observations.json` 的 archive 元数据；没有打开 senior tar member、
env、journal、代码、stdout、分数或任何 outcome。

## 固定观察

- baseline seal：128 archives；新增稳定归档：8；monitor transactions：8；
- monitor 连续报告 `outcomes_read=false`、`ready=0`；
- observations SHA-256：
  `1fa399a1a7aeded2729bfbc2c9b07e9e83b312977f57031e8d77fc89d9239665`；
- 8 个 archive 各自已有 immutable archive SHA 与共同 snapshot SHA
  `174a781fc3a62f69182049e538ae5db249af26e495e5b5e4329f4b43f4090782`。

按文件名中冻结的 `Nseeds` 字段，两个独立文本实现一致得到：

| quantity | value |
|---|---:|
| archives/tasks | 8 |
| declared seeds upper bound | 52 |
| max declared seeds for one task | 8 |
| max/total | 0.153846153846154 |
| shortfall to 150 | 98 |

任务分别为 dog-breed、dogs-vs-cats、learning-agency-lab、random-acts-of-pizza、ranzcr、tweet-sentiment、
ventilator 和 whale；声明 seeds 为 8/8/4/4/8/4/8/8。

## 严格解释

`Nseeds` 不是已经验证的 physical-run receipt，archive mtime 也不是 candidate 的
`generation_started_at_utc`。因此 52 只能是当前 cohort 的声明上界，不能写成 52 个合格 prospective runs；
更不能据此读取 outcome、提交 replay 或放宽 150-run 门。即使未来确认这 52 个全部合格，主实验仍至少缺 98 个
post-mechanism physical runs。声明层面的任务占比低于 25% 门，但最终仍需按真实 run receipt 重新计算。

现有远端 metadata monitor PID `4087890` 继续每 300 秒 outcome-blind 轮询；新增 archive 必须先完成稳定性、
archive SHA 与 snapshot transaction，再进入相同台账。
