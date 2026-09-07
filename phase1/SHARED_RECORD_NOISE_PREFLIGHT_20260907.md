# 共享执行记录的噪声反例：只校准机制解释

执行前冻结，2026-09-07。主线和所有效果门不变，不读取任何真实语料或结果。
问题：已有有效电阻代理依赖比较噪声模型；当多条比较由同一批带噪节点分数派生时，
额外cycle的线性估计优势是否仍等同于独立edge噪声模型的优势？

固定模型：连通无向图的有向incidence矩阵B；d=B(theta+eta)+epsilon。
eta为独立同方差节点噪声、variance=rho/2；epsilon为独立edge噪声、variance=1-rho。
因此每条edge的边际噪声variance均为1。rho只取0,.25,.5,.75,1。
theta采用sum-zero约束；比较目标固定为原tree的所有edge contrasts。
两个完全合成、六节点case：path→complete，star→complete；节点/目标不变，新增边仅为cycle。

预先提出、待数值核对的恒等式：任意zero-sum contrast c的GLS variance为
`(1-rho) * c^T L^+ c + (rho/2) * ||c||^2`。
故edge contrast为`(1-rho)*R_eff + rho`；rho=1时同一节点分数派生的cycle不能降低该variance。
这不是神经critic或binary Bradley–Terry的定理，不估计真实rho，不预言G→L无效。
原G/L新增桥可以改变可比较方向的rank；本项不否定已验证的incidence-rank计数。

验证：生产器由Laplacian eigendecomposition算封闭式；独立验证器直接构造edge covariance与
sum-zero设计矩阵，广义最小二乘/SVD求每一目标的variance。两个case×5rho，绝对误差≤1e-9；
rho0必须重现纯有效电阻且full优于tree；rho1必须无cycle收益；固定rho网格上优势不得上升。
额外检查边方向/行序/节点编号不改变aggregate，重复edge输入拒绝，不通过就不解释其数字。
不做Monte Carlo、无seed/随机抽样/训练/模型加载，无新选择器，不重跑历史selector或改50%冻结成本点。

资源：单CPU、BLAS线程1，测试和双实现各≤60秒；纯numpy合成数组，GPU/API/真实数据读取均0。
先本地和Linux测试，后固定commit运行；两实现逐项相等并记录Python/numpy版本/命令/耗时/源SHA。
本地首次collection因多行if缺括号报SyntaxError，未计算矩阵；修正后测试，保留工具失败记录，不计作正式运行。
意义仅为解释边界：零新增执行标签不等于零训练收益，潜在收益来自监督组织/优化，必须由同预算critic实验验证。
