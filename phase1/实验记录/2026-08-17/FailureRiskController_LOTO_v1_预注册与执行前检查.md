# Failure-risk controller LOTO v1：预注册与执行前检查

日期：2026-08-17。状态：`NOT RUN`。本文件冻结在训练任何模型之前。支持输入固定为
`VERIFIED_FAILURE_RISK_PAIR_SUPPORT` 的 494 unique-parent pairs / 13 tasks / 126 runs，summary SHA256=
`77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1`。

## 唯一问题

仅从候选静态代码、完全 held out 当前任务，轻量 controller 能否在同 parent 对中把 retained execution success
排在 execution failure 之前？这只检验跨任务 feasibility signal，不检验 quality 或 search utility。

## 十三项执行前检查

1. Split：13 folds leave-one-task-out；task 和其所有 physical runs 不得跨 train/test。
2. Unit：494 unique parents，每 parent 恰一 success/failure pair；不按失败 children 数重复加权。
3. Input：只用 code；不输入 task 名、task type、diagnostic、failure category、stdout、grade 或 frozen code。
4. Truncation：<=20,000 chars 原样；更长固定取 head 5,000 + tail 15,000。
5. Model：char TF-IDF 3--5 gram，min_df=2，max_features=50,000，sublinear TF，保留大小写；
   LR `C=1`、balanced、liblinear、max_iter=1000、seed 20260817。不得调参。
6. Baseline：只看 `log1p(code length)` 的同配置 LR，方向只由 training folds 学习。
7. Pair score：`P(success_code)>P(failure_code)` 记 1，反之 0，精确 tie 记 0.5。
8. Headline：494 对 micro accuracy；同时报告 13-task macro、逐任务和 run/task clustered CI。
9. Inference：固定 seed 20260817，10,000 次 task-cluster bootstrap；run cluster CI 作次要稳健性。
10. Positive gate：TF-IDF micro>=0.60 且 task-cluster CI lower>0.50。
11. Nontriviality gate：TF-IDF-length 的 task-cluster CI lower>0；8 个 n>=20 tasks 中至少 6 个 accuracy>0.50。
12. Resources：CPU-only，预计 <15 分钟；双跑逐字节一致；完整测试；GPU=0、API=0、底座更新=0。
13. Stop：任一门失败即关闭 v1；不得结果后改 n-gram、截断、阈值或 fold。通过也不允许写 search utility，
    必须另做固定预算 shadow/前瞻实验并申请预算。
