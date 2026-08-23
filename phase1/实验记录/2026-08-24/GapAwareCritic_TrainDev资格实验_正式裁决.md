# Gap-aware critic：train/dev 资格实验正式裁决

日期：2026-08-24。正式状态：`RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK`。本实验是结果已见的 retrospective
dev 资格门，不是 frozen test、future confirmation、search utility 或方法首创。

## 1. 冻结问题与失败链

唯一问题是：在相同 component-clean train/dev、相同 char-TFIDF 与线性 Bradley--Terry critic 下，用 train-only
task-relative raw-grade gap 作为 pair 强度，是否同时优于 unweighted binary baseline 和保留每 task 完整权重 multiset、
但破坏 pair↔gap 对应的 hash-cyclic 负控。

合同 SHA-256=`f411c0f732df12158e8c683ddbb94cea107d7673b40b8305ee5b83c8219ef4f8`。首次 formal commit
`959764b22880d797b08a48f70654ff320b2b7d54` 在任何 Cards parse/model fit/dev aggregate 前，因把 dev 的合法
`intask_split="dev"` 错断言为 `"train"` 而 fail-closed。失败 root 原样保留，没有科学结果。唯一工程修复是 role-specific
schema 与 synthetic fixture；机器合同、输入、四臂、训练权重、统计门和 claim 均未改。

修复 commit=`b79717b3956a1b546943708a4c62e65841ffb663`。fresh no-smudge formal root：
`/research/d7/spc/yzyang4/critic-gap-aware-qualification/b79717b-v1`。

## 2. 正式执行与复核

- focused=`20 passed, 12 warnings`，完整 `phase1/tests`=`955 passed, 47 warnings`；
- producer×2 在不同 `PYTHONHASHSEED` 下逐字节一致；
- 不 import producer 的 verifier×2 各自重新读取源、重训四臂并逐字段复算，回执逐字节一致；
- independent-refit 最大数值差=`0.0`，producer/verifier diff 均为 0 bytes，所有 stderr 为 0 bytes；
- formal `SHA256SUMS` 自身 SHA-256=
  `49ab567a5fb109e2928b246d665859d2e3fdcef8cf675a25eac41004216988a9`；
- post-audit SHA-256=`3f3860366e90ff6b8a6e75eb4d9ce09d1583a409afead053adb860d4f01cf1ff`；
- outer held-out test、prospective vault、score-channel truth 与 test predictions 均未打开；GPU/API/base-LLM update=`0/0/0`。

支持门全部通过：25 tasks、246 released parent/groups、dominant-task parent share=
`0.0975609756097561`，train/dev pair 与 endpoint overlap 均为 0。

## 3. 冻结 headline

| arm | pair-micro accuracy | task-macro parent/group-macro accuracy |
|---|---:|---:|
| `binary_bt` | 0.6043557168784030 | 0.5102786098859761 |
| `gap_permuted_bt` | 0.6206896551724138 | 0.5324983224925042 |
| `gap_weighted_bt` | 0.6188747731397459 | 0.5289167039832994 |
| `gap_ridge`（non-rescuing） | 0.5753176043557169 | 0.5345622370769056 |

`gap_weighted_bt - binary_bt`：

- point=`+0.01863809409732331`，通过预设 `+0.015` 点门；
- task-bootstrap 95% CI=`[-0.02676049343489505,+0.066027790932867]`，失败；
- LOTO minimum=`+0.0070690023390327685`，通过；
- positive/zero/negative tasks=`12/5/8`，positive fraction=`0.48`，低于 `0.60`，失败。

`gap_weighted_bt - gap_permuted_bt`：

- point=`-0.0035816185092047113`，失败；
- task-bootstrap 95% CI=`[-0.04433344970163935,+0.0395666585234688]`，失败；
- LOTO minimum=`-0.013761716811285777`，失败；
- positive/zero/negative tasks=`10/5/10`，positive fraction=`0.40`，失败。

因此小幅高于 binary 的点估计不能归因于 pair 的真实 gap 信息：保留相同非均匀权重、但打乱 gap 对应关系的负控更高。
`gap_ridge`、pair-micro、gap-weighted utility 或语义 subgroup 都是预注册 non-rescuing diagnostics。

## 4. semantic structure postflight

第一次附加结构脚本错误要求所有 released groups 都是 physical-run siblings，得到 fail receipt；该文件原样保留，不能当作
corpus failure。冻结 estimand 本来已明确：Improve 是 physical lineage parent，Draft 是 synthetic cross-run released group。

修正后的独立 v2 对五个锁定输入逐 SHA 重建，状态为 `INDEPENDENT_SEMANTIC_STRUCTURE_PASS`：

- Improve：train `1787/1787`、dev `257/257` pairs 的 endpoints 与 parent 均在同一 physical run；
- Draft：train 2,902 rows / 109 released groups，dev 294 rows / 34 released groups；跨 run 是其既有构造语义；
- train/dev 共享 8 个 Draft parent groups，分别影响 139/29 rows；Improve parent overlap=0。

所以该 dev 是 pair/endpoint/run/component-clean，但不是 Draft-parent-novel；critic 不读取 parent ID，仍不能把这一限制省略。
这与 2026-08-21 已独立验真的 parent-context audit 完全一致，不改变本轮 `NO_UNLOCK`。

## 5. 裁决与后续

1. 关闭当前 dev 上全部 gap-weight/clip/Q75/阈值/超参重试；不按 Draft/Improve 或 hard/easy 子集 rescue。
2. 不创建 gap-aware future escrow，不改变已冻结的 component-breadth future hypothesis，也不授权 GPU replay。
3. 该结果作为“raw score resolution 并不会自动转化为 critic gain”的诚实 ablation 保留；它不是论文正方法主张。
4. 当前正向工作继续集中在 target-300 outcome-blind cohort、双 truth 测量合同和已冻结 component-breadth future prediction
   escrow；待 8 个新 archive 过稳定与 intake 门后按原协议自动推进。

完整紧凑证据位于 `phase1/results/critic_gap_aware_qualification_20260824_b79717b/`。
