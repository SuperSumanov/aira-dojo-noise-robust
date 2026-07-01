# 实验提示词集 — MLE Agent 的噪声鲁棒 RL 搜索控制器

> 🟡 **扩展线（gated，非默认）。** 主线是「多保真 + 保真度一致评估」（见 `研究提案 v2…md`）。
> 本 RL 控制器线**仅当预实验 0.5 绿灯（TD 在真实树上确实降方差）且算力有余时才做**——
> 否则其保底（RQ1/T0）不成立。别默认朝这条线 fork + 实现全套。

> 用法：按 `0 → 0.5 → 关口C → 1 → 2 → 3 →(4)→ 5` 顺序粘进 Claude Code。
> Prompt 0、0.5、1、3 都强制「先给计划/diff，我批准再动」。
> ⚠️ T0（Prompt 2）原被当成「几乎稳成立的保底」，但这依赖「TD 在真实树上有东西可 backup」——
>   未必成立。所以先用 **Prompt 0.5（预实验）** 验证保底生死，再决定是否投入实现。

---

## 执行总纲：关口次序（先砍风险，再放大）

别一上来就 fork + 实现全套 + 跑几百个 run。按下面三道关，每关用最小代价砍最大风险；
过不了就停或换线。配套：`planning/TD_保底验证_预实验.md`、`planning/预算与可行性估算.xlsx`。

1. **关口 0.5 — TD 保底生死**（半天，~6–15 GPU·时）
   跑 `planning/TD_保底验证_预实验.md` 的 Prompt 0.5：只用现有 baseline 搜索日志 + 离线复算，
   验证「TD 相比 MC 在真实树形上是否真降方差 / 减选错」。
   🔴 红灯（树太浅 / TD≈MC 落噪声带）→ 别做 Prompt 1，把保底换成多保真 / 方差感知选择（提案 v2 线）。
   🟢 绿灯 → 进下一关。

2. **关口 C — 最小 go/no-go**（~6 墙钟天，~$275）
   只跑 T1 的 B(UCT+MC) vs C(完整控制器)，4 任务 × 5 seed，先证「B≠C 值不值得放大」。
   B≈C 且落噪声带 → 转「瓶颈归因」或换线，别盲目放大。

3. **关口 B — 分级放大**（~46 墙钟天，~$1710，约占 9/29 窗口一半）
   值得才放大：核心 A/B/C ×10 seed + 消融先 ×3 seed 筛，存活对照再补到 ×10。
   ⛔ 完整设计（7臂×8任务×10seed ≈ 600 run / 81 天 / $3000）塞不进存储窗口，别直接上。

> **正式开跑前先拿 1 个 pilot run 实测**每-run 的 GPU 小时与 token 成本，回填
> `预算与可行性估算.xlsx` 的 B4/B6——现有 6h / $5 都是占位估值。
> 口径：效率横轴用实际训练 **GPU-秒**（不用墙钟，共享节点会污染），并用 `-w` 钉节点。

---

## 研究问题（贯穿全程）

当 MLE agent 的评估被做干净（Hidden Consistent Evaluation, HCE）之后，在**搜索控制器层**（不微调 LLM 权重）引入正经的 RL credit assignment / 探索 / 预算分配，能否改善 MLE agent —— 即推翻还是确认 AIRA-dojo「搜索策略不重要」的负结论。

- **RQ1**：噪声 reward 下，TD/advantage 回传相比 MC 回传，能否显著降低节点价值估计方差、减少选错分支？
- **RQ2（主）**：HCE 干净评估下，完整 RL 控制器能否改善 MLE agent？
- **RQ3**：把多保真预算分配重写成固定预算 best-arm identification，能否在「一天预算」下更高效？

---

## 用之前先填这几个空

粘贴前替换所有 `<...>` 占位：

