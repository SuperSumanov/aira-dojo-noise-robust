# Target-Graph Connected Augmentation：一次性 train-only OOF 预注册

日期：2026-08-14。协议名：`tgca_v11_train_oof_discovery_v1`。状态：**TGCA outcome 前冻结**。
本实验是 `PairGraph_文献边界与正方法候选.md` 允许的唯一下一方法候选；它不改变稳定的数据集/benchmark
主线，也不恢复 HCE、多保真、TD/RL 或 probe。选择 TGCA 与 char-TFIDF 明确使用了此前 v11 的描述性结果，
所以本实验只是一次性 discovery；论文 frozen pairs 与 0812 label vault 继续封存。

## 1. 唯一问题与固定公平契约

问题：在保持 v11 train-only endpoint universe、5 个 physical-run outer folds、代码视图、char-TFIDF 特征、
LogisticRegression solver 与评测 sibling parents 不变时，向 outer-fit comparison graph 加入同 task、跨 run、
gap-matched 且优先连接不同分量的边，能否提高未见 physical runs 上的真实 sibling top-1 与 utility？

固定输入为 4,263 条 `decision_train_v11_b0` sibling pairs、333 个旧 physical-run groups、23 tasks、2,293
parents、5,499 endpoints。outer fold 逐 run 继承自已归档的 heterogeneous OOF；v11 provenance backfill 已知
其中有 5 个保守 merge、可追溯范围 0 个 source split。为避免 outcome 后改 fold，本实验保留原 fold；merge
只会把两个真实 run 更保守地放在同一侧。每 fold 强制 fit/valid run、endpoint 与 raw-code SHA 三层零交集。

仅允许训练 frozen char-TFIDF + 线性头，不更新任何底座 LLM，不调用 API。代码视图固定为 20,000 字符的
head-5,000 + tail-15,000；`char_wb` 3–5 grams、`max_features=30000`、`min_df=3`、`sublinear_tf=true`、
float64。线性头固定 `C=0.5`、无 intercept、`liblinear`、`max_iter=2000`、`tol=1e-6`、seed 887。每 fold
只在 outer-fit endpoints 上 fit vocabulary，一次 transform 后四臂共享同一矩阵。

## 2. 四臂与精确选边规则

四臂均先包含该 fold 的全部原始 outer-fit sibling edges：

1. `sibling_only`：不增加边；
2. `sibling_reweight_control`：增加 TGCA 实际数量相同的原 sibling edge 副本；
3. `uniform_crossrun_control`：增加每 task 与 TGCA 实际数量相同的同-task、跨-run边，按固定 SHA 顺序均匀取；
4. `tgca`：增加同-task、跨-run、gap-matched、优先连接分量的边。

跨-run有限总体是在 outer-fit endpoints 内逐 task 枚举全部 unordered pairs，排除同 run 与 raw-grade tie；方向
只由 outer-fit pristine grade 与固定 task orientation 决定，gap 固定四舍五入到 6 位。gap bins 为右开区间，
上界固定 `[1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,inf]`。

augmentation ratio 固定 1.0。每个 task×gap-bin 的 TGCA target 等于原 sibling fit edge 数；若候选不足只取
有限总体，不跨 bin 回填。TGCA 从原 sibling graph 的 union-find 状态开始，bin 按小到大处理。每个 bin 候选
先按 `(max(两端原图度数), 两端原图度数之和, SHA256(seed=20260814,fold,task,bin,排序后ID))` 排序；第一遍
只选当前连接不同分量的边并立即 union，直到 target 或桥接候选耗尽；第二遍按同一顺序填足该 bin 的可用
target。各 task 的 TGCA 实际新增数 `m_t` 冻结后，两个控制都严格取 `m_t`：reweight 在该 task 原 sibling
edges 上按独立固定 SHA 顺序无放回选取并作为重复训练行；uniform 在该 task 全部跨-run有限总体上按独立
固定 SHA 顺序无放回选取。由于 `m_t` 不超过原边数且 TGCA 候选属于 uniform 总体，数量不匹配即 INVALID。

模型优化使用每个训练 edge 的正负对称差分；重复 sibling 行等价于明确重权。训练 graph 统计按唯一无向边
计算，重复不虚增 connectivity。每 fold/task/arm 必报节点数、唯一边数、component 数、最大 component 占比、
normalized Laplacian 的第二小特征值、跨-run新增数与 gap-bin计数。

## 3. 评测、推断与一次性裁决

四臂只在该 fold 未参与训练的全部真实 sibling rows 上预测；五 fold 合并后保持相同 4,263-row support。必报：

- pair accuracy；
- complete-parent top-1；
- parent-equal grade utility：先在 parent 内计算 `sum(gap*hit)/sum(gap)`，再等权平均 parent；
- TGCA 相对每个控制的逐 parent paired delta、run-clustered 与 task-clustered 10,000 次 bootstrap CI；
- 逐 task utility 方向、支持任务数与 dominant-task share。

task support 在 outcome 前固定为至少 20 条 validation sibling rows；dominant share 用全部 validation sibling
rows 计算。bootstrap seed 固定 20260815；tie prediction 计 0.5。所有分数、edge manifests、图统计与输入
SHA 写入 append-only 产物；producer 后由不 import producer 的 verifier 独立重枚举边、重拟合 20 个模型并
逐 endpoint 比较分数（绝对容差 `1e-10`），再重算全部 metric/gate。

只有以下条件全部满足才输出 `TGCA_DISCOVERY_UNLOCK`：

1. TGCA 相对 `sibling_only` 的 overall parent-equal utility 增量 `>=0.02`，run/task 两个 paired CI 下界均 `>0`；
2. TGCA 相对 `sibling_reweight_control` 的 overall utility 增量 `>=0.015`，两个 CI 下界均 `>0`；
3. TGCA 相对 `sibling_only` 的 overall complete-parent top-1 增量 `>=0.02`，两个 CI 下界均 `>0`；
4. 至少 15 个支持任务、dominant task share `<=0.25`，且至少 60% 支持任务的 utility delta 非负；
5. 所有输入、隔离、方向、数量、收敛、finite、checkpoint、producer/verifier 一致性门通过。

`uniform_crossrun_control` 必报但不替代上述门。跨-run pair accuracy 或 graph connectivity 上升而真实 sibling
utility/top-1 不升，仍为失败。任一效果门失败即 `TGCA_DISCOVERY_NO_UNLOCK`，不在同一 OOF 改 ratio、gap
edges、seed、C、任务、连接顺序或门槛；任一完整性门失败则 `TGCA_DISCOVERY_INVALID`，只能修工程错误后以
新协议重跑。只有 unlock 才允许先冻结 TGCA scorer/predictions，再一次性解封 0812 temporal blind holdout；
否则 label vault 保持未读，资源回到 prospective first-960 与数据发布。

## 4. 资源与预期

正式链为 5 folds × 4 arms = 20 个 CPU 线性头；0 GPU、0 API、0 底座更新。每 fold 原子 checkpoint，producer
与 verifier 各有 7,200 秒 wall cap；预估整链 25–50 分钟。不得因运行时间或中间 fold 表现停跑。所有随机源、
版本、commit、命令、环境与失败配置写入产物，最终 CSV 一行一个 fold×arm 或 fold×task×arm。
