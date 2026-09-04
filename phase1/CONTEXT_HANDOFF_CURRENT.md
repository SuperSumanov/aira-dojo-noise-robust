# Context handoff：Decision Corpus + Predictor Benchmark

**Last updated:** 2026-09-04

**Dynamic status timestamp:** 2026-09-04 14:27 Asia/Hong_Kong

**Purpose:** 给上下文压缩或新会话一个短入口，防止恢复已经关闭的旧方向。

**Authority warning:** 本文件不是科学方向的最高权威。开始任何实验前必须先 fetch Git，再读
`phase1/CURRENT_DIRECTION.md` 的最新日期段；若两者冲突，以后者和用户最新指示为准。

## 2026-09-04 最新入口，覆盖下文所有动态状态

先fetch，再读CURRENT_DIRECTION.md顶部0L9及更新的ACTIVE_WORK_SESSION_20260904.md。
当前唯一已提交GPU作业是G0 12377，2卡117分钟只计价；06:02UTC仍PENDING/Resources，估计香港9月5日12:38:50，
不保证。旧12288启动前失败已保留；新作业不要重投。正式五臂15fits未获预算，不能把G0说成收益实验。
新候选是同一已执行端点集合上的G-reuse→L；两个历史train真实诊断支持3058个新增比较/28tasks，
假设54407806validtokens，但143配置不一致/193来源未明，不能物化成训练池或说有模型收益。
完整来源、双验证、hash与方法限制见LABEL_REUSE_FINDINGS_20260904.md；旧冻结v2和历史开发v1字节不改。
需要同版本producer包+权威来源/config+experiment-closed划分、G0实测和新预算；不得自行过滤问题样本。
最新结构619/960eligible、645physical、316归档、16844endpoints/3910pairs/51tasks，closure=false、config-v2=0。
LATEST=bc9833d834fba65adbbf174301fe968c2c12da4eb8190a8f418ece58d0219456；摄取PID3884166在06:02UTC存活。
学长head=b8d095180415957aa1bab31fa53ead1bba261c03，无新outcome。首次960/Target300/522仍盲态；旧失败链不恢复。
复用候选的30个消费计划、独立重放和6组跨臂前缀检查已完成，receipt5a8ddba9…ff12a88，不再重跑。
L1是Lbudget前37次更新；未来若真实checkpoint绑定验证，可保留15评估单元、以12训练流少约12.9%重复tokens，
未验证真实GPU节约或模型收益。详见results/historical_reuse_execution_20260904/README.md。
没有新clean scaling或跨seed同预算模型收益。六小时窗口06:12:22—12:12:22UTC内原heartbeat已更新并恢复，
只做接力，不以巡检或重复已完成计划冒充实验；正式source/config/split及fit预算门不变。

## 0N. 09:53 动态覆盖（历史记录，已由2026-09-04状态覆盖）

- 当前唯一主线仍是 Decision Corpus + Predictor Benchmark + Audit Protocol；旧 HCE/多保真/probe/score-channel
  effect/K≥1 lookahead/conformal stop 均关闭，不得恢复。
- 2026-08-21 新提交的 COTA（arXiv:2608.21027v1）已经直接实现 exact-prefix branch、same frozen continuation actor、
  0.5B A/B/T pairwise comparator、双顺序一致性与在线 winner-count intervention，并在 9 个 actor×environment 设置报告
  正收益。因此“比较两候选谁会通向更好结果”“tiny comparator 指导强 actor”及 pairwise-to-gate 均不再是我方方法
  novelty；不恢复 K≥1/lookahead。保留边界是 MLE 完整程序 decision corpus、即时 pristine score 与 run/component/
  config/时间前瞻审计，并明确它与 COTA 的 actor-conditioned continuation return 是不同 estimand。
- 联合边界：2024 Guided Evolution 更早已覆盖二元 ML-program discriminator、跳过候选执行及 PAM/PAM-RT 搜索引导；
  CPRD/BoN 又已覆盖 comparison distribution→deployment estimand 的一般理论。COTA 的新增直接重叠是 exact-prefix
  continuation advisor。故 comparator、execution skipping、runtime gate 与“pair construction 决定 estimand”均非我方
  通用 novelty；只保留完整 Python MLE sibling distribution 上的 run-clean、连续分数、盲态时间前瞻领域实证。
