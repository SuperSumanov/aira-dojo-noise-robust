# Prospective decision scorer：正式冻结与激活

协议：`prospective_decision_v1`。运行代码 commit：
`41d638b1c8154415d523d8f22bbd10b7ae5b48be`。

## 裁决

正式状态为 **`PROSPECTIVE_SCORER_ACTIVE`**。producer 先在 v11 train-only 的 4,263 pairs、333 physical
runs、23 tasks、2,293 parents、5,499 endpoints 上拟合固定 `static_lr` 与 `char_tfidf_lr`；随后不 import
producer 的 verifier 从五个原始输入重新拟合全部数组。所有数组逐项差为 0，5,499×2 个 reference scores 的
最大绝对差为 0，全部完整性门通过。

激活时刻：`2026-08-13T22:19:17.348021Z`（北京时间 2026-08-14 06:19:17）。只有
`generation_started_at_utc` **严格晚于**该时刻的 physical runs 才能进入固定 first-240 cohort；v11 的 667 个
physical runs 另有显式 denylist。激活前已上传但尚未入库的 0812 senior archives 也按 pre-cutoff 处理，不能因
入库较晚而成为前瞻样本。

## 固定对象

- `static_lr`：与 heterogeneous OOF 相同的 decision-time static features、`C=1.0`、无截距；
- `char_tfidf_lr`：`char_wb` 3–5 grams、30,000 vocabulary、`min_df=3`、sublinear TF、20k head/tail code
  view、`C=0.5`、无截距；
- 模型 bundle SHA-256：
  `c4b9713d5a994c90ac8e24674154ae78d39f7c7961473078c1c7d61ce1c15d23`；
- model key：`b5481457d73eb6f0edd66b7dcfd8faa86ca86522a596f5ceb6394b84cee29bf1`；
- 667-run denylist SHA-256：
  `94c39feda828ed19e4a543b2abd7ad07bfb1e7266883bf49d0193cf48cbf012a`；
- producer runtime：527.9715677574277 秒；保存—重载最大误差 `1.11e-14`。

## 前瞻裁决保持冻结

first-240 按 `(generation_started_at_utc, source_sha256, physical_run_id)` 排序；不能按 outcome 提前停止。
支持门为至少 15 tasks、dominant task share `<=0.25`、至少 150 finite-decision runs 和 1,500 sibling pairs。
primary 是：

`I = (char_uniform - static_uniform) - (char_sibling - static_sibling)`。

只有 `I>=0.05`、task-bootstrap 95% CI 下界 `>0`、至少 15 tasks 且至少 60% 任务方向为正，才记为
`PROSPECTIVE_PAIRGRAPH_INTERACTION_CONFIRMED`。critic 的真实用途另由相对 deterministic random 的
complete-parent top-1 与 parent-equal grade utility 双重门裁决；pair-graph interaction 通过不等于搜索有用。

## 产物

- `fixed_scorer.npz`：不使用 pickle、`allow_pickle=false` 可读的固定模型；
- `freeze_receipt.json`：激活时间、commit 与模型/验证哈希；
- `independent_verify.json`：独立重拟合结果，SHA-256
  `e01ea94a91fbb845e865817e262afea11fed71d018fe8eb666cfe2fe6b2eeddf`；
- `summary.json`：producer summary，SHA-256
  `975f0a6d5c24c6f515c2e4662072822be2e7f02736b6afd1ee24cb7419f0ee04`；
- `train_reference_scores.csv`：固定训练参考分数，SHA-256
  `ed52fcc66979e394a0acf27f1b1ebce48eb2ae364994c6067d1bf5ca1a4d474a`；
- `full_artifacts.tar.gz`：28 members、681,687 bytes，SHA-256
  `80a21f8d05d52fd602edd61c0e2538c3b18910ca92cefb24ca6040ad4937d379`。

正式归档前，manifest 22/22 文件逐项通过；可疑文件名与高置信 secret 文件均为 0。全过程 0 GPU、0 API、
0 底座更新，且没有读取论文 frozen pair files。
