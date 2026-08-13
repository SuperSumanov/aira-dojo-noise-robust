# 新 physical-run 前瞻 decision benchmark：预注册

日期：2026-08-14。协议名：`prospective_decision_v1`。状态：**outcome 前冻结中**；只有固定 scorer
产物、pre-cutoff run 清单及 freeze receipt 进入 Git 历史后，本协议才开始接纳新 run。

本协议晚于 `PairGraphIntervention_裁决.md`。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树
数据集/benchmark；不恢复 HCE、多保真、probe 或底座微调。已有 v11 OOF outcome 已用于形成下列假设，故只有
冻结后的新 physical runs 能提供确认性证据。

## 1. 研究问题

主问题不是再找一个同数据分数更高的 critic，而是确认：**同一批固定 endpoint scorer 的结论和相对排序，是否
会因评测 pair graph 从真实 sibling 决策换成全局跨 run 配对而系统改变。** 这决定“critic accuracy”能否脱离
真实搜索决策分布横向比较。

同时报告一个独立的部署问题：固定 scorer 在真实 sibling parent 内是否相对无信息随机选择改善 top-1 和
parent-equal gap utility。pair-graph 结论通过不等于 critic 对搜索有用；后者只有通过单独的 utility 门才成立。

## 2. outcome 前冻结的 scorer

只用以下 v11 `intask_split=train` 输入训练一次，不打开 `decision_frozen_v11_b*`、test、held、stdout、runtime、
self-report 或任何执行后特征：

- pairs SHA-256：`bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- run map SHA-256：`3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30`；
- cards SHA-256：`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- endpoint manifest SHA-256：`8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19`；
- 精确支持：4,263 pairs / 333 train runs / 23 tasks / 2,293 parents / 5,499 endpoints；
- 完整 v11 run map 的 667 个 physical run ID 全部写入 pre-cutoff denylist，而不只排除 333 个训练 run。

固定两臂：

1. `static_lr`：与 `heterogeneous_oof_v11_discovery_v1` 相同的执行前静态特征、对称 pair difference、
   `StandardScaler(with_mean=false)`、无 intercept 的 liblinear LR，`C=1.0`、seed=887；
2. `char_tfidf_lr`：相同的 `char_wb` 3--5 gram、30,000 features、`min_df=3`、`sublinear_tf=true`、
   固定 head-5,000/tail-15,000 截断，对称 pair difference、无 intercept LR，`C=0.5`、seed=887。

模型不用 pickle/joblib。vocabulary、IDF、scaler scale 和 coefficients 写入 `allow_pickle=false` 的 NPZ；训练
reference scores、模型数组、源文件、输入和软件版本全部哈希。独立 verifier 不 import producer，重新拟合并
核对数组与 endpoint score。底座 LLM 权重不更新；0 GPU、0 API。

## 3. 前瞻边界与不可选样本

freeze receipt 中的 `activated_at_utc` 和 scorer SHA 进入公开 Git commit 后才开始计数。一个 run 必须同时满足：

1. physical run ID 不在 667-run denylist，且 endpoint ID 与 train manifest 零交集；
2. 可核验的 generation start UTC **严格晚于** receipt；来源 archive/journal、生成 job/config 与字节 SHA 落盘；
3. scorer 只读严格 code-only manifest；manifest 顶层和 lineage schema 采用 allowlist，出现 label/grade/score/
   reward/runtime/stdout/obs/self-report 字段即 fail closed；
4. 在任何 future pair/grade 文件被 scorer 进程打开前，code-only manifest 与逐 endpoint 两臂 score 已原子落盘并
   哈希；随后 evaluator 才能读取 pristine external grade；
5. 不以是否成功、分数、gap、task、operator 或 scorer margin 决定是否收录。失败/无 finite grade 的 run 仍进入
   流程审计，并按预声明删失原因报告，不能静默删除。

