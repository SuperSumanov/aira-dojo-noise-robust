# Parent-relative transition OOF：正式裁决

- 正式代码 commit：`e8eb25cf2540303c9fddd53bebfb23b2c5a0f3a5`
- 数据：5,240 pairs、28 tasks、1,711 parents、152 parent-closed supercomponents、5 folds
- 正式状态：`NO_ROBUST_TRANSITION_GAIN_VERIFIED`
- 结论：父相对 edit-shape 产生了方向一致且接近门槛的增量，但预注册的 task/parent 双 CI 门没有全部通过，
  因而不能称稳健正方法结果。

关键结果：

| subset | child-only task macro | child+transition task macro | task delta (95% task CI) | pair delta (95% parent CI) |
|---|---:|---:|---|---|
| merged | 0.529716 | 0.546841 | +0.017125 [−0.000013, +0.035410] | +0.011832 [−0.003403, +0.027366] |
| Draft | 0.533768 | 0.540188 | +0.006420 [−0.011728, +0.025304] | +0.004068 [−0.014908, +0.023025] |
| Improve | 0.503540 | 0.539699 | +0.036159 [+0.003552, +0.069032] | +0.023973 [−0.001487, +0.049611] |

merged 的 task CI 下界只低于 0 约 `0.0000128144`，parent CI 下界为 −0.003403；Improve 的 task CI
已高于 0，但 parent CI 下界为 −0.001487。merged 的 28 个 leave-one-task-out 点估计全部为正，最小
+0.012468。child+transition 在 merged 与 Improve 的 task/parent chance CI 均高于 0.5。尽管这些是有价值的
方向性证据，冻结门要求 paired task 与 parent CI 同时高于 0，故正式 no-unlock 裁决不能改写。

控制与完整性全部通过：三个 learned arms 全覆盖、无 ties、反对称误差为 0；orientation/random、5-fold
endpoint/run/parent/component isolation 全部通过。producer×2 与不 import producer 的 full-refit verifier×2
逐字段一致；51-entry manifest 全部通过，11 个 diff/stderr 均为空，目录不可写，安全扫描为 0；focused tests
13 passed，phase tests 568 passed。

完整只读产物：`/research/d7/spc/yzyang4/critic-transition-static-oof/e8eb25c-v1`。
`output_manifest.sha256` 自身 SHA256：
`f2945f22c5bdd1741275d3468756727a78d6d48922b9e2cfa1f866df50193639`。

停止边界：不在同一 5,240 pairs 上修改 edit features、模型、阈值或裁决门追救。若将这个**完全冻结**的 arm
加入未来 outcome-unread scorer escrow，必须另立协议、保持 extension 身份，并不得回填当前正式状态。
