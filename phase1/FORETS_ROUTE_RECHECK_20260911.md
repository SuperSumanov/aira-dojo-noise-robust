# 固定免费路由的单次额外检查窗口

2026-09-11，用户要求继续推进。保留上一窗口NOT_READY（6尝试、5超时、1/2逻辑请求成功），
不覆盖它，也不据此提交GPU。当前生产code仍为5c8c07b711e7d3846fc5eda978f1efd6cd0b64ea。

本轮仅新增一次、最多2次生成尝试（两个公开人工输入，各只尝试一次），每次仍120秒/8192输出token，
Nemotron免费模型、tools、禁fallback、原实际config与transport不变。这是原6次以外的明确额外窗口，
不是把原预算写成未用完。两次均匹配才发布新READY；失败不循环重试。不申请GPU用于此检查。
独立脚本先锁定新窗口，检查原失败回执SHA、当前代码/config、凭据与免费目录，再调用既有检查器。
只发布安全摘要，凭据仅远端环境；两次通过仅是启动可行性证据，不能保证长时可靠性。

公开端点元数据依然列出免费Nemotron与工具支持，近期可用率波动；不足以确定此次超时根因。
源代码中120秒为整次请求的明确墙钟限制，不是把默认1500秒误当实际限时。
不通过缩短输出、关闭reasoning或换模型让检查变容易；这些都将改变生成工作负载，不能冒充同一配置已恢复。

若通过：执行原固定8-run协议的第一块，仍两块顺序、相同硬件/原镜像、19GPUh总上限，不重复G0。
实际结果与作业号待执行后记录；本文件不代表已运行或正收益。

实际额外窗口：08:37:44 UTC开始，两个请求均120秒超时，0/2成功；NOT_READY，无GPU、无生产runtime。
新finished SHA=21bb4857cf01c8fe07de97af2de3e9f248f2f93e2b1d5768140195df9507d3b6。
不再继续同配置重试。代码检查确认这不是GPU问题；目录访问/账户认证通过不能证明生成通路稳定。

接着只检查学长已明确推荐的另一个免费client：poolside/laguna-s-2.1:free。
独立人工可行性窗口最多2次请求、无重试、仍120秒/8192token；原配置仅在内存改model并去掉未声明支持的top_p。
保留tools、temperature、零价格筛选、禁fallback与实际bounded transport；不修改任何原8份配置或release。
结果即使通过也只写FEASIBLE_NOT_RELEASED，不能作为Nemotron READY；更换生产生成器须明确建立新版本并让两臂一致。
这不是选择效果最好的模型，不读取任务成绩；只是停止对故障免费接口的无限等待。

## 实际结果与收尾（08:51:14 UTC）

| 独立检查 | 尝试 | 有效生成 | 观察结果 |
|---|---:|---:|---|
| 原Nemotron配置额外窗口 | 2 | 0 | 两次120秒超时 |
| Laguna、去掉top_p、仍指定函数 | 2 | 0 | 两次404 |
| Laguna、去掉top_p、显式auto工具 | 2 | 0 | 两次429 |

本轮共6次额外人工生成尝试、零GPU/真实MLE；加上上轮6次共12次，但分别保留窗口，不合成伪成功率。
所有窗口均NOT_READY，API实际用量/账单不完整，费用仍未知。不再无界重试，不改限流/隐私/价格筛选或转付费。
08:51:14 UTC队列仍仅12535 held；原block-1.route.json与block-1.runtime都不存在。

### 确切兼容性发现与修复

官方[模型端点信息接口](https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints)的现场读数：
Laguna工具模式支持auto=true、required=false、function=false，同时不声明top_p支持。
这比仅看supported_parameters含tools/tool_choice更细；初检漏查强制指定函数能力，两个404不可写成“模型不存在”。
去掉top_p后仍404，随后仅改变工具选择为auto得到429；与强制函数不兼容的判断相符，
但请求发生在不同时刻、429可能来自账户或上游，**不能称已唯一确定404根因或证明生成可用**。
没有读取429原始响应，限流层级与重置时间未知，不能猜是余额不足/日限额或擅自改账户设置。

补丁0019只增加bounded_tool_choice_mode=auto的显式选项，默认named不变；非tools/无schema/非bounded拒绝。
实际JSON解析、函数名、schema验证保持原样；无工具响应不能视为有效候选，无文本fallback。
8项新增CPU检查通过；首次测试夹具缺类型别名导致8个setup error，补齐夹具后8项通过，不称两轮16项。
真实auto检查是在独立source副本上执行；后端SHA=5cf4f2d5ce1190e1f758137f0468c4eb6b09625b260dc95f037b4ecd9377ed9f。
它未接入生产、未放行8run、未改学长分支；源package与现成模型均不改。

### 证据与下一项真正依赖

安全摘要在results/forets_route_recheck_20260911/：
- nemotron.json：21bb4857cf01c8fe07de97af2de3e9f248f2f93e2b1d5768140195df9507d3b6。
- laguna-named.json：4b8bf0af4c6aa597828f4dc369b5c6d6176344a65e823185f0d53e2843a82e86。
- laguna-auto.json：a332ff7bd510f8141f50639b7af1eea4a719aa23e6f8f212fb2347635ea79152。

若免费入口恢复，需重新明确有界检查窗口，不能重用失败目录、加长超时或更换模型假冒旧READY。
更实际的解阻是学长/用户提供稳定生成入口及可用的本轮费用上限（只需平台/模型/预算，不再发密钥）。
若改变生成器，以新版本让两臂共同固定；不在未获明确费用范围时启用收费fallback。
当前没有新的critic最终成绩/干净scaling正结论；13004原负向探索结果不变。
