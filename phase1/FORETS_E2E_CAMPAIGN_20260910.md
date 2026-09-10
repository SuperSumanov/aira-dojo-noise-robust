# ForeTS 同预算端到端对照：实际运行包与协调入口

2026-09-10（香港）。用户要求六小时内推进同预算最终成绩，不重复 G0/模型验收。
首次交付是实际运行准备及接线修复。随后状态更新如下；准备阶段的未完成项不再代表当前状态。

## 最新状态：12933因任务镜像/GPU不兼容，未运行即取消

用户于9月10日明确指出现有MLE-bench镜像Torch与projgpu39架构不兼容。12892仅验证宿主critic，
未验证任务SIF。12933同时在projgpu39运行critic和MLE执行的部署缺少关键兼容性检查。
2026-09-10 06:09:40 UTC取消唯一PENDING作业12933，06:10:10 UTC独立核CANCELLED、Elapsed0、无运行产物。
未复现实际CUDA报错；兼容性故障由用户报告，部署/环境分离由代码确认。没有新的GPU/API执行或替代提交。
原19:59排队估计失效；原包/入口/配置保留为历史，不能直接重投。证据见results/forets_e2e_20260910/cancellation.json。
下一部署先核真实任务镜像的GPU计算与critic资源；两臂硬件/镜像一致，不擅自升级Torch或退到CPU。
当前仍无端到端结果；下列原矩阵与提交记录是历史事实，不是运行就绪证明。

## 原提交记录（已由上述取消状态覆盖）

用户随后提供凭据并要求继续，已仅在远端安装为0600。账户校验通过；固定免费Nemotron首个公开输入请求失败，
第二个请求成功（4.406812197004911秒，292输入/48输出/340总token），不因此宣称长期稳定或实际费用已知。
两次检查均非真实task，没有读取语料/保护集。安全导出已移除私人账户余额字段。

2026-09-09 18:14:51 UTC实际提交12933，18:15:23 UTC独立确认PENDING(Resources)、2GPU/12CPU、04:30:00、Requeue=0。
入口commit为8366208fb7e6329627dce90173d0e9583f1200c1；没有重复G0/模型验收，也没有重复投递。
调度预计香港9月10日19:59:12启动，非承诺；目前没有任务成绩。
唯一运行根为下述隔离目录的package-c；断线后先检查12933和submission.json，禁止盲目重投。
实际GPU账等作业结束，队列等待不计GPU分配时长。其余配置、失败保留和读出定义不变。

## 固定问题与矩阵

leaf-classification、spaceship-titanic × seed 6/7 × uniform_random / critic_topk_random，共8run。
按既定交错顺序，两臂使用同一 Nemotron 免费生成器、4步、300秒单次执行限时、同候选生成规则。
每run worker上限1740秒，Slurm step上限30分钟，40次请求额度、单请求最多8192输出token、120秒请求超时。
两卡分配270分钟：1卡供critic、1卡供串行执行；随机臂闲置critic卡仍计入总费用。
名义9 GPU·时；按本轮实查KillWait=300秒计算为9.166666666666666 GPU·时，不能保证任意故障都能准时清理。
生成接口不自动回退到付费模型；最多320次实验请求，不把请求预留数当成功请求数或实际账单。
单独的公开人工输入端点检查已进行2次，每次最多1个生成请求；1次失败、1次通过，另计于320次实验请求之外。

seed用于既有metadata及selector；不宣称相同seed能使外部API返回完全相同。
critic取top-2再选1；省略无筛选作用打分的开关仍关闭，不更换模型或事后调整top-k。
最终指标及失败处理沿用 `FORETS_E2E_READOUT_20260909.md`：选中解外部分数、完整8run、逐任务配对，不混合指标。

## 准备阶段历史（凭据与提交状态已由顶部更新覆盖）