确认 cohort 固定为按 `(generation_started_at_utc, source_sha256, physical_run_id)` 排序的**前 240 个合格 run**。
达到 240 前只允许查看标签盲的计数、任务/生成器配置与作业健康状态；不得查看 scorer-vs-grade 指标。达到后只
运行一次 evaluator，不 optional stopping、不追加到显著。若少于 15 tasks、dominant task share >25%、少于
150 个含至少一个 finite sibling decision 的 run，或 eligible sibling pairs <1,500，状态为
`INSUFFICIENT_PROSPECTIVE_SUPPORT`，不替换、不补挑任务。

## 4. 固定评测图与指标

所有未来 pair 必须来自同 parent、同 physical run 的真实 sibling 候选，budget=0，raw external grade finite 且
不相等；方向由 hash-locked task orientation 决定。以 10,000 次 paired task bootstrap 为主、run bootstrap 为
辅；task 是推断单位。score tie 计 0.5。

对两臂分别报告：

- 真实 sibling graph 的 micro/run-macro/task-macro pair accuracy；
- complete-parent top-1 与 parent-equal gap utility；
- task consistency、覆盖率、删失、query/init cost；
- task-matched uniform cross-run graph；
- 固定旧边界 `[0,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,∞)` 的
  gap transport graph；
- 三图的 mean gap、`gap<1e-2` share 与逐 task/stratum 支持。

跨 run 候选必须同 task、不同 physical run，且从冻结 cohort 的 endpoints 中有限总体全枚举；若规模超出实现的
预注册上限，必须先给出不依赖 outcome 的精确聚合算法并另立实现修订，禁止事后随机抽容易 pair。

无信息基线固定为 `crc32("887:" + card_id)/2**32` 的 endpoint score。它只用于真实 sibling top-1/utility
paired comparison，不参与 graph-interaction 主检验。

## 5. 确认门与解释

### 5.1 Primary：predictor × pair-graph interaction

定义 task-macro interaction：

`I = (char_tfidf_uniform - static_uniform) - (char_tfidf_sibling - static_sibling)`。

全部满足才输出 `PROSPECTIVE_PAIRGRAPH_INTERACTION_CONFIRMED`：

- `I >= 0.05` 且 paired task-bootstrap 95% CI 下界严格 >0；
- 至少 15 个 task 各自有两图共同支持，且 task-level interaction 为正的 share >=0.60；
- 两臂、三图、共同支持、freshness、blind-score-before-label、hash 与独立 verifier 完整性门全过。

该门来自已见 v11 rank reversal，属于一次明确的前瞻复现，不可改成只检验 char-TFIDF 的正向 inflation，也不可
按正任务筛选。通过只支持“模型比较依赖 pair graph”，不支持某个 scorer 已改善搜索。

### 5.2 Secondary：真实决策效用

每个 scorer 相对固定随机基线单独裁决。只有 complete-parent top-1 delta >=0.03、gap utility delta >=0.02，
且二者 paired run/task CI 的四个下界都严格 >0，supported tasks >=15、nonchance share >=0.60，才记为
`PROSPECTIVE_DECISION_UTILITY_SUPPORTED_<ARM>`。否则如实为 unsupported；不得用 uniform graph accuracy
替代真实 sibling utility。

### 5.3 禁止升级

- 本协议不打开论文 frozen b0/b1/b2；
- 不在 first-240 outcome 后改 scorer、阈值、feature、任务或 pair graph；
- 不把 retrospective v11 与 prospective cohort 合并后报告确认 p 值；
- 即使 utility 门通过，也只证明离线真实 sibling 选择，不等于 fixed-budget search improvement；后者需要另立
  search A/B，固定 generator/operator/budget/grader 后再跑。

## 6. 资源与失败语义

scorer freeze 为单 CPU 任务，wall cap 1 小时；未来 blind scoring 为 CPU，0 API。evaluator 应支持 checkpoint/
resume、原子输出和 append-only artifact root。任何 forbidden path、旧 run、时间证据缺失、label-bearing scorer
manifest、输入 SHA、模型 round-trip、独立 refit、coverage 或真实 rc 失败，一律 `INVALID`，不解释科学结果。
