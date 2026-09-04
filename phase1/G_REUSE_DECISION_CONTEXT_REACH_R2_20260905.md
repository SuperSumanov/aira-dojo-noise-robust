# Decision-context reach 正式根 r1 失败与 r2 工程修复

首个结果根 `g-reuse-decision-context-8da7fd6-20260905-A` 在 producer import 前失败：runner 从远端登录目录
执行 `/tmp/.../phase1/g_reuse_decision_context_reach.py`，Python 只把脚本所在的 `phase1/` 加入模块路径，因而
`import phase1...` 报 `ModuleNotFoundError`。`producer_a.json` 为 0 字节，stderr 271 字节；未打开输入、未产生
任何 metrics/gates，不能算科学结果。

本提交只让 runner 的四个子进程以冻结 source root 为工作目录。它不修改 producer、verifier、输入、选择规则、
计数或任何科学门。失败根保留；r2 必须使用新 source archive 与新结果根，producer/verifier A/B 全部重新运行。
