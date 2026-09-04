# G-reuse 对 local decision context 的覆盖与连接：结果前预检

日期：2026-09-05。范围：0L22 后的历史 train-only 结构机制检查；不修改 0L23 效果路径。

## 1. 问题与目的

已有 rank/谱结果仍可能只说明 endpoint graph 更连通，却没有触及足够多的 local sibling 决策组。本实验检验
full G-reuse 是否跨 parent context 连接广泛的 local 决策，以及预先冻结的 spectral50 是否保留大部分这种触达。

## 2. 假设与 estimand

local row 的 `(task,parent)` 定义一个 decision context。每个 local endpoint 必须唯一属于一个 context，否则
fail-closed。G 边两端属于不同 context 时才增加 parent-context graph rank。主要 estimand 是 full 的 context
覆盖、local-pair 触达与 parent-rank 广度，以及 spectral50 相对 full 的保留率；不是模型 accuracy。

## 3. 输入与 population

输入及 SHA 与 0L22 完全相同：历史 train L、历史 G、grouped Cards、batch/source 投影、16K cached token lengths。
使用既有 2,745 条 record-consistent G-reuse、790-edge basis 和冻结 spectral50 规则。不得读 dev/test/vault、
first960、Target300/522、score、prediction 或代码正文；不得输出 task/parent/run/card/edge 身份。

## 4. arm 与公平

只比较 `basis`、`spectral50=basis+冻结中点选择`、`full`。三臂使用同一 L graph、context 映射和 token 成本；
spectral50 仍从 basis 开始、逐任务 `floor((full-basis)/2)` 额外上限和 15 位量化
`log1p(R_eff)/token`，不得重选 25%/75%。

## 5. 指标与结果前 gates

全部成立才称 `G_REUSE_DECISION_CONTEXT_REACH_STRUCTURALLY_SUPPORTED`：

1. local=4,689、full=2,745、basis=790、spectral50=1,811；每个 endpoint 唯一映射一个 context；
2. full 跨 context 边占比至少 0.90；
3. full 至少触达 0.60 的 local contexts，且至少双端触达 0.20 的 local pairs；
4. full 在至少 20/28 tasks 有正 parent-rank gain，最大单任务 rank-gain share 不超过 0.20；
5. spectral50 保留至少 0.75 的 full parent-rank gain、0.80 的 full context coverage、0.75 的 full
   双端 local-pair coverage；
6. spectral50 G-stage valid-token 相对 full 至少减少 0.25。

这些阈值不得结果后降低。basis 只作描述，不设救回门。

## 6. 资源与 ETA

CPU 单进程；producer A/B、独立 verifier A/B 各不超过 300 秒，BLAS 线程 1。预计正式 8--15 分钟，
实现/测试/复验 45--75 分钟。GPU=0、API=0、model fit=0、底座更新=0。

## 7. 随机性与统计单位

无随机 seed。A/B 是复现检查而非独立样本。task 只用于广度/集中度，不报 p 值，不把 edge 或 parent 当独立标签。

## 8. 划分与泄漏

只读历史 train；Python audit hook 禁网络、子进程、未列数据和写入。受保护 cohort 打开数必须为 0。
历史来源缺陷仍保留，结果不能升级为 effect-eligible。

## 9. 复现与独立验证

结果前 commit；完整输入/源码 SHA；producer 两次 byte-exact；verifier 不 import producer，使用 grounded
Laplacian 重建 spectral50；下载后 archive/manifest/credential/身份字段与 producer-verifier 指标独立核验。

## 10. 失败与重试

未知 parent 多重归属、计数漂移、数值选择差异、哈希/访问/manifest 异常均 fail-closed。仅工程 bug 可在保留失败根、
提交最小修复后用新根重跑；科学门失败不得改阈值或换预算点。

## 11. 可说与不可说

若通过，只能说 G-reuse 对 local decision contexts 的结构触达/连接广泛，且 spectral50 保留大部分并降低 token；
不能说模型利用了这些边、accuracy 提升、执行成本归零或算法首创。若失败，0L20--0L22 的图结果仍保留，但不能再称
它直接覆盖 local decision contexts。
