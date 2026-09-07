# 给学长：完整尺寸保存/恢复验收已完成，下一步转向合格标签来源

2026-09-07 10:03 UTC完成；本报告区分工程验收、来源资格和模型收益。

## 本次真正完成了什么

原作业12664在两张RTX3090上完成Qwen3-1.7B Base、16,384 context、BF16、FlashAttention2、
ZeRO3 CPUAdam的G更新/保存→新进程恢复→L更新/保存。参数量1,720,577,025；seed6、lr1e-5，
world2×micro1×accum64，global128 pairs。两次更新合计8,388,608 valid tokens，全部为合成工程输入。
GPU实际2729秒、5458 GPU秒；累计本轮工程21960 GPU秒的既有账目不变，本次CPU续行没有新增GPU消耗。

此前单次CPU终验触及900秒上限，只有AUTHENTICATED，不能冒充通过。这次保持原六role实物检查器不变，
按两个检查点×两个rank分成四个可恢复事务，每项先后完整hash，最后再重核两个整包。
四组及最终阶段均returncode=0，无超时，文件访问trace检查均通过；所有实际检查点原文件保留。

|验收项|当前证据|
|---|---|
|实际GPU路径|G更新/保存、新进程恢复、L更新/保存已完整退出|
|四组实际payload|AdamW、FP32 master分片、Python/NumPy/Torch RNG、scaler六类状态均通过原检查器|
|文件与身份|逐组前后全hash、最后两整包hash、源码/原AUTH/manifest绑定通过|
|独立收尾|另一个无tensor导入的程序复核68源码、四项唯一覆盖、五EXIT、文件metadata及访问trace|
|测试|固定audit源码43项实际Linux测试；独立收尾工具另有6项本地/远端自检|

独立收尾是证据链复核，**不是第二套tensor重实现**；它不再反序列化或重读41GB payload。
实际payload读取与全量hash由前述固定核验器完成。文件trace不覆盖网络syscalls，也不声称通用恶意pickle沙箱。
五个CPU阶段墙钟合计1190.3012236970098秒；逐阶段见[runs.csv](runs.csv)。这不是多seed吞吐实验。

## 尚未证明的事

- 没有新critic收益、clean scaling或真实搜索utility结论。
- 没有做本尺寸“不间断训练”对照的final parity；不能由保存/恢复验收推断完全等价。
- 工程输入只有warmup更新，没有steady-state吞吐结论。
- `ADMITTED_RELEASES`仍为空，同预算seeds6/7的`Lbudget`对`G-reuse→L-full`四fit未启动。
- first960/Target300/Target522结果未打开，旧12535未改变。

## 学长语料与下一步

10:01 UTC复查公开上传目录：最新可见日期0905；0904/0905分别6/12个归档名，与本地相符，无config-v2 sidecar。
这次只查元数据，不下载/打开归档；名称相同不代表内容已经重新认证。
当前摄取仍737 physical /711 eligible runs、4380 structural pairs、58 tasks，closure=false。
对应[safe metadata原回执](senior_metadata.json)。我方分支fetch成功，学长分支仍为
`40d7dea10738f159fc97cad8487ab4ada88022a3`；上游origin的TLS fetch失败没有影响本次固定版本核验。

下一步不再重复G0。已找回固定84个历史run的12个记录commit，并物化3547份程序文件；
缺口是实际评分/运行出处与合格新标签，不是缺一份相同Cards。遵循学长建议，不再索要已删snapshot：

1. 若生产端仍有原评分/运行的实际记录，按现存记录核验；不能以今天SHA代填过去。
2. 若无法恢复，优先明确后续独立开发生产范围并从生产时保留运行/评分出处；不能从冻结前瞻cohort挪样本。
3. 历史程序的完整重执行仅作为另立、有界、预先冻结的来源路线；不按旧成绩挑样本、不先短跑再追加预算。
   全量3447非空程序的条件cap为6364.666666666667 GPU小时，不能默认全量重跑。

当前还没有足够证据将任何一条来源路线标为可正式训练。工程障碍已经缩小，但不能靠放松数据边界制造正结果。
完整下一步边界见[来源路线](../../NEXT_REAL_DATA_ROUTE_20260907.md)。

## 可复核身份与失败保留

- training commit：`88522f74cafcd45778751c5315fa0a89a1704965`
- audit commit：`c7c0aa4a0181be51d7c38dfa1942c6b68ca353e9`
- [FINAL](final.json) SHA：`0886d832747c1f5ac5e9db80d8f516f271987df6a3b348f2379a44d3be03f9d8`
- [独立回执](independent_review.json) SHA：`f8174e863b3621d989c27118c803f1e4e02a4e8001229b039b94aafc4d3793d8`
- [导出清单](export_manifest.json) SHA：`851336456fc9bddfa5b1310ac57b1f406013fd9b4e87a6840e1b3ec6f9a6a873`
- 40份原始安全文件由清单绑定；清单本身、最新语料元数据及5份实际helper另按远端SHA逐字节核对，共47文件。
- 旧900秒超时记录在[上一轮说明](../session_completion_20260907/README.md)；本轮初次R5缺pytest的准备目录保留。
  新r2仅给测试进程私有pytest工具层，未安装或修改训练环境，生产核验不使用该工具层。
- `operations/`保留实际执行helper；**它们不是应再次运行的任务清单**，本验收已完成。
