# Source Retention Transport v1：首次封装失败与修复

日期：2026-08-21。状态：`NO_SCIENTIFIC_RESULT_MODULE_PATH_FAILURE`。

commit `6739948cbe069588832ad83d83fd81d255b33c64` 的首次正式 runner 完成了输入 SHA、隔离 worktree、
预检和 6 项 focused tests；随后 producer A 在 Python 解析 CLI module 入口时立即失败：runner 位于 `/tmp`，
其当前目录不在隔离 worktree，且没有显式设置 `PYTHONPATH`，因此报
`ModuleNotFoundError: No module named 'phase1'`。

失败发生在 producer module 导入前；`producer_a.stdout` 为空，artifact 目录、summary、per-task profile、
Spearman、置换、bootstrap 与任何科学裁决均未产生。既有正式输入没有被 Python producer 打开；失败目录
`/research/d7/spc/yzyang4/source-retention-transport/6739948-v1` 保留，不覆盖、不提升为正式结果。

唯一修复是在 worktree commit/clean 门通过后显式设置 `PYTHONPATH=${worktree}`。输入 SHA、3,252-parent
分母、task 支持门、metric、seed、置换/bootstrap 次数、裁决阈值、producer/verifier 源码和 scope 均不变。
修复后必须使用新 commit、新 worktree 和新输出目录完整重跑 producer×2、verifier×2 与全部测试。
