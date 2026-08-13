# Probe-First Contract Safety A/B V1：无效运行裁决

日期：2026-08-13
状态：**`INVALID`；不是方法输赢，不回填、不复用这 6 个任务/seed**

## 1. 实际发生了什么

- frozen commit：`e01b19547fea57070f5e9f7a5fa06c5c39a74717`；
- generation job：`10637`，`4×RTX3090`，wall=`00:55:03`，scheduler allocation=`3.67 GPU·h`；
- 6 task×seed blocks、original/contract 两臂，共 12 个 generation entries；
- 12 个 entry wrapper 均 `rc=0`，三波运行完成；
- parent 最后在 generation manifest 的 fail-closed 审计中 `FAILED 1:0`，因此 replay 没有提交，
  预注册 K0--K3 没有计算。

冻结 chain log SHA-256：
`7f135fc158893830499ad00d1d5d0cc55de34f4023bdd35b4c7ebbb264bf08b5`。

## 2. 根因

manifest builder 把整个 resolved solver dict 在只替换 draft prompt 后做逐项相等检查，却没有排除两个由每个
run identity 自动生成的字段：

- `solver.exp_name`；
- `solver.checkpoint_path`。

对六个 task 的独立 diff 都恰好只有这两项；step/debug/time budget、client、operator 与其他 solver 旋钮没有
发现差异。这是审计器过严造成的 false positive，不是两臂实际科学配置漂移。不过预注册明确规定任何
generation/manifest 完整性门失败都记 `INVALID`，所以不能在看过运行后修改 validator，再把 job 10637
追认成正式 A/B。

## 3. 修复边界

`normalize_solver` 现在只删除上述两个 per-run identity 字段，再屏蔽唯一允许变化的 draft prompt；其余科学
字段继续 fail-closed。回归测试同时验证：

1. 只改变 `exp_name/checkpoint_path/prompt` 时归一化相等；
2. 改变 `step_limit` 时仍不相等；
3. 原完整 12-entry fixture 具有两臂不同 identity 路径并仍能通过 builder/extractor。

修复后在远端对冻结 raw generation 做了一次**只读诊断重建**，输出到 `/tmp` 而未写回正式 ops：
`rows=12, pairs=6, normalized_equal=6`，diagnostic manifest SHA-256=
`93408d1ff102e9c2ed0f2e0868497c401562dce995390f6399c888ca2fa1f788`。这只证明 validator 根因，
不改变 `INVALID` 科学裁决。

现有 job 10637 的 raw 产物只允许用于基础设施诊断，不能报告 coverage、quality 或 contract effect，也不能据此
选择下一批任务。下一次因果 A/B 必须使用全新任务、全新 seed、修复后的 commit，并在任何 API POST/GPU outcome
前重新冻结矩阵、prompt 差分、预算、manifest 审计与裁决门。
