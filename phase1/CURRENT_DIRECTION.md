# 当前研究方向唯一入口（2026-08-15）

> 本文件按日期与撤回链整理，覆盖最近两周的实验记录与 Git 提交。后续实验先读本文件，
> 不得用更早报告、旧 `AGENTS.md` 摘要或旧 HCE 配置覆盖这里的裁决。

## 0X. 2026-08-15 项目级纠偏：评分通道是唯一主实验，failure-censored 结果降为 benchmark 支线

本节晚于 0W，并按项目级方向决定覆盖 0W 及更早小节中关于“当前主线/下一实验”的措辞。论文容器保持为
MLE-agent 搜索树的 NAS-Bench-style 数据集与系统性 predictor study；当前活跃科学问题是 execution cliff 与
评分通道。冻结发现集上，pristine 外部 `submission.csv` 分数相对 stdout self-report 的正效应仍只是机制候选，
不能写成已确认、已加速或可外推到 silent candidates。

1. **唯一主实验**仍是机制 commit 后至少 150 个新 physical runs 的前瞻 score-channel 复现：同一 120 秒、
   共同候选上的 `sub_score - stdout_val` tie-aware top-1；约 690 replays、17--23 GPU·h。它必须同时满足
   预注册资格门、任务占比门和用户对确切矩阵/预算的批准；当前保持 `NOT SUBMITTED`，禁止 optional stopping。
   8 个 0813 新归档经 credential-first intake 得到 47 个唯一 physical journals；47/47 的 root creation time
   都严格晚于机制 commit，覆盖 8 tasks，dominant task=`8/47=0.170213`。因此时间与任务占比门暂时满足，
   但距 150-run 固定门仍差 103；label vault 未读，finite-sibling parent 资格尚未冻结，不能提前开跑。
2. **立即支持实验**只允许复用学长在旧 validation 上事先锁定的 Qwen3-4B/8B checkpoint，对 v11 frozen
   b0/b1/b2 各一次评分。不得重训、不得看 frozen 后挑 checkpoint；extension 单列。当前 evaluator 已就绪，
   但仓库尚缺两条 checkpoint 的绝对路径、训练配置与锁定收据，因此不得猜路径开 GPU。
3. 0U--0W 建立的 labeled-fragment、source-opportunity identity 与 failure-status registry 保留为重要数据资产：
   721/870 incomplete parents 可恢复 sibling identity，902/996 missing identities 可恢复 journal status，其中
   893/902 为 execution error。这些结果限定 benchmark estimand，但不取代评分通道确认。
4. 预注册 hurdle baseline 已完成确定性复跑与独立复核，裁决为
   `VERIFIED_FAILURE_CENSORED_MECHANISM_ONLY`。构造门通过，但 frozen 上 hurdle TF-IDF 相对 quality-only 的
   scoreability 增量仅 `+0.0200`，task-CI `[-0.0505,+0.0884]`；utility 增量 `-0.00135`，task-CI
   `[-0.01527,+0.01785]`。`method_positive_claim_allowed=false`，不得把它升级成方法主线。
5. first-960 critic confirmation、Probe-First/E1 continuation、随机日志接入、旧 HCE/TD/RL、多保真三臂和已关闭
   critic 变体均不是当前主实验；只有新的明确预注册、资格门与预算批准才能重开。已经 outcome-blind 运行的语料
   intake monitor 可继续记录元数据，但不得读取 outcome 或据其改方法。

直接证据：

- `phase1/results/source_opportunity_hurdle_v11_20260815_c89c5bd/README.md`；
- `phase1/results/score_channel_prospective_eligibility_20260815/README.md`；
- `phase1/实验记录/2026-08-15/SourceOpportunityHurdleBaseline_预注册与执行前检查.md`；
- `phase1/实验记录/2026-08-13/评分通道前瞻复现_预算与预注册草案.md`；
- `phase1/README_8B.md`。

## 0W. 2026-08-15 最新覆盖：90.56% missing identities 找回 node，99.00% 为 execution error

本节晚于 0V。稳定主线进一步收敛为 physical-run-clean、decision-local 的 MLE-agent **failure-censored
source-opportunity benchmark** 与 first-960 prospective confirmation；完整 labeled choice-set、missing-at-random
和通用 critic 方法收益仍不允许，旧 HCE、多保真、probe、TD/RL 与已关闭变体均不恢复。

1. 结果前冻结的 `source-opportunity-journal-status-v1` 在精确 commit
   `42cb6b1ac0575f26350b72519b3d558aab5a084a` 上扫描八个预定 allowlisted roots；不读 tar 其他 member、env、
   numeric grade、code/stdout、pair orientation 或 first-960。producer 与不 import producer 的 verifier 一致裁决
   `VERIFIED_HIGH_COVERAGE_MISSING_STATUS_REGISTRY`。
2. 996 个已恢复 missing sibling identities 中，902 个唯一绑定 source journal node，recovery=
   `0.9056224899598394`，source collision=0、journal parent mismatch=0。train/frozen/extension coverage 分别为
   `0.9089726918075423/0.8888888888888888/1.0`。
3. 902 个 recovered nodes 中，893 个为 `EXECUTION_ERROR`，9 个为 exit-0 但 `OFFICIAL_GRADE_ABSENT`；execution
   error share=`0.9900221729490022`。因此有限 labeled fragment 的主导缺口不是任意抽样，而是执行失败引起的
   informative censoring；剩余 94 个 targets 保持 `SOURCE_JOURNAL_NOT_FOUND`，不得外推类别。
4. 远端聚焦测试 `7 passed in 0.16s`，完整 `phase1/tests` 为 `299 passed in 26.21s`；producer/verifier 分别
   311.49/274.61 秒，产物高置信凭据命中 0。首次 `a1` 在结果前因 byte-identical journal copies 的路径 hash
   被误判为冲突而 fail-closed；新增回归测试后，`a2` 按 source SHA 折叠副本。
5. 正面论文主张改为：发布真实 MLE-agent source opportunity、retained label 与 failure-censor status 的分层数据契约，
   并证明只在成功候选内做 pair ranking 改变了部署 estimand。下一方法门只能是预注册的 feasibility→quality 两阶段
   baseline 与同预算 prospective utility；hurdle 原语本身不申新，方法收益未验证前仍以数据/benchmark 贡献为主。

直接证据：
- `phase1/results/source_opportunity_journal_status_v11_20260815_42cb6b1/README.md`；
- `phase1/实验记录/2026-08-15/SourceOpportunityJournalStatus_预注册与执行前检查.md`。

## 0V. 2026-08-15 最新覆盖：82.87% source-incomplete parents 可恢复完整 sibling 身份

本节晚于 0U。稳定主线现为 physical-run-clean、decision-local 的 MLE-agent **labeled-fragment benchmark +
显式 source-opportunity identity registry** 与 first-960 prospective confirmation；完整 labeled choice-set 主张仍撤回，
旧 HCE、多保真、probe、TD/RL 与已关闭 critic 变体均不恢复。

1. 结果前冻结的 `source-opportunity-identity-recovery-v1` 在精确 commit
   `3faf0013ff34f8a6f4c33ac99b0431b5ef394580` 上运行。producer 与不 import producer 的独立 verifier
   一致裁决 `VERIFIED_HIGH_COVERAGE_SOURCE_IDENTITY_RECOVERY`；远端聚焦测试 `6 passed in 0.13s`，完整
   `phase1/tests` 为 `292 passed in 36.39s`，产物高置信凭据命中为 0。
2. 870 个 source-incomplete parents 中，721 个能由 parent `children_ids` 精确恢复全部缺失 sibling 身份，
   parent-equal recovery=`0.828735632183908`；train=`0.8180451127819549`、
   frozen=`0.8556701030927835`、extension=`1.0`，均通过预注册门。共恢复 996 个 missing child IDs。
3. 2,328 个 source-complete、非 orphan 正控全部精确对齐。149 个不可恢复 incomplete parents 恰好全部是
   orphan parent cards；非 orphan 不可恢复数为 0。这把边界从不透明过滤收缩为一个明确、可机读的 orphan
   provenance 缺口。
4. 允许的新资产仅是 identity registry：对可恢复 parent 发布 source sibling IDs、retained/missing 标志与
   `missing_status=UNKNOWN`、`missing_outcome=UNKNOWN`。它不证明 missing-at-random，不恢复执行/评分/剪枝原因，
   也不允许把 fragment 内 predictor utility 写成完整 choice-set utility。
5. 下一门是 journal-level status recovery：在读取任何 tar member 前先做路径 allowlist、流式凭据红删与 archive
   hash 固定，再判断 996 个 missing identities 中有多少能绑定 generation/execution/evaluation receipts。没有该证据，
   不训练 censor-aware 模型，也不猜缺失机制。

直接证据：
- `phase1/results/source_opportunity_identity_recovery_v11_20260815_3faf001/README.md`；
- `phase1/实验记录/2026-08-15/SourceOpportunityIdentityRecovery_预注册与执行前检查.md`。

## 0U. 2026-08-15 最新覆盖：撤回完整 choice-set 主张，发布单位改为 labeled sibling fragment

本节晚于 0T。稳定主线仍是 physical-run-clean、decision-local 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation，但 **`choice-set-faithful` / 完整 source choice set 主张已撤回**；旧 HCE、
多保真、probe、TD/RL 与已关闭的 critic 变体均不恢复。

1. 结果前冻结的 `raw-choice-set-completeness-v1` 在精确 commit
   `6610618a89c91bd2dbea2ea5be05e8acaac11e94` 上审计 v11 的 16,012 cards、5,897 b0 pairs 与
   3,252 parents。producer 与不 import producer 的独立 verifier 一致裁决
   `VERIFIED_LABELED_SIBLING_FRAGMENT_BOUNDARY`；远端聚焦测试 `11 passed in 0.21s`，完整
   `phase1/tests` 为 `286 passed in 24.95s`，输入与产物高置信凭据命中均为 0。
2. 结构完整性没有失败：所有 parent 的发布端点均为同 run/task/parent 的 finite retained direct children；发布
   `set_size` 均等于 finite retained child 数；有 parent card 时其 `children_ids` 均包含所有 retained children。
   因此 b0 可称 **结构有效的带标签兄弟片段**，但不可称完整 source opportunity set。
3. source retention 未全过：train 仅 1,628/2,293 parents 保留完整 source set，frozen 为 651/845，extension
   为 103/114；对应 parent-equal mean retention 为
   `0.8885485280818947/0.9140433925049315/0.9678362573099415`。train 另有 10 个 source size>5 parents，
   不能用旧生成上限作默认解释。
4. 当前 pair/top-1 结果的 estimand 统一改写为 **published labeled fragment 内的决策风险**。在恢复 source
   identities、缺失状态与可识别的 missingness 证据前，不得把它外推成 agent 当时面对的完整候选集效用；first-960
   scorer 保持冻结，但最终解释也必须遵守这一边界。
5. 下一正面突破门改为 outcome-blind source-opportunity recovery：只用 lineage/source journal provenance
   衡量能否恢复完整 sibling identities、失败/未评分状态与 inclusion mechanism。它若通过，将形成比当前 pair
   文件更强的 censor-aware MLE decision resource；若不通过，诚实保留 fragment benchmark，不再使用完整候选集措辞。

直接证据：
- `phase1/results/raw_choice_set_completeness_v11_20260815_6610618/README.md`；
- `phase1/实验记录/2026-08-14/RawChoiceSetCompleteness_预注册.md`；
- `phase1/实验记录/2026-08-15/RawChoiceSetCompleteness_执行前检查.md`。

## 0T. 2026-08-14 最新覆盖：scheduler receipt 内部闭环通过，生产真实性门仍关闭

本节晚于 0S。稳定主线仍是 physical-run-clean、choice-set-faithful 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation；随机兄弟日志仍是未接入生产的 gated interventional resource。

1. commit `6a68c7dd7cdcf2fe5faf25017b3ef8bcb3a1d4b5` 新增不 import assignment producer 的
   scheduler receipt verifier。它先通过独立 assignment verifier 重建 frozen assignment，再从 canonical eligible-set
   receipts 重做 SHA-256 top-m 无放回随机化，要求 selected parent 集合、receipt hash 与 `m/n` propensity 全部精确。
