# Contract LOTO retrieval support v1

日期：2026-08-17。裁决：`INSUFFICIENT_TASK_HELDOUT_RETRIEVAL_SUPPORT`。

结果前 commit `456ba1991217cc1e65339974ae1f0d58cf6e071f` 冻结去任务名、去列名、去 description、去 score 的
public-contract fingerprint 与 20-task leave-one-task-out 协议；task type 只作为事后评价标签。远端完整
`phase1/tests` 为 `351 passed in 26.80s`。两次 100,000-permutation 独立进程输出逐字节一致，SHA256=
`fa41c1b01d72445486fefaa82f60b89f4b835b12ca645e799d389b2468b9586b`。

主要门未通过：mean same-type nearest credit=`0.50`，低于冻结阈值 0.55；标签置换零假设均值 0.332117、
95% 分位 0.55，单侧 `p=0.13867861321386787`。分任务类型为 image 0.5714、NLP 0.6667、tabular 0.0。

支持度的其他部分较好但不能救 primary gate：14 个不同任务被检索，最大 retrieval mass share=0.15；
18/20 query 的最近邻集合含至少 5 个 writer-marked best episodes；5 个无 public contract 的 image tasks
全部 abstain。

第一次正式 wrapper 在计算前发现 clean-worktree 的 memory audit 被换行归一化，SHA 与预注册输入不一致而
fail-closed，没有 retrieval output。随后单独传输预注册 bytes，并在运行前验证精确 SHA；算法、门和 commit
均未改变。

因此关闭“仅靠 names-stripped contract structure 已支持跨任务 memory retrieval”的主张。不得结果后加入列名、
description 或手调距离救 v1；若未来研究 description-based learned retrieval，必须作为新的探索/预注册问题，
不得把 v1 写成通过。方法效果与付费三臂仍未授权。
