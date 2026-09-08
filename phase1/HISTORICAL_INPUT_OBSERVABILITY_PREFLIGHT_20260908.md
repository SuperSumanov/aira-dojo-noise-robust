# 有界输入诊断，不读取效果标签

先于结果固定：只使用已独立核验的84个历史run程序包（非保护前瞻数据），其
manifest SHA为0912a2e6cf8342fe6c209645d2d1b56c142f91a066197fcd5e37d07f8c0955e7。
所有3447非空程序均保留，不按编译、长度、成绩或代码家族筛选。

使用现有Qwen3-1.7B-Base tokenizer ea980cb0a6c2ae4b936e82123acc929f1cec04c1，绑定已有五文件SHA；
任务名前缀、无special tokens、head25/tail75，三个事前固定长度2048/8192/16384。
复用现有encoder并逐token核对；不载模型、不读取权重、不训练、不执行候选、不连接API。

报告每档完整/保留token、截断程序、字节不同同父候选编码完全相同的数量，以及按任务统计。
完整token本身相同与截断新增碰撞分开。独立实现用位置mask、逐run同父分组重算，结果逐字段核对。
相同编码表示该确定性输入无法区分；不相同不证明关键语义修改保留，更不证明critic可预测或有正效果。

只读取既有不含结果的pack manifest和已credential-shape检查的独立code文件；复查源hash、只读和安全路径。
不读取旧label/outcome、保护人口、archive成员或预测。不改变源码、训练输入、来源准入和冻结配方。
只写独立新诊断目录，公开只含聚合task/count和SHA，无run/endpoint/private identities。
成本限单进程CPU1200秒、最多128MiB代码读取、无GPU/API；保留错误，不自动扩资源或改分析口径。
这是确定性输入诊断，不做随机统计检验，不把派生pair当独立执行样本。
