# 给学长：Decision Corpus 20 天冲刺与当前唯一关键阻塞（2026-09-02）

## 一句话结论

我们已把项目收敛为 **Decision Corpus + Predictor Benchmark + Audit Protocol**。未来 20 天不再扩散做小型事后审计；
最值得共同完成的正结果是：在下一批带 outcome-before config provenance 的新语料上，用未触碰 cohort 严格确认
0.6B→8B critic scaling，并同时把数据集/审计论文写完。

## 当前结构状态

- 学长 source=`296` archives；prospective first-960 provisional=`559` physical runs；Target-522 结构目标已达到。
- first-960 还差 `401` runs。按你之前说的理想 60 runs/day，条件点估计是 `6.683333` 天；上传节奏和 eligible
  rate 会使它变化。
- 最新 outcome-blind snapshot=`bf7674a4...ce0d6`，结构计数为 14,383 endpoints / 3,447 pairs / 45 tasks；
  closure 仍未提供，canonical config-v2 sidecar 仍为 0。
- first-960、Target-300、Target-522 的 label/outcome/prediction values/accuracy/utility 仍未读取。
- 你当前 `dojo-reproduce` head 仍为 `5baccb170ce287f9c8eed7b23ccf693a0268515a`；outcome 目录相对该 head 没有新增。

## 最近闭环的正资产

### 1. Archive-granular structural gate 是 support-preserving 的数据工程结论

在结算的 283-archive 状态中，14 个 structural reject events 触及 7 个 competitions：6 个仍保留 accepted eligible
support，合计 20 archives / 94 physical runs / 92 eligible runs / 2,558 endpoints；每个至少 4 eligible runs 和 50
endpoints。唯一没有 accepted support 的 competition 对应 zero-checkpoint archive（2 个 roots 均为 live-only）。因此当前
观察到“结构门删掉最后可用 checkpoint support”的 competition 数为 0。

边界：这是已有 aggregate evidence 的 post-hoc certificate，不是新的独立实验、predictor effect 或 universal no-loss
定理。formal 与 fresh-public-checkout 都已通过；公开包在
`phase1/results/structural_gate_utility_certificate_20260902_a0e04d2/`。

### 2. 论文资产已从旧方向切换到当前主线

- 20 天执行路线：`phase1/TWENTY_DAY_POSITIVE_RESULT_SPRINT_20260902.md`
- 当前论文蓝图：`phase1/PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md`
- 当前数据卡草稿：`phase1/DATACARD_DECISION_CORPUS_DRAFT_20260902.md`
- claim ledger：Evidence Index v10，20 项 distinct entries；support-floor reconstruction 与 gate certificate 均不重复计数。
- 旧 `paper.tex` 已标为历史 “Decodable but Not Usable” 稿，不再延续。

### 3. v11 内容扫描保守隔离后，94.766425% cards 仍可进入后续审查

v11 的 16,012 cards 已用冻结阈值对 23/25 prepared tasks 做全量 code-literal/comment + stdout 高熵逐字扫描：
3,766,518 candidate patterns 中 173 个命中，影响 419 cards；两个尚无 prepared source 的任务另含 419 cards。
在看到 task/card 分布前冻结的 whole-card rule 将两类都同时 withholding code+stdout，其余只标为
`CONTENT_REVIEW_ELIGIBLE`。正式 tier 为 15,174 review-eligible / 838 structure-only（94.766425% / 5.233575%）。

scan 与 tier 分别通过 exact-commit、producer A/B、独立 verifier A/B、2,029/2,063 full tests、file/network/security gate
和独立 postflight 重建。这个结果说明保守隔离不会把大部分结构资产一起丢掉，是正面的 release-engineering 资产；但
review-eligible 不等于 clean/cleared，仍需补两个 source、私下审查 173 matches、credential/PII/path 与法律门。

Target-522 的 Stage-A/rank 兼容链也已收口，但预注册支持要求不足，正式为 `LIMITED_SUPPORT`，既非正也非负；我们不做
事后阈值/分区 rescue，也不让它占用 20 天冲刺主力。

## 当前最关键阻塞：真实 producer sidecar 仍为 0

source 中 canonical `*.config_v2.jsonl` 仍为 `0`。这意味着接下来即使继续产生几百个 runs，只要没有 outcome-before
producer/config fingerprint，仍不能把它们用于 exact-stratum clean scaling；旧 archive 也不能事后回填。

已经交付、并在你当前 head 上 clean-apply 验证的补丁：

- path：`phase1/upstream_patches/0001-Add-prospective-config-v2-producer-hook-18-tests.patch`
- SHA-256：`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`

补丁默认关闭，只在显式启用时于真实 `dojo.main_run` 启动路径写 `producer.config_v2.jsonl`；不写 env dump、credential、
label 或 outcome。

## 麻烦你下一批 producer 做的最小动作

1. review/apply 上述 patch；
2. 显式设置 `DOJO_CONFIG_V2_SIDECAR=1`；
3. 给同一 generator/build 设置稳定且可公开的 `DOJO_GENERATOR_RELEASE`；
4. 把 `producer.config_v2.jsonl` 与对应 archive 一起作为 immutable sibling 上传；
5. config/generator 变化时换新的 public release ID，不复用旧 ID；
6. 不回填历史 archive，也不要把 first-960/Target-522 冻结评测行用于训练或周期 checkpoint 选择。

首个真实 sidecar 出现后，我们只先做 metadata/redaction/schema review；通过后才判断它能否进入 exact-stratum support。

## 拟确认的 clean scaling（尚未授权开跑）

候选矩阵：独立 critic `Qwen3 Base 0.6B/4B/8B × seeds 6/7`，共 6 个 training runs。context、steps、optimizer、
prompt、train/dev/frozen split、checkpoint rule、scorer 与资源 stratum 只允许模型规模变化。checkpoint 只看 train-run dev，
最终 frozen cohort 一次性评估。

我们会在 sidecar/support/closure 通过后另报：每臂 GPU 型号/卡数、实测 wall-clock hard cap、总 GPU·h、磁盘和
checkpoint/resume 方案，再由用户批准。当前没有启动 GPU 或训练。

预先固定的最低正门是两个 seed 的 `8B−0.6B` 都为正，并同时报告 task/run clustered interval、task-macro、LOTO、
dominant-task deletion、coverage/tie/missingness 和 init/query/execution 成本。若不过，不加 seed、不换 split、不删任务救结果。

## 论文定位与贡献归属

- 不能再申“首个 MLE trajectory dataset”“首个 tree/sibling reward model”或“首次 critic-guided code search”；
  ML-Agent、OpenMLE、mle-traj、AgentRM、ReLoc、SELA 等已覆盖相邻主张。
- 可守位置是：真实 MLE search 的 provenance-bound sibling-fragment benchmark，联合 physical-run/config/time split、
  outcome-blind closure、label/noise/cost/missingness/pair-weight audit 与同池 predictor study。
- 原始前瞻语料生产和 0820 探索性 scaling 信号归学长；run-clean/temporal corpus、sibling estimand、benchmark/audit、
  independent verification 与论文测量主张归我们这边；clean confirmation 联合完成。

## 同步推进

我们继续守候 Target-522/first-960、维护 prediction escrow/closure，并写 Table 1--3、Figure 1--2、数据卡、撤回表与
methods/audit sections。没有新 sidecar 前不再用缺 provenance 的新 runs 冒充 scaling confirmation。