- `<GPU型号×可并行张数>`（如 `RTX 3090 24GB × 4`）
- `<每任务预算小时>`（单 run ≤1 天，建议先 6–8h）
- `<seed数>`（主实验建议 ≥10）
- `<任务子集>`（建议先手挑 6–8 个轻量 tabular 任务，让 Prompt 0 帮你选）
- `<DeepSeek API key 与 base_url>`
- `<另一个 OpenAI 兼容底座>`（T2 用）

---

## Prompt 0 — 项目启动 + 侦察（先跑这个，别让它直接写代码）

```
我们要做一个 ML 研究项目。这条消息只做侦察和规划，先不要写实现代码。

## Goal（整个项目的唯一问题）
当 MLE agent 的评估被做干净（Hidden Consistent Evaluation, HCE）之后，在“搜索
控制器层”（不微调 LLM 权重）引入正经的 RL credit assignment / 探索 / 预算分配，
能否改善 MLE agent —— 即推翻还是确认 AIRA-dojo “搜索策略不重要”的负结论。

## Context
- 代码基线：fork facebookresearch/aira-dojo（开源，含 Greedy/MCTS/Evo 搜索策略、
  MLE-bench 任务、Apptainer 执行环境）。
- 底座：DeepSeek（OpenAI 兼容 API），model-agnostic 是卖点，全程不微调权重。
- 硬件：<GPU型号×可并行张数>，单次实验 ≤1 天，集群支持长任务但要 checkpoint/resume。
- 关键前置工作：AIRA-dojo（2507.02554，搜索 policy×operator 形式化、负结论）、
  AIRA_2（2603.26499，HCE 协议、把退化诊断为评估噪声）、ArchPilot（2511.03985,
  proxy 多保真）、RewardHackingAgents（2603.11337，full_locked 防作弊）。

## 这一步只做四件事，做完停下来等我确认：
1. clone aira-dojo，读它的 Solver / 搜索策略 / 评估(fitness) / 数据划分 抽象，
   告诉我【精确的集成点】：(a) 在哪改节点价值回传与选择策略，(b) 在哪插入
   HCE 的 train/search/val 划分与外部化评分，(c) 在哪挂 proxy/低保真评估钩子。
   贴出相关文件路径与关键类/函数签名。
2. 列出可在 <GPU型号> 上、每任务 ≤<每任务预算小时>h 跑完的【轻量 tabular 任务
   候选清单】（从 MLE-bench 里挑 6–8 个），并说明为何这些 proxy 评分与全量评分
   的排序相关性大概率较好（视觉/大模型任务先排除）。
3. 给出仓库改造的最小计划：模块边界、配置项、产物（CSV schema）。
4. 指出任何会破坏“公平对照”的坑（算子/底座质量盖过控制器收益、proxy 相关性、
   污染共模等）。

## 贯穿全程的硬约束（写进 CLAUDE.md，后续每步都遵守）
- 公平契约：对照实验中【只有搜索控制器变】，算子集、底座、每任务预算、任务集、
  HCE 划分全部固定且记录。
- 复现：pin 依赖版本与 git commit；记录所有 seed（python/numpy/框架/采样温度）；
  把命令、config、环境与 seed 写进产物文件；结果用 CSV，一行一个 run，所有旋钮
  作为列。
- 诚实：报 median + 跨 seed 方差，绝不只报均值；长/贵实验前先给我配置清单和预计
  GPU·时，我批准再跑；主动标注 confound、measurement artifact、“好得不真实”的结果；
  实验日志要记下失败和废弃的配置，不只记漂亮数字。
- 完整性：评估用 full_locked / HCE —— 外部 pristine 评分、固定隐藏 split、禁止
  训练期读 held-out/test 路径。
```

---

## Prompt 1 — 实现 RL 搜索控制器 + HCE（确认侦察结果后）

