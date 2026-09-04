# G-reuse 已知记录缺陷排除敏感性：结果前预检

日期：2026-09-05。状态：历史 train 结构敏感性，结果前冻结。
本项不修改历史输入、训练池、G0 12377 或冻结评测；不授权 GPU/API/model fit。

## 1. 假设与最小充分问题

已知 3058 条 G-reuse 中有 143 条两端 observed card config 不相等、193 条至少一端 run 的旧
source projection 非 unique，二者重叠 23 条。这里固定排除其并集，只问剩余的 2745 条
`equal observed config AND unique projected source` 边是否保留此前 924 图秩增益的广度。

三门必须同时通过：保留至少 0.80 的 full-reuse incidence-rank gain；至少 20 个任务仍有正 gain；
最大单任务 gain 占 filtered 总 gain 不超过 0.20。阈值、任务、边和分组不得在结果后调整。

## 2. 输入、population 与污染边界

固定历史 L train、G train、92a9651 grouped Cards、a466888-v3 run-batch manifest 与其上游 manifest；
SHA 沿用已发表 source/cost receipts。只取 train unordered endpoint identity、task/run、四个 observed
card fields（client/hardware/time_limit/execution_timeout）和 source_match_status/batch hash。
不打开 dev/test/vault、归档成员、first960、Target300 或 Target522。

这是旧版本间记录的一致性敏感性，不是权威 producer config 或 source 修复。Cards 与 G 不是同一完整
producer package；`unique` 只是旧 manifest 的投影；完整 experiment split 未证明。故 filtered 集合不得
物化为训练池，也不得称 clean/source-authoritative。

## 3. 单一分析与 estimand

先按既有资格规则重建全部 3058 条 reuse 边，再只保留“两端 observed config 编码相等，且两端 run
source_match_status 均为 unique”的边。固定每任务 L endpoint 集，分别计算 L 与 L+filtered 的 connected
components；gain 为二者之差。输出仅含 aggregate 与按数值排序的匿名 task rows，不输出身份、配置值、
方向、score、gap、label、prediction 或代码。

## 4. 对照、混杂与失败解释

full 3058 reuse 只作固定分母；filtered 不能按结果补边。加边不会降低 rank，非平凡问题是相对 full 的
保留率、任务 breadth 和 concentration。通过不代表独立标签数、模型可利用性、准确率或搜索收益；失败也
不撤回 full-reuse 结构结果，只关闭“对已知记录缺陷稳健”的说法。

## 5. 资源矩阵与停止规则

单 CPU：producer A/B 各最多 180 秒，完全独立实现的 verifier A/B 各最多 180 秒；数学线程固定 1。
预计正式墙钟 4--7 分钟，实现与复验合计 15--25 分钟。任一 rc 非零、stderr 非空、A/B 不同、hash
漂移或 producer/verifier 不同立即 fail-closed；不重定义门或另做 rescue。

## 6. 随机性、重复与统计

算法确定性，无 seed、warmup 或抽样区间。A/B 是复现检查，不计独立实验样本。任务是聚合层；不把
3058 或 2745 当作独立统计样本。

## 7. 可复现绑定

源码必须在结果前提交并以 exact commit 导出。五输入读取前 credential-shape+SHA，读取后再验 SHA；
Python audit hook 拒绝网络、子进程、未列数据和写入。A/B receipt、独立 verifier、逐文件 SHA256SUMS、
命令、解释器、耗时与 stderr 字节数全部记录。

## 8. 完整性与公平契约

唯一变化是预先声明的 edge exclusion；L endpoint population、task 分组、full denominator 和图定义固定。
不访问任何模型、checkpoint 或 held-out outcome，不更改 agent、operator、预算或 scorer。

## 9. 输出与版本化

新独占 `/tmp` 根，结果下载后再验 archive hash 与内部 manifest。正式 JSON 一行一个 deterministic receipt；
匿名 per-task rows 全保留。GPU jobs/API calls/model fits/base-model updates 均必须为 0。

## 10. 预期结果与结论措辞

三门全过只称 `RECORD_CONSISTENT_G_REUSE_SENSITIVITY_SUPPORTED`：当前 full-reuse 结构增益对已知记录缺陷
的保守排除稳健。任一失败称 `RECORD_CONSISTENT_G_REUSE_SENSITIVITY_NOT_SUPPORTED`。

## 11. 后续门

无论结果如何，同版本 Cards/G/L/source 包、权威完整 config、producer instance 和 experiment-closed split
仍为训练前硬门；G0 实测计价和明确 GPU·h 批准也不解除。本项不得自动触发训练或付费调用。
