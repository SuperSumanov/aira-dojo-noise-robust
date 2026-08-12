# v10 决策 critic：给学长的数据交接（2026-08-13）

## 获取

```bash
git checkout phase1-value-critic
git pull --ff-only
git lfs pull
```

v10 大文件已经上传到 Git LFS，不需要访问我的 big-data-storage 路径。当前共享分支至少应
包含 commit `4ebc495`（v10 语料）；后续决策对提交会在它之后。

## 数据文件

```text
phase1/
  cards_current_v10.jsonl            # 15,158 cards / 624 runs / 24 tasks
  cards_senior_0810.jsonl            # 学长 0810 增量：835 cards / 38 runs / 8 tasks
  card_run_map.json                   # 15,158 个 card_id -> physical run_id
  task_orientation.json               # lower_is_better
  v10_decision/
    decision_train_v10_b0.jsonl       # 4,122 条，只供训练
    decision_train_v10_b1.jsonl       #   814 条，只供训练
    decision_train_v10_b2.jsonl       #   661 条，只供训练
    decision_frozen_v10_b0.jsonl      # 1,498 条，论文冻结测试
    decision_frozen_v10_b1.jsonl      #   323 条，论文冻结测试
    decision_frozen_v10_b2.jsonl      #   265 条，论文冻结测试
    decision_extension_v10_b0.jsonl   #    68 条，v10 新 run 扩展测试
    decision_extension_v10_b1.jsonl   #    12 条，v10 新 run 扩展测试
    decision_extension_v10_b2.jsonl   #     9 条，v10 新 run 扩展测试
    decision_v10_audit.json           # 输入 SHA、计数、泄漏验收
    runsplit_holdruns_v10.json         # 冻结 + 新增 run 分配
```

其中 v10 共有 15,140 张有限真分卡；18 张历史非有限标签卡保留节点与血缘，但已明确隔离，
不得参与训练或评测。

## 公平契约（最重要）

以下文件绝不能进入训练：

- `decision_frozen_v10_b*.jsonl`
- `decision_extension_v10_b*.jsonl`

训练只读 `decision_train_v10_b*.jsonl`。已验证：冻结测试节点进入训练为 0；训练 run 与扩展
测试 run 交集为 0；旧有效冻结集逐对复现，missing/extra/reversed 均为 0。

headline 结果只报 `decision_frozen_v10_b*.jsonl`。`decision_extension_v10_b*.jsonl` 是 v10
新增 held run 的前瞻检验，必须单列，不能和 headline 混算。

## 建议你现在做的最省事实验

优先复用你 0812 的最佳 Qwen3-4B/8B checkpoint，对三份 frozen 文件逐对打分；无需重新训练。
每个 budget 单独报告 accuracy，并保留逐 pair 结果供 task/run 聚类 bootstrap。8B/16k 的作用是
检验现有约 0.55 的结果是否受容量或上下文限制，而不是只报最佳单次 seed。

推荐输出：

```json
{
  "model": "qwen3-8b-16k",
  "checkpoint": "<path-or-id>",
  "seed": 7,
  "predictions": {
    "<better_id>|<worse_id>": 1
  }
}
```

`1` 表示模型把 `better` 排在 `worse` 前。请同时保存确切命令、commit、依赖和 seed。

## 为什么旧数字变了

旧 `decision_clean_b0.jsonl` 实有 1,499 条测试行，其中 1 条引用历史 `NaN` 标签；严格隔离后
是 1,498 条。旧 README 写的 b0 train=3,777 也已过期：真实旧有效训练对是 3,907，v10
再增加 215 条，得到 4,122。完整证据见
`phase1/实验记录/2026-08-13/v10冻结决策集与训练增量验收.md`。
