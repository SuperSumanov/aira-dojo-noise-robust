# 当前短交接 — 2026-09-14 12:48 UTC

## 当前裁决与用户
方向以CURRENT_DIRECTION 0L210为准。用户要求把资产变成重要、独特、充分证明的同预算E2E主张；不接受只堆审计/G0。必须实际推进但不制造正结果。
原六小时窗口09-13 21:06:43→09-14 03:06:43 UTC；最后新作业03:10:02结束，独立读出06:04–06:18完成，收尾晚于目标，不假装准时或虚构网络原因。
学长新回复：27B INT4是较弱的降API成本替代，不是更强生成器；建议我方一次申请8卡、2卡部署生成服务，提供vllm.sif下载链接。
不再等待共享endpoint；27B完整下载/校验已完成，已提交13365自有gpu28三卡接入作业，是否运行以现场核验为准。不借allocation、不索key。
下一对照区分筛选机制与同总GPUh系统效率，不让无critic基线闲卡来证明划算；原短时间预算不盲搬。无新自动任务。
此前GPU/API实验全部结束；本轮新提交13365（≤3GPUh），0付费API/fit，不重复旧读出/补seed/调门槛。

## 正在推进的27B接入

用户授权清理已于12:10:25 UTC完成：7月公开Qwen2.5-Coder 14B/7B的10个分片全部上游SHA吻合后删除，回收44,771,426,304bytes。
54个配置/tokenizer/下载元数据保留并复核；当前critic、两镜像、语料、结果、venv不动，未递归删除。
cleanup ROOT=/research/d7/spc/yzyang4/research-storage-cleanup-20260914-mlaygiaj；plan SHA f2ac6247a4d4c00c8787dc67c0c8e66aa09d3eb9ee8d01daa4da1faa2d7c9b80。
reclaimed SHA 0c6f9d1c3cb7b0cac13e175d7c573c5c60008339303a5535ed044809d771cf9e；实际40GiB分配PASS且临时文件已释放，容量回执1ece8dace830567c29a115c90db3b5cf606145eb89dbedaea7fd853a8aa79c57。
当前27B空间阻塞解除，缺少文件28,868,542,488bytes开始下载。此批及前轮12GB压缩包均已删除，禁止重跑清理。最后squeue仅12535旧held，未改。
12:18首次下载PID1918178已失败退出：202byte generation_config的307响应330bytes被curl的max-filesize=202拒绝，非上游漂移；直接下载202bytes与上游hash吻合。
仅将小文件传输上限提高到1MiB，最终size/hash不变，5个本地针对性测试过（最初unittest discover误导入其他包失败，后改直接测试入口）。
12:20新唯一launcher1919652，日志download-weights-redirect-fixed.log，7200秒上限/独占download.lock。capacity.json申请31,016,026,136bytes并实际分配31,016,030,208bytes后释放；12:41:49已完成5/6片，第6片831,004,672/3,139,552,912bytes。完整complete.json尚未出现，不重启旧launcher或重复下载。
local_generator_runtime_20260914.py已写controller/server/worker/prepare/cpu/submit，有界3卡60min/12CPU；ROOT/integration只做CPU测试，从未提交，保留为历史。
旧CPU包commit968e77fa6ef1074b3380fe862859774ab15782d1，prepared SHA69dd299aafb61120b97c6c23cc5e52f52138bac61d1f77666182d6fe06d76d20；12:30配置预检、12:32实际驱动双draft mock-transport都PASS，0真实推理。
12:38生产准备转ROOT/integration-v2，新增未认证401→专用凭据唯一模型检查；6驱动单测通过，预算/模型/任务未改。旧integration禁止submit。
v2已12:40:16 prepare，commit5954661954adb6dabc5a953fe6a2f06ef6831cd9，prepared SHA4e7c441cd27486231bfaf7229f3a5efb622bdce0fd11941b4259b2b42fda592d；12:40:36四配置CPU门PASS，12:41:14双native draft mock-transport门PASS，0真实推理/执行/GPU。三回执已复制到results/local_generator_integration_20260914/v2，不能覆盖旧v1回执。
12:42现场gpu28 idle/9RTX3090，用户squeue仅12535旧held；这不是资源预留。
12:44全部6分片/17模型文件已落盘，仍等最终镜像重核/complete。发现接入asset_check硬编码17少算了镜像；固定plan实际18项。已改按固定plan SHA982e97a454ee502f89a0df72b2c3ae1626d24cc942f828137ed6f45aaaf8e4cd检查完整集合/重复，7驱动测试通过。
生产已转integration-v3，v1/v2均只CPU测试且未submit，不能运行。v3 commitd58c43d29ea5891f24bce0ff585c1fcf07cb4a84，prepared02527b5874cf96397ec5957e1574cdea785087827cc86c0f64b63d2c81c5ca4c；12:47前cpu及双native mock-transport门PASS。
完整18资产于12:45:46 UTC校验完成，总36,808,331,288bytes、模型28,868,542,488bytes；complete SHA0d5c2f4a0c46b4e9b151b584582834f8054f5013be7287a378bed3bba3078b2a，launcher已退出。禁止重复下载。
12:47:28已提交job13365到gpu28：2卡服务＋1卡原MLE执行、12CPU、60min≤3GPUh。12:47:58 squeue RUNNING/29秒；12:48:02服务真实Torch2.13+cu130双卡CUDA计算正确，启动中，尚未真实draft。ROOT/integration-v3/launch.json为唯一新提交回执；不得重复submit。监控已上传status_local_generator_20260914.py（指v3），不读raw response/.service.env/旧保护集。
status_local_generator_20260914.py只看资产/公开结构字段、脱敏启动日志，不读模型回答、.env、原程序输出或保护集。
新4项驱动单测＋5项下载器单测通过，远端4条真实FreshContainer配置解析通过。Slurm19.05.4无--exact，提交前已删除该参数；保持既有exclusive分卡。
服务容器入口python3 -m vllm.entrypoints.cli.main已静态确认，保留原CUDA库路径，不把服务--nv路径替换到MLE。service/worker UUID不相交门在真实请求前。

