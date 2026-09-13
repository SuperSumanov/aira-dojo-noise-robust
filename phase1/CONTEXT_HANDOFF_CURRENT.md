# 当前短交接 — 2026-09-14 HK，EScope准备中
方向CURRENT_DIRECTION 0L200；用户要求会话内持续六小时实质研究。本轮2026-09-13 21:06:43 UTC开始，目标到09-14 03:06:43 UTC / HK11:06:43。不得靠新自动任务替代，不保证正数或隐藏失败。

## 新方案与状态
EScope：Leaf/Space×新seed42–45×whole_program/model_module，共16次1200秒完整搜索，2生成2执行uniform、原UCT/debug/action主终点。模块臂仅返回build_model(X)，外部I/O/验证/提交由共享RF基线拼接；完整臂可自由重写。是编辑范围/格式干预，不是固定算子集critic对照。
原RF起点仅重构为函数，超参/划分不变，实际初始执行计每次预算。接口限制不是安全沙箱或防泄漏证明。模块错误留作失败候选进入原debug，不替换成好解、不补样。
两份gpu28 RTX3090/6CPU/原镜像/4小时分配，上限8GPUh。16次全闭合才读效果；不追样本。具体门见FORETS_EDIT_SCOPE_PLAN_20260914.md。
21:09 UTC现场：SSH正常，只有旧12535 JobHeldUser，未动；gpu28空闲（21:18左右观察）。学长head仍be9335348b569086ef9b0af36a15b13e61fec45c，无新commit。
目前仅本地实现/5项单测通过，尚未build远端/激活账/调用API/提交GPU。所有动态必须新核，不凭本段旧观察重投。
新文件build_edit_scope_20260914.py、forets_edit_scope_20260914.py、verify_edit_scope_20260914.py、launch_edit_scope_20260914.py、derive_edit_scope_tools_20260914.py及release/forets-edit-scope-tools-20260914。先完整CPU接线与冻结reader再开跑。

## 账与源码
唯一当前账 /research/d7/spc/yzyang4/forets-repair-transfer-20260913-d151en61/paid.sqlite；1779calls/held6366536198nUSD/settled4966536198nUSD/2旧未知。
T1 auth a3a4561fb81d538d797e32997cf75deff8131784d8fa12da5b329a76f023743e；新包需原子封闭并完整承接。原100人民币/保守10USD总帽，不重置。凭据只远端aira-dojo/.env OPENROUTER_API_KEY，不回显/索要/本地保存。
生成Flash/Alibaba only/nofallback；原APIcritic Plus但本轮不调用。不存在免费共享Qwen可达性确认，不借别人的allocation或绕权限。
继承搜索source tree746d97a67922896b7d1581c4689f8b5f85204d30；配置/控制器前驱 /research/d7/spc/yzyang4/forets-wallclock-20260912-103zf3nb，prepared b676bfa46afae3c6e83b1d98855e77a368994fe7fdc22263f6693d581a4a57fd。
该PARENT旧账已被T1封闭，绝不再用。新builder配置和账分别指向上述两根。新source/interface尚待冻结actual tree。

## 不能重做/夸大
T1已闭合：20已知未成功4未知，0有效修复；两对照各6已知配对0胜6平，2未知；13257/13258终态。T1不是多步经验收益的逻辑必要条件。单次diff不扩大/不补跑。详见FORETS_REPAIR_TRANSFER_RESULTS_20260913.md。
此前34–37交付2胜6平是我方bounded交付修复，不是critic；38/39宽度1胜3负；40/41短记忆1胜2平1不可比；32/33参考critic0胜1平3负。单池critic选中有效程序但未兑现e2e。CV错位只一例，不推广。
G0/8B验收12892已完成不重跑；旧未通过kernel recovery补丁不得部署。间歇就绪风险真实存在，不掩饰、不擅自重试。
局部编辑已有AlphaEvolve/FunSearch和2609.04061先例；普通记忆已有ACL Findings/HASTE/CEB/MERIT/DisCo/OpenMLE-Evo。收益与机制必须实测，不宣称独特性已保证。
保护first960/Target300/Target522保持封闭。禁止旧HCE/多保真/Probe/score-channel/K>=1/agent底座更新。当前实验台仍aira-dojo。

## 操作
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
MLE镜像仅gpu27/gpu28兼容3090，不用projgpu39/不升级Torch/不静默CPU替换。节点名gpu28不是projgpu28。
本地repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813。只push myfork HEAD:phase1-value-critic；不强推/新branch/修改学长branch。最近已公开a94b1693f3773ad0dfd8a828589c87fdd00b9ad7。
apply_patch本地编辑；复杂SSH脚本scp后确认完成才调用。保持无关untracked不动。结果CSV/JSON若要逐字节，scoped -text并git add --renormalize后核index bytes。
研究盘1TB到期09-29，延期未知。0911包已隔离 senior-quarantine-0911-20260913，四配置非四合格run，不重下或打开未知cohort结果。学长doc先远端credential-shape scan命中流式脱敏再读。