- 最新 immutable snapshot=`ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e`：first-960
  provisional=404/960 runs、11,310 endpoints、2,884 structural pairs、31 tasks；closure=false、label vault=false、
  outcome files=0。target-300 独立支持人口=129 runs/41 archives，remaining=171，truth 未读；两个人口不得混池。
- historical-v11-train↔future identifier-erased audit 已在 5,519 historical endpoints 与 11,299 可 fingerprint future
  endpoints 上完成；5,923,921 exact candidate checks、Jaccard≥0.85 links=`0`，cross-run/cross-task=`0/0`。这是
  benchmark-integrity 正资产，不是 predictor effect，closure 后必须重跑。
- opportunity-yield 404-run 外延按预注册正式 NO-GO：E1/E5 PASS，E2/E3/E4 FAIL；最大单-drop attribution=
  `1.0617531614480789`，删除 dominant OSIC 后反转不保留，run→pair TV 的 yield fraction=
  `0.44105064109821923`。只保留 run-level coverage 与 pair-micro task weight 背离的描述性诊断，不 rescue 机制主张。
- 学长 `dojo-reproduce` 最新精确 HEAD=`61459c0a1248900079dafed7c505afa87e476b40`，没有新的 clean scaling outcome。
  latest future producer 仍未观察到真实 `*.config_v2.jsonl`，旧 archive 禁止回填。
- 已针对该精确 HEAD 交付 config-v2 producer auto-hook patch，SHA-256=
  `56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`。fresh Linux focused/full=
  `19/84 passed`（full 另有 1 skipped）；128 个合法变体与独立 v2 exporter 字节全等，4 个非法变体共同拒绝，
  secret=`0/0`。状态仅为 `PATCH_VERIFIED_NOT_DEPLOYED`；学长 review/cherry-pick 后的下一批才可形成真实 sidecar。
- 历史 schema-only compatibility smoke 又用 metadata-only 规则冻结 20 个真实 `dojo_config.json`：20/20 两实现
  row/bytes 全等，覆盖 7 tasks、2 clients、2 solver fingerprints、9 strata；forbidden opens=0、sidecar writes=0。
  这不读取 env/outcome，也不回填 provenance，只排除 synthetic fixture 与当前可见真实 config shape 不兼容。
- 下一动作：保持盲态摄取和 prediction escrow monitor；等待真实 v2 sidecar 后做 source/expected/config composition 与
  support audit。只有 support gate 通过，才提交模型×数据×seed×GPU·时矩阵请求 clean scaling 重训；当前不启动 GPU。

## 0. 15:50 动态覆盖（覆盖下文冲突的旧 monitor/coverage/task-balance 状态）

- task-balance v1 的输入链已确认下游继承 withdrawn prediction matrix：旧 guard 直接读该 matrix 的逐任务
  pair counts，旧 forward 又绑定该 guard 与另一 value-reading matrix。因此 v1 的 `657→645` 算术虽未被证明错误，
  但其“first-960+closure 前严格零 prediction-value access” provenance 已撤回；旧 artifacts 原样保留，只作历史记录。
- structural-only v2 已从独立 structural gate、snapshot-bound accumulator summary、其 SHA-256 绑定的 first-960
  ledger 和 receipt-only independent receipt 重建同一算术。正式 fresh Linux focused/full=`4/1113 passed`；
  baseline/current pairs=`2635/2755`、debt=`657/645`、delta=`-12`，current OSIC share=
  `0.308529945553539`，25% cap 与即时 route-away 遵从仍失败。该结果只恢复结构算术，不恢复 v1 provenance，
  也不是 predictor effect。
- 公开结果 commit=`b90429ddc817c72bae81eadd32f444174326babb`；fresh public post-push worktree 又通过
  focused/full=`8/1117 passed`、结果包 inner manifest=`12/12`、检出前后 `git clean=true`，post-push
  manifest=`5d645f21aa9fe61f88c90c350e75bf3f8acfb5680c7c5d232e18c1943e39fcb4`。分支可能有仅文档后继，
  每次接手仍须先 fetch。
