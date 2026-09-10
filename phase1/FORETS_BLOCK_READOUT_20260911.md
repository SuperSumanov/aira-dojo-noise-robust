# 新分块读出模块已实现（2026-09-11）

用户明确批准后，新增 `forets_block_readout_20260911.py` 及对应测试；旧reader、旧seed计划、13004产物均未修改。
这完成了新seed8/9矩阵的**结果读取能力**，不是一次新的MLE运行或正效果结论。

## 实现与验证

- 全部8个预定槽位都保留，逐任务输出4个配对，不跨任务混合logloss和accuracy。
- leaf使用random−critic，spaceship使用critic−random；报每对差值、median、跨seed样本标准差与有效分数数量。
- 失败、未开始、缺分、重复最终事件均不补0；失败进程即使残留看似很好的最终分，也不进入有效比较。
- 仅读唯一最终选中节点的EVAL分数和bounded process结果，不重新评分、不读取轨迹最大值/自报分/中间候选。
- 准备config与实际pool config允许JSON序列化字节不同，但值/类型必须一致；两者各有自己的SHA，不能直接互换。
- 两块必须先有独立终态/未开始closeout；开放状态被拒绝。同一allocation不能在两个block重复计费。
- allocation GPUh与共享服务启动按block保存一次；未知耗时/费用不补造，实测超预算不裁剪。
- 输出runs.csv、pairs.csv、blocks.csv、summary.json；新目录独占创建，拒绝覆盖旧报告。

最终本地人工测试：**20 passed in 1.52s**。包含正/负方向、失败残留分、缺分/重复/nonfinite、错seed/hash/config、
越界路径、缺槽位、旧role、未关闭block/run、共享allocation重复、未知时间、未开始block、真实超预算、CSV空值与CLI。
旧代码没有修改，未重跑G0、模型验收或已完成控制器测试。

远端Python3.12.13于 **2026-09-10 21:45:39 UTC / 香港9月11日05:45:39** 用已准备的8份真实config核对接口。
closeout只在内存中人为设为NOT_STARTED；分数/进程读取函数被替换为一调用就报错。
结果绑定8配置/4配对，未写runtime manifest、未打开实际成绩、未提交GPU/API或模型调用。
该校验不是实际终态或0 GPUh测量；不得将人工状态转成生产记录。最初校验命令有一处Python上下文管理器语法错误，
在执行前退出；修正后通过，没有因此读写真实结果。

证据：[implementation.json](results/forets_block_readout_20260911/implementation.json)。
远端独立代码根：`/research/d7/spc/yzyang4/forets-block-readout-20260911-dKurmv`。
新reader SHA256：`7a0efc73323ce549da2c05704dce7a6f7ce26b67d0026e3fcb667790f61b0f1b`；依赖源码hash随输出记录。

## 给下一步真实适配层的接口

入口只允许固定新开发包 `/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4`。
prepared SHA与source tree固定；不接受旧role、config-draft或替换数据根，不能解封任何保护cohort。

runtime manifest由未来控制器/独立终态采集器生成，至少包含：

- 顶层schema=1、role=forets_e2e_fixed_blocks_runtime_v1、source_tree、prepared_sha256、controller_commit。
- blocks为顺序固定的1/2：allocation_id、实际node（gpu27/gpu28）、state、带时区observed_utc、
  elapsed_seconds、allocated_gpus=2、service_startup_seconds。未分配的NOT_STARTED块这些测量字段均为null。
- runs为原8槽位顺序：run_id/block/task/seed/arm、run_dir、prepared_config_sha256、runtime_status，
  以及实际pool生成的runtime_config_path/runtime_config_sha256/process_summary。路径全为包内相对路径，禁止猜占位路径。
- 未开始run无实际runtime路径；completed/failed/cancelled必须绑定实际config及process路径。

reader只验证记录内部一致性，**不会替代独立sacct终态核实或证明生产来源真实性**。当前没有正式新runtime manifest，
所以没有实际成绩可读，也不能用上述人工NOT_STARTED对象填补这个缺口。

代码接口检查不改变既定的两任务、seed8/9、两臂、6步或280分钟/块提案；下一步仍是实际服务启动/停止限时接线，
并等待OpenCL单卡暴露方式及checkpoint历史输入模板。批准实现不等于这些外部事实已经存在。
后续真实同预算配对仍可能为负；当前条件有效配对差值也不等价于全部尝试的净效用。
