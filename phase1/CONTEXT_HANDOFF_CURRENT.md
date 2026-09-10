# 当前交接：ForeTS 同预算端到端探索

更新：2026-09-11香港。只维护当前事实，不在顶部继续叠加历史交接。
恢复顺序：fetch → [CURRENT_DIRECTION](CURRENT_DIRECTION.md) 最新节 → 本文件 → 所需证据。
实验前对照 [ADVISOR_DIRECTIVES](ADVISOR_DIRECTIVES.md) L/M；历史在dated reports与Git。

## 目标与实测

- **最新停止事项**：13042非零step被程序映射到设备9并实际做了人工GPU运算；该映射没有独立分配证据。
  “精确可见设备”只是对程序自选minor自洽，不足以证明Slurm分配正确。接入验证作废，泛化隔离解决声明撤回。
  当前adapter/新诊断在GPU查询前关闭；13042已主动释放。不可复用旧未关闭副本或按旧0L152开跑。
  /etc/slurm/gres.conf只读被拒绝，未绕过；等权威GPU ID→设备路径/UUID映射。见FORETS_GPU_MAPPING_ERRATUM_20260911.md。

- 科学目标：**同预算下，critic是否改善最终选中解的外部成绩**。Corpus/predictor/audit是支撑。
- 13004首对已完成：leaf-classification/seed6，random logloss **0.66022**，critic **2.5208**；
  random−critic **−1.86058**。critic此次更差，仅一个探索seed，不能外推普遍无效。
  [实测与读出](FORETS_FIRST_PAIR_20260910.md)；旧包、失败记录和未启动槽位保持不变。
- 当前没有新的critic收益或干净scaling结论。配置、人工测试、输入编码差异均不是效果结果。
- 最近队列实查：**2026-09-10 22:40:20 UTC / 香港9月11日06:40:20**，只有12535 PENDING/JobHeldUser。
  它不会自己开跑；不释放/取消。无本轮运行中的GPU作业；这是观察时间，不是永久实时状态。

## 已完成，不再重复

- G0/12892、8B/16K模型接入与3090原镜像基础CUDA验收。CUDA通过不等于OpenCL隔离正确。
- 13004及13007/13009/13010均终态；不重投、不自动补13004余下6项、不重复失败的设备遮蔽。
- 新八包已下载并仅读安全配置/成员头：205,912,386 bytes，32配置、29有journal成员头。
  **不是32或29个合格physical runs**；含两个代码版本，预算7200秒/次、86400秒/总，与短预算不等价。
  未并入生产/训练；env、journal、代码和结果未打开。见 [新包说明](SENIOR_UPLOADS_AND_FORETS_NEXT_20260911.md)。
- 当前训练/服务编码差异已用真实tokenizer人工输入复现。checkpoint历史模板仍未知，不能归因负结果。
- common_priority_v1已准备为显式可选源码补丁；保留旧默认，只保证同池耦合，不是新算法或最终分改善。
- 新8份真实RunConfig已生成、往返和独立配对核对；**不要再次生成或执行旧campaign**。
- 新控制器核心13项、新读出20项、新runtime/collector 22项CPU测试通过，均勿重做。Linux计时/中断清理及实际pool导入已核。
  生产接线已实现但未发行可执行release、未做真实Slurm生命周期实测；不把准备算模型收益。

## 当前唯一新方案与产物

- 两任务leaf-classification / spaceship-titanic × seed8/9 × uniform_random / critic_topk_random。
  两块，每块4run，顺序预先平衡；不能看结果后重选seed、任务或丢弃失败。
- 相同6步、width4、top2选1、单次执行300秒；worker3540秒、step60分钟；每run100请求、8192输出token。
  固定免费Nemotron，无付费/模型fallback；只变selector及机械身份路径。两臂原SIF/相同3090硬件。
- 当前预算提案 **280分钟/块，两块名义18.666666666666668 GPUh，计allocation KillWait为19.0 GPUh**。
  原prepared.json/next-budget.json的17.0是已更正的历史提案；8份配置字节不变。
- 预算/准入入口：[PACKAGE_STATE.json](results/forets_next_package_20260911/PACKAGE_STATE.json)，readiness=false。
  [配置报告](FORETS_CONFIG_PACKAGE_20260911.md)、[控制器进度](FORETS_BLOCK_CONTROLLER_20260911.md)。
- 新包：/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4；source子目录。
  组合source tree：3aae90ae26b5ae7b65e6efed14fb49f2907c9c42。
  prepared SHA：d6fcf987924bf696c8a6ea7fb252a6a634ad3fdac9de192a24eb07ec63fee76d。
  预算更正SHA：2137b4e96c365351af1fe1b0d104b71dc15b67831e485ce5641142578b9bb408。
