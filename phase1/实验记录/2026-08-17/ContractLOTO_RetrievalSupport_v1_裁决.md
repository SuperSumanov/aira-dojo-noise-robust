# Contract LOTO Retrieval Support v1：裁决

日期：2026-08-17。裁决：`INSUFFICIENT_TASK_HELDOUT_RETRIEVAL_SUPPORT`。

去任务名、列名、description 和 score 的结构 fingerprint 在 20-task LOTO 上得到同类型信用 0.50；
100,000 次固定 seed 标签置换的单侧 p=0.13867861321386787。它未通过冻结的 0.55 与 p<=0.05 双门。
image/NLP 各自高于 0.5，但 tabular=0；不能因两个类型较好而撤换 primary metric。

检索多样性与历史经验数量门通过，说明资源存在、纯结构路由不足。v1 在此关闭，不追加列名/description
救结果。正面路线转向已通过的 train-only failure-memory 数据资产；learned failure-risk controller 必须另行
冻结负例、run/task split、utility estimand 和预算。
