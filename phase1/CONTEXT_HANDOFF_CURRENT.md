# 短交接：e2e未确认收益，8程序生成器单变量诊断准备

2026-09-12最后更新04:47 UTC。用户本轮02:44起要求三小时有价值证据，目标05:44 UTC；留在会话，不新建automation。
先fetch→CURRENT_DIRECTION顶部→本文件→现场，不把旧状态当实时。主线同预算MLE-bench最终收益。

## 生成器对照当前正在生成，尚未提交GPU

- 当前root **/research/d7/spc/yzyang4/forets-generation-capacity-20260912-asl_0ytg**。
  stage forets-generation-stage-20260912-fyGr0bRP；controller **f3b2c68551b9eea728b67781e630cb5bb0426810**。
  preparedSHA **ab7bfcd9d1c93b14fbb6f65c04995d9ec3faca42299aba1120f2f9dd4e2fad06**。
  04:46启动generate，当前exec session21780，待8/8闭合才能submit；无重试/改代码/补槽。
- 矩阵两任务×replicate16/17×Flash/Plus=8全新程序；同JSON/描述/环境/采样/原镜像/gpu28单3090/6CPU/300秒配置。
  实际路径/workspace/data；prepare已调用真实容器命令构造器核对，2条件只改model。7本地生成/账本测试+4读出测试。
  75分钟1.25GPUh、额外API责任≤3USD，原100人民币/保守10USD累计不变；候选支持诊断，不是critic/e2e或等费用优势。
- 全生成完成后运行当前root里的forets_generation_capacity_20260912.py submit --root本根 --commit上述f3b完整SHA；
  程序源码tree900fa3bdf6971381c37a9792723dba42c63e5ac6。不得重复prepare/generate/submit。
  全8执行闭合且sacct COMPLETED后，用stage的readout_forets_generation_capacity_20260912.py --root本根，单次排他输出。
- **旧尝试不能恢复**：tps3pbrw在catalog门0调用停止；ngtb47lk生成8次后提交13141，但我方prompt错写/input，
  与真实挂载/workspace/data不符，04:38整组CANCELLED/46秒，3结果文件均未读值；8程序不重跑，费用.021790639USD照计。
  vkgl8inm迁移账本scope重名，0新调用；两个旧副本均stopped。修复使用root唯一scope和failed根排他recovery-claim防多活克隆。
  失败事实见FORETS_GENERATION_CAPACITY_PLAN_20260912.md，不把这几项当模型失败。
- 04:38后唯一旧队列是held12535，暂未再核；提交新GPU后覆盖此段。报告草稿FORETS_PROGRESS_FOR_ADVISOR_20260912.md待新结果补齐。

## 已完成，禁止重复读出/作业

- 13124 seed14 + 13128 seed15：3双方有效对均random更好。Leaf收益−0.91916/−0.12765；Space seed15−0.00920。
  critic4/4 final有效、random3/4，小样本不称稳定有效率优势；缺失不补0；两臂独立生成，不能全归因选择。
  原submission独立数值复核已完成。FORETS_CONTEXT_TWO_SEED_RESULTS_20260912.md。
- 更正：40解释器调用9正常、23代码错误、4真实执行超时、4启动就绪失败。最后4次未派发候选，
  却附加“执行超过5分钟”（seed14一次/seed15三次）。原成绩保留，撤回技术完全干净/纯critic能力解释。
  证据results/forets_context_s15_20260912/readiness-stage-correction.json；独立审计已完成，不补旧槽。
- 13129 COMPLETED，792秒/.22GPUh；root forets-current-pool-20260912-0hz06xtj。
  两个seed14完整首池8/8原程序全部无有效提交（6代码错误、2超时），无启动故障。
  全部结构/身份核验通过，数值复验实际0项（没有submission），不可称8项数值通过。
  summary SHA4e5abe5626e2e42971138f3edbae73a085c22a2c7cb559fd22642f9e0af3ef15；
  proof SHAd0068555ad80c08ee4fb298791c41da6ce310c49745ea9ceab01626790ffea28。
