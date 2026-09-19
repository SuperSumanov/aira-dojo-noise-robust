# 当前短交接 — 2026-09-19 11:03 UTC
只记最后观察；恢复顺序为fetch后CURRENT_DIRECTION顶部→本文件→现场。详细历史留Git/dated reports，不重复旧实验。

## 当前授权和方向
用户明确恢复09-14暂停、允许新comparison报告/脚本/脱敏逐run成绩与候选ID/hash正常push，并要求本轮三小时内实质进展（09:26 UTC起，约12:26 UTC）。
主问题仍为固定生成器/总资源下ForeTS/critic能否改善真实E2E；目前先补完整候选池反事实。27B为降API成本替代，不能称已验证更强。
不重复G0、旧失败选择器或关闭HCE/多保真/Probe/score-channel/K>=1；first960/Target300/522结果仍封，不更新agent底座。

## 正在执行
Spooky完整池job14099，10:59提交、11:01观察RUNNING gpu28，seed1已有3结果，6唯一GPU隔离绑定全true，新分数未读。
ROOT=/research/d7/spc/yzyang4/comparison-spooky-pool-20260919-04qsl2xc
commit=93cf17a16f4dc9cefeb3ea003c5ac3beb6ec57e4
prepared=e3337e7affc534e6e0c3e4e2a75571fc08a9b4a7c271877a71073dda5e8917d6
固定Spooky forets-1 seed1→2→3，每池6原程序，最多18；原镜像/7200s、6GPU/36CPU/150min≤15GPUh、0API/训练。少于7500秒不开下一整个池，不自动续跑/补seed。COMPARISON_SPOOKY_EXECUTION_20260919.md。
7个CPU合成测试+18实际driver mock通过，未重复GPU验收。首次准备遗留输出变量NameError；修复第一次scp失败，第二次prepare仍旧文件同错；均0GPU/模型调用。重传hash一致后新目录prepare→mock→submit成功，失败目录保留。不能重投14099。

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
COMPARISON_RUNTIME_FINDING_20260919.md；本地补丁加timeout_phase/区分反馈，5CPU控制流测试过，仅待发布，不部署到本轮远端源码，不声称修好startup根因。
25/25初始池最长生成请求>原选两程序exec总和；Leaf逐池比值中位5.12，但含排队/快失败、不是GPU服务时间或缩宽收益。COMPARISON_COST_FINDING_20260919.md。
相关工作见COMPARISON_NOVELTY_CHECK_20260919.md；AGRV/RPM/MARS已强重叠，Speculative Actions/PASTE也覆盖宽泛重叠执行，不因而开启旁支。

## 数据、发布与后续入口
学长head54e8a0e3458e12443658104d244e2b6d9e553451；0918新outcome已credential-first脱敏阅读。比较生产归学长，独立分析/完整池执行归我方。
comparison/0912五包已下载703326526bytes，不重下；ROOT=/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6，manifest d2e9f41bc697651d266a2574f7b9d4a2d7e474c3851b92d504763e9b535c80cb。
structure SHA2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94；只读新Qwen46配置/43journal，旧API28未读、env未读。新起始09-12以后与保护LATEST1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f的日期/journalhash隔离已过。
原始排名info日志未随包给出，不能从异步顺序/新checkpoint分数猜原rank。25完整初始六候选池的安全导出在results/comparison_qwen_20260919。
0918共享视图10:03双读0文件，不等于学长没上传；回执comparison-0918-metadata-20260919-zoc4kjov，SHAd36f39e6e9476279df19da46f006f182236737f29e64e5808e93733d676ae239。
公开head最后确认0a393f07d3499f2c55a8c501b58739eeb51a09dc；后续d561/bb779/93cf及本轮结果待正常push。只myfork HEAD:phase1-value-critic，不改学长分支、不force。保留无关untracked。
14099整个allocation终态后，只运行ROOT内readout_comparison_spooky_pool_20260919.py一次；下载安全summary/runs至results/comparison_spooky_pool_20260919，再运行verify_comparison_pool_results_20260919.py、analyze_comparison_topk_bounds_20260919.py、summarize_comparison_pool_20260919.py。未知不填分，不自动补池。
当前主要待办：推送Leaf报告/安全结果/反馈补丁；在会话里核14099、完成跨任务读出，按真实结果裁决。新稿未完成前不把待验证方案称正结论。

## 固定环境/不要重做
SSH linux5；BASE=/research/d7/spc/yzyang4；Python venvs/aira做任务/分析，venvs/exp有gdown；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
MLE用gpu27/gpu28 RTX3090原镜像；禁projgpu39/Torch升级/CPUfallback；旧12535不动。密钥仅远端.env，永不回显/本地/Git；tar先远端扫描脱敏。
原任务SOURCE=/research/d7/spc/yzyang4/forets-wallclock-20260912-km65uuej/source，tree61b48862532d048f5f04a517e3f89b211c59bd3d。
27B完整资产已有local-qwen27b-20260914-zcx1k1dy，18文件36808331288bytes，revisiondc430725f831dd90d9271738b877879a46a82239。旧13368用户取消只完成一draft，不重复下载/G0；旧容量清理已做不重删。研究盘1TB到2026-09-29，续期未知。
