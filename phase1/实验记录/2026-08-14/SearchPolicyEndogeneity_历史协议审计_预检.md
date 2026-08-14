# Search-policy historical contract audit：13 项运行前预检

协议：`search_policy_contract_audit_v1`。虽然预计 CPU 流式审计低于 15 分钟，仍按长实验同等级执行。
launcher 只有逐项 PASS 才可开始正式 producer；任何 preflight 失败不得写成科学 `NO_EFFECT`。

1. **方向/产物**：当前主线仍是 run-clean、decision-local MLE search-tree dataset/benchmark；本轮只审计
   historical search-policy label endogeneity，不恢复 HCE、多保真、probe 或底座微调。预注册、producer、
   independent artifact verifier、tests、正式命令和结果目录全部固定到同一 commit。
2. **cheap tests**：producer/verifier `py_compile`；tar path/type、credential-before-parse、config contract、
   parent/children graph、balanced/concentrated metric、incomplete-root coverage 与 contract matching 单测全过；
   prospective intake/accumulator/scorer 回归测试同时通过。
3. **入口/allowlist**：正式命令只接受显式 `(arm,batch,dir)` 清单和新 output root；MCTS 固定为
   0802/0803/0804 三个 batch，sequential 固定为 0805 一个 batch。代码只对
   `dojo_config.json`、`checkpoint/journal.jsonl` 调用 `extractfile`，禁止 env/log/HTML/workspace/submission/
   grading/frozen/test/held 输入。
4. **输入分布**：运行前 metadata inventory 必须恰为 MCTS 14 个 tar、sequential 8 个 tar；身份固定为
   `(arm,batch,archive basename,SHA-256)`，避免跨日期同名 tar 碰撞。每个 tar 先固定 bytes + SHA-256，
   重复字节 fail closed。physical-run 数不在 outcome 前猜测，按 checkpoint-journal SHA
   唯一计数并完整报告。
5. **平衡/前瞻规则**：只比较共有任务；结构支持门固定为每臂至少 20 physical runs、每臂 journal coverage
   至少 80%、至少 2 个共有任务、至少一个共有任务每臂 4 runs。任务不因结构方向或区间删除。
6. **checkpoint/resume**：预期低于 wall cap，不做语义 resume；input manifest 先写 staging，全部产物完成后
   parent 原子 rename。正式和 staging root 均不得预先存在；中断 staging 不能当正式结果。
7. **泄漏/结论**：不读取 grade/metric outcome，不写代码、prompt 或 term output；结构差异不得宣称 critic
   accuracy/utility。contract 任一关键字段不同就固定降级为 descriptive-only，不能看结果后豁免字段。
8. **RNG/数值**：bootstrap seed=20260814、10,000 replicates；每个 run 的概率和 concentration 指标 finite；
   eligibility、node accounting、HHI/entropy/effective branches/Gini 由合成树精确测试。
9. **密钥**：allowlisted payload 在 JSON parse 前扫描；env member 永不读取；正式前和 push 前 staged filename
   与高置信内容 secret scan 都必须为 0；不读取远端 `.env`，0 API。
10. **wall-clock smoke**：真实单个 0802 与 0805 tar 已通过仅 schema/contract 的安全 smoke；正式 producer
    wall cap 1,800 秒，verifier 1,800 秒。超时只诊断 I/O，不增加输入、资源或改阈值。
11. **推断/停止**：主门先看 exact contract，不看结构方向；非随机 historical collection 的 bootstrap 只作
    描述性不确定度。旧 fragment 两任务结果与已见 nomad 配置差异明确记录为 prior knowledge。
12. **真实退出码**：producer 和 verifier 的 rc 在各命令后立即保存；`tee`、hash、archive 等后续命令不能覆盖。
    timeout/exception 为 `INVALID`，不是 contract kill 或无效应。
13. **append-only/hashes**：正式 root 新建；input、source、prereg、run CSV、catalog、summary、metadata 与
    archive audit 全进 SHA manifest。verifier 独立重哈希输入/产物并重算 inventory、contract、support、task
    medians、macro difference 和 deterministic bootstrap CI。

资源上限：1 CPU process，0 GPU、0 API、0 LLM 权重更新；MCTS 14 archives + sequential 8 archives；
producer/verifier 各 1,800 秒 cap。预计总墙钟 5–15 分钟。