2. committed budget receipt 必须绑定 assignment manifest/summary；每个 assignment ID 一对一替换一个唯一标准
   production slot 并占用一个唯一 randomized slot。若 assignment 数为 `|A|`，强制
   `B_standard_after=B_before-|A|`、`B_randomized_after=|A|`、`B_total_after=B_before`；任何重复、漂移、
   outcome-bearing key、凭据形状、非 canonical JSON 或时间逆序均 fail-closed。
3. 精确 commit 的全新 Linux worktree 中，相关测试 `19 passed in 0.39s`，完整 `phase1/tests` 为
   `275 passed in 25.48s`；安全扫描可疑文件名 0、高置信凭据 0，下载后 5 文件 hash mismatch=0。Windows 本地
   完整套件的两项失败均来自既有测试缺 SciPy，Linux 全套通过排除了本轮回归。
4. 本轮没有伪造生产 true flag。通过只允许写
   `upstream_selection_probability_reconstructed_from_declared_eligible_sets=true`、
   `committed_budget_decrement_internally_consistent=true` 与 `budget_conserved_within_receipt=true`；同时强制
   `eligible_stream_completeness_verified=false`、`external_scheduler_receipt_authenticity_verified=false`、
   `upstream_selection_probability_verified_by_assignment=false`、`actual_production_budget_decrement_verified=false`、
   `production_activation_authorized=false`、`causal_claim_allowed=false`。
5. 下一门必须来自真实 scheduler：只读 append-only eligible-event stream、连续 sequence/window 完整性、实际预算
   transaction 与 pre-outcome sealing。未经与学长共同确认生产接口和机会成本，不得接入其日常语料生产；E1 批准
   不自动授权该 sidecar，E2/E3 仍关闭。

直接证据：

- `phase1/results/scheduler_receipt_verifier_20260814_6a68c7d/README.md`；
- `phase1/verify_randomized_sibling_production_receipts.py`；
- `phase1/tests/test_randomized_sibling_production_receipts.py`；
- `phase1/实验记录/2026-08-14/RandomizedSiblingLogging_v1_设计冻结.md`。

## 0S. 2026-08-14 最新覆盖：随机兄弟日志契约通过合成验收，生产接入仍未授权

本节晚于 0R。稳定主线仍是 physical-run-clean、choice-set-faithful 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation；E1-Q 仍只是标签可行性支线，E2/E3 仍关闭，也没有切回旧 HCE、多保真或 probe。

1. 近期防 scoop 审计进一步确认：AgentRM、ReLoc、DataPRM、CePRM、PRO-Step 与 UATS 已覆盖 MCTS/agent
   状态价值、同 parent revision/sibling 监督、环境感知过程奖励和不确定性预算分配等原语。因此 tree critic、
   sibling pair、listwise、hurdle 或 uncertainty 本身均不申新。可防守的正面资产收缩为真实 MLE 场景下
   physical provenance + exact choice set + outcome-blind randomized intervention + cost/propensity 审计。
2. commit `59b5b8c698c6d687510cc184034d887619324243` 冻结 Randomized Sibling Logging v1：输入只允许
   parent/sibling 身份与哈希、上游选择概率声明、receipt hash 和 displaced-slot 声明；禁止 code、score、label、
   execution status 等 outcome-bearing 字段。Broad 层每 sibling K=1；task-fixed calibration 层 K=2；兄弟顺序与
   rollout seed 独立哈希随机化，并写出严格 propensity。
3. 精确 commit 的全新 Linux worktree 中，聚焦测试 `25 passed in 1.04s`，全部 `phase1/tests` 为
   `263 passed in 27.85s`。独立 verifier 不导入 producer，逐项重建 6 parents、2 tasks、16 rollout jobs 与
   16 candidate-execution slots，裁决 `VERIFIED_OUTCOME_BLIND_RANDOMIZED_SIBLING_ASSIGNMENT`；产物 outcome=0，
   远端可疑文件名与高置信凭据命中均为 0，下载后 16 个文件 hash mismatch=0。
4. 该验收明确不是生产闭环：`actual_production_budget_decrement_verified=false`、
   `upstream_selection_probability_verified_by_assignment=false`。只有生产 scheduler 独立签名真实被替换 slot、
   真正扣减日常预算并记录上游 propensity 后，才可称 budget-neutral interventional logging。未经与学长共同确认，
   不得接入其约 60 runs/day 的生产，也不得宣称因果效果或方法收益。
5. 第一轮远端验收在测试前暴露既有 LFS 404；坏 run 保留。对应 1,119,807-byte 对象经 43-member tar 流式扫描
   （可疑名 0、高置信凭据 0）、OID 校验后仅补传既有对象；集群对精确 commit/path 重新 fetch 并重算完整 SHA，
   状态 `VERIFIED_REMOTE_LFS_OBJECT`。这修复仓库可获取性，不改变任何科学结果。
6. prospective monitor 截至 `2026-08-14T11:09:48Z` 仍为 128 baseline、0 ready transaction、0 outcome read；
   学长 `dojo-reproduce` 仍为 `2cb6f0c57790407cae84070d3eb475da3cbe9597`。在新 archive 到达前不读取或调参。

直接证据：

- `phase1/results/randomized_sibling_logging_contract_20260814_59b5b8c/README.md`；
- `phase1/实验记录/2026-08-14/RandomizedSiblingLogging_v1_设计冻结.md`；
- `phase1/实验记录/2026-08-14/最新直接竞品与正面突破_防scoop审计.md`；
- `phase1/实验记录/2026-08-14/LFS对象_a96e41b_补传审计.md`。

## 0R. 2026-08-14 最新覆盖：E1-Q 标签可行、label repeatability v2 入主线，方法收益仍未解锁

本节晚于 0Q。稳定主线仍是 physical-run-clean、choice-set-faithful 的 MLE-agent 决策数据/benchmark 与
first-960 prospective confirmation；没有切回旧 HCE、多保真或 probe。Balanced continuation 只是 gated 支线。

1. 0Q 的 Qwen smoke fail 后来被定位为 task-type validator bug：accuracy 任务的 boolean submission 被错误强制
   为 float。immutable artifacts 在 0 新执行/API/GPU 下重验为 2/2 合规。随后另立 fresh-anchor E1-Q，固定
   `qwen3-coder-flash`、one-shot/0 retry、两任务各一新 anchor、两 sibling、K=2、H=1，并排除旧 E1 runs 与
   frozen b0/b1/b2 overlap；这改变 operator policy，不能追认旧 DeepSeek E1。
2. E1-Q 在 source commit `0d1ca6fd948d24f23d4abecc3298d8ff6ef53974` 完成两阶段 8/8 rollout、
   16/16 candidate processes、8/8 operator calls，retry/analyze/D_test read 均为 0。complete-coverage 前
   `sealed_values_opened=false`，之后一次性打开 16 receipts；独立 archive verifier 重算 8 rollout、4 sibling、
   2 task 和 summary，summary SHA=`f98ee3d663fab2d1085ec9cefcf14c36d17e15b966ba45eb90ef538f49f92d11`。
3. 两任务的 sibling winner 在两次 replicate 中均一致（2/2），四个 balanced `V_1` labels 非退化，按预注册裁决
   为 `E1Q_LABEL_FEASIBILITY_OBSERVED`。但只有 2/8 positive gains、0/8 达 `0.01` practical delta；实际
   candidate 成本 `1.3663852174544364 GPU·h`。因此这是 label-design feasibility 正结果，不是 continuation
   方法收益。
4. compact collection 漏了预注册要求的 execution-status 明细，未改写原 collection；status-only reporting
   repair 从已过独立 worker verifier 的 receipts 导出：warm=6 ok+2 execution_error，continuation=6 ok+
   1 execution_error+1 timeout，两阶段均 6/8 artifact 被 D_search/D_val 评分。它支持未来把 validity 与
   conditional gain 分开设计，但不证明 hurdle critic 有效。`primary_gate_claim_allowed=false`、
   `e2_e3_unlocked=false` 不变。
5. 旧 `noise_ceiling.py` 的 node bootstrap 实际没使用 resampled nodes；original single 与 repeat mean 也不可交换，
   所以旧 `0.9923/0.9578` 不再作 release-grade ceiling headline。预先冻结的 v2 在 commit `4e3bebe` 通过
   4 项聚焦和全部 256 项远端测试；独立 verifier 重建三种 retry sensitivity、PAVA、九个 v11 transport 与
   2,000 次 task bootstrap。
6. v2 在 207 cards/10 tasks/3,017 pairs 上的 original-vs-first-regrade raw agreement=
   `0.9658601259529334`，task-cluster CI=`[0.9438143714671886,0.9913402891372938]`。frozen b0 transported
   repeat agreement=`0.9134305309964227`，CI=`[0.8353851659068688,0.9494041168867747]`；对称独立误差
   模型量=`0.9488254145489123`，CI=`[0.8571329199113228,0.9682215874512448]`。但 measured-task pair
   coverage 只有 `0.732977303070761`，必须写明 10→22 task extrapolation，不能称全任务 empirical ceiling。
7. 相邻领域已明确覆盖 candidate-set sampling 导致 metric/模型排名反转（推荐系统）和 NAS predictor 的
   rank/search-utility/query-cost 比较；因此统计原理本身不申新。可防守核心收缩为真实 MLE-agent 的 physical run、
   parent choice set、effective support、gap/noise/cost 与 prospective boundary 的可执行审计标准。v11 audit 已验证
   九个 pair sets；frozen b0 为 1,498 pairs/845 parents/92 runs/22 tasks，train--frozen 四层 overlap 全为 0。
8. prospective monitor 仍健康但没有 activation 后新 archive：128 baseline、0 ready transaction、outcomes
   unread。学长 `dojo-reproduce` 最新仍为 `2cb6f0c`；其 checkpoint direction bug 尚需在下一轮训练前修复。

直接证据：

