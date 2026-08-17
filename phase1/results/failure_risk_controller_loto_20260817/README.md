# Failure-risk controller LOTO v1

日期：2026-08-17。裁决：`INSUFFICIENT_TASK_HELDOUT_FAILURE_RISK_SIGNAL`。

结果前 commit `11a866bd8e734afd977b9acfef4d1c1d5115e043` 冻结 494 unique-parent pairs 的 13-fold
leave-one-task-out 协议。模型只看静态代码：char TF-IDF 3--5 gram + 固定 LR；不输入任务、诊断、failure 类别、
grade 或 frozen code。远端完整 `phase1/tests` 为 `356 passed in 29.58s`。两次单线程运行分别用时 8:33.83、
8:25.43，峰值 RSS 1,733,300/1,733,080 KiB；输出逐字节一致，SHA256=
`ee2364ebfa5499e03b322f34c636970e9a8554a8e56af62d471adefea59f164c`。

TF-IDF micro pair accuracy=`0.5242914979757085`，task-clustered 95% CI
`[0.48885059790758445,0.5851563704084254]`，run-clustered CI
`[0.47368421052631576,0.5774357721067435]`；未过 0.60 与 CI lower>0.50 门。预先固定的 length-only LR
为 `0.5688259109311741`，task-CI `[0.5209636505871054,0.6253654998528029]`；TF-IDF-length=
`-0.04453441295546556`，task-CI `[-0.0976442470927765,0.024710381648629962]`，也未过非平凡性门。

task macro 0.6192 明显受只有 2、3、8、10 对的小任务抬高；不能替换预注册 micro headline。长度基线的 CI
高于 0.5 是一个预先指定但非 primary 的探索性关联，可在未来全新 cohort 上冻结确认；不得消耗现有 frozen
b0/b1/b2 来追认，也不得在同一 494 对上换截断/ngram/阈值追正数。

因此关闭 learned static-code controller v1；保留 494 对 benchmark 与 560/691 structured failure-memory
数据资产。没有 search utility、GPU/API 或底座更新。
