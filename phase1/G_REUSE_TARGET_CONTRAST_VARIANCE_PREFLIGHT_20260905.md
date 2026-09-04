# G-reuse target-local contrast variance：结果前预检

日期：2026-09-05。状态：0L22之后的解析机制检验；尚未读取本项任何 variance 结果。
机器协议 SHA-256=`8c5b2f74cf7d84de899d2b8b00649564f450fb9517cc5978dcf68faa305460b5`。

## 1. 问题与可证伪假设

此前的 A-opt 指标平均所有同连通块节点对，不直接回答最终任务所关心的 local sibling decisions。
本项在单位方差、独立的线性 comparison-noise 模型下，计算每条目标 local edge 的
`b_e^T L^+ b_e`。固定 50% 额外 G-token 预算时，spectral selector 必须比 cheapest 和
SHA-order 同时降低目标 local contrast variance，且优势不能由少数任务贡献，才算机制正证据。

## 2. 输入与隔离

输入、SHA、2745 条 record-consistent full G、790 条 minimum-token basis、4689 条 local、28 tasks
及 16K cached valid-token 成本与 0L21--0L22 完全相同。只读历史 train 结构；禁止 dev/test/vault、
first960、Target300/522、真实 orientation/score/prediction、代码正文和候选身份输出。pair 文件中的
`better/worse` 只 canonicalize 为无向 endpoint edge，方向不得进入计算。

## 3. 固定 arms 与唯一 estimand

五个结构 arms 为 `basis`、`spectral50`、`cheapest50`、`hash50`、`full`。三条 50% arm 都从同一
task-wise basis 开始，额外预算固定为 `floor((full_tokens-basis_tokens)/2)`；selector、15 位 score
量化、tie-break 与 0L21 完全相同。每个 arm 的 Laplacian 使用 `local + selected G` 的单位 edge weight。

对每条 local edge 计算 effective resistance，即单位独立 edge-noise 下最小二乘节点势估计的该 contrast
方差。主汇总同时报告 4689 edges pair-weighted mean、28-task macro mean 和 pooled p90；不把 edge 当独立
统计样本，不报 p 值。full/basis 只作解析正控和 headroom，不是同成本比较。

## 4. Primary gates

全部通过才称 `G_REUSE_SPECTRAL50_TARGET_CONTRAST_VARIANCE_SUPPORTED`：

1. 固定 edge/task 计数、三条 50% arm 的逐任务预算与选择身份哈希一致；
2. spectral50 的 pair-weighted local variance 严格低于 cheapest50 与 hash50，且相对各自至少降低 3%；
3. spectral50 的 task-macro mean 与 pooled p90 均严格低于两个同成本 baseline；
4. 对两个 baseline 分别至少 20/28 tasks 不劣、至少 15/28 tasks 严格更低；
5. 对每个 baseline，task-level 正向 variance reduction 的最大单任务份额不超过 20%；
6. full 的 pair-weighted 与 task-macro variance 都严格低于 basis，所有 variance 有限且非负。

失败后不得降 3%/20-task/15-task/20% 门、改看 25% 或 75%、删除任务、改 edge 权重或转 BTL 模拟救回。

## 5. 资源矩阵与 ETA

单 CPU、BLAS 线程 1。producer A/B 与不导入 producer 的 grounded-Laplacian verifier A/B 各≤300秒；
预计正式 10--25 分钟，实现、测试、Linux 复验共 75--120 分钟。GPU=0、付费 API=0、神经模型加载/fit=0、
agent 底座更新=0；闭式矩阵求逆次数和墙钟单独记录。

## 6. 随机性与统计单位

无随机 seed。SHA-order 是确定性 baseline，不代表随机分布；A/B 是确定性复跑，不是独立样本。
task 是广度/集中度单位；local edges 只是预定 estimand 的有限总体。

## 7. 公平契约

同一 task 内三条 50% arm 使用同一 local、basis、remaining candidate、endpoint、edge weight 与额外 token cap；
唯一变化是 selection order。basis/full 不参与“同成本获胜”判断。不得把 selector 实际未花完的预算补给别的 task。

## 8. 完整性与独立复验

输入读前 credential-shape+SHA，读后重验；audit hook 禁止网络、子进程、未列数据和写入。producer 用
shifted-Laplacian inverse，独立 verifier 用 grounded inverse，不 import producer；两者各做 A/B，并比较选择
manifest hash、计数和全部 aggregate（固定容差）。结果根独占、mode-0600、命令/环境/耗时/stderr/source/manifest 留档。

## 9. 输出约束

只输出 arm aggregate、匿名排序 task 数值行、门、输入/source/protocol hash 与访问计数。不输出 task/run/card/
component/edge 身份或 selected edge 列表；只允许 selected-set SHA-256 与数量离开进程。

## 10. 失败解释与主张边界

若通过，只能说已有有效电阻 selector 在本真实 MLE comparison topology 上，把同成本图信息优势转化为更低的
目标 local contrast 解析方差。该结论依赖线性独立同方差噪声模型，不等于真实 critic accuracy、校准或搜索收益。
若失败，说明此前全图 D/A 指标不能可靠代理目标 local decisions，spectral50 的成本 challenger 机制支持减弱。

## 11. 后续门与相关工作

graph experimental design、ranking Laplacian 与 effective resistance 均有直接先例，不能宣称定理或 selector 首创。
通过最多加强 0L23 中 spectral50 的事前机制理由；它仍只能在 core 真模型效果全门通过后运行，且同 producer 来源、
experiment closure、G0 计价和精确 GPU·时批准一个都不解除。
