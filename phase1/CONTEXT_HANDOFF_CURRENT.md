# 当前交接：ForeTS 同预算端到端探索

更新：2026-09-11香港。只维护当前事实，不在顶部继续叠加历史交接。
恢复顺序：fetch → [CURRENT_DIRECTION](CURRENT_DIRECTION.md) 最新节 → 本文件 → 所需证据。
实验前对照 [ADVISOR_DIRECTIVES](ADVISOR_DIRECTIVES.md) L/M/N；历史在dated reports与Git。

## 目标与实测

- **正在推进：无API候选池全执行诊断13085**。13004 leaf/seed6/step1完整三候选代码/历史分数保留；
  原样各执行两次，顺序0/1/2/2/1/0，gpu28原SIF、每次300秒，总≤1GPUh含KillWait。
  不重新生成/重算critic，不恢复旧pool，不拿这个单池即时排序冒充e2e收益。原负结果及8-run计划不变。
  香港2026-09-11 17:08:24提交；17:08:48最后观察RUNNING/gpu28，已有首个真实程序容器binding。
  根/research/d7/spc/yzyang4/forets-closed-pool-20260911-pDXbiZ93；commit eb173ba00656721b095cf9e38e99c13f8f5dbc4c。
  [固定方案/预检](FORETS_CLOSED_POOL_20260911.md)、代码forets_closed_pool_20260911.py；10项新增CPU测试通过。
  尚无结果结论；只看状态/完成后统一读出，不重投或复用旧入口。原无GPU状态仅为先前观察。
- **本轮继续实施**：用户要求继续推进，按CURRENT_DIRECTION 0L156固定现成checkpoint/既有部署输入做探索。
  历史模板仍未知，不改模板、不试选、不冒充训练匹配或干净scaling；不再因该未知无限等待。
  原8配置不变，两任务×seed8/9×两臂，280分钟/双GPU每块、两块含KillWait上限19GPUh。
  新production worker身份/PATH接线已实现，10项新增CPU检查通过（含实际pinned pool派发边界）。
  远端两块静态预检、22文件发布包/Git及231份原源码核对通过；代码commit5c8c07b711e7d3846fc5eda978f1efd6cd0b64ea。
  **当前阻塞：两个免费入口均无有效生成**。原6尝试5超时/1成功保留；本轮Nemotron额外2次均超时，
  Laguna指定函数2次404、改显式auto工具2次429。各窗口预算用完，不覆盖、不继续循环重试或静默转付费。
  新发现：Laguna只声明auto工具支持，不支持强制function/required；0019补丁默认named不变、解析/函数/schema不放宽。
  8项新增CPU检查通过，独立副本真实auto仍429；不是已恢复，限流来源/重置时间未知。
  无READY回执、无GPU提交、无MLE运行；原生产包不变，auto尚未接入生产。
  详见 [当前路由检查/兼容修复](FORETS_ROUTE_RECHECK_20260911.md)。API实际费用未知，不补0。
- **最新实测修复**：13076的两个真实Jupyter步骤在gpu28原SIF均通过CUDA算术与LightGBM OpenCL GPU拟合。
  原生CUDA分别选中物理卡0/1，按UUID→驱动/proc信息绑定，各容器仅见各自单卡；不再将STEP_GPUS作NVML下标。
  执行commit4a7fae18e8dcbd256ccbae13e37c86264fc2d314；根/research/d7/spc/yzyang4/forets-native-gpu-adapter-20260911-y8jOwZ。
  完整字段独立复核与5份原始回执SHA通过，见 [接入结果](FORETS_NATIVE_VISIBILITY_20260911.md)。
  学长反馈已采纳：不要求STEP_ID等于GPU编号，不再索要gres.conf；现有新控制器绕过失修恢复，仅fresh-start。
  新native adapter现有固定探索release生产绑定；真实GPU验证仍限定13076，完整8-run尚未运行，不等于e2e或全节点验证。
  13073metadata首试超时失败保留；13074metadata完成、13075原生身份查询完成；四个allocation均终态且释放。
  本轮含失败合计284GPU秒/0.07888888888888888GPUh，无API/critic模型/真实MLE任务，不重复这些检查。
