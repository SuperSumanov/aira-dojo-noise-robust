# target-300 monitor：exact branch-head 耦合修正

日期：2026-08-24

状态：`CONTROL_COMMIT_STILL_EXACT / PUBLISHED_DESCENDANT_ALLOWED / OUTCOME_UNREAD`

## 1. 问题

`run_score_channel_future_cohort_20260823.sh` 会在触发时为调用者传入的 control commit 建立 detached exact
worktree，并再次检查该 worktree 的 HEAD。但它此前还额外要求 fork 的当前 branch HEAD 与 control commit 完全相等。
这项额外要求不增加科学不可变性：正式代码仍来自传入的 exact commit；反而会使任何后续纯文档提交都令已运行的
outcome-blind monitor 在新快照到达后 fail closed。

实际触发链证明了该问题：文档提交 `795e3da...` 推送后，仍绑定 `5d44361...` 的 monitor 必须在未观察新快照、未启动
formal runner、未读 outcome 的状态下封存，再轮换到 `795e3da...`。旧 monitor 的 stop receipt SHA manifest 为
`0c287c915cda805c5e125f8f120080c07696008907463ccdb5aa367df5bddd3d`；替代 monitor PID=`1926934`，首轮仍停在
`f109ac...`。

## 2. 唯一修正

runner 现在要求 control commit 是已发布 fork branch HEAD 的 ancestor；随后仍以该 **exact control commit** 创建 detached
worktree，并保持原有 HEAD equality、protocol SHA、producer/verifier replicas、forbidden-open、credential、manifest
和只读门。因而：

- branch force-push 删除 control commit 或传入未发布 commit：继续 fail closed；
- branch 只新增文档或未来代码提交：旧冻结 commit 仍可按原字节执行；
- runner 不会静默使用 descendant 的新科学代码。

新增静态攻击测试同时要求 ancestor proof、exact worktree HEAD proof，并禁止恢复 branch-head equality。该改动不读取
cohort outcome、不生成预测、不改 target/order/boundary overshoot，也不解锁 truth/replay/GPU。

## 3. 独立验证

在 fresh remote overlay worktree 上，仅覆盖 runner 与攻击测试后执行：

- focused：`16 passed in 0.57s`；
- full phase1：`965 passed, 47 warnings in 4509.30s (1:15:09)`；
- 正式状态：`PRECOMMIT_TARGET_ANCESTOR_FULL_TEST_PASS`；
- receipt root：`/research/d7/spc/yzyang4/precommit-target-ancestor/795e3da-v1`；
- `SHA256SUMS` 自身 SHA-256：
  `7e89bd435378a8666ed81cf257b6cb8162759058f07cb7611c74ec6ea7c819c7`。

独立复验执行 `sha256sum -c SHA256SUMS`，全部条目通过；`COMPLETE` 与 `SHA256SUMS` 均为只读。Windows 本地
全量 suite 因默认环境缺少 `scipy/sklearn` 在 collection 阶段不可运行，未把依赖缺失写成代码失败；正式裁决以上述
固定 Linux 环境全量结果为准。
