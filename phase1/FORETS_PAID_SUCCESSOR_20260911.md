# 2026-09-11：100元上限的同预算端到端新版本

用户明确批准本轮生成API总计100人民币，包含连通性检查、失败、重试及实际生成，不购买额度。
沿已批准两任务×seed8/9×两臂、8run / 两块19 GPUh上限继续；不扩GPU预算，不重复G0或验收。
旧免费窗口与配置保留。新生成器固定 `qwen/qwen3-coder-flash` / OpenRouter / Alibaba。
两臂共同改变生成器和收费保护，仍只以选择方式作为研究变量；不可与旧Nemotron结果当作同分布重复合并。

## 费用与运行契约

- 全campaign单账本10 USD：接口检查共享1.20 USD，8run各1.10 USD，不能互相借额。
- 按8人民币/USD再加10%费用余量计88元，另留12元。不声称实际外汇结算已确定。
- 每次传输先持久化预留0.70 USD，覆盖端点百万token上下文、最高缓存写入档0.65/M及8192输出×2.6/M。
  API侧固定only Alibaba、无fallback，max_price输入0.65/输出2.6/每请求0；不加插件、图像或缓存指令。
- 返回后只按OpenRouter原始 `usage.cost` 核销。未知、超时、中断保留全部预留；缺账单/超界停止，不补零。
- 每worker的收费传输串行，避免四候选同时预留超过该run额度；候选生成/选择算法不改。
  每次真正传输仍120秒，排队受既有3540秒worker总时限约束；两臂完全相同。保留100尝试/8192输出上限。
- 保留失败、预算截断和未启动槽位；最终选中程序的外部成绩才是指标，不取历史最大分。

端点价格：<https://openrouter.ai/api/v1/models/qwen/qwen3-coder-flash/endpoints>。
计费字段：<https://openrouter.ai/docs/cookbook/administration/usage-accounting>。
路由约束：<https://openrouter.ai/docs/guides/routing/provider-selection>。
中国银行2026-09-11美元卖出参考672.5人民币/100USD：<https://www.boc.cn/sourcedb/whpj/>。
实际费用上限使用更保守折算，并非对账户余额或到账费用的披露。

## 当前状态

11:01 UTC：两块实际静态配置检查通过，8份RunConfig往返、4对唯一selector差异通过；
7项费用边界测试在本地和远端通过。真实入口两个人工指定函数调用均成功，分别1.724104883032851秒、
1.2292241620016284秒；原始账单合计0.000113724 USD，2调用、0未结项。
CPU/人工接口检查不是MLE有效性或critic收益结论。
沿用13076的gpu28原SIF兼容证据；现成critic历史模板未知继续披露，不调模板，不称干净scaling。

生产根：`/research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8`。
代码commit：`f051cfded55259d5320407a9e0269ab9141ab345`，组合源码tree：`f9087ae47470f7f1868c61405c3b827327f31c2c`。
prepared SHA：`58558eed5abe1f793c77049572549c66de8c104255f8a13fa3c48e0a8b4d3593`。
source inventory SHA：`6857f18c60fecaa745710960c0f2f9dfd50d485717ca8a7e86faa47dedc10c1b`。
release SHA：`819621d75c9c95efe1e337866884b8701ad5f3f71cf5ea7e849f2b6ab0dd8798`。
26份控制器文件从5c8c07b的22份旧代码按明确根目录/hash/付费入口/worker费用变量机械派生，
不是声称26份原样存在于f051cfde；code-manifest保留逐文件派生前后SHA，构建器可重建。
新源代码仅两个目录src/aira_core与src/dojo，共233文件；首试误打包整tree触发无效LFS对象404，
未获得数据，停止并改回原来的代码白名单；移除的只是本次生成的不完整诊断tar。旧包与数据不改。

## 提交前13项清单的适用性

1. 实际8配置全4算子均Qwen3 Coder Flash/paid guard；禁用env dump、wandb及use_test_score，6步、width4、300秒成立。
2. 新边界本地+Linux测试；真实GenericLLM指定函数两次通过，同代码含paid ledger和严格工具解析。
3/7/13. 本轮无训练/切分/扩语料；冻结保护集不访问，不复用其标签，不变更旧分配。
4/5. 固定两个任务、每个双seed，最终逐任务/逐seed报告；四对不足以声称普遍收益或确认scaling。
6. 现成权重不训练，不产生新checkpoint；候选/轨迹/失败及最终选择产物按原logger保留。
8. common_priority_v1、任务/seed/顺序与原8矩阵不动；收费串行不消耗选择RNG。
9. 仅远端既有.env载入，输出白名单，发布前逐文件凭据扫描；不公布私有账户余额。
10. 原每块280分钟/双卡、KillWait实查300秒，两块总上限19GPUh；原worker3540秒、step60分钟。
11. 小规模现成系统探索，历史训练模板未知，不声称统计高功效或干净scaling。
12. Python显式检查每个returncode；新receipt/ledger/启动记录只写新文件，不能用失败回执放行。

11:01:05.970998 UTC 队列仅12535 held（不干预），gpu28 idle。研究文件系统free35224858656768字节，
此为文件系统余量，不冒充用户配额；本轮无大checkpoint写入。收费API已放行，GPU尚未提交时记录本节。

## 实际启动

第一块实际作业 **13088**，2026-09-11 11:02:18 UTC观察RUNNING/gpu28，已用23秒、上限4:40。
控制器started.json记录11:01:58.232757UTC，code commit f051cfde；启动的是固定seed8的四run，非训练/G0。
第二块seed9未提交；两块须依次运行避免服务端口冲突，并共用同一paid.sqlite。此时尚无新效果结论。

11:07:27.950776 UTC：现成critic在单张RTX3090、16K、BF16就绪（加载215.88420586613938秒）。
leaf/seed8/random进入真实worker13088.1，原SIF native-binding回执已存在；其它三项pending。
任务生成实际派发4次，其中3次已结算、1次尚在进行；加接口检查共6次，已结算0.006374277 USD，
另持有0.70 USD预留，预留不是实际扣费。无完整配对效果结果。
独立旧新配置差异核对只见40处机械路径、32处共同模型、32个费用开关、64个价格字段，
并逐一验证32个only Alibaba限制；任务/seed/算子prompt/selector/critic/镜像/预算均未额外改动。
