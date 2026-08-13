# Heterogeneous Run-OOF：长实验 13 项预检

协议：`heterogeneous_oof_v11_discovery_v1`。本文件与预注册、producer、独立 verifier 一起在 outcome
前 commit。正式 launcher 只有全部 13 项通过才运行 producer。

## 固定矩阵与预算

每个 5-fold outer physical-run fold 拟合 `op_only_lr/static_lr/static_gbm/char_tfidf_lr`，共 20 fits；
producer 完成后独立 verifier 从源 cards 全量 refit 同样 20 fits，总计 40 fits。另有 1 fold outcome-free
engineering smoke（4 fits）。全部 CPU，无 GPU、无 API、无底座更新。formal producer+verifier 总硬上限
3,600 秒；launcher 外层总硬上限 4,200 秒。checkpoint 按 fold 原子提交，可在同 commit、同输入 hash、同
协议 checkpoint key 下 resume。

## 13 项

1. **artifact/knobs**：记录 git commit、源码 hash、固定 arm/grid/seed 与 output root；Git worktree 必须干净。
2. **cheap tests**：producer/verifier/smoke `py_compile`；完整定向 pytest；两个 `--help` 独立检查 rc。
3. **pair/forbidden path**：producer/verifier CLI 不得出现 frozen/test/held pair 参数；全部科学输入文件名通过 guard。
4. **distribution**：重算 exact 4,263 pairs / 333 runs / 23 tasks / 2,293 parents / 5,499 endpoints / 2,259 complete parents。
5. **balance**：锁定 outer fold 均有至少 66 runs；报告 dominant task；不按 outcome 重加权或挑任务。
6. **checkpoint/resume**：每 fold 保存 float64 endpoint score；fold summary 绑定 checkpoint key 与 score SHA；
   stale key、损坏 SHA、半完成 tmp 均 fail closed。
7. **leakage**：复核已有 train-held run/node/raw-code-hash 三层交集为 0；每 outer fold train/valid run 与 endpoint
   交集必须为 0；source cards loader 只保留 manifest train endpoint 的 code/task/run/lineage allowlist。
8. **RNG/numerics**：seed=887；对称正负训练样本；固定 solver/tolerance；所有 fit accepted、score finite；
   random control 与 orientation oracle 必须通过。
9. **secrets**：运行精确 staged filename 命令
   `git diff --cached --name-only | grep -icE 'env|key|token|secret'`，要求输出 0；另扫高置信内容；正式输入不含 `.env`。
10. **wall-clock smoke**：真实全量 train input 上跑一个完整 outer fold；不计算 accuracy/selection metric；按
    producer+verifier 10 folds ×1.5 外推，须低于 3,600 秒，同时记录 RSS。
11. **power/utility**：这是全量 4,263 pair、2,259 complete-parent discovery，不是小样本 smoke；效果门、双聚类
    CI、任务一致性与互补性门已在 outcome 前固定。
12. **true rc**：producer 与 verifier 的 rc 在任何后续命令前立即捕获；非零即终止，不生成成功标记。
13. **append-only hashes**：逐项重算 pairs/run-map/cards/manifest/baseline SHA；output root 已有 completed summary
    时拒绝覆盖；结束后创建全文件 manifest。

## Fail-closed

任一项失败不得进入正式 producer；工程 smoke 产生的 score 不读、不打印、不进入 gate。producer 成功但 verifier
失败时状态为 `INVALID`，不得据 producer 的 headline 做科学解释。冻结 pair 文件在任何状态下都不由本链读取。
