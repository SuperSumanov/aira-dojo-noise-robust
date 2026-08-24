# f109 prediction escrow 七臂同池结构矩阵

日期：2026-08-25

正式状态：`OUTCOME_BLIND_PREDICTION_COVERAGE_VERIFIED`

科学状态：**结构资产成立；transition future support 仍不足；没有效果结论**

## 1. 这次回答什么

本次只检验 WL 四臂与 transition 三臂是否真正在同一批 future structural pairs 上完成了结果前 prediction
escrow，以及两套各自激活时间和 missingness 之后还剩多少合法可比支持。输入接口没有 label、grade、outcome、
winner orientation 或 search utility；预测值只逐行检查有限性、符号/选择一致性和显式 null 契约，不汇总预测分布。

冻结 snapshot 为
`f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708`。四个输入 SHA-256 为：

- WL pairs：`cd99277991397884f9fcbaa92b7e30175bf69bdc497687eacb1a388d859a1513`；
- WL summary：`1370533dfc808ea8f2f6891d544c2ccfd460a503c5f535e4b6fe078eb9ba94ff`；
- transition pairs：`498a8aebf79027e96294e6c22fdce87e4007cdaeacfbb969198f55627b9db3fe`；
- transition summary：`da62681ed53835de40a9a3dda583e589e05aef7c5bd1d602cc556b78c851d5cf`。

七臂为：`step_only_lr`、`wl_graph_lr`、`wl_graph_static_lr`、
`wl_graph_static_tfidf_lr`、`child_code`、`transition_only`、`child_plus_transition`。

## 2. 正式结构结果

| 项目 | WL | transition |
|---|---:|---:|
| structural pairs | 2,589 | 2,589 |
| 有 pair 的 physical runs | 324 | 324 |
| tasks | 29 | 29 |
| 全臂 non-tie pairs | 2,589 | 2,244 |
| 各自激活后 pairs | 924 | 417 |

两套 canonical unordered pair universe **逐 pair 完全一致**：intersection=union=2,589，IoU=1.0，WL-only=0，
transition-only=0；2,589 行 left/right 顺序也全部一致。独立实现重算得到同一 identity mapping SHA-256：
`e01313687e69161317226cc4cf2d35f6127fa341b6d5dad14c895c1744fb392f`。

这不是说两套 strict population 相同。它们的 activation receipt 不同，正确的交叉表是：

| WL 时间层 | transition 时间层 | pairs |
|---|---|---:|
| post-WL-activation | post-transition-activation | 417 |
| post-WL-activation | transition support-only | 507 |
| WL support-only | transition support-only | 1,665 |

因此绝不能把 WL 的 924 个激活后 pairs 直接叫作 transition future pairs；其中 507 个发生在两个 activation
边界之间。早期实现曾错误尝试把两个 strict 名称统一成一个 stratum，正式结果前已经由 fail-closed 暴露并修正。

transition 的结构 missingness 也被保留而非静默丢弃：2,261/2,589 pairs 有 parent source，328 pairs 的 parent
source 缺失，故三个 transition prediction 按原协议均为 `null`；另有 17 个 parent-present pairs 至少一臂为 tie，
所以全三臂 non-tie 为 2,244。全体中 `source_novel=true` 也是 2,261 行，但本报告不因总数相同而假定它与
parent-present 是同一集合。

在更晚的 transition activation 后共有 417 pairs，其中 parent source 可用 366，最终
`strict_effect_eligible=363`。既有 outcome-blind gate 仍是
`TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`：eligible runs=45<150，pairs=363<1,500，dominant-task
share=107/363=`0.29476584`>0.25；只有 tasks=16≥15、parent-source coverage=
`0.8776978417266187`≥0.80 及训练重叠为零等门通过。不得提前揭盲或把 1,500 structural-pair 支持门改成停止门。

全 2,589 pairs 还存在明显 task 不均衡：OSIC 823/2,589=`0.3178833526458092`。论文后续必须以 task-clustered
或 task-macro 为主，不能用 micro headline 掩盖主导任务。

## 3. 正面资产与严格边界

这是一个真实的正面**方法学资产**：七个预先封存的 predictor arms 现在拥有完全相同的 2,589-pair 身份宇宙，
今后在相应 truth 合法开放后可做 paired comparison，不再有“方法各自在不同 pair pool 上评估”的混杂。两套原生
pair ID 算法虽不同，独立 canonical identity 仍逐行相同。

它目前不证明任何 predictor 准确率、WL/transition 优越性、scaling、search utility 或 query-cost 优势。共同 runtime
receipt 不存在，本报告明确写 `runtime_or_query_cost_comparison=NOT_COMPUTED`。transition effect population 也只有
363 eligible pairs，仍未过预注册支持门。

## 4. 失败链与修正

正式成功前共有 6 个失败尝试，全部保留、没有覆盖：

1. `d958157` 两次重复 launcher 均在 `env_setup.sh` 前错误开启 nounset，未读输入；
2. `5e293ac` 一次遇共享 remote-tracking ref 锁竞争、未读输入；另一次进入 builder 后拒绝未知 WL stratum；
3. `8321bc1` 在 builder 中再次以未知 WL stratum fail closed；
4. `488b877` 暴露 transition 缺 parent 时 hash/prediction 应为 `null` 的合法契约；
5. `2c5626d` 明确分开两套 activation、实现 missingness 契约后才正式通过。

前两类工程错误分别由“先 source、后 set -u”和
`ls-remote → fetch --no-write-fetch-head → ancestor proof` 的攻击测试锁住。两个 schema 错误促使最终定义更严格，
而不是删行或放宽输入。失败/复验 registry 的 `SHA256SUMS` 自身 SHA-256 为
`dff24b099884b23712b80b69f0f0a5334e535c796d37826324b4575b308a8f6e`。

## 5. 复现与收据

- formal control commit：`2c5626ddd94f8fd21c2e4ae6fe5ec4f6cce17e7d`；
- formal root：`/research/d7/spc/yzyang4/prediction-escrow-coverage-matrix/2c5626d-f109-v1`；
- builder×2 逐字节一致，independent verifier×2 逐字节一致；
- focused：`10 passed`；完整 phase1：`975 passed, 47 warnings in 74.75s`；
- formal `SHA256SUMS` 自身 SHA-256：
  `e50065777f18b6167648e5d6900b5f134e6b6b14c56175c7e5540e41e344e7c7`；
- formal 与 config-v2 两个目录均已独立 `sha256sum -c` 全通过，且递归无可写路径；
- archive/tar、label/grade/outcome/winner orientation 未读，effect/accuracy/search utility 未算，GPU/API/base-LLM
  update=`0/0/0`。

下一步仅让连续 monitor 对新 snapshot 追加 prediction escrow；在 transition 的 run/pair/task-balance 门全过且 closure
满足前，不打开 truth，不做 effect，不启动 GPU。
