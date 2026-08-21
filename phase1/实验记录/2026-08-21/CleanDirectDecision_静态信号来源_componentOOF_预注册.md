# Clean Direct-Decision 静态信号来源：component-OOF 预注册与预检

日期：2026-08-21。状态：`SUPERSEDED_BEFORE_MODEL_OUTCOME`。本文件在产生任何新 OOF margin、accuracy、CI 或
feature-group 比较前冻结。实验只做 0CJ 静态 suite 的结果盲来源审计：判断已观察到的 pooled static-GBM
信号是否可由候选代码特征单独恢复，还是主要来自 `depth/step/n_siblings` 搜索位置捷径。它不是新模型搜索、
不读取 frozen test、first-960 或 prospective outcome vault，也不改变当前论文主线和 G0/G1 资格门。

## 1. 唯一问题与证据边界

唯一问题：在 outer-train 的全部 5,240 对上，以 pair-graph connected component 为不可分单位做固定 5-fold
OOF 时，`code-only` GBM 是否稳定高于 chance 和 `lineage-only` GBM，并且相对 `all-static` GBM 不劣超过
1 个百分点。

若全部效果门和复核门通过，只允许写：

> retrospective outer-train component-OOF 支持 pooled static signal 不可由
> `depth/step/n_siblings` 三个搜索位置特征解释，且去掉它们没有实质损失。

不得写“模型理解代码”、因果机制、task-unseen 泛化、frozen-test 提升、prospective confirmation、search
utility 或方法 novelty。代码 token、库选择、长度和任务风格仍可能是 shortcut；本实验只排除三个明确 lineage
特征是主要来源。

> 结果盲结构勘验随后发现 16 个 `(task,parent)` 跨既有 pair component；尚未拟合模型或产生 prediction。
> 因此本 v1 在执行前关闭，改用 parent-closed supercomponent 的 v2。效果门、feature arms、模型和统计阈值
> 均未改变。修订与时间线见
> `CleanDirectDecision_静态信号来源_componentOOF_v1结构失败与v2修订.md`。

## 2. 固定输入与禁止读取

| 输入 | rows/items | bytes | SHA-256 |
|---|---:|---:|---|
| grouped Cards | 31,742 cards | 604,190,866 | `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb` |
| component train | 4,689 pairs | 3,208,089 | `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e` |
| component dev | 551 pairs | 376,635 | `3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4` |

train+dev 的结构盘点固定为 5,240 pairs、168 components、28 tasks。脚本 CLI 只接受上述三个输入和新建输出
目录；不得接受或打开 `test.jsonl`、TF-IDF per-pair receipt、Draft/Improve outcome 文件、first-960、WL、
prospective ledger、score/grade/self-report/runtime/stdout/obs/label/`parent_val`。共享 Cards 容器虽含其他 card，
但先由 train+dev endpoint 白名单筛选，非白名单 card 在读取 `id` 后立即跳过；模型矩阵只准访问白名单 card 的
`code`、`lineage.depth/step/n_siblings`，并只用 task/run/config 做完整性核验。

## 3. 固定 fold 算法

五折 seed=`20260823`，不得按 outcome、gap、task accuracy 或模型表现分折。

1. 每行必须带已验证协议 `pair-graph-component-train-dev-split-v1` 的 64 位 `pair_component_id`；每个
   component 只能对应一个 task，且 endpoint、physical run、parent 不得跨 component。
2. 将 components 按 `(-pair_count, task, component_id)` 排序。
3. 对 task `t`，固定循环 tie order 的起点为
   `int(SHA256("20260823|" + t),16) mod 5`。
4. 对每个 component 选择使
   `(该 task 在 fold 的累计 pairs, fold 总累计 pairs, 循环 tie rank)` 字典序最小的 fold。
5. 每个 fold 的 eval 是该 fold 全部 components，fit 是其余四折；五折 eval union 必须逐行等于 5,240 对。

fold assignment 必须对输入行顺序不变。每折重验 fit/eval unordered-pair、endpoint、physical-run、parent 和
component overlap 全为 0；每折 fit/eval 均非空。只在模型拟合前输出 fold receipt，不输出 label aggregate。

## 4. 固定特征、arms 与训练

34 维特征及正则逐字沿用 `critic_component_static_suite.py`。冻结三组：

- `gbm_code`：除 `depth,step,n_sibs` 外的 31 个 code-derived features；
- `gbm_lineage`：只含 `depth,step,n_sibs`；
- `gbm_all`：全部 34 维。

三个 learned arms 均使用相同 pooled `HistGradientBoostingClassifier`：`loss=log_loss,max_iter=300,
learning_rate=0.08,max_leaf_nodes=31,max_depth=None,min_samples_leaf=20,l2_regularization=0,
early_stopping=False,random_state=7`。每折 fit pair `d=x_better-x_worse` 扩增为 `(d,1),(-d,0)`；eval margin
固定为 `0.5*(decision(d)-decision(-d))`。不输入 task ID，不做 task-conditioned interaction，不调参、不选
champion、不拼接 TF-IDF、不更改 feature group。

