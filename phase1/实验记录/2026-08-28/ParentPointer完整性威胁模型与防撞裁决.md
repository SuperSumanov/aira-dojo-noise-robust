# Parent pointer 完整性威胁模型与防撞裁决

日期：2026-08-28。性质：基于已披露 snapshot 887 development aggregate 的诚实重解释与公开文献防撞；不修改
Target-522 已冻结 protocol，不产生新的前瞻结果。

## 1. 裁决

不能把当前结果包装成新的 lineage inference 算法。真正可守的正资产是一个面向 MLE Decision Corpus 发布的三层
完整性栈：

1. **provenance 层**：append-only intake、物理 run、snapshot/manifest hash 与 closure receipt；
2. **graph 层**：parent 必须同 task、同 physical run、无环，并满足 preceding depth；
3. **content 层**：对通过前两层、且 fingerprint 可用的最难同层替换，只有 recorded parent 是 identifier-erased
   Jaccard unique top 才接受，否则拒绝或 abstain。

价值在于：语料中的 parent pointer 不只依赖 producer 自报，而是由独立来源的结构元数据与代码内容交叉认证；同时
明确保留 false alarm、随机 corruption 与 adversarial corruption 三种不同风险口径。这是 dataset-integrity artifact，
不是 predictor effect、search utility 或通用 lineage 方法首创。

## 2. 错误 pointer 的穷尽分类

对任意 observed child 与 proposed parent，validator 依次分类：

1. proposed parent 不在 observed fragment：标成 fragment boundary / unverifiable，不当作已认证 pointer；
2. task 或 physical run 不同：graph 层直接拒绝；
3. parent depth 不是 child depth 减一：graph 层直接拒绝；
4. 任一 endpoint 无固定 fingerprint：content 层 abstain；
5. 同 run、exact preceding depth 且 fingerprint 有效：与该 child 的完整同层候选集比较，只有 unique top 接受，tie
   也拒绝。

因此 content 实验针对的是结构规则无法排除的 hardest residual corruption，不把明显的跨 run / 错 depth 错误混入分母
制造漂亮数字。Target-522 hard gate 又要求 fingerprint coverage≥`99/100`，避免大量 abstention 被隐藏。

## 3. development 数字的三种分母

固定 887 development 中，exact-depth ambiguous population 有 9,739 个 child，99,039 个 wrong alternatives：

| 口径 | exact 值 | decimal | 合法解释 |
|---|---:|---:|---|
| 真 pointer unique-top acceptance | `9196/9739` | `0.94424478899270969` | 正确 pointer 的 child-level sensitivity |
| 至少存在一个可误收 wrong candidate 的 child | `543/9739` | `0.055755211007290278` | 知道相似度后可定向挑选 wrong candidate 的 adversarial vulnerability |
| 所有 wrong alternatives 的 micro FPR | `543/99039=181/33013` | `0.0054826886378093482` | 对全部 child×wrong-candidate proposal 做 micro average |
| 每 child 均匀随机替换一个 wrong candidate | `781932207218999183/74583226893151856880` | `0.010484022209701351` | 先等权 child、再在其 wrong candidates 中均匀抽样的期望 |

本开发人口 `9739-9196=543`，且 wrong unique-top child 也是 543，所以 tie-only failure=`0`。这只是已见 population 的
描述，不冻结“未来也无 ties”的假设。正式写作必须至少同时给 child-level sensitivity、adversarial vulnerability 与
all-alternative micro FPR；不得只展示 0.55%。

Target-522 强门中的 true recovery≥`9/10` 已把未来 child-level 总失败率压在 10% 以内，wrong-alternative micro
FPR≤`1/50` 则额外约束大候选集加权后的误收。两门回答不同问题，互不替代；现有 protocol 无需结果前改门。

## 4. 直接防撞

- [Towards Automatic Software Lineage Inference](https://www.usenix.org/conference/usenixsecurity13/technical-sessions/papers/jang)
  已在 1,777 个 goodware revisions 与 114 个 known-lineage malware 上恢复 straight-line/DAG software lineage，并
  评价 graph-arc edit、partial order 等图质量；“代码相似性恢复 lineage”不是我方首创。
- [Neural Lineage](https://arxiv.org/abs/2406.11129) 已提出 similarity-based 与 learned parent-model detection；
  [modelDNA](https://arxiv.org/abs/2607.10617) 又把 weight fingerprint 做成 calibrated parent verification 和
  merge decomposition。一般 fingerprint parentage verification 已被覆盖。
- [Tracing the Roots](https://arxiv.org/abs/2604.10480) 已自动重建 post-training dataset evolutionary graph；
  “数据 lineage 图”也不能作为泛化 novelty。
- code-clone genealogy 与文件 origin analysis 更早已用文本/clone similarity 补软件历史。它们进一步要求我方把方法
  novelty 收紧到零，而不是声称 agent 场景让旧问题自动变新。

尚未看到直接相同的工作是：对自然产生的 MLE-agent search physical parent，在 outcome-blind、time-forward、完整
same-run preceding-depth candidate set 上，以 exact wrong-pointer controls 做 release certificate，并与 frozen predictor
benchmark、run-clean split 和 closure audit 同时发布。该判断仍是差异化组合，不写 `first/only`。

## 5. 对论文和下一步的约束

若 Target-522 最强门通过，正文可把 parent integrity 写成：记录指针经过 provenance、graph invariant 与 content
concordance 三层独立证据；对最难同层替换，同时报告真 pointer sensitivity、child-level adversarial vulnerability、
uniform-child corruption risk 与 wrong-alternative micro FPR。

若只过 content、不满足 hierarchy complementarity，则只能说内容与 recorded pointer 一致，不能说三层互补；若 strong
gate 失败，则保留开发信号与失败回执，不换表示、不换 threshold、不用累计 population rescue。无论结果如何，都不从
parent integrity 外推 predictor accuracy、semantic correctness、causal ancestry 或 search utility。
