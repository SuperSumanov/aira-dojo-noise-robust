# critic 门控升级的真实成本–质量 Pareto 裁决（2026-08-13）

## 结论

存在一个有信息量但尚不能升格为主结果的 Pareto 点：在 120 秒低保真阶段后，按既有
out-of-sample TF-IDF critic 只升级排名前两名的沉默候选，top-1 为 **0.9300**
[0.8621, 0.9823]，restart / resumable-continuation 成本分别为全量执行的
**0.8783 / 0.8290**。相对“升级所有沉默候选”的 0.9600，配对差为 **−0.0300**，
physical-run clustered 95% CI **[−0.0706, 0.0000]**。

这说明可以换取约 10.7%（restart）或 17.1%（可恢复执行）的成本节省，但当前数据不能
证明这 3 个百分点的质量损失可忽略。它是后续独立确认的候选，不是已经成立的突破。

## 冻结设计

- 人群：原 fidelity manifest 的 100 个真实 sibling sets（50 hard + 50 easy），230 个
  children / 19 tasks / 52 physical runs；没有重新抽样。
- 低保真：每个候选独立冷启动到 120 秒；有 `submission.csv` 时由 pristine grader 评分。
- 沉默候选排序：直接读取 `perpair_decision.json` 中已在 run-clean 训练侧拟合、在冻结兄弟
  集上 out-of-sample 查询的预测；本脚本不训练模型。
- 成本：120 秒阶段的实测 wall time + 每个被升级候选的 v9 历史逐卡 full runtime；同时报
  当前 restart worker 和假设可恢复执行的 continuation。
- 推断：top-1 以 physical run 聚类 bootstrap 10,000 次，seed=7。
- 固定对照：random、TF-IDF、三预测器多数/全票、stdout/progress、truth-oracle 正控；不调参。

## 主要结果

| policy | top-1（run-cluster CI） | 完整升级次数 | 剪枝 | restart/full | continue/full |
|---|---:|---:|---:|---:|---:|
| artifact only | 0.5783 [0.4865, 0.6703] | 0 | 144 | 0.0586 | 0.0586 |
| all silent | 0.9600 [0.9010, 1.0000] | 144 | 0 | 0.9850 | 0.9312 |
| unanimous-3 gate | 0.9500 [0.8737, 1.0000] | 141 | 3 | 0.9826 | 0.9300 |
| top-1 random | 0.6000 [0.4706, 0.7190] | 71 | 73 | 0.5298 | 0.5033 |
| top-1 TF-IDF | 0.6600 [0.5463, 0.7623] | 71 | 73 | 0.4849 | 0.4584 |
| top-1 stdout+TF-IDF | 0.6700 [0.5521, 0.7778] | 71 | 73 | 0.5263 | 0.4998 |
| **top-2 TF-IDF** | **0.9300 [0.8621, 0.9823]** | **132** | **12** | **0.8783** | **0.8290** |
| top-2 random | 0.9200 [0.8505, 0.9770] | 132 | 12 | 0.9128 | 0.8635 |
| top-1 truth oracle | 0.9600 [0.9010, 1.0000] | 71 | 73 | 0.4951 | 0.4686 |
| top-2 truth oracle | 0.9600 [0.9010, 1.0000] | 132 | 12 | 0.8810 | 0.8317 |

TF-IDF 相对同预算 random 的增益不显著：top-2 为 **+0.0100**
[−0.0225, +0.0449]；top-1 为 +0.0600 [−0.0392, +0.1591]。所以不能把 top-2 的
成本优势归因于 critic 已经可靠学会排序。

## 机制读法

正控非常关键：truth-oracle 只升级一个沉默候选，就能在 **0.4951 restart cost** 下完全
保留 all-silent 的 0.9600 top-1。这说明这批决策本身存在约一半成本的可压缩空间；当前
失败的瓶颈是“从沉默候选里认出该升级的那个”，而不是 120 秒调度在数学上没有 headroom。

反过来，TF-IDF top-1 只有 0.6600，stdout+TF-IDF 也只有 0.6700。结合学长 Qwen3
1.7B–14B 约 0.55 的结果，当前已测 critic 远不足以兑现 oracle headroom。全票门只敢剪
3 个候选，成本仍为 0.9826，也没有实用意义。

## 裁决与下一步

1. 不启动 live 三臂长跑；当前证据没有达到“质量基本不掉且成本明显下降”的门槛。
2. 保留 top-2 TF-IDF 作为 prospective 候选，在新 sibling sets 上原样确认，不再调 k。
3. 真正值得攻的是沉默候选排序/不确定性，而不是继续扫 30/120/300 秒 cap。若独立集上
   top-2 仍保持 ≥0.92 且 restart≤0.90，再进入在线 smoke。
4. 该结果可以成为数据论文的正面机制图：真实搜索决策有很大的 oracle 可压缩空间，但
   当前廉价预测器只兑现了很小一部分；数据集能直接度量这条 cost–quality frontier。

## 完整性

- `artifact_only=0.578333`、`all_escalate=0.9600`、`restart=0.984978` 必须逐项复现，
  否则脚本 fail closed。
- 两次完整运行的 `summary.json` 与 `per_set.csv` 逐字节相同。
- 输出严格记录全部输入 SHA、脚本 SHA、git commit、Python、命令、seed。
- 本分析是在看到 120 秒覆盖率后提出，属于 exploratory；必须用新数据确认。

复现：

```bash
python phase1/critic_gated_escalation.py \
  --cap 120 --bootstrap 10000 --seed 7 \
  --out-dir phase1/critic_gated_escalation_v9
```