- 14:27 metadata-only 复核：first-960 仍为 366/960 runs、10,683 endpoints、2,755 structural pairs、30 tasks，
  snapshot=`8579d7cd...d9248`；closure=false、label vault=false、outcome/scorer-prediction opens=`0/0`。
- 当前顶层进程：intake watchdog=`2247187`、replacement intake monitor=`2400213`、transition snapshot-chain=
  `2320379`、WL snapshot-chain=`2374019`、receipt-only join=`2374760`、future config-v2 readiness=`2385217`。
  旧 intake PID `2247183` 已被 replacement monitor 接替，不应再作为存活判据。
- 学长 archive source 最新仍是 0824；`myfork/dojo-reproduce` 精确 HEAD=`2b22f3102a2a64cb89ebcae9ede4d8eb72e1430d`，
  `src/mle_critic/docs/outcomes` 仍只有 0812/0817/0820 三批文档。metadata-only 搜索仍未发现
  `*.config_v2.jsonl`，故 future exact-stratum clean scaling 尚不能启动。
- clean-provenance Decision Corpus Evidence Index v7 已从未污染 v5 重建，不读取 v6 或 withdrawn matrix/guard/crosswalk
  路径；14 entries、37 JSON artifacts、3 bound files、434 assertions 全部独立通过。fresh Linux focused/full=
  `10 passed, 1 skipped` / `1127 passed, 1 skipped, 47 warnings`，A/B 均逐字相同，production forbidden opens=0。
  source commit=`a83bebfdb8dcf59bea21a1b84269b2e87bf7a02e`；结果包位于
  `phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/`。
- replacement ABC crosswalk v2 已从公开 source commit=`c97371d7433b808933624b706a848a644991139c` 的 fresh
  Linux worktree 通过：24 items、29 clean evidence files，删除 6 个污染 IDs、加入 11 个 clean IDs，人工状态仍固定
  `9/9/5/1`。focused/full=`11 passed, 1 skipped` / `1144 passed, 1 skipped, 47 warnings`；production removed
  evidence/prediction/outcome path hits=0，GPU/API/model-fit/base-update=`0/0/0/0`。crosswalk/independent SHA-256=
  `65cbf6cf...1487ee` / `242ef697...5dd06`，formal manifest=`1552c911...ffcef`；结果包位于
  `phase1/results/agentic_benchmark_checklist_crosswalk_v2_20260826_c97371d/`。这是审计来源修复，不是 predictor
  effect 或 D&B 合规总分。
- 新增的 outcome-blind fuzzy-clone audit 在公开 source commit=`cb368f95c5374fd2ab7448455b3ba3af054d02ec`、
  snapshot=`8579d7cd...d9248` 上 formal 全门通过。10,683 endpoints 中 10,674 可 fingerprint（coverage=
  `0.9991575400168492`）；Jaccard≥0.85 有 7,069 near-duplicate pairs，但全部在同一 physical run：
  parent-child/sibling/same-run-other=`4078/50/2941`，cross-run/cross-task=`0/0`。0.95 下 2,758 pairs 仍无
  cross-run edge。producer/verifier A/B、384-doc brute force、focused/full=`13/1163 passed` 和禁读/密钥门均通过。
  这是“高相似演化严格 lineage-local”的 D&B 正资产，不是 semantic uniqueness 或 predictor effect；closure 后重跑。
- 下一项 historical-v11-train↔prospective-first960 bipartite fuzzy-overlap 已在真实 similarity 前冻结：历史侧固定
  5,816 train rows/5,519 unique endpoints/333 runs/23 tasks；同一 token-5gram、0.85/0.95 定义，成功门为两侧
  coverage≥0.99、future affected≤1%、cross-task≤0.5%、无大跨任务 component 与 256×256 brute-force 一致。
  producer/non-importing verifier 的 14 项合成测试已通过；尚未计算真实 edge。只读 historical identity/code，前瞻
  label/outcome/prediction 仍为零访问；通过也仅是 lexical train→future independence 资产，closure 后重跑。

## 0A. 13:31 历史动态状态（被上文覆盖）

