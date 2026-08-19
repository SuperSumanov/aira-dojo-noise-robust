# BalancedContinuation E2-A：1200 秒边界不稳定执行审计（2026-08-19）

状态：**六任务 warm 资格门失败；formal 未提交；本协议下 E2-A 关闭且不补跑**。

## 1. 执行边界

- source commit：`0ee657a14a9bba0ddf58670f177e9e103c33720a`；
- warm root：`/research/d7/spc/yzyang4/balanced-e2a-warm-smoke-0ee657a-a1`；
- 首批 array job：`11232`，slots 0--3；
- 冻结矩阵：六个固定 assignment、4+2 顺序 chunks、每 candidate 1200 秒、0 API、0 retry；
- 解锁条件：六任务从零 6/6 capability/producer/verifier/safety rc=0，之后才允许 formal。

launcher 在提交前通过 434 项远端 Linux tests、13/13 preflight、独立全 cache 543-entry 重哈希以及
secret filename/content scan=0。不可变 cache 的 manifest SHA 为
`fed0649b91372ce6c40d75a64be7b17f87cfc091fb66bc0b53b2d834be3daad0`，payload SHA 为
`5786d13a522dce0a827cdacae515a3fe89aacfebf7f8927ce19be6398d39f901`。

## 2. 观察结果（仅公开执行回执）

首批四项中三项完整通过：

| slot | task | candidate wall (s) | execution | 四层 rc |
|---:|---|---:|---|---|
| 0 | spaceship-titanic | 7.048006015946157 | ok | 0/0/0/0 |
| 1 | tabular-playground-series-may-2022 | 1200.2556150490418 | timeout | 0/3/-1/-1 |
| 2 | spooky-author-identification | 87.6522306620609 | ok | 0/0/0/0 |
| 3 | us-patent-phrase-to-phrase-matching | 5.995276015950367 | ok | 0/0/0/0 |

实际 candidate wall 总和为 `1300.9511277429992` 秒；Slurm 四个元素累计 `1808` GPU 秒
（`0.5022222222222222 GPU·h`）。TPS candidate return code=143、artifact SHA=null；其余三项 artifact
shape 合法。四项均为 API calls=0、candidate retries=0、private mounts=false，且
`dsearch_rows_read=dval_rows_read=dtest_rows_read=0`、`labels_opened=false`、`outcomes_read=false`、
`external_score_or_gain_reported=false`。

monitor 在 `2026-08-19T12:45:24Z` 写入 `CHUNK_GATE_FAILED`，第二批 Nomad/Essay 没有提交。follow-up
在 `2026-08-19T12:45:27Z` 写入
`FOLLOWUP_STOP warm_status=E2A_WARM_CHUNK_FAILED formal_not_launched=true`；目标 formal root 经检查不存在。

## 3. 跨 run 可重复性对照

与 0BG 的旧 warm slot 1 对照：

| 项目 | 旧 run (`81e0535-a1`) | 本 run (`0ee657a-a1`) |
|---|---:|---:|
| candidate code SHA | `b3e02d...f4163f` | `b3e02d...f4163f` |
| public data gate | `balanced-e2a-data-81e0535-a1` | 同左 |
| container / node / allocation | 同一 container；gpu27；6 CPU/1 GPU | 同左 |
| candidate wall (s) | 1119.5009202449583 | 1200.2556150490418 |
| status | ok，artifact present | timeout，artifact absent |

完整 code SHA 为 `b3e02d2f3e2452395a08e2df53f64cad1ed0242a280e200dfee8d9a821f4163f`。
旧执行在 CV 后的 final fit 于 iteration 1878 early-stop；本次五折的 early-stop/最佳 iteration 序列明显不同，
进入 final fit 后触及 1200 秒上限。候选固定了 `StratifiedKFold` 与 `train_test_split` 的 random_state=42，
但 LightGBM GPU 参数没有显式 `seed`/`deterministic` 设置。

直接成立的结论仅是：**该冻结候选在 1200 秒边界的 terminal artifact 可用性不可重复**。具体漂移究竟由
GPU histogram 数值非确定性、LightGBM 内部随机路径还是瞬时系统负载贡献，当前两次运行不能辨识；不得把
任何一个猜测升级为已证明根因。TPS 不调用 DeBERTa，因此该失败也不支持“safetensors 修复无效”。

## 4. 预注册裁决

本 warm 的 6/6 解锁条件失败。按结果前写明的 `0 retry / no partial supplement / no formal`：

1. 不提交第二批，不单独补 TPS，也不借旧 warm 的 TPS/其他 task 拼接 6/6；
2. 不提高 timeout，不改变 candidate、task、parent/sibling、并发或预算后继续沿用本次授权；
3. 不打开任何分数、标签或 sealed outcome；
4. E2-A formal 在本协议下关闭。本结果是**资格/测量可重复性失败**，既非正方法结果，也非负方法结果。

未来若要重开，只能新预注册以下二选一并重新做预算授权：一是把 runtime timeout 明确纳入 censoring/terminal
hurdle estimand；二是改用与最坏运行时间有充分余量的统一 timeout，同时重新计算 candidate hard cap。当前
优先级返回评分通道的前瞻主线，不继续消耗 E2-A API/GPU。

## 5. 可审计回执

Git 内紧凑回执：
`phase1/results/balanced_continuation_e2a_warm_timeout_20260819_0ee657a/audit.json`。
其中记录 current/old process 与 execution 文件 SHA、四个 job rc SHA、monitor/final-status SHA 和远端根；
不包含 candidate stdout、标签、分数、密钥或 scientific outcome。
