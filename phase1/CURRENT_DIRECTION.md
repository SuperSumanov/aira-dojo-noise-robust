# 当前研究方向唯一入口（2026-08-13）

> 本文件按日期与撤回链整理，覆盖最近两周的实验记录与 Git 提交。后续实验先读本文件，
> 不得用更早报告、旧 `AGENTS.md` 摘要或旧 HCE 配置覆盖这里的裁决。

## 1. 审计截面

- 我方分析基线：`fork/phase1-value-critic@1b317eccc7e7c23754962248ad3548d35b8efd90`
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

### 3.4 冻结待跑的机制可行性审计（不是 selector）

只用执行前代码与任务身份预测“120 秒时是否有 finite pristine 外部分”，不把最终质量、stdout、
artifact 分数或 parent 比较用作特征。主模型使用 physical-run 分组的五折 OOF，task/run 双聚类
推断，另做五个 split-seed 敏感性与 whole-task leave-one-out。它只回答可观测性 propensity 是否
可建模；即使达到 GO-FEASIBLE，也不能声称搜索收益，只允许在新的 discovery/validation split
开发显式删失模型。旧 100-set selector 规则仍保持关闭。

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
2. **近期方法化候选**：parent-certified improvement 已以 **BORDERLINE** 关闭。若在新
   discovery split 上继续方法化，必须显式建模 artifact 的可用性/失败/删失过程及条件分数，采用
   cross-fitting 或独立 validation；不能把“是否及时产物”直接当质量，也不能在旧 100 sets 上
   继续搜索 selector、margin 或阈值。
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
