# 发现并修正“尚未执行”被报告为“程序超时”的反馈错误

2026-09-19。这是独立运行诊断与未部署的反馈修复，不是新的 critic / E2E 收益。

## 已核实事实

- 新 comparison 数据中，43 个可读 run 的 957 个已执行非根节点，有 16 条包含 harness 的 `Kernel did not become ready in time.`；涉及 11 个 run，16 条均附加了完整程序时限超时消息。
- 这些节点记录时间最小 120.05724292201921 秒、中位 120.06093958253041 秒、最大 120.06777003197931 秒。节点占比 0.01671891327063741，不能据此说“大部分失败都是基础设施”。
- 原配置层次分别为 forets 3/141、forets-1 6/198、forets-2 4/208、mcts 3/410。分母是执行节点，不是独立重复；任务、硬件、时长不配平，不能据此比较方法可靠性。
- 一个直接案例：Leaf seed1 原选节点 `c4ae6e85ce3245bb89cbde1218b7e3bf` 历史在 120.06161448499188 秒退出、buggy、无官方成绩；本轮相同代码 SHA 在统一 fresh 环境用 37.9015831949946 秒成功，官方 logloss 0.06983，与独立计算 0.06982953249751943 一致。
- fresh 环境与历史硬件/Jupyter状态不同，因此这不证明已修复历史启动根因或能按同样比例挽救其它失败。历史记录不删除、不改分。

## 源码因果链与修复边界

检查生产 commit `be9335348b569086ef9b0af36a15b13e61fec45c` 的 `jupyter_code_executor.py`：先以 `_wait_timeout=120` 等待就绪，失败则在调用候选 `execute(code, ...)` **之前** 返回 `timed_out=True`。`jupyter_interpreter.py` 对任何 `timed_out` 都追加配置中的完整程序时限，混淆两个阶段。

本分支补丁在 `ExecutionResult` 增加默认 `None` 的 `timeout_phase`，Jupyter 路径明确 readiness / code execution；只有 readiness 消息改为“候选代码执行前，内核就绪超时”。既有不带阶段的其它解释器保持原行为。

不增加重试、不改执行时限、不跳过失败、不升级镜像，不改变当前 14091 的固定源码。此补丁尚未做 live-kernel 部署验证，也不宣称修复内核启动故障。5 个 CPU 源码控制流回归测试覆盖：未就绪不执行/不重试、执行超时仍中断、成功、普通程序失败、旧结果默认值。测试通过不能替代真实 E2E 对照。

## 证据

- `results/comparison_qwen_20260919/kernel-readiness-census.json`，SHA `c10fe98afa81ee13effbbd05d072de802794598e8a740b3554be892858215fb5`。
- `kernel-readiness-independent.json` 独立检查节点/run身份、分母与汇总；它没有二次解析原日志，不能称双独立日志普查。
- 相同代码案例的新输出在 `results/comparison_pool_20260919/summary.json`，SHA `238bd65e00edd0f678b1f9dc6fbce0c92bf49247030765b64c703ed4d469547a`。
- 原始日志/代码/凭据未进入此报告；有限脱敏异常上下文仅留远端私有回执。

实质意义：critic 选到的候选质量与执行器是否把它跑起来必须分开。现在已有一个反例，说明“没得到成绩”不能一概归因候选差。但修正这个错误本身不构成新方法论文；主线仍是同预算下的真实收益。
