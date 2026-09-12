# 共同起点改进实验：实际投入运行的源码

源树 `1ec18564f176d58a3a7ac3a46852ad92044777b5`，控制器 `a46dbd189d6f74cf7357377ba41fcc065b1d414c`。
源码tar为1239040 bytes，SHA256 `c73b4ac18baf341256d0c598218d3ee5cdb065143145f8aa5cebcadef1c237b6`。
运行矩阵：seed28/29 × Leaf/Space × random/单票critic，13190/13191；配置/结果见对应报告与results目录。

仅此v4进入GPU。准备阶段v1发现digest名称冲突；随后补齐训练内真实验证反馈与生产Black格式绑定；
这三份未激活准备包不作为实验，不合并进入运行结果。
首步固定RandomForest代码在实际原镜像内执行并计入每臂600秒；后续恢复4候选；不是免费注入已评分解。
不含数据、密钥、日志全文或受保护cohort。
