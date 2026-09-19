# 当前短交接 — 2026-09-19 恢复工作

## 最新授权与方向
用户09-19明确“你继续推进”，覆盖09-14暂停；学长新指定共享盘 mle/comparison，约3–4天更新。
先核ForeTS/MCTS真实同预算端到端数据，不恢复G0、旧失败选择器或关闭的HCE/多保真/Probe/score-channel/K>=1。27B是降API成本替代，“更弱”为学长判断，非我方matched测量。
09-19用户明确允许本轮报告/脚本/脱敏逐run成绩与候选ID/hash推送，并要求三小时内有价值进展。
读取顺序：fetch后的CURRENT_DIRECTION顶部→本文件→现场。新14087已提交；API/模型训练为0。

## 本轮已做（最后观察，不冒充持续状态）
09-19 08:30 UTC队列只有旧12535 JobHeldUser，未动。我方公开HEAD eecc178b29dfff084267c593d34d77e93c2b674d。
学长head 54e8a0e3458e12443658104d244e2b6d9e553451；新0918/VERL_E2E_ANALYSIS_AND_DATA_HYPOTHESIS.md远端credential-first脱敏阅读，原SHA76028d7d03fe4489bdf29d0ea9685b02e9a00f9b40e43f35b6c8c5e15553588c。
共享盘完整root55项，comparison/0912有5个包；comparison/0918标题可见但无链接，未解析，不能说没上传。
发现清单ROOT=/research/d7/spc/yzyang4/comparison-discovery-20260919-pv25nsna，inventory SHA130937f91475e66a065a92c428888578150e0ecc0cbc854ab03b0b177552c9dd。
五包已09-19 08:44:13 UTC下载到独立隔离ROOT=/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6；703326526bytes；manifest SHAd2e9f41bc697651d266a2574f7b9d4a2d7e474c3851b92d504763e9b535c80cb。禁止重下，不入生产/训练。
结构检查74配置；structure.redacted.json SHA2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94。随后只读新Qwen46run（43有checkpoint journal），旧API28配置未读结果；env均未读。
原配置已见ForeTS既有6/top3又有9/top2，MCTS预算亦有82800，不能统一按报告6/top3及86400解释。
分析脚本journal_to_fig源码已远端脱敏（0shape），原SHA2c73ea117a7d047004da9ccbc64297526a571f720617969d6cf32a90ea926df7。
本轮方案：COMPARISON_FOLLOWUP_20260919.md；代码phase1/scripts/{discover,quarantine,inspect}_comparison_20260919.py。
09-19 08:58:52 UTC探索读出完成：ROOT/qwen-readout-v1；保护LATEST=1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f，身份SHA245c3a78a0571c5b09a46f1bf546443cde28c0fbc01719b2b8ce934da6f77708，最新起始09-07；本批配置/节点起始09-12之后且journal哈希无交集。0credentialshape。
43有journal的run中绘图选择与按solver方向/buggy过滤选择均未改变，不把源码潜在差异冒称实际胜负翻转。各run耗时明显不同，无hardware/总GPUh完整事实，当前仅描述性对照，不宣称同预算因果收益。首次因Leaf140885450-byte journal超过128MiB门失败且未发布结果；核大小后上限改256MiB，跳过重复大写事件日志，选择规则不改，8测试通过。
独立核验已完成（independent.json SHA da5667d1973f678125c26f0186a17bc9775ae7270b49304412cc027038bf092d）。共享seed描述比较：Pizza2胜3负，Spooky1胜4负，Leaf2胜1负，AI4Code仅1可读配对1胜；硬件/实际时长不配平，无稳定同预算效应结论。F2的9–13与MCTS1–6不能配对。
25完整初始六候选池（Pizza10/Spooky10/Leaf3/AI4Code2），每池2已执行+4未选、6distinct raw code hash；100初始未执行程序，整段搜索480未选节点。不是语义多样性或可执行性证明。清单及逐run安全导出在phase1/results/comparison_qwen_20260919；未运行新replay。
排名日志元数据检查：46个新Qwen根仅配置/env/JOURNAL/评分/checkpoint文件，0文本日志。未读env；源码info中的critic数值日志未随包提供，不能从异步顺序猜rank。现有original_ranks_available字段仅指journal顶层字段。回执SHA6c2eb42e29a44dc591aa509873e9d999256aa2113893a12e87700c6f18a36c81。
发布前8测试重跑通过，另目录独立重算independent.json/root_pool_inventory.csv均字节相同。明确stage22文件、敏感文件名0、credential-shape0、diff检查通过。先前推送被安全审查拦截，用户随后明确许可；09-19已正常推送并ls-remote核对公开head abb79d1f936d9e93d35a999ba88a3e0f9010744e，无学长分支修改。
曾遇子目录无链接导致发现脚本拒绝，现保留其他已核目录、子目录标未知；首次下载用aira环境缺gdown，零下载，改用既有exp环境完成。不安装/升级依赖。