ROOT=/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy。
完整18资产（17模型文件＋镜像）36,808,331,288bytes；39GB临时容量申请两次EDQUOT（第二次在回收后），两次下载均未开始。
已核完并仅删除旧critic压缩包12,051,153,651bytes，三个原成员全部保留，当前15GB权重未动；可由原模型分享恢复压缩包。
回执在forets-critic-incoming-20260908-3lcjjcwq/archive-reclamation-20260914.json。禁止重跑清理；本地一次性清理脚本含原私有分享链接，不公开。
官方uv cache prune只删51缓存文件、工具估算309.5KiB，不是18GB；未清venv/模型/语料/结果。学长共享镜像和权重路径仍Permission denied，不绕过。
后改为只下镜像：10,087,272,448bytes临时预留成功；11:38:54 UTC开传，11:46:47完整7,939,788,800bytes校验完成。
image-complete.json：SHA 495ca35a3fa7fc534bbd855829af1b86ce75ab9a5675b3b1ab7dba58ca74b7fa；这是自行计算，分享方无独立hash。
image-inspection.json只读核vLLM0.29.0/Torch2.13.0+cu130/Transformers5.16.1；支持VLLM_API_KEY环境变量，尚未生成/使用真实local key。
镜像无python命令，/usr/bin/python3可用；裸vllm入口未核，不照搬CLI。未加载模型/使用GPU；原MLE镜像不改。
镜像launcher1884813/子1884814已退出，两个先前失败launcher1868393/1881905也退出；不重下/不重启。模型空间已于12:10解决，后续下载须新建尝试日志且复核容量。

新源码tree b87178bf16d78c7217f2c88b85faf002553b2d7f，base b7f8ab0f65dba9877ac3af35e3e770fc32546565；
source.tar SHA c1206c13df05d9ab6b73119aabfb75820e90807e55a76f9f288f5d305a769291。只改本地认证/有界transport，不改闭合source/学长分支。
9本地测试过（6adapter+3容量计算）；远端真实GenericLLM文本/JSON两调用、两个真实任务native draft路径CPU mock transport通过，0真实推理。
修复只对本地模型容许1200秒，旧付费provider仍300秒上限，本地强制1次/无付费回退，记录finish_reason；成本标志不代替实际GPU账。
calibration-inputs SHA 7da450b0e9a2517216de79f8ad4398621d68bd615a865b259784cb37608d1f77；真实数据预览/生成/执行尚未跑。
拟Leaf/Space×新seed49，各1draft；3卡(2服务1执行)/12CPU/60min≤3GPUh，有界配置见LOCAL_GENERATOR_CALIBRATION_PLAN_20260914.md。
v3代码接线、CPU预检、完整资产已齐并提交13365；不能把提交称为真实GPU预检已过。无需等待学长回复。

