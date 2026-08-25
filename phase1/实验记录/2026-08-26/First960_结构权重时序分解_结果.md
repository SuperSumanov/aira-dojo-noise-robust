# First-960 结构权重时序分解结果

日期：2026-08-26

固定 snapshot：`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1`

结果前协议：`First960_结构权重时序分解_结果前冻结.md`

## 一句话结论

first-240→first-339 期间，run 层任务覆盖持续变均衡，而 pair 层任务权重持续变集中；机会产率变化解释了约 64.47% 的
pair-HHI 增量和约 59.51% 的 run→pair TV 增量。反转方向通过全部晚期时间点和全部单任务删除攻击，但 96.42% 的 pair-HHI
增幅可归因于一个 5-run 高产率批次，因此最强结论必须写成“**符号可泛化、幅度受批次影响**”。

## 结果表

| 指标 | First-240 | First-339 | 增量 |
|---|---:|---:|---:|
| Run HHI | — | — | `-0.007095167549882084` |
| Pair HHI | `0.08303759912408124` | `0.1357471491993994` | `+0.05270955007531816` |
| Run→pair TV | `0.2750745424635` | `0.337082500713674` | `+0.06200795825017402` |

固定门结果为 G1 PASS、G2 FAIL、G3 PASS、G4 PASS：

- G1：260/280/300/320/339 为 `5/5` 持续反转；
- G2：最大单批次 attribution=`0.9641733656841007`，失败；
- G3：`30/30` 个删任务攻击保留反转，删除 pair-dominant OSIC task 也保留；
- G4：yield 对 pair-HHI/TV 增量的份额分别为 `0.6446576519060645` / `0.5951060527094302`。

删除造成 G2 失败的 0820 OSIC 批次后，pair-HHI 增量仍为 `+0.001888405775504004`、run-HHI 增量仍为
`-0.007279189126736543`；删除整个 OSIC task 后，两者仍分别为 `+0.0026450815411386136` 与
`-0.008064315542060704`。这支持方向性机制，但明确否定“幅度不是单批次 artifact”的强表述。

## 解释边界

成立：真实搜索过程中 task-specific decision-opportunity yield 会改变 pair-micro benchmark 的隐式任务混合；只按 run 数观察
数据平衡会漏掉这一层；benchmark 应记录 sampling hierarchy、报告 task-macro estimand 并披露 drop leverage。

不成立：critic accuracy 已提高；某种 predictor 更优；搜索 utility 改善；pair 数是独立样本量；当前幅度可外推到 first-960
最终 cohort。

## 复现与证据

正式源码 commit=`57561d8114e3e284c658e2733e1749cdfc1a4cd3`。producer/verifier 各双跑逐字节一致；Linux focused/full
为 `5/1047 passed`；syscall exact-path audit forbidden hits=`0`；GPU/API/base update=`0/0/0`。完整产物位于：

`phase1/results/structural_weight_trajectory_7cda_20260826/`
