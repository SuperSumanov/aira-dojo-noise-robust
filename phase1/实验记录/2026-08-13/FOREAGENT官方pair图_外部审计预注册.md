# FOREAGENT 官方 pair 图外部审计冻结说明（2026-08-13）

状态：outcome 前冻结的探索性外部数据审计；不涉及 API/GPU，不改当前 late-artifact gate。

## 输入锁

- Hugging Face 自动转换 parquet：8,456,690 bytes，SHA256=
  `79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f`；
- 我方真实 sibling b0：SHA256=
  `33df48f8c9b54f60e6e3f100b9269e5e3950c506c8ff98601a61848e197ede50`；
- 官方仓库审计 commit：`c4d52cf99bd870d830b456ac7c0684aec1aef375`。

## outcome 前固定指标

1. 官方 rows、unique unordered pairs、unique solution paths、tasks、重复 pair 数；
2. 每个 solution 被组合复用的 median/mean/max 次数；
3. 每任务实际 pairs / `n_solution choose 2`；
4. raw score gap 的固定桶：
   `[0,1e-4),[1e-4,3e-4),[3e-4,1e-3),[1e-3,3e-3),[3e-3,1e-2),`
   `[1e-2,3e-2),[3e-2,1e-1),[1e-1,3e-1),[3e-1,∞)`；
5. `gap<1e-2` 的 pair-weighted share、task-macro share、median gap 与固定
   q10/q25/q50/q75/q90；
6. 文件名在最后 `_run_` 之前的 prefix 作为 agent trajectory key，报告可解析率和 same-trajectory share；
7. 与我方 b0 在全部任务及精确同名 common tasks 上作同口径描述，不作显著性检验；
8. per-task CSV 必须同时保存 solution 数、pair 数、pair-graph coverage、gap 与 trajectory 指标。

## 解释约束

- 若官方 common-task hard share 明显低于我方，最多说“pairing distribution 是候选解释”，不能在没有
  官方逐 pair prediction 的情况下声称它解释了 61.5%；
- 若不低，撤回“主要由 gap 分布抬高”的强解释，转而只保留真实 sibling/run context 的差异；
- 18,361 pairs 来自少量 solution 的组合复用说明观测依赖，不能据此直接判定原论文显著性错误；
- raw `1e-2` 跨任务阈值受 metric scale 影响，必须同时给 task-macro/per-task，不可只报 micro；
- 本审计不接触官方 judge outcome，不与我方 qwen-max 结果合并算新 headline。
