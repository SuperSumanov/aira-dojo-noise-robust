# Senior augmented scaling：接入审计与无泄漏修复协议

日期：2026-08-19。审计对象：`myfork/dojo-reproduce` commit
`92a9651f2e13a9e43623235b82c07c19721bc2ee`（commit title：`exp level split shows scaling effect`）。
本文件只做代码/证据接入审计，不读取或改写模型 checkpoint，不启动 GPU/API。

## 当前可确认的事实

1. 新提交加入 augmented run-grouped cards、gap-filtered runsplit pairs、8B launcher、context 测量与三个 light
   predictors；LFS pointers 分别绑定 cards 604,190,866 bytes、pairs 6,025,690 bytes、runsplit 118,448 bytes。
2. `load_training_pool` 只选择 `intask_split=="train"`，`load_testing_pool` 只选择
   `intask_split=="test"`。所以 frozen test rows **没有进入梯度训练池**；用户此前验证的 train/test 零交集没有被
   本审计推翻。
3. 但 `bradley_terry.py` 把 testing pool 直接设为 Trainer `eval_dataset`；augmented launcher 固定
   `--eval_steps 10`。因此 frozen test 每 10 optimizer steps 被反复读取，不能再称未触碰 final test。
4. `BradleyTerryConfig` 同时设置 `metric_for_best_model="eval_pair_accuracy"`、`save_strategy="best"` 与
   `greater_is_better=False`。准确率语义应越大越好，当前配置会把较低准确率当作 best；而
   `load_best_model_at_end=False` 又使内存中的 final model 与磁盘唯一保留 checkpoint 的语义可能不同。
5. 当前 launcher 只有 Qwen3-8B 臂实际执行，0.6B/1.7B/4B 均被注释。commit 内没有新增
   `docs/outcomes`、逐 run/seed CSV、训练日志哈希、checkpoint receipt 或 one-shot evaluator receipt。故仅凭 commit
   title 不能复核“scaling effect”的定义、矩阵、seed、checkpoint 或数值。
6. 0817 outcome 文档已明确：此前 0.6B--8B decision final 均约 0.50--0.52，value final 约 0.59--0.60，未见
   model-size scaling。`92a9651` 若有新发现，必须作为 augmented-data 的新 exploratory result 单列，不能覆盖旧结论。

## 当前裁决

状态为 **`EXPLORATORY_SCALING_CLAIM_AWAITING_ARTIFACTS_AND_CLEAN_EVAL`**。它不是“测试样本进了梯度训练”的
泄漏指控；问题是 frozen test 被重复用作 validation/checkpoint/人工停跑信号，以及 best-metric 方向错误。
现有 checkpoint 即使数值很好，也只能作为 exploratory，不得在同一 frozen test 上重选后追认 confirmatory。

## 唯一允许的修复协议

1. 从现有 `intask_split==train` 的 physical runs 内，按 task 建立一次性 SHA-hash train/dev split；原
   `intask_split==test` runs 全部排除，旧身份不漂移。
2. pair 只有两个 endpoints 都落在 train runs 才可训练；都落在 dev runs 才可 validation；跨边界 pair 丢弃。
   保存 code-free run manifest、pair counts、task/client support 与独立 verifier。
3. Trainer 的周期 eval 只读 dev；显式 `greater_is_better=true`，并把日志字段改为
   `best_validation_pair_accuracy`。checkpoint 只由 dev 固定。
4. frozen test evaluator 必须是单独入口；在 training process 结束、checkpoint SHA 固定后只调用一次，并保存
   exact command、model/data/commit SHA 与一行一个 run/task 的结果。不得从 test 结果回头改 checkpoint、gap 或矩阵。
5. model-size scaling 的最低矩阵应在提交前另行批准：同一数据、同一 effective batch/epochs、至少 0.6B/1.7B/4B/8B，
   多 seed；主要比较 final/dev-selected one-shot test，而不是多次 eval 的 best。GPU·时必须单列，本轮不授权。
6. 学长现有日志应先原样写入 `src/mle_critic/docs/outcomes`，至少提供每个 model×seed 的 final/best、完成状态、训练
   commit、checkpoint/log SHA 和是否依据 test 曲线停跑；不要只保留 commit title，也不要在收据前删除 checkpoint。

在 GPU 重训获批前，可以先做 0 GPU 的 train-only dev support audit 与 light-predictor learning curve；它只能验证
数据可学习性/缩放趋势，不能替代 decision critic 或 search utility。
