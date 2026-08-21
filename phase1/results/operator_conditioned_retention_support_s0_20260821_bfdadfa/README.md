# Operator-conditioned retention S0

正式状态：`INSUFFICIENT_OPERATOR_CONDITIONED_RETENTION_SUPPORT`。控制 commit：
`bfdadfade59b69a2c93af0a86e074b13792824c4`。

## 裁决

固定 3,252-parent source-opportunity 表与 16,012-card v11 的 SHA 均通过。3,049 个 parent 能精确连接 card，
join coverage=`0.9375768757687577`；203 个是上游已声明的 absent parent，presence mismatch=0、task/run context
mismatch=0。train/frozen physical-run overlap=0，parent overlap=0。

68 个 task×operator 单元中，9 个单元单独达到 train parents≥20、frozen parents≥10、train runs≥5、
frozen runs≥3。要求同一任务 `Debug` 与 `Improve` 同时合格后只有：

- `leaf-classification`；
- `petfinder-pawpularity-score`；
- `spooky-author-identification`。

因此 complete-contrast support 为 3 tasks/6 cells，未达到冻结的 8/16；361 个 supported frozen parents 中
dominant-task share=`0.6814404432132964`，也未达到≤0.25。S1 明确不授权；不读取 operator-conditioned
retention，不降门、不筛任务。

该结果只能说明当前 v11 对这个非因果 transport estimand 支持不足，不能说明 operator 没有效果。0AM 已因
mixed-operator parent=0 关闭 parent-matched 因果估计；本轮同时表明跨 parent 的 run-robust 替代也不能免费成立。

## 完整性

- producer×2、verifier×2：逐字节一致；独立 verifier 不 import producer；
- focused：`5 passed`；完整 phase tests：`666 passed, 25 warnings`；
- forbidden scientific path、输入/输出秘密、worktree 漂移、正式目录可写文件：均为 0；
- retention value、pair orientation、numeric grade、code/obs、prospective outcome、GPU/API：均未使用。

首次 formal attempt（`60a4f61...`）在第一张 card 因 canonical `task` 对象的机械 schema 映射错误退出，未生成
summary 或 cell 结果；旧目录保留。重试只把 producer/verifier 同步改为 `task.name` 并增加反例，不改协议、输入、
operators、门或停止规则。

关键 SHA-256：

- `summary.json`：`6840622d2f4454c0d85b0cbdbdadb30fb8bd59d4b75882bcd45ffbfd3f30b3ee`；
- `support_cells.csv`：`14d2b781be9ab45ef378d8fb2f28da2f3b58d4e1a55e147d0528b37f699312da`；
- `independent_verification.json`：`b891e70bb5222b95a0f1eb88662342eaf9c2ffdb1f2c1993807d68fc969b1ca8`；
- 远端完整 `SHA256SUMS`：`7b3de27bfb7bf61883ea571047cb1a7f558a7f0d5b19fff569344ed791423ed8`。

完整只读远端产物：

`/research/d7/spc/yzyang4/operator-conditioned-retention-support/bfdadfa-v1`
