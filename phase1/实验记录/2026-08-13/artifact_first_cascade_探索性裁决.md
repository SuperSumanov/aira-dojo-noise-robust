# artifact-first cascade：探索性裁决（2026-08-13）

## 裁决

预注册的 coverage-complete cascade **BORDERLINE，不是 GO**。在冻结的 100 sibling sets / 230
candidates / 52 physical runs / 19 tasks 上，`artifact_score_then_stdout` 相对同成本
`stdout_only` 的 tie-aware endpoint top-1 差为 **+0.0700**：

- run-clustered 95% CI `[0.0000, 0.1429]`；
- task-clustered 95% CI `[0.0108, 0.1369]`；
- run sign：7 正、2 负、43 tie，双侧 exact `p=0.1797`；
- task leave-one-out 全正，范围 `[+0.0479,+0.0833]`；
- 120 秒成本相对历史 full runtime：每 set 比率的 macro mean `0.2720`；aggregate
  ratio `0.0586` 仅作次要描述，因为它会被少数超长任务主导。

它没有通过预注册的 `delta>=+0.08`、run-CI 下界严格大于 0、sign `p<0.05` 三道门，因此不能
声称 coverage-complete cascade 已带来稳健正收益。hard/easy 分解为 `+0.1000/+0.0400`，只作
预注册 secondary，不替换 headline。

## 真正新增的机制证据

同一成本下的机制分解显示，问题不是“artifact-first 是否整体过线”这么简单，而是 artifact
的**分数值**与**可观测性**方向相反：

| 比较 | top-1 差 | run-CI | task-CI | run sign p |
|---|---:|---:|---:|---:|
| score cascade − presence cascade | +0.1447 | `[+0.0717,+0.2241]` | `[+0.0541,+0.2510]` | 0.000519 |
| presence cascade − stdout | −0.0747 | `[−0.1385,−0.0182]` | `[−0.1604,−0.0059]` | 0.096252 |
| score + random fallback − random | +0.1185 | `[+0.0326,+0.2087]` | `[+0.0208,+0.2337]` | 0.004344 |

前两项的 run-sign Holm 校正 p 分别为 `0.001038` 与 `0.096252`。所有 task-LOTO 在 score-value
比较中为正，在 presence 比较中为负。

最谨慎的解释是：**早期 pristine artifact 分数在被观察到时很有信息，但“120 秒内能否产出
artifact”并非随机缺失，且不能当质量的正向代理。** 这是选择性可观测/MNAR 的机制候选，
尚不能在同一发现集上升级为确认性结论。

## 完整性与复核

- 输入 SHA、100/230/52/19 计数、50 hard + 50 easy、每 card 的 30/120 秒完整网格均在运行前
  fail-closed 检查；oracle 正控 top-1=1，既有 random 与 artifact/random anchor 均复现。
- 主程序修正了两项报告口径后从锁定输入重跑：跨任务 raw regret 改为 median raw + 每 set
  normalized regret；成本门使用更保守的 macro set ratio。策略、top-1、聚类单位和 GO 阈值
  均未改变，修正已写入预注册附录后再产生最终结果。
- 第二个 clean worktree 的三份核心 CSV 与第三个 clean worktree 逐字相同；剥离 provenance 后
  summary 指标相同。
- 独立验证器不导入主分析脚本，改用 seed=9173、20,000 bootstrap draws，从 raw inputs 重建
  policy 与推断；主差、score-value、presence 三个点估计和 sign counts 全部复现，输出
  `INDEPENDENT_VERIFY_PASS`。
- 第一次 clean-worktree 尝试因非 login PATH 找不到 `git-lfs`，在读取输入和运行分析前失败；
  修复为显式加入已安装 LFS 路径。checkout 仍提示 16 个历史文件不是 pointer，但它们不在本审计
  输入链；所有冻结输入 SHA 均通过。
- 提交前 `git diff --check` 发现 Python `csv` 默认 CRLF 被 Git 判为 trailing whitespace；writer
  随后显式锁为 LF，并在第四个 clean worktree 从原始输入重跑。三份 CSV 与上一轮按 CSV 语义
  逐行相同，剥离 provenance 后 summary 完全相同，独立验证仍通过；未绕过质量门。

## 下一步边界

该发现将方法候选收窄为“**选择性/删失感知的外部评分融合**”，而不是继续推动 naive
artifact-first。下一次短验证仅允许一个预先冻结、无阈值调参的 parent-certified improvement
规则。真正的论文确认仍只能来自机制冻结后新 physical runs；当前 150-run 主实验资格数为 0，
且尚未提交。
