# Target-300 future identity cohort progress at snapshot ad0b624d

状态：`FUTURE_COHORT_COLLECTING`

这是 target-300 identity cohort 的 outcome-blind 进度收据，不是 score-channel 效果、truth-support 或 replay 结果。

## 固定执行与结果

- science commit：`ab59a011d945e4a96daf7dbbbc927a59027da077`
- immutable intake snapshot：`ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e`
- 触发：同一 `LATEST` 连续 5 次、间隔 300 秒，随后只运行固定 runner；monitor log 记录
  `quiescent_trigger` 与 `formal_finished rc=0`。
- append-only previous：64 runs / 21 archives；exact prefix survived=`true`。
- 当前：129 unique physical runs / 41 accepted archives / 21 tasks；相对 previous 新增 65 runs。
- target=300，remaining=`171`；没有 boundary archive、没有 one-time closure anchor、closure=false。
- settled archive prefix=`54`，其中 13 个 structural rejection；不做 partial-archive salvage。
- focused/full tests=`12/965 passed`，full 有 47 warnings；producer/verifier A/B 可复现 diff 均为空。
- `truth_support_computed=false`，label/outcome/score/raw archive payload 均未打开；GPU/API/model-fit/base-update=
  `0/0/0/0`。

允许写：target-300 的固定时序人口已从 64 增至 129 runs，并保持 append-only 身份前缀与结果盲。

禁止写：target-300 已闭合、truth support 已通过、score channel 有效、raw-grade supporting hypothesis 成立，
或这 129 runs 可与 first-960 混池。target-300 与 first-960 estimand 不同；达到 300 也不会自动授权 effect/replay。

## 文件

- `summary.json`：结果盲 cohort inventory；
- `independent_verification.json`：独立 verifier receipt；
- `preflight_matrix.txt`：正式预检；
- `focused_tests.txt` / `full_tests.txt`：固定 science commit 测试输出；
- `latest_before.txt` / `latest_after.txt` 与 observations hashes：输入稳定性收据；
- `filename_scan_count.txt` / `content_scan_count.txt` / `forbidden_open_count.txt`：安全计数；
- `remote_SHA256SUMS`：远端 formal manifest；
- `SHA256SUMS`：本公开包的内部清单。
