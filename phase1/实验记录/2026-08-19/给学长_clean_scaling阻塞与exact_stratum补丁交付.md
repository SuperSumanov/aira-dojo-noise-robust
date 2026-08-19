# 给学长：clean scaling 当前阻塞与 exact-stratum 补丁

## 一句话结论

现在不能从 augmented 8B 结果下“规模有/没有收益”的确认性结论；不是因为样本少，而是当前训练 pair 中混入了约
7.9% 跨运行配置比较，且 frozen test 被 Trainer 每 10 steps 反复 eval。两个问题都已定位，其中 pair producer 的
future-only 修复补丁已经完成并在 Linux 验证。

## 已核实的数据支持

你的 2026-08-18 snapshot（commit `92a9651f2e13a9e43623235b82c07c19721bc2ee`）结构上有：

- 11,946 train pairs / 1,574 test pairs；原 run split inconsistency=0；
- frozen test=148 physical runs，未进入 train/dev；
- 从 train runs 内固定哈希划分得到 9,001 full-train pairs / 626 dev pairs / 23 dev tasks；
- dev 最大任务占比 `0.16932907348242812`，样本量和任务覆盖足够。

问题是 full-train exact-config share 只有 `0.9213420731029885`：9,001 条中 708 条两端的
`(client, hardware, time_limit, execution_timeout)` 不同。708 条覆盖 8 tasks / 71 runs / 16 config transitions；
708/708 都来自同一解析出的 run family 和同一天。代码侧原因相符：当前 `build_subtree_pairs.py` 在 batch 内只按 task
组合，默认 batch 目录同超参，但没有机器检查。

## 已交付补丁

共享分支 `phase1-value-critic`：

```text
phase1/upstream_patches/0001-Enforce-exact-experiment-strata-6-focused-tests-pass.patch
```

- patch SHA256=`9f1445ae331846a4748cf82a41bebec7fd19fc28d28b4d8821c9f9333fa20f0a`；
- base=`92a9651f2e13a9e43623235b82c07c19721bc2ee`；
- Linux `git apply --check`、实际 apply、py_compile 全过；新增测试 `6 passed in 0.23s`；
- 在 shuffle/cap 前按 exact task+execution config 分层，仍保留原 per-task cap；
- pair 写 `experiment_stratum_sha256` 和 `batch_cards_sha256`；concat 前独立 verifier 逐条校验；
- producer 读取 batch cards 前先做 credential scan。

补丁没有直接推到你的 `dojo-reproduce`，避免覆盖你的工作。你审阅后可在兼容 commit 上 `git am`。它只用于未来
重建；不能过滤旧 708 条后把已经看过的 scaling 曲线追认为确认性。

## 训练侧还需同时修的两点

1. 目前 `intask_split==test` 虽未进梯度，但被直接作为 `Trainer.eval_dataset`，每 10 optimizer steps 都会读；因此它
   已不是 untouched final test。应在 train physical runs 内另切 dev，周期 eval 只读 dev；dev 固定 checkpoint 后，
   用单独 evaluator 一次性读 frozen test。
2. 当前 `metric_for_best_model="eval_pair_accuracy"` 配 `greater_is_better=False`，best checkpoint 方向反了；同时
   `load_best_model_at_end=False` 让 final 内存权重与唯一保留 checkpoint 语义不一致。accuracy 应设 true，并把
   dev-selected checkpoint SHA、step、seed 与 one-shot test receipt 保存下来。

## 下一轮建议

先把后续新 batch 用 exact-stratum contract 重建。数据达到支持门后，再冻结 0.6B/1.7B/4B/8B 的 context、seed、
训练 token/step 与 checkpoint rule；所有模型只看同一 train/dev，test 一次性评分。矩阵与 GPU·时仍需我们单独列出
后批准才跑。目前我方没有为了追正数启动新训练，也没有读取 frozen test 效果。
