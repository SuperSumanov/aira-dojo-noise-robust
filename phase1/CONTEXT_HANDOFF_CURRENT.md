# 当前短交接
## 最新：2026-10-09香港六小时窗口（覆盖下方10/8动态状态）
- 本窗口约06:12–12:12，用户要求在会话内继续，既有自主批准适用；不另建自动化、不提前完成。
- 当前仍R14。fetch己方9c52040372909aa2173705903def1a4102f6bb3f；学长0155c7dedded47b59e29e81089e814250e38bd70（implement the grpo pipeline），仅核元数据，不读取新samples或采用GRPO。
- 新live矩阵：2任务Pizza/Spooky dev、每池4独立run、FIFO执行许可1/2；ABBA四池块=16条×600s；base9B/2GPU12CPU服务每块重启，1GPU6CPU执行池，无rolling，不改变run内顺序。
- 新自限3张3090/90min/≤4.5GPUh，所有服务/失败/闲置计入；无API/底座训练/官方test。完整16分母，调度干预只有2配对块，不当16独立系统复制。
- 共同适配器：preview/异常kernel关闭后释放许可；有界info握手；排队计入600s但从exec_time反馈扣除。两臂源/输入/镜像/模型/采样/预算相同。
- 事前探索门：16端点/清理/审计齐，两配对池都增加有效dev返回，分任务配对选中dev分数中位差非负且无新增基础设施失败；不换seed救结论，缺失不补分。
- 文件sandbox_scheduling/live_search_trial_20261009.py、live_admission.py、live_runtime_hooks.py、test_live_*。根拟/research/d7/spc/yzyang4/scheduling-live-search-20261009-v1；06:40前未prepare/提交GPU。
- tmp=/tmp/r14-live-20261009.M0hvVk。donor=policy9b-paired-20261005-gpu27-v1，plan SHA12d1264457158c936e4f1eff8e9c844ce5044365e77056066c4ded2ecfe6cd79，source b8e75052a9f69e19436f12bc5a36a0ca26a69a57。
- 06:34香港：本地15项通过/3Linux项跳过；远端Linux3项全部通过（锁/超时取消/真实模块mock），无GPU/model calls。原接口mock首轮缺SUPERIMAGE_DIR，补测试环境后通过；不是实际任务执行通过。
- 只读前检通过：donor闭合、模型/镜像在、dev评分器SHA匹配、private目录不存在；同任务各run工作/提交路径独立，不读donor结果值。冻结数值读出与全16分母门已写好。
- SSH曾超时/中断/DNS失败，06:34前恢复；只读失败不是候选失败。剩余prepare核配置/派生源码/镜像hash，固定commit/preflight后才能submit。
- 最后队列仅12535；gpu27一张空卡，gpu28满，新3卡可能排队，需现场重新核实。下方旧writer一律不重跑，旧预算不用。

## 10/8已闭合历史（不作为当前授权/现场）
更新：2026-10-08香港晚间；一小时窗口实际始于22:37，GPU已闭合，23:25前完成独立结果复核；动态现场须重新核实。
较长历史完整保留于Git 3bd58e7e9d0b0c4a91519bdb3e65145415aefb0c及1ca06f255199785d84ef7ecf56129060d2b8d82f；原实验不改。