## 下一执行点
1. 主比较读出/独立复核/下载/推送均完成，不重跑reader或覆盖结果。报告COMPARISON_FINDINGS_20260919.md；保留无关untracked。
2. 继续当前14087，不另起重复作业：ROOT=/research/d7/spc/yzyang4/comparison-pool-20260919-7ujiaajp，prepared SHA394470c82755bdebf02d34c86f7474ef950a178f5718c4c0ca87ac24882e98a5，源码0adcf0f365b0ba68475cb79ed28cff77ab6cd407。最后观察09:56 UTC seed1六程序池闭合、seed2已启动；9条程序结果文件、12份GPU隔离回执，第一池六物理GPU不同。新成绩未读。
   矩阵Leaf seed1→2→3每池6原程序、7200s，gpu28六GPU/36CPU/150min≤15GPUh，0API/训练；仅剩余≥7500s才开下一整个池，否则未启动。新fresh-container干净工作区、原镜像，不冒称学长历史环境。18路径CPU mock及8组合测试通过；首次宽泛unittest discover误导入旧包，直接跑本测试文件已通过，非结果修改。
   全allocation结束后readout_comparison_pool_20260919.py读出，原选二vs均匀15组合。best-of-two为oracle诊断，不是部署策略/E2E；新结果未读，不按中间胜负调度。
3. 原选择的两个候选已知，故同池uniform对照不依赖重建原完整rank；缺原rank就不声称top3召回。原任务7200秒上限不可静默缩成低保真评测。
4. 检查comparison/0918的新可解析共享内容可按元数据续查；未解析不等于未上传。新outcome已读，因此只称探索性复核。RL63.37 vs BT60.01非matched算法效果。
5. 先核未来实验真实完成时间、GPU总资源、镜像/数据；同池效果和fresh-seed同预算E2E分开。不重做G0、不以审计报告取代效果实验。
6. 新成绩前已冻结top-3第三条缺失的四种可能分析，不猜完整rank；13单测通过。全allocation终态后运行prepared目录原reader，独立pair verifier及topk bounds；见COMPARISON_TOPK_BOUND_PLAN_20260919.md。
7. 并行历史成本诊断完成：25/25池最慢生成请求长于原选两程序exec_time之和，Leaf逐池比值中位5.12。客户端含排队/重试且13池原选无非buggy有限grade；不是GPU服务时间、缩宽收益或E2E正结果。25池独立join与6单测通过，见COMPARISON_COST_FINDING_20260919.md，相关工作强重叠见COMPARISON_NOVELTY_CHECK_20260919.md；不把廉价critic+昂贵验证当原创。

## 保留的27B接入（不重下载、不重跑旧任务）
ASSETS=/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy，17模型文件+镜像共18资产，模型revision dc430725f831dd90d9271738b877879a46a82239。
旧13365/13366/13367启动失败，80/123/369秒，均0draft。13368由用户暂停而取消（sacct00:21:21）；09-19复核仍仅generation-0.json，Leaf正常stop610.6572284079157秒，24110输出token、12659代码字符；另一个draft和MLE执行未完成。
ROOT=ASSETS/integration-v6，部署df785db5adaf6aeef1dd7f2f3885da141c4e7260，prepared21d01b917dd8de716bf1bc1a19a38058e236b21da29c81ec50d1b2a1d5356d61。
服务认证、2+1GPU隔离、两数据预览/预热已过；不等于新critic效果。服务临时盘与spawn修复在旧commit中；不可再次从旧错误入口提交。
09-14清理已完成：只删除已核对的旧公开权重/压缩包，现用模型/语料/结果保留，不能重复清理。

## 既有科学证据边界
09-14主报告FORETS_SIX_HOUR_EVIDENCE_20260914.md：20真实搜索+24同池执行。短代码探索4配对胜未通过新seed重复；类别门收益未发生相对连续排序的实际选择改变。9/12初始池双无效、3混合、0双有效，不是普遍无机会。旧结果不重跑、不删负例。
既有ForeTS实现/新comparison生产及训练归学长；我方独立复核、接入和实验分别归因。

## 位置与硬边界
SSH linux5；SLURM_CONF=/opt1/slurm/gpu-slurm.conf；MLE用gpu27/gpu28原镜像，禁projgpu39/Torch升级/CPUfallback。旧12535不动。
Python aira用于分析/任务，exp有gdown。密钥仅远端.env，不回显/本地/git/重索。原始包可能带env，只在远端先扫描脱敏，永不整包复制本地。
保护first960/Target300/522仍封，不训练agent底座。研究盘1TB到2026-09-29，续期未知。
只push myfork HEAD:phase1-value-critic，不修改学长分支、不force、不新建无必要branch。不stage无关untracked。
