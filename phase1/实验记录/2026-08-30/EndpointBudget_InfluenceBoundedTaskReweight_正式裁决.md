# Endpoint Budget：Influence-Bounded Task Reweight 正式裁决

日期：2026-08-30

## 结论

formal r1 完整通过工程与完整性链，但按七个冻结门分类为：

`HISTORICAL_SINGLE_FOLD_INFLUENCE_BOUNDED_TASK_REWEIGHT_DOES_NOT_ADVANCE`

这不是纯粹的“没有信号”。七门有 5 门通过；方法相对旧 yield 等权 critic 在两个预算都同时提高 task-macro 与 pair-micro
accuracy，且删除 dominant task 后仍为正。但 terminal calibration 略退化，而且 task-macro/drop-dominant 仍未超过强 uniform
baseline；置信区间跨 0。因此只能保留为机制性正信号，不能晋级或在同一 fold 上继续调公式。

## 结构处理实际做了什么

budget96 的闭式 influence cap 决定 `lambda=0.27033898305084747`：

- task L1：`0.7829313543599258 -> 0.5712744882236407`；
- ESS fraction：`0.9113902886416378`；
- 最大单 pair weight share：`0.04999999999999998`；
- 31 个已选任务覆盖 outer-train availability 的 `0.9600997506234414`。

budget192 的直接 density ratio 已满足两个影响门，因此 `lambda=1.0`：

- task L1：`0.37472469051416424 -> 2.220446049250313e-16`；
- ESS fraction：`0.7407179940998836`；
- 最大单 pair weight share：`0.038847117794486206`；
- 34 个已选任务覆盖 availability 的 `0.9950124688279302`。

结构机制按预期工作，并保留全部 `49/99` 个 yield-induced pairs。

## Efficacy

相对旧 yield：

| budget | task-macro acc | pair-micro acc | drop dominant | log-loss | Brier | task signs + / - / = |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 96 | +0.005352833441068732 | +0.036231884057971016 | +0.009615384615384616 | -0.00006509012884734215 | -0.00003257406873139214 | 4 / 2 / 14 |
| 192 | +0.08566095669036845 | +0.021739130434782608 | +0.028846153846153848 | +0.0005388794995246778 | +0.0002654579027394411 | 6 / 3 / 11 |

task-macro bootstrap 95% CI：

- budget96：`[-0.04763736263736264, 0.05185079993535874]`；
- budget192：`[-0.00446218487394958, 0.21191533344106867]`。

相对 uniform 的 terminal pooled accuracy 为 `+0.057971014492753624`，但 task-macro=`-0.018359728506787333`、
drop-dominant=`-0.009615384615384616`。因此失败的两门是：

1. terminal new-old yield 的 log-loss/Brier 不退化；
2. terminal new-uniform 的 pooled/task-macro/drop-dominant 三项同时不退化。

其余结构、L1、双预算 task-macro、terminal pooled 和 task-sign 门通过。

## 完整性与范围

- control commit=`d768cb2ffefd8fc1a9a74cf07e02a2a9ed8fabd7`；
- protocol SHA-256=`0cabba460cc6a0acc65b60a0271177dfc6d98c1d80b5e9a4453f286ed134f885`；
- formal/postflight manifest=`df1df724c72f8a34fdb1ebc6059755cf04cc09ac2ca15cc44ff6c774bc0f6273` /
  `92f9e4b0c1b11caec8a3426ab74a2c9beed833053d6e3640315ac5570e9cd762`；
- 5,240 个 formal manifest members 零失败；A/B + fresh C verifier 逐字节一致；
- focused/full=`37/1663 passed`，48 warnings；
- 公开包与结果一致性测试加入后，发布前 focused/full=`44/1670 passed`；
- 五类 scanner bytes 全为 0；私有文件 0400；
- historical source 全为 `intask_split=train`；senior test 与 prospective values 未读；
- 2 CPU fits，GPU/API/base update=`0/0/0`。

公开包：`phase1/results/endpoint_budget_influence_bounded_task_reweight_20260830_d768cb2/`。

## 后续裁决

不在 fold0 上尝试新的 exponent、clip、calibration 或任务删除。当前更可靠的正方向优先级是：

1. 把本结果作为“pair acquisition 与 effective task weighting 必须联合审计”的 benchmark 证据，而非新方法胜利；
2. 等未触碰新 physical runs 后，只有另行冻结且不依赖本 fold 选公式的机制才可确认；
3. 方法线转向学长已观察到的 exact-experiment split 容量 scaling，并先完成不触碰 frozen cohort 的矩阵、checkpoint 选择与
   GPU·时预算；
4. OpenRouter 全上下文 panel 已结构就绪，但凭据必须由用户或学长直接安全装入远端 `.env`，当前不得从聊天转存。
