# 当前短交接 — 2026-09-19 12:50 UTC
只记最后观察；恢复顺序为fetch后CURRENT_DIRECTION顶部→本文件→现场。详细历史留Git/dated reports，不重复旧实验。

## 当前授权和方向
本轮新请求12:10 UTC开始，目标15:10 UTC前实质结果；用户明确不要每次写汇报（需其再要求），只更新必要短交接/实验配置。原发布授权继续，不改学长分支。
主问题仍为固定生成器/总资源下ForeTS/critic能否改善真实E2E；目前先补完整候选池反事实。27B为降API成本替代，不能称已验证更强。
不重复G0、旧失败选择器或关闭HCE/多保真/Probe/score-channel/K>=1；first960/Target300/522结果仍封，不更新agent底座。

## 当前推进
comparison_reuse_plan_20260919.json固定首个失败后的动作对照：Spooky forets-1 seed1/2，每组六程序＝原首个失败draft＋其首个直接debug＋四条未选初始程序。总12程序、原7200秒/原镜像、6GPU/36CPU/150min≤15GPUh，零API/训练，不自动续跑。
14115已实际提交并执行，12:30观察第一组4结果、6唯一GPU、全部namespace绑定正确。ROOT=/research/d7/spc/yzyang4/comparison-reuse-20260919-5m6jrtah；prepare SHA5d7e98280f3b223bbf8c6968ebd3c84857b5329eac0744a51d3c16d3ced24518；execution commitef41925bed94b5de01efd1b95eab652720c81bb8（已push）。9CPU测试及12实际配置/代码交付mock通过，无准备失败或GPU重投。
不得重投14115；所有已启动组及allocation终态前不读新成绩。完成后仅调用ROOT/readout_comparison_reuse_20260919.py ROOT一次，保存安全summary/runs至新的comparison_reuse_20260919结果目录，独立核单候选概率和代数。不能把历史debug代码复跑当新LLM调用或E2E；首个前缀必须复现原错误，单cache均匀选择不得用oracle挑最好。生成时延只做独立/符号分析。
父索引是journal整数step，不是node ID；已核每run index1初始draft/index2直接debug，避免错配。已知缓存结果使本轮只能探索，两个原始run不是12独立seed。

12:49最后观察14115第一组5结果，未闭合；未读新成绩。独立读出核验器verify_comparison_reuse_results_20260919.py已写，5测试含1024种质量/有效性组合通过；完成后对safe summary运行一次。
forets_cached_continuation_20260919.py开发适配器已完成10项CPU控制流测试，使用be9335348b实际扩展函数（仅任务/生成传输mock）。关闭开关返回原类；每池最多均匀尝试一未选兄弟，独立RNG、正常执行/分析计步，成功回传兄弟路径而非失败节点。尚未部署；需两臂共同外层时间/步数门，不能将官方validity回放等同LLM分析接受率；不支持中途expansion恢复。首次时钟测试因全局mock干扰asyncio失败，已隔离时钟重过，未产生GPU作业。
12:37学长新head67e371960802d804bdab8b9b55f3dde2ed98f125；三篇文档差异远端凭据扫描0hit后读（read_senior_delta_20260919.py）。是小任务集训练/评估用法/可视化更新，无新效果结论，不改14115配置。12:45共享comparison/0918双读仍0可见文件，不代表未上传；回执comparison-0918-metadata-20260919-y5ulx468，listing SHA仍d36f39e6e9476279df19da46f006f182236737f29e64e5808e93733d676ae239。

