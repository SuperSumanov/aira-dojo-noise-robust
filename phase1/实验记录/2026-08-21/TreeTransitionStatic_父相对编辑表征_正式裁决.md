# TreeTransitionStatic：父相对编辑表征正式裁决

日期：2026-08-21。正式状态：`NO_ROBUST_TRANSITION_GAIN_VERIFIED`。

## 1. 一句话裁决

父相对 edit-shape 是目前方向最一致的廉价正向信号之一：merged task-macro 提升 +1.712 pp，canonical
Improve 提升 +3.616 pp，merged 的 28 个 leave-one-task-out 点估计全正，且 combined arm 本身在 merged/
Improve 的 task 与 parent CI 均高于 chance。但预注册要求增量的 task/parent 两类 CI 都严格高于 0；merged
两类下界为 −0.000013/−0.003403，Improve 的 parent 下界为 −0.001487。因此正式状态必须是 no-unlock，
不能称稳健方法突破。

## 2. 结果

| subset | child-only task macro | child+transition task macro | task delta / 95% CI | pair delta / parent 95% CI |
|---|---:|---:|---|---|
| merged | 0.529716 | 0.546841 | +0.017125 / [−0.000013,+0.035410] | +0.011832 / [−0.003403,+0.027366] |
| Draft | 0.533768 | 0.540188 | +0.006420 / [−0.011728,+0.025304] | +0.004068 / [−0.014908,+0.023025] |
| Improve | 0.503540 | 0.539699 | +0.036159 / [+0.003552,+0.069032] | +0.023973 / [−0.001487,+0.049611] |

merged/Draft/Improve 的最小 leave-one-task-out task-macro delta 分别为 +0.012468/+0.000960/+0.028428。
所以结果不是由一个任务单独翻正；失败来自 cluster uncertainty，而不是方向性点估计。transition-only 是预指定
机制消融：merged task delta 仅 +0.004820，task/parent CI 都跨 0；组合 arm 的方向更强，说明 child state 与
transition shape 的互补比单独 edit magnitude 更有希望，但这只是解释性线索。

## 3. 完整性

输入、矩阵与 fold SHA 均与 outcome-blind 预检一致；5 folds 的 endpoint/run/parent/component/supercomponent
交集为 0。三个 learned arms 全覆盖、无 ties、反对称误差 0；orientation/random 控制全过。producer×2 与
不 import producer 的 full-refit verifier×2 逐字段一致。51-entry manifest 51/51 通过，11 个 diff/stderr
为空，可写文件 0，安全扫描 0；focused tests 13 passed，phase tests 568 passed / 25 warnings。

正式代码 commit=`e8eb25cf2540303c9fddd53bebfb23b2c5a0f3a5`。完整只读产物位于
`/research/d7/spc/yzyang4/critic-transition-static-oof/e8eb25c-v1`；manifest 文件 SHA256=
`f2945f22c5bdd1741275d3468756727a78d6d48922b9e2cfa1f866df50193639`。Git 紧凑证据位于
`phase1/results/critic_transition_static_oof_20260821_e8eb25c/`。

## 4. 停止与正方向解释

不在同一 5,240 pairs 上修改 features、模型、阈值、bootstrap unit 或门来追救，手工 transition 方法线按正式
规则关闭。这个结果仍留下一个严谨的正方向候选：把当前 68 维 arm **原样冻结**，在尚未揭盲、与训练物理 run
完全独立的 future scorer escrow 中只作 extension。该动作若实施，必须另立协议、先锁 full-fit model/hash 和
predictions，再等待既有 closure；不能改变 first-960 primary，也不能把未来显著性回填成本次预注册成功。
