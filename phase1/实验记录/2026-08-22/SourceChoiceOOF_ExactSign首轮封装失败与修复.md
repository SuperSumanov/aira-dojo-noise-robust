# SourceChoice OOF exact-sign：首轮封装失败与机械修复

日期：2026-08-22。状态：正式 exact-sign outcome 产生前的 runner 修复。

## 失败事实

在 OOF 正式结果和独立 verifier 均只读封存后，commit
`223c5ad1a94a9876936773431bdfed6146b100a7` 的 exact-sign runner 首次执行返回 rc=1。失败 staging 原样保留为：

`/research/d7/spc/yzyang4/source-choice-oof-exact-sign-audit/.223c5ad-on-11b7f23-v1.tmp.1424257`

其中：

- focused test：`1 passed in 0.04s`；
- `audit_a.json` 未生成，`audit_a.stdout` 为 0 bytes；
- `audit_a.stderr` 为 `ModuleNotFoundError: No module named 'phase1'`；
- `FAILED_RC=2`；第二副本、diff、trace/credential audit 和 COMPLETE 均未运行。

因此此次失败没有 exact-sign 科学结果，不能据此报告 exact verdict。OOF 和独立 verifier 的正式只读目录均未修改。

## 根因与唯一修复

runner 的 focused pytest 位于 `cd ${worktree}` 子 shell 中，所以通过；随后两个正式 audit 副本却在调用者当前目录运行
`python -m phase1.audit_source_choice_oof_exact_sign`。调用目录不含锁定 repo，模块解析失败。

唯一修复是把每个 audit replica 的 `strace + python -m` 包进子 shell，并先 `cd ${worktree}`。没有改：

- audit Python 实现、输入 summary/predictions 或任何统计公式；
- OOF/verifier commit、结果 SHA、gate、seed 或 verdict 规则；
- frozen/extension model 或 label vault 访问范围。

修复后必须另立 commit 和新结果目录；旧失败 staging 不删除、不改名、不当正式结果。新 commit 先过 `bash -n`、focused
测试、秘密四扫与远端 SHA 校验，再允许重跑一次。
