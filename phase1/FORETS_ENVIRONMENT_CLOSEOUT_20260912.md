# 共同环境修复四run收尾：运行性出现非零，但尚无可比最终解

2026-09-12香港；独立关闭观察2026-09-11 21:14:16 UTC。不是方法收益报告。

实际作业13113于gpu28结束（allocation FAILED、1932秒），用量1.0733333333333333 GPUh。
controller=dfad1bba2171b62f6d476129e661de66d3c4801b，source tree=0a587f6b220b1aa0bd154f537f36594bc0690cb3。
两任务、新seed10、两selector均保留；同原镜像/300秒/6步，未重跑失败槽位或改正在执行的配置。

|任务|臂|worker|实际程序执行|exit0|有效最终解|
|---|---|---|---:|---:|---:|
|leaf|random|completed|5|1|0|
|leaf|critic|failed|0|0|0|
|spaceship|critic|completed|5|0|0|
|spaceship|random|failed|4|1|0|

共25个已生成候选、14次程序执行，2次exit0，12次非零退出；最终0/4有效、0/2可比成绩对。
程序错误分类：2超时、6其他代码错误、1LightGBM参数、1实验性导入、2categorical赋值。
这不是“critic打平”，也不证明全部critic无用。exit0不保证submission有效或最终选择成功。

## 真实阻塞

1. leaf/critic在生成期间ReadError，保留一次0.70USD未知费用预留；之后预留无法满足该run上限而拒绝请求。
   此run未执行候选，不归因critic筛选质量。spaceship/random后来也触发预算保护，未补跑。
2. 日志按attempt_id去重后有13次response_invalid/ValidationError，均已有真实费用回执。
   对应分析阶段的异常；源码将分析异常回退为is_bug=True，即使程序exit0也可能被排除。
   原始失败响应未保存，当前无法断言是哪个字段；不补造历史响应、不从中途分数挽救final。
3. 日志会重复打印同一事件。BudgetStopped未进收费calls表的尝试不算实际API调用；
   运行时unresolved还会包含在途请求，终态才只剩一个未知项。

本轮48实际API调用（含2路由检查），已结算0.102788283USD；连同前124次共172次，
累计已结算0.421563831USD，另有一次0.70USD保守预留、费用未知。不能把未知计零或说总费用已确定。
旧两块实际3.2583333333333333GPUh另计；旧8失败不覆盖。本次整块终态后才统一读出final。

## 零GPU后续诊断边界

最多两次人工analyzer示例（成功/失败各一），原分析提示、原schema、同收费模型，单次尝试、禁止重试。
只捕获校验字段路径/类型，不导出响应文本，不访问任务数据或保护集，不回填旧run。
API新增责任上限0.75USD，连同旧已结算费用与未知预留累计，仍受原100人民币/10USD上限。
旧ledger仅停止追加，calls逐行复制含未知预留；新诊断不能向旧scope继续派发。
两个人工示例离线通过；预算/脱敏测试首次因Windows连接句柄未关闭失败，补显式close后3项通过。
真实接口诊断仍需其独立回执，不能以mock宣称线上修好。

## 后续实际诊断与修复（不回写上表）

原人工成功/失败两例均在metric:string处失败；v1只做合法JSON数字/null字符串恢复，成功例过、失败例仍拒绝。
v2增加明确is_bug=True时文本metric置null，不能把坏节点变好；两个真实人工示例均被接纳，期望语义均匹配。
其他字段仍严格校验；未明确失败时百分号、布尔、非有限数、说明文字仍拒绝。
三轮共6实际API，无新增GPU；最新累计已结算0.422344104USD、旧0.70USD未知责任仍在。
诊断最初凭据映射在client构造后才设置，零真实请求，修复后仅执行原两次；
v1首个生产方法加载因class内类型别名缺失而在任何请求前失败，离线复现修复后再执行。
这些前置失败没有删除，也没有重新请求用户密钥。

journal实际存储的外部分数信息位于metric_info，而非嵌套metric.info；依正确字段复验：
两个exit0节点均外部submission_exists=1.0、valid_submission=1.0、有限分数，但analysis空、is_buggy=True。
这是接纳缺陷的实证，不是允许我们补写final或声称critic收益。接下来另用seed11四run验证。

回执：[原接口](results/forets_environment_20260912/analyzer-original.json)、
[v1未全过](results/forets_environment_20260912/analyzer-compat-v1.json)、
[v2人工示例通过](results/forets_environment_20260912/analyzer-compat-v2.json)。

证据：[结构与费用回执](results/forets_environment_20260912/diagnostics.json)、
[固定四run主表](results/forets_environment_20260912/final-readout/runs.csv)。
