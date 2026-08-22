# Grounding-availability secondary preflight

状态：`FROZEN_POST_HOC_SECONDARY_NOT_RUN`。

这是已知旧 primary aggregate KILL 后冻结的描述性分解，不是 outcome-blind confirmation。正式输入尚未运行；raw result
shards 与 label vault 尚未为本 secondary 打开。GPU=0，API=0，model fit=0。

冻结内容：

- protocol：`phase1/score_channel_grounding_availability_protocol_v1.json`；
- producer：`phase1/score_channel_grounding_availability.py`；
- independent verifier：`phase1/verify_score_channel_grounding_availability.py`；
- tests：`phase1/tests/test_score_channel_grounding_availability.py`；
- detailed record：`phase1/实验记录/2026-08-23/ScoreChannel_GroundingAvailability_结果后冻结.md`。

机器打印的冻结 SHA 见 `hashes.sha256`。本地 focused tests=`7 passed`；本地 full phase1 collection 因该 Windows
Python 3.13 环境未安装 `scipy`/`sklearn` 而 fail-before-tests，不能伪称通过。冻结 commit 推送后必须在远端完整依赖
环境做 fresh-checkout full suite，并把真实结果另行提交；在此之前不运行真实输入。

首次冻结 push 前 staged secret scans：required filename pattern count=`0`，high-confidence content hit count=`0`；
`git diff --cached --check` 通过。
