# Score-channel confirmatory replay 启动审计（2026-08-18）

状态：`RUNNING_CONFIRMATORY_REPLAY_NO_OUTCOME_READ`。正式 jobs 为 11127/11128/11129/11130，对应 frozen
shards 0/1/2/3 与 100/85/78/57 candidates；均在 gpu27、RTX3090 上于
`2026-08-18T13:39:18Z` 启动。worker source、approval、coverage 和 replay SHA 均沿用执行前冻结；没有重选
parent、改 cap、改 candidate code、调用 LLM API 或更新底座模型。

## Slurm 秒级取整修正

执行前计划给 shard 3 请求 `01:53:40`，但首次 `squeue` 在结果行仍为 0 时显示 Slurm 将其向上取整为
`01:54:00`。若不处理，四片理论分配加历史 20 秒会超过原 38,400 秒硬上限 20 秒。故在 job 11130 运行约
38 秒、尚无结果行时，用 `scontrol` 原地把 TimeLimit **降低**到 `01:53:00`；作业没有取消、重启或改变候选。

修正后四片 TimeLimit 秒数为 12,000/10,200/9,360/6,780，合计 38,340；加历史 fail-closed 20 秒为
38,360，较批准硬上限留 40 秒余量。远端 amendment receipt SHA=
`ba02fd171469b8b185754dcddfd17bd8fcfd4bc2bcfad69af68d6b4f7ee92147`。这项修正覆盖 preflight 中“Slurm 会保留
秒级 TimeLimit”的错误假设，但不覆盖其他冻结协议。

## 启动前最终门

- 完整数据 coverage SHA=`dd986c78a2f7f411ce16a1f1b757b7b8a77140aff99a36c9a311f7b81eeb8181`；
- approval SHA=`b107075810e5af0da084be087cfa70740cd846d198a155116a061599e3057e09`；
- worker commit=`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`；
- preflight 报告 commit=`b1797dea6003d4790319d873133c97357297b36b` 在远端完整依赖环境为
  `384 passed in 33.84s`、rc=0；
- 第二次显式 submit 前 dry-count/test-only/secret/active-job 门全部重跑通过。

当前监控只读取 Slurm state、job rc 与 JSONL 行数，不读取 `sub_score`、`stdout_val`、frozen labels 或任何科学
效果。只有四片终止、结果 SHA 固定且 completeness 门通过后，才允许 frozen analyzer 一次性打开结果与 label
vault；否则诚实报告预算内不完整，不扩预算、不改 analyzer。
