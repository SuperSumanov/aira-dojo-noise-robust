# 历史生产证据补齐：身份异常已解释，运行版本仍未认证

## 2026-09-06 05:59补查：固定归档未命中代码备份签名

在同一84run/24归档范围，另作一次300秒上限的header-only检查，不继续读原先终止的日志前缀。
实际849243182压缩字节、1489目录项，前后SHA与原固定账本一致；预定义代码快照、实现树、依赖/运行记录
签名均未命中，41.95562523882836秒完成。仅访问归档目录，不extract/parse任何成员，未发布成员名或私有路径。
gzip流式遍历会解压并跳过成员字节，不声称OS级零字节隔离。

公开原始回执`backup_header_inventory.json` SHA
`8afd1578e2f286b478ee471e66d0f3a79210dca691f884a94500730db13be521`；
执行源码`phase1/scripts/inspect_historical_backup_headers_20260906.py` SHA
`ae7de5cd4f1fa03ed45b547b17547c07ab88755b74d835df8eb9960ef4980294`。
只做过一次目录扫描及原归档前后hash，不称双独立raw抽取；5项本地签名检查通过。
阴性仅限指定归档和签名，不证明任意命名备份或其它生产机没有材料。没有解决训练来源资格，也没有模型效果。

## 01:22原报告

2026-09-06 01:22 香港。沿固定676-run来源账本继续推进；不是模型效果实验，也不是训练准入证明。

## 这轮真正补齐了什么

**原唯一Slurm不一致已找到真实worker证据。** 固定归档中两份身份JSON经过独立重读、严格字段检查、
归档前后SHA和原config/attempt连接核对。第一次worker与第一次controller记录一致；第二次worker与config一致，
但第二次controller的step字段为空。现在应表述为“447条controller匹配，加1条由worker文件支持的缺字段例外”，
不能把原清单改写成448条全部一致。缺字段的具体产生原因未证实，原hold和原lineage不修改。

配置记录的launch日期在这个例子中也不等于worker实际开始日期，不能据此静默改run key、时间序或已有切分。
此前两条仅目录匹配的候选，实际属于不同日期的launcher实例，snapshot和step也不同；
目录复用不能证明同一实例，现有保守组件已包含相关关联，未新增绑定或释放hold。

独立重读源码：`eabf24ade438384f0407dd680d6154192cb97e74`；
SHA `2ae85cfd9c381c88c6166833747cabbb12a5c60b69f8bab046c3ae978fa2ae28`。
原始聚合回执和独立回执分别见本目录`historical-worker-identity-triage-20260906.json`、
`historical-worker-identity-independent-20260906.json`，没有原始身份值、日志或凭据。

## 实际尝试过、但没有补到的证据

按执行前固定规则，在结构较完整的84run上，只检查manifest最后attempt明确绑定的日志前缀。
没有换子集、改尝试次数或放宽未知前缀规则。

|项目|实际结果|
|---|---:|
|固定历史run|84|
|固定archive SHA|24|
|stdout/stderr前缀|168|
|遇首个未知前缀即停|168|
|完整模块来源记录|0|
|单文件最大读取字节|349|
|CPU A/B实际耗时（秒）|61 / 61|
|该84run需要的snapshot|24|
|本机无权限 / 不存在|8 / 16|

A/B私有投影、逐归档记录及原summary逐字节一致；独立实现重新推导84范围和最新attempt绑定，
复核计数、读取上限和哈希。独立验算没有重新解析原始日志，不能称为第二套raw-log抽取器。
该路径不能为实际generator/evaluator版本提供证据；不因零覆盖而事后扫描更深日志。

### 一处明确勘误

79164e0原summary包含`task_phase_log_reads=0`。**它不成立为字节级保证**：首个未知行已被读入，
可能是任务阶段内容。确切保证只到“首个未知行或任务边界即停止，不解析成绩、不输出原文”。
原summary原封保留，独立回执显式拒绝零字节解释；eabf24a只修正以后源码的字段/说明，未重新扫描这84run。
归档流式解压和文件open轨迹也都不能证明tar成员的零字节读取或OS级隔离。

## 文件访问、复现与失败记录

- 实跑代码 `79164e047b46f7d76db38a89407d1b008c19221a`，主文件SHA
  `8cb3ae6db049bfdd550ebfeb087934c3b2ad373efff61f20236c1726be266624`。
  固定5文件bundle SHA `1e301af024cc3e56eab29d116162ebe69a3a710c82a47598edd8540fe6676d01`；
  导出时显式关闭autocrlf，并逐文件与Git blob精确比对，不再靠归一化等价代替字节一致。
- `prefix/`保留原summary、独立summary、真实命令/时间、逐leg CSV及public manifest。
  private投影SHA `fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b`。
  A/B目录均远端500、文件400；私有路径/记录未上传Git。
- open/openat初次核查9b908d6退出1：每leg有25次未分类访问。原因是C八进制转义被按Unicode字符而非UTF-8字节解码，
  另遗漏控制目录本身。失败回执保留，未改原trace、输入或实验结果。
- 5f9f43c本地测试31通过、1失败：Windows文件系统解码对非UTF-8字节与Linux不一致。
  此版本未执行远端核查。767e351显式采用Linux UTF-8/surrogateescape语义，随后32项测试通过。
- 最终trace核查源码 `767e351b2218b9e81637e773fd0a3ea0ed6c7e62`，SHA
  `84fa2e39ab9f49d3bd19826f4a3b1cd3e7078500975eb724f35be2f9a0dd01e8`。
  A/B各24个固定archive路径、96次archive open；无未分类成功open或意外写入项。
  这是观测到的open/openat检查，不是操作系统隔离证书；旧失败和v2回执同时保存。
- 本轮0新GPU、0付费API、0模型fit，未运行Cards/G/L真实构建，未读取保护cohort。

## 对下一步意味着什么

不再需要学长解释那1条Slurm缺字段，也不需要重传676run的语料或手填launcher映射。
最小补证优先缩至固定84run对应的24份实际snapshot，以及当时实际MLE-bench环境/外部评分记录；
“16个本机不存在”不等于在其它生产机或备份中已丢失。另需确认真实experiment跨launcher联系和历史开发资格。
README的版本pin仍只是安装recipe，不能替代执行事实。

资格补齐后，我们可用不可变输入做一次新的同版本Cards/G/L构建，保留旧hold，记录真实命令和产物SHA；
不必补造旧构建命令。在此之前，84run不能称为合格训练包，更不能声称已有G-reuse或scaling收益。

01:22只读查询：GPU12535仍PENDING/Resources、0秒；当前集群所见PRO6000仅projgpu39，
此前排程暂估9月6日19:38:15，非保证，没有同型号空闲替代节点。旧G0通过与本次consumer恢复验收是两件事。
学长head本轮fetch仍`b8d095180415957aa1bab31fa53ead1bba261c03`；0904六份新归档已接收，
最早03:44:48满足年龄，当前未提前摄取。完整主线与冻结评测门保持不变。
