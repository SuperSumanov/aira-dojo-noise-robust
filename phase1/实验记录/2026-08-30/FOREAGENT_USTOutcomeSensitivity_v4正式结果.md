# FOREAGENT UST outcome sensitivity v4：正式结果

## 裁决

这是一个可用于论文的**外部 benchmark-audit 正结果**，不是 critic 性能提升。

1. **图感知修正确实非平凡**：exact common support 有 18,381 条 pair rows，但 endpoint-edge incidence rank
   只有 `868`，cycle rows=`17,513`；UST 与 uniform edge distribution 的 total variation=
   `0.11449711207982645`，task-weight TV=`0.11373050512738934`。
2. **绝对 pair-micro 会移动，但下降未获 task-clustered 显著支持**：DeepSeek raw/UST=
   `0.6152186134232811/0.6052414090772692`，变化 `-0.0099772043460119031`，95% CI=
   `[-0.024529104704855254, 0.0026177484893845637]`；GPT raw/UST=
   `0.58895961409426412/0.58113517235648726`，变化 `-0.0078244417377768549`，95% CI=
   `[-0.020361700974923402, 0.0032945061117868324]`。两个区间都跨 0。
3. **模型比较对图权重稳健**：DeepSeek−GPT 的 equal-task task-macro 在 raw 下为
   `0.026657533634302202`，95% CI=`[0.0021004144235817652, 0.053036401295895153]`；UST 后为
   `0.02671874905758977`，95% CI=`[0.0019568230933495541, 0.053442489897444191]`。两者下界都高于 0，
   且 26/26 个 leave-one-task-out 删除下都保持正号。

因此允许的核心表述是：**pair 图依赖会非平凡地改变 benchmark 的隐式权重与绝对 headline；在一个外部公开 MLE
benchmark 上，图感知 UST 重加权没有推翻主要模型比较。** 不允许说 UST 提升模型、accuracy 显著下降、`868` 是有效
样本量，或据此重写 FOREAGENT 的 agent-level 结论。

## Exact common-support 结果

| 系统 | raw pair micro | UST rank micro | UST−raw（95% task CI） | raw task macro | UST task macro | UST−raw（95% task CI） |
|---|---:|---:|---:|---:|---:|---:|
| DeepSeek | `0.6152186134232811` | `0.6052414090772692` | `-0.0099772043460119031` (`[-0.024529104704855254, 0.0026177484893845637]`) | `0.60672439035215153` | `0.60580917495867836` | `-0.00091521539347316772` (`[-0.0027681028509883854, 5.9468097512005436e-05]`) |
| GPT | `0.58895961409426412` | `0.58113517235648726` | `-0.0078244417377768549` (`[-0.020361700974923402, 0.0032945061117868324]`) | `0.58006685671784952` | `0.57909042590108883` | `-0.00097643081676068721` (`[-0.0027150123363389733, 0.00017573968559969622]`) |

这里 release runs 先在同一 model-task-pair 内平均，再聚合；primary inference 是 26-task clustered bootstrap，
20,000 repetitions，seeds=`20260830/20260831`。不能用 18,381 行作 pair-iid 推断。

DeepSeek−GPT 的 pair-micro 差在 raw/UST 下分别为 `0.026258999329017273` 与
`0.024106236720782173`，对应 95% CI 分别为 `[-0.0035077846557868969, 0.058978263879274531]` 与
`[-0.0040085986029572184, 0.055564483872122969]`，均跨 0。只有预先并列报告的 equal-task task-macro 比较得到
下界高于 0；不能把 pair-micro 说成显著模型差异。

## 图结构

- pairs/vertices/tasks/components=`18,381/894/26/26`；
- complete/incomplete components=`7/19`；
- incidence rank/cycle rows=`868/17,513`，且 `18,381−868=17,513` 独立算术一致；
- UST weight sum=`867.99999999996919`，最大 component Foster residual=
  `1.0160761121369433e-12`；
- minimum/median/maximum edge weight=
  `0.039999999999999938/0.040000000000000029/0.66666666666666663`；
- unit-probability bridge edges=`0`；
- raw/rank maximum task share=`0.066644905065012791/0.056451612903225805`。

这里的 `868` 仅是 endpoint-edge incidence design rank；不是有效样本量、独立 label 数、feature-matrix rank、
Shannon information 或任意模型的自由度。

## Formal 与独立复验

- exact source commit：`b0fddf62134f006809278418a109411f4426da87`；
- scientific/execution/identity/numeric protocol SHA-256：
  `7d47b1aa...557a425` / `2da287a5...58c7869` / `e2d8f6a5...6f3684` / `5a47d185...83fb69`；
- formal root：`/research/d7/spc/yzyang4/foreagent-ust-outcome-sensitivity/formal-b0fddf6-v4`；
- focused/full：`13 passed in 0.46s` / `1773 passed, 48 warnings in 106.63s`；
- producer A/B 与 independent grounded-inverse verifier A/B 各自逐字节一致；四份 stderr=`0 bytes`；
- independent maximum absolute numeric difference=`2.2737367544323206e-13`；
- result/verification/manifest SHA-256：
  `ec51dcfadb2c322b784841f8f47fa7e71f0d75d631fa9224dcf32c46ceff4083` /
  `6a0942e070362f85ef45c270b3f3d00bb689337c08dc7260e74abd8859df43f1` /
  `a5d35103f8507396ead59d28695da72005d7dc7383c0be6b1af58b8a5dea0567`；
- 23-entry manifest 全通过，root/result/verification mode=`500/400/400`；
- producer/verifier forbidden-path 与 network hits=`0/0/0/0`；credential filename/content=`0/0`；
- confidence、solution code、prospective values 未读；raw task/endpoint identities 未输出；
- GPU/API/model fit/base update=`0/0/0/0`。

前三个 fresh formal 根分别因 BLAS 线程过订阅、raw path 未按 task 命名空间、以及 raw reproduction 门低于合法
binary64 summation error 而在完整结果前 fail-closed；均未复用。v4 只在结果前按追加协议修正对应工程门，scientific support、
estimands、bootstrap、KNOWN raw constants 与分类均未改变。

机器回执：`phase1/foreagent_ust_outcome_sensitivity_formal_receipt_20260830.json`。

## 论文意义与边界

这条结果把我方“comparison graph 需要 rank/UST-aware audit”的主张从自有历史语料外推到了直接相关的公开 MLE
predict-before-execute benchmark，并同时展示：结构修正可以改变绝对 micro headline，但严谨的 task-macro 模型比较可能仍然
稳健。它适合作为 Decision Corpus + Predictor Benchmark + Audit Protocol 的外部有效性实验。

它没有解决独立 critic 在干净、未触碰、时间外 cohort 上的性能问题，也不授权 first-960/Target-300/Target-522 提前揭盲、
新模型训练、GPU 或付费 API。下一步继续 outcome-blind 摄取与冻结 cohort，同时把 rows/vertices/components/rank、UST/raw
sensitivity、真实 run/parent grouping 和 cluster assumption 固化成 benchmark release checklist。
