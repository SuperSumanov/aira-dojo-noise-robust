# Senior config-provenance overlay：交付与边界

日期：2026-08-23。状态：`CONTRACT_IMPLEMENTED_REAL_MANIFEST_PENDING`。本轮只补 S0 metadata
阻断，没有读取 future truth/真实 archive payload/Cards/pairs，没有调用 API/GPU，也没有训练或更新底座模型。

## 为什么不是再造一套 provenance

既有 source manifest 已绑定 run→archive path/SHA、batch、producer commit；既有 exact-stratum 补丁已按
`(task, client, hardware, time_limit, execution_timeout)` 配对并在 pair 写 stratum/batch receipt。真正缺的是
两者之间一个**结果前、credential-safe、可公开分析的 run→config 映射**。因此本轮只增加 overlay：

- 不重复 archive/header 扫描；要求输入一个既有 `PROVENANCE_VERIFIED` source receipt；
- 独立重算 source mapping SHA，防止拿另一批 source receipt 拼接；
- config manifest 对 expected runs 精确全覆盖，并逐 run 重算与 pair producer 字节兼容的 stratum SHA；
- `client` 是 producer Cards 使用的公开 model ID，`generator_release` 必须在 outcome 前声明；
- server-side release 不可知时写 `unknown`，保留诚实 provenance，但禁止 interaction claim。

这消除了“只有 stratum hash、却无法解释 generator/client”的机器接口缺口，同时不改变现有 33/300 score-channel
协议。它是未来 clean capability×generator 设计的必要条件，不是结果本身。

## 攻击面与验证

11 个新增测试覆盖：确定性 join、unknown release/client 降级、stratum 篡改、漏 run、task 错配、source receipt
mapping 篡改、凭据形状、非法公开标识/非正 timeout、额外字段/乱序、不可覆盖 receipt，以及 input/output symlink
攻击。与既有 source provenance 测试合跑为 `21 passed in 0.18s`；远端完整 `phase1/tests` 为
`809 passed, 33 warnings in 51.65s`。文件名/内容凭据扫描均为 0。

首次 full suite 因未固定数值库线程，在登录节点展开约 30 个线程；约 17% 时主动中止并保留日志，不算通过。固定
OMP/OpenBLAS/MKL/NumExpr=1 后从头重跑全套，得到上述 808/808。这个过程按失败日志如实记录，未删除或美化。

三个核心文件 SHA-256：

- validator：`429e148e4d1a0f330eeb4769e0826a69622c5c5fe8a68f34065514556c443340`；
- tests：`f072984cccc77af36eb17fb10c62a8e0aacda317031b9d78ec596565725dad69`；
- contract：`81832acb1d9fece7b734ec283110e334e3f33e8ea14c01e0919dc7562ae4d5bd`。

## 科学裁决与下一步

1. 现有 33/300 cohort 仍只回答 score-channel，不回填 config sidecar，不做 capability×generator。
2. 新 critic confirmation cohort 应在任何模型 outcome 前同时冻结 source manifest、source receipt、config manifest；
   若有 `unknown` release 或支持矩阵不平衡，交互分析 KILL，但普通 exact-stratum capability curve 可独立判断。
3. 真实 manifest 尚未到位，所以 GPU/model-fit 仍不授权；下一步是让 producer 输出 sidecar，再做 0-GPU support gate。
4. 该资产强化 D&B 的 provenance/identifiability 贡献，不能包装为 critic 方法正结果。

证据目录：`phase1/results/senior_experiment_config_contract_20260823/`。
