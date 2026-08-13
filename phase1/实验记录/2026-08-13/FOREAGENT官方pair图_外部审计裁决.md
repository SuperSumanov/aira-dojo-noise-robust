# FOREAGENT 官方 pair 图外部审计裁决（2026-08-13）

状态：**PAIRING-MISMATCH VERIFIED（结构结果）**；不是官方模型准确率复算，也不是因果解释。

## 1. 输入与独立复核

- 官方 Hugging Face 自动转换 parquet：8,456,690 bytes，SHA256=
  `79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f`；
- 我方真实 sibling b0：SHA256=
  `33df48f8c9b54f60e6e3f100b9269e5e3950c506c8ff98601a61848e197ede50`；
- 官方仓库 commit：`c4d52cf99bd870d830b456ac7c0684aec1aef375`；
- 指标、固定 gap 桶、task-macro 与解释限制均在读取分布 aggregate 前提交；第一次执行因 b0 中
  `gap_raw=NaN` 的一行在写输出前 fail-closed。随后冻结为显式记录并排除该行：1,499 total / 1,498
  finite，与既有 headline 计数一致。

不导入主脚本的 verifier 从两份锁定 raw input 重算关键结果并逐任务核对 CSV：

```text
PBE_EXTERNAL_PAIR_INDEPENDENT_VERIFY_PASS official_rows=18361 solutions=895 official_hard=0.096400 our_hard=0.501335 official_common_hard=0.121988 our_common_hard=0.496975 directional_common_tasks=12/14
```

## 2. 结构结果

| 描述 | 官方全局组合对 | 我方真实 sibling b0 |
|---|---:|---:|
| finite pairs | 18,361 | 1,498 |
| tasks | 26 | 22 |
| `gap<1e-2` pair share | **0.096400** | **0.501335** |
| `gap<1e-2` task-macro share | 0.176171 | 0.463303 |
| median raw gap | 0.123900 | 0.009895 |

为控制任务组成，只看 14 个精确同名 common tasks：

| 描述 | 官方 common tasks | 我方 common tasks |
|---|---:|---:|
| pairs | 9,255 | 1,157 |
| `gap<1e-2` pair share | **0.121988** | **0.496975** |
| `gap<1e-2` task-macro share | 0.218633 | 0.439512 |
| median raw gap | 0.072300 | 0.010240 |

14 个 common tasks 中有 12 个方向一致：我方 sibling 对的 hard share 更高。该 12/14 是预注册
per-task 表的描述性方向计数，不追加 post-hoc 显著性结论。两个反向任务是 NOMAD 与 PetFinder，均在
完整 CSV 中保留。

官方图由 895 个 unique solutions 组成，18,361 个 unordered pairs 无重复。每个 solution 被复用的
次数 median=49、mean=41.0302、max=49；每任务 pair graph coverage 的 median=0.995918，说明多数任务
近乎穷举组合，而不是从 agent 当时面对的 sibling 决策抽样。只有 2,913/18,361=0.158651 pairs 来自
同一 trajectory prefix。

## 3. 允许的结论

**已验证的正向 benchmark 发现**：全局近穷举 pair corpus 与真实 sibling 决策点不是同一个评测分布。
后者的近平局比例约高四倍（common-task pair share 49.70% vs 12.20%），且前者只有 15.87% 同轨迹对。
因此只报全局 micro pair accuracy 会系统性掩盖 agent 搜索真正面对的局部决策难度；run-aware、
decision-aware、gap-stratified evaluation 是实质贡献，而不只是“换一种 split”。

这条发现与当前选择性执行反馈主线兼容：静态 judge 在真实 sibling 决策点失效后，120 秒 pristine
external score 在 observed 候选上仍有价值；论文可以把“全局预测能力”与“局部可用决策信号”分开。

## 4. 禁止的结论与新审计

- parquet 不含官方逐 pair judge predictions，不能仅凭本结果说 gap **导致** 61.5%；
- 不能把 18,361 pairs 当独立样本；但也不能仅凭 solution 复用断言原论文显著性无效；
- raw gap 的跨任务 metric scale 不同，所以 common-task、task-macro 和 per-task 必须伴随 micro；
- 论文声称 18,438 pairs，而自动 parquet 有 18,361，差 77。官方 alignment 的 APTOS 样例有完整
  1,225 pairs，而 parquet 为 1,216；差异来源尚未全量验证，暂不假定都是 ties。

官方发布包还含 26 tasks × 3 runs 的 DeepSeek-V3.2-Thinking 与 GPT-5.1 alignment JSON，字段包括
solution ID、两端 score、prediction、confidence 与 correctness。下一步应在下载任何全量 outcome 前冻结：
按固定 raw-gap 桶和 task 内 gap quantile 重算官方模型准确率；以 task-cluster 推断为主，显式剔除/单列
exact-score ties，并检查三次 release runs 的 pair grid 与 ground truth 是否一致。这比再次调用 Qwen 更
直接，也不消耗 API。
