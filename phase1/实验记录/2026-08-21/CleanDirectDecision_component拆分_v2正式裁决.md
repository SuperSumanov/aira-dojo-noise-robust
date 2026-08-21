# Clean Direct-Decision component split v2：正式裁决

日期：2026-08-21。正式状态：`COMPONENT_SPLIT_ELIGIBLE_FOR_G0_PROPOSAL`。科学 source=
`305355efacadbfbad493929cba3ff9e27bd6b5a3`，senior data commit=
`baf6bddefe62b769b2fab699ff5805dd627dc69f`。本轮 GPU/API/model fit/model download/prospective vault read 均为 0。

## 1. 失败链与为什么允许 v2

第一份 run-split launcher 用文件路径启动含 package-relative import 的脚本，在 producer 1、任何结构统计之前失败；
失败目录和回执保留。全新目录用 module 入口重跑后，producer×2、独立 verifier×2 均完成，但固定支持门正式失败：
train/dev/test=`4532/223/931`，dev Draft/Improve=`74/149`，485 个 source-train pair 被跨界删除，全部为 Draft。
总 dev `<300`、Draft `<100` 两门失败，因此没有放宽阈值或提交 GPU。

v2 是在任何模型 outcome 前修正 split unit，而不是调阈值：跨-run Draft preference edge 要同时满足零 run leakage 与
不删 pair，其不可分单元必然是 pair graph connected component。v2 保持固定 input、seed=`20260821`、target=
`1/10` 和 v1 全部门；每 task 用结果无关的 exact subset-DP 选择 component，只读取 endpoint/run/pair identity。

## 2. 正式支持结果

| 项目 | run sampler v1 | component v2 |
|---|---:|---:|
| train pairs | 4,532 | **4,689** |
| dev pairs | 223 | **551** |
| held-out test pairs | 931 | **931** |
| dropped outer-train pairs | 485 | **0** |
| dev Draft / Improve | 74 / 149 | **294 / 257** |
| dev tasks | 28 | **25** |
| dev dominant task share | 0.1031390134529148 | **0.147005444646098** |

v2 把 5,240 个 outer-train pairs 全部分配为 4,689 train + 551 dev，dev fraction=
`0.1051526717557252`；相对 v1 增加 328 dev、157 train，并消除 485 个删除。pair graph 有 168 components，
其中 41 个进入 dev；train/dev 为 430/81 physical runs。dev 覆盖 25 tasks，Draft/Improve=`294/257`，最大任务
ventilator 为 81/551=`0.147005444646098`，仍低于固定 0.20 门。Cassava、Facebook Recruiting 与 TGS Salt
各只有一个不可分 component，故按事前规则全留 train；没有为了凑 28 tasks 拆 component。

十个固定门全部为 true：train `>=3800`、dev `>=300`、零 pair drop、dev tasks `>=20`、dominant `<=0.20`、
Draft/Improve 各 `>=100`、test 恰 931，以及 train/dev/test Card、run、pair overlap 全为 0。held-out 文件 SHA=
`cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da`；train/dev SHA 分别为
`0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e` /
`3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4`。

## 3. 独立复核与复现

- producer×2 四个文件逐字节相同；
- 不 import producer 的 verifier×2 独立重建 union-find、component subset-DP、每行 receipt、manifest 与哈希，
  输出逐字节相同；
- structural gate×2 逐字节相同，聚焦测试 10/10；
- 每个 producer/verifier/gate exit status=0；单次 wall 分别约 8.37/8.39/6.41 秒，最大 RSS 约 1.40 GB；
- filename/content credential-shape scan 均为 0；
- bundle：`/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1.tar.gz`，
  SHA-256=`880dbe92607818fbeefd326ed2b0e48607523faec3ccd3722a167388062551b9`。

## 4. 可以与不可以声称什么

可以声称：跨-run preference graph 上按单 run 切 dev 会系统性缩小 Draft dev 并删除跨界边；在此固定 corpus 上，
component split 同时实现零泄漏、零删 pair 和足够的两语义 dev 支持。这是 benchmark integrity/data protocol 的
正面修复。

不能声称：critic 已提升、Qwen 已出现 scaling、held-out accuracy 已确认、真实搜索已改善，或 connected-component
group split 是通用算法首创。它只解锁 G0 的**申请资格**。G0 仍须按已冻结的 1 run / 2 GPUs / 10 steps /
最多 4 GPU·h 取得明确批准；G0 不读 held-out test。正式 G1 预算只能由 G0 实测推导后再次批准。
