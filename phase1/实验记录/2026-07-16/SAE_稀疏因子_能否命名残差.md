# SAE：能不能把 probe 的"残差因子"稀疏化成几个可命名的方向？

**日期：2026-07-16** ｜ 脚本：`phase1/sae_probe.py`（v1）、`phase1/sae_probe2.py`（v2，采用）｜ 单 GPU、冻结模型、不微调

---

## 一、这个实验在验什么

A1 发现：probe 有约 76% 是可读的好实践，但**扣掉这些后仍剩 0.20 的"微妙残差"**。这一步就来试：在冻结 layer-21 的**逐 token 激活**上训一个**稀疏自编码器（SAE）**，看能不能把那 0.20 残差拆成**几个可命名的方向**（这是"用稀疏化定位关键因子"的想法）。

## 二、两版

- **v1（弃）**：普通 L1 SAE，两个硬伤——① 根本没稀疏（每 token 341/1024 激活）；② 用了含自报分的提示（残差混进自报分）。不采信。
- **v2（采用）**：**TopK SAE**（强制每 token 恰好 24 个激活，现代标准做法）+ **纯代码提示**（mask 掉自报分）。

## 三、v2 结果（真稀疏了）

- 稀疏 OK：每 token 24 激活，887/1024 特征存活，重构良好。
- **SAE 特征 → grade：+0.121**（稠密 probe 0.29）→ 稀疏 + max-pool **丢了一半 grade 信号**。
- **SAE 特征 → 残差：+0.014 ≈ 0**（稠密残差 0.20）→ **几乎没抓到那 0.20 残差**。
- **最能"预测残差"的 top 特征全是 boilerplate**：chat 模板 token（`<|im_start|>assistant`）、任务元数据行（`metric=, higher_is_better=`）、import 行、seed 设置行——**没一个是质量因子**。（那些 0.2 的单特征相关是没做交叉验证的噪声；CV 后总残差是 0.01。）

## 四、结论

**SAE 原型没能从残差里拉出"可命名的方向"。** 两版一致（v1 非稀疏是 boilerplate，v2 真稀疏还是 boilerplate + 残差≈0）→ **那 0.20 残差不是一个干净、可稀疏隔离、可命名的"质量因子"，而是弥散、且和表面 token 纠缠。**

**诚实 caveat（不夸大）**：原型有局限（max-pool 聚合粗、k=24 激进、289 卡太少），所以是"原型层面劝退"，不是"SAE 原理上不可能"。真要深挖得当成一个独立的可解释性工程；原型不支持这个投入。

## 五、复现

```bash
source /research/d7/spc/yzyang4/venvs/critic/bin/activate
cd /research/d7/spc/yzyang4/aira-dojo
python -m phase1.sae_probe2   # GPU：抽逐 token 激活 + 训 TopK SAE + 分析，~10min
```
