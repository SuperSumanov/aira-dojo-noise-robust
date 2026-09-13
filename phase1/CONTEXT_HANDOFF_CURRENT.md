# 短交接：错误经验新八条已提交；交付修正2胜6平，宽度二1胜3负

最后观察2026-09-13 07:45 UTC。当前用户要求05:53–08:53 UTC连续会话推进；不要现在结束，不用automation/新任务代替。
恢复先fetch→CURRENT_DIRECTION最新节→本文件→现场。保护first960/Target300/Target522仍封；不更新agent底座，不重复G0。

## 当前唯一活动实验：冻结旧错误经验 vs 无记忆

ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-103zf3nb
STAGE /research/d7/spc/yzyang4/forets-memory-stage-20260913-jiwvOhj8
07:43:14单次提交13242/13243；07:45已确认两者gpu28运行、各自首条Leaf轨迹运行，实际GPU通道handshake为true。不重复提交。
source 746d97a67922896b7d1581c4689f8b5f85204d30；controller 4a692f866f1d02fd2476bb6147b33d28346c900b。
prepared b676bfa46afae3c6e83b1d98855e77a368994fe7fdc22263f6693d581a4a57fd；AUTH 0b4e20837991c8ec3f9cb16116170c62b1e0897e732c9b1e62ffb1eaa8db5b4c。
readout-plan b08c242aef408b2a8f286d63f5269c705c85a1877d278edb9f394867721178d7；冻结v2 readers不得改。
Leaf/Space×seed40/41×no_memory/execution_memory共8独立搜索，均uniform生成二执行二。
仅draft/improve/debug追加三条旧错误观测；analyze/原选择/原UCT/debug/RF起点/镜像/硬件/生成器不改。
Qwen3-Coder-Flash / Alibaba；600秒搜索/300秒程序/64步；2×单3090/6CPU/90分钟分配，上限3GPUh。
计划06:38冻结，早于34–37读出及38/39开跑；宽度二与提示未按新结果挑选，不能因宽度结果不利临时改四。
24次实际operator→GenericLLM提示配对、实际2生成/2执行、原action/log/debug、typed8、超时/档案检查通过；不是新GPU/模型验收。
新账已激活，旧2z2s7sc3永久封账；继承1622调用/责任6034084481nUSD/已结算4634084481nUSD/两个旧未决。
原100人民币/保守10USD累计帽；新最大责任3.965915519USD。两个route通过；build/freeze/activate/route/submit都只做过一次。
控制STAGE/forets_memory_control_20260913.sh；monitor_memory_control_20260913.py ROOT。
全八及两allocation终态后，一次readout_forets_memory_control_20260913.py ROOT；不要运行core旧默认seeds/blocks CLI。
随后audit_closed_reservation_waits_20260913.py与audit_closed_uniform_work_20260913.py ROOT，只作辅助、不变资格。
下载明确命名的readout-finished、wallclock-summary/runs、memory-summary/runs及辅助JSON；scp全部完成后再本地verify_delivery_width_exports_20260913.py memory RESULTS。
预计45–60分钟，不能保证排队/清理时间；不得削减原budget赶08:53。先事实、后结论；不补跑坏seed。

## 刚完成：宽度对照，不再读出/激活/提交

ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-2z2s7sc3
STAGE /research/d7/spc/yzyang4/forets-width-stage-20260913-ODIHCjEU
13239/13240全终态，07:36–07:38正式读出与本地独立数值/CSV/hash/算术通过；8技术合格，两个终点全有效且本轮各条一致。
二生成相对四生成1胜0平3负：Leaf38 1.51485→.40938，Leaf39 .31730→.58447；Space38 .81379→.79655，Space39 .79655→.78506。
各臂均执行二、主action次iteration。运行API合计四生成.157249092USD、二生成.129106575USD；更便宜但非质量保持收益。
全部1.3030555555555556GPUh，含清理。没有新的API未决；八条无已记录完成预留等待/拒绝，不证明取消中的等待不存在。
source cda5e378046811fa20eadc7bc9a0d2343e69ddca；controller f3b601ace676aa8bec8f29578d8eac72ef331970。
summary9ceacd308c7928b243094f09ae028f34e2e0df1e5fc32b21ba04f5a26febfff8；closure277ad5aaa0eac4fd15bb56ecad3c828725448926d0e1fbaabb75b9e11b4ebd85。
memory-parent-facts74810d12e68931955044ea06ea6d0fe99d3ce311cadcd8e32124c01b19e3349e已继承；旧账封闭不可复活。
FORETS_WIDTH_RESULTS_20260913.md及results/forets_width_control_20260913已本地完成，待随本次进展推送。

