# 当前交接：ForeTS 同预算端到端探索

更新：2026-09-11香港。只维护当前事实，不在顶部继续叠加历史交接。
恢复顺序：fetch → [CURRENT_DIRECTION](CURRENT_DIRECTION.md) 最新节 → 本文件 → 所需证据。
实验前对照 [ADVISOR_DIRECTIVES](ADVISOR_DIRECTIVES.md) L/M；历史在dated reports与Git。

## 目标与实测

- 科学目标：**同预算下，critic是否改善最终选中解的外部成绩**。Corpus/predictor/audit是支撑。
- 13004首对已完成：leaf-classification/seed6，random logloss **0.66022**，critic **2.5208**；
  random−critic **−1.86058**。critic此次更差，仅一个探索seed，不能外推普遍无效。
  [实测与读出](FORETS_FIRST_PAIR_20260910.md)；旧包、失败记录和未启动槽位保持不变。
- 当前没有新的critic收益或干净scaling结论。配置、人工测试、输入编码差异均不是效果结果。
- 最近队列实查：**2026-09-10 21:32:51 UTC / 香港9月11日05:32:51**，只有12535 PENDING/JobHeldUser。
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
- 新控制器核心13项CPU测试已通过；新读出20项通过并与远端8配置核对，均勿重做。真实服务/硬件入口仍未完成。

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
  这里只有inspect入口；未加载服务/模型、未派发worker。不能通过改readiness布尔值取得实际启动能力。

## 未解决与下一步

1. **等外界**：GPU9共享约定及受支持的单卡OpenCL暴露方式。已问学长/管理员，未回复；不重复试/dev/null绑定。
   设备可打开不证明13004使用过它，不据此改写旧结果。原镜像/任务代码不改，不升级Torch、不退CPU。
2. **等外界**：checkpoint-100历史训练输入是否含预测指令；当前分支含指令不能证明历史模板。
   问题已留给用户转学长，不重复索要权重/密钥，不猜模板并改生产默认。
3. **读出已完成**：用户明确批准后的[新读出实现](FORETS_BLOCK_READOUT_20260911.md)已验证，不改旧reader、不再索批。当前缺真实runtime manifest，不造终态/成绩。
   新控制器服务启动/退出的实际限时仍未完成；核心不用重做，不复用旧execute()，不能称完整控制器已部署。
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

- 本地Git：C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；外层MLEvolve不是Git仓库。
  只push myfork HEAD:phase1-value-critic。学长branch dojo-reproduce最近fetch仍065b0fba，不改它。
  本轮起点HEAD为a2c3fcde5d4bf6167cef51771f6083cf9a249e57；最新HEAD每次fetch核实。
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
