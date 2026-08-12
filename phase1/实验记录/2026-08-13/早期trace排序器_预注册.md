# 早期 trace 排序器：零 GPU 预注册

时间：2026-08-13（读取模型结果之前）

## 1. 问题与动机

冻结的 100 个真实 sibling 决策集上，120 秒已有可评分提交的候选可以作为可靠
incumbent，但其余 144/230 个候选仍无提交。全部续跑几乎不省成本；oracle 只续跑每组
最有希望的一个 silent candidate，却可保持全部续跑的 0.9600 eventual endpoint identity，
说明存在约一半成本的
可压缩上界。问题是：**只使用 120 秒时已经可见的执行痕迹和已冻结的静态 critic 输出，
能否跨物理 run 选择应续跑的 silent candidate？**

## 2. 冻结总体与泄漏边界

- 总体固定为 `fidelity_manifest.jsonl` 的 100 个 parent、230 个 child、52 个物理 run；
  不增删样本。
- 120 秒观测固定为 `fidelity_results.jsonl`；标签为已经支付过的最终外部 `graded`。
- 静态信号只读 `perpair_decision.json` 中对冻结测试对的 OOS 预测；不重新训练代码 critic。
- 外层切分的最小独立单元是物理 run，同一 run 的所有 parent/child 必须同折。
- 再报告 leave-one-task-out；它是更强的跨任务压力测试，不替代 run-OOS 主结果。

## 3. 预先固定的特征与模型

仅在 silent candidates 之间学习 pairwise 顺序。候选特征不含最终 `graded`、最终 runtime、
最终 self-report 或 120 秒外部 `sub_score`。

1. `scalar`：`log1p(stdout_bytes)`、`log1p(stderr_bytes)`、`rc==0`、是否解析出 stdout
   validation、其组内有向 percentile、keyed 标记、固定关键词阶段计数，以及冻结的
   `code_len/static_lr/tfidf_lr` 组内 Copeland 分数。
2. `text`：只对该外层训练折的 `stdout_tail + err_tail` 拟合 word 1--2 gram TF-IDF
   (`min_df=2, max_features=2048, sublinear_tf=True`)。
3. `combined`：scalar + text。

scalar 仅用外层训练折拟合均值/尺度，text 保持 TF-IDF 自身的 L2 normalization。三个模型
均为固定 `C=1`、L2、`fit_intercept=False` 的 pairwise logistic regression；每个
训练 pair 同时加入正、负两个方向，不调参。主模型预先指定为 `combined`；`scalar/text`
只作消融，不能事后替代主模型。

## 4. 策略、基线与成本

- 已有 artifact 按 120 秒外部 pristine score 作为 incumbent。
- 每组只续跑模型得分最高的一个 silent candidate；然后在 incumbent 与该完整结果间选择。
- 基线：解析 stdout 优先 + 冻结 TF-IDF、解析 stdout 优先 + 随机 silent、以及解析 stdout
  优先 + oracle silent（上界）。所有 top-1 策略续跑数和成本完全相同。
- 成本同时报告 restart 和 resumable continuation 两种口径，使用冻结的历史精确 runtime。

## 5. 指标与推断

- 主指标：100 个 parent 上的 top-1 命中率。
- 主比较：`combined(run-OOS) - random` 的逐 parent 配对差；95% bootstrap 以物理 run
  聚类，10,000 次，seed=7。
- 辅指标：raw regret、LOTO top-1、相对全完整执行的精确成本。
- 同命令复跑必须逐字节一致。

## 6. 预注册裁决

- **GO**：主比较的 run-cluster 95% CI 下界严格大于 0，且 LOTO 点估计不低于随机；
  才能称为“早期 trace 提供可迁移续跑信号”。
- **BORDERLINE**：run-OOS 有正点估计但 CI 跨 0，或 LOTO 低于随机；仅作为扩大预注册
  数据集的候选，不得称突破。
- **KILL**：run-OOS 点估计不高于随机，或出现任何 run/fold/标签泄漏；停止该方向。
- 无论结果如何，不在这 100 组上调关键词、C、TF-IDF 范围或选最优模型。

## 7. 成本与可复现性

纯 CPU，预计小于 5 分钟，无 API/GPU 消耗。产物需记录输入 SHA256、脚本 SHA256、commit、
Python/sklearn 版本、折分映射、逐 parent CSV、汇总 JSON 和确切命令。

## 8. 冻结后结果（不得用于改写以上规则）

语义边界：本节预注册的 top-1 是“所选 card 的 eventual full endpoint 是否为最优”的
routing diagnostic，不是 artifact 停在 120 秒时的实际部署分数。后续独立部署审计发现
all-escalate 的两者分别为 0.9600 与 0.9200；本方向的 **KILL** 仅依赖 combined 相对
同预算 random 的配对差，故不受公共语义偏移影响，但这些 top-1 数字不得再称部署质量。

两次同命令复跑的 `summary.json`、`per_set.csv` 和 stdout 逐字节一致。总体为 100 sets、
52 physical runs、230 children，其中 144 silent；可用于训练的非平局 silent pair 只有 87。

| 策略 | top-1 | run-cluster 95% CI | restart/full | continuation/full |
|---|---:|---:|---:|---:|
| random expected | 0.6433 | [0.5578, 0.7294] | 0.4982 | 0.4717 |
| stdout + frozen TF-IDF | 0.6600 | [0.5417, 0.7677] | 0.5247 | 0.4982 |
| combined, run-OOS（主模型） | 0.6100 | [0.4956, 0.7222] | 0.5081 | 0.4816 |
| combined, LOTO | 0.6000 | [0.4808, 0.7130] | 0.5167 | 0.4902 |
| oracle top-1 silent | 0.9600 | [0.9010, 1.0000] | 0.4951 | 0.4686 |

主比较 `combined(run-OOS) - random expected = -0.033333`，run-cluster 95% CI
`[-0.094982, +0.033003]`；LOTO 差为 `-0.043333 [-0.108911, +0.020000]`。因此严格按
预注册判为 **KILL**。普通早期 trace 文本/进度统计没有提供可迁移的续跑排序信号；不在
这批 100 sets 上继续调关键词、正则或模型选择。oracle endpoint headroom 仍在，但不能当作
方法收益或部署质量保证。
