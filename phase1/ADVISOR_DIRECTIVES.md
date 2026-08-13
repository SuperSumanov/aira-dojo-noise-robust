---
name: advisor-directives
description: 学长(advisor)历次意见的完整清单——每次做实验/下结论前必须逐条对照；含已生效的框架纠正(自报分不免费)和 NAS/NAS-Bench 模板
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b02aa9ce-c8e5-440f-9f4f-b8040fa6c31f
  modified: 2026-08-09T20:00:54.590Z
---

**用法:每次设计实验、下结论、写汇报前,逐条过一遍这个清单。我已经因为漏掉其中一条(「免费」)白做两天。**

## A. 已生效的框架纠正(最重要,曾导致我两天的评估全错)

**A1「为什么说执行反馈和自报分是免费的?执行一次任务的耗时肯定远长于 critic 预测一次。我们本来的目标就是用 critic 来节省成本加速搜索。」**(2026-08-09)
→ 自报分只在节点**执行后**存在;critic 的价值在执行**前**。拿事后信号当基线否定事前工具是错的。
→ 量化:自报分 query 成本 = 一次执行 = 中位 **561 秒**;tfidf 预测器 **4.8ms**。七百万倍差换 13 个准确率点。
→ **规则:任何预测器对照表必须有 query-cost 一列,并标注自报分为「事后信号」。**