- GitHub 发布分支精确 HEAD=`ff9d42672da138a7bf9283e3704ef741567a2a94`；最终 fresh Linux 已通过
  checked-in inner manifest、focused/full=`24/1109 passed`，复现 manifest=
  `3fa4e2451a6eef55cb9d82e1d53828d7ac303ec4ce02fc64d29b8d68c2ea5384`。
- first-960 仍为 366/960 runs、10,683 endpoints、2,755 structural pairs、30 tasks，snapshot=`8579d7cd...d9248`；
  closure=false、label vault=false、outcome opens=0。
- 旧 coverage matrix 会打开 prediction pair files、解析 margins/selections 并聚合 tie/eligibility；其
  `prediction_values_aggregated=false` attestation 为假。0FT/0FU/0FV 的“预闭包合规 coverage”及 evidence-index v6
  相关项已撤回为 historical-withdrawn。旧 artifacts 保留，但不得再引用 orientation/tie/eligibility 数字。
- replacement receipt-only 正式件已认证 WL/transition 对 2,755 canonical structural pairs 的 exact common support：
  pair-file opens=0、prediction values accessed/aggregates=`false/[]`、identity/orientation 未重开、outcome/effect=0。
  这是 benchmark integrity 正资产，不是 predictor accuracy/effect。
- 新 monitor 精确存活：intake PID=`2247183`、intake watchdog=`2247187`、transition snapshot-chain=`2320379`、
  WL snapshot-chain=`2374019`、receipt-only join=`2374760`。旧 WL/value-reading coverage PIDs `2288648/2288649`
  已在 replacement live 后 TERM，历史输出未删。
- WL exact replay focused/full=`22/1094 passed`，producer 与 one-shot current artifact 逐字相同，manifest=
  `ba152f6171a87cc72ec805c8c4ecacd07bd0462b9a93e063709ce19b798e121d`。
- 学长 `dojo-reproduce` 仍为 `2b22f310...`，没有新 outcomes 文档；archive source 最新仍是 0824。metadata-only 搜索
  未发现任何 `*.config_v2.jsonl`，而我方可见原 run root 的最新 `dojo_config.json` 只到 0813。因此 future
  exact-stratum clean scaling 当前阻断于 producer-side outcome-before config-v2 sidecar，不能启动 GPU 矩阵或把 0824
  事后回填成 exact-stratum。
- 当前下一动作：持续盲态摄取；新 snapshot 由 transition/WL 各自重算后，receipt-only monitor 只通过 receipts 合并支持；
  等学长 future batch 在归档前随包上传 config-v2 sidecar，再做 frozen support audit，并在另报矩阵/GPU-hours 获批后训练。

## 1. 项目目标与当前唯一容器

- 目标：发布大规模、富标注的 MLE-agent 搜索树数据集和 predictor study。
- 优先投稿：NeurIPS Datasets & Benchmarks；ACL R&E/ARR 与 ICML 为后续选择。
- 论文容器：**Decision Corpus + Predictor Benchmark + Audit Protocol**。
- 实验台：`facebookresearch/aira-dojo`。MLEvolve 只作现状对照或快速 sandbox，不能作为公平主实验台。
- agent 底座 LLM 不做微调或 RL-finetune；独立 critic/predictor 可按批准协议训练。

## 2. 当前冻结人口与盲态

### First-960 confirmation cohort

- 唯一确认人口是按预注册时间全序排列的 first-960 eligible physical runs。
- 必须另有独立 accrual-closure receipt；1,500 structural pairs 只是支持门，不是提前停止门。
- 最近一次只读状态为 366/960 runs、10,683 endpoints、2,755 structural pairs、30 tasks。
- 仍为 `PROSPECTIVE_COHORT_COLLECTING`，closure 未成立。

### Target-300 support cohort

- target-300 是 score-channel dual-truth 的独立支持 cohort，保留 boundary-archive overshoot。
- 它与 first-960 estimand 不同，不能混池，也不能因达到 300 自动授权 replay/effect。

### 绝对盲态

- first-960 + closure 前，禁止读取 prospective label/outcome vault、accuracy、search utility 或 prediction values。
- 固定 scorer/WL/component extensions 只能写 prediction escrow。
- 最近一次安全证明：label vault 未打开，outcome files 与 scorer prediction files 的 opened list 均为空。

