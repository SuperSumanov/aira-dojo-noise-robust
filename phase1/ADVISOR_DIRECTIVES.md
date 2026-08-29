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
→ 旧量化需要纠正：`561077ms / 4.8ms = 116891.041666666671517`，不是“七百万倍”；后续
  `suite_v9.csv` 的单次计时为 `437888.154ms / 4.245ms = 103153.864310954057146`，但两者都没有
  多次重复与硬件绑定。正式引用等待 2026-08-20 的 DeploymentCostAttestation；不得把旧成本比和旧 accuracy
  拼成联合方法收益。
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
- **语料 LFS 发布契约**：Git LFS 只放一次写入的不可变分批文件，每批只上传一次；版本由该版本固定的 manifest
  和 `rebuild_corpus.sh` 组合，pull 后必须以行数与 SHA 验证逐字节重建。不要为每次 v4/v5/vN 重建反复上传一份
  merged corpus。2026-08-14 审计同时确认：该契约直到 `da27852` 才实际落地，legacy v4/v5 的提交不含后来引用的
  LFS batch；用现存 batch 重放分别为 8,579/9,433 行而非历史 8,607/9,323。因此旧版本在找回原始 payload/hash
  前必须标注不可逐字节复现，不能让正确的设计描述覆盖当前 provenance 缺口。
  2026-08-14 后续落实：v6–v11 已用 append-only registry、prefix lock、release-specific protocol 与
  输出 rows/bytes/SHA 三元门逐字节复核；v10/v11 必须分开冻结 taxonomy。新增 batch 只能 append 新记录并新增
  version descriptor，严禁改旧记录或只凭行数宣布复现。直接证据见
  `phase1/实验记录/2026-08-14/CorpusLFS_版本化逐字节重建_裁决.md`。
- **配置审计提醒**：学长最新 `2cb6f0c` 把 best metric 改为 `eval_pair_accuracy` 却保留
  `greater_is_better=False`。逐 checkpoint 日志不受影响，但 best-only 保存方向会反；修复后先用人为递增 metric
  做最小保存测试。旧 0812 结果使用较早的 eval-loss 配置，不能把旧 0.55 事后归因于这个新 bug。

## H. 2026-08-15—25 新增意见、结果与边界

- **方法应由 agent 自然学出，而不是固定工程规则**：学长认可早期 submission 方向的现象，但指出，如果能提供
  更灵活的 harness，让 agent 根据过去经验通过训练或其他方式自然发展出该能力，会更有趣；当前在 AIRA 外挂
  early-submission 检测和处理逻辑，容易被批评为 heuristic/engineering。
  → 规则：固定检测器可作机制 smoke 或系统基线，不能直接冒充算法创新。若恢复类似方向，贡献必须落在可学习、
  可泛化的 controller/evaluator，以及固定预算端到端 utility；不得把旧 HCE/多保真重新命名后复活。
- **16,384-context 训练的诚实结果**：学长报告该轮仍接近随机，效果太差，不准备进入下一步测试，并删除 checkpoint
  节省空间。
  → 规则：这是该具体数据/协议/run 的负结果，不推出所有长上下文都无效；但 checkpoint 已不可追溯，不能事后补测或
  把聊天结论升级为正式证据。未来贵训练必须保存 config、日志、停止原因、选点规则与必要 checkpoint receipt。
- **experiment-level split 出现更强 scaling 迹象**：学长随后在 `0820` outcomes 中补齐两 seed value-pair 结果，
  Qwen3 0.6B/1.7B/4B/8B final mean 为 58.64%/60.67%/62.01%/64.68%，8B 比同数据
  TF-IDF 61.18% 高 3.50 pp；decision zero-shot transfer 为 56.25%/56.25%/59.06%/59.38%，
  8B 仍低于 TF-IDF 59.90%。
  → 这是当前最强的探索性 capacity signal，覆盖更早“1.5B—8B 都在 0.55、规模不是杠杆”的宽解释；但旧实验含
  cross-exact-config mixing、shared endpoints、周期性 outer-test eval、非正常结束和 checkpoint 方向/version 问题，
  不能称确认。正式确认只允许 future exact-stratum、train-run-disjoint dev 选点和全新 immutable frozen cohort。
- **语料生产与方法分工**：学长仍负责持续生产 physical runs 和训练/规模侧；我方负责 run-clean 数据、真实 sibling
  estimand、冻结评测、成本/噪声/覆盖审计和独立复核。结构依赖图谱的分析与 benchmark 主张来自我方，原始前瞻
  语料生产来自学长；scaling 信号来自学长，写作时必须分开归因。
