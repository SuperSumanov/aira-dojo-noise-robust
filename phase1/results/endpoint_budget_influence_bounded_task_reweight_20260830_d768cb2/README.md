# Influence-Bounded Task Reweight：正式结果

权威 control commit：`d768cb2ffefd8fc1a9a74cf07e02a2a9ed8fabd7`

协议 SHA-256：`0cabba460cc6a0acc65b60a0271177dfc6d98c1d80b5e9a4453f286ed134f885`

严格分类：
`HISTORICAL_SINGLE_FOLD_INFLUENCE_BOUNDED_TASK_REWEIGHT_DOES_NOT_ADVANCE`。

## 结果

七个预注册门通过 5 个、失败 2 个。相对相同 endpoint budget、相同 yield-selected pairs 的旧等权 critic：

| budget | task-macro accuracy delta | pair-micro accuracy delta | drop-dominant delta | log-loss delta | Brier delta |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 96 | +0.005352833441068732 | +0.036231884057971016 | +0.009615384615384616 | -0.00006509012884734215 | -0.00003257406873139214 |
| 192 | +0.08566095669036845 | +0.021739130434782608 | +0.028846153846153848 | +0.0005388794995246778 | +0.0002654579027394411 |

两个预算的 task-macro 和 pooled accuracy 都同向改善，positive task 也不少于 negative task；但 terminal calibration 略退化。
相对强 uniform baseline，terminal pooled accuracy 为 `+0.057971014492753624`，task-macro/drop-dominant 却仍为
`-0.018359728506787333/-0.009615384615384616`。两档 task-macro bootstrap CI 都跨 0，故不能晋级。

这支持一个有限机制判断：保留 yield pairs 再做受影响力约束的任务密度校正，比通过 selection 丢 pair 更有希望；但当前
historical fold0 证据不足以证明跨任务稳健优于 uniform，也不能在同一 fold 上换权重公式继续追结果。

## 完整性

- 13 项 preflight 全过；focused/full=`37/1663 passed`；
- formal manifest 5,240 个成员、0 失败；
- formal verifier A/B 与 fresh postflight 第三 verifier 逐字节一致；
- 私有 summary/pair witness/checkpoints/verifier 均封为 0400；
- forbidden path、verifier card、network、credential filename/blob 五类扫描均为空；
- senior test 与 first-960/Target-300/Target-522 prospective values 均未使用；
- GPU/付费 API/base-model update=`0/0/0`。

加入本公开包及 7 个结果一致性测试后，发布前 focused/full 回归为 `44/1670 passed`（48 warnings）。

公开文件：`summary.json`、`runs.csv`、`verifier.json`、`formal_receipt.json`、`integrity_receipt.json`、测试与 manifest 回执。
