# Decision Semantic Mixture：parent 权重机制消歧条件预注册

日期：2026-08-21T07:28:58+08:00。协议：
`decision-semantic-parent-weight-disambiguation-v1`。状态：
`CONDITIONALLY_PREREGISTERED_BEFORE_V2_RESULT_READ`。

本文冻结时，`decision-semantic-mixture-discovery-v2-exact-config` 的两个 producer 已完成，第一份独立
verifier 仍在运行；尚未读取任何 `summary.json`、`per_task.csv`、accuracy、delta、CI、gate 或 scientific
status。本文只使用已经公开在 exact-config support receipt 中的结构计数，不使用 pair orientation、gap、code、
prediction 或 prospective outcome。

## 1. 为什么必须先做机制消歧

exact-config train 中，Draft 有 3,196 pairs / 135 `(task,parent)` keys，Improve 有 2,044 / 1,576。
因此两类的平均 pairs per parent 分别为 `23.674074074074074` 与 `1.2969543147208122`，相差
`18.253591360440673` 倍。Draft 占训练 pair 的 `0.6099236641221374`，却只占 parent keys 的
`0.07890122735242548`。

原 v2 对每一条 pair 等权。若固定 semantic mix 优于 pooled，它至少有两种解释：

1. Draft/Improve 的条件关系确实不同，specialist 学到了可迁移的 construction semantics；
2. pooled head 被少数大 Draft choice fragments 的重复 pair 过度加权，specialist 只是间接改变了 parent 权重。

第二种解释并不否定一个可用 baseline，但会否定“语义异质性是机制”的强解释。因为这个混杂在结果揭晓前已经
由结构回执暴露，必须现在固定消歧，不能等看到正结果后再挑 weighting。

## 2. 条件触发与停止规则

- 只有 v2 的双 producer、双独立 verifier、安全扫描和 manifest 全部通过，且 scientific status 精确为
  `DISCOVERY_UNLOCK_FUTURE_CONFIRMATION`，本协议才允许运行。
- 若 v2 为 `DISCOVERY_NO_UNLOCK` 或工程 `INVALID`，状态直接为
  `NOT_RUN_PARENT_WEIGHT_DISAMBIGUATION_NOT_TRIGGERED`；不得用 parent weighting 追救旧 test。
- 触发后只运行下述一个固定 2×2；不搜索权重、C、任务、语义子集或阈值。

## 3. 固定输入与 2×2

输入逐字沿用 v2 已绑定的 cards、eligible merged/Draft/Improve、support summary 与 verifier SHA；source 必须
在新 commit 上，且运行前再次核对全部 SHA/bytes/counts。表示、三 heads、代码前 20,000 字符、TF-IDF、LR、
0.5 margin mix、tie 规则和 test semantic identity 都与 v2 不变。

唯一新增旋钮是训练 pair 权重：

- `raw_pair`：每条 pair 权重 1，必须逐值复现 v2；
- `parent_equal`：在每个 head 的训练集内，以 `(task,parent)` 为 cluster，原始 row 权重固定为
  `N_pairs / (N_parents * n_pairs_of_parent)`；对称的正负实例复制同一个权重，因此每个 parent 总权重相同且
  sample-weight mean 为 1。

每种 weighting 都拟合 pooled、Draft、Improve 三个 heads，并报告：

| weighting | baseline | candidate |
|---|---|---|
| raw pair | pooled raw | `0.5*pooled_raw + 0.5*specialist_raw` |
| parent equal | pooled parent-equal | `0.5*pooled_parent_equal + 0.5*specialist_parent_equal` |

## 4. 固定 estimand、推断与裁决

primary 是 parent-equal 行中 `semantic_mix - pooled` 的 merged task-macro accuracy delta。task-clustered paired
bootstrap 固定 20,000 次、seed=`20260823`；secondary `(task,parent)` clustered pair-micro bootstrap 固定
20,000 次、seed=`20260824`。仍完整报告 merged/Draft/Improve micro、task macro、逐任务正/零/负数、margin/tie
与 raw-vs-parent-equal interaction；interaction 只作解释，不另设可追逐门。

只有以下全部通过才裁决为 `SEMANTIC_SIGNAL_SURVIVES_PARENT_EQUALIZATION`：

1. raw-pair 全部聚合、逐任务结果与 v2 逐值一致；
2. parent-equal merged task-macro delta `>=+0.010`；
3. task-bootstrap 95% CI 下界 `>0`；
4. test pairs 至少 10 的 supported tasks 至少 15，严格正 delta 比例 `>=0.60`；
5. Draft 与 Improve 的 parent-equal micro delta 均 `>=-0.005`；
6. 全部输入、split、exact-config、数值、双跑、独立重拟合和安全门通过。

触发后任一效果门失败，状态固定为 `SEMANTIC_RESULT_PARENT_WEIGHT_CONFOUNDED`。这不把 v2 数字改写成无效；它只
禁止把 v2 的正差解释成超越 parent multiplicity 的语义机制。即使全部通过，仍只是已见旧 test 的 retrospective
robustness diagnostic，必须在 future exact-stratum cohort 预注册确认，也不得申 semantic routing/MoE 方法首创。

## 5. 复现与资源边界

- producer×2 + 不 import producer 的 full-refit verifier×2；每个进程 2 weightings × 3 heads，共 24 个 LR fits；
- 单进程、单 CPU 线程、顺序执行；预计总 wall 25--60 分钟、峰值 RAM <8 GiB；GPU·时=0、API=0、checkpoint=0、
  base-LLM update=0、prospective vault read=0；
- synthetic tests 必须覆盖 parent weight mean=1、每 parent 总权重相同、`(task,parent)` 防碰撞、正负实例同权、
  raw 精确回归、tamper fail-closed、producer/verifier 独立性；
- 新目录写入，已有路径拒绝覆盖；先写 staging，全部文件完成后原子 rename；运行两次逐字节比较；
- 13 项 preflight、完整命令/环境/seed、外部 wall/RSS、SHA manifest、filename/content credential scan 全部入包；
  Git 只收聚合结果与回执。
