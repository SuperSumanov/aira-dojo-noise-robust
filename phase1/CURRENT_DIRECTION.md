# 当前研究方向唯一入口（2026-08-13）

> 本文件按日期与撤回链整理，覆盖最近两周的实验记录与 Git 提交。后续实验先读本文件，
> 不得用更早报告、旧 `AGENTS.md` 摘要或旧 HCE 配置覆盖这里的裁决。

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
