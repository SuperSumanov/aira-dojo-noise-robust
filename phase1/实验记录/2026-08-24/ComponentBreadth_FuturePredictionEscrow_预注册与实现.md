# Component-breadth future prediction escrow：预注册与实现

日期：2026-08-24

状态：`FROZEN_PRETRUTH_SCIENTIFIC_COMMIT / RELEASE_BOUND_WAITING_COHORT / FUTURE_EFFECT_UNKNOWN`

## 1. 结论先行

旧 component-clean dev 在等 pair 预算下给出 broad−concentrated accuracy
`+0.0332204391514186`，三 seed 与全部 LOTO 同向，但 95% task-bootstrap CI
`[-0.010859355050261277, 0.07987928182598769]` 跨 0，正式状态仍是
`RETROSPECTIVE_DEV_COMPONENT_BREADTH_NO_UNLOCK`。本轮没有把这个线索改写成正结果，也没有在同一 dev 池追加 seed、
换 endpoint 或筛 task。

本轮完成的是 revised raw-grade breadth hypothesis 的一次 prospective test 所需的**结果前预测托管**：在任何 future label/outcome 打开前，冻结旧训练选择、9 个
cheap critic、未来 target-300 identity cohort（含 boundary overshoot）、输出 schema、parent population、truth precision、支持门和效应门。真实 future
cohort 仍是 33/300 runs、11 tasks，故没有运行 9-model formal fit，更没有 future accuracy、log-loss 或正/负结论。

为消除调用者同时选择 cohort path 与 SHA 的自由度，identity cohort formal runner 在第一次达到 closed 状态时会以
`O_EXCL` 发布固定路径 `FIRST_CLOSED_COHORT_ANCHOR.json`；后续 prediction/truth runner 只能读取这个首个闭合锚，
不再接受候选 cohort path/hash 参数。target 是 300，完整 boundary archive 造成的 overshoot 保留，不截断为恰好 300。

这是一条 supporting positive hypothesis，不取代 Decision Corpus + Predictor Benchmark 论文容器，也不把 300-run
identity cohort 误称为已经获批的 mechanism-effect 主实验。该 cohort 当前只授权结果盲身份闭合、dual-truth 支持审计和
结果前预测托管；任何 replay/effect 实验仍须资格门、功效/成本设计与用户 GPU 预算批准。

## 2. 为什么这是 revised hypothesis 的 prospective test，而不是同池 rescue

旧结果已知，所以新合同如实把它写入 `known_before_freeze`。合法的新证据只允许来自结果前已经按 archive 时间顺序冻结的
target-300 future identity cohort（含 boundary overshoot）；预测必须先于 truth，且后续只 join score-channel 协议已经用固定 SHA lottery 选出的
`selected_parents.jsonl`，禁止看结果后重选 parent、pair、task 或 truth precision。

旧 dev 的 `y_norm` 标签存在严重离散化 alias（147 parents / 16 tasks，且该审计在 raw endpoint 选择前已知）；同时
official five-decimal raw grade 在同一旧 parent support 上几乎全部 non-tied。因此这不是原 endpoint 的独立确认，
而是如实预注册的 revised raw-grade hypothesis。新合同把：

- official-five-decimal raw-grade sibling ranking 定为**新的高分辨率 primary**；
- 原 `y_norm` 定为纯描述性的 normalized sensitivity，不允许形成第二个 confirmatory/replication 主张；
- log-loss 定为 calibration diagnostic；
- random arm 定为 descriptive sanity baseline。

四者互不 rescue。若 raw primary 通过，只能主张预声明 broad-support curation policy 在该 raw-grade temporal cohort 上
优于 concentrated policy；不能写成 normalized replication。若只有 normalized secondary 通过，只能报告 exploratory
normalized signal，不能形成 confirmatory 正主张。这个 endpoint 选择在 future truth 前完成，且明确承认它不是旧 endpoint
的无缝延续。

## 3. 冻结矩阵与 curation-policy 对比

合同 SHA-256：
`c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b`。

训练输入逐字节沿用旧正式实验：

- Cards：SHA-256 `5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`，
  604,190,866 bytes；
- component-clean train：SHA-256
  `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e`，3,208,089 bytes；
