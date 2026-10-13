# 当前短交接：恢复先读本文件，不从旧心跳恢复任务

最后核验：2026-10-13香港晚；新独立24条长推理对照已获用户明确批准，当前准备/CPU预检，尚未提交GPU。
恢复顺序：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件 → 必要原始证据。
本次覆盖前的完整交接：Git 72167a42feccaec44f5793c3bc7d2f4e9132d581:phase1/CONTEXT_HANDOFF_CURRENT.md。

## 本轮独立xhigh批次（10/13晚，覆盖早间只读授权状态）
- 用户批准24条=2旧开发任务×4配对seed×fast/medium/xhigh；run1800秒、pool1960秒、2服务+4执行卡，allocation7500秒/12.5GPUh含失败，API/底座训练0。每臂一池，固定medium→xhigh→fast，不声称重复确认，不改旧17740。
- 共同代码输出32768、请求1500秒；Analyze仍medium/8192/600。相同warm父程序/greedy/镜像/数据/任务预算，候选自身执行300秒不延长。新目录/research/d7/spc/yzyang4/scheduling-long-effort-20261013-v1；临时源码/tmp/long-effort-20261013-4iRdot。不存在launch回执时不得说已跑。
- Git fetch无新提交，myfork/dojo-reproduce仍ff0e8d51；SSH先两次认证前关闭，用户修复后已正常。仅见旧Held12535，禁止操作。新六项本地CPU单测通过；真实冻结后端/24配置预检仍待核验。
- 新源码long_effort_{trial,policy,readout,native_cpu}_20261013.py与test_long_effort_20261013.py。改超时是新批共同改动，不改旧snapshot。finish_reason只记安全枚举；未完成不填造warm分数，完整质量门需胜两常数参照，不用生成数代替终分。

## 本轮用户要求与学长建议
- 用户转述学长建议补xhigh（可至几万长度）；学长当前重点是逐日用上一日轨迹/score训练新policy再采集，未来想用validation/D_search对抗去除score依赖。原话与边界已存ADVISOR_DIRECTIVES Y。
- 学长计划不记为已跑通/满分；我方不更新agent底座的禁令不因此解除。继续R14相关的推理成本/真实质量研究支持，不恢复旧critic/HCE/多保真/score-channel。
- 当前建议：旧/新日期固定checkpoint×fast/medium/xhigh，同最新archive、起点、可见历史、硬件及整池预算；版本效应和effort效应分别在另一轴固定时识别。先验证权重更新是否超出历史积累，能否降低推理成本；这是设计，不是新算法/新收益。
- 不用逐日累计最高分当学习证明：未训练旧模型也应获得同样最佳程序/历史。学长训练默认去掉proposal搜索记忆是明确设计，不先验判错；更需与上下文复用的廉价参照比较。
- 新旧checkpoint事前按日期选，不能用本轮结果挑最好点。训练/采集成本单列，部署收益与摊销后总成本收益分开；保护集未解除，当前仅开发证据，不能称独立test泛化。
- 最终E2E目标仍是同一初始archive下，“训练+搜索”胜“把同等新增总算力用于不训练的强搜索”。六格只是既有checkpoint的部署/机制读出；单程序发现与通用policy收益不能混同，不强加跨任务policy泛化为发现的必要条件。TTT-Discover v2直接覆盖单任务自举宽概念，不能称首次。
- 思路交付的优先顺序：冻结模型补fast/medium/xhigh强参照→日期固定旧/新checkpoint同历史比较→有收益才核整循环回本。同预算终分主读出，事前固定质量门槛的整池成本为辅；未达到按删失记录。只复现已有最佳程序不记新发现；新低effort胜旧xhigh不能单独证明压缩推理机制。
- validation/D_search若参与训练/搜索就不是最终封存集；“不用官方分数训练”和“部署不接收外部分数”不是一个问题。这里只澄清后续设想，不启动score-channel消融或analyzer。

## Git/材料最后观察
- 本轮fetch成功：本地/公开72167a42feccaec44f5793c3bc7d2f4e9132d581；学长myfork/dojo-reproduce=ff0e8d5148a25ecdaffdc40db990465b4bf24525（10/12 HK22:26，use metric as reward），另有69dffe5e客户端配置；未修改学长分支。
- 四个新增/修改文件credential-shape scan为0后读取；新增use_metric_reward默认false，不证明生产启用。policy outcome最后修改仍13d28830c66a96988c180532495326dc144eb93b（10/9 HK20:15）；没有确认新训练效果。
- overview明确metric=内部验证、metric_info.score=官方评分；reward=1是gold阈值，不等于任务满分。实际日更训练所用字段未确认；同组标准化可抵消正仿射变换，不能仅凭阈值复用认定训练bug。
- selection.training_messages源码默认对draft/improve/crossover strip memory，debug/analysis不改；overview末尾仍有旧相反描述，以固定源码为准，不能据文档猜实际训练产物。
- 本轮仅改ADVISOR_DIRECTIVES、CURRENT_DIRECTION、ROUTE_DECISIONS和本交接；暂未commit/push。用户未跟踪报告仍不动。

