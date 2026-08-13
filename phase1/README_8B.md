# v11 决策 critic：给学长的数据交接（2026-08-13）

> 研究路线以 `phase1/CURRENT_DIRECTION.md` 为唯一入口；本文件只定义 v11 数据契约与
> checkpoint 冻结评测，不代表恢复旧 HCE、TD/RL 或 lookahead 主线。

## 获取

```bash
git checkout phase1-value-critic
git pull --ff-only
git lfs pull
```

v11 大文件通过 Git LFS 共享，不需要访问我的 big-data-storage 路径。

## 数据文件

```text
phase1/
  cards_current_v11.jsonl            # 16,012 cards / 667 runs / 25 tasks
  cards_senior_0811.jsonl            # 学长 0811 有效增量：854 cards / 43 runs / 7 tasks
  card_run_map.json                   # 16,012 个 card_id -> physical run_id
  task_orientation.json               # lower_is_better
  v11_decision/
    decision_train_v11_b0.jsonl       # 4,263 条，只供训练（v10 4,122 原样 + 141）
    decision_train_v11_b1.jsonl       #   861 条，只供训练（v10   814 原样 +  47）
    decision_train_v11_b2.jsonl       #   692 条，只供训练（v10   661 原样 +  31）
    decision_frozen_v11_b0.jsonl      # 1,498 条，论文冻结测试（与 v10 完全相同）
    decision_frozen_v11_b1.jsonl      #   323 条，论文冻结测试（与 v10 完全相同）
    decision_frozen_v11_b2.jsonl      #   265 条，论文冻结测试（与 v10 完全相同）
    decision_extension_v11_b0.jsonl   #   136 条，累计扩展测试（旧68 + 新68）
    decision_extension_v11_b1.jsonl   #    39 条，累计扩展测试（旧12 + 新27）
    decision_extension_v11_b2.jsonl   #    30 条，累计扩展测试（旧 9 + 新21）
    decision_v11_audit.json           # 输入 SHA、计数、泄漏验收
    runsplit_holdruns_v11.json         # 冻结 + 累计新增 run 分配
```

其中 v11 共有 15,991 张有限真分卡；21 张非有限标签卡保留节点与血缘，但已明确隔离，
不得参与训练或评测。

## 公平契约（最重要）

以下文件绝不能进入训练：

- `decision_frozen_v11_b*.jsonl`
- `decision_extension_v11_b*.jsonl`

训练只读 `decision_train_v11_b*.jsonl`。已验证：冻结测试节点进入训练为 0；训练 run 与扩展
测试 run 交集为 0；v10 train/frozen/extension 都是 v11 对应文件的原样前缀。

headline 结果只报 `decision_frozen_v11_b*.jsonl`。因为 frozen 与 v10 完全相同，已有 frozen
预测无需重跑。`decision_extension_v11_b*.jsonl` 是累计 held-run 前瞻检验，必须单列，不能
和 headline 混算。

## 建议你现在做的最省事实验

优先复用你 0812 的最佳 Qwen3-4B/8B checkpoint，对三份 frozen 文件逐对打分；无需重新训练。
每个 budget 单独报告 accuracy，并保留逐 pair 结果供 task/run 聚类 bootstrap。8B/16k 的作用是
检验现有约 0.55 的结果是否受容量或上下文限制，而不是只报最佳单次 seed。

推荐输出（单个 pair set 时可用下列扁平格式；仓库 evaluator 为防止 b0/b1/b2
同端点碰撞，会在最外层再按 pair-set 名分组）：

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

仓库已提供严格 evaluator：`phase1/score_frozen_decision_checkpoint.py`。checkpoint 必须先在
旧 validation 上锁定；不得看过 frozen 结果后改选模型、epoch 或 checkpoint。单卡推理示例：

```bash
python phase1/score_frozen_decision_checkpoint.py \
  --cards phase1/cards_current_v11.jsonl \
  --run-map phase1/card_run_map.json \
  --pairs frozen_b0=phase1/v11_decision/decision_frozen_v11_b0.jsonl \
  --pairs frozen_b1=phase1/v11_decision/decision_frozen_v11_b1.jsonl \
  --pairs frozen_b2=phase1/v11_decision/decision_frozen_v11_b2.jsonl \
  --expect-cards-sha256 6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75 \
  --expect-run-map-sha256 3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30 \
  --expect-pairs frozen_b0=1498:2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8 \
  --expect-pairs frozen_b1=323:a56f6c7bd6aad141fdaa45f3f30f944062e8dea922eefc03e75bc8b415e7bc90 \
  --expect-pairs frozen_b2=265:79d4694d4cea5a81a04c9d463b5c6599a559bbf867f34205fa5715b054f10bc7 \
  --checkpoint /ABS/PATH/TO/LOCKED/CHECKPOINT \
  --base-model /ABS/PATH/TO/Qwen3-8B-Base \
  --checkpoint-locked-before-frozen \
  --max-len 16384 --batch-size 2 --bootstrap 10000 --seed 7 \
  --out-dir outputs/frozen_qwen3_8b_seed7
```

脚本把 pair 朝向只用于端点集合和最终 margin，不把朝向输入模型；输出 `per_pair.jsonl`、
按 pair-set 名嵌套的 `predictions.json` 和
`summary.json`；后者包含 run/task 聚类区间、run-level exact sign、输入/脚本 SHA 与渲染参数。
它会拒绝非 test 行、重复/反向 pair、空代码、跨任务或跨 physical-run pair，以及与训练架构
不匹配的 checkpoint；checkpoint 模式还会强制核对上述数据 SHA/条数，记录完整权重 SHA，且拒绝
覆盖非空输出目录。当前模型训练时没有 budget conditioning，所以不要加 `--budget-cond`。

## 为什么旧数字变了

旧 `decision_clean_b0.jsonl` 实有 1,499 条测试行，其中 1 条引用历史 `NaN` 标签；严格隔离后
是 1,498 条。旧 README 写的 b0 train=3,777 也已过期：真实旧有效训练对是 3,907，v10
再增加 215 条，得到 v10 的 4,122；v11 只追加 141 条，得到 4,263。完整证据见
`phase1/实验记录/2026-08-13/v10冻结决策集与训练增量验收.md` 和
`phase1/实验记录/2026-08-13/学长0811入库_v11验收.md`。
