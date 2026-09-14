# 当前短交接 — 2026-09-14 00:41 UTC
方向CURRENT_DIRECTION 0L202。六小时会话窗口09-13 21:06:43→09-14 03:06:43 UTC（HK11:06:43结束）。继续会话内研究，不新建自动任务替代，不伪造/保证正数。

## 廉价选择器v2已真实运行
00:38:17单次提交13298/13299；00:40:54确认两者gpu28 RUNNING，首条各native绑定4/3，已越过原路径失败处。预计约01:40–01:55 UTC全12闭合；最长两85分钟。不要中期读分/改策略/补seed。
ROOT=/research/d7/spc/yzyang4/forets-wallclock-20260912-km65uuej
STAGE=/research/d7/spc/yzyang4/forets-cheap-v2-stage-20260914-bqkP9eR8
source61b48862532d048f5f04a517e3f89b211c59bd3d；controller e4f9dfcf409b62ea7d6d00e6e4b9189712029ee3；preparedb2f53da2f6c9cde40c3a6b066a2670a13073f08547bb5d7f301ae4ba8293720b；auth42c7dff9a962500c91bc40b7e5928d688a525638b8afb66c0bcd20e4206031b7。
readout plan4affb5b380bf7aabd71a956208b7c3c96e243d0ab907158aa56c092ec48408fe。source archive57323979e6d07f3edc0a9991a3bad8abcccdbe04270737a85bf752425ea3ca67（same tree归档时间会使tar不同，必须成套复制）。actualbatch12+80tie、cutoff、两route均通过。
矩阵Leaf/Space×46/47×uniform/short_code/learned_validity=12，600秒/300秒程序/64step/100adapter、2生成1执行、固定HGB、共用Fresh原镜像gpu28/6CPU。只有选择器不同。每6搜索一allocation。真实最终action主终点；全12及两allocation闭合后运行STAGE/readout_cheap_selector_20260914.py ROOT，不改冻结reader。
用STAGE/monitor_cheap_selector_v2_20260914.py，只读结构/账。不同root的v1monitor不可复用。00:40:54账2635calls/held7679679107/settled6279679107nUSD/旧unresolved2，未stopped；在途请求可能临时增加unresolved，不能直接叫未知失败。现有reserve_backpressure会等待额度，不改费用策略。

## 原失败尝试/费用接线，保留并禁止重跑
v1 q_imzdb_：13293/13294各67秒取消，共134秒；4生产回执存在但backend找错integration固定名。四行报错、两中断、六未开始。proofa775e0d9a6dcf62accf055f31ebd6822fcf9b06a2adf225b16c03ada227ea8e7证明0生成/0评分/0search API，只4route调用。全矩阵保留，未按效果选seed。
修正仅生产childPID回执定位/拒绝旧回执，不改执行/image/GPU；4针对测试+7reader测试通过。v2临时草稿tpjljg17激活被重复route scope主键拒绝，独立验证原账仍active/2623calls、目标db空表，原子rollback无消费。改名route_cheap_selector_v2后新建正式km65uuej，旧草稿不复用。原q_imzdb_现在sealed。
两85分钟+失败134秒<=原3GPUh；原累计100RMB/保守10USD帽及两未知保留。禁止重试active原包/重新激活/复制旧账为新钱。

## 并行已完成EScope旧轨迹固定模型迁移
冻结CHEAP_SELECTOR_TRANSFER_PLAN_20260914在公开e4f9dfcf，跑完初分析ec995b738f2c49fb57b6e0e8cb3f7c26833f20a5ecf8db93a226963e60483cfb。
旧whole_program八run，原资格主组Leaf3run5pair/2discordant；Space4run25pair/7discordant。固定HGB关键对Leaf2成功vs短代码1；Space6vs2；每任务run bootstrap下界0。API/GPU/fit0；仅initial validity，非最终搜索收益/确认。31all observed，30eligible，训练重合/重复0（逐run完整原因在结果）。
ROOT88v5m9dr/cheap-selector-transfer.json；独立verify_cheap_scope_transfer_20260914正在CPU session37557，尚未确认。不根据该诊断修改当前E2E矩阵。

