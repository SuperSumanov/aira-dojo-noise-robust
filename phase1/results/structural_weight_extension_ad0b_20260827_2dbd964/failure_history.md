# Failure history

## formal v1：拒收，无科学结果

- fresh worktree、focused `12 passed` 与 full `1225 passed, 47 warnings` 均完成；
- 首个 producer 在生成 `trajectory.json` 前，以 `ModuleNotFoundError: No module named 'phase1'` 退出；
- 原因是 runner 用绝对脚本路径启动，未把仓库根放进 Python import path；
- v1 没有 `run_a/trajectory.json`，没有读取或打印 HHI、decomposition、deletion 或 gate 数值；
- v1 标记为 `ENGINEERING_ENTRYPOINT_FAILURE_NO_TRAJECTORY`，不得作为科学 attempt。

## formal v2：接纳

- 唯一修复是 producer/verifier 改用 `python -m phase1...` 模块入口；
- snapshot、commit、源码 SHA、协议 SHA、gates、阈值、检查点、环境与路径白名单全部不变；
- 从新的 detached no-smudge worktree 与新输出根完整重跑测试、producer A/B、verifier A/B 和 strace；
- v2 正式运行通过全部工程完整性门，科学裁决按预注册 E1—E5 原样记录，无 rescue。
