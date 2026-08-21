# TreeTransition future escrow：冻结扩展预注册

日期：2026-08-21。状态：`PREREGISTERED_BEFORE_ESCROW_IMPLEMENTATION_AND_ANY_FUTURE_OUTCOME_READ`。
本协议发生在 `TreeTransitionStatic` 正式 OOF 裁决之后，只允许把已经看过结果的 68 维 arm 原样冻结到未来
outcome-unread 数据；它不回填 OOF 的 `NO_ROBUST_TRANSITION_GAIN_VERIFIED`，也不改变 first-960 primary。

## 1. 资格依据与诚实边界

在 parent-closed OOF 上，`child_plus_transition-child_code` 的 merged task-macro delta 为 +0.01712455404609924，
task CI 下界为 −0.000012814366133543737；canonical Improve delta 为 +0.03615895099762306，task CI 下界
+0.0035516498662925295，但 parent CI 下界为 −0.0014866388423867886。该结果方向良好但正式未过双聚类门。
所以唯一合法的确认出口是新的、结果盲的物理 run，而不是在同一 5,240 pairs 上改特征、模型或统计门。

当前 snapshot=`83ab1d6...d5c047` 的单实现、outcome-blind 结构投影仅作设计依据：249 runs / 6,471 cards /
1,665 pairs 中 1,412 pairs 可找到同 run/task parent source，coverage=0.848048048048048。第一次投影把整个
31,742-card 输入文件都算作“训练可见”，得到 2,330 ID / 2,321 code-SHA overlaps；这不是模型实际 feature
支持集。按 train+dev rows 精确闭包到模型真正使用的 5,612 个 endpoint/parent 后，正确 overlap 是 579 IDs /
579 code SHA，physical-run ID overlap=0。数量口径虽被纠正，当前前缀仍不是 source-independent validation，
只能作工程支持集，绝不能作为 transition 效果验证。上述计数必须在激活前由不 import 主实现的 verifier 重建；
不一致即停止。

## 2. 唯一冻结模型

- 训练输入固定为 OOF 使用的 Cards SHA=`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`
  与 outer-train train/dev SHA=`0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e` /
  `3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4`，合计 5,240 pairs；禁止 held-out test、prospective vault、
  TF-IDF、score/self-report/runtime/stdout；
- 特征与 commit `e8eb25cf2540303c9fddd53bebfb23b2c5a0f3a5` 完全一致：31 维 child static、37 维
  transition、68 维 combined；矩阵/feature 名称和 edit-shape 定义不得改变；
- 固定三个 pooled full-fit arms：`child_code`、`transition_only`、`child_plus_transition`。三者同用正反 pair
  augmentation 与 `HistGradientBoostingClassifier(max_iter=300, learning_rate=.08, max_leaf_nodes=31,
  min_samples_leaf=20, early_stopping=false, random_state=7)`；
- future primary 只有 `child_plus_transition-child_code`；`transition_only` 只是机制消融。不得根据支持集预测
  分布、coverage 或未来结果选择 arm、阈值、任务、margin 或 checkpoint；
- 每次 append 由 producer 与独立 verifier 各自从锁定 train rows full refit；逐 pair margin 必须精确一致。

## 3. Activation、样本与 parent coverage

实现、测试和 source commit 冻结后，由远端 UTC 时钟自动创建 transition 专属 activation receipt，绑定 source/
input/model/protocol SHA。只有 `generation_started_at_utc > activated_at_utc` 的 physical runs 可进入 future effect；
当前及更早 rows 即使 outcome 从未读取，也永久标为 `support_only`。

pair 仍由现有 first-960 accumulator 的 `(task, physical_run, parent)` 组内 canonical unordered combinations 决定，
不另抽样、不重排、不改 closure。只有 parent ID 在同一 blind manifest 中存在、且 parent task/run 与 pair 一致时，
才能产生 transition margin；不补零、不从 label vault 或原始含密钥 archive 补 parent、不作 arm-specific outcome
complete-case 删除。缺 parent 是 outcome-free eligibility，必须在预测前冻结并报告覆盖。

future effect 的资格门固定为：至少 1,500 个 strict、parent-covered、source-novel finite non-tie pairs；至少
150 physical runs、15 tasks；dominant pair-task share≤0.25；parent-source pair coverage≥0.80；训练/未来 endpoint
ID 与 run ID overlap=0，exact code-SHA overlap rows 单列且排除 primary。任一门失败为
`TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`，不得放宽。