## CPU实质结果
旧v9过滤了无分节点，另恢复锚定旧run失败记录2296/123run，并补早期Space186/15run；合2482/138run/14任务、929有效1553无效。只限<08-12且与公开v9有节点对应的run，不代表无锚点全失败run。与157旧目标hash/AST/30k前缀purge0。
旧小TFIDF及历史四-fit门均失败，不重判。补Space后独立冻结两-fit（03942ad9278b356f28180d9a0b4f82ca69db4a86在训练前）：code_only Leaf .9215686274509804/Space .6581280788177338/macro .7898483531343572，CI[.7128176728118785,.8819572347335004]，通过开发门；task one-hot版本失败，不能称任务条件化有效。
短代码Leaf .9084967320261438/Space .6543513957307061；优势小且157/27run目标反复用于开发，非未触碰确认。独立raw labels/独立AST/固定模型314预测最大差0。同21旧双候选池仅3个discordant，code_only3/3 vs短代码1/3；不是21胜/E2E/策略反事实。两-fit CPU24.049559558043256秒/API0/GPU0。
模型根 /research/d7/spc/yzyang4/forets-task-validity-20260914-n8q3h72y，code_only.private.joblib SHA05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1，sklearn1.6.1，不重训。summary66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33；independent8fbd1c92e404ffbe585810a174ce78611e6df71ead976ced669019e84b2265cb。报告TASK_CONDITIONED_VALIDITY_RESULTS_20260914.md。

## EScope16已完，禁止扩大同配方
ROOT=/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr
STAGE=/research/d7/spc/yzyang4/forets-edit-scope-stage-20260914-HDeOvQ6i
source8bb325fa167a9db54656dd6535ce1f3d69859c22；prepared731001dfa4c054ec16823bbfb685de1f2ad14314e5d5ad4597d12097b713b979。
13282/13283终态FAILED/6862、8983秒，总4.401388888888889GPUh。实际保存了搜索产物；4技术未知（3kernel、1原100请求cap）。主action4可比对0胜4负、4对未知；Leaf1对gain−1.1474；Space3对median−.019540000000000002。原扩大门/preservation后继均失败，不补seed、不改资格。
首次主reader core完成后因漏原生extract_code的表示转换而失败。234候选调用只读排查，146处差异全部等于原生转换。明确addendum修正比较表示；原六reader/原始文件/资格/端点未改，core不重复。
summary8fd3598f99041d7878daec43ef107da68f2e91a340203a726f3c9e8aff1911cd；addendum21bf08bbeb3e08ecc7350c696ad2540d5a0901f930cc60b05705adc7048c0545；compare46494fc368919745e32fef789dbb8908597553f9650c132f354fe423875bf4f6；mechanismee9d1414ab9884c4ecd9af27cfb084ca2b3f6ef1f61ca812a061d7e355e1e100。剩余prefix/short-control按原脚本可运行。禁止重跑原main（exclusive结果已写）。新三臂来自独立cheap模型开发门，不是绕EScope失败门。

## 费用与已完成资产
传统13284完成8/8有效512候选；Leafmedian.05948logloss/Space .790805acc；API0/2054秒，非完整AutoGluon。Fresh13286/13287合成+真实RF四对1e-12一致、24双worker/IPython通过，非普遍可靠性/E2E。不重复G0。
0912学长包11,844,727bytes已隔离，4config producer61459c0a1248900079dafed7c505afa87e476b40，不是4合格run；未入训练/LATEST。别重下。免费共享端点未确认，不借他人allocation。

## 禁止重做/操作
G0/12892/8B完成；T1修复0有效门失败；旧宽度1胜3负/短记忆1胜2平1未知/参考critic0胜1平3负。旧HCE/多保真/Probe/score-channel/K>=1/底座更新禁；first960/Target300/Target522封闭。
CodeScaler/MARS/Gome/MLE-STAR/iML等已有相关先例，静态失败预测不自称原创。scope只是代码表面约定，非语义/安全隔离。
SSH linux5；airaPython=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE只gpu27/gpu28原镜像，禁projgpu39/Torch升级。旧12535 JobHeldUser不动。
凭据只远端aira-dojo/.env OPENROUTER_API_KEY，不回显/本地保存/索要；累计100RMB保守USD10责任帽。
本地C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；push仅myfork HEAD:phase1-value-critic，最后确认公开e4f9dfcf409b62ea7d6d00e6e4b9189712029ee3。精确暂存、secret计数扫描再push；不强推/新branch/改学长branch。apply_patch编辑，复杂SSH经文件，无关untracked保留。研究盘1TB到2026-09-29，续期未知。
