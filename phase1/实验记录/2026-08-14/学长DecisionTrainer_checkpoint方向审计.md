# 学长 DecisionTrainer checkpoint 方向审计

日期：2026-08-14。性质：只读代码审计；没有修改或推送学长 `dojo-reproduce` branch。

## 发现

最新可见 commit `2cb6f0c` 把
`src/mle_critic/src/train/config/bradley_terry_config.py` 的
`metric_for_best_model` 从 `eval_loss` 改为 `eval_pair_accuracy`，但同一配置仍为：

```python
save_strategy = "best"
load_best_model_at_end = False
metric_for_best_model = "eval_pair_accuracy"
greater_is_better = False
save_total_limit = 1
```

Hugging Face Trainer 的官方定义是：`save_strategy="best"` 在出现新的 `best_metric` 时保存，
`greater_is_better` 决定指标越大还是越小才算更好：
<https://huggingface.co/docs/transformers/main_classes/trainer>。pair accuracy 显然应最大化，因此这组默认值
方向相反：后续 best-only checkpoint retention 会把更低的 `eval_pair_accuracy` 当作改善。

`train_decision.sh` 没有显式覆盖 `--greater-is-better`，所以默认风险真实存在。`load_best_model_at_end=False`
只表示训练结束不自动把 best weights 载回内存，不会把 `save_strategy="best"` 的比较方向变正确。

## 影响边界

不能用这个 bug 追溯解释 0812 模型规模结果。`DECISION_MODEL_SIZE_EXPERIMENTS.md` 明确对应较早 commit
`7528bbff4ef9868fb9066e780f9d48e55e54c763`，并从日志手工同时汇总最高与最后一次
`eval_pair_accuracy`；该文档本身由 commit `5f071ec` 加入。最新 `2cb6f0c` 的一行修改晚于这些日志。
因此：

- 0812 的“1.7B--8B 没有单调规模收益、final 约 55%”结论不能因此撤回；
- 风险只作用于采用 `2cb6f0c` 默认配置后新跑、并依赖 best-only 保存出来 checkpoint 的实验；
- 若新实验另有完整 step 日志，仍可从日志重算 best/final，但磁盘只剩的 checkpoint 可能不是最高 accuracy。

## 建议的最小修复与验收

在下一次 GPU 训练前把 `greater_is_better` 改为 `True`，并加一个零 GPU smoke：依次喂
`eval_pair_accuracy=[0.54,0.57,0.55]`，要求 best metric=0.57 且 retained checkpoint 对应第二次 eval；再用
`[0.57,0.54]` 验证下降不会覆盖。正式日志同时打印
`metric_for_best_model/greater_is_better/save_strategy/best_metric/best_model_checkpoint`。

修复只改变 checkpoint 选择语义，不应与训练数据、模型、seed 或超参改动混在同一 commit；否则后续无法
区分“配置 bug 修复”与“critic 方法提升”。