## 已完成、独立验证的新结果
13311 FAILED（冻结准入截止正常占多数，但1个异常），gpu28/3808秒/1.0577777777777777 GPUh。
ROOT=/research/d7/spc/yzyang4/forets-wallclock-20260912-9uosb6me
STAGE=/research/d7/spc/yzyang4/forets-class-gate-stage-20260914-RWKXbwxc
OLDSTAGE=/research/d7/spc/yzyang4/forets-cheap-v2-stage-20260914-bqkP9eR8
8搜索：Leaf/Space×48×uniform/short_code/learned_validity/class_gate。7技术合格、1原资格未知，8原提交数值重评分。主action=次iteration。
Leaf48随机 .37782；短代码/连续/类别门均1.51485（loss↓）。
Space48类别门 .81264；短代码/连续 .79655（accuracy↑）；随机不合格，留下 .79655只保存，不算胜负。
主投资门FALSE。短代码新Leaf输随机，Space对随机未知，不称旧4/4已重复。
重要机制反证：Space类别门实际4池均一条p>.5另一条<.5，其选择与连续排序4/4相同；“类别内随机探索”在该run未发生，不能归因+1.609pp于门控。Space门控最终好代码来自debug；Leaf随机改善也来自debug，非因果修复证据。
异常根因：Space随机batch4选中的9052字符原响应经原生extract_code为空，ExecutionWitness schema gate，非GPU/密钥。原技术资格不改，不补跑；未来明确无代码响应与基础设施异常的不同处理。

源b7f8ab0f65dba9877ac3af35e3e770fc32546565；部署5bb9e2a05fc18c659d2835694c06290c75d6e7ca。
prepared0d924c4b9bde28a8a90367db23f1b6c098e8555d130798f01fd05316ce358581；readout-plan89724a497de7febe646488fb186e4ffe6f1930e92b971cba8c8411769fabb4ba。
summaryaa9c4610c0c6bc91011fca4e0edc8a6f6a8f7459351978bc73298d1a70258609；独立84e607b0199823f46debfbf8a0e1cbdb4e20b172556da7410fcb47949ed2eb47。
trace37beeaab13148d0a722d1afbcf71da66b6dd94f6093a5dc57175beeafc7d4e50；异常0e548a05b97e5481f2a6e34e4ecbd97c47ad5e474784ccf2e70c3783c05ac09c。
ledger2958calls/2旧未知，原累计10USD责任帽未提高、没有新增未结调用；不降低预留/清零/换key。本文件不记私余额。

## 新24原程序同池复跑已完成
ROOT=/research/d7/spc/yzyang4/forets-first-pool-replay-20260914-12xoscfq
13317 COMPLETED492秒，13318 COMPLETED730秒；0.33944444444444444 GPUh，0API/生成/debug/拟合。
旧12run全部最早非bootstrap双候选池×2原程序，干净workspace/原镜像3090/6CPU/300秒；不是K>=1或新E2E。
24正常返回/原生GPU回执：3有效21程序失败0基础设施未知。12池9双无效3混合0双有效；四策略均仅选中1有效程序，共同错过另2个。原已知12初始label重测无不一致。不能说四策略普遍等效或整个搜索没机会；零双有效池不能评估质量排序。
preparedfbb070b8fdad8f45b5dfeb32e346e0df70db0ec30be92ffc9c19ddcb19b991a2；部署fcaffc14aaf8c665e1ec95172971dbd06d4d5751。
主e1a07d80bf396d2f02c81f22f4dbd4e8b534a02f79ae2870fc29e0fa380aef28；独立4ff04b12c4f1622646b72728436600ab0fa67c6f89868e21530ecbf7a0b2db51。
所有main/independent为exclusive已完成，绝不再次运行。首CPU包p6czik62 from_dict失败保持废弃；实际12xoscfq原dataclass_from_dict已过24CPU路径。非G0重跑。

## 已验证旧正信号与限制，不再跑
13298/13299旧km65uuej全12技术合格、原数值/选择器独立通过。
Leaf46/47 U/H1.51485；S .35474/.36555。
Space46 U .79655/S .81839/H .80805；47 U .8046/S .8069/H .8023。
S对U/H均4配对胜为事后次要探索比较；共享预留wait不平衡：U158.686141/S98.829411/H107.524577秒。H主门失败，不称S稳定收益。
旧45pool追溯：S的4最终代码2来自candidate2来自debug，不可据此称短代码更易修复。传统小搜索Leaf median .05948（1200秒/不同空间）仍强。
旧主a2024478c6aa23feb7457d8d45738b51c622725b71eeba928af5e4d0a9dcac82；独立1bc25e391e6c2022cd174a5d16e3a682c6eef55bb4325ff8b841e0dd43750e6f。

