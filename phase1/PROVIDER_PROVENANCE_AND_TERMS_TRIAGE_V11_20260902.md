# Decision Corpus v11 provider provenance and terms triage（2026-09-02）

> 状态：`PARTIAL_NOT_RELEASE_CLEARED`。这是发布治理盘点，不是法律意见，也不是新的科学证据。

## 1. 先把 generator/model 与 service-provider/contract 分轴，再谈条款

v11 的权威范围是 29 个不可变 batch、16,012 行。metadata-only producer 与不导入 producer 的 verifier
分别重算 release batch lock、ordered manifest、generator annotation 唯一映射、rows/bytes 与四个输入 hash，结果逐项一致；
两者都没有打开 card payload，也没有读取 label、prediction 或 prospective resource。

| provenance 轴 | batches | rows | v11 rows 占比 |
|---|---:|---:|---:|
| configured model ID 已恢复 | 29 | 16,012 | 100.000000% |
| exact version-or-configured-model | 28 | 15,905 | 99.331751% |
| server-side version boundary 不确定 | 1 | 107 | 0.668249% |
| 映射到 provider family | 24 | 9,901 | 61.834874% |
| service provider / contract entity unresolved | 5 | 6,111 | 38.165126% |

原 inventory 中未映射的五批是 `cards_senior_0805seq.jsonl`、`cards_senior_0808.jsonl`、
`cards_senior_0809.jsonl`、`cards_senior_0810.jsonl`、`cards_senior_0811.jsonl`。现在已从它们各自的原始 archive
内精确 `dojo_config` 恢复 6,111/6,111 行 configured model ID：`deepseek-v4-flash` 1,429、`gpt-5.4-nano`
1,737、`gpt-5.6-luna` 159、`minimax/minimax-m3` 990、`moonshotai/kimi-k2.5` 323、
`qwen3.5-397b-a17b` 466、`tencent/hy3-preview` 62、`z-ai/glm-5` 945。该证据不推断调用所经 service provider、
base URL family、账号区域或 contract entity；模型厂商名也不能替代服务合同证据。

archived recovery 的正式 r6 通过 focused/full=`4/2,047 passed`，completion composition 通过
`5/2,068 passed`，两者均有 producer/verifier A/B 与独立 postflight byte-exact 重建。原 inventory / verifier SHA-256=
`88df63ed...b550a` / `66459ae...62f5b`；completion / verification SHA-256=
`3ba20307...ffc391` / `235e4c90...0f412`。公开证据见
`phase1/results/release_provider_provenance_v11_20260902/`、
`phase1/archived_generator_provenance_postflight_receipt_20260902.json` 与
`phase1/generator_provenance_completion_postflight_receipt_20260902.json`。

## 2. 已映射 provider 的官方条款初筛

### DeepSeek：22 batches / 9,857 rows

DeepSeek Open Platform 的 API 专用条款于 2026-04-29 生效，覆盖后续 7--8 月采集窗口。条款把服务输出中
DeepSeek 持有的权利（如有）转让给用户，并明确列出学术研究、衍生产品开发等使用场景；同时把输入权利、输出合法性和
第三方不侵权责任留给用户。官方入口：
[DeepSeek API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html)。

这只把 DeepSeek 自身对 Output 的权利障碍降为较低风险，**不**解决 Kaggle competition data、第三方代码、输出可版权性、
AI 标识义务或拟用 Apache-2.0/CC-BY-4.0 对所有下游用途授权的问题。因此状态仍是
`PARTIAL_REQUIRES_INSTITUTIONAL_LEGAL_REVIEW`，不能写成“DeepSeek rows 已许可发布”。其中 107 行还存在
v1/v2 静默切换边界，虽然 provider family 已知，但模型版本不可精确归因。

### Qwen / 阿里云百炼：2 batches / 44 rows

现有 annotation 只记录 `qwen3-coder-flash`，没有记录调用账号所属区域、签约主体或当时接受的协议版本。当前中国大陆
[阿里云百炼服务协议](https://terms.alicdn.com/legal-agreement/terms/common_platform_service/20230728213935489/20230728213935489.html)
显示生效日为 2026-09-02，晚于 Git 可验证的 2026-08-04--08-07 collection window，因而不能反向证明采集时权利。
当前文本虽说明在输入权利合法时合成内容知识产权原则上仍归用户，但也禁止未经许可用服务/模型输出训练或开发与平台竞争的
产品，并把第三方权利风险留给用户。国际版
[Model Studio product terms](https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-product-terms-of-service-v-3-8-0)
同样不自动解决历史账号区域与合同版本。

因此 Qwen 44 行当前状态是 `BLOCKED_CONTRACT_ENTITY_AND_COLLECTION_TIME_TERMS`。需要账号订单/控制台协议回执或当时的
条款快照；不能用今天的网页替代，也不能先假定 CC-BY-4.0 与“不得训练竞争产品”的合同限制兼容。

## 3. 关闭 gate 的最小动作

1. 学长为五个 provider-unresolved batch 提供**不含密钥**的 service provider/base URL family/collection-time
   account-region/contract entity 元数据；configured model ID 已精确恢复，不再要求按记忆回填 model。若无原始日志，
   provider/contract 轴保持 unknown，不按日期或模型名推断。
2. 对 Qwen 两批提供 2026-08-04--08-07 当时的签约主体、账号区域与已接受协议版本/订单回执；先做 credential-shape
   scan，再只提取非敏感 metadata。
3. 机构/法律 review 分别裁决：DeepSeek 输出条款、阿里云历史条款、Kaggle task 规则与最终数据许可之间是否兼容；
   `licenses.json` 必须逐 batch 绑定 provider 状态，不能只写一个全局 license。
4. 若证据无法找回，release candidate 必须把 provider-unknown / contract-unknown rows 单列为 withheld tier，不能以
   “大概率是某 provider”发布。

## 4. 明确不证明

- 不证明任何生成代码具有版权或不侵犯第三方权利；
- 不证明 Apache-2.0、CC-BY-4.0 或其他最终 license 已获授权；
- 不证明当前网页条款追溯适用于历史调用；
- 不把 configured model ID 当作 server-side version、service provider、账号区域或 contract entity；
- 不读取或评价 predictor accuracy、search utility 或 prospective outcome；
- 不计入 Evidence Index 的 distinct scientific claims。