## 3. 最近确认的正面资产

### 3.1 Structural weight trajectory 与 opportunity-yield 分解

在结果前固定 9 个时间点、Shapley 分解和四个主张门后，对 first-240→first-339 做 outcome-blind 双实现复算：

- run-HHI 增量 `-0.007095167549882084`，pair-HHI 增量 `+0.05270955007531816`；
- run→pair TV 增量 `+0.06200795825017402`；
- 260/280/300/320/339 共 `5/5` 个晚期检查点保留反转；
- `30/30` 个 leave-one-task-out 和删除主导 OSIC task 均保留反转；
- opportunity yield 解释 pair-HHI/TV 增量的 `0.6446576519060645` / `0.5951060527094302`。

单批次稳健性门失败：一个 5-run OSIC drop 的 attribution=`0.9641733656841007`；删除后反转符号仍在，但 pair-HHI
增量只剩 `+0.001888405775504004`。因此只能称“符号可泛化、幅度受批次影响”。证据：
`phase1/results/structural_weight_trajectory_7cda_20260826/`；源码 commit `57561d8`。

精确重加权恒等式为 `q_t=p_tY_t/E_p[Y]`；`TV(p_run,p_pair)=0.337082500713674` 也是任意 `[0,1]` task-level metric
在这两种聚合下的 sharp worst-case 差，即 33.71 pp 结构 leverage。它不是已观察 accuracy 差或 expected bias。

### 3.2 Closure-time opportunity-yield aggregation audit

- outcome 前把 `run → final informative pair` 冻结为两级：`R_t → S_t → I_t`；
- structural opportunity yield=`S_t/R_t`，informative retention=`I_t/S_t`；
- closure 后对每个冻结 arm/contrast 精确分解 structural-yield 与 informative-filter 两段聚合影响；
- 每段和总差同时报告 task-metric range × weight TV 的 sharp bound，但不得称 observed/expected bias；
- first-960+closure、frozen registry、exact common support 和 full task universe 是硬 entry gate；
- alternate weighting、decomposition、subgroup 或 sign flip 均不能挽救失败 primary。

fresh Linux focused/full=`17/1064 passed`，18/18 independent checks PASS，verifier A/B 逐字节一致；源码提交
`f970262`。informative cluster size 理论已有先例，本项目只主张真实 MLE-agent chronological sibling benchmark 中的
outcome-blind 证据与预冻结机器审计。

公开结果包 commit `bad6ec5` 的 post-push fresh Linux 复现进一步为 focused/full=`20/1067 passed`，结果包 inner
manifest 全通过，verifier 双跑与 committed receipt 三者逐字节一致；formal `SHA256SUMS` hash=`06832278...3ee246`。

### 3.3 历史：Frozen task-balance guard v1 的首次 forward audit（provenance 已撤回）

> 本小节保留旧 v1 当时实际报告的数值，但其输入链继承 withdrawn prediction matrix，不能再作为严格零
> prediction-value access 的证据。可引用的 replacement 是本文件 0 节所列 structural-only v2。

- `7cda→8579` 新增 27 runs / 120 structural pairs：27 OSIC、93 non-OSIC；
- frozen debt identity 精确：`657 + 3×27 - 93 = 645`，债务净减 12；
- descriptive pair-HHI / run→pair TV 分别下降 `0.0025179437619996525` / `0.009224557381629972`；
- 但 OSIC share 仍为 `0.308529945553539`，25% cap 失败；route-away immediate action 也明确未遵守；
- 只能称 outcome-blind accounting 与结构改善，不能称 causal acquisition effect、producer compliance 或 method effect。

339 个旧 runs 全部保留、旧顺序为新序列 subsequence、同 ID 行不变；2 个新 runs 因冻结总序插入旧 tail 前，故 raw file
byte prefix 不是正确 invariant。fresh Linux focused/full=`15/1080 passed`，双 producer/verifier 逐字节一致；源码
`76bdaad`，formal hash=`688f8b4f...eb45721`。

### 3.4 Provisional first-960 snapshot-chain 完整性

