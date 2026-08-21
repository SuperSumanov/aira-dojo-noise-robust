# TreeTransitionStatic：父相对编辑表征的条件预注册与防 Scoop 边界

日期：2026-08-21。状态：`PREREGISTERED_BEFORE_STATIC_SOURCE_OOF_OUTCOME_READ`。本设计在
`208e381...` 的 parent-closed static-source OOF 完全封存、读取任何 accuracy/margin/gate 之前冻结。它不改变该
在途实验；只有在其完整性、双重确定性和独立 full-refit verifier 全通过后，才允许读取该结果并启动本实验。

## 1. 问题与结果盲资格依据

当前 31 维 child-code 静态表征只回答“两个候选代码看起来有什么不同”，没有显式表达搜索树中更自然的转移：
“每个候选相对共同 parent 改了什么”。对于同一 parent，signed feature delta 在 pairwise difference 中会严格抵消，
所以本实验不把重复的 `f(child)-f(parent)` 冒充新信号，而只加入不会抵消的**编辑幅度/形状**。

结果盲结构投影给出的资格支持为：

| semantic | pairs | tasks | `(task,parent)` | lineage parent matches 0 / 1 / 2 | endpoint runs |
|---|---:|---:|---:|---:|---|
| Draft | 3,196 | 28 | 135 | 2,808 / 371 / 17 | cross=2,609, same=587 |
| Improve | 2,044 | 28 | 1,576 | 424 / 862 / 758 | same=2,044, cross=0 |

两层共同覆盖 28 tasks。Improve 的 parent 全部与 endpoints 同 physical run，且 1,620/2,044 rows 至少有一个
endpoint 的直接 lineage parent 与 pair parent 相符；Draft 多为跨-run relational construction，不能把编辑表征解释成
直接代码修订。因此 primary 是 pooled OOF 的总体增量，canonical-Improve 是预先指定的关键 secondary；若增益只在
Draft，必须标为 construction-specific artifact candidate。

## 2. 固定输入与隔离

- Cards SHA=`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`，bytes=`604190866`；
- train/dev SHA=`0ec49d76...` / `3b3fb53f...`，rows=`4689/551`；
- Draft/Improve identity SHA=`3ca77a18...` / `7aca481a...`；
- 不得打开 held-out test、TF-IDF、frozen/prospective ledger、score/self-report/runtime/stdout 或任何 execution outcome；
- 沿用 `208e381...` 的 152 个 parent-closed supercomponents、固定 seed=`20260823`、5 folds；每个 fold 的 pair、
  endpoint、physical run、`(task,parent)`、原 component 与 supercomponent overlap 必须全为 0；
- semantic identity 只用于预先固定的分层报告，不进入模型特征、训练权重、fold assignment 或模型选择。

## 3. 唯一模型矩阵

三臂都用同一个 pooled `HistGradientBoostingClassifier`：`max_iter=300`、`learning_rate=.08`、
`max_leaf_nodes=31`、`min_samples_leaf=20`、`early_stopping=false`、`random_state=7`；每 fold 用正反 pair augmentation，
margin 固定为 `(decision(d)-decision(-d))/2`。

| arm | 每个 candidate 的预执行表征 | pair 输入 |
|---|---|---|
| `child_code` | 31 个既有 code-only static features | `c(a)-c(b)` |
| `transition_only` | 31 个 `abs(c(child)-c(parent))` + 6 个源码编辑形状 | `t(a,p)-t(b,p)` |
| `child_plus_transition` | 上述两者拼接 | 两个 pair differences 拼接 |

六个源码编辑形状由 `difflib.SequenceMatcher(..., autojunk=False)` 的 line opcodes 和原始字符长度唯一确定：candidate
added lines、parent deleted lines、non-equal hunk count、equal-line fraction relative to parent、equal-line fraction
relative to child、`abs(log1p(child_chars)-log1p(parent_chars))`。不得增加 AST、embedding、task ID、semantic ID、
threshold、特征选择、超参搜索或新 arm。所有特征在候选执行前可由 parent/child source 得到；记录初始化总耗时与逐
pair amortized query time。

## 4. 固定统计与裁决

每臂完整报告 merged/Draft/Improve 的 pair micro、task macro、ties/coverage、task-clustered 与 parent-clustered
20,000 次 bootstrap（seeds=`20260825/20260826`）。`child_plus_transition-child_code` 与
`transition_only-child_code` 用同 pair 配对差；merged 另报 leave-one-task-out，不能删 task、parent、tie 或小 margin。

