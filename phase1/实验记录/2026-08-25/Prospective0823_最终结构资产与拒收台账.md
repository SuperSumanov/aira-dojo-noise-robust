# 0823 批次最终结构资产、七臂同池与拒收台账

## 一页结论

本轮有两个可以正面写进 Decision Corpus / Predictor Benchmark 论文、但不越过 outcome-blind 边界的结果：

1. 最新语料达到 339 physical runs、10,196 endpoints、2,635 canonical sibling pairs、30 tasks；七个冻结 prediction
   arms 在全部 2,635 pairs 上逐 pair 同池、方向完全一致，未来可做严格 paired comparison。
2. 218 个已观察 source archives 被精确分成 128 baseline、78 accepted、12 rejected、0 pending。post-baseline 拒收率
   为 13.33%，且 91.67% 的拒收来自任务身份元数据；所有 6 个出现拒收的竞赛也出现过 accepted archive，证明门控必须
   逐归档执行，不能使用 task 白名单。

这些是数据集与审计协议的正资产，不是 predictor accuracy 或搜索效用正结果。first-960 仍为 339/960、没有 independent
accrual closure，truth vault 保持关闭。

## 1. 0823 六归档最终裁决

| 归档 | 裁决 | 相对前一 snapshot 的增量 |
|---|---:|---:|
| plant-pathology | accepted | +4 runs / +50 endpoints / +4 pairs / +1 task |
| tensorflow-speech | accepted | +4 / +80 / +30 / +0 |
| RANZCR | accepted | +1 / +13 / +1 / +0 |
| Alaska2 | accepted | +2 / +61 / +11 / +0 |
| AI4Code | rejected | 4 journals 中任务身份基数为 3×1、1×0；整归档拒收 |
| LMSYS | rejected | 4 journals 的任务身份基数均为 0；整归档拒收 |

总增量为 +11 runs、+204 endpoints、+46 pairs、+1 task、+4 accepted transactions。最终 snapshot 为
`7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1`。

独立结构审计还得到：334/339 runs 有 finite sibling decision；30/30 tasks 有 pair；exact-code unique fraction 为
`0.9970576696743821`。21 个 exact duplicate groups（首个以后 30 endpoints）均未跨 run、未跨 task，因此不能用语料
冗余解释当前 critic 困难。

## 2. 七臂 prediction escrow 的 common support

WL 四臂（step-only、WL graph、WL+static、WL+static+TF-IDF）和 transition 三臂（child code、transition only、
child+transition）均覆盖 2,635 pairs、334 runs、30 tasks。独立无序 pair identity 复核为：

- intersection=union=2,635，IoU=1.0；
- left/right 同向 2,635，反向 0；
- canonical mapping SHA-256=`ca1b2b558671f4b77e2b70f4824a6fa4b2a8bd452023f4eb345b79cf383bef15`；
- activation 交叉表：463 双 activation 后、507 仅 WL 后、1,665 双 support-only；
- transition strict-effect-eligible=399 pairs；独立 transition receipt 对应 52 runs、17 tasks，仍不足以揭盲。

正式 matrix SHA-256=`be63fbe02c63c306bb488aa30416de7260e83e4701bdce3ed3f1d8843fd6f6b7`；focused/full=
`10/1002 passed`；formal `SHA256SUMS` 文件自身 SHA-256=`f67c1ecac1bea3cd743b9667d222a49867109e8f97e8983ea4634fe69f391a26`。
这里没有聚合 prediction value，所以 common support 不能被误写成七臂效果相同或某臂更好。

## 3. 完整 archive-disposition 审计

observer metadata 的互斥完备分区为：

| disposition | 数量 |
|---|---:|
| sealed baseline | 128 |
| accepted post-baseline | 78 |
| rejected post-baseline | 12 |
| pending | 0 |
| observed total | 218 |

因此 post-baseline settled denominator 完整为 90，拒收率为 `12/90 = 0.13333333333333333`。原因分布：

- `JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE`：9；
- `JOURNAL_TASK_IDENTITY_ABSENT_ALL_CHECKPOINTS`：2；
- `ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS`：1。

身份相关原因合计 `11/12 = 0.9166666666666666`。出现拒收的 6 个 competition——AI4Code、LMSYS、
multi-modal gesture、Plant Pathology、Russian text normalization、tweet sentiment——均也至少有一个 accepted archive
transaction。这个 mixed-disposition 事实反驳“某个任务天生不能摄取”的解释，支持 archive-level fail-closed validation。
它只是时间序观察，不证明任何 metadata 修复导致 recovery。

partition/partition-independent/ledger/ledger-independent receipt SHA-256 分别为：

- `aa161d4cf601bd323420336381f932818b4b4bbb310abedeb6951b852910f07c`；
- `ffa0974dcc09d7cf67c55f348ea601c39c84eb688c83535ff8ed5a62bf77b82e`；
- `b194b1bc88e561e77f982ae6f46d5ea7cccb745cc960c26da2661ea0ce8bad03`；
- `1281797c52007f3a6f9687ded4a785f21f0cc779bb8276e9e41e4ed057587a60`。

## 4. 当前科学判断与下一步

论文容器继续是 Decision Corpus + Predictor Benchmark + Audit Protocol。本轮使数据/协议线明显变强：真实摄取过程不仅
产生大规模 tree/pair 数据，还量化了 13.33% 的结构拒收与 archive-level 非平稳性；七臂同池又消除了未来方法比较的
pair-pool confound。

方法线仍没有新的 confirmatory effect。现有最强探索性假设仍是“global value pretraining → local decision transfer”：
学长旧结果的 global value 容量曲线随 0.6B→14B 上升，而 direct local pairwise 约在 0.55 附近，说明直接扩大 local-only
模型不是当前最优赌注。clean confirmation 必须使用 future exact producer stratum、train-run dev 选 checkpoint 和全新未触碰
test；在明确配置矩阵与 GPU·时批准前不启动。

近期执行顺序保持：继续 append-only intake；让 transition/WL escrow 随新 snapshot 前滚；推动 producer 在归档前写 config
sidecar v2；等待 first-960 + independent closure，再按冻结协议一次性打开 truth。target-300 支持 cohort 继续独立收集，绝不与
first-960 混池。

## 5. 失败与边界记录

- AI4 audit v1 的 credential scan 误把自身输出纳入扫描；v2 使用新根重跑。
- 四归档 batch audit v1 缺 repo cwd/PYTHONPATH；修正后重跑。
- 629 prepush v1 对 incremental bundle 错误要求不存在的 `HEAD` ref；v2 绑定精确发布分支。
- 上述失败均发生在科学结论前并完整保留，没有用失败目录支持结论。
- 本报告没有读取 label、grade、outcome、winner orientation 或 prediction aggregate；GPU/API/base-LLM update 均为 0。