- `phase1/results/balanced_continuation_e1q_20260814_0d1ca6f/README.md`；
- `phase1/results/label_repeatability_v2_20260814_4e3bebe/README.md`；
- `phase1/results/decision_corpus_audit_v11_20260814/README.md`；
- `phase1/实验记录/2026-08-14/ChoiceSetFidelity_当前主张边界.md`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_E1Q_裁决.md`；
- `phase1/实验记录/2026-08-14/LabelRepeatabilityAttestation_v2_裁决.md`。

## 0Q. 2026-08-14 最新覆盖：Qwen 执行门与 selective-execution 二次路线均关闭

本节晚于 0P。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；没有切回旧 HCE、多保真或 probe。

1. fresh-anchor Qwen execution-only smoke 在 commit `d89311a` 的新 root 上完成 2 个真实候选执行、0 次
   operator API 调用、0 次 frozen/first-960 读取。tabular 通过 public submission shape；spaceship 虽进程
   rc=0，但 boolean prediction 无法按 float 解析。冻结门要求 2/2，正式状态为
   `VERIFIED_QWEN_EXECUTION_SMOKE_FAIL`，因此 Qwen E1-Q 不得启动、不得换 prompt/model/cap 或补样本追认。
2. 随后冻结 `selective_execution_v11_retrospective_discovery_v1`，只在既有 v11 train-run OOF 的 1,520 个
   exact-two parents 上问：char-TFIDF、static LR 与 frozen head 三者一致且高置信时只执行共同 winner，
   其余执行两个，能否形成安全 cost--risk 点。协议明确承认 FOREAGENT、CIPHER、AgentSwift、CORA 与
   selective-code literature 已覆盖原语；本轮即使为正也只能是 benchmark operating point。
3. 科学 commit `7a1562a4506f17d713467956c797fb0d3226a8c5` 的 producer 与不 import producer 的 verifier 一致裁决
   `SELECTIVE_EXECUTION_DISCOVERY_NO_UNLOCK`：selected=293 / runs=129 / tasks=22；候选数节省
   `0.09638157894736842`，但 micro/run/task accuracy 仅
   `0.5494880546075085/0.5572152868664496/0.5575913930507589`，run/task CI 均跨 0.5；相对 matched
   char-margin 的 task delta `+0.03502779307071244`，CI=`[-0.05286426757718625,0.13190540852024105]`。
4. q=0.05 的 65-parent/18-task 描述点不满足冻结 support/节省门；margin 在 unanimous pool 内相对 CRC
   subset 也没有富集，故禁止改 q、删 task 或换 vote 集合救活。本路线关闭，不进入 first-960 sidecar。
5. 首次 postflight 因仍在追加的 `run.log` 被放进 manifest 而哈希失败；坏 manifest 原样保留。commit
   `98065c85c1900c6b1ba1e0632204ab8ad63d44db` 只修日志关闭顺序；postflight repair 没有重跑 producer/
   verifier，独立科学裁决不变。
6. 学长 branch 最新 `2cb6f0c` 把 best metric 改成 `eval_pair_accuracy`，却保留
   `greater_is_better=False` 与 `save_strategy="best"`；这会反向选择后续 checkpoint。该 bug 晚于 0812 日志，
   不能追溯解释既有 1.7B--8B 结果；下一轮训练前应单独修成 `True` 并做 best-checkpoint smoke。

直接证据：

- `phase1/results/balanced_continuation_qwen_execution_smoke_20260814_d89311a_a2/VERDICT.md`；
- `phase1/results/selective_execution_v11_20260814_7a1562a45/README.md`；
- `phase1/实验记录/2026-08-14/SelectiveExecution_回顾性发现裁决.md`；
- `phase1/实验记录/2026-08-14/学长DecisionTrainer_checkpoint方向审计.md`。

## 0P. 2026-08-14 最新覆盖：真实 E1 方法结果作废；Qwen 备选过门但 production DeepSeek 仍关闭

本节晚于 0O。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；balanced continuation 仍是 gated 支线，**没有得到正方法结论，也不是负方法结论**。

1. 冻结 E1 在 source commit `e59a759d99dd490b6f8a0011c66dd7c772307b28` 完成 8 个 rollout、
   16 次 candidate attempt、14 次实际 candidate process、8 次 operator API 调用；retry/analyze/D_test
   读取均为 0。候选累计墙钟为 `2047.6709687478572` 秒，即 `0.5687974913188492` GPU·时；537 条顶层
   manifest 记录逐一重算均匹配。collection 的独立 verifier 不 import producer，重建了 8 rollout、
   4 sibling、2 task 行。
2. 该 collection 的零分、tie 和 `0/8` positive gain **全部撤回为不可解释**。首个确定根因是 scorer
   接口不一致：public `sample_submission.csv` 覆盖 `D_search ∪ D_val`，而 v1 scorer 错误要求提交 ID
   恰好等于其中一个 private 10% 子集。干净 commit `f352b013c67fb1b98b17391ba32711faaa780367` 的
   零执行重放把有效提交从 `0/16` 修正到 `6/16`，但这 6 个全是 warm artifact；continuation 仍为
   `0/8`，因此可配对 rollout 为 0。
3. 第二个确定根因是 operator 完整脚本失败：8 个 continuation 调用全部恰好达到 8192 completion-token
   上限；失败谱系为 2 个 `invalid_format`、2 个 `SyntaxError`、4 个 `NameError`。旧 extractor 可能从
   截断响应中取最后一个短代码块，且旧 run 只保留 response SHA、没有可恢复的原始响应，故不能事后补算。
4. scorer 与完整脚本 gate 已修复，并以 mode-0600 raw response 做 hash binding。先验 Qwen 备选探针恰好
   调用 2 次、0 GPU、0 candidate execution：两任务均 `finish_reason=stop`，分别输出 172/104 行、
   1579/1014 completion tokens，状态 `PASS_OPERATOR_ONLY_GATE`。但冻结 E1 的 production operator 是
   DeepSeek，不能用 Qwen 结果宣称原路径已修好。
5. 因此另立 production-matched 两调用门，精确复用 `deepseek-v4-flash`、temperature=0.6、top_p=0.95、
   max=8192、system role 与 180 秒 timeout。spaceship 返回 178 行完整代码并通过；tabular 再次达到
   8192 tokens、`finish_reason=length`，只在 `reasoning_content` 留下未闭合输出，最终状态为
   `FAIL_PRODUCTION_MODEL_OPERATOR_GATE`。原 production path 保持关闭；Qwen 只能作为未来**新 operator
   contract** 的候选，不能追认旧 E1。
6. 因此 `primary_gate_claim_allowed=false`、`e2_e3_unlocked=false`。原 E1 已消耗预算不能被 probe 覆盖；
   任何真实 rerun 都是新的 GPU/API 实验。若换 Qwen，还同时改变 operator policy；必须使用新 run root、
   新预注册和未被本轮 D_val 揭盲影响的 fresh scientific anchors，不能沿用旧批准自动启动。
7. 复现审计发现两个既有 LFS 结果对象曾只有 pointer、GitHub 返回 404：681687-byte fixed-scorer tar 与
   17145534-byte frozen-embedding tar。两者在补传前分别完成 tar 路径、链接、文件名与内容凭据扫描，
   unsafe/name/content hits 均为 0；只补传这两个既有对象后，集群端按 commit 重新 fetch 的 SHA-256 分别为
   `80a21f8d05d52fd602edd61c0e2538c3b18910ca92cefb24ca6040ad4937d379` 与
   `096a3581bfce48c83019f3440e88089d4b8a4dd0a768224493f892941a3d64f7`。语料契约不变：未来只上传
   不可变 batch 一次，merged corpus 仍由 release descriptor + `rebuild_corpus.sh` 逐字节重建。

直接证据：

- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/README.md`；
- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/adapter_replay_f352b01.json`；
- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/operator_probe_summary_1fc6031.json`；
- `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/deepseek_production_probe_summary_9146d82.json`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_E1_裁决.md`。

## 0O. 2026-08-14 最新覆盖：Linux real-adapter mock 关门，E1 获批但仍受 preflight 约束

本节晚于 0N；稳定主线和 balanced-continuation 的 gated 地位不变。

1. 精确 commit `eb2e693b2e1cca931148c504c68239b203b82731` 在干净 Linux worktree 通过 36 项聚焦测试、
   157 项完整 `phase1/tests` 和 13/13 preflight。正式 0-GPU mock 为 1 rollout、2 candidate、2 D_search、
   2 D_val sealer、1 operator process，retry/analyze/API/GPU/Slurm 均为 0。
2. 不 import mock producer 的 verifier 报告 `VERIFIED_ZERO_GPU_REAL_ADAPTER_MOCK`：visible D_val fields=0、
   D_test rows read=0、实际 sealed mode=0600；archive SHA-256 为
   `a58c86a10540b40daecebc118fe8179db9c6dde6b2e516c20ef67ceab56836a5`。
3. 该结果只关闭 synthetic process/receipt boundary，不证明 production container capability isolation，也不证明
   balanced label 或 search utility。此前四次 remote/env/LFS/import/post-scan 失败全部保留，未被成功 run 覆盖。
4. 用户已明确批准既有 E1：2 tasks × 1 anchor/task × B=2 × K=2 × H=1 = 8 rollout jobs、16 real
   candidate executions、预计 3.24 GPU·时。批准不等于立即提交：真实 80/10/10 split、public-only executor、
   D_search/D_val 隔离、真实 assignment 与 13 项 preflight 必须先全部 PASS；E2/E3 未获批准。

直接证据：
- `phase1/results/balanced_real_adapter_mock_20260814_eb2e693/`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_RealAdapter_接口审计.md`。

## 0N. 2026-08-14 最新覆盖：真实 adapter 边界已冻结，执行实现仍待完成

本节晚于 0M。稳定主线与 balanced-continuation 的 gated 地位均不变；本轮是 0-GPU/0-API 接口审计，
不是方法正结果。

1. 当前 MCTS 路径会生成多个 child、自动 debug、调用 analyze，并在抽取失败时重试；它不能满足每个
   transition 恰好一次 operator call、一次执行、零重试的 equal-K 干预，真实 adapter 必须绕开该路径。
2. 当前 `MLEBenchTask.step_task` 默认在进程内读取完整 private answers；旧 HCE 又是 50/25/25，且把
   `dval_score` 放入 orchestrator 可见的 `AUX_EVAL_INFO`。它不能通过改 config 变成当前 80/10/10、
   D_search-only visible、D_val mode-0600 sealed、D_test never-read 的 full-locked 契约。
3. `balanced_continuation_real_contract.py` 已冻结 worker、public execution、D_search、sealed D_val、visible
   step 与 operator request/response 的 exact-key schema、SHA identity、finite-number、POSIX path、
   one-call/no-retry 和 credential fail-closed 规则。新增 12 项接口测试；连同 assignment/worker 测试共
   34 项通过。
4. 当前尚未实现真实 public-only executor、80/10/10 split、隔离的 D_search scorer/D_val sealer 与独立
   collection verifier。下一步仅做 0-GPU mock adapter 端到端烟测；E1 的 8 jobs/16 real executions/
   预计 3.24 GPU·时仍需明确批准，不得因 schema 测试通过而自动启动。

直接证据：
- `phase1/balanced_continuation_real_contract.py`；
- `phase1/tests/test_balanced_continuation_real_contract.py`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_RealAdapter_接口审计.md`。

## 0M. 2026-08-14 最新覆盖：balanced-continuation 完整 synthetic worker E0 关门

本节晚于 0L。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；balanced continuation 仍只是 gated 方法扩展，没有变成论文已证实正结果。

1. 在精确 commit `f7b75a5b7d353116a0ecb0ca94ed3e7ca9870585` 的干净远端 worktree，22 项聚焦测试、
   全部 143 项 `phase1/tests` 和 13/13 preflight 均通过。正式 E0 随后完成 24 个 rollout、72 次 synthetic
   candidate attempts、48 次 continuation operator calls；24 个 workspace 路径和 token 均唯一，retry 与
   replacement 均为 0。
2. assignment 由不 import producer 的 verifier 独立重建；每个 rollout 又由独立 worker verifier 重验代码链、
   operator、outcome、backend receipt 与 workspace；collection verifier 验 exact-K、完整 block、总执行数和
   workspace 唯一性；最后 452 个文件逐一重算 SHA，mismatch=0。
3. checkpoint/resume 现为 fail-closed：PENDING 没有完整 durable receipt 时禁止自动重跑；有 receipt 时也必须在
   继续花费前重验全部既往代码/receipt/workspace 链。回归测试覆盖 durable promotion、ambiguous pending、语义篡改、
   workspace collision、NaN/Inf、timeout/invalid 与 duplicate token。
4. 本轮 GPU=0、API=0、没有读 frozen cohort、label vault 或科学 outcome。synthetic utility 只用于工程分支覆盖，
   其均值不得进入论文结果或方法收益叙事。当前 production worker 仍未实现真实 aira-dojo backend 与 pristine
   evaluator adapter，因此真实 E1/E2 仍未启动，原预算审批门不变。
5. 第一次远端启动在创建 worktree/实验目录之前因 `env_setup.sh` 与 Bash nounset 不兼容而失败；修复为先 source
   再启用 nounset 后重跑。该失败已与成功证据一并归档，没有被从记录中删除。

直接证据：
- `phase1/results/balanced_worker_e0_20260814_f7b75a5/README.md`；
- `phase1/results/balanced_worker_e0_20260814_f7b75a5/verification_summary.json`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_E0Worker_裁决.md`。

## 0L. 2026-08-14 最新覆盖：版本化 corpus 契约与 equal-K E0 已独立复核

本节晚于 0K。稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与
first-960 前瞻确认；没有切回旧 HCE、多保真或 probe，也没有把工程通过写成方法正结果。

1. 学长确认的 LFS 契约已实现为 append-only batch registry + release-specific prefix lock +
   release-specific serialization protocol + 输出 rows/bytes/SHA 三元门。v6–v11 已在远端从 fork
   LFS materialize，并与保留的原始 merged files 逐字节 `cmp` 全部通过；最终实现 commit 为
   `73fd5f6a927e8deeb07d84372e1ba87fb7d2b3c5`。
2. v4/v5 继续标记不可恢复：历史 8,607/9,323 行与现存 prefix 8,579/9,433 行不符，首次 LFS
   发布前同名 batch 已被替换，且没有原 merged 备份。不得制造假 release 或声称任意旧版均已复现。
