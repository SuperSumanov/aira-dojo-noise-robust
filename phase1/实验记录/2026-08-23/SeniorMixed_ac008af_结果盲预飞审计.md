# Senior mixed `ac008af`：结果盲预飞审计与 GPU 门裁决

日期：2026-08-23。作用域：学长 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69`
的四份 pair LFS 对象、mixed launcher 与训练源代码。审计只读 pair metadata 和代码；没有打开 Cards/code/grade、
prospective outcome 或模型输出，GPU job/API/model fit 均为 0。

正式裁决：`EXPLORATORY_ONLY_PROTOCOL_AND_REPRODUCIBILITY_BLOCKED`。学长已报告的 value scaling 仍是有价值的
探索信号；本裁决只说明当前 mixed commit 不能直接升级为确认性长实验。

## 1. 数据层的正面事实

独立脚本对四份已物化 LFS pair 文件重算：

| 文件 | rows | train/test | tasks | train/test endpoints | endpoint overlap | unordered dup/self |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed | 15,875 | 14,715/1,160 | 39 | 9,620/1,705 | 0 | 0/0 |
| decision | 7,644 | 6,484/1,160 | 39 | 5,672/1,705 | 0 | 0/0 |
| hardware/time value | 8,598 | 7,703/895 | 39 | 6,274/954 | 0 | 0/0 |
| batch value | 16,204 | 14,206/1,998 | 39 | 9,165/1,884 | 0 | 0/0 |

Mixed 的 test 最大任务是 leaf-classification，105/1,160、share=`0.09051724137931035`。因此 pair 层面没有
endpoint train/test overlap、重复 pair、自比较或单任务支配这一类显眼错误。

Mixed train 由 13,312 value rows 与 1,403 decision rows 构成，value share=
`0.9046551138294258`；整个文件另保留 1,160 条 decision test。这个配比可以作为探索 arm，但不能在没有固定
builder command/weights 的情况下解释为“mixed objective 本身”的可复现实验。

## 2. 四个阻断项

### 2.1 launcher 当前会直接失败

四个模型都引用 `decision_value_mixed_pairs_filtered_runsplit.jsonl`，而提交的真实对象名是
`decision_global_local_value_mixed_filtered_pairs_runsplit.jsonl`。前者不存在。只改文件名能让程序启动，不能解决
以下科学协议问题。

### 2.2 1,160 条 test 是旧 decision test，且训练期反复读取

Mixed 的 1,160 条 test 与 `merged_decision_pairs_filtered_runsplit.jsonl` 的 test 在顺序和 multiset 上都逐 pair
完全相同。训练代码把 `load_testing_pool(...)` 的结果直接赋给 `validation_records`，launcher 每 10 optimizer steps
评估一次；配置同时使用 `save_strategy="best"`、`metric_for_best_model="eval_pair_accuracy"` 和
`greater_is_better=True`。即使 `load_best_model_at_end=False`，test 曲线与“best checkpoint”元数据仍受 test 指导。

这不是“test 行进入梯度”的指控；它意味着该 test 已不是一次性 frozen confirmation，任何 best/final 选择都只能按
探索性结果报告。

### 2.3 experiment identity 仍未闭合

pair endpoint overlap=0 不等于 experiment-closed。0CR 的结果盲审计已经证明旧 test 的 87 个 experiments 中，49 个
与 train role、11 个与 dev role 重叠；而 676 个匿名 runs 的真实 source-batch join 仍有 32 ambiguous、8 missing、
2 个 archive errors，正式状态为 `IDENTITY_UNAVAILABLE`。不能通过结果后过滤、日期/config 代理或只保留可 join 子集
追认现有曲线。

### 2.4 生成与 checkout 都未完全可复现

仓库 `src/` 与 `docs/` 中没有出现真实 mixed 输出文件名，因此没有固定的 builder command、seed、输入 SHA、sample
weights 或 dedup receipt。当前物化文件显示 train 的 90.47% 是 value，但为什么是这一比例无法从提交重建。

完整 fresh checkout 还会在 Cards 对象
`5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343`（779,146,574 bytes）处收到
GitHub LFS 404。四份小 pair 对象可单独拉取，但没有 Cards 仍不能从干净 clone 启动训练。

## 3. 额外混杂与工程风险

同一 commit 同时改变了训练输入 prompt（给每个 Card 增加预测指令前缀）、mixed 数据目标和 ZeRO parameter offload
设置；因此即使跑通，也不能把变化唯一归因于 mixture。`read_cards` 的输入类型校验与 `gap_filter` 的有限数/非负数、
原子写入等保护也被削弱；新增 mixed/hardware-time 代码没有相应测试。桌面环境缺少 torch/scipy/jsonschema，无法把
完整 upstream suite 的收集失败误报成代码测试失败；本审计脚本自己的 focused synthetic tests 为 3/3。

## 4. 解锁顺序

1. 学长 producer 侧发布不可变 `run_id -> source-date,batch-id,task,archive-sha256` manifest，并替换 0CR 指出的
   0811/0812 leaf 和 0730/0809 异常 archive；先让所有身份与 archive 门全过。
2. 固定 mixed builder command、输入 SHA、seed、抽样权重与 dedup receipt；train/dev/frozen 三个 role 必须由
   experiment identity 分组，不能复用旧 test。
3. 训练期间只读 dev；先冻结 checkpoint，再由独立 one-shot evaluator 打开全新的 frozen test。逐 pair receipt 必须
   带 task/run/experiment cluster，统计以 task/experiment clustered CI 为主。
4. 把 prompt、数据 mixture 与 ZeRO/offload 分成独立提交；确认实验只改变一个科学旋钮，并恢复输入校验和 focused tests。
5. 修复 Cards LFS 可用性，并从 fresh no-cache clone 完成一次 materialization + SHA 验证。

上述门全部通过后，再先提交一项 dev-only G0 预算校准；用实测 wall time报价模型×seed矩阵和总 GPU·时，另行获批。
在此之前不启动当前 mixed GPU launcher。

## 5. 证据

- `phase1/audit_senior_mixed_dataset.py`；
- `phase1/tests/test_audit_senior_mixed_dataset.py`；
- `phase1/results/senior_mixed_ac008af_audit_20260823/formal_receipt.json`。