- 旧13042非零step曾被我方新增adapter误映射到设备9并实际运算；旧接入声明仍撤回、旧入口仍关闭。
  不是学长原实现问题，不复用旧未关闭副本；失败与勘误保留FORETS_GPU_MAPPING_ERRATUM_20260911.md。

- 科学目标：**同预算下，critic是否改善最终选中解的外部成绩**。Corpus/predictor/audit是支撑。
- 13004首对已完成：leaf-classification/seed6，random logloss **0.66022**，critic **2.5208**；
  random−critic **−1.86058**。critic此次更差，仅一个探索seed，不能外推普遍无效。
  [实测与读出](FORETS_FIRST_PAIR_20260910.md)；旧包、失败记录和未启动槽位保持不变。
- 当前没有新的critic收益或干净scaling结论。配置、人工测试、输入编码差异均不是效果结果。
- 最近队列实查：**2026-09-11 08:51:14 UTC / 香港9月11日16:51:14**，只有12535 PENDING/JobHeldUser。
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
  生产接线与固定探索release现已发布；完整分块生命周期因路由未就绪尚未实测，不把准备算模型收益。

## 当前唯一新方案与产物

- 两任务leaf-classification / spaceship-titanic × seed8/9 × uniform_random / critic_topk_random。
  两块，每块4run，顺序预先平衡；不能看结果后重选seed、任务或丢弃失败。
- 相同6步、width4、top2选1、单次执行300秒；worker3540秒、step60分钟；每run100请求、8192输出token。
  固定免费Nemotron，无付费/模型fallback；只变selector及机械身份路径。两臂原SIF/相同3090硬件。
- 当前固定探索预算 **280分钟/块，两块名义18.666666666666668 GPUh，计allocation KillWait为19.0 GPUh**，尚未消耗。
  原prepared.json/next-budget.json的17.0是已更正的历史提案；8份配置字节不变。
- 历史草案 [PACKAGE_STATE.json](results/forets_next_package_20260911/PACKAGE_STATE.json) 仍保留readiness=false，不修改原配置包。
  当前准入另由 [固定探索release](forets_native_e2e_release_20260911.json) 与每块新鲜READY回执共同限定。
  [配置报告](FORETS_CONFIG_PACKAGE_20260911.md)、[控制器进度](FORETS_BLOCK_CONTROLLER_20260911.md)。
- 新包：/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4；source子目录。
  组合source tree：3aae90ae26b5ae7b65e6efed14fb49f2907c9c42。
  prepared SHA：d6fcf987924bf696c8a6ea7fb252a6a634ad3fdac9de192a24eb07ec63fee76d。
  预算更正SHA：2137b4e96c365351af1fe1b0d104b71dc15b67831e485ce5641142578b9bb408。
- 控制器独立CPU根：/research/d7/spc/yzyang4/forets-block-controller-20260911-t7d8kr。
  最新runtime/collector根：/research/d7/spc/yzyang4/forets-block-runtime-20260911-75kVIA。
  原runtime CLI仍仅inspect；新入口是/research/d7/spc/yzyang4/forets-native-release-20260911-dAKj2b/forets_native_run_20260911.py。
  inspect通过；route检查失败；execute缺新鲜READY回执必拒绝。不能通过改readiness布尔值取得实际启动能力。
  见[运行接线与排障](FORETS_RUNTIME_AND_UNBLOCK_20260911.md)；新采集先独立查两块终态，再读pool，最后才交reader。

## 未解决与下一步

1. **GPU等待与生产绑定已解除，路由未就绪**：13076已通过两步真实Jupyter，生产接线10项CPU检查通过；不重查gres.conf/G0。
   新native adapter仅读CUDA选中UUID再解析minor，不再猜Slurm/NVML对应；正确身份/PATH已接到新控制器。
   不能执行旧forets-gpu-adapter-20260911-DosPND副本或本轮换行失败根FJDvAf；不能跳过失败的路由门。
   原SIF/任务代码不改；gpu27未做本次验证，不能把gpu28实测泛化到所有节点。设备9用途无需作为当前启动前提。