3. 直接用最新 transformer 重放 v9 虽仍为 14,323 行，却改变 744,500 bytes；因此后续版本发布
   必须同时冻结 batch、顺序、变换协议和输出 hash，不能只看行数。
4. equal-K outcome-blind E0 已在精确 commit `4ff44dd` 通过 34 项测试、13/13 preflight、producer、
   不 import producer 的独立 verifier 与确定性 replay：4 anchors、3 siblings、K=2、H=2、24 jobs，
   assignment manifest SHA=`122628cc49f92a22aeb9acbdacee3ea18828b10edabc665d655c8aa930e5a726`。
   这是 0-GPU/0-API 工程证据，不是方法收益；真实 E1/E2 仍受已记录预算门约束，尚未启动。
5. LFS pull 错 remote、当前协议漂移、临时目录缺失、v11 taxonomy 漏项和 v10 helper 漏 `cd` 等失败
   均已保留日志；只有修复后通过 exact hash/`cmp` 的结果进入裁决。

直接证据：

- `phase1/实验记录/2026-08-14/CorpusLFS_版本化逐字节重建_裁决.md`
- `phase1/results/corpus_release_contract_20260814_73fd5f6/summary.json`
- `phase1/results/balanced_manifest_e0_20260814_4ff44dd/README.md`

## 0K. 2026-08-14 最新覆盖：equal-K continuation 正方法转为 outcome-blind 工程实现

本节晚于 0J；稳定主线不变，balanced continuation 是 gated 方法扩展，真实 GPU/API 长跑尚未启动。

1. 最新原始论文查重确认：rollout-tree return/Q 聚合（RTMC）、adaptive branch rollout（PaTR/TRACE）、
   off-policy tree-search correction、OCBA-MCTS 与 fixed-budget BAI 均已有直接先例。不能把 equal sampling、
   future return 或 budget allocation 单独写成 novelty。
2. 可防守组合收缩为：真实 MLE program-search 节点 + physical-run provenance + historical behavior-policy label
   对 matched equal-K interventional label + fresh workspace/pristine evaluator + 不微调底座的轻量 continuation
   critic + 相同真实执行预算下的 D_val utility。
3. `V_H^π` 明确定义为已执行节点在固定 continuation policy/horizon 下的 future best utility 期望；这是
   post-execution expansion decision，不与“尚未执行 sibling 先跑谁”的 pre-execution benchmark 混称。
4. 直接 FIFO/BFS 被否决：它不保证 sibling 获得 equal compute；当前 Python interpreter 只重启 process、不清空
   working directory，候选可留下 cache/model/temp 文件，必须每个 rollout 独立 fresh workspace。
5. outcome-blind assignment producer 与不 import producer 的 verifier 已实现；blocked schedule 保证每个 sibling
   exactly K、每个 replicate block 含全部 siblings、inclusion probability=1、order probability=1/B，并在 JSON
   parse 前拒绝 credential shape。当前 synthetic tests 通过，尚未证明真实方法有效。
6. 真实矩阵已先给预算：E1 为 8 jobs/16 candidate executions/预计 3.24 GPU·时；E2 为 72/216/43.76；
   E3 候选为 384/768/155.58。按硬门，先完成 worker/workspace/evaluator smoke；没有新批准不启动 E1/E2 长跑，
   E3 更不预授权。
7. 0809 LFS object 已从全新集群 clone 端到端 pull：commit `8b38d9a`、1,940 行、56,424,624 bytes、SHA
   `133500c0fd731201bde35f44598ada17430684ed2b762326ae006101722a3094`，不依赖 big-data-storage。

直接证据：
- `phase1/实验记录/2026-08-14/BalancedContinuation_可识别正方法与查重.md`；
- `phase1/实验记录/2026-08-14/BalancedContinuation_真实实验预算门.md`；
- `phase1/balanced_continuation_manifest.py`；
- `phase1/verify_balanced_continuation_manifest.py`；
- `phase1/results/corpus_lfs_audit_20260814/fresh_pull_receipt.json`。

## 0J. 2026-08-14 最新覆盖：历史 policy 自然实验失效；LFS 发布真源纠偏

本节晚于 0I；稳定主线仍是 run-clean、decision-local 数据集/benchmark 与 first-960 前瞻确认，未切回
HCE、多保真或 probe。

1. 0802–0804 MCTS 对 0805 “sequential/no-selection” 的历史自然实验正式判
   **`HISTORICAL_POLICY_AUDIT_INVALID_NO_CAUSAL_CLAIM`**。冻结实现通过 28 项测试和全部 13 项预检后，
   因一个非 root 节点 `parents=[]` fail closed；另有 archive 超过预注册 member byte cap。正式结果未产生，
   grade/outcome 未读。
2. 两臂在正式结果前已知底座、timeout、children、总时限和 commit 不同；提交历史也没有可追溯的
   sequential selection 实现。因此旧 fragment 两任务“0.73 对 0.56”撤回为 confounded exploratory，
   不进论文主张。下一可识别实验必须是显式 matched fixed-sibling/equal-K continuation 新采集。
3. 学长确认的语料发布真源是 Git LFS 中每批只上传一次的不可变 card batch，由对应版本 manifest/
   `rebuild_corpus.sh` 重建；合并语料不得继续作为反复上传的真源。审计发现该设计直到 commit `da27852`
   才实际落地：v4/v5 提交本身没有对应 LFS objects，现存分批按旧顺序分别得到 8,579/9,433 行，与历史
   记录 8,607/9,323 不同。因此不得宣称当前 Git 可逐字节复原 legacy v4/v5。
4. 当前 manifest 引用的 `cards_senior_0809.jsonl` 在远端是 1,940 行、1,940 个唯一 ID、0 credential shape，
   SHA-256=`133500c0fd731201bde35f44598ada17430684ed2b762326ae006101722a3094`，但此前未被 Git 跟踪。
   本轮只补这个 immutable batch 的 LFS pointer/object，不新增合并 corpus object；legacy 缺口明确保留。

直接证据：
- `phase1/实验记录/2026-08-14/SearchPolicyEndogeneity_历史协议审计_裁决.md`；
- `phase1/results/search_policy_contract_audit_invalid_20260814/diagnostic_summary.json`；
- `phase1/实验记录/2026-08-14/CorpusLFS_发布契约审计.md`；
- `phase1/results/corpus_lfs_audit_20260814/summary.json`。

## 0I. 2026-08-14 最新覆盖：prospective 收样、累积与原子评分完整盲链通过影子回放

本节晚于 0H；主线没有变成旧多保真/HCE/probe，仍是 run-clean、decision-local 数据集/benchmark 与
first-960 前瞻确认。

1. v11 的 16,012 个历史 endpoints 已生成 `(card_id, exact-code SHA-256)` denylist；唯一 code SHA 为
   15,912 个，producer SHA 为
   `2f0cc4f3dc203801c569237716ba82cbc2bde2f854b67eee6efa9452e92447e6`。不 import producer 的 verifier
   从 hash-locked cards 逐行重建完全一致；正式远端 23 项测试通过。
2. denylist SHA/行数现为 intake 与 scorer 的源码常量，公开 CLI 不能自报覆盖；旧 667-run denylist 继续保留。
   新 manifest 还必须满足 `run_id == journal:<source_sha256>`，endpoint ID 与 exact code 两层 overlap 均为 0。
3. 最终 0812 全量影子回放在 commit `ca86739ed992d11a11d652dcbcb2e85394308532` 通过：远端测试
   28/28 通过；60 roots 中 57 个
   checkpoint runs、3 个 live-only、1,304 endpoints、286 structural pairs、9 tasks。它们全部早于激活，
   eligible=0；env/live-event 未读、raw journal 未落盘、源 archive 前后 SHA 一致、两层历史 overlap=0。
   intake summary SHA 为
   `9e3e9b3df34e07d792baf77401c2cf9292b0aaacdabd59c64feb22b4b1e0bdc6`。
4. `prospective_accumulator_v1` 已实现并在同一真实 schema 上复放：它从 hash-locked registry 逐批重验 archive、
   source/run/endpoint identity、历史端点与 exact-code denylist、结构 pair 重建，并拒绝跨批重复 source/run/endpoint。
   当前状态为 `PROSPECTIVE_COHORT_COLLECTING`，summary SHA 为
   `f2cbefa765b90c8c432a1ecb2467ce235ce7051cfaa0e7cbb22c3cc4c776d13c`；`label_vault_opened=false`，
   outcome/prediction 打开列表均为空。
5. first-240/first-960 在生产关闭前只能是 provisional。只有独立于 outcome 的生产关闭凭据明确
   `all_scheduled_runs_uploaded=true` 且 `outcomes_read=false`，并绑定当时 registry SHA，才可冻结身份；这避免晚上传的
   更早 run 改写所谓 first-960。关闭时不足 960 就诚实记为不完整，不能后补或按效果停止。
6. 该回放只证明工程链适配真实 tar schema，不是 prospective 正结果，未计算任何 scorer-vs-grade metric，
   label vault 未复制或打开。目前 senior 目录最新仍为 0812；metadata-only monitor 继续运行。
7. 语料版本发布固定为：Git LFS 只存不可变分批文件，每个上传一次；在有 LFS 的环境 pull 后由统一 manifest
   驱动 `rebuild_corpus.sh`，再核对行数与 SHA。不得把每版合并语料重复上传，也不得绕开 manifest 手拼版本。
8. 固定 scorer 原子编排与跨批 score registry 已在 commit
   `4b12c8f80abee4fafcacf8bc8268f9344ead7b61` 完成。远端 33/33 相关测试通过，其中包含真实冻结 bundle 对
   synthetic 非空 prospective manifest 的端到端推理；随后 0812 最终 shadow 得到
   `NO_ELIGIBLE_ENDPOINTS` 与 `PROSPECTIVE_SCORE_REGISTRY_VERIFIED`。单批事务和 registry 的 `strace` 中
   `label_vault.jsonl` 文件系统调用都为 0。score transaction summary SHA 为
   `237313bc7a9a015b0dcfcbda1c70546d4572024b3a04cd2d9a3f1fe407f5ff5f`，registry validation summary SHA 为
   `4a74e0fb6ad85a39581d4d62e4cad4ca3ca7ec5772b565eab7ebf84558049722`。
9. 第一次远端工程预检因 `critic` venv 没有 pytest 而在 intake 前 fail-closed；无正式 artifact。重跑改用同时含
   pytest/sklearn 的 `exp` venv，失败日志与成功日志均保留。至此新 drop 到达后的固定评分链没有人工补步骤；
   没有新 drop 时仍不读标签、不在同一 OOF 上启动新一轮追参/GPU 方法实验。

直接依据：

- `phase1/results/fixed_decision_scorer_v11_20260814/precutoff_endpoint_independent_verify.json`；
- `phase1/results/prospective_intake_shadow_0812_v4_20260814/README.md`；
- `phase1/results/prospective_accumulator_shadow_0812_v1_20260814/README.md`；
- `phase1/results/prospective_score_pipeline_shadow_0812_v1_20260814/README.md`；
- `phase1/实验记录/2026-08-14/ProspectiveIntake_预注册.md`；
- `phase1/实验记录/2026-08-14/ProspectiveAccumulator_预注册.md`；
- `phase1/实验记录/2026-08-14/ProspectiveScoringRegistry_预注册.md`。

## 0H. 2026-08-14 最新覆盖：TGCA 经独立复核关闭，盲测继续封存

本节晚于 0G；稳定主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与前瞻复核。

1. `tgca_v11_train_oof_discovery_v1` 已完成 13 项预检、5-fold producer 和不导入 producer 的完整重拟合
   verifier；正式状态为 **`VERIFIED_TGCA_DISCOVERY_NO_UNLOCK`**，最大 refit score 差为 0，所有完整性门通过，
   `frozen_read=false`、`temporal_vault_read=false`。
2. TGCA 相对 sibling-only 的微平均 utility/top-1 仅为
   `+0.010310682590593189/+0.004426737494466578`；run/task clustered 区间均跨 0，支持任务中 utility
   非负仅 `11/20=0.55`。相对 uniform cross-run 的 utility 为 `-0.00639610796665303`。三个预注册效果门
   全部失败，0812 vault 不解封。
