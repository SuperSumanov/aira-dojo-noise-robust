# Yield-Guarded Breadth Feasibility v2：Post-Push 回执

日期：2026-08-29

公开开发包 commit=`e816a5d8909fbb1d2bd379e625d6a0ec3b419020` 已完成 fresh detached Linux post-push 复验。

## 失败保留与唯一权威回执

r1 root=`/research/d7/spc/yzyang4/yield-guarded-breadth-development/postpush-e816a5d-r1`。它先通过 9/9 package manifest，随后在 scientific self-test 前因 runner 未给直接执行的脚本设置 `PYTHONPATH` 而 `ModuleNotFoundError`，`FAILED_RC=1`；没有 focused/full tests 或新 scientific output。r1 不算通过。

r2 只给 self-test 命令增加 exact worktree `PYTHONPATH`，commit、源码、结果包与所有科学门均未改。唯一权威 root：

`/research/d7/spc/yzyang4/yield-guarded-breadth-development/postpush-e816a5d-r2`

## r2 精确回执

- fetched/requested commit 均为 `e816a5d8909fbb1d2bd379e625d6a0ec3b419020`；
- package members=`9`，全部 hash exact；
- result SHA-256=`e43831946643d60654bb10b834278fd480c97292fcf91ea6dfa95962c77c191d`；
- independent aggregate verification SHA-256=`c3680fb2a767ad51a3b3c1109f102ec56556d17ec33e041d248cdb9e22f06a2d`；
- checked-in solver synthetic/exhaustive/infeasible self-test=`SELF_TEST_PASS`；
- focused/full=`6 passed in 0.29s` / `1594 passed, 47 warnings in 89.62s (0:01:29)`；
- changed files=`16`，credential filename/blob hits=`0/0`；
- remote receipt manifest 共 12 个成员，`SHA256SUMS` SHA-256=`13c84f028f6576ba864b3ed7d8d53dde6b68229b2fa24a56d18c596be4de702c`；
- prospective values、senior test 未读；GPU/API/model-fit/base-update=`0/0/0/0`；
- completed UTC=`2026-08-29T02:25:04Z`。

该回执只证明公开开发包可复现，不把已读历史图升级成未来确认，也不补足 private witness graph-level 双实现。
