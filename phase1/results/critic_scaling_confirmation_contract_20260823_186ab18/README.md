# Clean critic scaling confirmation contract：exact-commit 验收

状态：`CONTRACT_READY_ASSETS_PENDING`。本目录验收的是 future-only 分析/复核接口，不是模型效果结果。

## 冻结身份

- scientific commit：`186ab1800973972b8066c7a706bd06f92c8d124a`
- contract SHA-256：`579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568`
- remote no-smudge worktree：`/research/d7/spc/yzyang4/aira-dojo-verify-186ab18-nosmudge`
- durable log：`/research/d7/spc/yzyang4/prospective_decision_v1/scaling_contract_verify_186ab18.log`

## 验收结果

- 聚焦正控/负控/攻击/确定性/独立复核：`7 passed in 2.02s`；
- 完整 `phase1/tests`：`830 passed, 33 warnings in 56.22s`；
- Python compile、`git diff --check`、worktree clean；
- 文件名/内容高置信凭据扫描：`0/0`；
- GPU/API/model fit/base-LLM update/future truth：`0/0/0/0/false`。

第一次普通 fresh worktree 因仓库历史 LFS 对象 404 在测试前失败，故另建 no-smudge worktree；失败目录没有删除。
日志化复核运行的科学测试全部通过，但零命中的 `grep` 在 `pipefail` 下返回 1，使脚本在扫描打印前退出；只读
postflight 随后追加修正原因、0/0 扫描、clean worktree 与 `verification_complete=1`，没有重跑或改写测试结果。

## 尚缺资产

没有新的 dev-only checkpoint matrix、逐 pair prediction bundle 和 one-shot ledger，因此分析器当前不可生成效果
裁决。任何 GPU 训练仍需另行提交 exact matrix、run 数与 GPU·时预算并获得批准。
