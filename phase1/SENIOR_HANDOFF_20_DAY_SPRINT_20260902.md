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

### 4. 五个历史批次的 generator model ID 已精确恢复；不要把它误写成 provider clearance

我们从 `cards_senior_0805seq/0808/0809/0810/0811` 对应原始 archive 的 exact `dojo_config` 恢复了 6,111/6,111 行
configured model ID，0 ambiguous、0 missing。与既有 inventory 合成后，v11 的 model ID 覆盖为 16,012/16,012（100%），
exact version-or-configured-model 为 15,905/16,012（99.331751%）；107 行 DeepSeek 静默版本边界仍保留。

两层正式链分别通过 2,047 与 2,068 个 full tests、A/B、独立 verifier 与独立 postflight。重要边界是：五批的 service
provider、base URL family、账号区域和 contract entity 仍未知，provider-family coverage 仍只有 9,901/16,012
（61.834874%）。所以麻烦你若能提供原始、无密钥的调用端/provider/账号区域/合同元数据就补这一轴；不用再凭记忆提供
model ID，也不要从模型名猜 provider。该结果改善可复现元数据，但不是 release clearance 或新的 predictor 科学证据。

另外，两个缺 prepared text 的 image tasks 已尝试固定 staging，但远端 Kaggle API credential 对应账号仍报告未接受规则，
因此在任何下载前 fail-closed。若方便，请确认接受规则的网页账号与远端 API credential 是同一个账号：

- `https://www.kaggle.com/competitions/aptos2019-blindness-detection/rules`
- `https://www.kaggle.com/competitions/histopathologic-cancer-detection/rules`

### 5. Predictor 主表与一个可守的方法贡献已经成稿

历史 Table 4A 现在只绑定一个可审计入口：931-row exact-common-support development graph，覆盖 28 tasks / 550
decision parents，incidence rank=787、cycle rows=144。旧 400-pair judge report 因 run bootstrap 只绑定 better endpoint，
实际 303/400 pairs 跨两个 endpoint runs、涉及 39 runs 而报告写 35，已排除出主表。Table 4A 的 static/TF-IDF 排名没有
显著突破；我们不会把 null shift 包装成模型增益。

正面的论文方法资产是 graph-basis sensitivity：对 parent-local comparison graph 用标准
`pi_e=b_e^T L^+ b_e` / uniform-spanning-tree inclusion weight，把 component 总权重固定到 incidence rank，并与
realized-row estimand 同表报告。它有精确 expected-basis 解释，且明确不是独立性修复、ESS、因果校正或新图论定理。
fresh exact checkout 已通过 18 focused + 2,082 full tests，0 failures。英文主稿 v0.4 已把 Tables 1--4A 合并到单一
reviewer packet；Table 4B 和 scaling Table 5 仍封存。

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

新运行的机器契约已经冻结：

- contract：`phase1/critic_scaling_confirmation_contract_v2.json`
- SHA-256：`c64ab02a20066a9d282de8b3d5a803838e3637e33dd39b53600b52b1dd277642`
- implementation commit：`977e06aae6812c4fb30555184ccd9fcebadb33fb`
- exact-checkout verification：31 focused + 2,074 full tests passed，0 failed（48 warnings）

旧 v1 的 0.6B/1.7B/4B/8B × 2 seeds 八-run 矩阵只留作历史兼容，不要再按它提交新训练。v2 会在任何结果计算前
要求 lock 中有 100% canonical sidecar coverage、sidecar manifest SHA、稳定 public generator release、exact config
stratum、outcome-before attestation 和 `historical_backfill_used=false`；主分析器和独立 verifier 都会 fail-closed。

我们会在 sidecar/support/closure 通过后另报：每臂 GPU 型号/卡数、实测 wall-clock hard cap、总 GPU·h、磁盘和
checkpoint/resume 方案，再由用户批准。当前没有启动 GPU 或训练。

预先固定的最低正门是三点均值单调、平均 `8B−0.6B≥0.02`、两个 seed 各自为正、task-bootstrap CI 下界为正、
所有 high-low LOTO 为正、删除主导任务后仍为正。主导任务只按 primary pair 数确定并以 task ID 字典序破平，不看
outcome。TF-IDF 与 component gain 是分别命名的更强门，不能救失败的容量 primary。若不过，不加 seed、不换 split、
不删任务救结果。

## 论文定位与贡献归属

- 不能再申“首个 MLE trajectory dataset”“首个 tree/sibling reward model”或“首次 critic-guided code search”；
  ML-Agent、OpenMLE、mle-traj、AgentRM、ReLoc、SELA 等已覆盖相邻主张。
- 更直接地，FOREAGENT（arXiv:2601.05930）已经发布 MLE solution-preference corpus 并报告 Predict-then-Verify
  加速；AI Research Preference Models（arXiv:2608.13940v2）已经在 AIRA-dojo 同 parent 生成 15 个未执行 child，
  用 inference-only/agentic RPM 选择一个执行，并给出 20 tasks × 10 seeds 的端到端正结果。因此“首次执行前比较
  两个 MLE 解”“首次 preference-guided AIRA 加速”“subtree future-potential 新标签”也全部关闭。
- 可守位置是：真实 MLE search 的 provenance-bound sibling-fragment benchmark，联合 physical-run/config/time split、
  outcome-blind closure、label/noise/cost/missingness/pair-weight audit 与同池 predictor study。
- Table 4B 会把 RPM-style inference-only prompt transfer 作为必须出现或明确说明缺失原因的直接 baseline；只有 exact
  prompt/model/context/tournament/budget 全匹配才称 reproduction，否则必须标为 transfer。closure 前仍不读任何结果。
- 原始前瞻语料生产和 0820 探索性 scaling 信号归学长；run-clean/temporal corpus、sibling estimand、benchmark/audit、
  independent verification 与论文测量主张归我们这边；clean confirmation 联合完成。

本次只把 2026-08-22 已完成的一手竞品审计补进当前英文稿和 citation map，不是新科学结果，也不改变 sidecar/closure/
GPU 门。主引用入口为 `phase1/RELATED_WORK_CITATION_MAP_20260902.md`。

## 同步推进

我们继续守候 Target-522/first-960、维护 prediction escrow/closure，并写 Table 1--3、Figure 1--2、数据卡、撤回表与
methods/audit sections。没有新 sidecar 前不再用缺 provenance 的新 runs 冒充 scaling confirmation。

### 2026-09-02 最新防 scoop 增量

- DeltaML-Bench（arXiv:2608.19653v1）已覆盖 48 个真实研究仓库上的 MLE agent benchmark，并加入分层
  specification-gaming 检查；BAITBENCH（arXiv:2608.30724v1，8 月 31 日提交）已覆盖 planted shortcut、隐藏
  robust split、canonical run evidence 与多 judge 的 reward-hacking 审计。
- 因此不得再写“首个可信 MLE-agent benchmark / 首个隐藏 held-out 评测 / 首个 integrity audit”。二者没有把
  naturally logged sibling choice + common-pool cross-family predictor measurement 作为主单元，故我们的窄定位仍成立。
- 这是防 scoop 文稿维护，不是新科学结果，也不改变 clean-scaling 的 sidecar/closure 门、GPU 批准门或贡献归属。