2. **历史模板未知已作探索裁决**：保留当前服务输入，不冒充历史匹配；如学长后来提供新事实，另记版本，不途中改臂。
   不重下权重/重复问密钥；本轮可回答固定现成系统的e2e问题，不能据此确认干净scaling或最佳能力。
3. **控制器/读出/native生产接线已完成准备**：代码根dAKj2b、固定release均在；需稳定生成入口，不循环消耗失败检查。
   当前无真实runtime manifest；不造终态/成绩，不复用旧execute()。每块需各自新鲜路由回执，不能沿用上块旧检查。
4. 待用户/学长给稳定入口及本轮费用范围，或免费入口恢复；不重复问密钥。不能把历史泛化批准当作无限付费API预算。
   如换生成器/采样参数，明确新协议并让两臂共同固定，不能在现有Nemotron矩阵中静默混用。
   读最终选中节点的外部分数，失败与完成率分开；不取轨迹最大分，不拿自报分替代，不跨任务混合原始指标。

本轮检查产物与禁止重做：
- 原额外窗口：forets-next-config-20260911-4h_0y6b4/block-1.route-recheck-1，SHA21bb4857...；2次均TimeoutError。
- Laguna原模式：/research/d7/spc/yzyang4/forets-laguna-feasibility-20260911-v1，SHA4b8bf0af...；2次404。
- Laguna auto：/research/d7/spc/yzyang4/forets-laguna-feasibility-20260911-auto-v1，SHAa332ff7b...；2次429。
- 完整SHA/安全本地摘要见FORETS_ROUTE_RECHECK_20260911.md及results/forets_route_recheck_20260911。
- 独立auto后端SHA5cf4f2d5...；补丁生成器forets_auto_tools_patch_20260911.py固定TREE3aae90ae，不能应用到未知源码。
- 三窗口都结束；无后台检查/新monitor。下一次先看用户是否补齐稳定入口/费用范围，不复跑失败窗口或GPU验收。

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
  13042测试代码ef6a4d04现已撤回；新native代码4a7fae18的成功仅限新integration根，不以旧回执恢复旧入口。
- linux5；SLURM_CONF=/opt1/slurm/gpu-slurm.conf；CPU Python=/research/d7/spc/yzyang4/venvs/aira/bin/python。
  模型Python为同根venvs/exp/bin/python；复杂SSH用脚本/scp，避免引号被剥离。
- MLE worker只在兼容gpu27/gpu28（不是projgpu28/39）；两臂同硬件/原镜像；QOS4jobs/8GPU。
  排除projgpu7/8/33、gpu36/38。不得干预12535或他人作业。
- 凭据仅远端.env，绝不存本地/git或回显；新outcome/压缩包credential-first。push前扫描明确暂存名单及完整内容。
- first-960/Target-300/Target-522的标签、结果、预测及私有选择继续隔离；不更新agent底座。
  不恢复HCE、多保真、Probe、score-channel、K≥1 lookahead。保留未跟踪codex_tmp/output/tmp等用户文件。
- 研究盘1TB /research/d7/spc/yzyang4；已知到期2026-09-29，续期未知。
- 六小时窗口已于 **香港2026-09-11 10:38** 截止，已有g0-r5已通过应用工具暂停并独立读回PAUSED；
  未新增监控、未取消无关作业。窗口后用户新反馈触发本次有界修复，不是恢复旧monitor或开放完整8-run。
  本轮fetch公开基线64275f7c9a10550093676397dabd4f19ccd3a3e3，学长dojo-reproduce仍065b0fbaa89e0eb663f2834ec768081f5d56394d；
  新commit通过安全扫描后只push我方phase1-value-critic，最终公开HEAD用Git核实，不回填旧观察为实时。
  不再等权威设备映射；历史输入探索裁决与生产release已落地，当前实际阻塞是固定免费路由不稳定。
  旧窗口完成项见 [NIGHT_WORK](NIGHT_WORK_20260911.md)；本轮没有新增/恢复自动监控。
- 旧交接全文保留在Git aac4acc0:phase1/CONTEXT_HANDOFF_CURRENT.md；更早869行版在684e1c6c。
  即时状态覆盖本文件；历史/失败/撤回保留dated报告与Git，不把每次轮询堆回本入口。