状态按以下互斥顺序裁决：

1. **INVALID**：输入、fold isolation、反对称、full coverage/no-tie、orientation/random control、producer×2、
   verifier×2 或 artifact sealing 任一失败。
2. **CANONICAL-TRANSITION-POSITIVE**：`child_plus_transition-child_code` 在 Improve 的 task/parent CI 下界都
   `>0`，combined Improve 的两类 chance CI 下界都 `>0.5`；merged 的两类 paired CI 下界也都 `>0`，merged
   所有 LOTO 点估计 `>0`，且 Draft point delta `>=-0.01`。
3. **POOLED-TRANSITION-POSITIVE**：merged 的两类 paired CI 下界都 `>0`、所有 LOTO `>0`、combined 的两类
   chance CI 下界都 `>0.5`，且 Draft/Improve 两个 point delta 都 `>=-0.005`；但第 2 类 canonical 门未全过。
4. **DRAFT-ONLY-CONSTRUCTION-SIGNAL**：Draft 的 task/parent paired CI 下界都 `>0`，而 Improve 未过同门。
   该状态只能支持 construction diagnostic，不能称 canonical search critic 改进。
5. **NO-ROBUST-TRANSITION-GAIN**：其余有效结果；路线关闭，不在同一 5,240 pairs 上改 diff 特征、模型或门。

`transition_only` 是机制消融，不参与“从两个新臂中挑赢家”；正式正面裁决只由预指定的
`child_plus_transition-child_code` 决定。

## 5. 13 项预检与资源矩阵

1. **方向**：服务 Decision Corpus + Predictor Benchmark，不恢复 HCE/TD/probe/multifidelity。
2. **问题**：唯一问题是 parent-relative edit representation 是否增加 parent-closed OOF 信号。
3. **输入**：五个文件的 SHA/bytes 固定；test/prospective 参数不存在。
4. **split**：复用 parent-closed supercomponent folds；六类 overlap 必须逐 fold 为 0。
5. **标签**：只使用既有 better/worse；不重标、不按 gap/score 过滤。
6. **特征**：31+6 transition 契约一次冻结；signed parent delta 明确因代数抵消而排除。
7. **模型**：3 arms、同一固定 GBM；无调参、无 dev selection、无 task/semantic conditioning。
8. **统计**：task/parent 双聚类、配对差、LOTO、完整 strata，固定 20k seeds。
9. **控制**：random CI 含 0.5、orientation=1、反对称、fold isolation、coverage/tie 门。
10. **支持**：5,240 pairs / 28 tasks；Improve 2,044 pairs / 1,576 parents；Draft 3,196 / 135。
11. **资源**：producer×2 + independent full-refit verifier×2，共 60 个 CPU GBM fits；单线程；0 GPU·h、
    0 API、0 base-model update；预计墙钟 55—80 分钟。
12. **复现/安全**：精确 commit/worktree、命令/环境/seed/耗时/SHA、producer/verifier byte diff、前后凭证扫描、
    manifest 与只读封存全部留据。
13. **停止/主张**：只执行一次；失败不追特征。即使 canonical-positive，也只称 cheap transition-aware baseline，
    不外推 frozen/prospective/search utility。

## 6. 防 Scoop 边界

- [ReLoc](https://arxiv.org/abs/2508.07434) 已在代码 local search 中用 tree-derived **revision distance labels** 训练
  `R(code|task)`，并在 siblings/parent/local neighborhood 构造偏好；因此“利用修订树训练 reward model”不是本项目
  的方法首创。
- [Agentic Predictor](https://arxiv.org/abs/2505.19764) 已用 graph/code/prompt multi-view 表征预测 agentic workflow
  performance；“多视图轻量 predictor”也不能申首创。
- CoT-Edit 与 QiMeng-PRepair 已分别用 diff/edit-aware reward 做代码编辑建议和精确修复训练；本项目不微调底座，
  也不把“edit-aware”作为新概念。

若结果为正，允许的贡献只是：在真实 MLE-agent decision corpus、parent-closed OOF 和 execution-free query
契约下，父相对编辑形状是对 child-only 静态表征的可复现增量 baseline。论文新意仍来自数据、estimand、隔离与
系统性 benchmark，而不是 37 维手工特征本身。
