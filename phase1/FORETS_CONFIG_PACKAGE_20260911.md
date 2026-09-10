# ForeTS：完整新配置包已生成，未启动实验

更新：2026-09-11香港05:13。主线仍是同预算最终解收益；本轮没有新模型成绩。

## 完成了什么

独立根 `/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4` 已生成8份真实RunConfig，
对应leaf-classification/spaceship-titanic × seed8/9 ×随机/critic top2，共4对、两块。
源码固定为 `3aae90ae26b5ae7b65e6efed14fb49f2907c9c42`，包括0018显式选择开关。
231份源码文件从Git原始归档物化，再由另一检查程序逐字节对照；没有修改原13004包、生产来源或学长分支。

远端真实Hydra/RunConfig/ForeTSSolverConfig构造、校验、序列化与重新读回都通过：

- 两臂都显式用common_priority_v1；6步、宽度4、top2选1、300秒执行、debug深度1。
- 每run最多100次请求、8192输出token/次、120秒请求超时；解析尝试2、传输尝试3。
- 真实SrunPoolConfig记录每step60分钟、worker3540秒、退出预留330秒、启动前至少剩3930秒。
- 两臂生成器和免费路由约束一致，不允许provider fallback；没有读取/安装/使用凭据或调用API。
- 两块启动器配置一致；8份配置都保留ForeTSSolverConfig具体类型，不是手填JSON冒充真实配置对象。

独立检查没有复用生成器的差异归一化函数。四对配置的差异只在selection_policy，以及六个机械身份/目录字段：
id、interpreter.working_dir、logger.output_dir、solver.checkpoint_path、solver.exp_name、task.results_output_dir。
另外四个内存负控分别修改seed、步数、选择版本、输出token上限，全部被拒绝，没有改真实文件。
旧campaign的实际validate_inputs函数拒绝新草案；本次没有调用它的execute或凭据安装函数。

环境：Python3.12.13、hydra-core1.3.2、omegaconf2.3.0、python-dotenv1.2.2。
继承配置仍有缺少`_self_`的Hydra警告；没有顺便修改其继承顺序，最终配置已逐字段核对。
准备过程禁止网络/子进程派发、模型框架导入、任务数据与保护目录内容打开；只检查数据/镜像路径存在。

## 提交前发现并修正的预算漏项

旧预算草案只按15分钟准备＋4×60分钟算每块255分钟，漏计每step退出预留与轮询余量。
这不表示实际跑过超预算；**没有提交过这个方案**。但按声明的上限，最后一项可能因启动余量不足而不启动。

用实际SrunPoolLauncher._can_launch与人工剩余时间核对：旧255分钟的边界轨迹为通过/通过/通过/拒绝。
按15分钟准备、4×(3600+330+5)秒、最终30秒清理，算得最少278分钟，建议向上取整到每块280分钟。
对应同一人工轨迹四次都通过；这是预算算术，不是集群调度实测，也不保证任意故障下必然完成。

新外层预算草案：每块双GPU280分钟，9.333333333333334 GPU·h；两块名义18.666666666666668 GPU·h，
连同已观察到的每块300秒allocation KillWait为19.0 GPU·h。矩阵、每run预算与8份config字节均不变。
该修正不是实际用量或自动追加授权；不提交GPU，未来控制器还须显式执行这些准备/终止上限。

原next-budget.json、prepared.json保留为历史生成记录，其中17.0 GPU·h已被外层修正覆盖。
**当前预算读PACKAGE_STATE.json指向的allocation-budget-correction.json，不得只拿旧prepared.json启动。**
没有为修正总时限而重新生成8份配置或重复原先测试。

## 现在仍缺什么

1. 学长/管理员确认的OpenCL单卡分配隔离方式；不能按“设备可访问”就使用未分配GPU。
2. 所交付8B checkpoint的历史训练模板；已有前缀差异线索不等于当前模型确实错配。
3. 与新矩阵、两块执行顺序、修正预算匹配的控制器；旧入口硬编码4步/40次请求/旧seed，不能直接复用启动。
4. 明确检查预算内的新鲜固定路由可用性证据。

目前状态`CONFIG_DRAFT_COMPLETE_EXECUTION_NOT_READY`。无提交脚本/执行命令，无GPU、模型前向或API请求。
21:13:42 UTC只见旧12535 JobHeldUser，未释放。学长head在本轮fetch时仍065b0fba。
13004的单seed负结果保持，不把本轮配置接入写成critic收益或干净scaling。

证据：[PACKAGE_STATE](results/forets_next_package_20260911/PACKAGE_STATE.json)、
[真实配置生成](results/forets_next_package_20260911/prepared.json)、
[独立核对](results/forets_next_package_20260911/independent-verification.json)、
[预算修正与门函数轨迹](results/forets_next_package_20260911/allocation-budget-correction.json)。