- source selection contract：SHA-256
  `1dc28d105922741d0c6a8263d9b2ebd2566d1a28de3dec1eb8f490116f7e6316`。

矩阵固定为 `broad/concentrated/random × seeds 20260823/24/25`。每个 arm×seed 都是 2,353 train pairs，且每 task
预算逐字节相同；broad=127 components，concentrated=53。三 seed 的 broad−concentrated physical-run contrast 固定为
205/206/205。9 份 unordered-pair selection SHA 均已在真实源、0 次 model fit 的 structure-only preflight 中重建，并写进
机器合同，因此后续无法静默换 pair。

固定模型仍是 char-wb TF-IDF 3--5 gram（train-only fit、30,000 features、`min_df=3`、sublinear TF）加 mirrored
Bradley--Terry LR（`C=0.5`、LBFGS、1,500 iterations cap）。future endpoint utility 使用 `X @ coef`，明确排除 intercept；
pair margin 必须严格反对称。

这不是单一因果旋钮。broad 与 concentrated 除 component/run 覆盖外，还会共同改变 endpoint support、comparison graph、
代码分布、pair difficulty 与 endpoint 重用结构。因此 estimand 只能是两个**预声明 curation policy** 的 controlled contrast；
正结果最多解释为“consistent with avoiding over-concentration”，禁止归因于 component count 或 run breadth 单独作用。

## 4. Future population、估计量与支持门

prediction population 是 target-300 closed identity cohort（完整纳入 boundary archive，允许 overshoot）各 hash-bound
`eligible_blind_manifest` 中全部 nonempty-parent endpoints 所诱导的 unordered pairs。producer
只读取各 intake 的 `eligible_blind_manifest.jsonl` 和 `eligible_structural_pairs.jsonl`；CLI 根本不接受 label-vault path。
它同时验证 cohort/archives/runs/intake summary、code SHA、run/task/journal/generation、complete sibling clique、训练 ID/code
零交集和 credential-free bytes；还逐 run 对齐 pre-outcome endpoint ledger、逐 intake 对齐 eligible endpoint/pair 总数，并从
**全部 blind endpoints** 重建 expected clique 后与 pair 文件精确相等。这个合同证明相对于 hash-bound pre-outcome intake
manifest 的完整性，不声称在不重开 raw archive/journal 的情况下重新证明原始 archive 绝对无漏端点。

truth 打开后，primary 仍只使用 frozen score-channel parent lottery 的 exact selected parents。统计顺序固定为：pair credit
先在 parent 内平均，parent 再在 task 内平均，三 selection seed 再平均，最后做 task-macro broad−concentrated；报告
20,000 次 task bootstrap 与全部 leave-one-task-out。

在计算 primary effect 前，以下四门必须全部通过：

- raw non-tied selected parents ≥200；
- 至少 150 个 physical runs 实际拥有 raw non-tied contributing parent（tie-only run 不计）；
- 有 raw non-tied selected parent 的 tasks ≥50；
- dominant task selected-parent share ≤0.20。

tasks≥50 只是最低 analyzability/breadth floor，**不是功效门或功效保证**。旧 accuracy task-effect SD
`0.11959407586040109` 下，若 `+0.03322` 真效应持续，约 102 independent tasks 才对应普通双侧检验约 80% 的
normal-approximation power；若最小相关效应只有 `+0.02`，同一近似约需 280 tasks，且“三 seed 全正 + 全 LOTO 全正”
会进一步降低 conjunction power。每个只有一个 contributing parent 的 task 仍按预注册 task-macro 等权进入，但必须逐 task
报告 contributing-parent 数。若支持门失败，状态只能是 insufficient support，禁止计算或形容 primary effect。

primary positive 还要求同时满足：point ≥`+0.02`、三 seed contrast 均>0、task-bootstrap 95% CI low>0、全部 LOTO>0。

## 5. 交付链

新增 producer：

- `phase1/critic_component_breadth_future_escrow.py`。

它生成：

- `endpoint_scores.csv`：future identity/code hash 与 9 组 endpoint score；
- `pair_predictions.jsonl`：固定 structural pair identity、9 组 margin 与 selected endpoint；
- `training_selection_receipts.jsonl`：9 组真实训练选择与 fit receipt；
- `summary.json` 与 `artifact_manifest.json`。