3. 操纵检查明确成功：114 个 fold×task 图中，TGCA 把平均 components 从 `80.45614035087719` 降至
   `5.780701754385965`，最大分量占比升至 `0.934134980605146`，正代数连通度图为 `101/114`；因此不能把
   NO_UNLOCK 归因于“没有把图连起来”。关闭本实现，不在同一 OOF 改 ratio/选边/任务/门。
4. 学长的规模实验文档已定位到 `myfork/dojo-reproduce` commit `5f071ec`：旧 1,303-pair validation 上
   1.5B--8B 没有单调规模收益，Qwen3 base final 均值约 55%，1:1 混入 value pairs 下降。它是独立旧口径，
   不替代本项目 run-clean OOF。该分支更新 commit `2cb6f0c` 仍把
   `metric_for_best_model=eval_pair_accuracy` 与 `greater_is_better=false` 并置；修复前的新 checkpoint
   不能按“best accuracy”解释。
5. 接下来资源只回到固定 scorer 的 first-960 prospective cohort、新 source-journal provenance 与 benchmark
   发布物。gap/parent-normalized loss 已被 learning-to-rank/NAS top-centered 文献覆盖；若补做只能在新验证
   证据上作为强 baseline，不作为 novelty，也不在当前 OOF 追参。

直接依据：

- `phase1/实验记录/2026-08-14/TGCA_裁决.md`；
- `phase1/results/tgca_v11_20260814/independent_verify.json`；
- `phase1/results/tgca_v11_20260814/summary.json`。

## 0G. 2026-08-14 最新覆盖：短 run 改变 pair 产率，盲态扩为固定 first-960

本节晚于 0F；没有读取 activation 后 outcome 或论文 frozen pairs，稳定主线不变。

1. 学长 0812 drop 已先安全提取并脱敏：10 个唯一 archive（另 1 个 leaf 文件被 SHA 与包内根目录共同证明为
   tabular 错包重复）、60 个 env 的 512 个字段脱敏、原始 credential 残留 0；57 journals 产出 805 cards、
   9 tasks，所有 grade/y_norm finite，和 v11 的 ID/exact-code overlap 均为 0。
2. 旧 `step <= previous_step` run heuristic 在 0812 得到直接反例：两个 ranzcr journal 的有标签 steps 分别为
   1–2 与 6–7，被静默合并为同一 segment。source-journal truth 是 57 runs，heuristic 只有 56；无 source split，
   所以该例是保守合并而非泄漏证据。新 batch 改为 flatten 前显式 run ID，旧 heuristic 不再是 source truth。
3. 0812 已在不打印、不用于 metric 的条件下封成 `temporal_blind_0812_v1`：805 endpoints、57 runs、9 tasks，
   但只有 103 个 structural sibling pairs、7 个 pair-support tasks。它明确是 pre-activation analyst-blind holdout，
   不是 prospective cohort；TGCA 配方与 prediction 冻结前不得解封 label vault。
4. 103/57=1.8070175438596492 pairs/run，说明短 run 机制下 first-240 约只有 433.6842105263158 pairs，原
   1,500-pair 支持门大概率不足。outcome 前 append-only 附录因此保留 first-240 为必报 pilot、禁止中途看
   outcome，并固定 first-960 为确认 cohort；门槛、scorer、estimand 和任务约束均不变，960 前停产则记不完整。
5. v11 source-journal provenance backfill 已完成：在可追溯的 14,339/16,012 cards（89.5515863102673%）中，
   覆盖 587 个旧 heuristic runs、592 个唯一 source journals；发现 5 个 heuristic run 各自合并了两个真实
   journals，但 **0 个 source journal 被拆成多个 heuristic runs**，card-source collision 也为 0。因此当前证据
   没有发现这种边界错误造成跨 split 泄漏；它造成的是保守合并、run 数少计与 cluster 过粗。另有 1 个旧
   journal 命中 credential 形状并在 JSON 解析前跳过；1,673 张未追溯 cards 仍明确记为未知，不能外推成全量证明。

直接依据：

- `phase1/实验记录/2026-08-14/ProspectiveDecisionConfirmation_功效修正附录_预注册.md`；
- `phase1/results/temporal_blind_0812_v1/seal.json`；
- `phase1/results/temporal_blind_0812_v1/source_truth_audit.json`；
- `phase1/results/v11_source_provenance_audit_20260814/summary.json`。

## 0F. 2026-08-14 最新覆盖：固定 scorer 已激活，前瞻 first-240 开始计时

本节晚于 0E；稳定论文主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark，旧 HCE、
多保真、TD/RL 与 probe 不恢复为主线。

1. `prospective_decision_v1` 已在 commit `41d638b1c8154415d523d8f22bbd10b7ae5b48be` 正式完成
   13 项预检、producer、独立重拟合 verifier 与原子激活。固定 scorer 是 v11 train-only 上的 `static_lr` 与
   `char_tfidf_lr`；独立 verifier 的所有数组与 5,499×2 reference scores 最大差均为 0。
2. 激活时刻固定为 `2026-08-13T22:19:17.348021Z`（北京时间 2026-08-14 06:19:17）；模型 bundle
   SHA-256 为 `c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23`。v11 的 667
   physical runs 在 denylist 中；只有 generation start 严格晚于激活时刻的 run 才可进入 first-240。
3. 学长最新 `mle/0812` 的 11 个 archive 已被发现，但其源文件时间均早于激活；它们只可作为下一版历史语料，
   不计入前瞻 cohort。导入前必须先隔离提取并脱敏，禁止直接读取原始 tar 内容。
4. first-240 固定排序、支持门、pair-graph interaction 与真实 top-1/utility 门均保持预注册，不按 outcome 停止，
   不改 scorer、不筛任务、不打开论文 frozen。通用“pair distribution/graph matters”已有明确文献先例；本文可守
   novelty 是真实 MLE sibling decision graph、physical-run provenance、estimand transport、搜索 utility 与前瞻复核。
5. 唯一允许继续预注册的正方法候选是 `Target-Graph Connected Augmentation`：只在 outer-train 内加入同 task、
   gap-matched、跨 physical-run 的桥接边，并以等边数 sibling 重权与 uniform-crossrun 为控制；必须在未见 run 的
   真实 sibling top-1/utility 上过门。若失败即关闭，不在同一 OOF 调阈值或换任务。

直接依据：

- `phase1/results/fixed_decision_scorer_v11_20260814/README.md`；
- `phase1/results/fixed_decision_scorer_v11_20260814/freeze_receipt.json`；
- `phase1/实验记录/2026-08-14/PairGraph_文献边界与正方法候选.md`。

## 0E. 2026-08-14 最新覆盖：pairing 统一膨胀未确认，保留 predictor×graph 排序反转

本节晚于 0D；稳定论文伞仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark。

1. `pairgraph_v11_train_oof_descriptive_v1` 在 3,921/4,263 common-support sibling rows、20 tasks 和
   196,949 个有限非平局跨 run pairs 上完成；producer 与独立 verifier 一致为
   `VERIFIED_PAIRGRAPH_EFFECT_NOT_SUPPORTED`，所有完整性门通过，`frozen_read=false`。
2. char-TFIDF 的 task-macro 为 sibling=`0.5284907717433142`、task/fold-matched uniform cross-run=
   `0.5814158858170438`、再匹配固定 gap bins=`0.5478674917657668`。total 点估计 +0.052925114073729684，
   但 task CI=[-0.04418436017058699,0.15460114273445769]；gap component +0.03354839405127704，CI
   也轻微跨零。四臂只有 2 臂点估计为正、0 臂 CI 下界为正，故关闭“全局 pairing 普遍抬高所有 critic”强主张。
3. 保留明确标注为 outcome 后描述的 rank reversal：sibling task-macro 上 static LR=0.5389068809808808
   高于 char-TFIDF=0.5284907717433142；uniform cross-run 上 char-TFIDF=0.5814158858170438，而 static LR=
   0.49652226450484627。pair graph 不只是统一难度旋钮，而与 predictor family 和 task 强交互。
4. 因此 benchmark 主张收紧为：不同 pair graph 的 headline accuracy 不是可直接横比的同一 estimand；发布物
   必须同时报告真实 sibling graph、task weighting、固定 gap transport、run-clean provenance 与 top-1/utility。
   同一 train OOF 上不改门、不筛正任务、不再做新阈值。确认性复现只用协议冻结后的新 physical runs 与事先
   冻结 scorer，论文 frozen 继续封存。

直接依据：

- `phase1/实验记录/2026-08-14/PairGraphIntervention_裁决.md`；
- `phase1/results/pairgraph_v11_20260814/independent_verify.json`。

## 0D. 2026-08-14 最新覆盖：异构低容量方法关闭，转 pair-graph benchmark intervention

本节晚于 0C；稳定论文伞不变，且不恢复旧多保真/HCE/probe 主线。

1. `heterogeneous_oof_v11_discovery_v1` 已在精确相同的 4,263 train-only pairs、333 physical runs、
   23 tasks 与 inherited five outer folds 上完成；不导入 producer 的 verifier 重新拟合全部模型后裁决
   `VERIFIED_DISCOVERY_NO_UNLOCK_NO_ENSEMBLE`，`frozen_read=false`。
2. char-TFIDF 是最强 arm：pair=`0.5219329110954727`、complete-parent top-1=`0.4674634794156706`、
   parent-equal gap utility=`0.5310468507329235`。pair 的 run/task macro 95% CI 均高于 0.5，说明代码文本
   有弱信号；但 20 个支持任务只有 11 个不低于随机，且相对 anchor 的 top-1/utility task-clustered CI
   均跨零，不能升级为稳健 decision critic。
3. char-TFIDF 与 anchor disagreement=`0.4468684025334272`，oracle-union top-1=`0.6715360779105799`；
   但 oracle 不可部署，而预注册 nested gate 因任务一致性和 utility task-CI 失败。禁止同一 OOF stacking、
   事后改权重或用 equal-rank secondary 替代 primary。
4. 当前 sparse patch、global frozen linear、task-conditioned/top-centered linear 与 static/char-TFIDF ensemble
   低容量方法线一并关闭；论文 frozen 继续封存。下一步转数据/benchmark 的 **pair-graph intervention**：
   固定同一 OOF endpoint 分数和 endpoint universe，只改变全局随机、gap-matched、真实 sibling 三种 pair
   graph，定量分解表观准确率中由 gap 分布与真实决策拓扑造成的膨胀。先只用 train OOF 做描述性审计，
   不把它冒充新 critic 或 prospective search utility。

直接依据：

- `phase1/实验记录/2026-08-14/HeterogeneousRunOOF_裁决.md`；
- `phase1/results/heterogeneous_oof_v11_20260814/independent_verify.json`。

## 0C. 2026-08-14 最新覆盖：task-conditioned/top-centered 关闭，转 exact-same-pool 异构审计

本节晚于 0B；稳定论文伞不变。

1. 预注册 `task_topcenter_v11_discovery_v1` 已完成 5-fold physical-run OOF，并由不导入 producer 的
   verifier 独立重建。裁决为 `VERIFIED_DISCOVERY_NO_UNLOCK`，`frozen_read=false`。
2. 主模型 pair=`0.5066854327938072`、complete-parent top-1=`0.45108455068614434`、
   parent-equal gap utility=`0.5125829562017966`。相对 fixed global head 的 top-1/utility 微平均增量只有
   `0.00398406374501992` / `0.002076308434788266`，run/task clustered CI 全部跨零；任务一致性也未过门。
3. 2×2 消融没有给 task residual 稳健支持；top-centered objective 只有小而不一致的变化。因此关闭当前
   task-conditioned linear 实现，不扩大正则网格、不按任务翻转、不读 frozen。
4. 下一步按 0B 已冻结的条件，只做 exact-same-pool、同一 outer physical-run folds 的 char-TFIDF/static
   train-only OOF 与 error-complementarity 审计。互补性标准须在结果前固定；只有通过才实现严格 nested
   ensemble，不能在同一 OOF 行上训练并报告 meta-head。

