# 受控并发下的同预算critic对照：完整结果

2026-09-12 12:00 UTC。13156全8闭合，11:55:43独立读出通过，5份合格原submission数值复验一致。
这是开发探索，没有证明稳定正收益或干净scaling。对应[冻结方案](FORETS_PARALLEL_E2E_PLAN_20260912.md)。

## 完整结果

Leaf/Spaceship × seed24/25 × random/contextual critic。Flash生成、Plus双序Borda/top2后选1，
600秒搜索截止、程序300秒、64步上限、原镜像/gpu28/单3090/6CPU。两臂共同恢复最多4路生成请求在途。
只有选择规则在臂间变化；与旧串行版本使用不同seed，不作并发的因果收益比较。

| 任务/seed | random截止合格成绩 | critic截止合格成绩 | 解释 |
| --- | ---: | ---: | --- |
| Leaf24（logloss越低越好） | 缺失 | 0.47866 | 双方技术合格；critic有终点、random截止仍无合格终点 |
| Leaf25 | 缺失 | 0.71343 | random内核握手故障，不能算公平质量胜出 |
| Spaceship24（accuracy越高越好） | 0.81839 | 0.80230 | 唯一双方有效配对：critic−0.01609，即−1.609个百分点 |
| Spaceship25 | 0.75402 | 缺失 | critic内核握手故障，不填0或补跑 |

- 全8：random合格2/4、critic3/4，技术合格6/8。缺失终点不等于从未产生任何submission。
- Leaf critic条件中位数0.596045、样本标准差0.16600745901916578；random无条件成绩可报。
- Spaceship random条件中位数0.786205、样本标准差0.04551646350497801；critic仅一个有效值0.80230，方差不可估。
  分母不同的条件中位数不能替代逐seed配对，唯一有效配对是负差。
- Leaf24是局部的可兑现提交信号，但Leaf25被基础设施混淆；不能将2/2对0/2包装成跨seed稳定效果。
  与13152一起看质量方向仍不稳定；停止同配方追加seed追显著，保留所有失败和不利配对。

## 成本、故障与计时边界

allocation 4009秒，1.113611111111111 GPU·h；8搜索API结算0.547526252 USD，排名占0.178036040 USD。
全历史账658条，累计结算2.200861988 USD、含未知的责任3.600861988 USD；仍为两条历史未知，本8搜索无新增未知。
这不是账户余额。科学截止600秒不代表占卡精确600秒；第一步骤含清理971秒，全部额外资源照计。

129条公共传输计时按scope独立匹配，全部8搜索均观察到客户端peak=4；另23次排名走单独路径，没有该计时。
不能将129条当全部152个搜索请求，不能相加并发时长后宣称墙钟加速或纯模型推理速度。

51次握手计数中2次失败：Leaf25 random的debug派发前、Spaceship25 critic的候选派发前。
两次均120秒发120条kernel-info请求，仅收到3条无关parent消息，匹配shell reply/idle均为0。
不是“只有idle缺失”；kernel/server/WebSocket底层原因仍未知。51次为8run内嵌事件，不是51次独立实验。
未放宽握手、增加超时或补跑。两条600秒截止random仍有未闭合task调用，归因余量明确包含该调用，不能全算生成/critic延迟。

## 收尾恢复与证据

08:38:53自动收尾查询Slurm数据库连接超时，记录`failed_closed/readout_called=false`；不是实验在此时终止。
恢复前核实全终态、8槽无running、原PID退出、四个固定收尾SHA一致且无readout intent。
仅调用原固定读出一次，参数仍`--seeds 24 25`；无新GPU/API/程序执行，不改选点/评分。
原`closeout-finished.json`保留失败，另写`recovery-readout-finished.json`。补充归因显式接受该恢复收据，
29项截止/读出/归因回归通过；原四个stage文件未覆盖。

[完整逐run结果与收据](results/forets_parallel_s24_s25_20260912)：

- source：`e07cb8c61bca347c61bb8253c84eda826b1add6a`
- producer/controller：`8df9858fa6f746e598b6fe56527d081fe51383aa`
- summary SHA：`a127831408688b545e3d666b790fe1f75b65e82f9324d21c8c4cfc0243d39e90`
- CSV SHA：`b535b6a439cefdcb29ada9d5ef26baeb3e8b0793f90bca0fa31c5c79bda37f81`
- attribution SHA：`3a144d4db72f5889cefee2704a689a1198e99426d7d4d89669a891919a99154c`
- diagnostics SHA：`c1bb304c8d1ffa4be487100bf14c75d67eb93eef63984ec8235e79c0e0b79a36`

原产物：`/research/d7/spc/yzyang4/forets-wallclock-20260912-cxb9p0og`。不重跑/重评分，不将已揭盲结果改为新冻结测试。
当前裁决：保留有效性/质量分开研究的线索，优先解决执行故障、本地生成服务可用性与预算匹配，
再比较低额外成本独立critic与random；历史API语料继续利用。见[来源迁移](LOCAL_GENERATOR_TRANSITION_20260912.md)。
