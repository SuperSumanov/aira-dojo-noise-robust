# Run-Split Breadth Pareto Falsification v1：正式裁决

日期：2026-08-29

权威 control commit：`6cdcc928b3b654a8c7df31999cc3e332bccb0269`

固定分类：**`POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE`**。

## 1. 完整性与 support

fresh r2 从公开勘误提交整轮执行。producer A/B 在 `PYTHONHASHSEED=0/1` 下逐字节一致；non-importing verifier A/B 各自从
raw inputs 重建并全字段 exact。result/verifier SHA-256=
`f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042` /
`9025f2e5f3254421a6e1015ef4218fb60cec6ce6c5723307863c505c403f991b`。

full graph=`539 pairs / 1036 endpoints / 505 parents / 190 runs / 36 tasks`。两折为：

- fold0=`278 / 535 / 261 / 90 / 28`；最大 task/run pair share=`23/139,9/139`；
- fold1=`261 / 501 / 244 / 100 / 34`；最大 task/run pair share=`25/261,22/261`。

两折全部 support gates 通过，pair/endpoint/parent/run overlap=`0/0/0/0`，所以 curve 合法计算。focused/full=
`37/1588 passed`（47 warnings）；forbidden/network/credential filename/blob=`0/0/0/0`。GPU/API/model-fit/base-update=
`0/0/0/0`，senior test 与 prospective values 未读。formal manifest=
`223549d32214ab32993d314e9b1d7b63b16ea42bbcb51f532047f04e42df5d77`。

## 2. 哪些门失败

fold1 七个 gate 全过：六点 integrated yield 的最差 balanced 与 uniform median 同为 `259`，pointwise=`5/6`；task/run
integral=`186/122,239/198`，终点 parent=`59/62`，anti-dominance 也过。

fold0 的 breadth、parent 和 anti-dominance 五类门都过，但两个 yield 门失败：

- integrated yield=`274/276=0.99275362318840576`，少 2 个累计 closed edges（`-0.724637681159%`）；
- pointwise only=`4/6`；budget 117 为 `58<59`，budget 133 为 `67<68`，其余四点均不低于 baseline。

因为协议要求两折全部 gate 同时通过，fold1 不能 rescue fold0；不得把 tie-seed minimum 换成 median，也不得把 5/6 降为 4/6。

## 3. 仍成立但只能描述的形状

两折的 breadth 增益方向一致且幅度大：

- fold0 task/run integral=`164/96`（`+70.8333333333%`）和 `262/191`（`+37.1727748691%`）；终点
  task/run=`28/19,63/42`（`+47.3684210526%,+50%`），终点 yield=`67/68`（`-1.47058823529%`）；
- fold1 task/run integral=`186/122`（`+52.4590163934%`）和 `239/198`（`+20.7070707071%`）；终点
  task/run=`34/24,59/45`（`+41.6666666667%,+31.1111111111%`），终点 yield=`64/64`。

因此数据支持的是 **small-yield-cost / large-breadth tradeoff**，不支持“strictly free breadth Pareto”。这仍是同一 graph 的
post-readout internal robustness，不能当 external replication。

## 4. 下一条正方向

失败机制非常具体：现有 balanced greedy 把 breadth 当软惩罚，fold0 在高预算牺牲了各 1 个 closed pair。下一步 development
改为 **yield-guarded breadth optimization**：每个 nested checkpoint 把 topology-only closed-edge yield 硬约束为至少
uniform-edge median，再在可行域内最大化 task/run coverage，并保留 parent/anti-dominance 约束。closed-edge 数只依赖已知
sibling topology，不读任何 label/outcome，因此可以在执行前认证 yield floor。

该方法在当前 graph 上只能做 development/falsification；若结构可行，再把算法、solver、预算和门冻结到下一份未见历史 graph
或未来 immutable corpus 上确认。不得用当前两折重新宣称 confirmatory positive。
