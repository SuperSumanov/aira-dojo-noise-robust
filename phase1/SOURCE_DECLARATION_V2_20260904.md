# 来源声明v2：两种日期分开，header证明与执行证明分开

这是 Global→Local 来源解锁的验收修复，不是新效果实验，也不是重开旧S0。
旧`validate_senior_source_provenance_manifest.py`和其10项测试不改，旧S0=IDENTITY_UNAVAILABLE保持。

## 为什么新增v2

旧v1要求run ID的启动日期、source_date、归档目录MMDD三者相等。但原2026-08-21审计明确指出：
run后缀是启动日期，不是权威归档目录日期。对已有676行header-only映射重新做日期结构检查：
636个unique来源中537同日、99异日；source目录日减launch日为-1的73个、+1的26个。
输入SHA=`60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d`。
不打开归档payload、Cards、pairs或前瞻值；未重跑原S0、未重选来源。差异可能涉及打包跨日、目录约定或时区，
本轮没有核实具体成因。不能把这99个记录算成新增已恢复physical runs；它们原本已有唯一header来源。

## 交付字段（每个run一行，按run_id排序，exact schema）

| 字段 | 含义与检查 |
|---|---|
| run_id、task | 精确对应预先绑定的历史run manifest，不能多或少 |
| launch_date | ISO日期，等于run ID后缀；不是从source目录推断 |
| source_date | 声明的归档目录日期；MMDD匹配archive_path首层，**不要求等于launch_date** |
| archive_path、archive_sha256 | 根目录内的明确相对归档路径与完整SHA；前后重验，拒绝link/traversal |
| batch_id | producer声明的实际batch目录，不用family/date/config代理填补 |
| journal_member | 完整、明确的tar member路径；首层为batch_id，尾部为源run/checkpoint/journal.jsonl |
| producer_commit | 声明的40-hex执行代码版本；格式通过不等于执行已被证实 |
| producer_instance_id | producer导出的唯一实例ID；不能临时用日期或run名哈希伪造，不允许多个run复用 |

已有七字段基础上增加launch_date、journal_member、producer_instance_id。同basename存在多处归档时，
必须由维护者给出权威实例/路径，不由我们按日期接近、分数或文件先后挑选。对于missing或坏归档，仍需真实替代来源。

新入口：`python -m phase1.validate_senior_source_provenance_v2 --expected-runs ... --expect-runs-sha256 ...
--provenance-manifest ... --expect-provenance-sha256 ... --source-root ... --output ...`。
输入schema/重复JSON key/覆盖/实例冲突/journal复用/错误哈希/缺失或重复header/链接/路径穿越均拒绝。
只扫描headers，不调用extractfile/extract/extractall；不解析journal里的标签、分数、代码或凭据。

## 不会替学长“证明”的东西

成功状态故意写为`HEADER_BACKED_DECLARATION_ONLY_NOT_EFFECT_ELIGIBLE`。
它只证明声明的路径确实有唯一header且文件哈希一致；不能证明producer_instance_id确实代表独立执行、
producer_commit被实际执行、source_date年份/实际时间属实，或config真实、split是experiment-closed。
这些必须由producer侧执行回执补齐；任意40位字符串不是代码执行证明。未引用的归档也没有被本检查器审计。

因此旧32个歧义run、8个缺失run、2个archive errors仍未解决；当前Global→Local候选中的19/6亦未自动修复。
新v2不会生成训练池、过滤pair或开启模型fit，原冻结v2与历史开发v1保持原字节。
本轮先公开报告真实日期诊断，再验证独立新声明接口；并非未见结构结果的全新预注册S0。
