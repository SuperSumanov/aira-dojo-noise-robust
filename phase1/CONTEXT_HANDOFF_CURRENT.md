# 短交接：共同起点改进实验正在运行，全8结束前不读成绩

2026-09-13 HK / 09-12 19:45 UTC。恢复先fetch→CURRENT_DIRECTION顶部0L187→核现场。
用户希望本会话一小时内有价值结果；本轮始于19:12 UTC，预计20:06–20:12 UTC收齐/复验，不启动新的automation。

## 活跃实验（不是G0/训练，也不覆盖冷启动）

- 13190/13191于19:28:51 UTC提交；19:44观察两份均RUNNING/gpu28，各第一条已退出（控制器exit1），第二条running，Space四条pending。
  控制器exit1不直接等同无效提交，预算截止也可如此；须全矩阵闭合后按冻结读出核技术资格和成绩。
- seed28/29×Leaf/Space×random/单票Plus critic，共8；两份各单3090/6CPU、90分钟，总最多3GPUh。
  每搜索600秒/程序300秒/原镜像/Flash生成/相同操作提示，臂间仅选择规则不同。
- 第一扩展只执行同一固定RandomForest，0生成/排名调用，实际训练内80/20验证再全量拟合、评分分析都计入600秒。
  第二扩展恢复原4候选。两首run真实账本已观察相同baselineSHA、1候选、0生成、1任务调用，仅结构未看分数。
  全8闭合才核每对起点有效且独立分相同、再比较最终分与改进。缺失/失败保留，不补0、不补跑。
- 生产source唯一1ec18564f176d58a3a7ac3a46852ad92044777b5；controller a46dbd189d6f74cf7357377ba41fcc065b1d414c。
  4本地新测试/6读出测试通过；实际导入首步和后续步、两任务合成程序已通过，不称真实效果。
  提交前排除digest重名、缺少真实CV反馈和格式绑定问题；只有v4投放，早期3准备包未激活/无GPU/API。
  测试清理时SQLite连接未闭导致NFS目录非空，已正确关闭；重用基础集成收据时补齐显式模块路径，未改科学协议。
- 当前账ROOT/paid.sqlite，前身bll4ghfa已sealed。继承815条、结算2.697577935/责任4.097577935USD、两旧未知。
  总责任cap10USD（用户100人民币授权的保守界限）；不重置旧账。两route均rc0，新搜索不允许新增已结束未知。

## 位置与读出（一次性，未执行）

ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-2o9mw39n
STAGE /research/d7/spc/yzyang4/forets-common-stage-20260913-I7fhYJJa
prepared 2fcde0dd017124ab20c73a7bb505462185525d7b377d890c4e66e08f801986b5
AUTH 6dc2fc5b2e522fa762016e761921692b5ee213b445bad580f59a3fe7536116e1
reader commit a81f0c44416f8adc6cadaf4231d9b9f7f18b821d
readout-plan SHA 0a8abf4ccd5d76d70f2d59e8f95a6aca4e22b37c053b11d692e9fa4d896c5cb9，19:28冻结七reader SHA。
全8/两job终态、无活跃scope、新收费全结算后：
/research/d7/spc/yzyang4/venvs/aira/bin/python -B STAGE/readout_forets_common_start_20260913.py ROOT
把STAGE/ROOT替换成上述绝对路径。只调用一次；如intent已存在先诊断，不盲目重跑。
输出wallclock-summary/CSV、singlevote-attribution、common-start-summary/CSV、readout-finished。
独立核起点归档/原始终点/选择回放，公共成本模块只用于新ROOT；不能调用旧singlevote main函数。

## 最近已闭合结果与禁止事项

- 等待中另核旧bll4ghfa：四份Space保存图确实为单链，零分叉/悬空边/不可达节点；四份Leaf无完整journal，不当空树。
  实际ForeTS继承MCTS，CPU示例uct_c=0/1/100同选坏叶，incumbent参考选旧好父；无GPU/API/反事实收益。
  旧图审计v1曾把整数step引用误当UUID，错误悬空/不可达数作废；v2纠正，原件保留。
  v2 SHA92ba7283c81fd8b3fa817ec667260859170e596e8382083b2132770a5199a434；详情FORETS_PARENT_TOPOLOGY_FINDING_20260913.md。
  parent-only参考/默认不变patch已准备、本地测试通过，但未投放；不改13190/13191，未激活下一矩阵。
- 上轮13184/13185 source fb2c041c8ec8e352847881ee6fe2fb56d9561aec已闭合，8/8技术合格、
  random有效2/4、critic0/4；Space random .80230/.81034。无双有效配对；不重跑旧readers或追seed。
  报告FORETS_SINGLE_VOTE_RESULTS_20260913.md，旧summary e1722e9277dda73a9c73471f2cb2c53703e260d107e8bdaa31311fe48259cdab。
- 当前共同起点只是诊断，不是新方法/干净scaling/冷启动获胜。single-proposal成本强基线已准备但仍未部署。
- SSH linux5；Slurm配置/代理沿用入口；MLE原镜像仅gpu27/gpu28兼容3090，不能投projgpu39、升级Torch或静默CPU回退。
  旧held12535不动；无底座更新；first960/Target300/Target522封闭；不恢复HCE/多保真/Probe/score-channel/lookahead。
- 本轮fetch学长dojo-reproduce仍113e25e7fa2570cb5f60401d051a1de3cce307c2，未改学长分支。
  上次共享本地模型镜像PermissionError、已有问询待回复；勿重索要key。
  Key仅远端aira-dojo/.env，OPENROUTER_API_KEY→PRIMARY_KEY，不自动发给学长本地服务。
- push只myfork phase1-value-critic，secret/content/archive先扫描、正常快进，不force。
  研究盘2026-09-29到期，续期未知；保留无关未跟踪目录及原实验。
