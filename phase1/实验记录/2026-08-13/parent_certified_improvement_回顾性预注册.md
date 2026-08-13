# parent-certified improvement：回顾性预注册（2026-08-13）

状态：**规则、输入、主比较和裁决门已冻结；尚未运行 outcome 分析。**

## 动机与诚实边界

上一项冻结发现集审计显示，120 秒 artifact 的 pristine **分数值**有用，但 artifact **是否被观察到**
本身相对 stdout 是负信号。因而本实验只检验一个无训练、无可调阈值的删失感知规则：以当前
incumbent/parent 已知的外部搜索分数为锚，只有早期 artifact 被同一 pristine scorer 证实严格改善
parent 时，才允许覆盖默认 stdout 决策。

本实验仍复用同一 100-set 机制发现集，只能决定该规则是否值得在新 physical runs 上前瞻复现，
不能提供独立确认。`cards_current_v9.jsonl` 中的历史 `label.graded` 只作为“线上已经由允许的
`D_search` pristine evaluator 得到的 parent 分数”的回顾性替身；它绝不能解释成部署时可访问
`D_test`。未来实现若没有合法、在决策前已存在的 parent 搜索分数，则该规则不可部署。

在只检查 schema/覆盖、不读取或汇总 parent 数值和规则结果的 feasibility pass 中：100 个 parent
有 88 个存在且 `label.graded` finite；这 88 个的 task 与 higher/lower orientation 全部一致。其余
12 个固定回退 stdout。88 个可见 parent 还全部满足：manifest child 的 `lineage.parent_id` 指回该
parent、parent 与 children 同一 physical run、parent step 严格早于所有 children。因此 parent 是
因果上先于本次 sibling 决策的真实 incumbent，而不是事后匹配的任意节点。feasibility 数字不是
outcome，也不改变下面的规则。

分数可比性的证据边界是：120 秒 `sub_score` 明确由 `mlebench grade-sample` pristine worker
产生；parent `label.graded` 来自原 journal 的外部 MLE-bench `metric_info.score`。历史文件没有把
两次 grader 可执行文件的版本/hash 写进每行，因此“完全相同 grader build”不能由现有产物机器
证明，必须作为本回顾性验证的限制；前瞻复现必须把 grader binary/version/data SHA 写进产物。

## 冻结输入

| 输入 | SHA-256 | 固定约束 |
|---|---|---:|
| `fidelity_manifest.jsonl` | `77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef` | 230 cards / 100 sets |
| `fidelity_results.jsonl` | `b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d` | 每 card 30/120 秒各一行 |
| `fidelity_runtime_v9.jsonl` | `dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7` | 230 cards |
| `card_run_map.json` | `3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30` | 52 physical runs |
| `task_orientation.json` | `e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a` | 19-task orientation |
| `cards_current_v9.jsonl` | `daeb29fc07ad670b5ca7a10cd2d84f1fa9a27dfa9d22510533417f1a8ad9407f` | 12,383 cards；88/100 parent finite |

总体必须仍为 100 sets / 230 children / 52 runs / 19 tasks / 50 hard + 50 easy。任一 SHA、计数、
parent task/orientation、120 秒覆盖或 anchor 不符即 fail closed。

## 唯一规则

对每个 sibling set，记 task-oriented utility 为：higher-is-better 时等于 score，lower-is-better 时
等于负 score。

`parent_certified_override`：

1. 若 parent 的历史 pristine 分数有限，对每个具有 120 秒 `sub_score` 的 child 检查
   `utility(sub_score) > utility(parent_score) + 1e-12`；`1e-12` 只用于浮点严格比较，不是可调阈值。
2. 若至少一个 child 通过证书，只在通过者中按 `sub_score` 选最优；并列用解析期望，不抽样。
3. 若 parent 缺失、无 finite 分数、无 artifact，或没有 artifact 严格改善 parent，则按
   `stdout_only`：在 finite `stdout_val` 中选最优。
4. 若连 stdout 也不存在，则在完整 sibling set 上均匀随机，仍用解析期望。

不允许 epsilon sweep、按任务阈值、按 hard/easy 改规则、只保留 parent 可见集合或 outcome 后新增
fallback。参考策略固定为 `stdout_only`、上一项已冻结的 `artifact_score_then_stdout`、`random`
和 `full_oracle`；后二者只作 anchor/正控。

三项历史 anchor 也在运行前锁定：`random=0.4598333333333333`、
`stdout_only=0.5383333333333333`、`artifact_score_then_stdout=0.6083333333333333`。它们只用于
检查输入/策略实现未漂移，不作为 parent 规则的独立验证。

## 指标与推断

headline 是全部 100 sets 上
`parent_certified_override - stdout_only` 的 tie-aware endpoint top-1 配对差：

- physical-run clustered percentile bootstrap 为主，task clustered percentile bootstrap 为次，均
  10,000 draws，seed=`20260813`；
- physical-run effect 的双侧 exact sign test，物理 run 为独立采集单位；考虑同 task 相关性的
  task-clustered CI 也必须过门，因此 sign test 不单独支撑 GO；
- task leave-one-out 最小/最大差，不删除任务；
- hard/easy、mean normalized regret、median raw regret、mean rank 均为 secondary；
- 报告证书触发 set/run/task 数；仅在 88 个 parent 可见 set 上，报告所选 child 最终分数严格改善
  parent 的比例，作为 secondary，不替换 headline；
- 120 秒成本沿用相同 replay 账本，门使用每 set cost ratio 的 macro mean；aggregate ratio 只作描述。

`parent_certified_override - artifact_score_then_stdout` 仅用于解释锚点是否缓解 naive cascade 的
选择偏差，不参与多重策略挑选，也不能替换主比较。

## 裁决门

- **PARENT-GO**：“证书触发”明确指至少一个 child **通过**严格 parent-improvement certificate；
  通过者至少覆盖 15 sets 且跨至少 8 physical runs；headline 差 `>=+0.08`；run-
  与 task-CI 下界均严格 `>0`；run sign 双侧 `p<0.05`；task-LOTO 最小值 `>-0.10`；macro cost
  ratio `<=0.35`。
- **KILL-UNDERSUPPORTED**：证书触发不足 15 sets 或 8 runs；不因大点估计放宽。
- **KILL**：支持门通过但 headline `<=0`，或 run-CI 上界 `<=0`。
- **BORDERLINE**：支持门通过、headline `>0`，但任一 GO 门未过。

无论结果如何，不在这 100 sets 上继续试第二个阈值、第二种 parent margin 或训练 selector。若 GO，
仅可把完全相同的规则加入机制冻结后新 physical runs；若 BORDERLINE/KILL，下一种可训练删失模型
必须另立新 discovery split。

## 运行前 adversarial review 处置

一次 `deepseek-v4-pro` 调用把 3,500 completion tokens 全耗在隐藏 reasoning、正文为空，明确记为
失败审查；随后一次封顶 `deepseek-chat` 调用实际路由为 `deepseek-v4-flash`，返回
`FIX-BEFORE-RUN`。在未看 outcome 前采纳了可操作项：明确“触发=至少一个 certificate pass”、
把 lineage/同 run/时间先后变成 fail-closed 校验、把三个历史 anchor 写入预注册、显式验证 run-map
覆盖，并把输出目录改为存在即拒绝。以下意见经代码/文本核对后不采纳：它声称 `-0.10` 与 `0.35`
阈值未写入预注册（本节此前已明确写出）；把 run-level sign test误称为“未聚类的 set test”（代码先
聚合为 run effect）；把 oracle 正控解释成有效性证据（它只用于代码一致性）。模型审查只作为
preflight，不是论文证据。
