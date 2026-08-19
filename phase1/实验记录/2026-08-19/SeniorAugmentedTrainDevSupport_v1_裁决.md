# Senior Augmented Train/Dev Support v1：裁决

## 复现

- 结果前 commit：`af51c8cefae81faeeafa34a673282949e99ad042`；
- 学长输入 commit：`92a9651f2e13a9e43623235b82c07c19721bc2ee`；
- 完整测试：`390 passed in 35.43s`；
- producer 双跑逐字节一致；summary SHA256=
  `7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8`；
- 独立 verifier 两次通过；verification SHA256=
  `205d89fa1b4db4cc7fec9fb52ae6b61bc467828c9a8a972f75c787b02b32d1e2`；
- numeric grade/frozen-test validation/model training/GPU/API/底座更新：0/0/0/0/0/0。

## 结果

- current inventory：676 runs / 28 tasks；
- 原始结构：11,946 train pairs / 1,574 test pairs / 0 split inconsistencies；
- 固定划分：148 test-hold runs / 92 dev runs / 430 train runs / 6 excluded low-support runs；
- dev：626 pairs / 23 tasks，最大任务占比 `0.16932907348242812`，9 个任务至少 20 pairs；
- full train：9,001 pairs / 26 tasks；
- nested curve：1,118 / 3,061 / 5,798 / 9,001 pairs，严格递增；
- dev same-experiment share=`0.9808306709265175`；
- full-train same-experiment share=`0.9213420731029885`，未达到冻结门 0.95；
- 跨 train/dev/excluded pairs=2,319，已按预注册丢弃。

除 `full_and_dev_same_experiment_share_ge_0_95` 外，其余十个资格门均通过。失败并非样本过少或 frozen-test
泄漏，而是训练配对中存在不可忽略的运行配置差异。

## 裁决

固定为 **`INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT`**。当前 augmented pair 文件不启动确认性 TF-IDF
learning curve；不得在已经看见结果后降低 0.95、只保留好看的任务/配置，或把过滤后的结果追认为确认性 scaling。

后续仅允许 outcome-blind 的配对生成诊断：定位 mismatch 来自 batch 混合、pair builder 还是 run metadata；随后把
exact `(task, client, hardware, time_limit, execution_timeout)` stratum 作为未来 pair-builder 的强制契约，写入
manifest 和 verifier。只有时间更晚、按该契约新建的 cohort 才可另立效果预注册。
