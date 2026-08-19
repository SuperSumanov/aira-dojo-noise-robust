# BalancedClientPilot v1：预注册与长实验预检

日期：2026-08-19。状态：`INSUFFICIENT_BALANCED_PILOT_SUPPORT`。

## 目的与冻结矩阵

三 client smoke 已过工程门；本 pilot 只判断平衡生产是否能稳定产生足够的可评分节点和真实 sibling 支持，
不比较 client 分数、不训练 critic、不计算 winner/accuracy。

固定 `3 clients × 2 tasks × 2 seeds = 12 physical runs`：DeepSeek v4 Flash、Qwen3 Coder Flash、GLM-5；
任务为 `spooky-author-identification`、`spaceship-titanic`；seed=`1402,1403`。每行 MCTS step=4、
execution timeout=300 秒、run cap=1800 秒、1×RTX3090。为服从 QOS=4 jobs，按 task×seed exact
stratum 切成 4 个 shard jobs，每个在同一张卡上顺序跑三 client；顺序冻结为 D-Q-G / Q-G-D / G-D-Q /
D-Q-G，使三个 client 的先/中/后位置尽量平衡。每 shard 2 小时 15 分钟，硬上限仍为 9 GPU·h。成功路径
约 72 次 operator API 调用；代码抽取重试协议上限 144 次，另有三次 one-token probe。

## 冻结支持门

完整性要求 12/12 rows 的 source/control commit、resolved/final 四 operator client、task/seed/budget、
checkpoint/journal/search、Slurm rc 全部一致，且 env dump=0。支持 GO 还要求：

1. 每 client 至少 2/4 runs 含至少一个 finite、valid、非根候选；
2. 合计 valid 非根节点至少 18；
3. 按相同 parent 形成的 finite sibling pairs 至少 6；
4. 每 client 至少 1 pair，最大 client pair share 不超过 0.60。

任一完整性项失败则 `INVALID`；完整性过而支持门失败则 `INSUFFICIENT_BALANCED_PILOT_SUPPORT`，不降门、
不换 task/seed 拼结果。GO 也只授权另立更大 acquisition 预注册，不授权在这 12 runs 上挑模型、超参或结论。
verifier 只报告 finite/valid 布尔支持计数，不输出数值成绩，不计算 winner。

## 13 项预检

1. manifest 明确列出 12 行，不靠运行时随机分配。
2. 三 client 在每个 task×seed exact stratum 都有一行。
3. 三家 one-token probe 后才提交。
4. source/control 使用同一 immutable commit。
5. 三个生产 client YAML 与 probe matrix 有测试绑定。
6. worker 在运行前核验 resolved config 四 operator。
7. final config、journal/state/search 由独立 verifier 再验。
8. 新 issue/root/seeds，不复用 smoke outcomes。
9. 不读取 frozen/test/vault，不训练模型。
10. key 只 source 远端 `.env`，`logger.write_env_vars=false`。
11. 四个 stratum shard 各 1 GPU×2.25 小时，Slurm 硬上限 9 GPU·h；API 成功路径 72、上限 144。
12. 逐 client/task 报支持与失败，不用 pooled completion 掩盖。
13. pilot 不作 effect；更大生产必须另立预算、manifest 与门。

## 结果与冻结裁决

source/control commit=`79bc2bb6e5bb86b7cc60c61bed5cdcf6cdd7c692`。四个 shard jobs
`11198/11199/11200/11201` 均 `COMPLETED 0:0`；12/12 physical runs、48/48 journal rows、12/12
worker rc=0，完整性检查通过，env dump=0。四个一 GPU作业合计 9,373 秒，即
2.6036111111111113 GPU·h。

冻结支持计数为：valid-run DeepSeek/Qwen/GLM=`4/0/3`，valid 非根节点=`7/0/4`，finite
same-parent sibling pairs=`3/0/0`。因此总 valid 节点 11<18、总 pair 3<6，Qwen/GLM 没有 pair，
最大 client pair share=1.0>0.60，五项支持 predicate 全部失败。按预注册裁决为
`INSUFFICIENT_BALANCED_PILOT_SUPPORT`，不降门、不放大原三 client 矩阵、不报告 client score。

独立 verifier 连跑两次逐字节一致，SHA=
`7527ef2dec44aff2c4bebeca8a9f4749f11532f3c9b40f20314f3b33809dbd04`；
`score_values_reported=false`，`winner_labels_computed=false`。直接证据见
`phase1/results/balanced_client_pilot_20260819_79bc2bb/`。
