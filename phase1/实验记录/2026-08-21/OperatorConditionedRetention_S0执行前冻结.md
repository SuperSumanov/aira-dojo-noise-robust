# Operator-conditioned retention S0：执行前冻结

日期：2026-08-21。状态：`NOT RUN`。本轮只裁决跨 disjoint-run train/frozen 角色的身份与支持规模，
不读取或输出任何按 operator 分层的 retention 值，不授权 GPU/API、模型拟合、搜索控制器或因果主张。

## 与已关闭路线的边界

`ProspectiveOperatorSupport_v1` 已确认同一 parent 内 mixed-operator parents=`0`，因此现有语料不能识别
parent-matched operator effect；该因果路线保持关闭。本轮问题更窄：在不同 parents 上，`Debug` 与 `Improve`
是否各自拥有足够的 train/frozen 物理 run 支持，使后续可以测试一个**非因果的条件删失结构 transport**。

冻结前已知全 v11 card 的边际 op 数为 Debug=6,598、Improve=8,723、Draft=691；这些不是新结果。尚未查看的
唯一新信息是 3,252 个 source-opportunity parents 在 task×role×operator 单元中的 parent/run 支持。

## 固定输入、单位与访问合同

- source-opportunity per-parent CSV：3,252 行，SHA-256=
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；
- v11 cards：16,012 行，SHA-256=
  `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- 只使用 CSV 的 `role/task/run_id/parent/parent_card_present` 与 card 的 `id/task/run_id/lineage.op`；
- 不访问 `raw/finite_source_retention`、child counts、pair orientation、numeric grade、code/obs 内容或 prospective
  outcome；代码字段虽然与固定 card JSON 共处同一文件，但分析不引用、不输出；
- 分析单位为 parent，支持单位同时报告 distinct physical runs；train/frozen run 与 parent overlap 必须均为 0。

## 结果前固定支持门

只有全部通过才记为 `OPERATOR_CONDITIONED_RETENTION_TRANSPORT_SUPPORT_FEASIBLE` 并允许另立 S1：

1. parent-card join coverage≥0.90，presence/context mismatch 均为 0；
2. 每个 eligible task×op cell：train parents≥20、frozen parents≥10、train runs≥5、frozen runs≥3；
3. 每个 supported task 必须同时拥有 eligible `Debug` 与 `Improve`；
4. supported tasks≥8、对应 task×op cells≥16；
5. supported frozen parents 的 dominant-task share≤0.25；
6. train/frozen physical-run overlap=0 且 parent overlap=0。

任一门失败即固定为 `INSUFFICIENT_OPERATOR_CONDITIONED_RETENTION_SUPPORT`：不降低 parent/run/task 门、
不筛任务、不把 Draft 删除后追救，也不查看 operator-conditioned retention。过门也只授权另写结果前 S1 协议；
它仍不能声称 operator assignment randomized、within-parent contrast 或 operator causal effect。

## 十三项 pre-flight

1. 方向：failure-censored、task-stratified Decision Corpus 的 D&B 描述性扩展，不恢复旧 HCE/TD/多保真。
2. 代码：producer、独立 verifier、协议与测试在完整 40 位 commit 冻结后运行。
3. 输入：两份不可变输入逐字节 SHA 绑定，行数与 role 数固定。
4. 分母：parent 为基本单位，run 作为独立支持门；不把 child/edge 当 iid。
5. 已见结果：只披露全卡边际 op 数与既有 mixed-parent=0；新 task×role×op 支持未看。
6. 特征：只使用身份与 `lineage.op`，retention/count/grade/orientation/code 均不进入。
7. 泄漏：不打开 prospective、label vault、regrade、score-channel 或 outcome registry。
8. 安全：两输入在 parse 前做 credential-shaped bytes 扫描，输出只含聚合单元。
9. 统计：S0 只报精确支持计数和固定门，不做效果检验或 CI。
10. 复现：producer×2、verifier×2、逐字节 diff、完整 manifest 与 syscall 路径审计。
11. 资源：CPU-only，GPU=0、API=0、底座更新=0；预计含全测试小于 30 分钟。
12. 失败：SHA/schema/context/秘密/路径任一异常 fail closed，旧产物不覆盖。
13. 停止：支持失败永久关闭该 v11 S1；支持通过也先冻结 S1 的 contrast、推断与 kill gates 后才读值。