另报两个非学习控件：

- `random_hash`：unordered endpoint ID 的稳定 CRC32 选择一端，负控；
- `orientation_oracle`：始终选择标注 better，正控，只验证方向与统计管线。

learned margin 必须逐对满足交换端点后的和绝对值 `<=1e-12`；NaN/Inf、fold 缺失、重复 OOF prediction 或
learned tie 均使正面主张失败。tie 若出现，统计记 0.5 credit，但不得通过 no-tie 门。

## 5. 固定统计与效果门

对三 learned arms 和 random control 全报：5,240 对的 micro、28-task macro、逐 task、逐 parent、逐 fold、
coverage/ties 与 margin quantiles。task-clustered task-macro bootstrap 用 20,000 次、seed=`20260823`；
parent-clustered pair-micro bootstrap 用 20,000 次、seed=`20260824`。同一 pair prediction 上固定计算
`code-lineage` 与 `code-all` paired delta；task bootstrap 对 task 内 accuracy delta 等权，parent bootstrap
按 parent cluster 重采样后保持 pair-micro estimand。另报删除任一 task 后的 `code-lineage` task-macro delta，
不以 fold 当独立统计样本。

只有以下全部成立，才允许上述窄正面主张：

1. `gbm_code` 的 task-clustered 与 parent-clustered accuracy CI 下界都严格 `>0.5`；
2. `gbm_code-gbm_lineage` 的 task-clustered 与 parent-clustered paired-delta CI 下界都严格 `>0`；
3. `gbm_code-gbm_all` 两类 paired-delta CI 下界都 `>=-0.01`；
4. 删除任一 task 后的 `code-lineage` task-macro delta 最小值严格 `>0`；
5. `random_hash` 的 task/parent CI 都包含 0.5；三个 learned arms coverage=1、ties=0；
6. component/fold/反对称/orientation、producer×2 byte identity、独立 full-refit verifier×2 全部通过。

任一门失败，只报告“来源审计未支持窄主张”及每项数值；不得在这 5,240 对上改 fold、feature group、GBM
超参、delta 门、task/subset 或 tie 规则追救。无论结果如何，都不读取 frozen test 来选择解释。

## 6. 独立复核与产物

producer 与 verifier 分文件实现；verifier 不 import producer，独立重读输入、重建 features/folds、重拟合 15 个
GBM 并逐 pair 对比 margin、fold、correctness、task/parent/summary。producer×2、verifier×2；同实现重复产物
需 byte-identical，跨实现最大数值差 `<=1e-12`，否则停在 invalid，不以第三次多数票覆盖。

产物必须含 `summary.json`、`per_pair.jsonl`、`per_task.csv`、`per_parent.csv`、`per_fold.csv`、模型/fold
receipts、输入/输出 SHA、确切命令、Python/sklearn/numpy/CPU 环境、耗时和独立复核 receipt。正式输出目录新建、
不覆盖，结束后只读封存。

## 7. 13 项执行前检查

1. **唯一比较轴**：只改变静态 feature group；数据、fold、模型与统计不变。
2. **输入绑定**：三个固定 SHA/bytes 已核；5,240 pairs、168 components、28 tasks 只属结构元数据。
3. **泄漏边界**：无 test/TF-IDF/semantic/prospective 参数；Cards 仅投影 train+dev endpoint 白名单。
4. **component 单位**：component、endpoint、run、parent 均不可跨 fold，行顺序不影响 assignment。
5. **模型冻结**：三臂相同 GBM 超参、相同 5 folds；无 tuning、selection 或 task conditioning。
6. **方向契约**：正反扩增、显式反对称 margin、random 负控和 orientation 正控均先写测试。
7. **完整报告**：micro/task/parent/fold、coverage/tie、两 paired delta、LOTO 全报，不只报均值。
8. **推断冻结**：task/parent 20,000 bootstrap、seed 与 non-inferiority margin 已在结果前固定。
9. **成功/停止门**：六组门逐项固定；失败不换 task、subset、fold、特征或模型追正。
10. **资源**：CPU-only、显式单线程；0 GPU·h、0 API calls、0 base-LLM update/checkpoint。
11. **复现**：producer×2、independent verifier×2、输入/代码/环境/命令/耗时/SHA 全留据。
12. **安全**：push 前文件名扫描与 credential-shape 内容扫描；不复制或打印任何密钥值。
13. **结论边界**：只作 0CJ retrospective robustness audit；不改 first-960、closure、WL、G0/G1 或论文 novelty。

预检裁决：设计层面 13/13 已冻结；状态仍是 `PREREGISTERED_NOT_RUN`，须先实现聚焦测试并通过，再运行正式
CPU 矩阵。预计正式矩阵为 15 fits/producer × 2 + 15 fits/verifier × 2，GPU/API 均为 0。