直接依据：

- `phase1/实验记录/2026-08-14/TaskTopCentered_RunOOF_裁决.md`；
- `phase1/results/task_topcenter_v11_20260814/independent_verify.json`。

## 0B. 2026-08-14 最新覆盖：global frozen head 关闭，转 task-conditioned parent objective

本节晚于 0A 并覆盖其中“Parent-Conditioned Patch / Action Critic 是当前首选方法候选”的下一步措辞；
稳定论文伞仍不变。

1. Sparse parent patch discovery 已正式 `NO_UNLOCK`：patch 相对 whole-code pair accuracy 为负，关闭固定
   line-diff 实现，不读 frozen。
2. 随后按学长“0.5B 多卡换长 context”的建议完成正式训练期 gate：Qwen2.5-0.5B、8,192 tokens、
   5,499 endpoints、4×RTX3090 frozen extraction、5-fold physical-run OOF、单一 global linear head。
   独立 verifier 裁决 `VERIFIED_DISCOVERY_NO_UNLOCK`：pair=0.5038705、complete-parent top-1=0.4471005、
   parent-equal gap utility=0.5105066；run/task CI 都包含 0.5；`frozen_read=false`。
3. 这只关闭 fixed `mean+last + global linear`，不关闭 embedding 资产。描述性 per-task accuracy 高度异质，
   下一候选是 outcome 后另立协议的 **task-conditioned parent-level top-centered/listwise head**；正则和混合只能在
   inner physical-run folds 选择，outer run OOF 裁决，不得按已见任务结果手工翻转或挑任务。
4. 若 same-pool OOF 证明 frozen/char-TFIDF/static predictor errors 互补，再做严格 nested ensemble；不允许在
   同一 OOF 行上训练并报告 meta-head。listwise/top-centered losses 与异构 predictor ensemble 在 NAS 已有先例，
   所以它们是正方法 baseline，不是单独 novelty。
5. 新协议通过前继续封存 `decision_frozen_v11_b*`。完整可共享结果（含 174 embedding chunks）在
   `phase1/results/frozen_embed_v11_20260814_f339eb9/`；Git LFS 归档 SHA-256 为
   `096a3581bfce48c83019f3440e88089d4b8a4dd0a768224493f892941a3d64f7`。

直接依据：

- `phase1/实验记录/2026-08-14/Frozen05B8192_RunOOF_裁决.md`；
- `phase1/results/frozen_embed_v11_20260814_f339eb9/independent_verify.json`。

## 0A. 2026-08-14 覆盖裁决：回到真实决策 benchmark，Probe Contract 降为支线

本节晚于下方所有 08-13 裁决并覆盖其中“当前唯一主实验/活跃方法主线”的措辞。

1. 稳定论文伞仍是 **run-clean、NAS-Bench-style 的 MLE-agent 搜索树数据集与真实 sibling
   决策 benchmark**。旧 HCE/TD/RL/多保真三臂不恢复。
2. Progressive Artifact Contract / Probe-First 与 early-fidelity 相邻；它只保留为 gated 支线，
   不能再冒充稳定主线。V2 job `10686` 只完成 16/16 generation，自动 replay 已在 outcome 前停掉；
   因而没有 A/B 质量或固定预算收益结论。
3. 当前首选方法候选改为 **Parent-Conditioned Patch / Action Critic**：不再独立判断完整 child code，
   而是在相同 parent 下判断候选 edit/action 的相对改进。即时 b0 先用 run-clean sibling 数据裁决；
   budget-conditioned future value 只能在相同 continuation policy 或显式 right-censoring 下扩展，
   禁止重新使用历史 MCTS 的 subtree maximum 当无偏标签。
4. 文献边界已收紧：SWE-bench 的 Guided Search Strategies 已有 learned action-value + one-step
   lookahead；BAVT 已有 residual relative progress + budget conditioning。因此“action-value critic”
   本身不构成 novelty。允许的差异只能落在 MLE patch/action 表示、run-clean/censor-aware 标签、
   不微调底座与真实 fixed-budget utility，以及本数据基准的系统测量。
5. 第一闸是零 GPU、outcome 前冻结的 sparse patch CPU discovery。只有 train-run OOF 同时通过效果、
   双聚类稳健性、任务一致性与完整性门，脚本才允许读取 b0 frozen 文件；否则关闭 sparse patch
   实现，不把工程 timeout 或旧 lookahead 负面偷换成方法结论。

直接依据：

- `phase1/实验记录/2026-08-14/ParentPatchCritic_文献边界与路线.md`；
- `phase1/实验记录/2026-08-14/ParentPatchCritic_CPU发现门_预注册.md`。

## 0. 8 月 13 日晚间覆盖裁决（优先级最高）

### 0.1 21:20 后的最新覆盖：关闭 identity SPT，保留 Probe-First 因果线

本小节晚于 0 节后续文字并覆盖其中“下一步”措辞：

1. Scoreable Prediction Tap 的冻结 job `10648` 已真实完成 18/18 executions（3×RTX3090，
   `00:45:53`）。主 verifier 与独立 raw verifier 一致为 **`INCONCLUSIVE`**：baseline evaluable=2/6，
   probe-by-120=2/6，语义等价=2/2，latency pairs=2，中位相对提前仅
   `0.04135151374612629`。不启动 v11 176-pair 扩展。
2. 机制诊断表明 identity wrapper 只能在候选已有 `.predict*` call 时截获，而这些 call 通常位于昂贵训练之后、
   submission 写盘之前；它不能主动创造早期 fidelity。因此 SPT 只保留为 measurement/baseline，不再是核心方法。
3. Probe-First original-vs-contract A/B job `10637` 的 12 个 generation entry 都 `rc=0`，但 manifest builder
   错把每个 run 必然不同的 `solver.exp_name/checkpoint_path` 当作科学配置漂移，parent `FAILED 1:0`，replay
   未启动。按冻结规则该批保持 **`INVALID`**，不能解释方法输赢或修后追认。
4. validator 已收窄为只忽略上述两个 run-identity 字段，并增加“真正改变 `step_limit` 仍必须失败”的回归门。
   活跃正方法仍是 **Probe-First/Progressive Artifact Contract**，但下一批必须全新任务、全新 seed、重新冻结；
   headline 是 coverage、full-quality safety、observability/ranking regret 与固定预算 best-final，而非 prompt
   compliance。
5. 文献审计已撤回“没有 3/5 close baseline”：ArchPilot 是 3/5 close baseline，后续必须实测
   ArchPilot-style low-fidelity rewrite、FOREAGENT/最强 critic、Probe-First 与 full execution。仍未发现 4/5
   direct scoop，但若没有端到端 search utility，仅靠 artifact contract 不足以构成顶会方法贡献。

最新直接证据新增：

- `phase1/实验记录/2026-08-13/SPT_标签盲机制pilot裁决.md`；
- `phase1/实验记录/2026-08-13/probe_contract_ab_safety_v1无效运行裁决.md`；
- `phase1/实验记录/2026-08-13/SPT_文献防scoop审计.md`。

本节发生在本文后续各节之后，**覆盖**后文“当前唯一主实验”和后续顺序中的旧措辞。论文伞形定位仍是
NAS-Bench-style 的 MLE-agent 搜索树 benchmark；当前方法主线已经进一步收敛为：
**Anytime MLE Search under Selectively Observable Execution Feedback**，首个主动干预是
schema/probe-first artifact contract。旧 HCE、TD/RL、多保真三臂和继续扩大静态 critic 均不是当前路线。

变化来自同日已经冻结的证据链，而不是按文件名回退：

1. late-artifact pilot 中 6 个预先冻结的 fresh-120-silent 候选到 600 秒仍为 0 个 stable artifact；
2. 冻结 100 sibling sets 的完美 120 秒 hindsight oracle 有 0.512644 的理论 headroom，但现有
   censor-aware race 的 optimistic avoidable tail 只有 0.026163；瓶颈不是继续调 observed selector，
   而是高价值候选在决策时刻不可评分；
3. schema/probe V1 对两个预先冻结任务一次生成、一次连续 replay，最终只有 1/2 probes 和
   1/2 full transitions 通过，按预注册规则正式为 **FAIL**；成功任务证明基础 contract 可实现，失败任务
   在任何 artifact 前触发通用 sklearn API 错误，因此不能宣称跨任务稳定可行；
4. KompeteAI 已覆盖 reduced-epoch logs 预测和 MLE pipeline 加速，delayed-feedback BAI、failure-aware
   BO 与 early termination 也已有先例；SandMLE 还使用了 valid-output milestone。因此 novelty 不能写成
   “首个 early metric/valid artifact/early stop”，而必须落在真实自由形态 MLE sibling、候选特异且不可变
   的 artifact contract、host/pristine provenance、选择性可观测 regret 分解及固定预算搜索因果收益；
5. 独立新任务/新 seed 的 V2 已按 outcome 前冻结规则正式 **PASS**：Spaceship 与 Tweet 均为
   `root→valid draft`，host 在 12.542975/11.046629 秒捕获 probe，且两者都在 600 秒内出现 full transition；
   主验证器与不导入主实现、重新调用 pristine grader 的独立验证器一致为 probes=2/2、full=2/2。
   这只证明 prompt-only contract 的工程可行性，不证明 coverage、排序、质量非劣或搜索收益。

V1 结果不得回填或同任务修补；V2 也不得在这两个任务上继续调 prompt。V2 的 PASS 现在只授权在
**全新任务、全新 seed**上设计小规模独立因果 A/B：标准 draft 与只增加 artifact contract 的 draft 使用
相同 conditional-debug、API/GPU/grader 和停止预算，先裁决 time-to-first-scoreable artifact、120 秒 coverage、
失败率与 full quality。两个 V2 draft 都首次执行成功、没有触发 debug，因此不得把 V2 写成 debug 有效性证据；
- 150-run 评分通道确认保持 `NOT SUBMITTED`，保留为 benchmark 机制确认资产，但不再阻塞上述低成本
  operator feasibility gate，也不得用旧数据替代前瞻确认。

最新直接证据：

- `phase1/实验记录/2026-08-13/schema_probe_smoke_v1裁决.md`；
- `phase1/实验记录/2026-08-13/schema_probe_repair_v2裁决.md`；
- `phase1/实验记录/2026-08-13/Anytime可观测性主张_20260813.md`；
- `phase1/实验记录/2026-08-13/late-artifact连续轨迹_pilot裁决.md`；
- `phase1/实验记录/2026-08-13/anytime_oracle_headroom_探索性上界.md`。

## 1. 审计截面

- 我方分析基线：`fork/phase1-value-critic@96b7b01a3563db10dec82d2aff1becfad2eab1db`
  （本轮 Qwen/K2 验收与 schema-first 预检开始前的干净截面）
- 学长分支：`fork/dojo-reproduce@2cb6f0c57790407cae84070d3eb475da3cbe9597`
- 最新发布语料：v11，16,012 cards / 667 physical runs / 25 tasks；15,991 finite，21 quarantine。
- 论文冻结决策集：b0/b1/b2 分别 1,498 / 323 / 265 对；v10 与 v11 逐字相同。
- 扩展评测集：b0/b1/b2 分别 136 / 39 / 30 对，必须与 headline 分开报告。

本裁决直接对应以下最新证据链，发生冲突时按日期和明确的撤回/预注册关系解释，而不是按文件名猜：