固定code-only HGB model forets-task-validity-20260914-n8q3h72y/code_only.private.joblib，SHA05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1。
2482旧节点/138run/14task、28static code[:30000]features；有锚点run失败补齐但非无偏全语料，不再改模型。
四旧协议45完整对/11discordant：H10/S4/size6；按run对S4胜0负11平，不当11独立trial。
反证：3both-valid全Space H全偏低分；14任务LOTO H .48886771165193804 vs short .5558735851921456；不称通用迁移。28CPU诊断fit不部署。
旧EScope16门失败（4可比0胜4负4未知），T1/width/memory/旧8B失败保留；不复活G0/12892/8B/经典/Fresh验收。

## 当前文件与发布
主结果报告FORETS_SIX_HOUR_EVIDENCE_20260914.md，旧报告顶部已有后继链接；最新方向0L207。
近期汇报ADVISOR_PROGRESS_20260910_20260914.md已补学长最新更正；LOCAL_GENERATOR_UTILIZATION_UPDATE_20260914.md记录接入证据与新比较边界。
本轮更正/独立source包/9测试/接入回执一并发布；确切发布SHA以Git HEAD及results/local_generator_readiness_20260914/post-push-receipt.local.json为准，后者是推送后本地回执，不重复提交自引用commit。
新source原包只1.29MB，不含模型、真实凭据、raw私有链接；closed实验结果未改。唯一私有恢复链接的一次性cleanup脚本不stage。
results/forets_class_gate_s48_20260914/（6原manifest成员+trace/异常/汇总）；
results/forets_first_pool_replay_20260914/（4原manifest成员）。
导出tarSHA6cf86ea96092e5e8090d207ce2e96ad3ffe2fe5755dd6f600dfedba6eb777c4a及4f701916b625f70f39542d617fa52048ad753c77807fdaefd9a39215c8e01ca8，逐字节校验；tar本身不需git。
新汇总dbffe89448a594d06c299f6ec19ec11d57b4989183c25e759212abd301bc0766，新增10测试及原主读出/独立检查合计18测试通过，PS独立计数9/3/0/0及Space4/4选择/空code通过。首次unittest错cwd模块未找到，改cwd通过，非科学代码变动。
本轮结果已公开74427889240d7b9d2cc476ae2b69004c1803765e；push成功后ls-remote核对同一SHA，16份数据产物与staged blobs逐字节一致，credentialshape/sensitive文件名均0。之后的纯交接更新不改变结果commit；恢复先核git实际HEAD，不盲重跑/重发。
只push myfork HEAD:phase1-value-critic，不新branch/force/修改学长分支。无关untracked和原报告保留。

## 后续与硬边界
不扩大当前HGB/短代码/0.5门。新生成器单独来源/协议，不许称更强或将旧失败配方原样扩量；新协议将候选供给、真实选择改变、最终修复交付分开测，仍以跨seed同总预算E2E收益为终点。不能宣称一般门控/廉价失败预测新颖：CodeScaler、Automata、Verification Horizon已有直接相关；最后一篇只摘要边界。
学长branch本轮fetch为aae6f7d685b09cacdc5a3d1992dd81b9eeaa7ad8，仅新增4个H200 recipe/script，无新outcome；我方核验前public head83efa174373816520f899bec120dd920ba61a9ee。
Drive镜像已下载、hash/只读版本检查完成，见上；HF cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4 revision dc430725f831dd90d9271738b877879a46a82239，public/ungated；未下权重。
LOCAL_VLLM_SERVER原SHA d65edfaaa0df1875458d422f13ea9f1e5b9a96a4f4f39ca626d651249442a2fa，3credentialshape先远端脱敏；E2E_EVALUATION SHA84954ccce9b872e78f328068869c6a10de59f069b3d85d89dea79289ad3c5463/0shape。
11:11 UTC最后观察gpu28 idle/gpu27 mix，均9张3090；不是预约/免排队保证。12:10最后squeue我方仅12535旧held，未提交新作业。用户quota总余量未知，清理后实际40GiB申请成功且释放；覆盖先前39GB申请失败，不用文件系统free代填。
0912四config已隔离不是4合格run；不重下/不摄取保护cohort。
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
MLE仅gpu27/gpu28原镜像；禁projgpu39/Torch升级/CPUfallback。12535 held不动。
远端aira-dojo/.env OPENROUTER_API_KEY，source ~/env_setup.sh取proxy；绝不回显/本地/git/重索key。复杂脚本scp完成后再执行。SQLite closing防NFS。
保护first960/Target300/522封；HCE/多保真/Probe/score-channel/K>=1/agent底座更新禁。研究盘1TB到2026-09-29，续期未知。
