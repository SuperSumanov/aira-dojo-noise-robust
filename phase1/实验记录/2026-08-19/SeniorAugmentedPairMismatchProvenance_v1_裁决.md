# Senior Augmented Pair Mismatch Provenance v1：裁决

## 复现与执行记录

- 结果前 source commit：`5b9f285c2f1a62bf82a2820346da26be96e3570c`；
- 远端完整测试：`391 passed in 34.88s`；
- producer 双跑逐字节一致，独立 verifier 两次一致；
- summary SHA256=`7c141bd6b74ee1f3aa6e60459d272da34edb99a1f6734508510d8d75c04ccc76`；
- verification SHA256=`065f8b7e7d7d2ad3b334e29ca508896a99cb02352e9a0481da5b0fb7aece851d`；
- grade/orientation/code/frozen-test/GPU/API/model training：0/0/0/0/0/0/0。

正式 scientific producer 启动前，harness 依次暴露并修复了五个环境问题：远端 GitHub 暂不可达、LFS smudge
依赖/缺失对象、预设 temporary root 不存在、未绑定 Python venv、pytest 收集范围过宽。每次均在 producer 输出前
fail closed；最终通过离线 Git bundle、no-smudge detached worktree、已存在 `/tmp`、固定 venv 与
`phase1/tests` 范围解决。没有覆盖或续写失败输出目录。

## 结果

- full-train pairs=9,001；
- config mismatch pairs=708，share=`0.07865792689701144`；
- 8 tasks / 71 runs / 16 unordered config transitions；
- same day=708/708，same parsed family-date=708/708，run-ID parse failure=0；
- 最大任务：191/708=`0.269774011299435`；
- 最大 config transition：98/708=`0.1384180790960452`。

任务分布为 dog-breed-identification 191、tabular-playground-series-may-2022 148、
nomad2018-predict-transparent-conductors 100、leaf-classification 79、
text-normalization-challenge-english-language 74、new-york-city-taxi-fare-prediction 49、
dogs-vs-cats-redux-kernels-edition 45、text-normalization-challenge-russian-language 22。

## 裁决

固定归因为 **`BATCH_CONTENT_MIXING_LIKELY`**。直接代码证据与结构证据相合：学长的
`build_subtree_pairs.py` 在 batch 内按 task 形成任意组合，但没有按 experiment config 分层；文档把每个目录描述为
同超参 batch，却没有 producer/verifier 强制检查。由于旧产物未保存 batch path，归因仍保留 `LIKELY` 而非
`CONFIRMED`。

上游 `INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT` 不变。不得过滤 708 条后把当前 8B/scaling 曲线追认为确认性结果。
允许的下一步是实现 future-only exact-stratum pair contract 与独立 verifier，并交给学长用于下一版语料；新 cohort
到达后重新冻结 train-only dev 与 learning curve。该修复是 D&B 数据质量资产，也是日后可信 scaling 正结论的必要
条件，不是当前方法效果正结论。
