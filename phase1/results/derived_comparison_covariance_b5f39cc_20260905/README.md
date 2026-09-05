# 同源派生比较：Gaussian 连续差值反例

目的：审视图谱代理解释，而非重算语料、模型训练或确认性效果实验。
推导和适用边界见 `phase1/PROJECT_REASSESSMENT_20260905.md` 第 3 节。

- as-run commit：`b5f39cc8b92d5746c3f627f0e9b6bbe904fb2def`。
- source SHA：`d4873b18655cc648c9f103db223a2c4b1c773c6e178ea8019f21b5a7a62026ca`。
- git archive SHA：`01b3a80a14f4adb5ae5c011fd9112b4de095039d4529d7bba202970a7975b718`，本地/远端一致。
- result.json SHA：`4de8a1803800daf6bf4d2cb5643b2df37fecb3739c3c53223b0114ca5a4276d1`，下载原字节一致。
- NumPy 1.26.4；单线程；固定矩阵、无采样 seed、无拟合、无语料读取、无 GPU/API。
- stdout 与新目录独占创建的 result.json 逐字节一致；脚本正常退出。

复现：从 exact commit 导出源码，执行

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/research/d7/spc/yzyang4/venvs/exp/bin/python \
phase1/check_derived_comparison_covariance_20260905.py --output NEW_RESULT.json
```

同方差/异方差、forest/complete/重复 forest 的依赖感知 Fisher 最大差为
`9.992007221626409e-16`，在预定 `atol=rtol=1e-10` 内；每个 contrast 方差还与端点方差和的闭式值比较。
两个真实独立执行向量作为方差减半正控制。不同 scalar 向量具有相同 forest 二元方向但不同完整方向，
作为“不能把连续差值 sufficiency 推广到二元标签”的反向控制。
同父节点的常量 parent 分数相减不改变 sibling 排序也已代数核验。

本脚本使用 Gaussian 连续差值模型。它不证明实际执行噪声是 Gaussian，不证明二元 BTL 的无效或一致，
也不测 full G 的实际优化作用。初次交互推导计算已可见这些案例；这个 exact-commit 复跑不是声称
在未知数据上预注册发现了结果。旧图指标、门和 sealed cohort 均不修改。