- append-only source 不推出 chronological first-960 membership append-only；960 后迟到的较早 run 可进入并挤出 tail。
- 旧 WL/transition prior-support-subset 检查会误拒绝合法 churn；prefix 不变时旧 WL 还会误拒绝 stasis。
- 新 verifier 固定 immutable snapshot binding、source set/subsequence/row identity、共同 prediction row exact，以及所有
  增删必须由固定 rank 解释；不改 scorer、activation、模型、预测或 estimand。
- 合成 append/stasis/churn 与篡改反例通过；真实 362→366 shadow 为 added/removed=`4/0`、共同/新增 pairs=`2728/27`。
- 不传 legacy prior 的真实 monitor replay 与旧 `8579` 2,755-row predictions 逐字相同；focused/full=`25/1090 passed`。
- 公开结果 commit `9db2d9f` 的 fresh post-push focused/full=`11/1093 passed`，原 7-entry manifest 全通过。
- churn-safe monitor PID=`2320379`，300 秒×72 polls；旧 artifact 全保留，intake monitor 不变。
- 当前真实 removed=0，不能声称真实 churn 已发生；closure 前 support gate 仍 provisional，outcome/effect 未读未算。

证据：`phase1/results/provisional_first960_snapshot_chain_f21a76c_20260826/`；control commit `f21a76c`。

### 3.5 Structural dependency atlas

对 provisional first-240 与当前 339-run 快照做 outcome-blind 双实现复算：

- run-weighted 最大任务占比：0.1083333333 → 0.0914454277；
- run-weighted inverse-HHI：17.8660 → 20.4595；
- pair-weighted 最大任务占比：0.1714990746 → 0.3123339658；
- pair-weighted inverse-HHI：12.0427 → 7.3666；
- 当前 run→pair task-distribution TV：0.3370825007；
- pair 主导任务相对其 run share 的放大：5.0419625915 倍。

结论：新增 runs 的任务覆盖更均衡，不代表 pair-micro benchmark 的隐式任务权重更均衡。这是
D&B benchmark-design 正结果，不是 predictor accuracy 或 search-utility 结果。

2,635 pairs 来自 2,593 physical decision-parent groups；只有 42 个 pair 超过 one-pair-per-parent
基线，因此集中现象不是少数 parent 大量重复枚举造成的简单假象。

证据：`phase1/results/structural_dependency_atlas_7cda_20260825/`；源码/确定性修复/发布提交为
`e19f5f3`、`b8ea5f7`、`1e3ea6d`。

### 3.6 Outcome 前冻结统一 estimand panel

- generic benchmark headline：pair credit → physical parent 内平均 → task 内平均 parents → tasks 等权。
- 强制并列、不得 rescue：task-pair macro、task→run→parent→pair macro、pair micro。
- 所有 arms 必须 exact common pair support，并先算 pair-level arm difference 再聚合。
- 推断：20,000 task bootstrap，seed `20260901`，固定 SHA index，LOTO，run-cluster sensitivity。
- pair-i.i.d. CI 不能做 headline；alternate aggregation/truth/subgroup 不能挽救失败 primary。
- 既有 scaling 与 component-breadth primary 保持原 authority，不被 generic panel 改写。

证据：`phase1/contracts/DECISION_PREDICTOR_ESTIMAND_PANEL_V1.md`、
`phase1/results/decision_predictor_estimand_panel_v1_20260825/`；提交 `1763030`、`b7e90fd`。

### 3.7 Benchmark checklist 与其他数据资产

- ABC/NAS-Bench-style 24 项 crosswalk：PASS_LOCAL 9、PARTIAL 9、INHERITED_UPSTREAM 5、N/A 1。
- 语料唯一性：12,383-card 审计中 raw 99.47%、AST/skeleton 98.96%，0 个 duplicate group 跨 run/task。
- label-noise ceiling、query/init/execution cost、run-level leakage、撤回链、真实 sibling protocol 已有证据。
- 这些资产提高 D&B 完整性，但不能替代 prospective method effect。

## 4. 方法侧最强但仍未确认的信号

学长 2026-08-20 experiment 内 value-pair 两 seed final mean 随 Qwen3
0.6B/1.7B/4B/8B 为 58.64%/60.67%/62.01%/64.68%；8B 比同数据 TF-IDF 61.18%
高 3.50 pp。decision zero-shot transfer 为 56.25%/56.25%/59.06%/59.38%，8B 仍低于
TF-IDF 59.90%。