## 实际effort语义：已查到什么，没查到什么
- 旧root=/research/d7/spc/yzyang4/scheduling-feedback-effort-20261012-v2。只读tokenizer模板及配置，合成固定提示的default=xhigh、medium≠xhigh；不是实际模型输出验证。
- 镜像内vLLM0.29.0的protocol接受xhigh且转发至chat_template_kwargs；protocol SHA8a1f1138f79557aa5b5add12e81b9745fd5e286fa35f0502a97f2a377d41665b。
- 旧四角色max_tokens8192、请求600秒、run1020秒，服务context131072、TP2/max_num_seqs6。上下文上限不能替代输出上限/时间预算；旧bounded适配器还硬拒绝timeout>600。新独立长推理设计必须说明共同调整，不静默改旧批。
- 模板SHA c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041；tokenizer_config SHA b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27；service_entry SHA ec18d6804087e17354934d9dfe24f129d8378211b043c04bc9e519e6951ecfef。
- 冻结backend实际为async，SHA458683d335cbe5f558ef06288a40d670af4fd2ef9a64b448ca577d7d78138cb8；GenericLLM SHAde768c80238b0cf13b6359a64223f913ff30d133b9f23711d2ff643adc2949e8。工作树同名旧sync文件不能替代它。
- CPU脚本在本地_codex_tmp/effort_semantics_20261013.py、vllm_effort_source_20261013.py、effort_transport_20261013.py，前述静态检查已完成；无模型/HTTP/GPU。
- effort_wire_cpu_20261013.py已在SCP完整结束后通过：固定backend→LiteLLM1.65.7→实际序列化→假HTTP响应，medium/none/xhigh三例均保留正确reasoning_effort/enable_thinking、max_tokens8192；socket尝试0、真实HTTP/模型调用0。这是当前离线传输复验，不是历史抓包或xhigh质量/长度验收。先前SSH超时/banner中断均发生在测试前，未重启实验。

## 本轮文献与判断边界
- AREX-2同Qwen3.8-27B长轨迹训练及MLE相同skills/rounds参照已读；无正确性反馈实验是BrowseComp，不当MLE去score已解决。Guidance-TTT已训练小指导器配冻结执行器，不把这个拆分称新。
- RHI已有harness优化与高effort比较（合成研究任务/LLM judge，不是真执行MLE）；Ares/CoT-retry/LASER/InfraMind限制简单动态档位主张。When Agents Slow Down仅核摘要，不能声称已排除全文近邻。
- 优先问同预算最终质量—成本关系是否真改善，不开发新的复杂router救17740。暂无新方法阳性，引用和较细边界见ROUTE_DECISIONS。

## 最近真实实验17740：已闭合，不重跑
- 10/12 HK18:26:18 COMPLETED，48/48、6等预算池；2旧开发任务×4搜索seed×3臂×2反序重复。medium/fast/feedback_think，共享greedy，Analyze固定medium；1020秒/run、1180秒/池、2服务+4执行。
- 原quality=false、structure/mechanism=true。去噪两重复medium/fast/混合分别0.019929967149881492/0.014879316923648044/0.01841157291063107及0.016919910295110023/0.016424072925913014/0.014526227565536542。
- 混合比medium相对误差低7.618648981362969%/14.147136053465204%，但对fast一负一正；Aerial近天花板只作不退控制。混合去噪胜起点3/8，fast5/8，medium3/8；池内相关，只有2池重复，不能称普遍可靠性/新方法确认。
- 46评分重算、24CPU配对、固定物理GPU/清理、独立Node逐格CSV与统计核验通过；原门不变。成功code调用触8192计medium7/34、fast0/51、混合2/41，未记录finish_reason，不证明截断因果。
- source1cd338f86dac1381795c0295abcefefc8391df8d；planSHA4b33b157e65ba4b14668dfb9e3309ba2e9173ba62c0d542614ef9bad7befd0fc；summarySHAecf3dc4123e657c3f4221e7b061c7a0a7550be27f4febc21034367c7282e3b8a；结果sandbox_scheduling/feedback_effort_v2_closed。
- 实际44166GPU秒；含17736入口失败1968秒，共46134秒=12.815GPUh≤13。17736零模型调用/零评分，旧48分母保留。最后观察本批GPU/monitor/readout/SCP全部闭合；本日未提交新作业，未重新查询全队列。
- ABCCBA共享prefix-cache/两复用任务/条件暖起点限制保留。停止本角色混合配方自动扩大，不补seed、延上限或换任务救旧门。xhigh若做是独立新研究，不翻转旧门。

## 历史关闭与操作
- 17681硬预约质量门false且不完整；17675资源项改变选择0次、质量门false；17670请求时限复验质量门false。不改阈值/重命名重开；细节在前述Git交接和各closed目录。
- 2服务+4执行已真实跑通，不重复G0。跨节点交管理员；历史OpenBLAS EAGAIN根因未确认。旧Held12535不动，失败原件不删。
- first-960/Target-300/Target-522、D_val/官方test、16560数值导出继续关闭。不训练或RL更新agent底座，不恢复旧critic/HCE/多保真/Probe/score-channel/K≥1。
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；detached HEAD有意。发布仅myfork/phase1-value-critic，需显式stage/安全guard/快进与ls-remote核；本轮未发布。
- 用户未跟踪phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md与旧checkout dirty不动。凭据只远端，学长新材料先scan；不导出候选/预测/标签/权重。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。已知IP137.189.88.148可配HostKeyAlias=linux5.cse.cuhk.edu.hk和StrictHostKeyChecking=yes，不跳过hostkey。
- 本轮gpu3 RTX3090已有资格；优先gpu27/gpu28。现有MLE镜像不投projgpu39、不升级Torch/退CPU；排除projgpu7/8/33、gpu36/38；gpu24 cuInit999未解。
- 研究盘4TB至2027-08-30，不是实时剩余空间。Windows Python不可用；SCP必须等exit0再核SHA，不拿复制中缺文件当最终失败。长贵批次先矩阵/全成本/停止门，不复用旧失败预算。