**A2「critic 的思路要做得更合理,必须参考和讨论 MCTS+neural network / NAS 的工作。」**(2026-08-10)
→ 已落地为论文框架。NAS 同构:训网络太贵→性能预测器;执行程序太贵→critic。
→ [How Powerful are Performance Predictors in NAS?](https://arxiv.org/abs/2104.01177) NeurIPS'21:31 个预测器,**init time 与 query time 分开计价**(即 A1 的解法),指标=秩相关+搜索加速比。
→ **[NAS-Bench-Suite-Zero](https://arxiv.org/abs/2210.03230) NeurIPS D&B'22 = 我们该照抄的形态**:13 代理×28 任务,头条是负面的(#params/FLOPs 打平所有零成本代理),但形态是**基准发布+系统分析**;另挖正面=代理互补,合并提升 42%。
→ NAS-Bench-201 仅 15,625 架构即顶会;我们 10,755 完整程序×22 任务量级相当。
→ **规则:我们缺的是方法广度(他们 13 个,我们 1 个),不是更强的单模型。**

## B. 关于写作时机与论文形态

- **「现在开始转写作有点夸张了,还有半年才到 ACL ddl,NIPS D&B 甚至还有接近一年。这时间够我们把方法多迭代几轮。」**(2026-08-09)
- **「目前的实验感觉还能打磨,不建议用负结果写论文。」**(2026-08-09)
- 更早:**按投 ACL / ICML 的标准来**(不是 findings/workshop 水平)。
→ **规则:不要再提议"转写作";负面结论在没穷尽打磨前不能当定稿。**

## C. 算力与模型配置(他的实测,别用我的先验覆盖)

- **pro6000/H200 随时可用,8B + 16384 ctx 绰绰有余**;但他要**先在 pro6000 上验证加大模型和 ctx 确有收益**再投入。
- **「0.6B、1.7B 和 4B 的表现并没有非常大的分别」**(他周五 pairwise 实测)→ 与我们 1.5B vs 0.5B(0.573/0.538)一致。**规模不是杠杆。**
- **「试一下多卡并行 + 0.5B 模型来提高 ctx length,没必要一直用 1.5B。」**
- 他会**在我们新的干净数据上训**,验长 ctx / 大模型收益。
- 我方实测支撑:2048 时 **84% 程序被截断、只看到 63% token**;8192 可达 99% 覆盖;丢失的主要是特征工程(`merge(` 仅 25% 可见)。

## D. 采集协议(他执行)

- 0805 起改**顺序扩张所有叶子**(去掉 MCTS 影响)+ 压时限压 children,产更多更深的树。
- 我方必须回传的约束:**children ≥ 2**(压到 1 则同父兄弟决策集为空,整类分析做不了);**卡片带 run id**(现只能靠批文件连续性反推)。
- 他的分工:**重点跑节点少的任务**;我方在节点充足的任务上测 in-task oracle。
- 我方新增建议(基于功效分析):**冲独立 run 数而非卡片数**,多 seed 浅树 > 少 seed 深树;目标约 2,000 run(现 515)。

## E. 待尝试(他点名,尚未做)

- **「用 codex + git 替换 MCTS 非常值得尝试。」** → 换生成器架构,工程量大,我判断为下一篇;**未经他同意不要擅自降级为"不做"**。
- **「也可以试试再训一把。」**
- **「如果现有卡训不出更好结果,想想还能做什么,或调研其他相关领域怎么做。」** → 这是 A2 的来源,已见效,应继续用同样方式找模板。

## F. 他的 H200 早期结果(引用时注意口径)

checkpoint-180(仅约 6% 训练量)accuracy **0.8143** / macro 0.7956,「加长 context 训出来效果一般」。
→ **正确读法:6% 训练量就追平我方全量截断训练的 0.8200,说明长 ctx 远没跑到头**,不是"没优势"。
→ 但那是**旧的泄漏切分**,不能与 run 级干净的 0.6493 直接比;干净 pairs 已推送给他(`ab580f3`)。

相关:[[decision-point-inversion]] [[fragment-run-leakage]] [[preflight-checklist]] [[top-venue-bar]]

## G. 2026-08-11—13 新增意见与已交付结果

- **数据生产节奏**：「现在理想情况下每天能出 60 个 run 左右，打算按这个速度再跑两三周，之后先停数据生产，
  把精力集中在方法。」
  → 规则：新数据优先提高独立 physical run、task balance 与真实 sibling pair yield；不能用 cards 数代替决策支持数。
  任何前瞻确认必须按机制冻结时间筛 physical run，晚入库的旧 run 不能冒充 prospective。
- **训练结果交付位置**：学长会把结果放在其 branch 的
  `src/mle_critic/docs/outcomes`。每次设计新实验前先只读检查该目录、commit 与对应数据 LFS object，不能只看聊天摘要。
- **约 4k decision 数据的规模实验**：学长报告 Qwen3 1.7B—14B 在测试上最好约 0.55 浮动。正式 0812 文档目前可验证：
  Qwen3 1.7B/4B/8B final 为 54.80%/55.41%/55.18%，best 为 55.33%/58.79%/56.64%；Qwen2.5
  1.5B/3B/7B final 为 55.03%/52.80%/54.57%。没有模型规模单调性，14B 尚未完成，且缺少 multi-seed
  显著性；只能说“现有 1.5B—8B 证据不支持容量是主杠杆”，不能说规模永远无效。
- **数据文件区分**：约 4k 的 `decision_pairs_runsplit.jsonl` 是较早的、用于训练/开发的 run-split pair pool；
  `decision_frozen_v11_b0/b1/b2` 是从 v11 在固定规则下重建、全部 `intask_split=test` 的论文冻结评测集，
  分别 1,498/323/265 个 finite pairs。前者的 train/test 与后者不能按文件名假定等价，必须做 endpoint、parent、
  physical-run 与 SHA 对照；冻结 test 绝不进入训练。
- **共享可访问性**：学长无法访问我方 big-data storage 时，README 引用的必要小型 manifest/eval/result 必须随 Git
  或正确的 Git LFS object 推送；大型 raw corpus 保留可重建 manifest、SHA、远端共享路径。不能写一个学长打不开的路径
  就声称已交付数据。
- **配置审计提醒**：学长最新 `2cb6f0c` 把 best metric 改为 `eval_pair_accuracy` 却保留
  `greater_is_better=False`。逐 checkpoint 日志不受影响，但 best-only 保存方向会反；修复后先用人为递增 metric
  做最小保存测试。旧 0812 结果使用较早的 eval-loss 配置，不能把旧 0.55 事后归因于这个新 bug。
