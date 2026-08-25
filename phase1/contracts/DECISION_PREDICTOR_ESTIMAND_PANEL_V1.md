# Decision Predictor Estimand Panel v1

状态：`FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE`。

## 1. 为什么现在冻结

`7cda` 的结构图谱显示：first-240→339 runs 时 run-weighted task diversity 改善，但 pair-weighted task diversity
反向恶化；当前 run→pair task distribution 的 TV=`0.337082500713674`。因此 closure 后看到 predictor accuracy 再决定
用 pair-micro、task-macro 或 parent-macro，会构成 estimand 选择自由度。

本面板只冻结通用论文表格的汇总顺序，不读取 truth/prediction，也不改写已经冻结的实验 primary：

- scaling confirmation 继续由 `critic_scaling_confirmation_contract_v1.json` 的 task-macro pair accuracy 裁决；
- component breadth 继续由 `critic_component_breadth_future_evaluation_v1.json` 的 task-macro parent-macro pair
  accuracy 裁决；
- 任一实验 primary 失败时，本面板中的其他聚合均不得 rescue。

## 2. Generic benchmark headline

通用 Decision Corpus predictor table 的第一行固定为：

```text
pair credit → physical decision parent 内平均 → task 内平均 parent → tasks 等权平均
```

也就是 `task_macro_parent_macro_pair_accuracy`。parent 是一次真实 logged candidate-choice opportunity；先在 parent
内平均可以避免多 sibling parent 的组合数决定权重，tasks 等权则避免任务的 endpoint/pair yield 决定 headline。
physical run 保留为身份与依赖 cluster，不被 pair 频率隐式加权。

## 3. 必须同时给出的 non-rescuing panel

1. task-macro / pair-macro：兼容 scaling primary；
2. task→run→parent→pair macro：检查不同 physical runs 的 parent yield；
3. pair-micro：保留 empirical pair-frequency 视图，但必须并列 task mixture；
4. 每 task、run、parent 支持与 missingness；任何一行都不能替代失败的冻结 primary。

所有 arm contrast 先在同一 pair 上求差，再用同一层级聚合；不得比较两个不同支持池的单独均值。prediction margin 恰为
0 固定记 0.5；truth/tie 规则仍由对应实验的既有冻结契约决定，不得由本面板改写或跨 truth channel rescue。

## 4. 推断与支持表

generic headline 用 task bootstrap（20,000 draws，seed `20260901`，固定 SHA-256 index algorithm）并报告全部
leave-one-task-out；physical-run clustered 结果为必要敏感性，pair-i.i.d. CI 禁止进入 headline。实验自身已有 bootstrap
时，其 gate 仍以原契约为准。

支持表至少报告 cohort/finite-decision runs、tasks/informative tasks、parents/informative parents、pairs/informative
common-support pairs、truth/prediction ties，以及 task 按 run/endpoint/parent/pair 四种权重的集中度。inverse-HHI 必须标成
descriptive diversity，不能叫 statistical ESS。

## 5. 访问与计算边界

本冻结没有读取 prospective label、grade、outcome、winner orientation 或 prediction values，没有计算
accuracy/effect/search utility；GPU/API/model fit/base-LLM update=`0/0/0/0`。first-960 + 独立 closure、结构门、所有
prediction escrow hash 与 exact common support 未通过前，不执行效果表。
