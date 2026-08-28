# Task-balance 887 外延：任务集合扩张 KILL 与失败链

状态：`TASK_UNIVERSE_CHANGE_KILL_INDEPENDENTLY_VERIFIED`。本项没有产生 cap 或方向性 balance 结论。

## 两次正式尝试

结果前协议在 commit `e8c74260310ee5bbbffe2f55d082214a3c002a2e` 冻结：固定 887 快照、25% dominant-task
cap，并按 `CAP_PASS`→`DIRECTIONAL_BALANCE_GAIN_ONLY`→`NO_BALANCE_GAIN` 解释；任何 task-universe
变化属于 kill condition。

第一次正式尝试在科学计算前退出：远端默认 `/usr/bin/python` 没有 pytest，focused test 输出为 0 bytes，
forward JSON 不存在。失败目录与 deployment receipt 均保留，不能引用为科学运行。

commit `1e5f949856430e297daf2a8ed783af5e4a08b2e1` 只增加一行，显式激活既有 `venvs/exp`；没有改
snapshot、阈值、统计量或解释顺序。第二次 focused=`4 passed`、full=`1238 passed, 47 warnings`，随后 producer
在冻结检查处以 `TASK_BALANCE_FORWARD_V2_ERROR: task universe changed` fail closed。没有产生
`forward_a.json` 或 `classification.json`。

## 独立复核

独立 postflight 只读取两个 hash-bound accumulator summary 的 task-key sets，不读取每任务结果值、label、outcome、
prediction 或 balance 指标。它重建出 baseline/current task universe=`30/34`、新增/删除=`4/0`；两个 canonical
task-set digests 分别为：

- `e408a4c9bc37cbd54461b51988583f5a32775de39be45f60d6666de651353e51`；
- `039758b3a7144c60231564e977b39aecdae54f0761fe627eddbb365414302b00`。

postflight root：
`/research/d7/spc/yzyang4/task-balance-structural-extension-887/postflight-task-universe-kill-1e5f949-v1`；
其 `SHA256SUMS` 文件 SHA-256 为
`2fca093bdb43462ed506208b33d77fa0c482c9236ea04527f598f9d70adce9e1`。

## 裁决与边界

不得把新任务按 0 回填后在同一 887 快照重跑 v2，也不得引用已知总 pairs 推算方向分类。允许报告的正面结构事实只有：
任务覆盖从冻结 baseline 的 30 扩到 34，且没有旧任务退出；这不是 task-balance cap 通过证据。

若继续 balance accrual，必须先实现允许 baseline-task set 为 current-task set 子集、并对新增 task 做显式零扩展的 v3，
用 synthetic/adversarial tests 验证后，只冻结到 887 之后第一个尚未出现的稳定 snapshot。v3 不得回看 887 来 rescue
本项。GPU/API/model-fit/base-update=`0/0/0/0`。