## 上轮已闭合
Spooky完整池job14099已COMPLETED，1960秒/6GPU=3.2666666666666666GPUh。前两池共12执行，3有效9无有效提交；seed3六条因固定剩余时间门未启动，无续跑或换seed。11:41队列只见旧12535 PENDING，未动。
ROOT=/research/d7/spc/yzyang4/comparison-spooky-pool-20260919-04qsl2xc
commit=93cf17a16f4dc9cefeb3ea003c5ac3beb6ec57e4
prepared=e3337e7affc534e6e0c3e4e2a75571fc08a9b4a7c271877a71073dda5e8917d6
固定Spooky forets-1 seed1→2→3，每池6原程序，最多18；原镜像/7200s、6GPU/36CPU/150min≤15GPUh、0API/训练。少于7500秒不开下一整个池，不自动续跑/补seed。COMPARISON_SPOOKY_EXECUTION_20260919.md。
7个CPU合成测试+18实际driver mock通过，未重复GPU验收。首次准备遗留输出变量NameError；修复第一次scp失败，第二次prepare仍旧文件同错；均0GPU/模型调用。重传hash一致后新目录prepare→mock→submit成功，失败目录保留。不能重投14099；root reader已完成，不能再运行覆盖。
Spooky summary SHA721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1，安全副本results/comparison_spooky_pool_20260919。
seed1三有效但原选二都失败，0胜3平12负；top3任何第三条下随机抽二有效概率最多2/3<均匀4/5。连续质量净效应仍不识别。seed2六条全失败，只重排当前池不可能获得有效提交。
四条原选同代码终端错误逐条在历史生产日志复现；九新失败是regex/错误API参数/liblinear多分类/Booster.classes_/未定义model，非程序超时，无GPU架构/readiness标记，未修复重试。官方/独立数值和全部已固定辅助分析通过；未知六条保留。
本轮合计30实际执行，12有效18无有效提交，6未启动，8.738333333333333GPUh，零API/训练。Leaf两正例仍成立，跨任务一致优势未过；不自动扩大硬淘汰或重训。有限复用未选候选仅待验证假设，未实施。

## 已完成的实质结果
Leaf原定18条全闭合：14087做seed1/2（1888秒），14091只补未启动seed3（1395秒）；均COMPLETED。9有效9程序失败0未知，实耗5.471666666666667GPUh，0API/训练。
seed1/2/3：原选best .06983/1.80818/.11709；全池best .06983/.12444/.11709；原选二vs15uniform二选胜平负分别10/5/0、1/2/12、10/5/0。
官方与独立数值、独立组合核验通过。未知top3第三条四种可能下seed1/3均正、seed2不识别；等池效应边界[-.029629629629629645,.37777777777777777]跨零，不能称稳定总体/E2E优势。
新fresh环境不同历史Jupyter/硬件；原选也重跑，未拼历史分数。seed3一输出行和偏差最多1.850020151517029e-07，原容差及五位数值一致，未改提交。
报告ADVISOR_PROGRESS_20260919.md；安全数据phase1/results/comparison_pool_20260919/{remainder,combined}。
合并summary SHA41e42fbff91ca970e8f5ee19a1ffdf57c31ffe0ddd6a24182e5e304c1225ef4f。
14087 ROOT=/research/d7/spc/yzyang4/comparison-pool-20260919-7ujiaajp，summary238bd65e00edd0f678b1f9dc6fbce0c92bf49247030765b64c703ed4d469547a。
14091 ROOT=/research/d7/spc/yzyang4/comparison-pool-20260919-1z7l72bz，summary051c550d80b3d9fa50d592f6a615d1ebb02c14a87c6c2dbf0a861b928b52bae4。reader均已跑，不能覆盖/重跑。

## 并行发现（非方法收益）
readiness故障16/957非根执行节点、11/43run、约120s；源码先于候选执行返回却加“2h执行超时”。Leaf seed1一条同代码此次38s成功loss.06983。不能外推所有错误可恢复。
COMPARISON_RUNTIME_FINDING_20260919.md；本地补丁加timeout_phase/区分反馈，5CPU控制流测试过，已发布，不部署到本轮远端源码，不声称修好startup根因。
25/25初始池最长生成请求>原选两程序exec总和；Leaf逐池比值中位5.12，但含排队/快失败、不是GPU服务时间或缩宽收益。COMPARISON_COST_FINDING_20260919.md。
相关工作见COMPARISON_NOVELTY_CHECK_20260919.md；AGRV/RPM/MARS已强重叠，Speculative Actions/PASTE也覆盖宽泛重叠执行，不因而开启旁支。

