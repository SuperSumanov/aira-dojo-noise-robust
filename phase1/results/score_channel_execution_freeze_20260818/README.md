# Score-channel execution/analysis freeze verification

状态：`VERIFIED_IMPLEMENTED_NOT_AUTHORIZED`。

## 冻结对象

- worker/analyzer/verifier source commit：`ca3bb7315078f2c4bed99fa4c33d93c2f353d670`；
- 远端 detached worktree：`/research/d7/spc/yzyang4/wt_scorechannel_frozen_ca3bb73_nosmudge`；
- 正式 GPU replay：未批准、未提交；GPU=0，API=0，底座更新=0；
- replay outcome：未产生、未读取。

## 精确验证

在上述 detached commit、`/research/d7/spc/yzyang4/venvs/exp/bin/python` 上：

- `py_compile`：通过；
- worker + primary analyzer + independent verifier 聚焦测试，连续两次：均为 `11 passed`；
- 完整 `phase1/tests`：`373 passed in 37.33s`；
- worktree：clean；
- 日志：`/research/d7/spc/yzyang4/prospective_decision_v1/logs/verify_scorechannel_ca3bb73.log`；
- 日志 SHA-256：`f9120267576770fbf37f8cab052942f369960a107f53e98e70a4f16faef5b4bd`。

## 失败与修正记录

正式测试开始前的 harness setup 有四类 fail-closed 失败：环境脚本在 nounset 后 source、远端 remote 名误写为
`myfork`（实际为 `fork`）、历史 Git LFS 对象 `full_artifacts.tar.gz` 在服务器缺失；新 worktree 改为
`GIT_LFS_SKIP_SMUDGE=1`。首次测试又发现 system Python 没有 pytest，随后显式固定到项目 venv。上述失败均发生在
测试收集/执行前，没有 replay、outcome 或科学结果；失败现场与远端日志保留。

## 裁决

允许把 commit `ca3bb7315078f2c4bed99fa4c33d93c2f353d670` 作为未来 approval receipt 的
`worker_source_commit`。这不构成预算批准：仍须等待固定 intake 窗口结束、双重冻结精确 replay 数与 GPU·时，
再由用户明确批准四 shard 矩阵。
