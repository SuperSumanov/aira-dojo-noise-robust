# 当前研究方向唯一入口（2026-08-13）

> 本文件按日期与撤回链整理，覆盖最近两周的实验记录与 Git 提交。后续实验先读本文件，
> 不得用更早报告、旧 `AGENTS.md` 摘要或旧 HCE 配置覆盖这里的裁决。

## 1. 审计截面

- 我方分析基线：`fork/phase1-value-critic@53ab345e04f271bcc5086752fbeba0da8c91706c`
- 学长分支：`fork/dojo-reproduce@8c57b7580e22fdbb2cbab350bc34475d084fe5ee`
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
- `phase1/实验记录/2026-08-13/late-artifact连续轨迹_pilot裁决.md`；
- `phase1/实验记录/2026-08-13/连续fidelity轨迹_watcher_smoke冻结说明.md`；
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
3. **更强但改 operator 的候选**：让 agent 在固定早期预算内优先产 schema-valid cheap submission，
   再继续优化。这可能提高 120 秒 artifact 覆盖，直接攻击 144/230 silent 的瓶颈；但它改变
   operator/prompt，必须另立三臂公平实验，不能冒充只改评估旋钮。
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
