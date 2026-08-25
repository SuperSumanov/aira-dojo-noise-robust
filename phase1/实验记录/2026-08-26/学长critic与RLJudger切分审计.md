# 学长 critic / RL-judger 切分与 checkpoint 选择审计

日期：2026-08-26

审计对象：`myfork/dojo-reproduce` commit
`2b22f3102a2a64cb89ebcae9ede4d8eb72e1430d`。本轮只读 Git 中的源码、脚本和 LFS pointer；没有启动训练、读取
prospective outcome，也没有把 `intask_split=="test"` 行送入任何模型。

## 结论先行

训练脚本把同一个 runsplit JSONL 同时传给 `--train_pairs` 与 `--test_pairs`，**这一点本身不是 train/test 行泄漏**：当前
loader 会在内部按 `intask_split` 精确过滤，普通 in-task 模式下 train pool 只取 `train`，testing pool 只取 `test`。

但当前训练协议仍不能把输出称为“冻结 test 结果”，因为 `test` pool 被直接作为 Hugging Face Trainer 的
`eval_dataset`，每 10 steps 重复评估；默认 `save_strategy="best"` 且 `metric_for_best_model="eval_pair_accuracy"`。因此这批
`test` 实际承担了 dev/checkpoint-monitoring 的角色。即使 `load_best_model_at_end=False`，训练过程仍记录 best metric，并按
它保存 best checkpoint；若人工汇报多次 eval 中的最好分数，污染更直接。

最稳妥的表述是：当前 scaling 仍是有价值的**探索性容量信号**，不是 untouched frozen confirmation。这与当前
`CURRENT_DIRECTION.md` 的定位一致。

## 1. 已通过的源码级检查

1. `train/dataset/pairs.py:66`：非 LOTO 的 training pool 只保留
   `pair["intask_split"] == "train"`。
2. 同文件 `:83`：testing pool 只保留 `intask_split == "test"`。
3. `preprocess/build_bt_pairs/apply_runsplit.py:140-143`：跨 split 的 pair 被丢弃，其余 pair 才写入固定 split。
4. `postprocess/rl/build_judger_messages.py:86-119`：RL-judger message 已拆成 train/test 两个输出文件，且 deterministic
   seed 决定 A/B 朝向。

因此，学长问到“同一个约 4k pair 文件为何同时传两次”时，可以准确回答：文件路径相同只是接口写法，loader 在内部分流；
真正要修的是把 outer test 当作周期 eval，而不是路径相同本身。

## 2. 必须修复或显式降级的风险

### 2.1 Outer test 参与训练期观察与保存

- `train/bradley_terry.py:103-122` 读取两个 pair 参数并构造 training/testing pool；
- `:150` 把 testing pool 传给 `eval_dataset`；
- `train/config/bradley_terry_config.py:49-53` 默认 steps eval、best save、以
  `eval_pair_accuracy` 作为 best metric；
- `scripts/train/8xh200/train_mixed_decision_value.sh:29-92` 各模型都把同一 runsplit 文件作为 train/test 输入，并设
  `eval_steps=10`。

这不会把 test 样本加入梯度，但会让模型开发、训练终止判断、checkpoint 保存和人工选择接触 test。论文里不能再称它为
一次性 test。

### 2.2 LOTO 分支绕过 `intask_split`

`train/dataset/pairs.py:62-64,79-81` 在 `--loto` 非空时按 task 过滤，而不再按 `intask_split` 过滤。这可以是一个独立的
leave-one-task-out estimand，但它会把其他任务中原本标为 test 的 pair 纳入训练。不得同时把它解释成 run-clean frozen-test
评估；两种协议必须分开命名和出表。

### 2.3 缺失 endpoint 被静默丢弃

`read_pairs` 会静默过滤 cards 文件中缺失任一 endpoint 的 pair，没有打印 dropped count 或 coverage receipt。不同模型若因
context/data materialization 得到不同覆盖，scaling 曲线可能混入样本池变化。正式训练前应 fail-closed 或至少输出 exact
coverage + dropped IDs hash。

### 2.4 RL-judger 的 test 标签与位置偏差

train/test message 分文件是进步，但 test JSONL 每行仍含 `solution`。训练 launcher 必须只能访问 train 文件，最终 evaluator
应把 test solution 放到独立、不可见 label sidecar。当前每 pair 只采一个 seeded A/B 朝向；训练可以接受，最终评估必须双朝向
或至少报告 position consistency。

### 2.5 context 统计默认路径已经失效

最新 commit 删除了单一 `rl_judger_messages.jsonl`，但 `measure_context.py:26,67,130` 仍以该旧文件为默认路径。显式传
`--messages` 可绕过，但默认命令会失败；应分别统计 train/test，尤其要单独报告 test over-limit fraction。

## 3. 推荐的最小修复协议

1. physical-run 固定三分：`train / dev / frozen_test`；同 endpoint、同 physical run 在三者间严格零交集。
2. 训练器只接受 `--train-pairs` 与 `--dev-pairs`；训练期间禁止 `--test-pairs` 参数和 test basename。
3. checkpoint/超参/epoch 只由 train-run dev 决定。完成后将选中 checkpoint 的 SHA 固定，再由独立 one-shot evaluator 打开
   fresh frozen cohort。
4. 产生机器可读 overlap receipt：run/card/pair 三层交集都为 0，另报每层 coverage 与 silent-drop count=0。
5. scaling 矩阵中所有模型共享同一 train/dev/frozen pool、相同数据序列定义与 seed；至少 3 seeds，报告 task-macro、LOTO、
   physical-run clustered uncertainty，不只报 best single run。
6. RL-judger test labels 单独封存；训练进程的文件访问审计应证明 test message/solution 未打开。

## 4. 当前允许主张

- **成立**：相同 runsplit 文件路径没有自动造成训练行/测试行混入；内部普通模式确实按 `intask_split` 分流。
- **成立**：学长的 0.6B→8B 趋势仍是当前最强探索性 capacity signal，值得用全新协议确认。
- **不成立**：现有 outer-test 数字是 untouched test；best checkpoint 与 test 无关；LOTO 与 run-clean test 是同一 estimand；
  或现有脚本已经提供完整 data-level 零交集收据。

下一步不应继续在这份 outer test 上挑模型。应先修成 train/dev + 一次性 future frozen cohort，再决定新的 GPU 矩阵；在用户批准
精确模型×seed×GPU·时之前不启动长训练。
