# ForeTS 同预算端到端对照：实际运行包与协调入口

2026-09-10（香港）。用户要求六小时内推进同预算最终成绩，不重复 G0/模型验收。
本轮交付是实际运行准备及接线修复，**不是已运行的收益实验**。

## 固定问题与矩阵

leaf-classification、spaceship-titanic × seed 6/7 × uniform_random / critic_topk_random，共8run。
按既定交错顺序，两臂使用同一 Nemotron 免费生成器、4步、300秒单次执行限时、同候选生成规则。
每run worker上限1740秒，Slurm step上限30分钟，40次请求额度、单请求最多8192输出token、120秒请求超时。
两卡分配270分钟：1卡供critic、1卡供串行执行；随机臂闲置critic卡仍计入总费用。
名义9 GPU·时；按本轮实查KillWait=300秒计算为9.166666666666666 GPU·时，不能保证任意故障都能准时清理。
生成接口不自动回退到付费模型；最多320次实验请求，不把请求预留数当成功请求数或实际账单。
单独的公开人工输入端点检查尚未进行，其额度必须在实际启动前明确，不暗中额外发请求。

seed用于既有metadata及selector；不宣称相同seed能使外部API返回完全相同。
critic取top-2再选1；省略无筛选作用打分的开关仍关闭，不更换模型或事后调整top-k。
最终指标及失败处理沿用 `FORETS_E2E_READOUT_20260909.md`：选中解外部分数、完整8run、逐任务配对，不混合指标。

## 本轮实际完成

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

`prepare_forets_e2e_20260910.sbatch`是待审核执行入口，本轮**未提交**。执行开关只是误触保护，不是授权凭据。
需先安装远端OPENROUTER_API_KEY、完成有界公开输入的端点可用性检查，并明确该8run资源与检查额度，才能提交一次。
执行端只在进程内将该已知变量映射到PRIMARY_KEY；不会猜测现有PRIMARY_KEY属于哪个平台，也不使用聊天中的密钥。
新包不绕过原先保护集门；不读first-960、Target-300、Target-522，亦不训练/更新agent底座。

运行完成时输出runtime-manifest、全部run及配对读出、请求预留数；实际GPU分配费用仍需allocation结束后由sacct补齐。
不将service进程退出视作整个Slurm清理证明；不自动重试或重投。没有新的模型收益、干净scaling或e2e正结果。

调度器本轮只读确认：Slurm19.05.4、SelectTypeParameters=CR_CPU,CR_LLN、KillWait=300秒、OverTimeLimit=0。
准备入口保留已有`--exclusive`与明确CPU/GPU数，不为绕过资源阻塞打开共享GPU的overlap。
通用语义参考[Slurm srun官方文档](https://slurm.schedmd.com/srun.html)；仍以本集群实际行为为准。
