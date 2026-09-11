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

实施中。尚无收费接口真实回执、GPU提交或新效果结果。
CPU验证只针对费用保护/传输接线，不是模型或MLE有效性结论。
沿用13076的gpu28原SIF兼容证据；现成critic历史模板未知继续披露，不调模板，不称干净scaling。