## 本轮已完成：逐动作交付修正，禁止重跑

ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21，13233/13234全终态；旧账已封。
8技术合格/双终点有效：Leaf35/37提高，总2胜6平0负；不是critic/scaling/跨任务稳定效果。
同一实际轨迹两个交付终点，不是16独立run；原迭代终点是我方bounded包装规则，不是所有原生AIRA默认。
首先是纠正我方交付基线，不包装成超越原生AIRA算法。记录开销计预算；时间记录只是开销下界。
FORETS_ACTION_DELIVERY_RESULTS_20260913.md及results/forets_action_prospective_20260913已推；readout/overhead/timeline/capture事实全已完成。
closure34eafb5d6a6e2b347f86b380697f0d4eb5ff52fc45ce441cd5361e4e60c33011；summary182e8a424cc99e7cdd0ec9a46a219ba84f05a1c578ca6d2dc8ff9685fbb80d65。

## 经验依据与新颖性边界

冻结输入旧32闭合开发run，157保存执行节点105非零退出；类别错误31份不同代码/11条Space轨迹。不是保护cohort。
taxonomy fbea5f58486ea518255e6227f5d26014a5e5b0d138c78ce335b66086e3c1ef2b；recurrence f6b3b807c6c859e9c3fec6aff69a55467181f8131bb9dabd568c22b2e3bec97f。
memory text222da8b9d643c2023bc17683eed9b3a112260cbf443598b7275c753f7626a25c，含错误观测无代码答案/新结果。
旧debug父子链59边47非零/12有效；20类别错误父节点debug边中6次同族复发，5条轨迹、6份代码都变。只描述现象，不是经验有效证明。
ACL Findings2026 Demystify the Role of Memory in Machine Learning Engineering Agents是直接先例；另有HASTE/CEB/ReASearch/MLEvolve。
错误记忆、可靠性—多样性取舍、按阶段记忆都非原创；40/41定位经验强基线，不是顶会方法确认。FORETS_METHOD_HYPOTHESIS_20260913.md。

## 学长资料最后核验

Drive0911一包16011265bytes在/research/d7/spc/yzyang4/senior-quarantine-0911-20260913隔离，4个credential-screened配置git065b0f...、width2。
未开journal/env/outcomes或入训练，四配置≠四验证physical runs。manifest c1ee6108efc3bdb08cb5ffd676df141573629cd81011f8cbe68ab56cbd0411e1。
07:27 fetch senior head仍be9335348b569086ef9b0af36a15b13e61fec45c：timeout1500→14400及LOCAL_VLLM_SERVER文档，非新训练outcome。
文档先远端脱敏才读；qwen3.8-27b节点localhost:8000/v1，镜像/权重共享路径我方Permission denied，未绕过/借用学长allocation/发请求。
默认长thinking不适配600秒，文档ctx不一致；当前实验不换模型/超时。FORETS_LOCAL_GENERATOR_READINESS_20260913.md。

## 运维和禁止回退

SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；Drive用venvs/exp/bin/python。
SLURM_CONF=/opt1/slurm/gpu-slurm.conf；MLE只用兼容gpu27/gpu28 RTX3090，非projgpu28/39；镜像不升级、不退CPU。
旧held12535不动；最多4jobs/8GPUs。PRIMARY_KEY远端映射OPENROUTER_API_KEY，绝不存/回显key。
此前critic32/33零胜一平三负；13227补齐、13232CV单例诊断皆完成，不再跑、不倒改负结果。不恢复HCE/多保真/Probe/score-channel/K≥1。
只push myfork HEAD:phase1-value-critic；最后核验公开4a692f866f1d02fd2476bb6147b33d28346c900b，不动学长branch/强推/新建branch。
复杂SSH用脚本/scp；远端无rg；本地rg用-g而非literal通配路径。激活输出删v.billing.scopes再显示。
研究盘到期2026-09-29延期未知；未清理，无关untracked旧release/tmp/output保留。memory工具用-v2，旧v1从未部署。
