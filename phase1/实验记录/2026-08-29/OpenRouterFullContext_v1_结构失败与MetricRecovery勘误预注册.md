# OpenRouter full-context v1：结构失败与 metric recovery 勘误预注册

## 已观察失败链

1. `8ead91f` 已在任何真实 panel readout 前冻结原协议；r1 fresh worktree 因无关旧 LFS object 404 退出，没有读 pair/card。
2. r2 改为 no-smudge，同一协议未变；在遇到相关 Card 的空 `task.metric` 时退出，没有 panel。
3. `c06a77b` 把缺 prompt 元数据改为既有 eligibility 的候选拒绝，而不是全局 parser crash；r3 仍在 selection 前退出。
4. aggregate-only census=`7a3ac11f...8647`：两个历史 test 输入的 2,208 个唯一 endpoint 中，task 描述、metric direction、
   client、hardware、time limit、execution timeout 与 code 均 0 缺失，只有 `task.metric` 为 2,208/2,208 缺失；因此
   endpoint-only 解释使八个 panel×gap strata 全为 0 eligible。这是 schema lineage 问题，不是 evaluator 效果结果。

所有失败 root 均无 `COMPLETE`；prospective values、API 输出、模型结果未读，GPU/API/model-fit/base-update=`0/0/0/0`。

## 勘误规则（在 run consensus readout 前冻结）

原协议要求 prompt 包含 metric name，但没有规定该字符串必须来自 endpoint Card 自身。Cards 的 task 元数据在同一 run 的
root/其他记录上可能更完整。因此冻结以下唯一允许的 schema recovery：

- 键为 `(physical_run_id, task.name)`；
- 在原协议已绑定、已凭据扫描的 Cards 中收集该键下所有非空字符串 `task.metric`；
- 不做大小写归一化、strip 后 alias、人工映射、网页查询或从 task description 猜测；
- distinct 值恰为 1 时，endpoint 的空 metric 才可从该共识回填；endpoint 若已有值，也必须精确等于共识；
- distinct 值为 0 或大于 1 时，该 pair 分别以 missing/ambiguous consensus 拒绝；
- metric source 不发送给 provider，只发送恢复后的 metric 字符串。

机器协议为 `openrouter_full_context_metric_recovery_erratum_v1.json`。冻结时尚未读取 run-task consensus 的覆盖、歧义、
恢复后 eligible strata 或任何 selected identity。原协议的两个 panel、4 桶×8 配额、run/endpoint/task 限制、exact resource
stratum、完整 code、模型、双方向、隐私和 2/10 USD stop 全部不变；仍不授权 live calls。

若恢复后任一桶仍不足 8，v1 按 `RUN_TASK_METRIC_CONSENSUS_RECOVERY_PANEL_INFEASIBLE` 停止，不继续增加 fallback 或缩配额。
