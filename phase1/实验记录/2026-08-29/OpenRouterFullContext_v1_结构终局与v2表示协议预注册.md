# OpenRouter full-context：v1 结构终局与 v2 表示协议预注册

## v1 终局

v1 原协议 SHA=`56a33c24...27a29` 与 metric-recovery erratum SHA=`0882bd6e...9206` 均在对应 readout 前冻结。
run consensus formal r4 仍在 selection 前以 `insufficient eligible stratum` 退出；aggregate census 表明 2,501 个相关
endpoint/parent Cards 全部没有可恢复 metric，八个 strata eligible 均为 0。因此 v1 分类固定为：

`RUN_TASK_METRIC_CONSENSUS_RECOVERY_PANEL_INFEASIBLE`

不能删除 v1、缩小每桶 8 对、从 description 猜 metric 或把该失败称为 evaluator 负结果；它只说明 v1 的输入表示契约与
历史 schema 不相容。

独立 verifier commit=`7b047399...5662` 在 fresh no-smudge worktree 完成 A/B byte equality：result=
`85a3c828...6379`，确认 845 runs / 40,950 Cards 中非空 `task.metric` 为 0；2,208 test endpoints 与其 174 个 run-task
keys 也全部无 metric consensus。decision/value_hardware_time pair 中不同 run-task key 分别 198/315，和既有 relation/run
审计方向一致；该数字不是新的 pair-quality 结论。trace network/prospective opens=`0/0`，资源=`0/0/0/0`。

## 为什么允许另立 v2

单独的 metric-name 行是我们在实现学长“完整上下文”建议时额外加入的表示要求，并非 pair estimand、selection 或成本控制。
Cards 对所有 40,950 行都不提供该字段，所以继续 recovery 会变成人工猜测。与此同时，相关 endpoint 的完整 task
description、higher/lower direction、client、hardware、两个时限与完整 code 均有结构支持。

v2 不是把 v1 改成成功，而是一个新的、在任何 v2 eligibility/model readout 前冻结的表示协议：

- 删除单独 metric-name 行，且不发送 null placeholder；
- 禁止从 description 解析、alias 或联网查 metric；
- 保留完整 task description 与 higher/lower direction；
- 其余 immutable inputs、两个 panel、4 桶×8、direct sibling、same-run exact-resource、run/endpoint/task caps、
  deterministic selection、模型、双方向、完整 code、ZDR 与 2/10 USD stop 全部继承 v1；
- v2 仍是历史 development diagnostic，不是 frozen confirmation，不授权 live API calls。

机器 amendment=`openrouter_full_context_metric_omission_amendment_v2.json`。若冻结后仍有任一 stratum 不足 8，则分类为
`METRIC_INDEPENDENT_EXACT_PANEL_INFEASIBLE`，不再增加第三种 fallback。
