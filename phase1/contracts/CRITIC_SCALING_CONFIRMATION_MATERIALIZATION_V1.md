# Clean scaling confirmation materialization v1

状态：`MATERIALIZER_READY_SYNTHETIC_ONLY_REAL_TRUTH_FORBIDDEN`。本实现不授权 GPU、API、模型拟合或真实 future
truth 读取；截至本记录只在合成 Cards/pairs/receipts 上运行。

## 三个不可混用的阶段

1. `truth`：在 checkpoint test access 前，从精确 SHA 锁定的 dedicated test pairs 与 Cards 生成 canonical truth。
   它拒绝非 test、非 `canonical_raw_sibling`、跨 run、lineage 不一致、重复/反向 edge、混 budget、非有限或方向不一致
   的 grade；同 parent 的 pair graph 取零丢弃 maximal connected components，component ID 与 pair ID 均按 canonical
   JSON 做 SHA-256。这个阶段会打开标签，只有另行授权后才能对真实 cohort 执行。
2. `model-prediction`：不重新评分，只把 upstream `rm-one-shot-test-v1` 的 endpoint receipts 规范化。它同时绑定
   truth/lock/source output/source ledger/checkpoint manifest，要求 pairs/Cards 哈希来自 truth source、逐 checkpoint
   artifact 哈希一致、output/ledger 路径已在 test 前锁定、pair_index 全覆盖且同 endpoint 分数一致。
3. `bundle`：不复制、不修改 result row，只把已经位于同一 non-symlink root 的 truth、baseline、8 个 model
   predictions 与 ledgers 组装成 analyzer 接受的相对路径 bundle；路径逃逸、矩阵缺失/重复、hash/rows/ledger 不一致
   均 fail closed。

`phase1/verify_critic_scaling_confirmation_materialization.py` 不 import 上述 adapter，以第二套 Cards/pairs parser、图连通
算法、canonical IDs 与 one-shot 映射分别验证 truth source binding 和 model source binding。最终 bundle 还会再经过
原有、同样不依赖 materializer 的 frozen analysis verifier；source 与 metric 两层错误不能靠同一实现自证。

## test 前 lock 的额外交付字段

这些字段加固交付身份，不改变冻结 contract 的矩阵、estimand 或 gate：

```json
{
  "dataset": {
    "truth_sha256": "...",
    "truth_rows": 1,
    "pairs_sha256": "...",
    "cards_sha256": "..."
  },
  "runs": [{
    "checkpoint_manifest_sha256": "...",
    "one_shot_output_path_sha256": "sha256(abs_path_utf8)",
    "one_shot_ledger_path_sha256": "sha256(abs_path_utf8)"
  }]
}
```

checkpoint manifest 的 protocol/status 必须是
`critic-scaling-checkpoint-manifest-v1/LOCKED_BEFORE_TEST_ACCESS`，并含 model size、seed 与实际评估 artifact 哈希。
同一路径不可覆盖的 upstream ledger 加上 prelocked path identity，使换文件名重试不能进入正式 bundle。

## 当前验证边界

- materializer + independent source verifier focused：18/18；
- 与 analyzer/endpoint overlay 联合聚焦：另有 10/10；
- 合成 bundle 已被冻结 analyzer 完整接受；
- 本机 full phase1 collection 因环境缺 `scipy/sklearn` 阻断，不把它记作通过；集群 exact commit
  `81a09d53...` 的正式依赖环境完整回归为 848/848（33 warnings），focused 25/25，secret scan 0/0，证据见
  `phase1/results/critic_scaling_materializer_20260823_81a09d5/`；
- real future truth/GPU/API/model fit：`false/0/0/0`。

独立 verifier 的集群 exact code commit `2a49d4cf...` 已通过 focused 28/28、full phase1 851/851（33 warnings）、
secret scan 0/0、worktree clean；证据见
`phase1/results/critic_scaling_materialization_verifier_20260823_2a49d4c/`，没有沿用前一个 848-test receipt。

这项交付只消除“即使未来 scaling checkpoint 到了也无法严谨生成 component utility bundle”的工程阻断，不是模型
效果，也不能抬高当前 scaling 结论等级。