- 信息包消融root forets-information-ablation-20260912-rwohlohw，8调用全部闭合并已readout。
  Leaf full/omitted聚合top2均[0,1]，Space full[1,3]/omitted[1,0]；全无有效代码，不能证明信息收益/无用。
  summary SHAb746890fb734c19e935e6cbc9e111903aae00d459d41bbc70cee70e355e55ad3；新增.035282USD。
- 13133 COMPLETED17秒；root forets-readiness-live-20260912-6oyOub2Q；old/new各6实际内核均正常就绪/marker。
  旧版本次没失败，仅确认新修复可接通，不证明故障率下降；无任务/模型/API，不是G0。
  result SHA8d81ceac210032c2c00181e198f2050bf159d86e36378732e0b4feeb86fea70f。
  13132此前缺SUPERIMAGE_DIR，2秒失败/0内核；保留，不当内核故障。

## 修复源码已实际导入验证，未启用新paid e2e

- source **900fa3bdf6971381c37a9792723dba42c63e5ac6**，父54e353963a6899965896b2e8ea492207829b3cbd。
  仅3文件：有界120秒握手重发、就绪失败抛KernelReadinessError、新helper；不改执行300秒轮询超调。
  root /research/d7/spc/yzyang4/forets-readiness-source-20260912-BQletMGi。
  archive SHA221f20372c0b52472172238b4674bb012799d1781dfbb1f05102cbc858a00a71，239源文件核对。
- 04:23实际venv导入executor/witness，假内核验证就绪失败0候选派发、raised且无质量metadata，
  普通代码错误仍原样返回。控制流测试不是故障率/e2e正结果。archive/artifact/receipt已本地下载。
- 新生成器诊断两条件用同修复源；旧效果根不动、旧paid授权不改、不重新加载8B/G0。

## API账（新generate正在执行）

当前有效账应在asl_0ytg（查看其authorization.json和paid.sqlite只读统计核实），不得继续使用信息消融/旧生成器根。
最新继承370行、settled1.235371007USD/accounted2.635371007USD、旧两个.70未知；
新费用以generation-finished.json为准。上限继承责任+3USD，原100人民币/保守10USD不重置。
父ngtb47lk及失败迁移副本vkgl8inm均stopped；恢复只能单一后继，失败副本应有recovery-claim绑定asl_0ytg。

## 学长新提交已安全阅读

- 04:20 fetch：dojo-reproduce **9c46cca1dccd7633b556374d33c6c76390d1d061**（04:15UTC）。
  0911/RL_DATA_AND_FORETS_E2E_EXPERIMENTS.md和E2E_EVALUATION.md远端先扫描后读，credential-shape0。
  新报告SHA5e28c9e94644f7558f50e7f5ddaef5818718357cad5fe1fee43063e38c6901ff。
- 0905 BT scaling两seed不一致，14B RL未超过8B BT；3组e2e仍探索，无稳定正收益。
  任务事后选/seed硬件观察时间不同，AI4Code还在运行。这是学长报告，不是我方复验。
  没有声明新可用checkpoint，文档仍0827 8B；新报告不等于新语料runs，未修改学长分支。

## 边界与操作

- 不恢复HCE/多保真/Probe/score-channel/K≥1 lookahead/CPU期限筛查/**旧静态失败precheck**；不更新agent底座。
- first-960/Target-300/Target-522封闭；0910六包已隔离，不重复下载raw journals。
- SSH linux5；BASE /research/d7/spc/yzyang4；venvs/aira运行；proxy source /uac/y24/yzyang4/env_setup.sh仅远端。
  PowerShell→bash stdin有CRLF坑；复杂远端命令走Python stdin/subprocess。SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  gpu28登记RealMemory=1MB，不额外指定mem=8G；真实物理内存并非1MB。原镜像，不退CPU、不投projgpu39。
- key仅远端aira-dojo/.env OPENROUTER_API_KEY，绝不回显/本地/Git/再索要。仅push myfork HEAD:phase1-value-critic且先扫secret。
- held12535不碰，g0-r5 PAUSED，无新automation；研究盘1TB/2026-09-29到期，续期未知。
- 保留无关untracked；本轮未发布的3结果目录/source capsule须扫描后push；禁止重复排他写校验器。
