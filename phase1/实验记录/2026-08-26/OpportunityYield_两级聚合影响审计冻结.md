# Opportunity Yield 两级聚合影响审计：结果前冻结记录

**日期：** 2026-08-26

**状态：** contract 与独立 verifier 正式通过；尚无 prospective effect 结果

**源码提交：** `f97026221e099c11fa1ca8f2c13a95c389bea743`

## 1. 为什么需要这项审计

现有 outcome-blind 结构分析已经表明，真实 MLE-agent search 中不同任务每个 physical run 产生 sibling decision pair 的速率
不同，导致 run-weighted 与 pair-weighted 的 task mix 明显分离。若 closure 后直接比较 pair-micro 与 task/run-macro，实际
差异还可能混入第二种机制：有些 structural pairs 因 truth、共同覆盖或 evaluability 条件不能进入最终分析。

因此不能把 `run → final pair` 简写成单一 pair yield。若不在 outcome 前拆开，揭盲后很容易把有利的聚合口径解释成方法
结果，或者把 structural opportunity production 与 informative filtering 的影响混为一谈。

## 2. 冻结的两级定义

对每个任务 `t`：

- `R_t`：eligible physical runs；
- `S_t`：任何 truth/evaluability filter 前、所有冻结 arms 精确共同覆盖的 structural canonical pairs；
- `I_t`：最终 informative/evaluable exact-common pairs；
- `Y_t=S_t/R_t`：structural opportunity yield；
- `E_t=I_t/S_t`：informative retention。

令 `p_t=R_t/sum R`、`q_t=S_t/sum S`、`r_t=I_t/sum I`，机器实现逐项验证：

```text
q_t = p_t Y_t / E_p[Y]
r_t = q_t E_t / E_q[E]
```

对任一 arm 的 task-level metric vector `a_t`，closure 后必须同时给出 `r·a`、`q·a`、`p·a` 与 uniform-task mean。
`r·a - p·a` 精确分解为：

```text
(q·a - p·a) + (r·a - q·a)
 structural yield   informative filter
```

paired arm contrast 先在完全相同的 pair support 上求差，再执行同一分解。每个 component 与 total 都报告
`range(a) × TV(weights)` sharp bound。这个 bound 只回答“设计上最多可能移动多少”，不能写成实际 bias 或模型 effect。

## 3. 进入条件与失败语义

只有同时满足以下条件才允许运行：

1. chronological first-960 已完成，且独立 closure receipt 成立；
2. arm 与 paired-contrast registry 已冻结；
3. 所有 arms 使用 exact common pair identities；
4. cohort 中每个任务都同时有至少一个 structural pair 和一个 informative pair。

任一任务缺失支持，固定返回 `NOT_IDENTIFIABLE_FULL_TASK_UNIVERSE`。禁止删除该任务、改变 task universe 或改用别的
truth/aggregation 重跑。精确零统一记为 `ON_BOUNDARY`；sign flip 仅作描述性敏感性。

## 4. Authority 与非挽救边界

这项审计不改变：

- generic benchmark 的 task-macro parent-macro headline；
- clean scaling 与 component-breadth 各自冻结的 primary；
- truth channel、support gate、effect floor、bootstrap/cluster hierarchy；
- first-960 membership 与 closure 规则。

若既有 primary 失败，alternate weighting、两级 component、task subgroup 或 sign flip 都不能救回。审计通过只说明未来分析
规则已经 outcome-before 冻结，不说明 critic accuracy、search utility 或方法效果为正。

## 5. 相关工作边界

cluster size 与 outcome 相关时，cluster-weighted 与 individual-weighted estimand 的区别并非新问题。明确先例包括：

- Williamson, Datta & Satten (2003), *Marginal analyses of clustered data when cluster size is informative*；
- Kahan et al. (2023), *Estimands in cluster-randomized trials: choosing analyses that answer the right question*。

因此不主张 size-biased identity、range×TV bound 或 informative-cluster-size 理论本身的新颖性。我们可守住的本地贡献是：
在真实、chronological、outcome-blind 的 MLE-agent search corpus 中证明 decision-opportunity production 会内生重写衍生
sibling-pair benchmark 的 task mix，并在揭盲前把 structural-yield 与 informative-filter 的实际影响及非挽救规则冻结为
可执行协议。

## 6. 验证结果与诚实失败记录

- focused tests：`17 passed in 0.24s`；
- fresh Linux full suite：`1064 passed, 47 warnings in 77.09s`；
- independent checks：18/18 PASS；
- verifier 在 `PYTHONHASHSEED=0/1` 下逐字节一致；
- contract SHA-256：`49a9e7c659057f1f8e7db032b7b25de14e3de9e594f969df20d3d3f80686cff3`；
- formal `SHA256SUMS` 文件自身 SHA-256：
  `60711365ffe7ccaf00b346a78303c65f2d80fe6a2f5eb99c9d506cad980ecf95`。

公开结果包 commit `bad6ec5428c62b6a213b0d75fa0d1e58d858b5d4` 的 post-push fresh Linux 复现为
`20 passed in 0.42s` / `1067 passed, 47 warnings in 72.20s`；结果包 inner manifest 全通过，两个 verifier replica
与 committed receipt 三者逐字节一致。该次 formal `SHA256SUMS` 文件自身 SHA-256 为
`068322783ea6328c8b9f5c457c3a919d55e6e09bfe1f1d375ae0f5e39f3ee246`。

本地 Windows full-suite 尝试因该环境缺少 SciPy 与 scikit-learn，在旧测试 collection 阶段失败；没有把它伪报成源码失败或
成功。随后使用固定、已有依赖的 fresh Linux worktree 完成 authoritative full suite。另一个在预提交阶段发现并纠正的问题
是初稿把 structural pair production 与 informative filtering 合为一个 yield；最终 contract 已改为上述两级链后才提交。

本次未访问 prospective label/grade/outcome/winner orientation、prediction values 或 raw archive payload；未计算 accuracy、
effect 或 search utility；GPU/API/new-model-fit/base-LLM-update 均为 0。

## 7. 直接证据

- contract：`phase1/contracts/OPPORTUNITY_YIELD_AGGREGATION_AUDIT_V1.md`；
- machine schema：`phase1/opportunity_yield_aggregation_audit_v1.json`；
- arithmetic implementation：`phase1/opportunity_yield_aggregation.py`；
- independent verifier：`phase1/verify_opportunity_yield_aggregation_audit.py`；
- formal result package：`phase1/results/opportunity_yield_aggregation_audit_v1_20260826/`。
- post-push receipt：`phase1/results/opportunity_yield_aggregation_audit_postpush_bad6ec5_20260826/`。
