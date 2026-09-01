# Target-522 selection-container compatibility preflight（2026-09-02）

状态：`FROZEN_BEFORE_FORMAL_V2_RUN`。本次只修复 Stage-A 的执行容器契约，不改变已冻结的
`vertex_cost_contrast_target522_effect_v1` 科学协议，也不读取 Target-522 的候选身份、graph profile、
private selection、标签、结果值、预测值、accuracy 或 utility。

## 1. 方向与问题

当前唯一主线仍是 Decision Corpus + Predictor Benchmark + Audit Protocol。Target-522 已按原始自动规则闭合，
但 Stage-A v1 在产生任何 public/private selection 前因 `selection-support basename set mismatch` fail closed。
问题是：能否在不修改原始闭合包、不重选 cohort、不改变科学协议的条件下，严格兼容闭合包里的恢复回执？

## 2. 结果前假设与杀死条件

元数据复核固定 core / auxiliary / actual=`12/6/18`，missing / unknown=`0/0`；六个 auxiliary 文件均是
gap-recovery 流程回执，全部进入原始 `SHA256SUMS`。若正式运行前后 outer manifest 不同、出现第七个额外文件、
任一 auxiliary 未被 manifest 锁定、临时 core projection 不能被原始 verifier 接受，或原始根被修改，则停止。

## 3. 实验单位与处理

实验单位仍是原始自动选择的唯一 Target-522 cohort；没有第二个候选、人工 snapshot 或结果后 arm。
处理只发生在文件容器层：先验证原始 18-member package，再在 mode-0700 临时目录复制 12 个冻结 core member，
用 outer manifest 中对应 digest 生成 core-only manifest，运行原科学逻辑后删除临时目录。

## 4. 冻结输入与精确绑定

- 科学协议 SHA-256：`b3df170ebb4ae097549cb0225142e94aebfa481aea6c79815f1be2af687d9e1d`；
- 原始 selection `SHA256SUMS` SHA-256：`8e00c2e21818b89dafed76d06244df041efb27d901a67cf5f409c620c3e3b7e2`；
- v1 失败 producer stderr SHA-256：`a9e363f14d3b9e71f89bb311f61ab63ac84f904e06508b9180725059b81cbf69`；
- compatibility protocol、execution v2、producer、verifier、tests、runner、monitor 必须由同一公开 exact commit 绑定。

## 5. 公平契约与唯一改变量

唯一改变量是 selection container 的解析方式。cohort、baseline、run split salt、arms、checkpoint budgets、
support gates、solver time limit、ordered classification、effect gate 与 first-960 closure gate逐项保持原值；
任何科学字段变化都视为协议失败，而不是“修复”。

## 6. Outcome-blind 与泄漏控制

定义修复只使用 basename、文件类型、symlink 状态、manifest membership/digest 与脱敏异常类别。
不得读取 candidate.tsv/READY/observed.tsv 的内容来设计修复；正式 producer/verifier 可按原冻结 Stage-A 权限读取
code/topology，但 public artifact 继续禁止 raw identity，private selection 保持 0600。first-960 vault 保持关闭。

## 7. Estimand 与统计边界

本次不是新的 effect、accuracy、scaling 或 utility 实验，没有新增统计 estimand。Stage-A 即使通过，也只说明
固定 cohort 的结构支持、split 与 selections 可复现；后续 critic fit 仍要求 first-960 closure 与单独 GPU·时批准。

## 8. 独立性与复现

Producer 与不导入 producer 的 verifier 分别实现 outer-package 验证和 core projection；A/B public、private（若存在）
与 verifier 输出必须逐字节一致。focused tests 当前为机器实测 `23 passed`；本地 Python 缺 scipy/sklearn，故本地
full suite 只记录为环境不可用，正式远端必须在固定 exp venv 中先通过 focused + full suite 才能打开 Stage-A 输入。

## 9. 资源、ETA 与 checkpoint

CPU-only，GPU / 付费 API / model fit / base update=`0/0/0/0`；producer 最多两次、verifier 最多两次，
预计 10--70 分钟，90 分钟 fail-closed。monitor 有独占锁、FAILED/INTERRUPTED/TIMEOUT receipt；不得覆盖 v1 失败根，
v2 使用新 exact-commit output/worktree/root。

## 10. 完整性与安全门

正式 runner 必须 fresh detached worktree、umask 077、source/hash preflight、file+network strace、outer manifest
before/after、core manifest、credential filename/content、forbidden path、network、mode 与 clean-worktree 全部为零漂移。
临时 projection 只能在进程私有目录存在，结束后不得残留。

## 11. 报告与失败政策

只先报告 exact commit、tests、outer/core manifest hash、A/B、trace/security 和 COMPLETE/FAILED 结构回执；
当前自动守护期间不向模型读取或展示 candidate identity/profile/private selection。任一未知文件、hash 漂移、测试失败、
结果依赖修复或新权限需求都 fail closed；不得用同 cohort 改阈值或另选 snapshot 救结果。
