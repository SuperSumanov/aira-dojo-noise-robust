# 固定历史范围的已有预测文件可用性

固定source34343b8ff7dbe4107ccced6781df627afce7c988；84run、24归档，两遍header-only扫描。
不打开tar member；真实Linux5项测试通过。A/B逐run计数一致，独立核验48份回执并再次重hash24归档。
原summary SHA c8bbefcf6a0f7df5da8a26f3e49af3fe41f6fb665c54c5b2313eb1c9e0526eb7；
independent SHA 6fd628afe3ba23acd0db638d22a436017fa823613941cec28f0532333aab3eb9。
本地两文件从远端逐字节复制，独立hash一致；私有逐run表不导出。

支持格式为csv/csv.gz/parquet/npy/npz；仅发现84个可能grading JSON，覆盖全部84run。
未发现上述预测表或已列举的依赖锁文件，故这一归档范围目前不支持“直接重评分已有预测”捷径。
**不等于**所有可能格式/缓存/生产机位置均无预测，也不说明grading文件的内容/版本/分数。
未执行新评分、未读保护cohort，source admission仍false；不从文件名推断pristine evaluator。
