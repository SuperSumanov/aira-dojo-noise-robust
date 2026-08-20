# Clean Direct-Decision：run-split 支持门失败裁决与 component-split v2 预注册

日期：2026-08-21。状态：`V1_INELIGIBLE / V2_PREREGISTERED_NOT_RUN`。本文件写于 v1 outcome-free
结构统计揭晓之后、v2 component split 的任何支持度统计之前。到此为止 GPU/API/model fit/model download 均为 0。

## 1. v1 失败裁决，不放宽阈值

固定 input、seed=`20260821`、dev fraction=`0.10` 的 physical-run sampler 完成 producer×2、独立
verifier×2，全部 byte-identical，聚焦测试 33/33。它得到 train/dev/test=`4532/223/931`，三者 Card、
physical run、unordered pair overlap 全为 0；dev 覆盖 28 tasks，dominant share=`0.1031390134529148`，
Improve=`149`。但 dev 总数 223 低于事前 300，Draft=`74` 低于事前 100，因此固定状态为
`STRUCTURAL_PREP_INELIGIBLE`。原 G0/G1 不解锁；不能改 dev fraction、seed、任务、语义子集或阈值追救。

另有 485 个 outer-train pairs 因 endpoint runs 被分到两侧而丢弃，全部为 Draft。该事实揭示的是 split unit
错误，而不是模型效果：Draft choice set 跨 physical runs 构造；若独立抽每个 run 进入 dev 的概率为 `p`，一条
跨-run Draft edge 两端都进 dev 的概率约为 `p^2`，另有约 `2p(1-p)` 的边跨界后必须丢弃。于是 10% run-dev
并不产生 10% Draft-pair dev，并且改变 Draft/Improve mixture。v1 失败 bundle：

- `/research/d7/spc/yzyang4/critic-decision-clean-prep/11c9a39-baf6bdd-v2.tar.gz`；
- SHA-256=`d4b0363162693ad4525af77c7275257ddff38dc4aaa2523b3a9fdafb53c9810c`。

## 2. v2 不是阈值追救：把泄漏不可分单元定义正确

v2 保持所有 input、seed、target fraction 和 v1 数量/平衡门不变，只把切分单元从“单个 physical run”改为
**outer-train pair graph 的 connected component**。这是由零 endpoint/run leakage 与零 pair deletion 联合推出的
最小不可分组：节点是 physical runs；每条 pair 连接两个 endpoint runs，同-run pair 是自环。任何 component 若被
拆开，至少一条 pair 就跨 split；component 整体归属一侧则所有 endpoint/run/pair 天然不泄漏且无需删边。

固定 producer 算法如下：

1. 只读 outer-train rows；outer-test 原序逐字节物化为 dedicated held-out file，不参与 component 选择。
2. 按 task 在 physical-run graph 上做 union-find；每个 component 的权重是其包含的 outer-train pair 数。
3. 对每个至少有两个 components 的 task，用动态规划在所有非空、非全集 component 子集中，选择 pair-weight 最接近
   `0.10 × task pairs` 的 dev 子集；目标差相同时先选较小 pair-weight，再按
   `SHA256(seed, task, sorted run IDs)` 的 component 顺序作字典序 tie-break。只有一个 component 的 task 全留 train。
4. component 内所有 pair 原样进入同一侧，只新增 `outer_intask_split=train`、协议名、seed 与 target fraction
   receipt；不得按 better/worse、gap、code、grade、client 或任何模型输出选 component。
5. 独立 verifier 不 import producer，重建 union-find、DP、每一行与所有哈希；producer×2、verifier×2 必须
   byte-identical。

## 3. v2 固定支持门与停止条件

沿用 v1 的全部门，不利用已见的 223/74 调低：train `>=3800`、dev `>=300`、原 cross-split drop 上限 25%、
dev tasks `>=20`、dominant task share `<=0.20`、dev Draft/Improve 各 `>=100`、held-out test 恰 931，且
train/dev/test Card、run、pair overlap 全为 0。v2 额外加强为 outer-train pair **零丢失**、每个 component 只属于
一侧、所有 source/output/hash exact。

若任一门失败，状态为 `COMPONENT_SPLIT_INELIGIBLE`，本轮 clean direct-decision GPU 路线关闭；不再设计第三种
split。若全过，只得到 `COMPONENT_SPLIT_ELIGIBLE_FOR_G0_PROPOSAL`：仍不代表已获 GPU 授权，G0 的 1 run / 2 GPUs /
10 steps / hard cap 4 GPU·h 与 G1 的 8 runs 仍按前一预注册等待明确批准。

## 4. 证据边界

component split 是 benchmark integrity/data protocol 修复，不是新 RM 方法，也不保证 Qwen scaling 为正。v1 的失败
必须与 v2 一起保留；论文若使用 v2，应报告为何普通 run sampler 对跨-run preference graph 产生语义比例偏移。
任何后续正结果仍限于 retrospective clean model support，不能写成 prospective 或真实 search utility。
