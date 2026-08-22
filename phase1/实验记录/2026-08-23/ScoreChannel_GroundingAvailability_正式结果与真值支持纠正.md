# Score-channel：grounding availability 正式结果与真值支持纠正

日期：2026-08-23。裁决：旧 primary 的形式化 `KILL` 保留，但科学解释从“未发现 external 优势”纠正为
`DISCRIMINATIVE_COMMON_SUPPORT_ZERO`；本 cohort 不能比较两通道的排序能力。

## 1. 为什么做这次 post-hoc 分解

直接竞品 [arXiv:2607.25152](https://arxiv.org/abs/2607.25152) 已关闭 broad grounding-gap 首创，旧 primary 又只有
6 common cards / 3 parents。为避免
共同覆盖 headline 隐藏 execution cliff，我在已知 aggregate KILL 后显式冻结 availability×ranking regret 分解；机器
协议把既有 aggregate knowledge 写死，禁止将其伪装为 outcome-blind confirmation。代码、协议和独立 verifier 先以
commit `ab062e1a41c483a87f6d30213b35b8ba88689cb6` 推送并通过 fresh full suite，之后才运行 detailed secondary。

## 2. 联合覆盖与 regret

320 candidates 的 both/external-only/stdout-only/neither 分别为 7/8/85/220，即 external 任意覆盖 15/320、keyed
stdout 92/320、union 100/320。158 parents 中 external 任意可用=10、comparative=5；stdout 分别为 56、36。

三策略的 mean ranking regret 都是 0；external/stdout/hybrid total regret 分别为
0.00862377700985218 / 0.008561457735747085 / 0.008561457735747085。external−stdout mean=
-0.00006231927410509466，run CI=[-0.009615384615384616, 0.00931010760618107]，task CI=
[-0.00024212570430995738, 0.0]；hybrid−stdout 精确为 0。按预先冻结范围，这些都不允许方法正主张。

## 3. 零 ranking regret 的真正原因

零 regret 看起来“过于漂亮”，所以没有直接解释，而是新增不导入 availability producer 的 direct truth-support audit，
从原 selection、label vault、replay、approval 与四个 result shards 重新校验 SHA 后计数。双跑逐字节一致，得到：

| 漏斗 | parent 数 |
| --- | ---: |
| structural selected parents | 158 |
| truth-informative（siblings 非全并列） | 10 |
| external comparative ∩ truth-informative | 0 |
| stdout comparative ∩ truth-informative | 1 |
| 两通道共同 comparative ∩ truth-informative | 0 |

148/158=0.9367088607594937 parents 的 truth 全并列；13/17 tasks 没有一个 non-tied selected parent。原 primary
的 3 个 common parents 全部 truth-tied。因此 external=stdout=1.0 是 tie-aware credit 的代数结果：所有并列候选都是
winner。它不是两通道都预测正确，更不能证明 external 与 stdout 相等。

在仅有的 10 个 non-tied parent 上，external 任意可用=0、comparative=0；stdout 任意可用=3、comparative=1。
所以 secondary 把 external 的所有 oracle headroom 归入 availability regret，并没有观察到 external 的 conditional
ranking。stdout 的 conditional ranking 也只有一个 comparative parent，零 regret 只有 n=1，不能泛化。

## 4. 协议缺口与撤回边界

原 selector 的资格是“至少两个 finite graded structural siblings”，没有要求至少两个**不同** truth values，也没有
truth-gap/precision gate。原预注册只把 common coverage=0 视为 insufficient，却漏了 common truth variation=0；这是
辨识门缺失。为保护历史记录，不事后改代码让机器 verdict 变好：

- 保留 `SCORE_CHANNEL_MECHANISM_KILL` 作为当时冻结规则的输出；
- 撤回任何“该 KILL 支持通道相等/无效”的解释；
- 新科学状态单列 `DISCRIMINATIVE_COMMON_SUPPORT_ZERO`；
- 旧 120s cohort 关闭，不按 task、cap 或 subset rescue。

## 5. novelty 边界与可保留资产

“只有被选择行动有标签”的 selective-label 问题、off-policy positivity/overlap、缺分 benchmark 的 partial ranking 都是
成熟问题：例如 [Wei (ICML 2021)](https://proceedings.mlr.press/v139/wei21a.html) 的 selective-label policy
learning、[Saveski et al. (NeurIPS 2023)](https://proceedings.neurips.cc/paper_files/paper/2023/hash/b7d795e655c1463d7299688d489e8ef4-Abstract-Conference.html)
的 positivity violation/partial identification，以及
[Himmi et al. (EMNLP Findings 2024)](https://aclanthology.org/2024.findings-emnlp.688/) 的 missing-score ranking。因此
`identifiability funnel` 不能申统计方法首创。

可保留的是 domain-specific D&B 资产：在真实 MLE sibling search 上同时物化 structural decision、truth variation、
post-execution evaluator availability 与 paired-channel overlap，并证明只报 accuracy/top-1 会把有效 parent 数从 158
误写成 3，进一步把真正可辨识的 0 忽略。这个审计接口应成为数据集每个 predictor/evaluator 表的固定列，而非新 selector。

## 6. 下一步门

不再自动重跑相同 120s experiment。若利用新 temporal corpus 重开，必须在新 replay 结果产生前先冻结：

1. task-specific truth-informative 定义（结合 scorer precision/noise，不在看到新分布后改阈值）；
2. non-tied parent 数、task/run balance 与最大任务 share 的 CPU 资格门；
3. external/stdout comparative effective-parent 功效目标；
4. 若 120s 预计仍无 overlap，先用独立 pilot cohort 决定是否值得申请另一 cap，confirmation cohort 与 pilot 必须隔离；
5. exact matrix、总 replay、GPU·时再交用户批准。

当前没有授权或提交新 GPU。正式 output、双实现、测试、SHA 与只读路径见
`phase1/results/score_channel_grounding_availability_20260823/README.md`。