只能称探索性 capacity/scaling 信号，因为旧实验存在：

- cross-exact-config mixing；
- shared endpoints；
- 周期性 outer-test evaluation；
- 部分大模型未正常结束；
- checkpoint direction/version 问题。

确认只能使用 future exact-stratum producer、train-run-disjoint dev 选择的新 checkpoint，以及从未触碰的
immutable frozen cohort。任何 GPU 重训仍需先报精确矩阵、总 runs、GPU-hours 与 ETA，获得用户批准。

## 5. 已明确关闭或撤回；不得自动复活

- 旧 `decision_pairs_runsplit` test 与 v11 b0/b1/b2 是同一 2,087-row multiset；旧 Qwen3-4B/8B
  checkpoint 的 frozen scoring 已撤回，禁止定位或运行。
- score-channel 排序优越性已预注册 KILL；execution cliff 只留作 missingness 数据诊断。
- 旧 HCE、TD/RL、多保真、Probe-First、E2-A、early-trace、conformal stop、旧 K≥1 lookahead。
- Parent-conditioned patch critic、source-choice、global→local、component/data scaling 等历史候选均须按
  `CURRENT_DIRECTION.md` 的最新撤回链解释，不能因旧 memory 或标题看起来正面而恢复。
- 不把结构支持、工程通过、prediction escrow、support gate 或调度完成写成 method effect。

## 6. 当前运行与数据摄取

最近一次远端只读状态：

- senior archives：226；最新观察到 `0824/osic-pulmonary-fibrosis-progression-8seeds.tar.gz`；
- latest snapshot：`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248`；
- 226 个 archives 已被互斥分为 128 baseline、86 accepted transactions 和 12 structural rejections；当前 ready/pending=0；
- intake、transition、WL graph、coverage matrix、component closure、target quiescence 六个核心监控存活；
- intake/transition/watchdog 以及 component monitor 均存活；watchdog 使用精确命令行检查确认，而非旧的错误 pgrep pattern；
- WL graph、coverage 与 target 在 `8579` baseline 后重启并存活；target recovery postflight 已逐哈希通过；
- 主 intake 每约 5 分钟轮询，最近 `ready=0`、`rejected=12`、`transactions=86`；
- 用户 SLURM 队列为空；没有 GPU 实验正在运行；本次监控恢复 GPU/API/model-fit 均为 0。

动态状态会过期。恢复时使用 metadata-only 脚本重新检查，不能直接沿用本段数字。

若生产维持约 60 eligible runs/day，剩余 594 runs 约对应 9.9 个生产日；这不是日历承诺。

## 7. 学长最新分支状态

- `dojo-reproduce` 最近观察到 `2b22f3102a2a64cb89ebcae9ede4d8eb72e1430d`；
- 新增 RL-judger message 构造、上下文统计、Qwen2.5 0.5B/1.5B/3B/7B mixed
  decision/value full-FT 脚本，以及避免复制/缓存完整数据的 prompt 约束；
- 没有新的 outcome 文档，不能称新 scaling 结果；
- train/test 参数当前指向同一 runsplit 文件；源码审计确认普通模式会按 `intask_split` 分流，因此路径相同本身不构成行泄漏。
- 但 outer test 被作为 Trainer `eval_dataset` 每 10 steps 观察并参与 best-checkpoint 保存，故只能作 dev；旧 scaling 仍是探索性，
  不能称 untouched frozen confirmation。LOTO 还会绕过 `intask_split`，必须与 run-clean frozen-test estimand 分开。

贡献归属：语料生产来自学长；structural dependency atlas 的问题、代码、双实现复核和 benchmark 主张来自
我方；0.6B→8B 探索性 scaling 来自学长。

## 8. 仓库、路径与分支

- 本地 worktree：`C:\Research\New\my_project\MLEvolve\aira-dojo-codex-20260813`
- 本地工作分支：`codex-prospective-decision-v1-20260814`
- 发布分支：`myfork/phase1-value-critic`
- 最近已验证的公开结果包：`bad6ec5428c62b6a213b0d75fa0d1e58d858b5d4`；恢复时最新分支 head 仍以 fetch 为准；
  contract source=`f97026221e099c11fa1ca8f2c13a95c389bea743`
