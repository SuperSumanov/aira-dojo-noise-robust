# Balanced three-client production smoke（2026-08-19）

状态：`PASS_BALANCED_CLIENT_SMOKE`。这是生产路径工程门，不是 client/critic 效果实验。

## 冻结矩阵与结果

- source/control commit：`f989b622def3c66dfa7aac6e1ccd1bc8b2a5b416`；
- clients：`deepseek-v4-flash`、`qwen3-coder-flash`、`glm-5`；
- task/seed：`spooky-author-identification` / `1401`；
- 每行 MCTS step limit=2、execution timeout=300 秒、run cap=900 秒、1 GPU；
- Linux 全套：`403 passed in 36.10s`；
- Slurm：job `11189/11190/11191` 均 `COMPLETED 0:0`，elapsed=`513/432/165` 秒；
- 独立 verifier：3 physical runs、6 journal rows、三套 resolved/final client config 一致、
  checkpoint state 与 search export/journal 一致、`env_variables.json=0`；
- verifier 连跑两次逐字节一致，SHA-256：
  `1fbe1464ad47346bf1a8e5e086c62053f70d21c5c07a701069d777610340c658`；
- verifier 明确 `score_fields_read=false`，本目录不报告 smoke 的分数或 client 排名。

Qwen 行虽然满足预注册的结构工程门并正常退出，但运行日志写明最终没有 valid solution；因此这个 PASS
只证明真实 client 切换和端到端生产链可运行，不能解释为三家都在该 seed 上成功解题。后续平衡 pilot 必须
逐 client 报 valid-submission/failure rate，不能只报 run completion。

## 失败链保留

- a1/job `11178`：旧 source pin 把 Qwen 解析为 `qwen-max-latest`，resolved-config 门在 Qwen 生成前拒绝；
- a2/job `11183`：三行 client config 均正确，但 native Slurm array 触发 AIRA/submitit 环境不兼容，三行在
  solver/operator 实例化前失败；
- a3：改为三个普通 Slurm jobs 后通过。a1/a2/a3 从未拼接。

## 本目录证据

`verification.json` 是不含 score 的主收据；`resolved_*.yaml`、`rc_*.json`、`slurm_accounting.txt`、
`provider_probe.log`、manifest 与 commit/submission 收据用于独立复核。raw journal/code 留在远端不可变
run root，以 SHA 引用，不随 Git 发布。
