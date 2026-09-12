# 短交接：单票同预算全8闭合，未出现critic收益

更新2026-09-13 HK / 09-12 18:30 UTC；恢复先fetch→CURRENT_DIRECTION顶部0L186→核现场。
用户要一小时内实质工作，已真实运行8次搜索、独立读出、核对选择与程序错误；不重复G0。

## 最新事实与边界

- 13184/13185已结束，gpu28两份单3090/6CPU，seed26/27×Leaf/Space×random/单票Plus critic。
  每seed内同物理GPU、原镜像/Flash生成/600秒搜索/300秒程序。不是8B checkpoint训练或scaling。
- 18:23:08 UTC独立读出verified。技术合格8/8；random有效2/4、critic0/4。Leaf全缺，
  Space random .80230/.81034，critic均缺。无双方有效配对，不填0，不再追加同配方seed追显著。
- 25池、24选择全部独立回放匹配；critic10排名中6次改选，总排名时间21.15828978922218秒。
  Leaf4首选均超时；Space critic8候选/8修复均程序报错。39调用元数据已核，退出码0不是有效提交。
  错误分类为posthoc，journal可缺；root占位不计执行，v2才是有效分类，原first-pass保留但不引用其总数。
- 实际4298秒=1.193888888888889GPUh；8搜索API .496488499USD、含route本轮 .496715947USD。
  累计815调用、结算2.697577935/含未知责任4.097577935USD，仅两旧未知、新搜索无未知。总cap10USD，不清零。
- 揭盲前后继规则dd9d5d91：终点严重缺失→共同起点诊断，不能代替cold-start结果；
  单候选直接执行成本强基线纯配置入口已测试、实际typed配置通过，但尚未提交/新收费。
  不把经验检索或减票当新颖性；新矩阵须新seed/同期对照/保留失败，预算仍累计。

## 精确位置，禁止重跑已闭合读出

ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa
STAGE /research/d7/spc/yzyang4/forets-singlevote-stage-20260913-NV8o3rXI
source fb2c041c8ec8e352847881ee6fe2fb56d9561aec
controller dbf204d0a94844cf4ee4743b3a7cca769d2c5899
prepared 29349e0d78ce57701db2d5eae8bc35648f1fa50165df5eaff17a6502b3e402fe
AUTH 81c286978ff9ff58f79d7e9f8029aab335686a2d15158c6f2462efc035ea3279
reader commit afb42b0ca0e1dde9bd898510781b1e40d96e22bd；selection另在揭盲前冻结a4331b04。
summary e1722e9277dda73a9c73471f2cb2c53703e260d107e8bdaa31311fe48259cdab
CSV f9432dd929bdd51c08eab7ea81b8e0c4bf8d4f9945ccb602536dbed8c01b82f5
readout-intent/finished、singlevote-selection-verification均已存在；一次性reader不可再跑。
本地phase1/results/forets_singlevote_s26_s27_20260913，报告FORETS_SINGLE_VOTE_RESULTS_20260913.md。
旧13156/13165已闭合，旧账在cxb9p0og已封、现账ROOT/paid.sqlite；旧细节见原报告/Git。

## 约束与外部状态

- SSH linux5；Slurm配置/代理沿用现有入口；MLE原镜像仅gpu27/gpu28兼容3090，不能投projgpu39。
  不绕权限、升级Torch或CPU回退；旧held12535不动。本矩阵已完成，没有新GPU/API投放或automation。
- 09-12 18:19前最后fetch：学长dojo-reproduce仍113e25e7fa2570cb5f60401d051a1de3cce307c2。
  17:36观察共享镜像PermissionError；已有问询待回复，勿再索要key，未修改学长分支。
- Key仅远端aira-dojo/.env，OPENROUTER_API_KEY→运行时PRIMARY_KEY，不向本地服务自动转发。
  不读first960/Target300/Target522；不恢复HCE/多保真/Probe/score-channel/lookahead，不更新底座。
- push仅myfork phase1-value-critic，先内容/归档secret扫描，正常快进；不force、不动学长分支。
  无关未跟踪codex_tmp/output/tmp、旧tests.xml/09-01记录保留。研究盘到期2026-09-29，续期未知。
