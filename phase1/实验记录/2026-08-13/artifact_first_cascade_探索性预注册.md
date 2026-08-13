# 120 秒 artifact-first cascade：探索性裁决预注册（2026-08-13）

状态：**规则冻结，尚未运行本文件定义的配对统计**。

## 诚实边界

本实验复用机制发现集，不能成为独立确认实验。既有 `coverage_escalation_v9` 已暴露
`sub120_available` 与 random 的全体点估计（0.5783 vs 0.4598），因此不得把本次包装成盲测。
本次新冻结的是：coverage-complete cascade、同成本 stdout 对照、机制分解、聚类推断和杀死条件。
它只负责决定该候选是否值得在新 physical runs 上前瞻复现。

## 唯一问题

对同一真实 sibling set 的所有候选各运行 120 秒后，下面这个不需要 critic、也不补跑 silent
候选的策略，能否比同成本 stdout-only 策略更常选中最终外部最优 endpoint？

`artifact_score_then_stdout`：

1. 若至少一个候选产生可由 pristine grader 评分的 schema-valid `submission.csv`，只在这些
   artifact candidates 中按 `sub_score` 选择；
2. 若没有可评分 artifact，则在具有 worker 原始 `stdout_val` 的候选中按该值选择；
3. 若两种信号都没有，则在完整 sibling set 上均匀随机；
4. lower/higher-is-better 只读冻结的 `task_orientation.json`；所有并列用解析期望 top-1，
   不实际抽随机数。

策略不混合两个数值尺度：一旦存在 artifact，stdout 不参与该 set 的排序。

## 冻结输入

| 输入 | SHA-256 | 固定计数 |
|---|---|---:|
| `fidelity_manifest.jsonl` | `77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef` | 230 cards / 100 sets |
| `fidelity_results.jsonl` | `b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d` | 460 rows；每 card 各 30/120 秒 |
| `fidelity_runtime_v9.jsonl` | `dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7` | 230 cards |
| `card_run_map.json` | `3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30` | v11 映射，v9 card 映射零漂移 |
| `task_orientation.json` | `e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a` | 冻结方向 |

总体必须恰为 100 sets / 230 children / 52 physical runs / 19 tasks / 50 hard + 50 easy，
且每 set 只能有一个 task、stratum 和 physical run。任一 SHA、计数或覆盖不符立即 abort。

## 对照与机制分解

- `stdout_only`：有 finite stdout 就按 stdout 选，否则完整 set 均匀随机。
- `artifact_presence_then_stdout`：有 artifact 时在 artifact candidates 中均匀选；否则与
  `stdout_only` 相同。它只测“及时产出 artifact”这一 liveness 信号。
- `artifact_score_then_stdout`：主策略；与 presence 版本的差只来自 `sub_score` 数值。
- `artifact_score_then_random`：有 artifact 按分数选，否则完整 set 随机；用于复现既有口径。
- `random`：完整 set 均匀随机。
- `full_oracle`：按最终 `graded` 选，必须 top-1=1、regret=0，仅作正控。

原始 worker 的 keyed 与 bare parser 输出均保留；`keyed-only` 只作稳健性审计，不能替换 headline。

## 指标与推断

主比较固定为全 100 sets 上
`artifact_score_then_stdout - stdout_only` 的 tie-aware endpoint top-1。

- 主聚类：physical run；次聚类：task；10,000 draws，seed=20260813。
- 同时报 run-level 双侧 exact sign test；run effect 为该 run 内 paired set effects 的均值。
- 报 task leave-one-out 最小/最大 effect；不得删任务改善结果。
- 报 hard/easy 分解、mean rank、mean/median raw regret、artifact/stdout 覆盖和实际 120 秒成本占
  历史 all-full runtime 的比率。
- 机制分解为 `score - presence` 与 `presence - stdout`；两项是 secondary，并用 Holm 校正。

## 冻结裁决

- **CASCADE-GO**：主差值 ≥ +0.08，run- 与 task-clustered CI 下界都 >0，run sign 双侧
  p<0.05，task-LOTO 最小差值 >−0.10，且 120 秒成本比 ≤0.35。
- **CHANNEL-GO**：在 CASCADE-GO 之外，还要求 `score - presence` ≥+0.03 且 run-CI 下界 >0；
  否则只能说 artifact readiness/liveness 有用，不能归因于分数数值。
- **BORDERLINE**：主点估计 >0 但任一 GO 门未过；只保留为前瞻候选。
- **KILL**：主点估计 ≤0、run-CI 上界 ≤0，或发现输入/方向/parser/聚类错误。

无论结果如何，不修改阈值、不增加按 task/coverage/child-count 挑选的 headline，不在同一发现集
继续搜索新规则。若 GO，下一步只能在机制冻结后新 physical runs 上按同一规则复现。

## 首次运行后的测量口径修正（结果提交前）

首次 clean-worktree 运行后、任何结果入库前的独立审计发现两处**不改变策略、top-1、聚类或
GO 效应阈值**的报告口径问题：

1. 跨任务 raw regret 的量纲不同，不能求跨任务均值。最终只保留 median raw regret，并增加
   每 set 以 `[best,worst]` 范围归一化的 regret；配对均值只用于 normalized regret。
2. `sum(120s wall)/sum(full runtime)` 会被少数超长任务主导。成本同时报告 aggregate ratio 与
   每 set ratio 的 macro mean，原 `≤0.35` 实用门采用更保守的 macro mean。

这两项在修正 commit 后从锁定输入重新运行；首次临时产物保留在独立 `/tmp` worktree 作失败/修正
审计，不进入论文结果。主 top-1 裁决规则保持原样，禁止借此重新选策略或阈值。
