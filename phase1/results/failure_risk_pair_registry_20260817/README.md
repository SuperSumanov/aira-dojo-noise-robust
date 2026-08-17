# Code-free failure-risk pair registry v1

日期：2026-08-17。裁决：`VERIFIED_CODE_FREE_FAILURE_RISK_PAIR_REGISTRY`。

结果前 commit `486e245927ac717e589ff7c9923e029c177d8b26` 冻结了既有 494-pair support 的派生发布协议。
正式运行只接受 SHA=`77b81f8d4356d74f14647c8a12281af201fe34c75da04ed077febdac17b400f1`
的 support summary 和锁定的 v11 inputs；target journal 先做完整 blob credential scan。

完整测试为 `358 passed in 30.72s`。producer 双跑的 registry 与 summary 均逐字节相同；registry 为
494 unique-parent pairs / 13 tasks / 126 physical runs，SHA256=
`ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747`。结构 verifier 不 import producer，
重新检查固定十字段 schema、digest、failure/success/parent identity 唯一性和 task/category aggregates，状态为
`STRUCTURALLY_VERIFIED_CODE_FREE_FAILURE_RISK_PAIR_REGISTRY`；summary SHA256=
`4aa42492e1d0a054f4a172a2acbc2f3bf802c91aead13f97daf0666ef40ceb12`。

registry 每行只含 parent/run/task、failure/success child ID、failure category、source journal SHA 与 endpoint
code SHA。它不含 raw code、stdout、diagnostic、grade 或 frozen endpoint code；credential target journal SHA=0。
这使 494-pair benchmark 成为可下载、可审计的数据资产，但不构成 method effect、search utility 或因果 failure
predictor 证据。

远端不可变产物：
`/research/d7/spc/yzyang4/failure-risk-pair-registry-v1-486e245/`。
