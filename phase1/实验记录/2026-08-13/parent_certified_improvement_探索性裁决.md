# parent-certified improvement：探索性裁决（2026-08-13）

## 裁决

**BORDERLINE；关闭该回顾性规则，不进入前瞻确认。**

冻结规则是：默认使用 `stdout_only`；只有当 parent 存在部署时可访问的历史 pristine 搜索分数，
且某个 120 秒 artifact 的 pristine 分数按任务方向严格优于 parent 时，才以该 artifact 覆盖 stdout。
规则、输入 SHA、支持门、效应门、聚类推断与 seeds 均在读取策略结果前冻结。

## 冻结结果

- 审计总体：100 sibling sets / 230 candidates / 52 physical runs / 19 tasks；88 个 parent 有有限分数。
- 证书支持：24 sets / 14 runs / 7 tasks。
- parent-certified top-1：0.5683；stdout-only：0.5383；配对差 **+0.0300**。
- run-cluster bootstrap CI：[-0.0235,+0.0833]。
- task-cluster bootstrap CI：[-0.0114,+0.0735]。
- run-level exact sign：4 positive / 2 negative / 46 ties，双侧 p=0.687500。
- hard/easy 次要分层：+0.0400 / +0.0200；不得替代 headline。
- 相对 naive cascade：-0.0400；run-CI [-0.0842,-0.0051]，task-CI
  [-0.0833,-0.0088]。但只有 4 个 informative runs 且 sign p=0.125000，不能宣称独立确认更差。
- 成本：set-macro 0.2720（主口径）；aggregate 0.0586（仅次要口径）。
- 不导入主实现的独立复核通过：point estimate、support、sign、anchors 与 counts 全部一致；其
  main run/task CI 为 [-0.024096,+0.084211] / [-0.011628,+0.074468]。

预注册要求支持至少 15 sets / 8 runs、差值至少 +0.08、run/task CI 下界均严格大于 0、run sign
p<0.05、LOTO 最低值大于 -0.10、macro cost 不超过 0.35。规则只通过支持、LOTO 与成本门，未通过
效应量、双聚类 CI 与 sign 门，故为 **BORDERLINE**，不是正结果。

## 机制解释边界

结果只支持一个很弱的方向性信号：以 incumbent 为锚点可能缓和一部分 artifact 可观测性偏差，
但现有证据不足以支撑方法主张。它也没有推翻前一个分解：artifact 的 pristine 分数在已观测条件下
有用，而 artifact 的及时可用性本身是负向选择信号。后续若方法化，应把早期 artifact 看作
selectively observed / censored feedback，联合建模“是否可观测”和“可观测时的分数”，而不是继续
堆叠确定性回退规则。

## 完整性与失败记录

1. 第一次干净执行在任何策略结果产生前，因为脚本残留旧语料计数 12,383 而 fail-closed；实际锁定
   SHA 对应 14,323 cards。只修正计数及相同前置断言后重新提交，未改规则、门、输入或 seeds。
2. 随后一次 launch wrapper 误指向旧 v1 脚本；旧 worktree 存在检查立即拒绝，未执行分析。
3. 正式结果来自全新 clean worktree；提升入库前逐文件 SHA-256 比对通过。
4. parent lineage、同 physical run、parent 早于 children、task/orientation 一致性均在 outcome 前由
   独立前置审计验证。
5. parent `graded` 可追溯到外部 `mlebench grade-sample` 评分，但历史行没有逐条保存 grader binary
   hash/version/data SHA。因此本实验只能作为回顾性机制审计；前瞻实验必须逐 run 固化这些 provenance。

## 后续边界

- 旧 100-set 发现集对 selector 开发正式关闭：不再扫 margin、threshold、fallback、任务规则或子集。
- 唯一确认性主实验仍是机制冻结后新产生的至少 150 physical runs 上，严格共同候选的
  `sub_score - stdout_val` 比较；本结果不改变其预注册与预算。
- 若开发删失感知方法，只能使用新的 discovery split，并保留独立 validation/test、run/task 聚类
  推断和固定成本口径。

结果目录：`phase1/parent_certified_v9/`。