- 控制器独立CPU根：/research/d7/spc/yzyang4/forets-block-controller-20260911-t7d8kr。
  最新runtime/collector根：/research/d7/spc/yzyang4/forets-block-runtime-20260911-75kVIA。
  CLI仍仅inspect；未加载服务/模型、未派发worker。不能通过改readiness布尔值取得实际启动能力。
  见[运行接线与排障](FORETS_RUNTIME_AND_UNBLOCK_20260911.md)；新采集先独立查两块终态，再读pool，最后才交reader。

## 未解决与下一步

1. **GPU映射硬阻塞**：13040只证明指定物理设备0上库能运行；13042真实Jupyter的非零编号步骤选了设备9。
   adapter把Slurm ID直接用作NVML index，没有独立映射依据，已撤回并关闭；**不要重跑、猜编号或放行8-run**。
   13041还暴露登录/计算节点Singularity路径不同；已修代码，但路径修复不解决GPU映射。
   最近新根forets-gpu-adapter-20260911-DosPND保留原错误实现/回执，禁止执行；当前Git入口已关闭。
   GPU9共享约定仍未知，已问学长/管理员未回复；新路径不绑定设备9、不依赖放宽共享约定。
   设备可打开不证明13004使用过它，不据此改写旧结果。原镜像/任务代码不改，不升级Torch、不退CPU。
   自查已知gpu28登记9卡、Slurm19.05.4；计算节点配置SSH被主机身份校验挡住，现有信任记录无匹配，不绕过。
2. **等外界**：checkpoint-100历史训练输入是否含预测指令；当前分支含指令不能证明历史模板。
   权重只读header已证实仅format=pt，不能自行恢复历史模板。问题已留给用户转学长，不再索要权重/密钥。
3. **控制器/读出准备完成**：用户已批准的实现不再索批或重写。缺已独立核实的设备映射/输入事实及实际发行绑定，不能打开release。
   当前无真实runtime manifest；不造终态/成绩，不复用旧execute()。每块需各自新鲜路由回执，不能沿用上块旧检查。
4. 外部事实就绪后固定新协议包、检查免费路由，再按明确矩阵/预算进入真实同预算对照；不追加训练或旧G0。
   读最终选中节点的外部分数，失败与完成率分开；不取轨迹最大分，不拿自报分替代，不跨任务混合原始指标。

## 语料与运行位置

- 新包隔离根：/research/d7/spc/yzyang4/senior-quarantine-20260911-v1。
  manifest SHA：67ac5406b789fa7a5a39f41e9483a095f671f2d25ba47ccf69af4f98264c7cb4。
- LATEST最后观测1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f：
  759总physical / 733 eligible，closure=false；未做本轮重新计数，不解封保护集。
- 13004旧根：/research/d7/spc/yzyang4/forets-resilience-20260910-4LGN21/package，只读保留。
- 权重、tokenizer与服务绝对路径见 [服务入口](forets_e2e_critic_service.py)；只查位置，不重下/重哈希15GB权重。

## 操作边界与续跑

- 用户最新要求：在当前会话连续完成可推进的工作，先自主排障再集中求助；不要每完成小模块就结束让用户续催。
  关键决定/证据及时更新本短交接；不拿重复验收、轮询或新增长审计冒充实质进展。

- 本地Git：C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；外层MLEvolve不是Git仓库。
  只push myfork HEAD:phase1-value-critic。学长branch dojo-reproduce最近fetch仍065b0fba，不改它。
  13042测试代码ef6a4d04现已撤回；最新关闭入口/勘误HEAD每次fetch核实，不以旧成功回执恢复。
- linux5；SLURM_CONF=/opt1/slurm/gpu-slurm.conf；CPU Python=/research/d7/spc/yzyang4/venvs/aira/bin/python。
  模型Python为同根venvs/exp/bin/python；复杂SSH用脚本/scp，避免引号被剥离。
- MLE worker只在兼容gpu27/gpu28（不是projgpu28/39）；两臂同硬件/原镜像；QOS4jobs/8GPU。
  排除projgpu7/8/33、gpu36/38。不得干预12535或他人作业。
- 凭据仅远端.env，绝不存本地/git或回显；新outcome/压缩包credential-first。push前扫描明确暂存名单及完整内容。
- first-960/Target-300/Target-522的标签、结果、预测及私有选择继续隔离；不更新agent底座。
  不恢复HCE、多保真、Probe、score-channel、K≥1 lookahead。保留未跟踪codex_tmp/output/tmp等用户文件。
- 研究盘1TB /research/d7/spc/yzyang4；已知到期2026-09-29，续期未知。
- 已有g0-r5每20分钟续跑，到 **香港2026-09-11 10:38** 截止；不创建重复monitor。
  任务读 [NIGHT_WORK](NIGHT_WORK_20260911.md)；仅有变化才处理，不重跑成功检查填时间。
- 旧交接全文保留在Git aac4acc0:phase1/CONTEXT_HANDOFF_CURRENT.md；更早869行版在684e1c6c。
  即时状态覆盖本文件；历史/失败/撤回保留dated报告与Git，不把每次轮询堆回本入口。