- `phase1/实验记录/2026-08-12/剂量响应曲线_首版.md`；
- `phase1/实验记录/2026-08-13/评分通道严格配对_审计.md`；
- `phase1/实验记录/2026-08-13/评分通道前瞻复现_预算与预注册草案.md`；
- `phase1/实验记录/2026-08-13/v10冻结决策集与训练增量验收.md`；
- `phase1/实验记录/2026-08-13/学长0811入库_v11验收.md`；
- `phase1/实验记录/2026-08-13/artifact_first_cascade_探索性预注册.md`；
- `phase1/实验记录/2026-08-13/artifact_first_cascade_探索性裁决.md`；
- `phase1/实验记录/2026-08-13/parent_certified_improvement_回顾性预注册.md`；
- `phase1/实验记录/2026-08-13/parent_certified_improvement_探索性裁决.md`；
- `phase1/实验记录/2026-08-13/120秒评分可观测性_机制预注册.md`；
- `phase1/实验记录/2026-08-13/120秒评分可观测性_探索性裁决.md`；
- `phase1/实验记录/2026-08-13/选择性可观测反馈_正面突破路线.md`；
- `phase1/实验记录/2026-08-13/anytime_oracle_headroom_探索性上界.md`；
- `phase1/实验记录/2026-08-13/FOREAGENT官方pair图_外部审计预注册.md`；
- `phase1/实验记录/2026-08-13/FOREAGENT官方pair图_外部审计裁决.md`；
- `phase1/实验记录/2026-08-13/FOREAGENT官方alignment全量审计_预注册.md`；
- `phase1/实验记录/2026-08-13/late-artifact连续轨迹_pilot裁决.md`；
- `phase1/实验记录/2026-08-13/连续fidelity轨迹_watcher_smoke冻结说明.md`；
- `phase1/实验记录/2026-08-13/学长checkpoint方向与QwenK2语料验收.md`；
- 学长分支 `src/mle_critic/docs/outcomes/0812/DECISION_MODEL_SIZE_EXPERIMENTS.md`。

## 2. 最近两周的路线更替

### 7 月 30 日—8 月 2 日：跨生成器/版本与 lookahead（已被后续审计降格）

早期报告把跨生成器、静默版本升级和 lookahead 作为主角。8 月 3 日以后证明：

- “静默版本升级导致塌陷”被同版本独立批次对照推翻，真实混杂是 batch/run；
- 旧 in-task 0.776 含 endpoint 与树碎片泄漏，最终 run-clean L1 为 0.6493；
- 44% orphan cards 使所谓 tree split 实为 fragment split；99.7% in-task test pairs 与训练共享物理 run；
- K≥1 的 RM 优势在 run-clean 决策集不复现；预算条件化 flip 效应也关闭。

因此这些结果只能作为方法学历史、数据 provenance 与 benchmark 挑战背景，不能恢复为当前方法主线。

### 8 月 8—10 日：NAS-style 数据基准（当前论文伞形定位，仍有效）

稳定定位是“MLE-agent 搜索树的 NAS-Bench + 系统性 predictor study”：

- 运行级干净切分、query/init 成本分账、覆盖率列、噪声上界和泄漏修复是核心资产；
- 在真实 sibling 决策点，静态特征、TF-IDF、1.5B RM、LLM judge/PBE 协议均接近随机；
- 学长 Qwen2.5/Qwen3 1.5B—8B 的旧 decision 验证约 0.52—0.56，未见规模单调收益；
- 但学长的旧日志使用 1,303-pair validation，不等同于当前冻结 1,498/323/265 三档，不能直接作为最终表。

该定位是论文容器，不等于必须写成纯负结果；当前最有希望的正机制见下一节。

### 8 月 12—13 日：真实决策的执行悬崖与评分通道（当前活跃科学主线）

冻结 100 sibling sets / 230 candidates / 52 physical runs 的冷启动 replay 显示：

- 30 秒 stdout 接近随机；120 秒 stdout 仍明显弱于完整执行；
- 120 秒能产 `submission.csv` 的候选，其 pristine 外部分是有用的早期信号；
- 最严格的同 parent、同候选、同 120 秒共同覆盖比较：external sub top-1=0.9167，
  stdout top-1=0.7083，配对差 +0.2083；run-CI [+0.0769,+0.3810]，task-CI
  [+0.0690,+0.4667]；24 sets / 15 runs / 9 tasks；
- 但只有 5 个 run 有非零方向，全部为正，双侧 exact sign p=0.0625。

允许的当前主张是：**pristine 外部评分通道是最强的正向前瞻机制候选**。不能写成已经确认，
不能从共同覆盖子集外推到全部候选，也不能说已经带来实用加速。

在同一冻结发现集上，coverage-complete 的 `artifact_score_then_stdout` 探索性 cascade 相对
`stdout_only` 提高 +0.0700，但未达到预注册 +0.08、run-CI 下界严格大于 0 和 sign p<0.05
三道门，裁决为 **BORDERLINE**。机制分解揭示了更重要的约束：

- 在同样观察到 artifact 的条件下，使用其 pristine 分数相对只看 artifact 是否存在提高
  +0.1447；run-CI [+0.0717,+0.2241]，task-CI [+0.0541,+0.2510]；
- 但“及时产生 artifact”本身相对 stdout 降低 -0.0747；run-CI
  [-0.1385,-0.0182]，task-CI [-0.1604,-0.0059]；
- 因而 artifact 可观测性是选择性缺失（MNAR）的候选机制：分数值有用，单纯把“能及时产物”
  当质量信号会造成偏差。该分解已由不导入主脚本的独立实现复核，但仍属于同一发现集。

## 3. 当前唯一主实验

### 3.1 前瞻通道复现

预注册 commit 为 `a18c285`，机制发现 commit 为 `4c964f8`（2026-08-13 05:31 +08:00）。

- 只接纳机制 commit 之后产生、且未进入旧 100 sets 的新 physical runs；
- 至少 150 runs，dominant task ≤25%；每 run 固定最多 2 个合格 parent；
- 主比较固定为同一 120 秒、共同候选上的 `sub_score - stdout_val` tie-aware top-1；
- 预计约 690 replay，17—23 GPU·h，4×1 GPU 时墙钟约 4.3—5.8 小时；
- 无 optional stopping，不按任务、hard/easy 或 parser 子集替换 headline。

截至本文件写入时，服务器最新 0811 archives 的时间均早于机制 commit；v11 虽在 05:48 入库，
但“晚入库”不等于“前瞻生成”。**严格合格确认 run 数为 0，实验 NOT SUBMITTED。**

### 3.2 立即可做的支持实验（不重训）

复用学长 0812 的最佳 Qwen3-4B/8B checkpoint，对 v11 三份冻结文件逐 pair 打分：

- headline：`decision_frozen_v11_b0.jsonl`；
- secondary：b1、b2；
- extension 只单列；
- 保存逐 pair 预测、checkpoint、commit、seed、命令，按 task/run 聚类；
- 目的仅是检验旧约 0.55 是否受容量/context 限制，不挑 best checkpoint 冒充 test 泛化。

现有 checkpoint 在学长环境，当前仓库只有日志和 outcome 文档；先交付严格 evaluator，不能伪称已完成。

### 3.3 已完成的短验证：选择性评分通道

在不改动上述唯一确认性主实验的前提下，只允许一次冻结、无调参的回顾性规则验证：默认使用
`stdout_only`；仅当 parent 有部署时允许访问的历史 pristine 搜索分数，且 120 秒 artifact 严格优于
parent 时，才用该改善证书覆盖 stdout。parent 缺失或无改善时回退 stdout。该实验用于检验
“以 incumbent 为锚点能否缓解 MNAR”，不得把旧 `graded` 当作线上 test 标签，也不得在同一
100-set 发现集上继续搜索阈值或策略网格。

该冻结规则已一次性执行并由不导入主脚本的独立实现复核：证书支持仅 24 sets / 14 runs / 7 tasks；
parent-certified top-1=0.5683，stdout-only=0.5383，差 +0.0300；run-CI
[-0.0235,+0.0833]，task-CI [-0.0114,+0.0735]，run sign p=0.6875。相对 naive cascade
为 -0.0400；尽管 run/task bootstrap CI 均低于 0，只有 4 个 informative runs，run sign p=0.125，
不能宣称独立确认更差。该规则未过 +0.08、双聚类 CI 与 run sign 门，裁决为
**BORDERLINE**。因此此候选关闭，不进入前瞻确认，也不得在旧 100 sets 上改 margin、阈值或回退规则。

### 3.4 已完成的机制可行性审计（不是 selector）

只用执行前代码与任务身份预测“120 秒时是否有 finite pristine 外部分”，不把最终质量、stdout、
artifact 分数或 parent 比较用作特征。主模型使用 physical-run 分组的五折 OOF，task/run 双聚类
推断，另做五个 split-seed 敏感性与 whole-task leave-one-out。它只回答可观测性 propensity 是否
可建模；即使达到 GO-FEASIBLE，也不能声称搜索收益，只允许在新的 discovery/validation split
开发显式删失模型。旧 100-set selector 规则仍保持关闭。

冻结审计已一次性完成并由独立实现复核，裁决为 **BORDERLINE**：主模型 AUC=0.8629，run/task
CI=[0.7602,0.9483]/[0.6951,0.9606]，5 个 split seeds 的 median/min AUC=0.8572/0.8444；
但 task-only AUC=0.8642，主模型相对 task-only 的 Brier gain 仅 +0.0072，run/task CI 均跨 0。
whole-task LOTO AUC=0.6676，task-bootstrap CI=[0.4554,0.8388]。因此可观测性在现有任务内高度稳定，
但没有证据证明代码模型优于任务先验或能可靠迁移到新任务。该结果不授权直接开发通用 propensity
selector；若继续，只能在新 split 上做 task-conditional 模型，对未见任务 abstain，并独立认证。

### 3.5 已完成的连续轨迹 watcher smoke（基础设施，不是科学实验）

冻结 validator 已一次性给出 **PASS**：job `10591` 在 1×RTX3090 上完成 2 cards × 30/60/120 秒，
共 6 条 records、1 个 stable artifact、0 个 racy copies、1 个 finite pristine grade。存活进程 checkpoint
的最大定时偏差为 0.000156 秒，最大 capture lag 为 0.000506 秒；另一个候选在 83.510392 秒自然退出，
按协议在 120 秒档记录真实退出时刻。worker/validator/job 均 rc=0，原子事务、hash/size、grader 隔离、
process-group 清理与无残留进程门全部通过。两个 card 的 coverage/score 不得作为论文结果；该 PASS
只授权把 watcher 用作机制冻结后新语料的被动仪器，扩大采集仍需冻结新 run/task 分区与总预算。

失败历史保留：job `10590` 因把登录节点本地 `/tmp` 工作树误当作 compute-shared 路径，在候选启动前
1 秒失败；另一次登录节点 compute-only NVIDIA 文件检查在提交前停止。二者均无科学结果、未进入样本。

### 3.6 已完成的一次性方法可行性诊断：Selective Feedback Racing

在仍不修改旧 100 sets 规则网格的前提下，允许最后一次无阈值、无训练的机制诊断：120 秒时只淘汰
“已有 finite pristine 分数且被另一 observed candidate 严格支配”的候选；所有 silent/unscored 候选
一律 abstain/继续。最终目标是保留 full-run winner，因此将保守 abstention 相对 `observed_only` 的贡献，
以及 observed 分数排序相对“同样保留所有 missing、仅在 observed 内随机”的结构匹配基线分开报告。

输入 SHA、100 sets / 230 cards 总体、run/task-macro bootstrap、资源 accounting 和裁决门均在 outcome
前冻结；不 import 主脚本的 verifier 已逐 set 复核。裁决为 **BORDERLINE**：winner survival=0.9800，
run/task-macro CI=[0.9712,1.0000]/[0.9561,1.0000]；相对严格 structured random +0.1413，双 CI
均在 0 以上，run sign p=0.000519，确认 observed score value 有稳定价值。策略淘汰 44/230=19.13%
cards，却只覆盖 3.36% 历史 full runtime；optimistic avoidable tail=2.62%，restart ratio=1.0250。
相对 observed-only 仅 +0.0900、5 informative runs、双侧 p=0.0625。故统一 120 秒 censor-aware race
没有实用成本杠杆，关闭旧 100 sets 上全部后续调参。

### 3.7 已完成的 late-artifact 路线裁决 pilot（不是论文效果实验）

只回答昂贵 fresh-120-silent 候选在同一进程继续到 600 秒时，是否会转为 finite pristine score。冻结
选择规则从 115 个“fresh 120 秒无分数且历史 full runtime≥600 秒”的候选中按固定 SHA 顺序贪心选择
6 cards / 6 tasks / 6 physical runs；不读取 final grade、stdout、代码内容或成绩。每 card 单次 continuous
执行，checkpoints=30/60/120/240/360/480/600；1×3090，候选执行上限 1.00 GPU·h，0 API。