- task-balance forward formal source：`76bdaad398da675aa62614260d63a019594f172c`
- GitHub：`https://github.com/SuperSumanov/aira-dojo-noise-robust`
- 远端 alias：`linux5`
- prospective state：`/research/d7/spc/yzyang4/prospective_decision_v1`
- senior archive metadata source：`/research/d7/spc/yzyang4/external/senior_data/mle`
- 远端 Python：`/research/d7/spc/yzyang4/venvs/exp/bin/python`
- `codex_tmp/` 是保留的未跟踪操作文件，除非明确判断，不删除、不整目录 stage。

## 9. 安全与远端硬规则

- API keys 只放远端 `.env`；不在聊天复述，不写本地、memory、日志或 Git。
- 学长 tar archives 可能含原始密钥；只读 metadata/listing。任何内容读取前必须先做 blind redaction。
- push 前执行 staged filename secret scan：
  `git diff --cached --name-only | grep -icE 'env|key|token|secret'`，并做内容扫描。
- 非交互脚本先 `source "$HOME/env_setup.sh"`，之后再 `set -u`。
- 所有 SLURM 命令必须 `export SLURM_CONF=/opt1/slurm/gpu-slurm.conf`。
- QOS 上限 4 jobs / 8 GPUs；避开 `projgpu7`、`projgpu8`、`projgpu33`、`gpu36`、`gpu38`。
- SSH 内层引号会被剥；复杂逻辑写成 LF 脚本、scp 到远端再执行。
- Windows 不跨 shell 拼接删除/移动命令；任何递归删除/移动前核验绝对路径。
- commit 标题若含数字，只能复制程序打印并验证过的数字，不能心算。

## 10. 实验纪律

- 每个长实验先完整执行 13 项 preflight，给目标、硬件/软件、固定项、成功/kill gate、矩阵、总 runs、
  GPU-hours 和 ETA。
- 新代码路径先做 CPU/tiny smoke；声称改了旋钮必须从 run artifact 反验。
- 保存 commit、版本、全部 seed、完整命令/config/environment；一行一个 run 写 CSV。
- 报 task/run 分解、median、跨 seed 方差和 clustered inference；不只报均值或单次数字。
- 训练期禁止访问冻结 test；任何外部 evaluator 使用 pristine code 与访问审计。
- 保留失败、INVALID、KILL 与撤回记录，不能只留下漂亮结果。

## 11. 恢复时的安全顺序

1. Fetch `phase1-value-critic` 和学长分支，读取 `CURRENT_DIRECTION.md` 顶部最新日期段。
2. 只读检查 Git drift、archive metadata、latest snapshot、六个核心 monitor、intake log 与正确 SLURM 队列。
3. 不打开 tar bytes、outcome/prediction vault 或旧 checkpoint。
4. 若有新 archive，让既有 append-only intake 与 stability gate 处理，再报告精确增量。
5. 没有 first-960 + closure 时，优先做 outcome-blind benchmark/integrity 工作；不要制造新的后验 effect 假设。
6. 如需 GPU，先提交精确实验矩阵和预算给用户批准；当前没有自动授权的 GPU effect 主实验。
7. 结果与代码完成后做 fresh Linux reproduction、独立 verifier、secret scan，再 commit/push。

## 12. 关键入口

- 唯一方向：`phase1/CURRENT_DIRECTION.md`
- 学长建议：`phase1/ADVISOR_DIRECTIVES.md`
- 给学长的近期汇报：`phase1/实验记录/2026-08-26/近期进展汇报_2026-08-26.md`
- 结构时序分解：`phase1/results/structural_weight_trajectory_7cda_20260826/README.md`
- 重加权恒等式：`phase1/实验记录/2026-08-26/OpportunityYield_重加权恒等式与影响上界.md`
- structural atlas：`phase1/results/structural_dependency_atlas_7cda_20260825/README.md`
- estimand panel：`phase1/results/decision_predictor_estimand_panel_v1_20260825/README.md`