## 4. 预测托管与禁读契约

每个 snapshot 在 outcome 揭盲前写：activation/source/input/model receipt、eligible pair identity、parent/child code
SHA、三个 signed margins、support/strict stratum、training ID/run/code overlap flags、coverage 与资源回执。旧 snapshot
已托管行必须逐字段保持，append-only survival 失败即中止。

producer/verifier 只能打开登记的 `eligible_blind_manifest.jsonl`、identity-only run/accumulator summaries、锁定训练
Cards/train/dev 和 activation/model protocol；禁止打开 `label_vault`、score registry/index、grade/outcome、frozen、
existing scorer predictions 或 raw archive/env。两条 syscall trace 对禁读路径零命中，输出 credential-shape 扫描为 0。

## 5. Closure 后唯一效果分析

只有既有 first-960 + independent accrual closure 与本节支持门全过后，才在完全相同 eligible pairs 上一次性比较：

- primary metric：`child_plus_transition-child_code` paired accuracy delta；
- primary inference：physical-run clustered bootstrap 20,000 次，seed=`20260827`；
- secondary：task/parent clustered bootstrap seeds=`20260828/20260829`、逐 task、逐 run、LOTO、Draft 不存在的
  canonical raw sibling语义说明；
- controls：combined task/run/parent chance CI、random/orientation、anti-symmetry、coverage、ties；
- `PROSPECTIVE_TRANSITION_EXTENSION_POSITIVE` 仅当 paired run/task/parent 三类 CI 下界均>0、combined 三类 chance
  CI 下界均>0.5、所有 LOTO>0，且 source overlap/support/完整性门全过；否则为
  `PROSPECTIVE_TRANSITION_EXTENSION_NO_CONFIRMATION`。

即使未来为 positive，也只称真实 MLE sibling 上 cheap transition-aware baseline 的时间外支持；不得称新 reward-model
算法、不得推断 search speedup，也不得把 OOF 改写成预注册成功。

## 6. 13 项预检与资源

1. 方向：Decision Corpus + Predictor Benchmark 的 outcome-blind extension，不恢复 HCE/TD/probe/multifidelity。
2. 唯一旋钮：只比较原样冻结 combined 与 child-only；产物必须记录实际 feature/model SHA。
3. 新路径：先做 synthetic tiny snapshot、missing-parent、overlap、timestamp、swap、tamper 测试。
4. 切分：训练/future pair、Card、run、code SHA 四查；现有 support overlap 已明确阻断效果使用。
5. 样本：existing first-960 order 与 closure 不变；不因 append 改旧抽签或旧行。
6. 分布：完整报告 task/run/parent、coverage、source overlap，不只报 micro/单次数字。
7. 评估：三种 cluster CI 与 LOTO；不能用 pair-binomial CI 替代。
8. RNG：模型、bootstrap、pair canonicalization 和 append order 固定并写入产物。
9. 安全：只读脱敏 blind manifests；禁止 raw archive/env；每次提交/输出双扫描。
10. 墙钟：每 snapshot 3 fits×producer/verifier，单线程 CPU，预计 5—15 分钟；0 GPU、0 API、0 LLM update。
11. 功效：严格支持要求 1,500 parent-covered pairs/150 runs/15 tasks；低于即不分析效果。
12. rc：runner 先保存每步 rc 再写日志，失败退出；不得让下游在坏产物上继续。
13. 复现：精确 commit/worktree、命令、版本、SHA、producer×2/verifier×2、manifest、只读封存。

## 7. 防 scoop

[ReLoc](https://arxiv.org/abs/2508.07434) 已训练 revision reward model 并用局部代码修订引导搜索；
[Guided Evolution](https://arxiv.org/abs/2402.05821) 已用二元程序 predictor 比较 child/parent 并拒绝预计更差的
mutation；[GRAF](https://proceedings.mlr.press/v235/kadlecova24a.html) 已说明廉价 graph features 可成为强 NAS
predictor。因此 parent/edit-aware critic、predict-before-execute 和轻量结构特征都不是本项目的方法首创。
本 extension 的价值只在真实 MLE-agent sibling、physical-run/source closure、选择性 parent 可观测性、成本与
outcome-before-prediction 隔离；论文不得写 first/only。