```
按上一步确认的集成点实现下列模块，先给我设计与 diff 预览，我批准再落代码。

## 要实现的（全部在搜索控制器层，不动 LLM）
1. 价值回传后端，可切换：
   - baseline: Monte-Carlo Q/N（复刻 AIRA-dojo/MLEvolve 现状）
   - ours: TD(λ) 自举 + advantage（baseline 取同层兄弟均值或一个轻量学习势函数）
2. 选择策略，可切换：UCT(baseline) / Thompson 后验采样(ours，对分支价值维护
   高斯后验，用多次噪声 proxy 评分估均值方差) + 可选新颖性内在奖励
   r_int = β·novelty(plan/解的嵌入距离)。
3. 预算分配，可切换：ad-hoc（baseline）/ 固定预算 best-arm identification
   （sequential halving / UCB-E）跨候选与保真档分配评估预算。
4. potential-based reward shaping: F(s,s')=γΦ(s')−Φ(s)（可开关，默认关）。
5. HCE 评估层：80/10/10 = train/search/val；D_search 对 agent 隐藏、外部化评分；
   D_val 只用于最终选择且对搜索隐藏；full_locked 强制（pristine 评分 + 禁训练期
   读 held-out）。
6. checkpoint/resume：搜索图、价值统计、记忆、最优解可落盘续跑（应对集群时限）。

## Constraints
- 每个组件用配置开关独立可关，保证后面能逐组件消融。
- 不改动算子集与底座调用；这俩是固定的公平变量。
- 所有随机性走统一 seed。

## Verification（实现就要带的自检）
- 单元测试：TD 回传在玩具树上收敛到解析值；HCE 划分无泄漏（写测试证明 agent
  拿不到 D_search/D_val 标签）；full_locked 下篡改评估代码不影响 true_metric。
- 给我一个 5 分钟内能跑的 smoke test（1 任务、极小预算），证明端到端跑通且产物
  CSV 字段齐全。
```

---

## Prompt 2 — T0 诊断实验（最便宜、几乎稳成立、保底结果）

```
## Goal（一个问题）
在带噪 reward 下，TD/advantage 回传相比 MC 回传，是否显著降低节点价值估计的
方差/偏差，并减少“选错分支”？（这是 RQ1，不需要赢分。）

## 设计（template: ablation + harness）
- 自变量：价值回传方式 {MC, TD(λ), TD+advantage}。
- 受控固定：同一搜索轨迹/同一批候选、同 seed 集、同任务。
- 噪声注入：在评估上叠加可控噪声以模拟“幸运 split”（给定方差 σ 的若干档），
  这样可以在便宜的离线/小规模搜索日志上直接对比，不必每次跑全量训练。
- 任务：<任务子集> 里挑 3–4 个最轻的；seed ≥ 10。

## 测什么
- 节点价值估计相对“真值”（用高保真重复评估的均值近似）的方差与偏差；
- 选错率：被选中的分支不是真·最优分支的比例；
- 随噪声档 σ 增大，三种方法的退化曲线。

## Verification
- 先给我配置清单与预计 GPU·时再跑。
- 报 median + 跨 seed 方差，画退化曲线（带 error bar）。
- 诚实判定：若 TD 的优势落在噪声带内或只在某些 σ 出现，明确说出来，并解释为何。
```

---

## Prompt 3 — T1 主实验（回答主问题，需要并行）

