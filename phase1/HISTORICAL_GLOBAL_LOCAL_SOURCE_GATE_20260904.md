# 历史 Global→Local 来源适用性诊断（事前固定）

本轮问题：已知的9392对G候选与4689对L训练对，在旧的真实批次身份回执上还有哪些确定的来源缺口？
这是现有证据的适用性检查，不是重跑20260821失败的S0，不解锁或重新选择其子集，也不创建训练池。

固定输入：历史L/G train、92a9651 grouped Cards，以及a466888-v3既有run_batch_manifest。
五个输入逐一SHA锁定、读取前凭据形状扫描、读取后再次SHA复验。批次文件SHA为
`60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d`，上游manifest SHA为
`e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92`。

只投影历史train unordered endpoints、card的id/run/task及client/hardware/time_limit/execution_timeout，
既有批次表只用身份状态及批次hash。不输出身份或配置值，不检查code/grade/gap/outcome。
grouped JSON容器仍须解析，不把“字段未使用”写成“结果字节从未进入解析器”。不打开dev/test/vault或归档成员。

固定统计（不得依结果改定义）：

- 分别报告L/G全部候选的配置相等/不等/缺失、source unique/ambiguous/missing及受影响pair数量。
- G的跨批次对只作描述，不假定全局比较必须同批次；card配置相等也不当作实际producer配置证据。
- 用整个旧676-run结构集合检查L-train批次与其外部的共享。外部可能是未使用run，**不等于dev/test**；
  这项诊断不能单独证明实际train-test泄漏，也不能证明完整experiment-closed划分。
- 来源缺失不丢弃、不猜日期或task代理、不重新分配train/dev。旧S0失败仍有效。

执行前检查：新生产器与不导入它的set-based独立验证器，局部11项测试通过；固定候选重复立即拒绝。
单进程CPU，生产A/B和独立验证A/B各最多180秒，数学线程1，不安装依赖；GPU/API/model-fit=0。
无学习seed、warmup或accuracy调参，elapsed只记实际成本，不称性能基准。新独占/tmp输出，逐阶段记录rc，
输出限定为结构JSON/CSV，源码与输入前后验hash。冻结v2和现有G0 12288完全不变。

本轮检索曾误把文件名glob扩到旧cards JSONL，产生过量旧语料输出；没有用其code或结果作判断。
后续检索已改为显式源码/报告路径，不再对语料目录做宽泛内容搜索；不声称本轮从未读到旧cards内容。
此事不改变前瞻盲态授权，新的诊断进程仍以精确文件白名单约束。

实际结果待追加；不是新正效果、clean scaling或确认性证据。
