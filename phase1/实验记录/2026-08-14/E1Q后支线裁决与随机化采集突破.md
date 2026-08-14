# E1-Q 后支线裁决与随机化采集突破

日期：2026-08-14。性质：设计记录，不是 E2 预注册或执行授权。

## 1. E1 真正回答了什么

E1 的独立单位不是 8 个 iid rows，而是 2 tasks / 2 anchors / 4 siblings。两个 task 的 sibling winner 在两次
replicate 中都一致，说明 fresh-workspace、policy-indexed matched labels 可以稳定落盘；但其中一个 tabular
sibling 两次都没有 scored artifact，稳定排序部分来自 feasibility hurdle，而不是细微 quality discrimination。

continuation 状态为 6 ok、1 execution error、1 timeout；6/8 被 D_search/D_val 评分。2/8 gain>0，0/8 gain≥0.01。
因此：

- “label construction 可行”过门；
- “H=1 continuation 有 practical utility”没有正证据；
- “hurdle critic 会胜过 monolithic critic”尚未实验；
- 不能把 6/8 当 iid Bernoulli 做窄区间，失败按 sibling/task 聚类。

实际成本为每 rollout `0.170798152181805 GPU·h`、`614.873347854496` candidate-wall 秒。若任务混合不变，
48/72/144 rollouts 的线性点估计为 `8.19831130472662/12.2974669570899/24.5949339141799 GPU·h`；但新任务
runtime 可能更长，正式预算仍须用每 candidate 600 秒上界另报，不能只报该点估计。

## 2. 不推荐直接做旧 E2

旧 72-rollout/43.76 GPU·h 表不是根据 Qwen validity、task runtime 或 observed variance 设计的。直接启动会同时
承担三个风险：样本仍被少数 task 主导；大量预算用于明显 invalid sibling；即使训练 loss 下降，也未必改善
parent-equal fixed-budget utility。E1 结果不构成 E2 自动授权。

## 3. 更强的正向突破：把随机化嵌入未来数据生产

学长计划继续以约 60 physical runs/day 生产两三周数据。若双方同意，可在**独立实验 runs** 中把少量现有搜索
预算改成 randomized sibling micro-intervention，而不是另加一套昂贵 side run：

1. 在满足 exact-two、fresh workspace 与 public/pristine evaluator 契约的 decision point，预先随机 blocked order；
2. 广覆盖部分每 sibling 恰好 K=1，保留明确 propensity；小型 calibration 子集 K=2，用于估计同 sibling variance；
3. 总 candidate-execution budget 与原 run 相同，只改变一小部分 allocation；必须另记 policy hash，不能和正常
   MCTS outcome 混成同一 estimand；
4. outcome-blind 固定任务/anchor 配额，按 physical run append-only 收样，不按 gain 停止；
5. 正常 production 与 randomized runs 分目录、分 release descriptor，避免污染 first-960 主线 cohort。

随机化/propensity/两阶段 hurdle 都不是新统计原语；突破在于得到可发布的真实 MLE-agent interventional decision
resource，并把数据生产本身变成可识别实验。它比继续在历史 behavior-policy labels 上调模型更可能形成正贡献。
但它会改变学长的生产 policy 与 opportunity cost，必须先共同确认，当前不得上线。

## 4. 若获批，下一次只做 E2-A 支持门

建议先给预算而不启动：至少 6 tasks × 4 anchors/task × 2 siblings × K=1 = 48 rollouts / 96 candidate
executions / 48 API calls；当前混合点估计 `8.19831130472662 GPU·h`，candidate cap 上界 `16 GPU·h`。目的只
是估计 task/anchor support、validity heterogeneity 与 effect-size，不训练或宣称方法。

E2-A 的预注册杀死条件应包括：

- 少于 6 tasks 或任一 task 超过 25% anchors；
- validity 结果几乎完全由单 task/sibling 决定，至少四个 task 内没有两类 outcome 支持；
- scored continuation 的 gain 仍全部低于 practical delta，且没有可用 conditional-value variation；
- K=2 calibration 子集显示 within-sibling ranking 不稳定，无法为 broader K=1 labels 校准；
- 实际成本/失败率使同预算 downstream evaluation 不再可行。

只有支持门通过，才比较 task/action-only validity baseline、monolithic expected value 与 hurdle
`P(valid) × E[value | valid] / cost`。最终主指标必须是新 physical-run 上的 parent-equal top-1 与相同真实执行预算
下 best-score/regret；pair accuracy、Brier 与 calibration 只作诊断。底座 LLM 不微调。

## 5. 当前推荐

主资源继续投向 first-960 与 Decision-Corpus release；支线停在“E1 label feasibility positive、E2 not unlocked”。
先把 randomized logging 方案与学长的数据生产计划对齐，再决定是否提出 48-rollout E2-A 预算。若不能改变
production policy，就不应为追方法正结果回到历史标签上反复调 critic。
