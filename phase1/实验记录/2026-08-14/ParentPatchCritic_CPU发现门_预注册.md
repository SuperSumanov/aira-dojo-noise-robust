# ParentPatchCritic sparse CPU discovery gate（outcome 前预注册，V3a amendment）

日期：2026-08-14；seed：887。本文写于任何新 patch 模型 accuracy 产生之前。V1 因 parent 缺失在
vectorization 前 ABORT；V2 因逐折重复拟合 TF-IDF 超过 10 分钟 CPU 上限而停止，二者都没有科学结果。
本次 V3 是新协议，不能继承 V1/V2 的 outcome 口径。

### V3a outcome 前修订（2026-08-14）

V3 首次真实启动在约 12 秒时因 `runs >=300` 完整性检查 fail closed：只完成了 train 的读取与
结构审计，尚未进入向量化、IDF、模型拟合或任何 accuracy 计算，`frozen_read=false`，且旧实验目录
原样保留为 `INVALID`。结构审计随后确认：原始 b0 train 是 4,263 对 / 333 runs，但仅保留 parent
card 存在的 common support 后是 3,948 对 / **280 runs** / 23 tasks，dominant task 21.88%。先前预检
把 raw-run count 错写成了 common-support run count。

在没有预测 outcome 可看的前提下，V3a 唯一修订是把纯样本量完整性下限由 `runs >=300` 改为
`runs >=250`；实际 280 runs 仍高于下限 30 runs。表示、fold、seed、classifier、全部效果阈值、
CI、任务一致性门、冻结 success 门和 15 分钟 cap 均不变。新提交、新 append-only 目录运行；V3 的
失败目录不得覆盖或删除。

## GCCV

**Goal**：在真实 b0 sibling decision 上，局部 `parent→child` line patch 是否比独立 whole child code
含有更强的执行前排序信号？这只裁决 sparse 表示，不裁决后续 frozen-embedding 非线性模型。

**Context**：v11（16,012 cards / 667 physical runs / 25 tasks）；训练文件
`v11_decision/decision_train_v11_b0.jsonl` 为 4,263 对 / 333 runs / 23 tasks。结构预检已知 parent
在 corpus 中的覆盖为 3,948/4,263；无 oriented duplicate、reverse conflict 或跨 run sibling。
冻结文件 1,498 对只允许 discovery 全过后读取预测结果。

**Constraints / fairness contract**：

- 两臂只改变表示：`absolute`=child code；`patch`=operator + 相对共同 parent 的 ADD/DEL line diff；
- 同一个 deterministic hash-TFIDF、同一个 SGD logistic head、同一 fold/seed/样本权重；
- 5-fold GroupKFold 按 physical run；IDF 每折只 fit train-fold candidates；hashing 无词表拟合；
- 每个 parent 的总训练权重相同；正负镜像样本各占一半；不使用 label grade、stdout、runtime、
  self-report、frozen outcome 或 task-specific threshold；
- code/patch 最多各 20,000 chars；char_wb 3--5 grams；`2^18` hashing dimensions；
- 仅 parent card 存在的 common support；不插补。train parent coverage 必须 ≥0.90；
- b1/b2 不参与 unlock：历史 future label 受行为策略/continuation allocation 混杂，另行建 censored protocol；
- 单进程 CPU，0 GPU、0 API；墙钟 cap 15 分钟；超时记 `ENGINEERING_TIMEOUT`，不是方法负面。

**Verification**：

- 输入 SHA、git commit、命令、Python/numpy/scipy/sklearn 版本、seed、阶段耗时写入 `summary.json`；
- oracle orientation 必须 1.0；随机 baseline 报告但不作门；
- 逐 pair OOF margin/hit 写 CSV；报告 pair accuracy、parent-macro top-1、run/task macro、双聚类 CI、
  每任务差异和 coverage；
- parent top-1 只在 pair graph 完整（`n(n-1)/2` 条边）的 parent 上计算；不完整集合只参与 pair
  accuracy，并单列完整 parent coverage，禁止把缺边默认为输赢；
- frozen 若解锁，必须检查 train/frozen endpoint 与 physical-run 零交集，并用训练全集一次拟合；
- 独立 verifier 从逐 pair CSV 重算主指标与 gate。

## Discovery unlock（必须全部满足）

1. 全部完整性门通过；train parent coverage ≥0.90，common-support runs ≥250，tasks ≥20，
   dominant task ≤0.25；
2. patch OOF pair accuracy ≥0.54；
3. `patch - absolute` OOF pair accuracy ≥+0.020；
4. parent-macro top-1 差 ≥+0.030；
5. pair 差的 run-macro 与 task-macro bootstrap 95% CI 下界都 >0；
6. 至少 10 个 n≥20 的任务，且其中 patch 差非负的比例 ≥0.60；
7. oracle=1.0、无 NaN/inf、两臂覆盖逐行完全相同、总墙钟未超 cap。

任一失败：脚本不得打开 frozen pair 文件，裁决 `NO_UNLOCK`。不能 outcome 后改阈值重跑。

## Frozen success（仅 unlock 后计算，必须全部满足才升级 GPU embedding）

1. frozen parent coverage ≥0.90、train/frozen physical-run 与 endpoint 交集均为 0；
2. patch pair accuracy ≥0.56；
3. pair accuracy 差 ≥+0.030；parent-macro top-1 差 ≥+0.040；
4. pair 差的 run/task macro bootstrap 95% CI 下界均 >0；
5. n≥10 的 supported tasks 中差非负比例 ≥0.60。

全过=`SPARSE_PATCH_GREEN`，授权设计 frozen-embedding 非线性 head 和 prospective fixed-budget A/B；
否则=`SPARSE_PATCH_NOT_GREEN`，只关闭当前 sparse line-diff 实现。无论结果如何，不允许用同一 frozen
文件调 hashing dimension、char range、alpha、截断、diff 格式或阈值。

## 资源矩阵与 ETA

- discovery：5 folds × 2 representations = 10 个 CPU fits；
- frozen（条件式）：2 个 full-train CPU fits；
- 总计最多 12 fits，1 CPU process，0 GPU·h，0 API 费用；目标 4--8 分钟，硬 cap 15 分钟。
