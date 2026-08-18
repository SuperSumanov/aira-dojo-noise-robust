# Score-channel replay 执行前数据门审计（2026-08-18）

状态：`BLOCKED_KAGGLE_RULES_NO_SCIENTIFIC_OUTCOME`。没有候选结果行，没有读取 label vault 或 replay outcome，
因此本节既不是正结果也不是负结果。

## 实际发生的执行

用户批准冻结矩阵后，approval SHA-256=`d34354dd3034792fb301b2f96d5e9269091d20c74c1cfc0426bb58600792c69b`。
第一次 Slurm `test-only` 因 gpu27 的 Memory 配置不接受显式 `--mem=64G` 而在提交前失败；移除该资源请求后，
四个正式 jobs `11105–11108` 被提交，但因 sbatch 未 `cd` 到 frozen worker worktree，均在模块导入前失败。
第二次只提交最小 gate job `11111`；它在候选代码执行前发现 `tgs-salt-identification-challenge` 的
`prepared/public` 缺失而失败。五个 job 的 Slurm `ElapsedRaw` 依次为 5/4/4/4/3 秒，总计 20 秒，即
`0.005555555555555556 GPU·h`；结果文件总行数为 0。

旧 approval 随后以 `incomplete_prepared_data_root_discovered_before_candidate_execution` 明确作废。未来若恢复，
必须从 38,400 秒硬上限扣除这 20 秒，并在完整数据冻结后签发新 approval；不得复用旧 receipt。

## 完整数据门

CPU-only 自动准备 10 个缺失任务时：

- `dog-breed-identification` 成功，public=10,225 files，private=1 file；
- 其余 9 个任务全部是同一种原因：Kaggle 返回“必须先接受竞赛规则”，没有其他错误类别；
- 9 个失败任务的 public/private 均为 0 files，不能把目录存在误当成数据完成。

新 fail-closed verifier `verify_score_channel_replay_data_coverage.py` 同时要求每个 frozen task 的 public/private
非空，并校验 replay manifest SHA 与候选数。commit `6c287d4d73758da03fd3f00e5cbc0aea6635e9b0` 在远端
聚焦测试连续两次均为 3 passed，完整 suite=`381 passed in 31.28s`。真实数据双 receipt 逐字节一致：

- 17 tasks / 320 candidates；
- 完整 8 tasks / 74 candidates；
- 缺失 9 tasks / 246 candidates；
- receipt SHA-256=`31545ae2ee318a9c0466c517a0a96d332fd0d0e0bd2f6577ccf09d04216b9774`。

因此不允许仅跑 74 个现成候选并将其替代确认性 headline；task-availability missingness 会造成严重选择偏差。

## 需要账号所有者完成的外部动作

必须由 Kaggle 账号所有者阅读并接受以下 9 个竞赛规则，或由学长提供同一 MLE-bench 版本已经 prepare 完成的
对应目录；自动化不能代替用户接受条款：

- https://www.kaggle.com/competitions/cassava-leaf-disease-classification/rules
- https://www.kaggle.com/competitions/dogs-vs-cats-redux-kernels-edition/rules
- https://www.kaggle.com/competitions/facebook-recruiting-iii-keyword-extraction/rules
- https://www.kaggle.com/competitions/new-york-city-taxi-fare-prediction/rules
- https://www.kaggle.com/competitions/osic-pulmonary-fibrosis-progression/rules
- https://www.kaggle.com/competitions/ranzcr-clip-catheter-line-classification/rules
- https://www.kaggle.com/competitions/tensorflow-speech-recognition-challenge/rules
- https://www.kaggle.com/competitions/tgs-salt-identification-challenge/rules
- https://www.kaggle.com/competitions/ventilator-pressure-prediction/rules

## 安全处理

Kaggle 403 traceback 把 cookie-bearing HTTP headers 写入 9 个 mode-600 日志。发布前已按整行原地脱敏并扫描：
cookie residual files=0、credential residual files=0。原始日志明确标记为不可发布；Git 中只记录分类和哈希，
不保存 cookie、API key 或原始 header。
