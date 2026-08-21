# Clean Direct-Decision 静态信号来源 component-OOF：v1 结构失败与 v2 结果盲修订

日期：2026-08-21。状态：`V2_PREREGISTERED_NOT_RUN`。本修订发生在任何 GBM fit、OOF margin、accuracy、CI
或 feature-group outcome 产生之前；v1 commit=`521e2014cf1ea7f20d6ee28410bab917b1e1e667` 已先推送，故
失败与修订时间线可核验。

## 1. v1 为什么不能执行

对固定 train+dev=5,240 rows 的纯结构检查得到：

- 既有 `pair_component_id` 共 168 个，component 跨 task=0；
- endpoint 跨 component=0，physical run 跨 component=0；
- 但 `(task,parent)` 跨 component=16。

因此 v1 中“parent 不得跨 fold”的断言与固定输入不相容。若忽略它，parent-cluster bootstrap 的 cluster 可能同时
出现在 fit/eval，且模型可在不同 pairs 间共享同一决策上下文；不能把这种结果称为 parent-isolated OOF。v1 在模型
运行前正式关闭，状态为 `V1_STRUCTURAL_PREFLIGHT_FAIL_NO_MODEL_OUTCOME`。不删除失败记录，也不放宽 parent
isolation 门。

## 2. v2 唯一修订：parent-closed supercomponent

先以 168 个既有 pair components 为节点；凡两个节点共享同一 `(task,parent)` 就 union，并取传递闭包。每个
supercomponent ID 固定为其中全部原 component IDs 排序后的 compact JSON 的 SHA-256。固定结构结果：

- 152 个 parent-closed supercomponents；
- 136 个含 1 个原 component，16 个含 2 个原 components；
- supercomponent 跨 task=0；
- 5,240 rows 一行不少、不重复，最大 supercomponent 为 143 pairs；
- 按定义 endpoint、physical run、parent、原 component 都不得跨 supercomponent。

v2 的五折算法把原文所有“component”替换为上述 parent-closed supercomponent；排序键变为
`(-pair_count, task, supercomponent_id)`，task-specific tie order、seed=`20260823`、字典序 greedy 规则均不变。
每折必须重验 pair/endpoint/run/parent/original-component/supercomponent overlap 全为 0。

## 3. 未改变项与成功门

以下逐字沿用 v1，不得因结构修订改变：

- 固定 Cards/train/dev 三个 SHA 与 5,240 pairs、28 tasks；不读 test、TF-IDF、semantic 或 prospective outcome；
- `gbm_code` 31 维、`gbm_lineage` 3 维、`gbm_all` 34 维及完全相同的 300-iteration pooled GBM；
- random-hash 负控、orientation 正控、显式 antisymmetric margin；
- task/parent 各 20,000 次 bootstrap、seeds=`20260823/20260824`；
- code chance、code−lineage superiority、code−all 1pp non-inferiority、LOTO、control 和独立复核六组门；
- producer×2、verifier×2、单线程 CPU、0 GPU·h、0 API、失败不追调。

v2 仍只允许窄主张“code-derived frozen features 的 OOF 信号不由三个 lineage 特征主导”；不扩大为理解代码、
因果、task-unseen、frozen/prospective/search gain 或 novelty。

## 4. v2 补充预检

1. parent closure 只读 pair identity/task/parent/component，不读 gap 或任何模型 outcome；
2. 16 个跨 component parents 已全部闭包，不删除对应 rows；
3. supercomponent ID 与 fold assignment 都须对输入行顺序不变；
4. 聚焦测试新增 parent-transitive closure、parent isolation 与 tamper detection；
5. fold receipt 可在模型前生成，但不得输出 label aggregate；
6. 其余 v1 13 项预检继续有效。

裁决：v1 不运行；v2 状态为 `PARENT_CLOSED_COMPONENT_OOF_PREREGISTERED_NOT_RUN`。实现与聚焦测试通过后，
方可执行原定 15 fits/producer ×2 + 15 fits/independent verifier ×2 的 CPU 矩阵。
