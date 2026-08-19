# CrossClientTransferSupport v1：预注册与执行前检查

日期：2026-08-19。状态：`PREREGISTERED_NOT_RUN`。

## 问题与边界

检验现有 augmented train 数据是否足以严格回答：代码 critic 的信号能否 leave-one-generator/client-out
迁移，而不是只在同一底座风格内成立。此轮只做 outcome-blind 结构支持，不区分 better/worse、不训练模型、
不读 frozen test；它与已失败的“pair 两端 client identity shortcut”是不同问题。

固定输入为 senior commit `92a9651f2e13a9e43623235b82c07c19721bc2ee` 的 31,742-card grouped corpus
和 11,946 个 `intask_split=train` pairs。只保留 pair 两端同 client 且 exact
`(task, hardware, time_limit, execution_timeout)` 的结构池；跨 client exact-code SHA 重复 pair 在效果前排除。

## 固定支持门

每个 held-out client 的每个 test stratum 必须从其他 client 获得至少 50 pairs、2 clients；随后 held-out
client 必须同时满足：test≥200 pairs、≥4 tasks、≥15 runs；匹配 train≥1,000 pairs、≥3 clients；最大 test
task share≤0.50。全局必须有≥6 个合格 client、合计≥3,000 held-out test pairs。

全部通过才允许单独预注册 LOSO 效果实验；失败不降阈值、不合并环境、不读效果。即使通过也不恢复 0AP 的旧
scaling claim，不打开 v11 frozen 或 0812 temporal vault。

## 13 项执行前检查

1. 唯一旋钮是 held-out client；exact execution stratum 固定。
2. 先跑 synthetic orientation-removal、duplicate 和 cross-environment fail-closed tests。
3. 只使用原 train split；test/frozen path 不作为参数。
4. 输出逐 client/task/run 支持，不只报总量。
5. 任务集中度≤0.50，且每个 stratum 要求其他 client 支持。
6. 输出 unordered endpoint pool、summary 与 SHA，不输出 code/grade。
7. client 隔离天然保证 run/endpoint 隔离，另按 code SHA 排除跨 client exact duplicate。
8. 本轮无 RNG；pool 使用确定性排序。
9. 两个输入在 JSON 解析前做 credential scan，命中即拒绝且不打印内容。
10. CPU-only、0 GPU/API，预计 10–20 分钟。
11. 训练支持要求≥1,000 pairs，全局≥3,000 test pairs，避免低功效空跑。
12. shell 保存真实 rc，任一 producer/cmp/verifier 失败即停止。
13. 输入 commit/SHA 固定；后续语料增长不得改变本轮 pool。