## 恢复与授权
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本文件；旧aira-dojo-codex-20260813有用户dirty，不覆盖。
- 唯一活跃R14 MLE沙箱资源调度。真实有限系统阳性，但没有重要独特、强基线跨任务同预算的新方法确认。R1–R13及旧HCE/多保真/Probe/TD/score-channel/K≥1不重开。
- 07:51–13:51香港旧窗口已闭合；旧一次性提醒已暂停。用户22:37新要求沿阳性探索一小时，既有自主批准适用：新资格1卡/10分钟/3次独立kernel；通过才新pipeline/share2两程序×3重启=12次、1卡/30分钟，总上限2400GPU秒。不复用旧余款、不覆盖17014/17021；两臂共用有界info握手，不重发候选，不改源码/输入/镜像/训练量。仍属基础设施重试，不是新工作负载或训练seed确认。
- 资格17124已COMPLETED/84GPU秒，3/3通过；source3f2f98469159bacd01f1193a3b78f38d1e604f51，plan18331b8dcdc5c8df5c6cf8a85b7000218d0bcb23e57834fe49f45bb9c6fba53c，closed SHA6ac6f3cf44dddb24fcf764d9876ab695bebffbbc71cf273884b338a6e053c4bd。根scheduling-readiness-live-20261008-evening-v1。资格不是速度或长期可靠性证明。
- 22:54正式prepare提前configure触发FileNotFoundError，零正式GPU提交；22566d06fc8de23d6c16cc2bd4a85b0858af0d66修正set_scope/prepare顺序并补测试，本地41/远端6入口通过，不重做资格。25本地+12远端较早测试和后续44组合测试有重叠，不累加成科学样本；首次本地临时目录权限错误保留。
- 23:20香港最后核：17128 COMPLETED/1120GPU秒，12/12且0失败。根/research/d7/spc/yzyang4/scheduling-neural-qualified-overlap-20261008-evening-v1，source22566d06fc8de23d6c16cc2bd4a85b0858af0d66，plan c73cb9ce97ae092ee3bb4ea761201da22dc08d35dfa3f5ecf3aa34bdd8415abc。新窗口84+1120=1204GPU秒=0.33444444444444443GPUh，自限2400秒，无新作业待投；不复用余款。
- 正式三配对1.2672909369785448/1.6617137953073626/1.6730949919847078，中位1.6617137953073626、sample std0.23107569245795057；150/640步各六次相同，固定查询数值差0。完整强参照过门，不是独立工作负载/训练seed、全任务质量或语义新方法。三次共置均快但Cactus单程序时长有波动，不将所有差异归因于GPU并行。
- 本地evening_overlap_v1_closed：summary SHA c763de7c8ee00db5d4ba4219d49c4d864e573061368be9566f7d48d4cc0bc258；audit41dd43c9e1082895dbe282e25a511e274a1c4ec593568f5efc153101563846a3；pipeline-contract e083914bafadb473cfa2ec154eed023d092b033c06ed60427fb8026d5bb12fdc；runs bbdc10e74a92382d558b92dc6ef24f9f833e477d4df6784efcd9554341519652；supplement4b9091d31668e305074a0ea830c38413c127add11370a0628b28e825958362e9。五hash下载后相符；本地PowerShell独立复算12分母/矩阵/中位/std通过。
- /tmp/r14-evening-20261008.TOHDvG/close.sh已一次执行成功，不重跑writer。256冻结文件/14242输入hash、12资源身份、pipeline前驱屏障均通过，60正式info握手ready；已记录preflight与六块0重叠，不能证明全主机无干扰。首次SCP连接关闭，单文件重试成功；无原始预测/标签导出。
- 资格只读导出已本地复核：evening_qualification_v1_closed/summary.json SHA39b2c381993ec6aa01b6a3b5070e783936c363b324daec42fe4aad6a93905022，runs.csv SHA f6c4bd2eaa75873122674003a4f3a16bd6831b669caa73ed0dd2734ee27f4ba0。冻结客户端execute AST的迟到消息/真实错误两项CPU注入通过，不是额外真实内核或超时根因确认。一次审计测试误在repo根目录运行，4项导入错误；正确目录20项通过，非GPU失败。
- first-960/Target-300/Target-522、D_val、官方test继续关闭；16560数值导出另待授权。不改学长分支，不动旧Held12535，不用付费API、不更新agent底座。
- 23:30香港发布后核验：己方phase1-value-critic=c270419f50da3255c40231ce199632d682b2e48e，含源码3f2f9846/22566d06与闭合证据；dojo-reproduce仍dfff0efb9daf1d4a63c74492f138c19c1fd8440e，未修改学长分支。24文件及3提交29个文件版本credential-shape/敏感文件名扫描0；五回执及两runtime在Git blob中的SHA与现场一致，精确字节属性已保留。本地44相关回归通过。发布前一次扫描命令引号错误被门拦住未push，修正重检后成功；不把Git附带sh.exe警告说成hook通过。
- 23:31香港队列只读复核17124/17128均已离队；一次带管道字符的显示格式被SSH拆分，改无引号/无管道格式后退出0、空队列。只读检查失败不是候选失败或新资源成本。此交接提交是已发布结果的状态回执，不另开新实验。
- SSH linux5/yzyang4；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。原MLE镜像仅gpu27/gpu28 RTX3090，不投projgpu39。研究盘4TB至2027-08-30，不是实时剩余容量。

## 17017：最新完整阳性，所有writer已闭合
- root=/research/d7/spc/yzyang4/scheduling-neural-full-confirmation-20261008-v1；tmp=/tmp/r14-neural-confirmation-20261008.eJVICI。
- source=5f44b1af605f4f7b6034d3556c4c1a2f62b7232b；plan SHA=b8bf8619c61a98db5af35bb2b68f4b9838354c9ccfef166d8dd788ca0b16df7f。
- 12/12，COMPLETED，2035GPU秒；serial/share2三配对1.6811874366439696/1.6923715665437906/1.6232967236130837，中位1.6811874366439696/std0.03707594310497998。
- Cactus150步、DnCNN3920步各六次一致，固定查询输出全同；同原seed42重启，非独立训练seed或全任务质量等价。DnCNN113公开配对中98内部train/15内部val，2noisy-only query；Cactus仍使用原源码子集逻辑。
- 输出/时间独立审计、CPU/GPU身份与输入hash通过；六块无已记录我方重准备重叠，不声称全主机隔离。原镜像/6CPU/450、525、550秒候选、解释器、worker限制未变。
- 本地sandbox_scheduling/full_confirmation_v1_closed：summary SHA8c985bc78b4056980436589486ffa50c0999a5b5efc91c6bae76d21e4db608a7。audit、runs、identity、measurement_context、feedback_latency均已保存；不要重跑原writer。
- 新service_time_comparison.json六配对独立PowerShell复算通过。DnCNN共置/单跑时长0.9978607824217048–1.0106516809488744；Cactus变化原因未分离。候选重叠分解已在原audit.json，本次复验不记新发现。观测共置峰值2639MiB，未验证迟发显存峰值/逼近容量风险。