- **最新分支资产不是结果**：`dojo-reproduce@2b22f31...` 新增 RL-judger messages、context 工具和
  Qwen2.5 0.5B/1.5B/3B/7B mixed decision/value full-FT 脚本，但尚无新 outcome 文档。train/test 参数
  指向同一 runsplit 文件，使用前必须核对内部 split、endpoint/run/experiment 零交集、outer-test 选点和停止收据。

## I. 2026-08-28—29 最新 outcome：从 proxy 上限转向可审计的 MLE label efficiency

权威来源为学长 `dojo-reproduce@f534114e60658043c07f7a15d6440492caffc8ad` 的
`src/mle_critic/docs/outcomes/0828/MIXED_PAIRWISE_REWARD_AND_RL_EXPERIMENTS.md`；后续数据/上下文修复 branch head
为 `30b396323f28064040bb0bdf9cccb198d676dd27`。该 outcome 的 Git blob=`7f691d9b6fa3d971bf889738fa8661694b6b0051`、
SHA-256=`17317a2d239cb862ec16d57aa0a2fa168f2c1a6cd841117950d8ee8127129ad6`。原文凭据行只经远端内存脱敏后阅读，
不得把其中任何 token、带权链接或原始 reasoning 放入本文件、日志或 Git。

- **proxy 与最终目标分开**：学长判断现有 value/decision pair proxy 的实际可见上限大约落在 60%—70% 区间，
  下一步重点应是它能否转化为固定预算下的 MLE end-to-end 改善。规则：pair accuracy、loss、gap 曲线和 scaling
  只能作探索证据；最终主张仍须落在真实搜索成本与任务成绩，不能把 proxy 百分点直接写成 agent 提升。
- **混合数据 scaling 仍不稳定**：Qwen3 Base 的模型规模趋势只在 seed 7 明显，seed 6 未复现；instruction 模型和
  Qwen2.5 对照也交叉。规则：不得把单 seed 最佳 checkpoint 写成规模律；必须同时审计 test composition、共享 endpoint、
  task/experiment 比例、标签噪声、优化配置与 checkpoint 选点。
- **RL 不能自动救回 critic**：当前 RL judger 在 decision test 上没有稳定随训练步提升，在 value test 上约 0.59，且与
  BT 8B 约 0.6411 不是严格 matched 比较。规则：不宣称 RL 自然带来 scaling；若未来比较，先固定 rollout、奖励、训练预算、
  prompt 和资源 stratum，并保留完整停止与 checkpoint receipt。
- **RL prompt 有真实资源错配**：现脚本每 task 只取第一份 step-1 journal 的 hardware/time constraints，可能与后续 pair
  两端实际条件不同。规则：任何 evaluator/RL prompt 必须按 pair/Card 的真实 `(task, client, hardware, time_limit,
  execution_timeout)` 生成并校验；不得用 task-level 第一条 journal 兜底。
- **混合采样必须保留 provenance**：8:1:1 是采样权重，不是最终比例，旧输出没有 `source_dataset`，无法恢复每条来源。
  下一版必须写入来源、原始 experiment/run 与 draft/improve relation，并在 test 中固定各类数量。
- **新的方法想法**：MLE 介于无标签 self-improvement 与充足监督之间——execution label 昂贵且稀少，可能在固定 generator
  下借助 verifier 反馈提高真实标签生产效率。广义 generator+verifier/self-evolution 已有大量先例，不能当作首次；本项目
  可守的窄创新是：昂贵、延迟、任务异质的真实 MLE execution labels 下，结合 run-clean corpus、成本账、relation/lineage
  certificate 与未触碰 confirmation，验证 verifier 是否提高 label allocation efficiency。
- **学长点名的 API 诊断**：从经过审计的 reward/decision pairs 选小而平衡的 panel，对 DeepSeek/GLM/Qwen flash 与免费
  Nemotron 做完整 task/resource/code、双方向评估；禁止截断输入输出，保留远端私有 reasoning，并先看 parse、顺序稳定性、
  隐私路由与成本，再看 accuracy。用户本轮已转达专用 OpenRouter 凭据与学长的 50 USD 账户限额；项目内 smoke 仍锁死
  64 calls、调度停止 2 USD，且凭据只能由远端 mode-0600 `.env` 注入。
- **generator 微调提案与项目硬边界冲突**：学长建议用 2—3 个简单任务采 API 数据微调小 Qwen generator 做 demo；当前
  项目明确禁止更新 agent 底座，因此未经用户明确修改边界不得启动。允许的替代是固定 generator，只训练/使用独立
  verifier 或轻量选择器，并在相同 execution 预算下测 label efficiency。
- **RL trajectory 审计只收脱敏导出**：outcome 的 W&B 链接含访问凭据，不能点击或自动使用。必须由学长先轮换凭据并导出
  脱敏 prompt/final answer/reward/metadata/run receipt；隐藏 chain-of-thought 不进入 Git，也不作为论文可复核证据。
