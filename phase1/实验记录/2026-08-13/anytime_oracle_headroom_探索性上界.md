# Anytime oracle headroom：冻结 v9 发现集的探索性上界（2026-08-13）

状态：**探索性 hindsight 描述**。它使用最终 `graded` 构造不可实现的完美 oracle，只回答“改善早期
外部分数覆盖是否仍有足够理论成本空间”，不是方法结果、不是实际 speedup，也不参与显著性检验。

## 1. 锁定输入与总体

- `fidelity_manifest.jsonl`：
  `77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef`；
- `fidelity_results.jsonl`：
  `b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d`；
- `fidelity_runtime_v9.jsonl`：
  `dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7`；
- `card_run_map.json`：
  `3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30`；
- `task_orientation.json`：
  `e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a`。

总体固定为 100 sibling sets / 230 cards / 52 physical runs / 19 tasks。主脚本拒绝覆盖已有输出；
独立 verifier 不导入主实现，从五份 raw input 逐 card 重算全部用于解释的 aggregate。

## 2. 结果

120 秒时有 finite pristine score 的候选为 86/230，silent/missing 为 144/230。两组历史完整执行时长
分布高度不同：

- observed：median=86.2466 秒，固定 nearest-rank Q25/Q75=[49.6182,145.8371]；
- missing：median=1323.1667 秒，固定 nearest-rank Q25/Q75=[690.4440,2937.7804]；
- 100 个 sibling sets 中，68 个 set 的全部 final winner 在 120 秒都仍 missing。

冻结的 censor-aware policy 在 120 秒保留全部 missing，只淘汰被另一 observed score 严格支配的
observed candidate：淘汰 44/230=19.1304% cards，却只覆盖 3.3579% 历史完整 runtime；扣除已经付出的
probe 后，optimistic avoidable tail 仅 2.6163%。

不可实现的 `perfect final-score-at-120` hindsight oracle 直接保留最终最优（含 tie），可淘汰
129/230=56.0870% cards，对应 54.4226% 历史完整 runtime；optimistic avoidable tail=51.2644%。
在理想 resume 口径下 cost ratio=0.487356；把 120 秒 probe 当额外开销并对保留候选从头 restart 的
悲观口径下 ratio=0.514381。

独立复核打印：

```text
ANYTIME_ORACLE_INDEPENDENT_VERIFY_PASS sets=100 observed=86 missing=144 winner_all_missing_sets=68 current_tail=0.026163 oracle_tail=0.512644
```

复核器第一次失败不是数据/结果冲突：它错误要求全语料 `card_run_map.json` 的键集合恰好等于冻结
230 cards。修正为“冻结 cards 必须全部被覆盖，允许 map 有额外全语料键”后通过；失败历史保留在记录中。

## 3. 允许与禁止的解释

允许：旧 120 秒策略几乎没有成本杠杆，主要原因不是“分数无价值”，而是高成本候选恰好经常没有
早期分数；如果能让高成本候选更早暴露**候选特异、pristine 可评分**的中间 artifact，理论上存在很大
剩余空间。这为 late-artifact pilot 与 schema-first/probe-first operator 提供了优先级依据。

禁止：

- 不能声称已经节省 51.26% GPU 时间；oracle 偷看了 final grade；
- 不能把历史 runtime 当成 continuation 的实测成本；
- 不能据此选择 120/240/600 秒阈值或在旧 100 sets 上调 selector；
- 不能把 68/100 的 missing winner 解释为因果关系；它是发现集上的选择性缺失描述。

下一步只由 GPU outcome 前冻结的 late-artifact gate 决定：若至少两个不同任务在 120 秒后出现新的
可评分 artifact hash，保留 `TaskHazard`；若为 0 且无 grader-recovery ambiguity，则转向
schema-first/probe-first operator；其余为 `INCONCLUSIVE`。
