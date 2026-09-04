# Decision-context reach r2 失败与 r3 import 隔离修复

r2 新根 `g-reuse-decision-context-9be1e46-20260905-A` 仍在任何输入或 metrics 之前以同一
`ModuleNotFoundError: phase1` 失败。仅设置 subprocess `cwd` 不足：以绝对脚本路径调用 Python 时，
`sys.path[0]` 仍是 `.../phase1` 脚本目录，而不是其父 source root。失败根保留，0 字节 stdout 与 271 字节
stderr 不算科学运行。

r3 只给四个冻结子进程显式设置 `PYTHONPATH=<exact source root>`，同时保留 `cwd`。不继承任意 worktree
模块，不改 producer/verifier、输入、选择、population 或门。新 archive、新结果根重新执行全部 A/B。
