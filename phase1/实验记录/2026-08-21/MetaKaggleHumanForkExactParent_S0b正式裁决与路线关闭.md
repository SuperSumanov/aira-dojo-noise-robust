# Meta Kaggle Human Fork Exact Parent：S0b 正式裁决与路线关闭

日期：2026-08-21。状态：`IDENTITY_UNAVAILABLE`；S1/S2 禁止执行。

## 1. 正式执行完整性

LFS 404 的第一次工程尝试没有进入 tests 或真实 CSV rows。结果前冻结的唯一修复是 worktree checkout 使用
`GIT_LFS_SKIP_SMUDGE=1`；输入、关系定义、门槛和科学源码不变。修复后的 commit
`64ec81945b19f232968391a0b10d0772b9895641` 完成 producer×2/verifier×2：两份 producer 目录逐字节一致，
两份独立 verification 逐字节一致；focused=`7 passed`，全套=`611 passed, 25 warnings`。四个正式进程退出码
均为 0，最大 RSS 分别记录在四份 GNU time receipt 中。

正式 runner 的 strace 确认 `Submissions.csv`、`KernelVersionKernelSources.csv`、Meta Kaggle Code 和 ipynb
路径命中为 0，外部网络 connect=0。文件名与内容凭据形状扫描均为 0，完整目录只读。S0b 没有读取 outcome row、
notebook code 或 predictor effect，GPU/API/model fit=0。

## 2. 身份门为何失败

两套实现独立得到以下同一结果：

- `Kernels.csv` 共 1,946,556 rows，391,175 explicit-fork rows；748 malformed 后有 390,427 parsed edges；
- `KernelVersions.csv` 共 18,979,184 rows；580,333 个所需 version IDs 中找到 537,972，缺 42,361；
- 全部 390,427 parsed edges 的 child first-version `ParentScriptVersionId` 都不等于 explicit fork parent，
  agreement=`0.0`，低于冻结门 `0.95`；
- 362,922 条 child first-version 的 `VersionNumber != 1`；另有 child first version missing=1、
  parent version missing=50,606、creation time missing=50,607、time order invalid=4；
- competition 表本身不是失败点：1,782 个 required competition IDs 全部找到；selected graph cycle nodes=0；
- base-valid edges=0，故 eligible parent groups=0、canonical pairs=0、completed competitions in pairs=0。

最保守解释是 Meta Kaggle 的公开过滤/保留规则使 `FirstKernelVersionId` 不能作为 fork-origin version 的完整代理，
且大量被引用 version 不在 snapshot。该结果是身份不可识别，不是“human fork 没信号”的方法负结论。

## 3. 关闭边界

原协议已经把双字段一致性定为 exact-parent 的必要条件，并明确禁止 dependency source 充当 fork edge。因此结果后
不能删除 `ParentScriptVersionId` 一致性、改用 `KernelVersionKernelSources`、仅保留看起来能联结的子集，或按 score
重新选 sibling。Meta Kaggle extension 在 S0b 关闭；`Submissions.csv` 保持封存，Teams 不下载，private score/code
阶段均不启动。公开 TraceML 已覆盖 human trajectory/fork graph，所以也不把此次审计包装成“首个 human-fork
dataset”。

该关闭不改变主线：继续等待 activation 后生成的新 AIRA physical runs，由 strict-future transition escrow 做
结果盲追加。完整远端证据位于
`/research/d7/spc/yzyang4/meta-kaggle-exact-parent-s0b/64ec819-v1`，小型可共享回执位于
`phase1/results/meta_kaggle_exact_parent_s0b_20260821_64ec819/`。
