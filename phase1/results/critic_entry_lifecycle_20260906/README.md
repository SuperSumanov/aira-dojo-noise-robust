# 训练入口、恢复和开发读出连接验收

2026-09-06，承接公开`bb6b20c5fb41486062f93f82b88b1afdfd008228`。
**这是工程完成，不是新的模型收益、scaling或GPU验收。** 没有合格生产数据包被悄悄放行。

## 实际完成了什么

TRAIN文件读取→既有四fit token计划→实际Qwen critic/AdamW→完整checkpoint→新进程恢复，
在2进程CPU实际运行。代码`95e72f37c1b745ca101390c887c41eed6e9b6f28`；
4433参数随机Qwen、float32、AdamW/WD0、dropout0.1、seeds6/7。
每次完整轨迹2updates/8pair visits/592valid tokens；是短合成序列，**不是1.7B或真实16K压力测试**。

A/B各4完整轨迹及seed6两臂prefix/resume，共16轨迹。独立校验24checkpoint、
8组实际状态比较、8次rank最终状态比较；模型、AdamW、Python/NumPy/Torch RNG及消费顺序相同。
A/B工程状态JSON逐字相同；时间字段不要求相同。独立回执SHA：
`5b444b055eeb40fc60b618ec6cfcd1c0e66ed94b1d2c32807afb31d380073786`。

随后代码`0d0bcb70a6ae688f263b0224f945cd4d543f4f8e`实际加载这4个最终checkpoint，
先锁完整模型集，再合并4模型+训练侧固定TF-IDF的8个合成开发endpoint/4pair预测，
固定全部预测后加入合成truth并执行单独四fit统计。独立逐seed重数相同，查询不改变权重。
pipeline summary SHA=`fe0a09d66629e3b970f6b0d21aeade7957803eb3e56939fc91f0e7f99b5c52c5`。
合成准确率/收益没有公开，也不能解释为研究结论。DDP checkpoint加载不等同ZeRO3生产推理已验收。

## 已接入的约束

- Lbudget不打开G标签文件；删除G标签文件后局部路径仍通过，full则拒绝缺失。
- dev/test/保护角色拒绝；文件身份/大小/稳定性/完整SHA和输入schema核验。
- launch计划不符在标签和模型加载之前拒绝；生产注册表保持空，不信任自填JSON资格。
- per-update记录实际消费哈希、pair/tokens/LR、时间，固定点存完整状态；不完整停止不叫COMPLETED。
- 四fit读出与五臂确认分离；按任务等权、两seed、预测tie=0.5、既定bootstrap与LOTO。
  2%边界与零LOTO用精确有理数计算后转显示浮点，避免相减舍入改变决策。
- TF-IDF仅train endpoint拟合词表和模型、query不refit；超参沿用固定baseline。
  不把合成字典或hash当生产资格，实际TRAIN池仍须固定来源。

## 修复和局限（原失败保留）

1. Windows路径stat与描述符fstat的ctime有差异：改为各接口内部前后稳定性检查，
   跨接口仍核inode/size及完整内容hash，未用放宽hash掩盖问题。
2. 首次远端launcher误拒tar的合法顶层目录，未开始CPU训练；只修复目录白名单，保留原helper和空失败目录。
3. 两rank必须先完成输出目录不存在检查，再由rank0创建，避免检查/创建竞态。
4. TF-IDF远端初测4失败/20通过：sklearn词表索引是numpy.int64，JSON无法序列化。
   `6394e3763dbcbbc67389eeb94eae17d5748dc3ff`转为原生整数，24项全通过；7条SciPy弃用警告保留。
5. 本地综合90项测试通过；本地缺sklearn的测试未冒充通过，使用远端exp环境实测。

trace仅对file/process追踪作明确禁止路径字面扫描，无命中；**不是完整路径解析、OS隔离或网络syscall审计**。
部署后源码仍与精确Git导出一致（CPU22文件，pipeline30项含manifest/已批准shell派生）。
`runs.csv`逐工程轨迹记录时间、seed、实际tokens和commit；时间不含包导入/启动/排队，不能外推正式成本。
原迹线留在远端，本目录仅小型结构回执；`manifest.json`绑定首批10个原始回执，后加README/operations不在该旧清单中。

## 正式四fit仍缺什么

真实生产/evaluator证据、experiment train/dev隔离和同版本Cards/G/L实际构建仍待学长。
03:08香港核12535仍PENDING/Resources/0秒；不得称GPU新consumer或FA2/16K恢复已过。
新的生产setup代码明确离线FA2、不静默fallback，但未在实卡验收，注册表不得开启。

存储也须重新按完整恢复状态核算：固定DS源码明确保存FP32 master与AdamW两个moment。
对1720577025参数，仅这三份原始数组就20646924300bytes（19.228946696966887GiB）；
4个最终checkpoint这部分即76.91578678786755GiB，另加metadata、padding、临时保存及其它产物。
这是未压缩payload推算，**不是实测checkpoint大小或空间预留**。旧仅权重4GiB预留不能作为本流程验收。
df显示共享盘可用34T，quota只返回home，均不能证明1TB研究目录剩余配额；本轮未做大额预留/删除。

学长fork/dojo-reproduce重新fetch仍为b8d095180415957aa1bab31fa53ead1bba261c03；
Drive根元数据仍最新0904，无0905。0904最早03:44:48.903091香港成熟，另须三次稳定观察；未提前摄取。
