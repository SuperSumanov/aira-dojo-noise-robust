# G-reuse 结构结果到模型效果：冻结执行决策

日期：2026-09-05。状态：结果盲的执行收敛；**不授权 GPU、API、model fit 或评测集访问**。
本文不覆盖 `global_local_calibration_candidate_protocol_v2.json` 或历史开发 v1；它定义同 producer
来源门通过后，G-reuse successor 应如何避免臂膨胀和结果后挑预算。

## 1. 要验证的唯一主效应

在同一批已经执行并由同一 pristine evaluator 评分的 MLE 程序上，增加 exact-stratum global 比较，随后用
local sibling 比较适配，是否在固定训练 token 上提高 run-clean local decision accuracy？

这叫执行标签复用效应，不叫新标签数增长。由同一标量执行记录导出的多条 pair 是相关约束；样本量与不确定性
仍以 physical run/task 聚类，不把 pair 行当独立观测。

## 2. Core stage：五臂，不把 spectral 偷换成主方法

来源门、G0 成本门和总 GPU·h 批准通过后，core stage 固定 seeds 6/7/8：

| arm | 作用 |
|---|---|
| `L1` | local 单遍，诊断重复训练/过拟合；不是同预算 headline |
| `Lbudget` | local-only 同 valid-token cap 主基线 |
| `G-reuse-budget` | exact-stratum reuse-global only，同 cap 的零样本 local 迁移基线 |
| `G-reuse-to-L-full` | 完整合格 reuse-global 一遍，再完整 local 一遍；主候选 |
| `Ghash-reuse-to-L-full` | 与上一臂输入、顺序、token、更新、LR、保存点相同，只替换 global 方向 |

这仍是 15 个拟议 fit，不是既有历史 9,392-row `G_to_L` 的改名。权威包到来后必须从冻结资格规则重新构造；
不得直接使用当前 3,058/2,745/790 的身份或为复现这些数而修改 producer。`full` 表示新包中全部合格的
record-consistent reuse edges，不保证仍等于 2,745。

core 成功门继承旧协议且不放宽：`G-reuse-to-L-full - Lbudget >= 0.02`；task-clustered paired 95% CI
下界严格大于 0；三个 seed 方向均正；相对 `G-reuse-budget` 的 task-CI 下界为正；只有这些通过后才检验
相对 hash control；leave-one-task-out 不反转，最大单任务正确差贡献不超过 0.35。checkpoint 必须全部锁定后
一次打开 untouched evaluation population。

## 3. Cost stage：只加一个 50% spectral challenger

只有 core deployment gate 通过，才允许复用 core 的 full checkpoint/结果并新增 3 个 fit：
`G-reuse-to-L-spectral50`，seeds 6/7/8。50% 是 0L21 在完整 frontier 之前首次冻结的中点，避免从
25%/50%/75% 曲线中结果后挑选最好点；75% 即使结构 capture 更高也不能替代它。

权威新包上先独立重算 task-wise minimum-token basis；再从 basis 开始，以每任务
`floor((full-basis)/2)` 的额外 valid-token 上限，按 15 位量化的 `log1p(R_eff)/token` 贪心选边。
选择只读 train 结构和 token 成本，不读 dev/frozen 结果；selected identities 保持私有，manifest 只发布 hash/count。

Cost stage 同时满足以下门才称 Pareto challenger：

1. G-stage valid-token 相对 full 至少减少 25%，总 `G+L` valid-token 至少减少 10%；
2. `spectral50 - full` 的 task-clustered paired 95% CI 下界严格大于 `-0.01`；
3. 三个 seed 的点差均不低于 `-0.02`；
4. leave-one-task-out 的聚合点差均不低于 `-0.01`，且最大单任务绝对差贡献不超过 0.35；
5. checkpoint 完整、无 NaN/OOM/访问违规，成本与精度按臂逐项报告。

`-0.01` 是 core 最小部署增益 0.02 的一半，事前固定为换取至少 10% 总训练 token 节省所能接受的最大退化，
不是结果后设定。若不满足，只报告结构压缩，不称模型效果 Pareto；不再试 25%/75% 救回。

