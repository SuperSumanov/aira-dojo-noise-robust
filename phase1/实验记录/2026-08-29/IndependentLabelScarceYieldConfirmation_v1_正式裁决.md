# Independent Label-Scarce Yield Confirmation v1：正式裁决

日期：2026-08-29

正式分类：**`HISTORICAL_INDEPENDENT_LABEL_SCARCE_FULL_EXECUTION_YIELD_NOT_CONFIRMED`**

## 1. 预注册问题与人口

本轮在公开冻结 commit `c7148fbc40ace86441248f7551c3c9b6637b547e` 之后才首次读取 acquisition curves。人口是
0IO 已认证的 strict residual：539 pairs / 1,036 endpoints / 505 parents / 190 physical runs / 36 tasks，四层 v11 overlap
全为 0。318 条 senior test rows 禁用。

primary 是 task/run-balanced closure greedy 对强 `uniform_edge`；预算为 endpoint 总数的 `[1..6]/32`，即
`[32,64,97,129,161,194]`。256 条 uniform trajectories 和 32 条 greedy tie trajectories 都是结果前固定的 nested paths。

## 2. 固定门的正式结果

| budget | uniform-edge median yield | balanced minimum | balanced median | strict median win |
|---:|---:|---:|---:|:---:|
| 32 | 16 | 16 | 16 | fail |
| 64 | 32 | 32 | 32 | fail |
| 97 | 48 | 48 | 50 | pass |
| 129 | 64 | 64 | 67 | pass |
| 161 | 81 | 82 | 84 | pass |
| 194 | 99 | 99 | 103 | pass |

uniform-edge trajectory integral 的 nearest-rank median=`341`；balanced tie trajectories 的 minimum/median/maximum=
`343/353/382`。最差相对中位 baseline 只有 `343/341=1.0058651026392962`，未达预注册 `6/5`。逐点 strict wins=`4/6`，
未达 `5/6`。终点最差 yield=`99` 对 baseline median=`99`，也未达 `11/10`。三个 yield-related gates 全失败，故总分类
必须是 `NOT_CONFIRMED`。

终点 parent/task/run breadth retention 与 task/run anti-dominance 六门全部通过；但这些通过不能救回 primary classification。
不得把 +20% 改成 non-inferiority，也不得删除最初两个相等 checkpoints。

## 3. 独立复验与安全

producer 在 `PYTHONHASHSEED=0/1` 下逐字节一致，result SHA-256=
`aea7a45b1ad3c7213cf90a508e4e0bba42ba72bfdd4ca9fca539e309d953622d`。non-importing verifier 使用独立 senior/v11 decoder
和独立 acquisition engine 重建全部 trajectories、summaries 与 gates，两次逐字节一致并全字段 exact；verifier SHA-256=
`13b70a87b4d6c4a49091a1684dc2ab0dec5fc8c064d7c994b7f2b2236c431d63`。

focused/full=`29/1580 passed`（47 warnings）；forbidden opens/network/credential filename/blob=`0/0/0/0`。orientation/gap/
grade/outcome/code/prediction/runtime、senior test 与 prospective values 未用；GPU/API/model-fit/base-update=`0/0/0/0`。
remote formal manifest=`a8a45c14b621b3ff959b97cac89f6b73910e4dea673a02203c12632eb4f784fe`。

## 4. 结果后出现的正面 Pareto 假设

虽然 yield 大增益没有独立确认，balanced 的 diversity 行为很稳定：六个 checkpoints 上最差 balanced yield 都不低于
uniform-edge median；终点 balanced median yield=`103` 对 `99`，同时 task breadth=`36` 对 `27`、run breadth=`94` 对
`70`，parent breadth=`94` 对 `96`。终点最差 balanced 也有 yield/task/run=`99/36/92`。

这说明更可能成立的贡献不是“拓扑让标签数大幅变多”，而是**在几乎不损失 pair-label yield 时显著改善 task/run 覆盖**。
但该阈值是在 readout 后形成，不能回写 v1，也不能称 confirmed。下一步只有在第三个未见图上先冻结 Pareto estimand（yield
non-inferiority + task/run breadth superiority）再读曲线，才可能升级为实质性正结论。

正式包：`phase1/results/historical_independent_label_scarce_yield_20260829_c7148fb/`。
