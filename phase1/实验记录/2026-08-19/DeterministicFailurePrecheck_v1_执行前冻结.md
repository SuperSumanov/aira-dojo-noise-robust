# Deterministic Failure Precheck v1：执行前冻结

日期：2026-08-19。状态：`FROZEN_NOT_RUN`。本实验是旧 train-only failure benchmark 上的一次
retrospective feasibility audit，不是前瞻确认、search utility 或跨 agent 泛化。

## 适应性披露与唯一问题

同一 494 unique-parent success/failure pairs 已用于固定 char-TFIDF LOTO 与 length diagnostics；failure taxonomy
及类别计数也已知。因此本轮无论结果多好，都只能回答：一个由执行契约直接导出的、无学习的保守预检，在这个旧
benchmark 上是否值得进入时间更晚的新 cohort 一次性确认？不得把它写成已确认的方法结果。

冻结本文前没有计算下述 rule 的 catch/false-reject、任务分布或任何效果数。规则不从 494 对拟合参数，不使用
failure category、task、stdout、grade 或 outcome 数值。

## 固定输入、单位与规则

- support summary SHA256=`77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1`；
- code-free pair registry SHA256=`ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747`；
- 494 unique parents / 13 tasks / 126 physical runs；每 parent 恰一 retained execution-success 与一
  evaluator-verified execution-failure code；frozen b0/b1/b2 runs 零交集；
- 使用完整 raw code，仅在内存分析，不截断、不输出；credential-shaped target journal 立即 fail closed；
- `REJECT_SYNTAX`：Python `ast.parse` 抛出 `SyntaxError`；
- 否则遍历 AST。任一 `.to_csv`、`.write_csv`、`.savetxt` 调用视为 conservative writer；或 `open` 写模式、
  `.write_text/.write_bytes/.copy/.copyfile/.move/.rename/.replace` 调用中包含静态字符串
  `submission.csv`（路径大小写不敏感）也视为 writer；
- 可解析但无上述 writer 时为 `REJECT_NO_ARTIFACT_WRITER`；其余为 `KEEP`。writer 出现在不可达分支也会 KEEP，
  这是有意保守，只会降低 catch，不会制造积极结果。

## 固定指标与资格门

以 494 个 parent 为配对单位。failure catch=`reject(failure)`；success false-reject=`reject(success)`；paired net=
两者之差。固定 seed 20260819、10,000 次 task-cluster bootstrap 为 primary，run-cluster 为稳健性；同时报告逐任务、
拒绝原因及 balanced-pair precision，但不外推真实 failure prevalence。

全部满足才记为 `RETROSPECTIVE_DETERMINISTIC_PRECHECK_FEASIBLE`：

1. 恰为 494 pairs / 13 tasks / 126 runs，且 code-free registry 的 child/code SHA 逐对一致；
2. failure catch rate≥0.05；
3. success false-reject rate≤0.01；
4. paired-net 的 task-cluster 95% CI lower>0；
5. 至少 6 个 tasks 各 catch≥1 个 failure；
6. 8 个 n≥20 tasks 的 observed success false-reject rate 均≤0.05。

通过只允许冻结同一 rule 到时间更晚的新 cohort；不允许在旧 494 对上增加 sink、改字符串、删任务或调门。失败则
关闭 v1，不看错误样本后修 v2。

## 十三项执行前检查

1. 方向：D&B failure-memory/decision-cost extension，不恢复 HCE/TD/多保真。
2. 代码：结果前 clean commit；输出新目录，禁止覆盖。
3. 输入：所有 cards/status/taxonomy/frozen-pair/root 继续沿用既有 SHA 锁。
4. 单位：unique parent 配对；不把两个 endpoint 当 iid。
5. 已见结果：TF-IDF/length/taxonomy 已披露；本 rule 效果未计算。
6. 特征：仅 AST syntax 与 artifact-writer contract；无 learned feature/阈值。
7. 泄漏：frozen runs 排除；不读 numeric grade，failure/success status 仅作 train-only benchmark 标签。
8. 安全：journal bytes 先 credential scan；raw code 不落盘、不输出。
9. 统计：task-cluster primary、run-cluster secondary、逐任务与原因全报。
10. 复现：producer 双跑逐字节一致；匿名 per-pair feature artifact 由不 import producer 的 verifier 重算统计。
11. 资源：CPU-only，预计<15分钟；GPU=0、API=0、底座更新=0。
12. 失败：任一 SHA、registry identity、pair 数或安全门变化即 fail closed。
13. 停止：旧 cohort 只跑一次固定 rule；通过仍必须用新 temporal cohort 确认，失败不救活。
