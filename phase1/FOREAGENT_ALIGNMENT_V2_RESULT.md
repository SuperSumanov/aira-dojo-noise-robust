# FOREAGENT 官方 alignment 审计 v2 结果（2026-08-13）

冻结裁决：**INSUFFICIENT-SUPPORT**。主实现与完全独立的 central-number verifier 一致；不能因效应方向
漂亮而改写预注册支持门。与此同时，两种官方 judge 都呈现“任务内最低 gap 四分位接近随机、最高四分位
显著更容易”的一致描述性信号，因此这是后续独立确认的强正向候选，而不是已确认结论。

## 1. 输入、代码与验证链

- outcome 前冻结 commit：`0851d81ca356ede9b36e485847a65882f82c16e7`；
- 官方 manifest：26 tasks、156 files、2 model families × 3 releases；
- compact primitive-field input：110,620 records，SHA256=
  `480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe`；
- DeepSeek primary：三轮 exact grid，18,438 pairs；GPT replication：三轮 intersection 18,430，
  union 18,438，排除 8 个不完整 triplicates，最小 task intersection ratio=0.9947368421；
- exact score ties=0；DeepSeek/ GPT intersection 内各有 49 个 nonfinite-score pairs，对称隔离；
- 13/13 preflight 通过，0 GPU、0 API；主实现 rc=0、独立 verifier rc=0 后才把 staging 原子提升为
  `foreagent_alignment_audit_v2/`；
- summary SHA256=`0f905b54b51af87ffd0d9001d2a27b4f5f76d6c0538ce5f1cf28ae7ea63e8d16`。

结果通过两份实现后，四张 CSV 仅把默认 CRLF 规范化为 LF 以通过仓库 whitespace gate，并重算
`SHA256SUMS`；JSON 数值、summary hash 与裁决均未改变。writer 随结果提交固定 `lineterminator="\n"`。

## 2. 冻结指标结果

三次 release correctness 先在 `model × task × pair` 内平均；headline 为 task-macro，CI 为固定 seed
`20260813` 的 10,000 次 task bootstrap。

| model | overall task-macro [95% CI] | pair-micro [task-CI] | Q1 task-macro [95% CI] | Q4 task-macro [95% CI] | Q4−Q1 paired task-CI |
|---|---:|---:|---:|---:|---:|
| DeepSeek | 0.606698 [0.548455, 0.664555] | 0.615150 [0.575673, 0.652556] | 0.533655 [0.458473, 0.609636] | 0.650385 [0.557848, 0.735120] | +0.116730 [0.039283, 0.196048] |
| GPT | 0.580067 [0.524150, 0.637097] | 0.588960 [0.551896, 0.626638] | 0.530522 [0.451257, 0.610656] | 0.620272 [0.532547, 0.703391] | +0.089750 [0.015195, 0.163951] |

若只看 v2 的效应条件，DeepSeek 满足：Q1 point `<=0.55`、Q1 CI 包含 0.5、Q4−Q1 CI 下界严格
大于 0；GPT replication 方向相同且差值 CI 也严格大于 0。但完整性/支持门优先，因此不得输出
`LOCAL-DIFFICULTY-CONFIRMED`。

## 3. 为什么是 INSUFFICIENT-SUPPORT

有两个独立失败项。

1. v2 沿用 v1，将合法 `prediction.best_index` 与合法 confidence 合并为每 task/run 至少 99% 的
   joint-coverage 门。结构复查显示 DeepSeek 的 55,167 个 finite non-tie release records 中，prediction
   index 覆盖率实际为 1.000000；缺失全部来自 confidence：总体 confidence coverage=0.893613935867，
   confidence-only invalid=5,869，78 个文件中 75 个低于 0.99，最小覆盖 0.666666666667。准确率使用了
   全部 prediction，没有 complete-case 删除；但冻结的 joint gate 仍必须判失败。GPT 55,159 records
   中只有 4 个 prediction/confidence 同时无效，总体覆盖 0.999927482369，逐文件最小 0.998973305955，
   通过 0.99 coverage 门。
2. v2 要求至少 24 tasks 的最低/最高 task-internal gap quartile 各有至少 20 pairs，实际两个模型都只有
   22/26。四个结构上过小的任务为：dog-breed-identification (1/1)、
   jigsaw-toxic-comment-classification-challenge (2/3)、
   nomad2018-predict-transparent-conductors (1/1)、plant-pathology-2020-fgvc7 (4/4)。括号为最低/最高
   quartile pair 数。该失败与模型预测 outcome 无关，但在 v2 前没有被单独统计出来。

方法教训是后续预注册必须把“directional prediction coverage”和“confidence/calibration coverage”拆成
两个门，并在冻结前只用标签无关的 per-task 网格大小验证支持条件。不过这些是下一份独立数据的设计修正，
不能回填到 v2。

## 4. 事后敏感性（明确不能升级 v2）

只为判断是否值得做独立确认，另做标记为 post-outcome 的诊断：

- 在结构支持充分的 22 tasks 上，DeepSeek Q1=0.517047，Q4−Q1=+0.126590，task-bootstrap
  CI=[0.042210,0.210558]；22 次 leave-one-task-out 的差值范围=[0.106535,0.147765]；
- GPT 对应 Q1=0.524708，Q4−Q1=+0.087128，CI=[0.004946,0.167206]；leave-one-task-out
  范围=[0.068868,0.104879]；
- 两模型在 22-task 子集都为 16 positive / 0 zero / 6 negative tasks，双侧 exact sign p=0.052478790283。

因此正梯度不由一个任务或四个微型任务制造，但 sign test 接近而未低于 0.05；这些数不能替代新的
confirmatory run。

## 5. 对早先自动 parquet 审计的版本纠正

官方 HF 自动 parquet（18,361 rows）与本次 alignment（18,438 pairs）并非同一网格少 77 行。用 task
与发布物四位 solution id 对齐后，主脚本和独立 verifier 一致得到：共同 18,270、alignment-only 168、
parquet-only 91。共同 pairs 也来自不同重评分版本：18,221 个双方都能定义 winner 的 pairs 中，5,068 个
winner 不同。故：

- `18,438−18,361=77` 不能解释为 ties、NaN 或简单过滤；
- 早先 parquet pairing audit 仍准确描述其锁定输入的组合复用与 gap 分布，但不能作为本次 alignment
  predictions 的精确 label/gap 网格；
- 本次 alignment 结论只使用同一发布文件内的 scores 与 predictions，并已验证两模型/三轮 truth 一致，
  不受 parquet 版本差异污染。

## 6. 允许与禁止的论文表述

允许作为描述性发现：在官方 alignment 发布物中，两种 judge 的 task-internal gap 梯度方向一致，且最低
四分位 task-macro 均接近随机；这与我方真实 sibling decisions 富集在局部近邻区域的结果共同支持
decision-aware / gap-aware benchmark 的必要性。

禁止表述：

- “v2 预注册确认了局部困难”——支持门失败；
- “FOREAGENT 的总体准确率是假的”或 agent-level 加速无效——本审计没有测试 agent-level 因果效果；
- 把 parquet 的 gap/labels 与 alignment 的 prediction 网格混为一谈；
- 在同一 26-task outcome 上开 v3 删除 confidence 门或降低 24-task 门，再称 confirmatory。

下一次确认必须使用尚未生成的 judge outputs 或新的 physical-run sibling 数据；预先拆分 prediction 与
confidence 门、先做标签无关的任务支持审计，并保持 task/run 聚类与一次性裁决。
