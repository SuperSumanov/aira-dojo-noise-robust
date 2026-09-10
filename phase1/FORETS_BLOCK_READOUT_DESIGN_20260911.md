# 新分块矩阵的最终成绩读出：实现前预览

日期：2026-09-11香港；状态：**仅设计，待用户批准代码改动**。
本轮只有只读代码检查与有界CPU校验，没有新增代码实现、GPU/API/模型调用或实验成绩读取。
依据用户最新AGENTS，先提供设计/diff预览，获批后再落代码；不把以前的泛化授权当作本方案已获批。

## 已验证的具体缺口

当前公开HEAD为dbadcc4b1a81838d14bc82a9f45faea8782344b7。
现有 `forets_e2e_readout.py` 从 `forets_pilot_plan.py` 导入SEEDS=(6,7)及旧run_order。
将新准备包的8个seed8/9槽位在内存中投影成旧manifest格式，直接调用现有validate_manifest，得到：

```text
old_seeds=[6,7]; new_seeds=[8,9]; planned_rows=8
projected_old_schema_rejected=true
rejection="duplicate or out-of-matrix run"
actual_results_read=false; gpu_jobs=0; api_requests=0; model_calls=0
```

测试期间禁止Path.read_text/read_bytes，验证函数仍按预期拒绝；没有读取新包或保护集的分数。
原reader SHA256：0f832951336926522a93d915b28aa6e068cf3f58308580a2f293d2d383f063c4。
这不是旧reader的错误：它正确限制了旧协议。需要新协议入口，不能修改旧全局SEEDS来绕过。
新prepared.json也不是runtime-manifest：其role/arm字段、缺少实际process路径均不能直接当作已运行记录。

## 目标、固定项与拟议diff

唯一问题仍是：相同执行预算下，critic是否改善最终选中解的外部分数。
不改变已准备的两任务×seed8/9×两臂、两个固定4run块、6步/100请求/每块280分钟预算。

```text
+ phase1/forets_block_readout_20260911.py
+ phase1/tests/test_forets_block_readout_20260911.py
  phase1/forets_e2e_readout.py             不改
  phase1/forets_pilot_plan.py             不改
  13004源码/结果、原SIF、8份新RunConfig   不改
```

新增入口只处理独立的新runtime manifest，明确与config-draft/旧runtime角色区分；无submit/execute参数。
固定新prepared SHA、source tree、8个run身份和顺序；实际config hash与来源必须由控制器绑定。
process路径由实际pool生成，不能把本轮人工校验中的占位路径复制成生产路径。
只接受明确声明的开发包内部路径，禁止遍历发现run或借软链接读出包外/保护集内容。

## 读出规则

- 最终汇总保留全部8行，包括失败、未开始、缺分；每行包含block/task/seed/arm、代码与config SHA、预算和运行状态。
- 仅读取唯一final EVAL中的最终选中节点分数及对应bounded process终态；不读取中间候选、自报分或取轨迹最大分。
- 进程成功且最终事件无歧义，才进入有效配对；重复final、未知状态、缺分、不匹配身份保持不可比较，不补0。
- 逐task比较同seed两臂：leaf的改善=random−critic；spaceship的改善=critic−random。
  逐任务保留每对差值，报median与跨seed样本标准差；不把两种原始指标混平均。
- 有效配对差值是条件分析；必须并列全部计划run的完成率/缺失，不把它冒充所有尝试的净效用或确认性收益。
- 每个block的allocation耗时/GPUh与共享critic初始化只计一次；未知费用写未知，不将worker秒数直接当GPUh。
  若实际allocation/用量来源未就绪，不补造对应数字。
- 输出CSV/JSON到新目录，拒绝覆盖旧报告。正式读出需独立核实两块终态或明确停止，不能据第一块成绩重选第二块。

## 验证与本次授权边界

获批后先用人工文件做CPU测试：已知正/负差值、两个任务方向相反、失败仍有分、未开始/缺分、重复final、
错误seed/config hash、包外路径、8行完整保留、共享资源不重复相加。测试不读取真实成绩或加载模型。
预计这部分单次验证不到1分钟，无GPU/API/训练预算；若出现真实性能/依赖问题再如实报告，不以测试通过代替收益。
本方案批准也不解除OpenCL隔离、checkpoint历史输入模板或实际服务有界启动/清理的剩余条件。

等批准时不反复运行这次拒绝校验、不改旧reader、不新增审计链；可以继续只读外部状态检查。
本轮现场观察2026-09-10 21:32:51 UTC：队列仅12535 PENDING/JobHeldUser，学长branch仍065b0fba。