```
## Goal
HCE 干净评估下，完整 RL 控制器 vs 基线，能否改善 MLE agent？逐组件拆，看各自贡献。

## 设计（template: sweep/ablation）
- 对照臂（只变搜索控制器，其余全固定）：
  A. Greedy（AIDE 式，下界）
  B. UCT + MC（= AIRA-dojo 的 MCTS，关键对照，复现其“策略不重要”的条件）
  C. RL 控制器（TD+advantage + Thompson + BAI 分配）
  D. 消融：从 C 各去掉一个组件（−TD / −Thompson / −BAI / +shaping）
- 受控固定（公平契约，逐项记录）：同底座(DeepSeek)、同算子集、同每任务预算
  <每任务预算小时>h、同任务集 <任务子集>、同 HCE 划分、同 full_locked。
- 任务：MLE-bench Lite 子集 <任务子集>；seed = <seed数>（≥10）。
- 单次实验 ≤1 天：用 <GPU型号×张数> 并行跑任务×seed；每个 run 必须能 checkpoint。

## 测什么
- 主指标：medal rate 与 Percentile Rank vs GPU·时（效率前沿）；
- 机制证据：跨臂的节点价值方差、长程是否退化（复刻 AIRA_2 Fig.4 式诊断，但在
  本设置下）、选错率；
- 各消融组件的增量。

## Verification（重点，别让结果骗我）
- 跑前给我完整 config 矩阵 + 总 run 数 + 预计 GPU·时；太大就先粗扫再细化。
- 每个数都要跨 seed 方差；任何“B≈C（策略不重要）”或“C 显著>B”都要先排除是
  noise / 是 seed 太少 / 是某个任务主导。
- plausibility check：把 B（UCT+MC）的绝对水平与 AIRA-dojo 报告对一下量级，
  对不上要查原因（底座/预算/任务差异）。
- 明确区分两种可发表结局：C 显著>B（推翻负结论）；或 B≈C（确认负结论→转“瓶颈
  归因”：把算子/底座质量设为受控轴，量化是不是它们盖过了控制器）。
```

---

## Prompt 4 — T2 扩展（算力允许再做）

```
## Goal
(1) 增益是否跨底座稳健？(2) BAI 多保真预算分配在“一天预算”下是否优于砍半启发式？

## 设计
- 加底座轴：DeepSeek vs <另一个 OpenAI 兼容底座>，看 C 相对 B 的增益是否保持。
- 多保真：低保真档（10% 数据 / 1 epoch，参照 ArchPilot）+ 全量档；比
  {ad-hoc 砍半, sequential halving, UCB-E} 在固定 GPU·时下的最优解命中率。
- 任务：在 Lite 子集基础上加 2–3 个 medium 任务测普适性（注意每任务仍 ≤1 天）。

## Verification
- 同前：配置清单先审、跨 seed 方差、效率前沿对比。
- confound 提醒：proxy 与全量分的排序相关性在 medium/视觉任务可能变差，逐任务
  报相关性，结论别外推到相关性差的任务。
```

---

## Prompt 5 — 分析与作图（每阶段结束跑）

```
## Data
<结果 CSV 路径>，一行一个 run，列含所有旋钮 + 指标 + seed + commit。

## 要回答的问题
就是该阶段的 Goal（T0=RQ1 / T1=主问题 / T2=RQ3+跨底座）。

## 做什么
- 用跨 seed 方差判断效应是否在噪声之上，给出 effect size；
- 作图：效率前沿（Percentile Rank vs GPU·时，带 error bar）、消融柱状图、
  价值方差/退化曲线；坐标轴带单位、出版可读。
- 标注一切可疑：非单调、离群、落在噪声带里的“胜利”、与已知基线矛盾的结果。
- 给出诚实结论，包括【数据不支持什么】。
```

---

## 关键提醒

- 顺序：`0 → 0.5 → 关口C → 1 → 2 → 3 →(4)→ 5`（见开头「执行总纲」）。
- **T0 不是无条件保底**：先用 Prompt 0.5 验证「TD 在真实树上有东西可 backup」；红灯就把保底换成多保真 / 方差感知选择（提案 v2 线）。
- 跑 T1 前必须定死三个数：**能并行几张卡** + **每任务预算小时** + **pilot 实测的每-run 成本** —— 它们决定 `seed×任务×臂` 的总 run 数、GPU·时与 API $（见 `planning/预算与可行性估算.xlsx`）。
- 参考文献：AIRA-dojo 2507.02554 ｜ AIRA_2 2603.26499 ｜ ArchPilot 2511.03985 ｜ RewardHackingAgents 2603.11337 ｜ MLEvolve 2606.06473。