新增独立 verifier：

- `phase1/verify_critic_component_breadth_future_escrow.py`。

verifier 不 import 新 producer；它复用此前独立的 component-breadth selection verifier 和独立 cohort/truth-support 的
identity-only loader，自行重建训练选择、future blind support、9 次 source refit、endpoint scores、pair margins、全部 receipt
与完整 summary。最大允许数值差为 `1e-12`。

另外在任何 future truth 前新增机器化 post-truth evaluator 协议与实现：它先逐文件认证 prediction escrow，再第一次打开
label vault，独立重建 exact selected-parent lottery；raw-truth tied pair 排除、zero prediction margin 给 0.5 credit，
所有 k-sibling unordered pairs 先在 parent 内平均，再做 task/seed 宏平均。bootstrap 的 SHA-256 抽样索引、type-7
分位数、LOTO 和 support-fail 时“不写 effect/task rows”均在代码中固定；不 import evaluator 的独立 verifier 已实现，
会从 prediction、cohort、intake vault 与 selected-parent SHA lottery 独立重建并逐字段复算。prediction/evaluation artifact
使用 no-follow descriptor 稳定读取、末尾二次一致性检查和 source-path binding，防止 symlink、替换窗口或同 SHA 异路径输入。

新增三阶段、只允许人工触发的 runner：

- `phase1/scripts/run_critic_component_breadth_future_escrow_20260824.sh`：先封存 prediction；
- `phase1/scripts/run_score_channel_future_dual_truth_20260823.sh`：只有 prediction formal 完整验真后才可打开 truth；
- `phase1/scripts/run_critic_component_breadth_future_evaluation_20260824.sh`：只有 prediction 与 dual-truth 两个不可变 bundle
  的 root/SHA 都已存在并在后续 release commit 中绑定后才可执行。

prediction/truth runner 均为零参数，并且当前用全零 control commit 明确 fail-closed；它们只能在 scientific commit 之后
由 release-only follow-up 绑定该 exact commit。cohort 身份只来自固定 one-time `FIRST_CLOSED_COHORT_ANCHOR.json`，调用者
不能传 path/SHA。evaluation runner 还要等前两个 bundle 真实产生后，再由另一 release-only commit 绑定完整 bundle SHA；
因此不能跳过 prediction、预先读 truth 或在多个合法输出中挑一个。所有科学 Python 子进程都用 `env -i` allowlist，
不继承已为 Git proxy 加载的 provider credential。三阶段均执行 12 项 preflight、focused/full tests、双生产/双独立核验、
逐字节 reproducibility、file/network trace 与 credential scan。prediction 阶段预算是单线程 CPU、36 次总 fit、预计
45--90 分钟；GPU/API/base-LLM update=`0/0/0`。runner 不接入 watchdog，不含 `sbatch/srun`，当前 collecting cohort
不能触发 formal fit。

## 6. 已完成验证

### 6.1 合成与攻击测试

Linux overlay 的联合 focused：`61 passed, 2 warnings in 7.30s`。覆盖：

- exact contract 与 outcome-free scope；
- independent verifier 不 import producer；
- target-300 synthetic closed cohort（含 overshoot）的 blind reconstruction；
- `Path.open` guard 证明 label vault 不打开；
- collecting cohort 在 training open 前拒绝；
- code SHA、parent、credential 攻击拒绝；
- producer/refit-verifier 数值一致；
- artifact numeric tamper 拒绝；
- evaluator 与其不 import 实现的 verifier 逐字段一致，source path/byte-identical alternate path 攻击拒绝；
- first-closure anchor 的一次性发布与非核心 metadata tamper 拒绝；
- 三阶段 runner 的固定锚、prediction-before-truth、12 项 preflight、无 GPU submission、无 vault CLI。

在与 formal runner 相同的 repo cwd、`env -i`、单线程环境下，全量 `phase1/tests`：
`935 passed, 35 warnings in 61.49s`。一次诊断命令从远端 home 而非 repo cwd 调用绝对 test path，导致 5 个旧测试因相对
fixture path 不存在而红；该无效调用在 15% 后停止，没有进入模型拟合或标签读取。改为正式 runner 的真实 cwd 后从头
935/935 通过。另一次未设置 BLAS 线程上限的诊断运行出现多核占用，已停止并用上述 exact allowlisted 环境重跑；不把
这些 harness invocation 错误计为科学失败或成功。