manifest SHA=`f535116e51dc7a03a65aa6df4b4621812367eea201f16aeb8d83d21bc398bbe1`，已经从锁定 raw
inputs 独立重建并逐字节一致。validator 在 GPU outcome 前冻结，区分真正新 artifact hash 与早期 artifact
仅在后续 grader recovery；≥2 个不同任务 late conversion 才保留 `TaskHazard`，0 个才转向
`schema-first operator`，1 个或 grader-recovery ambiguity 为 `INCONCLUSIVE`。完整性门失败则 INVALID。

job `10592` 已在 1×RTX3090 上完成，42 records、原 validator、fresh-directory 重验证和不 import 主
validator 的 raw verifier 均一致：stable artifacts=0、finite grades=0、late conversions=0、grader
recoveries=0，裁决为 **SCHEMA-FIRST-CANDIDATE**。其中只有 2/6 候选实际存活到 600 秒并被预算终止，
另外 4/6 在约 5.0/7.8/36.0/91.8 秒自然以 `rc=1` 退出；故允许关闭“统一晚等”作为近期方法投资，
但不允许宣称总体 late-conversion rate 为 0。`TaskHazard` 路线按冻结门关闭，转向候选特异的
schema/probe-first artifact contract。

### 3.8 已完成的 hindsight oracle headroom（探索性上界，不是 speedup）

冻结 v9 的 100 sets / 230 cards 上，120 秒 observed/missing 分别为 86/144；历史完整 runtime median
分别为 86.2466/1323.1667 秒，68/100 sets 的全部 final winner 在 120 秒仍 missing。当前 censor-aware
race 的 optimistic avoidable tail 仅 0.026163；偷看最终 `graded` 的不可实现 perfect-score-at-120 oracle
为 0.512644。两份实现从锁定 raw input 独立重算一致。

该结果只证明改善早期 score coverage 有理论成本空间，并把方法优先级从“继续调 120 秒 selector”转向
“让昂贵候选更早产生候选特异的 pristine-scoreable artifact”。禁止声称已节省 51.26% GPU，禁止据此
在旧 100 sets 上选时间阈值或策略。当前科学问题可概括为 **Anytime MLE Search under Selectively
Observable Execution Feedback**。late-artifact pilot 已把实现路线裁决到 schema/probe-first；oracle 仍只是
不可实现上界，不是效果基线或已实现的加速。

### 3.9 已完成的 FOREAGENT 官方 pair 图外部审计（CPU 描述，不是模型对决）

官方 Hugging Face 自动转换 parquet 已锁为 8,456,690 bytes、SHA256=`79363b7e...0b5f`，只含
18,361 行 pair paths/scores/ranking，不含官方逐 pair judge prediction。审计固定报告 unique solutions、
组合复用、pair-graph coverage、同 trajectory 比例、预注册 gap 桶，以及和我方真实 sibling b0 在全部/
common tasks 的 pair-weighted 与 task-macro 描述。

首次结构预检在 outcome 写盘前发现我方 b0 有 1,499 行，其中恰有 1 行 `gap_raw=NaN`；这与既有
1,498 finite headline 计数一致。冻结处理是明确记录并排除该行后再算 gap，负 gap 仍 fail-closed；
此次失败没有产生 audit JSON/CSV，也没有读取任何分布 aggregate。

独立复核通过，裁决为 **PAIRING-MISMATCH VERIFIED**：官方 `gap<1e-2` share=0.096400，我方=0.501335；
限制到 14 个同名 common tasks 后为 0.121988 vs 0.496975，task-macro 为 0.218633 vs 0.439512，
12/14 tasks 方向一致。官方 895 solutions 的每任务 pair graph coverage median=0.995918，每 solution
组合复用 median=49 次，仅 0.158651 pairs 同 trajectory。该结果直接确认“全局穷举 pair”和 agent
真实 sibling decision 是不同评测分布，但 parquet 不含官方 predictions，不能单独声称 gap 导致 61.5%。

同时修正 8 月 12 日 PBE 文档：旧 `qwen-max + description-derived unverified report + 非 COT + code
截断` 只能保留为该配置的历史结果；“报告未执行验证无关紧要”已撤回，不得再称直接裁决 FOREAGENT。
官方 executed reports 覆盖旧 300-pair 样本中的 211 pairs / 14 tasks；官方还公开 DeepSeek/GPT 三次逐
pair alignments，优先冻结并直接重算原模型的 gap 曲线，无需先花 API 重跑 Qwen。

### 3.10 FOREAGENT 官方 alignment v1 结构中止与 v2 结果

已锁定官方 26 tasks × 2 models × 3 releases 共 156 文件的固定 manifest；compact primitive-field
JSONL 共 110,620 records，SHA256=`480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe`。
v1 在写任何 accuracy/gap summary 前按完整网格门中止：DeepSeek 三次运行在 26/26 tasks 内 pair grid
完全一致；GPT run 1 在 6 tasks 合计少 8 pairs，而 run 2/3 完整。另确认 26 个 DeepSeek run-1 文件的
`log_index` 全 null，但 pair key/ordinal 唯一；Google QUEST 有 49 个含 NaN score 的 pairs，在六个文件
中对称存在。v1 结果目录为空，不允许补述任何性能结论。

v2 已在读取真实性能汇总前另立预注册：DeepSeek 完整三轮网格继续作 primary；GPT 仅在每 task 三轮
固定交集上作 replication，逐 task 报 union/intersection/排除数且比例必须 `>=0.99`；不计算跨模型
paired accuracy difference。非法 prediction 对 finite non-tie 按错误计入，禁止 complete-case 删除；
ties/nonfinite 对称隔离。raw-gap、task-internal quartile/decile、task bootstrap 与原 primary 裁决门不变。
主实现与不 import 主实现的 verifier 一致通过，但冻结裁决为 **INSUFFICIENT-SUPPORT**，不得事后改门：
DeepSeek overall task-macro=0.606698，最低任务内 gap 四分位=0.533655，最高减最低=+0.116730，
task-paired CI=[0.039283,0.196048]；GPT 对应为 0.580067、0.530522、+0.089750，差值
CI=[0.015195,0.163951]。效应门本身满足，但只有 22/26 tasks 的最低/最高四分位各至少 20 pairs，低于
冻结的 24-task 支持门；DeepSeek prediction index 在 55,167 个有限非平局 records 上覆盖 100%，但
confidence 仅覆盖 89.3614%，冻结的 joint-coverage 门也失败。该结果只能作为强描述性、双模型一致的
正向线索，不能升级为预注册确认；同一数据上禁止另开 v3 删门“修成显著”。

同时纠正 parquet 与 alignment 的版本边界：按 task 与发布物四位 solution id 对齐后，两者共同 18,270
pairs，alignment-only=168、parquet-only=91，而不是同一网格简单少 77 行；共同网格的 score 也来自不同
重评分版本，18,221 个双方均可定 winner 的 pairs 中有 5,068 个 winner 不同。因此 3.9 的结果只描述
锁定 parquet 的 pairing distribution，不能当作本节 alignment predictions 的精确 label/gap 网格。

### 3.11 Qwen/K2 exploratory 扩展与学长 checkpoint 配置审计

未进入 v11 的 Q01–Q08、K2a/K2b 共 40 个 manifest runs 已通过物理完整性与标签可用性双门：36 个
物理完整，4 个失败/取消；36 个完整 run 中 7 个没有任何 finite 外部分，最终只有 29 runs / 91 cards /
7 tasks 进入隔离的 exploratory extension。v11 保持不动；内部合并版为 16,103 cards / 696 runs，v11
是逐字节前缀，扩展与 v11 ID 交集为 0。独立 verifier 和第二次全量确定性重建均 PASS。

沿用原冻结 hold 与 v11 split universe 后，新语料只新增 1 个 b0 training pair，b1/b2 与 extension 均
新增 0；三份 frozen 文件和 v11 逐字节一致，冻结节点进入训练为 0。因此这批数据不授权 RM 重训或
“监督量显著增长”的结论；它揭示 run/card 数不能替代 clean sibling decision 支持数。

学长最新分支把 `metric_for_best_model` 从 `eval_loss` 改成 `eval_pair_accuracy`，但保留
`greater_is_better=False` 与 `save_strategy=best`。Transformers 4.49.0 官方实现会用 `np.less`，即把
更低的 accuracy 当成更优并保存。最新配置启动的 run 必须先修复再解释；0812 outcome 使用较早的
`eval_loss + greater_is_better=false`，不能事后把旧约 0.55 结果也归因于该新 bug。

这批 Qwen/K2 数据均早于评分通道机制冻结，角色只能是 exploratory/train，不能进入 3.1 的前瞻确认。

## 4. 已关闭或仅历史的方向

- **旧 HCE 三臂**：50/25/25 + 标签子采样 proxy，不符合当前 80/10/10、time-fidelity、
  full-locked 契约；6 月结果仅作历史，不继续补跑。
- **coverage-aware escalation**：120 秒后 restart/full=0.9850，resume/full=0.9312；实用成本失败。
- **critic top-2 silent routing**：有 Pareto 点，但相对 random 无显著增益，不能归因于 critic。
- **early-trace ranker**：预注册 KILL，0.6100 vs random expected 0.6433。
- **conformal risk-certificate stop**：0 次有效接受，restart/full=0.9850，预注册 KILL。
- **K≥1 potential/lookahead 作为现行 critic 的正面方法**：run-clean 不复现；8B 只能作一次防守性复核。
- **TD/RL 控制器**：不是当前主线。现有历史 journal 未通过 Prompt 0.5 的严格资格门；
  不启动 6—15 GPU·h 控制器实验。未随本次路线提交归档的探索性计数不作为论文证据。
- **把 v10/v11 当确认集**：禁止；它们源数据早于机制冻结。

## 5. 正面突破的分层路径

1. **近期最稳**：前瞻确认评分通道机制；这是数据论文可引用的正结果。
2. **近期方法化候选**：parent-certified 与执行前可观测性预测均以 **BORDERLINE** 关闭。新数据上
   若继续，必须显式记录 time-to-artifact 的删失过程和条件分数；现有结果只支持 task-conditional
   propensity，并要求对未见任务 abstain。连续 watcher smoke 已 PASS；首个低容量候选固定为
   `TaskHazard × ScoreValue`：任务级生存曲线决定等待时间，artifact 出现后才使用 pristine 分数。
   Selective Feedback Racing 进一步以 **BORDERLINE** 证明 observed score 排序稳定、但安全淘汰的只是
   便宜候选。下一裁决问题变为 silent 候选在 120 秒之后是否会转为可评分；有明显 conversion 才继续
   `TaskHazard`，否则升级 `schema-first operator`。采用独立 validation/certification；不能把“是否及时
   产物”直接当质量，也不能在旧 100 sets 上继续搜索 selector、margin 或阈值。
3. **当前已过工程门、待因果检验的 operator 候选**：让 agent 在固定早期预算内先产候选特异、
   schema-valid、可由 pristine grader 评分的 cheap probe，再在同一进程继续 full。V2 在两个新任务上
   已正式 PASS，但没有 original-prompt 对照。下一步只允许全新任务/seed 的标准 prompt vs contract prompt
   小规模 A/B；先要求 120 秒 coverage 提升、失败率不升和 full quality 无方向性损害，再冻结多候选固定预算
   搜索实验。它改变 operator/prompt，不能冒充只改评估旋钮。
4. **系统候选**：checkpoint/resume + 异步 successive halving，目标是把 continuation/full 从
   0.9312 实际压低；先做执行器可恢复性 smoke，再谈搜索收益。
5. **长期基准贡献**：持续增加独立 run 和任务平衡，发布 run-aware、gap/noise-aware、
   cost-aware 的 predictor benchmark 与完整撤回记录。

## 6. 每次继续工作前的顺序

1. 先看本文件和同日最新实验记录；
2. 检查是否有更新的 dated report/commit 明确 supersede 本文件；
3. 只读核对代码、输入 SHA、冻结集和资格门；
4. 短 CPU 审计可直接做；长 GPU/API 实验先给矩阵、总 run/replay 与 GPU·h；
5. 新结果无论正负都写入 dated report，并在这里更新活跃/关闭状态。
