# 0906新语料：有界原始复制，不解压、不揭盲

香港2026-09-08；用户要求继续工作并检查学长新上传。myfork fetch成功，方向入口仍3b9da334834e0c12421b09a6800574b7bab52ac5，学长branch仍40d7dea10738f159fc97cad8487ab4ada88022a3。

1. 目标仅为将固定0906目录的11个缺失压缩包安全复制到研究盘；不是效果实验或训练准入。
2. 两次目录元数据观测一致：11归档、0子目录、0非归档文件，未读payload。私有清单SHA为bd50b189f01f8730887ecfff4487d23c49228a039f3ccacff8abd3f15800042c。
3. 复用0904已完成下载器，只更换批次、固定manifest、计数和输出根；另加HTTPS、整轮deadline、重复新内容和LATEST守界。原脚本不改。
4. 单文件128MiB、整批1GiB、1800秒、100 HTTP请求上限；先实际分配1GiB并核inode/allocated blocks，再删除自身空间探测文件。失败保留，不自动重试。
5. 仓库固定脚本源码后执行；远端Linux合成manifest正负控和HTTPS边界测试，不下载/解压测试数据。
6. 只允许公开Google下载GET、验证TLS、禁cookie；私有文件名、Drive对象ID、原始包及可能的凭据不离开远端、不回显。
7. 临时新目录内逐文件排他创建、流式hash、fsync、独立重hash及gzip魔数，设0400；结束再核固定远端目录清单，原子移动到不存在的0906目录。
8. 原343归档不修改；当前LATEST固定6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116。未知增加、sidecar、哈希变化即停止。
9. 独立复验用另一实现及GNU SHA、mode/mtime/inode检查，只读压缩字节，不解析tar或读取冻结label/prediction/utility。
10. 六小时本地时龄和原3观测/300秒间隔/600秒跨度不变；实际下载完成前不给成熟时间，不能由上传日期替代本地mtime。
11. GPU/API/model fit=0；不重跑已完成12664、不释放旧12535，不建立新monitor或延长旧摄取窗口。下载不等于入库，入库不等于可训练来源。

后续方向仍为既定Lbudget对G-reuse→L-full、seeds6/7四fit；不因新文件出现而改监督关系、开启旧方向或把前瞻run换成开发数据。正式来源仍缺实际evaluator/runtime证据；本轮并行整理可直接给生产端的现成记录需求。
