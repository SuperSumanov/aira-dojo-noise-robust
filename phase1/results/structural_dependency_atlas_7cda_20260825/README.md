# first-960 结构依赖图谱：run 变均衡时，pair 权重反而集中

本目录对 snapshot
`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1`
做纯结构、结果盲的描述性审计。输入仅为 accumulator aggregate summary（SHA-256
`ad3e8fe4...d4585`）和已经独立重建的 structural gate（SHA-256 `ca44845b...eccca`）；CLI 不接受
label vault、outcome、winner orientation、prediction registry 或 score 路径。

## 1. 主要发现

尽管当前 prefix 从 first-240 增长到 339 runs，任务数从 25 增至 30，三种样本权重讲出的“任务多样性”完全不同：

| 任务权重 | first-240 最大任务占比 | 当前最大任务占比 | first-240 inverse-HHI 多样性 | 当前 inverse-HHI 多样性 |
|---|---:|---:|---:|---:|
| physical runs | 0.1083333333 | 0.0914454277 | 17.8660049628 | 20.4594979526 |
| endpoints | 0.1693716857 | 0.2699097685 | 14.0674991127 | 9.5037754223 |
| canonical sibling pairs | 0.1714990746 | 0.3123339658 | 12.0427373930 | 7.3666372067 |

也就是说，新增语料使 **run 权重更均衡**，却使 endpoint/pair 权重明显更集中。当前 run→pair 任务分布的 total
variation distance 为 `0.337082500713674`；pair 主导任务的 pair share 相对它自己的 run share 被放大
`5.041962591488208` 倍。pair 最大任务占比相对 first-240 上升 `0.14083489119912157`，pair HHI 变为原来的
`1.6347672696624505` 倍。

这个结果说明 raw pair 数不是中性的 benchmark 权重。若直接把 2,635 对做 micro-average，headline 会被
“每个任务产生多少 endpoints / decision parents / pairs”共同决定，而不是只反映 339 个 physical runs 的任务覆盖。

## 2. 集中不是由 sibling 两两组合爆炸主导

当前 2,635 个 canonical pairs 来自 2,593 个 decision-parent groups、334 个 finite-decision runs 和 30 个
pair tasks：

- pairs / parent group = `1.0161974546856922`；
- 超出“每个 parent 一对”的部分只有 42 对，占 `0.015939278937381403`；
- 每个 finite-decision run 平均 `7.889221556886228` 对，中位数为 `4.0`。

因此当前 task concentration 不能主要归咎于一个 parent 下大量 siblings 的组合展开；更主要的是任务/run 的 endpoint
和 decision-parent 产量不同。这也解释了为什么 25% pair-share 护栏必须按实际 canonical pair yield 重算，不能换算为
固定 raw-run 配额。

## 3. 对论文 estimand 的直接裁决

该图谱把评估口径固定为：

1. 主点估计用 task-macro，主不确定性用 task-clustered bootstrap + leave-one-task-out；
2. run-macro / physical-run clustered 与 pair-micro 只作次级视图；
3. raw pair count 不得写成独立观测数；inverse-HHI 只称“描述性多样性”，不得冒充统计有效样本量；
4. first-240→当前的变化是已见数据上的 post-hoc 描述，不是预注册效果检验，也没有 predictor accuracy、方法优越性或
   search utility 结论。

这是一条正面的 D&B / benchmark-design 结果：真实搜索树 benchmark 的 headline estimand 必须显式绑定抽样单位，
否则即便 run coverage 改善，pair-weighted evaluation 仍可能朝相反方向漂移。

## 4. 独立复验与失败历史

正式源码 commit=`b8ea5f7e3d30ced33043167ecaffcb363bb4e320`。fresh Linux worktree 的 focused/full
tests 分别为 `7 passed in 0.39s` 和 `1033 passed, 47 warnings in 71.41s`；producer A/B 与独立 verifier A/B
均逐字节一致。正式根目录为
`/research/d7/spc/yzyang4/prepush-structural-atlas/b8ea5f7-v2`，其 `SHA256SUMS` 文件自身 SHA-256 为
`17f41f52d0a4a9da4f32433b46b3a404a1932e0963a2c22691ca09d42e5d221d`。

机器产物：

- `atlas.json` SHA-256=`1c3e5c34afe82a236e4f242373ee7b71fd44d90207eb2d74b9177fb6776db1a5`；
- `independent_verification.json` SHA-256=`634c57840667d4cd9a301fb3d8c8d39e37c161ea1d11872a57ac740d951c150f`；
- `headline_metrics.json` SHA-256=`f6db60ae066323ff3e65944ab24d3c30e18074765f080d4f2618de4bfc86814f`。

四次未接纳尝试均原样保留并进入 `formal_summary.json`：错误测试范围、BLAS 线程爆炸、跨进程末位浮点不确定性、
以及文件名安全门误触发。最终修复加入了所有数值库单线程限制和跨 `PYTHONHASHSEED` 逐字节攻击测试。正式收据的
credential filename/content hits=`0/0`，strace 禁止路径命中=`0`，GPU/API/base-LLM updates=`0/0/0`。
