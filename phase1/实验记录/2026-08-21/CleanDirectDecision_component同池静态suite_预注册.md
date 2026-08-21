# Clean Direct-Decision component 同池静态 suite：预注册

日期：2026-08-21。状态：`PREREGISTERED_NOT_RUN`。本文件在生成任何新 static prediction、dev/test metric 或
模型 artifact 前冻结。该实验是已见 retrospective test 上的 benchmark completeness，不是 prospective confirmation，
不改变 first-960 scorer、WL extension、G0/G1 效果门或论文 novelty。

## 1. 问题与固定输入

唯一问题：在 component-preserving、Card/run/pair 零交集的 direct-decision split 上，纯 decision-time 的可解释
代码/lineage 特征能否形成稳定高于随机的 baseline，并在预先固定的强门下超过同池 char-TFIDF。

| 输入 | rows/items | SHA-256 |
|---|---:|---|
| Cards | 31,742 | `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb` |
| train | 4,689 | `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e` |
| dev | 551 | `3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4` |
| test | 931 | `cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da` |
| TF-IDF per-pair receipt | dev+test | `021f8b3c74db89c6b770714edb879731799b145744af7b765005eed72f9ecde6` |

Draft/Improve 身份仍锁定为 `3ca77a...` / `7aca48...`。不得过滤 task、gap、语义、长度或失败类别；四个 learned
arm 全部拟合与报告。test 已被更早 TF-IDF 和审计看过，所以无论结果多好都标作
`retrospective_same_pool_baseline`。

## 2. 特征与禁止信息

只读取候选 `code` 以及 lineage 的 `depth`、`step`、`n_siblings`。固定 34 维：

- 数量：`code_len,n_lines,n_imports,depth,step,n_sibs,n_cv,n_seed,n_ensemble,n_earlystop,n_hpsearch,
  n_augment,n_try,n_print,n_comment,n_fold_int,n_epoch_int,risk_leak,has_gpu`；
- 词旗标：`lightgbm,xgboost,catboost,randomforest,logisticregression,ridge,svc,torch,transformers,bert,
  resnet,efficientnet,timm,keras,sklearn`。

正则、关键词和大小写规则逐字沿用修正后的 `predictor_suite.py`。禁止读取或派生 `obs`、`label`、grade、
`gap_raw`、`clears_tau`、self-report、runtime、stdout、val curve、plan、lineage `parent_val`。任务名只允许作为
task-conditioned arm 的路由 ID，不做文本 embedding；因此该 arm 只支持 in-task，不得声称 unseen-task 泛化。

## 3. 固定 arms 与反对称契约

1. `random_hash`：对 unordered endpoint ID 的稳定 CRC32 决定 lexicographic endpoint，负控；
2. 单特征：`code_len,n_lines,depth,step,n_cv,n_ensemble`；相等记 tie，不填随机值；
3. `static_lr_pooled`：每个 train pair 加 `(d,1),(-d,0)`；`StandardScaler(with_mean=False)`；
   `LogisticRegression(C=1,max_iter=4000,solver=lbfgs,fit_intercept=False)`；margin 只用
   `coef·scaled(d)`；
4. `static_gbm_pooled`：同一 augmented train；`HistGradientBoostingClassifier(loss=log_loss,max_iter=300,
   learning_rate=0.08,max_leaf_nodes=31,max_depth=None,min_samples_leaf=20,l2_regularization=0,
   early_stopping=False,random_state=7)`；margin=`0.5*(f(d)-f(-d))`；
5. `static_lr_task`：pooled 34 维加 train-task×34 interaction block；同样 scaler/LR 与零截距 margin；
6. `static_gbm_task`：输入为 34 维 d 加固定 train-task one-hot；正反向 one-hot 相同，最终只取
   `0.5*(f(d,t)-f(-d,t))`。未知 task 必须 abstain；本 split 预计未知数须独立报告，不能回退后冒充覆盖。

所有 learned margin 必须对 dev/test 每对满足 `m(a,b)+m(b,a)=0`（绝对误差≤1e-12）；orientation oracle 必须
1.0、全预测与统计有限。producer×2 和不 import producer 的 full-refit verifier×2 必须逐 pair、模型 receipt、
统计一致；任何不一致停止，不取第三实现多数票。

## 4. 选择、统计与正面效果门

先在 dev 上对四个 learned arms 计算 task-macro；最大者成为唯一 champion，1e-12 内按
`static_lr_pooled → static_gbm_pooled → static_lr_task → static_gbm_task` 选更简单者。test 不参与选择，且四臂仍
全部报告。

固定输出 merged/Draft/Improve 的 micro、task macro、逐 task、逐 parent、ties/coverage/margin quantiles；
task-clustered task-macro bootstrap 与 parent-clustered pair-micro bootstrap 各 20,000 次，seed 分别
20260821/20260822。对 champion−TF-IDF 在相同 931 对上做 paired task/parent bootstrap；并报告删除任一 task 后
的 merged micro delta。单特征只在非 tie coverage 上报告，不与 full-coverage arm作 headline delta。

只有以下全部成立才允许主张“可解释静态特征在同池稳定强于字符文本”：

1. champion test 的 task-clustered 与 parent-clustered accuracy CI 下界都 `>0.5`；
2. champion−TF-IDF 的 task-clustered 与 parent-clustered paired-delta CI 下界都 `>0`；
3. Draft、Improve 两层 champion−TF-IDF point delta 均 `>=-0.01`；
4. leave-one-task-out 删除任一 task 后 point delta 都 `>=0`；
5. champion coverage=1、ties=0，所有反对称/独立复核门通过。

任一失败则逐项报告，不改模型、特征、C、GBM 深度/迭代、任务、阈值或子集追救。即使全过，也只是强 baseline
与“数据可学”正资产，不是新方法，不证明 Qwen scaling 或真实 search utility。

## 5. 13 项执行前检查

1. 唯一比较轴是固定静态模型家族；数据、split 与统计不变。
2. 先写聚焦单测：反对称、截距排除、task routing、tie、输入 hash、独立 refit。
3. 只用已见 retrospective test；不读 first-960/prospective outcome vault。
4. 报全部 arms、逐 pair/task/parent 和两语义，不只报 champion 均值。
5. task/parent clustered paired inference 与 LOTO 已预先固定。
6. champion 只由 dev task-macro 选择；test 不调参。
7. Card/run/pair/config/component integrity 沿用已独立通过的 split receipt并重验。
8. seed、特征、模型、阈值、平局规则均在结果前固定。
9. 输出前后执行文件名与内容 credential-shape 双扫描，不打印命中内容。
10. CPU-only、单线程；GPU/API/base-LLM update 均为 0。
11. 结论限定 retrospective benchmark baseline，不申 novelty/prospective/search gain。
12. producer×2、verifier×2、命令/环境/耗时/SHA 全留据；失败不覆盖。
13. 任一强门失败不换特征、超参、task、subset 或 delta 门追正结果。