scientific commit 已固定为 `e1093d8007449954c4561611c2ff381c55f7abe8`。从 GitHub 重新 fetch 后建立 fresh
no-smudge exact-commit worktree 的第二次验收为 focused `61 passed, 2 warnings in 6.41s`、完整 phase1
`935 passed, 35 warnings in 67.04s`；worktree 前后 clean，GPU/API/model fit/future truth=`0/0/0/false`。不可变回执位于
`/research/d7/spc/yzyang4/postpush-future-breadth/e1093d8-pretruth-v1/`，其 `SHA256SUMS` 自身 SHA-256 为
`6011cbad9072cad8861aca95304906173b494db189118cba50050f6a026b9f30`。

随后 release-only commit `d416c741dcfa8178699bd2027ab4bcc7154ef5f7` 只把 prediction 与 dual-truth runner 的
control commit 绑定回上述 scientific commit；evaluation runner 继续保持全零 inert。fresh no-smudge Linux 对 release
绑定的验收为 `26 passed in 0.36s`，回执位于
`/research/d7/spc/yzyang4/postpush-future-breadth/d416c74-release-v1/`，其 `SHA256SUMS` 自身 SHA-256 为
`8f2d18365239ef859232e12e51e5296d42c9fac006c3a832bcfcea3004ba83aa`。

### 6.2 真实训练源 structure-only preflight

对真实 Cards/train 做 12 项 preflight，得到：31,742 Cards、4,095 needed endpoints、676 run groups；train=
4,689 pairs / 28 tasks / 127 components / 430 runs。9 个 arm receipt 全部与合同一致，status=
`REAL_SOURCE_STRUCTURE_ONLY_PASS_NO_MODEL_FIT`；future truth/model fit/GPU/API=`false/0/0/0`。

### 6.3 当前 collecting cohort 负控

当前 cohort summary SHA-256=
`780126c257ceae38a830c9d8215fbf7a7ce6776987ba683a967d774d13488600`，status=
`FUTURE_COHORT_COLLECTING`，33/300 runs、11 tasks、11 accepted archives。把不存在的 training paths 传给 formal producer，
仍先以 rc=2 拒绝 collecting 状态；strace 中 training/vault/score forbidden open count=0，证明 gate 顺序不是文档承诺而是
实际 fail-before-training 行为。

连续 monitor 在 `2026-08-23T17:40Z` 将 metadata archive 总数从 204 更新为 212，但截至 `17:55Z` 仍为
`ready=0, transactions=68, outcomes_read=false`。这 8 个新观察项尚未满足 6 小时稳定门，尚未 intake，也未改变上述
33/300 formal cohort；本文不把 metadata observation 写成已入库数据。

## 7. Novelty 边界

这不是“数据多样性有益”的方法首创。preference recovery 已有 graph connectivity/margin 条件，固定预算 trajectory
diversity 已有直接 scaling 工作，NAS performance predictor 也已有 diverse/representative sampling。对应直接边界包括：

- Pukdee et al., *What Does Preference Learning Recover?*：https://arxiv.org/abs/2602.10286；
- *TDScaling*：https://arxiv.org/abs/2602.03219；
- DARE NAS predictor sampling：https://openreview.net/forum?id=QjWQxmKGlL。

所以即使 future primary 为正，也只作 MLE-agent 搜索树 D&B 的 temporal data-curation evidence：在真实 physical-sibling、
run-clean、结果前预测托管和 official-grade measurement contract 下，监督支持广度是否可 transfer。它不构成新采样算法、
scaling law 或 search acceleration。

## 8. 下一步

scientific commit/push、fresh exact-commit 复验与 prediction/dual-truth release binding 均已完成；evaluation runner
保持 inert，直到前两个 formal bundle 实际存在。之后继续 outcome-blind intake。只有 identity
cohort 达到 closed target-300（含 boundary overshoot）后，才先人工生成 predictions escrow，再运行 dual truth；随后再以
新 release commit 固定两个 bundle 的 root/SHA 并运行 evaluator。任何一门结果都不能替另一门 rescue。当前不启动 GPU、
不消费 API，也不提交额外同池实验。