- 已fetch：我方8425cffa、学长065b0fba未更新；没有修改学长分支或生产代码。
- 香港01:47只读取远端凭据变量的存在性：两处均无OPENROUTER_API_KEY、OpenRouter形状值计数均0。
  用户队列只有旧12535 JobHeldUser，未释放。12892已完成，本轮不再读取模型或重复验收。
- 两个任务的prepared/public、prepared/private目录均存在；只列public文件名，未读取任何数据内容/答案。
- 配置发现：aira-dojo/.env的SUPERIMAGE_DIR指向没有sif的目录；aira-dojo-reproduce配置指向的目录有
  `superimage.root.2026-07-macos-v1.sif`，大小19717783552字节。新包显式固定后者，两臂相同，不更改原.env。
- `forets_e2e_package.py`不再停在RunnerConfig模板：真实生成8个RunConfig，经worker反序列化往返校验，
  实际配置两两只允许selection_policy和明确run身份/派生路径不同。固定source-v5声明tree
  `2ff5277ba17327c6c03326a018b59f704402af6b`，没有为本次准备再读整模型或重建整个源码树。
- 初次准备package-a在Hydra新增metadata字段语法失败，修正为显式新增；package-b发现solver.exp_name
  是派生run编号，精确纳入身份归一化后package-c成功。失败目录保留，均没有GPU/API/任务运行。
- `forets_e2e_campaign.py`复用已有SrunPoolLauncher和bounded worker，不另造搜索算法。
  一个critic服务、独立限时worker、同一双卡allocation；服务退出则禁止继续启动，缺凭据则在模型启动前拒绝。
  运行汇总绑定pool真正写出的config和identity路径，而不是准备模板中的建议路径；保留失败和未开始的run。
- `forets_e2e_critic_service.py`只用于真实搜索的服务启动，不包含验收输入或计时循环；离线载入既有模型一次。
- 当前非交互SSH环境无https_proxy；batch入口复用已存在的远端env_setup.sh，只修改该作业进程环境并抑制输出。
  本轮仅检查文件存在和shell语法，没有为此调用生成接口，也没有据此声称代理连通已验证。
- 实际RunConfig验证、启动门拒绝、单臂预算变更拒绝、真实pool路径对接、缺失结果保留等CPU接线检查通过。
  服务与Slurm均为测试替身，未运行模型/任务/外部API；不能把它说成真实双step共同运行已验证。

## 可用位置与下一步

隔离目录 `/research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2/`；实际准备包为`package-c/`。
只读检查（不分配GPU、不读取凭据）：

```text
/research/d7/spc/yzyang4/venvs/aira/bin/python -B /research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2/forets_e2e_campaign.py --package /research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2/package-c
```

准备阶段的`prepare_forets_e2e_20260910.sbatch`现已用于上面的唯一作业12933。执行开关只是误触保护，不是授权凭据。
远端凭据和有界公开输入检查已完成；后续不要重复安装/重新检查来代替跟进实际作业。
执行端只在进程内将该已知远端变量映射到PRIMARY_KEY；不会猜测原PRIMARY_KEY所属平台，不把聊天密钥写入代码或产物。
新包不绕过原先保护集门；不读first-960、Target-300、Target-522，亦不训练/更新agent底座。

运行完成时输出runtime-manifest、全部run及配对读出、请求预留数；实际GPU分配费用仍需allocation结束后由sacct补齐。
不将service进程退出视作整个Slurm清理证明；不自动重试或重投。没有新的模型收益、干净scaling或e2e正结果。

调度器本轮只读确认：Slurm19.05.4、SelectTypeParameters=CR_CPU,CR_LLN、KillWait=300秒、OverTimeLimit=0。
准备入口保留已有`--exclusive`与明确CPU/GPU数，不为绕过资源阻塞打开共享GPU的overlap。
通用语义参考[Slurm srun官方文档](https://slurm.schedmd.com/srun.html)；仍以本集群实际行为为准。