## 17021：神经强参照不完整，不报确认收益
- root=/research/d7/spc/yzyang4/scheduling-neural-overlap-retry-20261008-v2；tmp=/tmp/r14-overlap-retry-20261008.jTdpZ1。
- source=f507a53f759b41fee5e3f39906ff6db50ec69796；plan SHA528026478eff9138b06ff53023d5793139ea3bd9246fc3082cc3d749c8c25dfc。
- FAILED/12尝试10完成/885GPU秒；slot6候选前就绪超时，slot7前驱失败屏障阻断，两者0候选开始。两个完整配对2.0118806105322156/1.3991776441257207，确认门false；不删失败、替换配对或补跑。
- 10可用输出每程序5份一致、150/640步一致；12身份、14242引用输入hash通过，成功槽串行屏障核验通过，六块0已记录我方重准备重叠。只是17014基础设施重试，非独立科学复制；17014预热0正式尝试/157GPU秒保留。
- 本地sandbox_scheduling/overlap_retry_v2_closed。summary SHA6cd031cd88f5312ba302b1f40751b284a2883c7f11ec9a90540634157fadc948；audit/runs/pipeline-contract远端四hash已逐一复核。远端runs.csv在根目录，audit在audit-v1/summary.json；猜错路径不等于原件缺失。writer均只执行过一次，不重跑。
- 16997四小程序36/36、pipeline/share2中位1.3177936445362894是另外的有效小负载证据，不能与17017拼成完整神经强参照。16999/17005部分计时有我方准备重叠，保留混杂；其他旧结果见CURRENT_DIRECTION和对应目录。

## 闭合成本与未部署修正
- 13:35香港重新sacct核本轮全终态：16987=37、16989=43、16992=100、16994=566、16996=1444、16997=488、16999=2053、17004=0、17005=1989、17014=157、17017=2035、17021=885单GPU秒；总9797=2.721388888888889GPUh，上限10800。余1003秒不复用；17004是已核未分配取消，不能泛化所有取消为0成本。
- readiness_evidence.json只读握手白名单/冻结源码：一次info查询、逐消息完整timeout；未提供传输轨迹，现场超时根因未知。bounded_readiness.py只为未来opt-in，不改src或闭合批次；仅重询info，不重启/重发候选，保持总deadline，要求独占接收队列。
- 13:38香港另修慢发送饿死接收窗口，测试先失败后通过。本地28相关测试、远端13握手测试通过；均mock/CPU，非真实Jupyter或GPU修复。阻塞send仍靠外层hard deadline；IOPub/close须真实资格核验。
- 远端/tmp/r14-readiness-cpu-20261008.SeumG5只含CPU测试与公开证据。首次未等上传完成，2项缺fixture；等待完成、3文件hash一致后13/13。工具返回session ID不是进程完成，依赖调用须先等待。
- helper SHA0fd8ead4c8eac2fc128b36d096ed15ceebeabc43a5fc5841d8c17e882ca381cd；test SHA3d49a2cbd3e7f1fe8019fde4f48f181560e7835ed8a0a0cfb7f943c7a3821a8c。无新GPU、候选执行或API。

## 接续判断
- 独立资格与两神经程序完整强参照已补齐，停止重复基础验收。再测相同生成容量、逻辑run队列/rolling规则的live净收益；不因简单并发阳性就造复杂LLM调度器。新批次先固定矩阵、全成本与资格门，不把本条当已提交。
- ForeTS按返回更新journal/step/价值且失败可debug；并发兄弟/按完成序消费会改变搜索。优先跨独立run共享、保留run内顺序；首返回不等于下一次普通生成/搜索质量。
- 固定外生run入口，不事后固定处理后的候选到达时刻；同时共享一个动态排队生成服务会造成两臂相互干扰。需要等容量隔离或随机化顺序独立时间块；全池含生成、等待、初始化与调度服务。
- SchedMate/TGS/Salus/Orion/Tally/Fluid及其他近邻详见README。透明共享、在线画像、逻辑策略与执行分离均已有，不把适用接口差异冒充优势。现有ready积压/生产收益未确认，旧16370的22.72%预留窗口不是节省。
- README另有说明性两run闭环解析反例，事件计算核对1000时间单位下串行1000/共享862次返回；纯假设、未拟合实测，不是新实验/排序翻转或正结果。它只说明固定批提速不保证live提速。
- 短入口已压缩、旧实验未改；本轮未新增长报告或自动化。交付明确正信号、未过门与全部成本，不承诺顶会概率；后续接续不重跑旧writer。
