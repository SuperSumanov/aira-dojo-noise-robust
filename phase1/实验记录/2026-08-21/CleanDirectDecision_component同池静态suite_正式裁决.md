# Clean Direct-Decision Component 同池静态 suite：正式裁决

日期：2026-08-21

结果前协议：`CleanDirectDecision_component同池静态suite_预注册.md`

源码 commit：`76c1b49422ed444ac2aaa43612e80e6261584acd`

正式状态：`STATIC_SUITE_INDEPENDENTLY_VERIFIED_NO_STRONG_ADVANTAGE`

## 一句话裁决

存在一个小而真实的正结果：只使用候选代码和 decision-time lineage 的 GBM，在冻结的 component 同池 test
上通过了事前规定的 task/parent 两个 chance gate；但 dev 选出的最强静态模型没有超过同池字符 TF-IDF，
并在 Draft/Improve 间发生方向相反的异质性。因此它是可信的 benchmark completeness 资产，不是方法突破，
不允许写成“静态可解释特征稳定强于文本”。

## 1. 冻结设计与实际执行

- 数据：component train/dev/test=`4689/551/931` pairs；train/dev/test physical runs=`430/81/140`；
  endpoints=`4095/626/1346`；components=`168`。
- 所有 train/dev/test 的 Card endpoint、physical run、unordered pair overlap 都为 0。
- arms：六个事前固定的单特征控制、pooled LR/GBM、task-interaction LR/task-conditioned GBM；特征仅来自
  candidate code 与 decision-time `depth/step/n_siblings`。
- 禁止字段：`obs`、grade、gap、self-report、runtime、stdout、`parent_val` 与 held-out fit。
- 选择：只按 dev task-macro；唯一 champion=`static_gbm_task`。
- 推断：test task-clustered 与 parent-clustered bootstrap 各 20,000 replicates；同池 TF-IDF 用逐 pair
  配对差；Draft/Improve 与 leave-one-task-out 按预注册全部报告。
- 实际矩阵：producer×2 + 不 import producer 的 full-refit verifier×2，顺序单线程 CPU；GPU/API=0。
- 单次墙钟：producer=`19:40.34`、`18:37.63`；verifier=`19:43.51`、`19:13.47`。

## 2. 四个 learned arms

| arm | dev task macro | test micro | test task macro | task-clustered 95% CI | parent-clustered 95% CI |
|---|---:|---:|---:|---|---|
| `static_lr_pooled` | 0.4945887907256833 | 0.5005370569280344 | 0.4710457686759721 | [0.39826280541916287, 0.5373397127817355] | [0.46274889202996916, 0.5377258235919234] |
| `static_gbm_pooled` | 0.4985101775819322 | 0.5531686358754028 | 0.5551940519097932 | [0.5002304312625108, 0.6133707849802903] | [0.514594373837081, 0.5905265323803335] |
| `static_lr_task` | 0.5084878218518177 | 0.5370569280343717 | 0.5202154082736445 | [0.4573501824844535, 0.5785845609724494] | [0.49947522998939575, 0.5746196881391467] |
| `static_gbm_task` | **0.5314760406597048** | **0.560687432867884** | **0.5585685275472433** | **[0.500809682553181, 0.6176416031350442]** | **[0.5228966986155484, 0.5984075062159282]** |

champion 覆盖 931/931，ties=0、abstentions=0。它在 Draft 的 micro=`0.6305732484076433`、task
macro=`0.5871412912484342`；Improve 的 micro=`0.5251215559157212`、task macro=
`0.5280138173750936`。pooled GBM 也同时通过两个 chance gate，说明结果不是只依赖 task-conditioned
实现；LR 两臂则没有通过双门。

## 3. 固定控制与同池 TF-IDF

主要单特征控制的 test micro 为：random hash=`0.5134264232008593`、code length=
`0.46616541353383456`、line count=`0.4698275862068966`（coverage=`0.9967776584317938`）、step=
`0.4978021978021978`（coverage=`0.9774436090225563`）、CV count=`0.4880382775119617`
（coverage=`0.22448979591836735`）、ensemble count=`0.5152722443559097`
（coverage=`0.8088077336197637`）；depth 在 sibling pair 内全为 tie，coverage=0。orientation oracle
为 1.0 且 anti-symmetry max abs=0.0。

