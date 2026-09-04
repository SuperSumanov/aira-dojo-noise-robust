# Decision-context reach r3 失败与 r4 source-archive 补全

r3 结果根 `g-reuse-decision-context-39b8e4d-20260905-A` 已使用 exact source-root `PYTHONPATH`，但精简
archive 漏含 `historical_global_local_pool_readiness.py` 及其依赖
`historical_train_encoding_readiness.py`，因此在间接 import 链上失败。stdout 为 0 字节、stderr 909 字节；
未打开数据或产生 metrics。

r4 不修改任何 Python 科学/运行代码，只从同一 Git commit 的新归档加入上述两个 tracked 模块并使用新结果根。
输入、population、spectral50、阈值和 A/B/verifier 门全部不变。
