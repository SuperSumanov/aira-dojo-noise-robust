# Decision Predictor Estimand Panel 结果前冻结

日期：2026-08-25

状态：`FROZEN_OUTCOME_BLIND_BEFORE_FIRST960_CLOSURE`

## 1. 裁决

结构图谱的正结果带来一个必须立刻关闭的 researcher degree of freedom：run-weighted mixture 更均衡时，pair-weighted
mixture 反而更集中，所以不能在 closure 后按哪种 aggregation 显著来决定论文 headline。

通用 benchmark headline 现冻结为：pair tie-aware credit → physical decision parent 内平均 → task 内平均 parent →
tasks 等权。parent 对应真实 logged candidate-choice opportunity，task 等权避免任务的 pair yield 决定 headline。

三个 mandatory non-rescuing views 是 task-pair macro、task→run→parent→pair macro 与 pair micro。前者兼容 scaling
primary，中间一项检查 run yield，后者保留 empirical pair-frequency 视图。四行必须一起报告，禁止结果后只挑一行。

## 2. 不改写旧契约

这是 paper-level reporting panel，不是 superseding amendment。`critic_scaling_confirmation_contract_v1.json` 的 task-macro
pair primary 和 `critic_component_breadth_future_evaluation_v1.json` 的 task-macro parent-macro primary 继续分别控制其
claim；truth、support、effect floor、bootstrap 也仍以各自文件为准。通用面板、subgroup、alternate truth 或 alternate
aggregation 均不能 rescue 失败的实验 primary。

## 3. 推断与缺失

generic headline 固定 20,000 次 task bootstrap、seed `20260901`、SHA-256 deterministic index 与全部 LOTO；
physical-run clustered 为必报 sensitivity，pair-i.i.d. CI 禁止。所有 arm 必须 exact common pair support，并先在 pair 求
paired difference 再做层级平均；预测缺失使 contrast fail closed，不得静默 complete-case 删除。

支持表必须同时给 all/finite-decision runs、tasks、parents、pairs、informative support、truth/prediction ties、按 task/run 的
missingness，以及任务按 run/endpoint/parent/pair 的集中度。raw pair count 不能写成独立样本数，inverse-HHI 只能叫
descriptive diversity。

## 4. 复验

contract SHA=`4f394d0e...7adea`，源码 commit=`1763030c14fee14d3269c1b3991e99b850dfc927`，independent
receipt SHA=`fcb74182...426de`。fresh Linux focused/full=`5/1040 passed`，verifier A/B 逐字节一致，正式根目录
`/research/d7/spc/yzyang4/prepush-estimand-panel/1763030-v1`，`SHA256SUMS` hash=`cd198c5f...3d402`。

strace 禁止路径、credential filename/content hits=`0/0/0`；prospective truth/prediction values 未读，
accuracy/effect/search utility 未算，GPU/API/model fit/base-LLM updates=`0/0/0/0`。
