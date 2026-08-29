# Endpoint-budget distribution-matched yield：结果前冻结设计

日期：2026-08-30

状态：`FROZEN_AFTER_TASK_HETEROGENEITY_AUDIT_BEFORE_NEW_SELECTION_OR_PREDICTION`

协议：`phase1/endpoint_budget_distribution_matched_yield_screen_v1.json`

协议 SHA-256：`371a5a2d1e57de886995c3ad2c09426c8de813bf3018921d6553380af156c4f4`

## 1. 为什么做这一项

旧 endpoint-budget smoke 在 96/192 endpoints 上有同向 pooled accuracy/calibration 描述性改善，但严格 gate 因
drop-dominant-task 反转而不晋级。随后冻结的匿名 task-heterogeneity 审计进一步显示：

- pooled accuracy delta 为 `+0.021739130434782608/+0.036231884057971016`；
- task-macro accuracy delta 为 `-0.03829778065072183/-0.1040206851971558`；
- terminal task sign 为 `6 positive / 6 zero / 8 negative`；
- yield arm 的 task-distribution L1 在 96 endpoints 从 uniform 的 `0.5776184538653364` 恶化到
  `0.8042139549086468`，192 endpoints 从 `0.3624937655860349` 恶化到 `0.37869971535806946`。

因此当前可证伪机制假设是：pure breadth 将有限 endpoint 标签跨 task 过度摊薄；若在保留 run/parent breadth 的同时，让
诱导 pair 的 task 分布匹配 train-only availability，可能把 pooled 小信号变成不依赖单一大任务的 task-macro 信号。
这是旧结果之后的历史开发假设，不是 confirmation。

## 2. 唯一改变的旋钮

只改变 endpoint acquisition rule。以下全部固定：

- 同一 539-row senior-0819 strict residual firewall，401 outer-train pairs、138 fold0 historical evaluation pairs；
- senior test 行导出数固定为 0；first-960、Target-300、Target-522 的 values 全部禁止；
- nested endpoint checkpoints：`72/96/120/144/168/192`；
- 与旧 yield arm 完全相同的 induced-pair counts：`36/49/61/73/85/99`；
- 同一 code representation、char-TFIDF LR、seed、评价 pair set 与三个指标；
- 旧 uniform/yield predictions 从绑定 witness 重用，不重训旧模型。

## 3. 冻结选择规则

令 outer-train task `t` 可用 canonical pairs 为 `n_t`，总数为 401；checkpoint `b` 的固定诱导 pair 数为 `Y_b`，
被选 pair 数为 `z_{b,t}`。主整数目标为：

`min sum_{b,t} |401 * z_{b,t} - Y_b * n_t|`。

约束在所有六个 checkpoint 同时成立：

- endpoint 数精确等于 checkpoint，且轨迹 nested；
- induced-pair 数精确等于旧 yield arm；
- 每个 task：`5 * z_{b,t} <= Y_b`；
- 每个 physical run：`10 * z_{b,r} <= Y_b`；
- 六个 checkpoint 的 represented-run 数之和至少 317；
- terminal represented-parent 数至少 86。

第一阶段必须由单线程 HiGHS 返回 status=0、mip gap=0；第二阶段固定第一阶段整数 optimum，再最小化预先定义的
SHA-256 endpoint 权重。任何带 incumbent 的 time limit 都不得标作 optimal，任何 A/B selection 漂移均终止。

## 4. 拟合与 estimand

仅在 endpoint budget 96 和 192 各拟合一个新 arm 模型，共 2 fits：

`char_wb TFIDF(ngram_range=(3,5), max_features=30000, min_df=3, sublinear_tf=True)`，接
`LogisticRegression(C=0.5, solver=lbfgs, max_iter=1500, random_state=0)`。

primary screen estimand 是 new minus old-yield 的 task-macro accuracy delta，两个预算都必须为正。secondary 包括 pooled
accuracy/log-loss/Brier、task sign、task/run-clustered bootstrap、terminal drop-dominant-task，以及 selection 的 task-L1。

## 5. 七个结果前 gate

必须全部通过：

1. 96/192 两预算的 new task-distribution L1 都严格低于 old yield；
2. 96/192 两预算的 new minus old-yield task-macro accuracy 都大于 0；
3. terminal new minus uniform pooled accuracy 大于 0；
4. terminal new minus uniform task-macro accuracy 不小于 0；
5. terminal new minus uniform drop-dominant-task accuracy 不小于 0；
6. terminal new minus old-yield pooled log-loss 和 Brier 都不大于 0；
7. terminal new minus old-yield 的 positive-task 数不少于 negative-task 数。

全过的分类仅为 `POST_AUDIT_DISTRIBUTION_MATCHED_YIELD_SCREEN_PROMISING_DEVELOPMENT_ONLY`；任一失败为
`POST_AUDIT_DISTRIBUTION_MATCHED_YIELD_SCREEN_DOES_NOT_ADVANCE`。失败后不得删/重加权 task、改预算、放宽 pair matching、
改 tie-break 或报告另一个 checkpoint 来救回。

## 6. 预检、验证与安全

formal runner 在读取 private labels 前必须完成并写入 13 项 preflight，绑定旧 formal manifest 与 11 个输入 SHA，随后执行：

- 新模块 + 旧 smoke + task-audit focused tests；
- `phase1/tests` 全测试；
- selection producer A/B 逐字节相同；
- 两个原子 mode-0600 fit checkpoints；
- 不导入 producer 的独立 verifier A/B，重建 primal constraints、objective、pair set、aggregate、CSV 和七个 gate；
- selection-stage label/card/prediction boundary scan；全程 prospective/raw-decision/network scan；
- credential filename/blob scan、整棵 SHA256SUMS、COMPLETE 后只读封存。

资源上限：CPU single-thread，预计小于 30 分钟；GPU=0，付费 API=0，base-agent update=0。若 formal 产物未出现 COMPLETE，
不得读取科学结果；若出现未知 hash drift、重复 root、mode 漂移或扫描命中，一律 fail-closed 并保留证据。

## 7. 结论边界

这项实验复用了已经开发过的 fold0，只能筛选机制，不能增加确认性证据。即使通过，论文中也只能作为 development/ablation，
最终正主张必须在规则冻结后新产生、physical-run disjoint 且从未触碰的 cohort 上确认。