已锁定同池 TF-IDF 的 test micro=`0.5714285714285714`、task macro=`0.5757982662586206`。相对它，
champion 的：

- pair-micro delta=`-0.010741138560687433`，parent-clustered 95% CI=
  `[-0.06271933251042952,0.04004332013926007]`；
- task-macro delta=`-0.01722973871137726`，task-clustered 95% CI=
  `[-0.11177361183157879,0.09201062529949726]`；
- Draft micro delta=`+0.050955414012738856`；Improve micro delta=
  `-0.04213938411669368`；
- 每个 leave-one-task-out 点估计都为负。

因此 `paired_task_ci_above_zero=false`、`paired_parent_ci_above_zero=false`、
`semantic_deltas_at_least_minus_0.01=false`、`loto_deltas_nonnegative=false`。强主张的四个效果门均失败，
`strong_positive_claim_allowed=false`。

## 4. 独立核验与封存

- verifier 不 import producer，并从原始输入 full refit；逐 pair margin、per-task、per-parent 与完整 summary
  最大绝对差全部为 0.0；六个 verifier gates 全为 true。
- producer×2、verifier×2 各自 byte-identical；对应两个 reproducibility diff 与四个 stderr 均为 0 bytes。
- focused tests=`12 passed, 13 warnings in 3.22s`；warning 是 SciPy 未来版本弃用提示，不改变本次拟合。
- 封存后在同一 commit 上运行整个 `phase1/tests`：显式限制 BLAS/OMP/进程池为单线程且禁用 GPU，结果为
  `550 passed, 25 warnings in 39.83s`，pytest rc=0；外层墙钟=`0:47.98`、最大 RSS=`327616` KiB，
  四份后验回执的 SHA-256 自检通过。
- 输出 manifest 共 35 entries；外部 `sha256sum --check` 全过，递归文件集合与 manifest 精确一致。
- 封存目录 mode=555，递归可写文件=0；输入前与输出后 credential-shape scans 均为 0。
- producer summary SHA-256=`b5937956761c1dab26e7db7bda49439fd8d354566cefb2a639cd99f27b680f24`；
  producer artifact manifest SHA-256=`294b6794c379e70f5d9ad948a55fdf0c4ad942aa6b578ef2943ba0cd7b5d1411`。

收尾审计中，第一版“manifest 文件集合”外部检查器错误地只扫描顶层且未剥离 manifest 的绝对路径前缀，
因此产生一次假 `MISMATCH`；35 项内容哈希在该次已全部通过。修正检查器为递归相对路径后，文件集合为
`EXACT`。封存目录在两次检查间始终只读，没有任何实验产物被修改。

全回归第一次启动时，外层虽只有一个 pytest 进程，但 BLAS 自动展开到约 30 个 CPU 线程；出于登录节点资源
卫生主动发送 TERM，保留 rc=143 回执，然后在不改源码与测试集合的情况下加入显式单线程环境约束重跑并全过。
这不是测试断言失败，也不参与科学结果计算；两次后验运行均发生在只读正式产物封存之后。

## 5. 可以写与不能写

可以写：在当前 run-clean、pair-component-clean 的同任务 retrospective benchmark 中，廉价静态 code/lineage
特征包含高于随机的可学习信号；GBM 比 LR 更能利用它；信号在 Draft 比 Improve 强，提示 construction
semantics 是 benchmark 报告必须保留的分层轴。

不能写：静态特征强于文本；task-unseen 泛化；时间外确认；search utility；新方法；或对 8B critic scaling 的
替代证据。test 已被早期 benchmark 审计使用，本轮虽结果前冻结但仍是 retrospective；不得在本 test 上继续
调特征、超参、语义权重或任务子集追救。

## 6. 后续裁决

这条支线在这里停止调参，只作为 Predictor Benchmark 表中的 cheap structured baseline。论文 primary 仍是
Decision Corpus + deployment-estimand sibling protocol + 结果盲 first-960/closure；WL 仍只作 extension。
下一项模型容量证据仍是 G0，但当前账号没有 Pro6000 QoS，且长 GPU 实验需要单独批准与学长授权，故本次没有提交。
