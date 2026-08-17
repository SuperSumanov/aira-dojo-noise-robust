# Failure-risk controller LOTO v1：裁决

日期：2026-08-17。裁决：`INSUFFICIENT_TASK_HELDOUT_FAILURE_RISK_SIGNAL`。

494 parent-matched pairs 的固定 char-TFIDF 在 13-task LOTO 上 micro=0.52429，task-cluster CI
[0.48885,0.58516]；相对预指定 length LR 差值 -0.04453，task-CI 跨 0。全部方法正结论门失败，v1 关闭。

长度 LR 为 0.56883、task-CI [0.52096,0.62537]，作为预指定 baseline 是值得记录的探索性 execution-risk
关联，但本预注册没有给它独立确认门，不能把整个方法实验改判为通过。若未来新 cohort 足够，可在任何 outcome
前冻结 length-only scorer 做一次确认；当前 frozen decision set 不为此打开。