仅作旧历史输入的资源可行性核算，50% spectral 的 G-stage 为 `5773896 + 6836387 = 12610283`
valid tokens，相对 full `19601875` 减少 `0.3566797564008545`；加同一 L `32187742` 后总量为
`44798025`，相对 full 总量 `51789617` 减少 `0.13499987845053962`，能穿过上述两个成本门。
这些数不锁定新包预算；来源重建后必须在读取模型效果前重算并重新 fail-closed 检查。

## 4. 为什么不是算法 novelty

- [Osting et al., JMLR 2014](https://www.jmlr.org/papers/v15/osting14a.html) 已把比较数据收集写成最大 Fisher
  information 的图实验设计，并展示少量精心选择的比较可提高 informativeness；
- [Shah et al., JMLR 2016](https://www.jmlr.org/papers/v17/15-189.html) 给出依赖 comparison-graph
  Laplacian spectrum 的 BTL/Thurstone sharp minimax bounds；
- [Hendrickx et al., ICML 2019](https://proceedings.mlr.press/v97/hendrickx19a.html) 直接把质量估计误差与
  graph resistance 联系起来；
- [Guo et al., SDM 2019](https://ece.northeastern.edu/fac-ece/ioannidis/static/pdf/2019/C_Guo_Accelerated_SDM_Submit_2019.pdf)
  已研究 pairwise D-optimal greedy selection；
- [Mikhailiuk et al., 2020](https://arxiv.org/abs/2004.05691) 已用 expected information gain 和逆信息增益
  minimum spanning tree 做主动 pair batch 选择。

因此不得声称首次 D-opt pair selection、首次有效电阻选边、首次 minimum spanning basis 或新的通用 ranking
方法。可争取的贡献是 Decision Corpus 的执行标签成本定义、同执行记录监督关系重组、run-clean 评测、严格来源/
泄漏审计，以及在真实 MLE critic 上验证信息—训练成本 Pareto 是否成立。

## 5. 解锁清单

开始任何 fit 前仍需同时满足：

1. 同 producer 版本的历史开发 Cards/G/L/split/source，含完整 SHA/LFS OID、producer commit/命令；
2. whole-experiment train/dev/frozen，pair/card/physical-run 零交集，exact generator/config stratum；
3. G0 真实双卡 wall-time/peak-memory/checkpoint receipt，并据此固定 pivot checkpoint、2/4 卡形状和总 GPU·h；
4. core 五臂机器协议和物化 manifest 的 producer A/B、独立 verifier、credential/访问/哈希门；
5. 用户对精确矩阵与总 GPU·时另行批准。

任一项缺失都 fail-closed；当前结构正结果不能替代这些门。

## 6. 结果前解释图：失败也不临时换故事

以下只是既定五臂比较的解释顺序，不新增指标、门或 fit，也不能 rescue 第 2 节的 primary：

1. `G-reuse-to-L-full > Lbudget`且`> G-reuse-budget`才支持“global复用后local适配”的组合效应；
   只胜其中一个不得缩写成主方法成功。
2. 若truth-global与hash-global均相似地胜`Lbudget`，只支持更多输入/更多更新的正则效应，
   不支持方向性执行标签有信息。
3. 若`G-reuse-budget`有利而`G-reuse-to-L-full`被local阶段抹平，当前sequential protocol仍判失败。
   只能把“遗忘/目标冲突”作为下一个全新、结果前冻结协议的候选，不得本次改成mixing救回。
4. 若`L1 > Lbudget`，表明local重复至同token cap可能过拟合；因此full除了胜`Lbudget`，还必须按
   已冻结层级胜`L1`，否则不得把少做local重复误写成global transfer。
5. 若点差为正但任务CI、LOTO或单任务35%门失败，只报效应异质/证据不足；不增seed、
   删任务、改权重或改切分。

这个解释图的作用是把后续方法决策与本次确认结论分开；它不提高当前功效，也不改变 2pp 主门。
