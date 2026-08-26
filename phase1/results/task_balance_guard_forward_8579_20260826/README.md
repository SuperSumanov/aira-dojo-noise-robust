# 7cda→8579 task-balance guard forward audit

这项 audit 把在 `7cda` 快照 outcome 前冻结的 25% dominant-task pair-share guard 应用于后续 `8579` 快照。它只使用
chronological run ledger 与七臂 exact-common structural pair inventory，不读取 truth、prediction values 或 archive payload。

## Confirmatory accounting result

新快照增加 27 runs 与 120 canonical pairs；其中 27 pairs 来自旧 dominant task OSIC，93 pairs 来自其他任务。冻结整数
envelope 的预测为：

```text
current debt = 657 + 3 * 27 - 93 = 645
```

独立实现从 current per-task counts 得到的 debt 也是 645，因此 accounting identity 精确通过，债务净减 12。与此同时必须
保留两个失败边界：OSIC share=`0.308529945553539`，25% cap 仍未通过；且在 debt 清零前新增 27 个 OSIC pairs，明确不符合
旧 guard 的“暂避 OSIC”即时动作。自然摄取不是随机干预，所以不主张 guard 导致了改善或 producer 遵从。

## Descriptive secondary

- pair-HHI：`0.1357471491993994 → 0.13322920543739974`，delta=`-0.0025179437619996525`；
- run-HHI：`0.048877054672340124 → 0.04868762877362716`，delta=`-0.00018942589871296517`；
- run→pair TV：`0.337082500713674 → 0.32785794333204404`，delta=`-0.009224557381629972`。

这些方向是已见过概要后的 descriptive secondary，不能救回 cap failure，也不是 predictor effect。

## Chronology correction and preserved failure

第一版提取错误地要求新 ledger 文件以旧 ledger 的原始 bytes 为前缀，因此 fail-closed。诊断证明没有旧 run 被删除、重排
或改写：339 个旧 run_id 全部存在，旧顺序是 366-run 序列的 subsequence，同 run_id 行完全相同；只是 2 个按冻结总序应
更早的新 run 插入了旧 provisional tail 之前。最终 audit 使用与 first-960 定义一致的 set/subsequence/row invariants，并在
`failed_attempt_v1.json` 保留首次失败。

safe structural input / forward result / independent receipt SHA-256 分别为
`0422e068eba42f6769dd4edbe41b17a5c058804108febd8068518c28098c095e`、
`58126971bc846fa14561d3665a824c19b16a6dc2cf96da6e1fea378ff843e799`、
`b9990aabacf93f3b921ca11d523e88eb2036257ba2b1ae86a0e149dc7f7af0fb`。

本结果是 acquisition-integrity 与 benchmark-design 的正向但有限证据，不是 accuracy、causal acquisition effect、search
utility、cap pass 或 strict guard compliance。GPU/API/model fit/base-LLM update=`0/0/0/0`。