## 数据、发布与后续入口
学长head54e8a0e3458e12443658104d244e2b6d9e553451；0918新outcome已credential-first脱敏阅读。比较生产归学长，独立分析/完整池执行归我方。
comparison/0912五包已下载703326526bytes，不重下；ROOT=/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6，manifest d2e9f41bc697651d266a2574f7b9d4a2d7e474c3851b92d504763e9b535c80cb。
structure SHA2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94；只读新Qwen46配置/43journal，旧API28未读、env未读。新起始09-12以后与保护LATEST1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f的日期/journalhash隔离已过。
原始排名info日志未随包给出，不能从异步顺序/新checkpoint分数猜原rank。25完整初始六候选池的安全导出在results/comparison_qwen_20260919。
11:44再次fetch学长head仍54e8a0e3458e12443658104d244e2b6d9e553451，0新doc读取。0918共享视图双读仍0文件，不等于学长没上传；新回执comparison-0918-metadata-20260919-ptruckdp，SHAd36f39e6e9476279df19da46f006f182236737f29e64e5808e93733d676ae239。
11:24已正常push并ls-remote确认05c577c8535040775e4e9065ccfdfec98f88efa9；新增14文件扫描0shape/0敏感文件名，包含CDF/质量成本/硬筛选辅助分析。前一发布ea6e55fd包括Leaf主结果及反馈修复。只myfork HEAD:phase1-value-critic，不改学长分支、不force。保留无关untracked。
14099 root reader和本地verify/topk/summarize/CDF/quality-cost/pruning均完成，输出exclusive，不重跑。Spooky概率行和最大偏差1.200000001588819e-07，在原容差内，未归一化改分。
辅助方法已在读Spooky分数前写成并测试：verify_comparison_stochastic_dominance、analyze_comparison_quality_cost、analyze_comparison_pruning_loss（均20260919）；分别6/5/4测试。Leaf事后结果：seed1/3对所有第三条在全部质量门槛CDF占优；seed2硬筛选必排除至少2更好有效程序、边界错误4–9/9，但top3净效应仍不可识别。不是新策略或E2E；不要把只知净效应不识别误写成完全不知筛选有错。
此前Spooky结果、图及跨任务裁决已发布c3a35d6db3da896c5cdd76ce2acc3efac27760f3，23文件扫描0凭据形状/0敏感文件名，summary与原SHA一致。此前作业不重复reader或辅助分析。leaf-spooky-candidate-pools.png已视觉核验，SHAe0b328a3ee24371c18cf18c7719311835a560697a5e972f8326aa6a2e2954dce；Leaf最初裁剪差的candidate-pools.png不发布，readable版已核。
11:45复查误用unittest discover导入无关critics/mock相对路径报错；改直接运行四个目标文件，7/6/5/4项全部通过，未修改无关包。不把发现命令整体称通过。短暂SSH中断只读重连成功，未重投作业。

## 固定环境/不要重做
SSH linux5；BASE=/research/d7/spc/yzyang4；Python venvs/aira做任务/分析，venvs/exp有gdown；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
MLE用gpu27/gpu28 RTX3090原镜像；禁projgpu39/Torch升级/CPUfallback；旧12535不动。密钥仅远端.env，永不回显/本地/Git；tar先远端扫描脱敏。
原任务SOURCE=/research/d7/spc/yzyang4/forets-wallclock-20260912-km65uuej/source，tree61b48862532d048f5f04a517e3f89b211c59bd3d。
27B完整资产已有local-qwen27b-20260914-zcx1k1dy，18文件36808331288bytes，revisiondc430725f831dd90d9271738b877879a46a82239。旧13368用户取消只完成一draft，不重复下载/G0；旧容量清理已做不重删。研究盘1TB到2026-09-29，续期未知。
