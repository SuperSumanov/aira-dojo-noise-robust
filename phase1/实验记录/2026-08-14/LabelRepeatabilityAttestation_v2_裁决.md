# Label Repeatability Attestation v2 裁决

日期：2026-08-14。源码 commit：`4e3bebe21fb96e356fdc1656bbfe8d5ba748e027`。正式状态：
`INDEPENDENTLY_VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2`。

## 裁决

旧 `noise_ceiling.py` 的 raw cross-session agreement 可以作为历史描述，但其 bootstrap 没有实际使用抽中的
节点；而把 original single measurement 与 repeat mean 当可交换标签反演也不成立。因此旧 `0.9923/0.9578`
不再作为论文 release-grade ceiling headline。

v2 在真实结果前冻结并改用两个单次跨时段测量：original grade 与 first successful regrade。用于分桶的
reference gap 排除了这次 first regrade，避免 primary label 同时决定自己的难度桶。远端干净 worktree 的 4 项
聚焦测试和全部 256 项 `phase1/tests` 通过；独立 verifier 重建三种 duplicate-rep 处理、全部节点对、PAVA、
九个 v11 transport 与 2,000 次 task bootstrap。

主结果为 207 cards、10 tasks、3,017 pairs，raw agreement=`0.9658601259529334`，task-macro=
`0.9801808283872976`，task-cluster CI=`[0.9438143714671886,0.9913402891372938]`。frozen b0 的直接
transported repeat agreement=`0.9134305309964227`，CI=`[0.8353851659068688,0.9494041168867747]`；
在独立、可交换、对称误差工作模型下，single-label quantity=`0.9488254145489123`，CI=
`[0.8571329199113228,0.9682215874512448]`。

但 frozen b0 只有 1,098/1,498 pairs 属于已重评任务，覆盖率 `0.732977303070761`。因此可写结论是：
**在已重评任务上，标签顺序高度可重复，标签噪声不足以解释 run-clean critic 的主要性能差距**。不得写成
“22 个 frozen 任务的真实 ceiling 已测为 0.949”，也不得省略模型假设、task extrapolation 与 observed-gap
transport 近似。

三种 retry sensitivity 对 frozen b0 transported agreement 的范围仅
`[0.9131214229466382,0.9134305309964227]`。最终 filename/content secret scan 均为 0；postflight 的首次
中断是 zero-match `grep` 在 `pipefail` 下返回 1，repair 没有重跑 producer/verifier。

精确 replay 还必须使用 artifact 记录的 Python `3.12.3`。后续本机 Python `3.13.4` 虽通过全部 normalized
input hashes，但因浮点 `sum()` 实现变化，让 `original_vs_repeat_mean` secondary 的一个 exact tie 从 3,020
pairs 变为 3,019；primary 仍是 3,017 pairs 且 raw agreement 不变，其余 primary transport 差异约 `1e-16`。
该本机运行明确记为不兼容环境下的 fail，没有用 tolerance 追认，也没有在看过结果后改 producer。

本 attestation 进入 Decision-Corpus Audit 的 label-quality 外部证据。它增强主线的数据质量论证，不解锁
新的 critic、E2/E3，也不改变 first-960 prospective cohort。
