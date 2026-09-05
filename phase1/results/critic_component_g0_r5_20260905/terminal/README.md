# G0 R5 12499：真实双卡训练、单次dev和最终权重保存已完成

2026-09-05，香港时间13:58:30—14:35:02。用户要求改为当前会话连续推进，本轮已暂停`g0-r5`定时守护，
没有新建任务或重复投递；跟到终态后完成以下只读验收。此处是工程校准，不是G-reuse/scaling效果结论。

## 1. 实际运行与产物

- Slurm主作业、batch、extern均`COMPLETED/0:0`；实际2192秒、两PRO6000、Requeue/Restarts均0。
- control=`90cd91058fd03e86185d42c14704845827259655`；source=`5f3bc362db922c8edee2ef134656dfdb9a2b74fb`。
- Qwen3-1.7B-Base原snapshot、seed6、16384ctx、microbatch8、accum8、effective pair batch128未变。
- 实际完成10个optimizer updates；仅step10进行一次551-pair历史开发集验证；有train_end、退出0与COMPLETE。
- `model.safetensors`为3441190802字节，SHA=`c66dea53f96795438f82a0950027fee996054bacb431216a50d3e184ef74daad`。
  独立从固定模型config构造meta-device模型，逐张量核312个名称、形状、BF16类型、区间连续性和文件长度；
  总参数1720577025。另以CPU分块读取全部保存张量，全部finite；未输出权重值或dev分数。
- `rm_meta.json`、`trainer_state.json`和`training_args.bin`文件哈希与作业验收回执逐项匹配。
  未反序列化`training_args.bin`。没有optimizer/RNG恢复产物，符合本次final-only配置；**不能声称resume通过**。
- 作业验收后再次核三输入与底座10文件SHA，均未漂移；源码/control提交与tracked状态未改变。

终态原始文件仅在远端`/research/d7/spc/yzyang4/critic-component-g0/runs/job-12499`。
原`verification.json`含历史dev值，不上传；公开的是下列结构投影及独立检查结果。

## 2. 实测成本和风险

|阶段|秒数|
|---|---:|
|launcher到train_begin|133.832880143|
|第一个optimizer update|150.490844516|
|后九个updates合计|1559.370525407|
|全部十步训练|1709.861369923|
|551对dev验证|169.536428516|
|dev结束到train_end，含保存|37.855029|
|Slurm完整资源占用|2192|

后九步均摊173.2633917118889秒/步；仅一个工程run、seed6、1280 pair visits，**不是跨seed速度估计**，
也不是基于新正式包valid tokens的完整训练预算。不能由它直接批准15-fit或另一个pilot。

本次1.2177777777777778 GPU·h；连同12181/12288/12377/12486失败和12497目录检查，
累计5349 GPU-seconds，即1.4858333333333333 GPU·h，原14400上限剩9051 GPU-seconds。
剩余额度不是新科学实验的授权，不自动花掉。

训练阶段采样峰值GPU0/1为87455/79145 MiB；dev阶段为97059/92107 MiB，单卡总量97887 MiB。
最高记录仅余828 MiB，且五秒采样可能漏掉瞬时峰值。后续生产配置应先验证更保守的dev microbatch，
全臂保持一致、记录可能的数值差异；本轮未改G0、未启动这个新验证，也不据此声称更大模型/长跑安全。

## 3. 访问范围审阅及其诚实边界

终态trace为130380728字节、1378483行，SHA=`49ab143f4b4c28531cc945c4202823256e85a06c8aa4a245f8aa0e4624a186ca`。
凭据形状和保护路径字面匹配均0；未解析syscall为0，pending unfinished为0。
成功打开的既存文件均能归入固定train/dev/cards、固定模型/源码/依赖、系统元数据、编译缓存或本次输出。
初次清点留下8种未分类操作，逐项复核为`/bin/sh`、3个O_EXCL新临时文件和4个CPUAdam编译产物创建。
四个相对路径创建缺少完整cwd继承记录；它们有O_CREAT与O_TRUNC，不是未知旧数据文件读取。

**不将上述审阅升级成完整OS隔离证书**：本次`strace %file`没有fork/clone、close/dup、继承FD、网络和
实际read内容记录；dirfd跟踪也不是完整生命周期证明。回执明确保留`scope_certificate=false`和
`all_output_cwd_resolved=false`。已完成的是这个固定、非对抗G0的观测范围审阅，不是未来正式数据的来源认证。
first-960/Target-300/Target-522没有被本轮分析读取；原历史工程输入不能改名成为合格的正式训练包。

## 4. 可复核文件

|文件|SHA-256|
|---|---|
|checkpoint_acceptance.json|d504f91d8716822554bd1b799b41585d735dd355f6162ea04a5974ea45a6a435|
|final_integrity.json|81e82959c6e17835db5ac55c706bf4307f220004cb522a7260b5a73699c6504f|
|timing_summary.json|c919d36630d180bd65313d8141728f889b25cc49ef53e246a23c631196596636|
|trace_review.json|5227b618ca550f49952b4047e5bf901782e11a71215d9595aa4445497d73644f|

`audit_scripts/`保留四份实际执行脚本，上传前与远端逐字节SHA比对一致。它们是一次性、明确绑定12499的
终态诊断，不是新的通用validator框架。最初只读调度查询用了本集群sacct不支持的Restarts字段；
改为scontrol核Restarts/Requeue，作业和科学配置未动，没有额外GPU开销。
meta模型构造仅出现torch_dtype弃用提示；没有GPU上下文或新model fit。
`run.csv`一行记录本次实际run；完整科学/执行配置由原source/control、固定preflight SHA和远端原始回执绑定。

## 5. 对主线的实际意义与下一步

现在可以明确划掉“G0尚未真实跑通”这一阻塞。尚不能划掉：

1. 正式来源包：本轮fetch学长仍`b8d095180415957aa1bab31fa53ead1bba261c03`；已知Drive根43项、37日期目录，
   最新0903，无0904/0905，单次metadata请求、0 payload下载。这不证明其它共享位置没有上传。
   所需生产端事实仍见`../../../SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md`，不能由我们猜。
2. 新token-plan consumer的production接入：此前CPU-DDP梯度/SGD检查不覆盖真实AdamW/ZeRO3/bf16、
   完整checkpoint/resume和合格数据caller；本次G0跑的是原Trainer，不能把它冒充新consumer已验证。
3. 正式效果预算：待合格来源包的实际token量及上述接入验证后，再固定完整GPU·h并取得批准。

继续full G-reuse→L主假设和既有五臂/跨seed成功门；不恢复关闭路线、不提前揭盲、不以工程测试数
提高“方法正结果”的计数。终态后不再为已完成G0安排守护。
