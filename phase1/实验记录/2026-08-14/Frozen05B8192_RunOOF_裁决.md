# Frozen 0.5B @ 8192 run-OOF critic 裁决

日期：2026-08-14。对应 outcome 前预注册：`Frozen05B8192_RunOOF发现门_预注册.md`；运行 commit：
`f339eb971c6d04fd149c608cc570b4bcdcdd1aac`。

## 裁决

正式状态是 **`VERIFIED_DISCOVERY_NO_UNLOCK`**。固定的 frozen Qwen2.5-0.5B mean+last 表示加单一全局
linear rank head 没有从 v11 b0 训练集学到稳定的跨 physical-run sibling 排序。发现链和独立 verifier
都记录 `frozen_read=false`；论文冻结 b0/b1/b2 没有进入 manifest、embedding 或评分。

| 指标 | outcome | 预注册门 | 结果 |
|---|---:|---:|---|
| OOF pair accuracy | 0.5038705 | >=0.54 | FAIL |
| run-macro 95% CI | [0.4979729, 0.5669365] | 下界>0.50 | FAIL |
| task-macro 95% CI | [0.4835613, 0.5711860] | 下界>0.50 | FAIL |
| complete-parent top-1 | 0.4471005 | >=0.50 | FAIL |
| parent-equal gap utility | 0.5105066 | >=0.55 | FAIL |
| supported task 非劣于随机 | 10/20=0.50 | >=0.60 | FAIL |
| random control | 0.5036359 | [0.47,0.53] | PASS |
| complete-parent share | 0.9851723 | >=0.95 | PASS |
| pair/run/task/coverage/finite/convergence | 全过 | 全过 | PASS |

## 完整性与真实资源

- 输入 4,263 pairs / 333 runs / 23 tasks / 2,293 parents / 5,499 endpoints；dominant pair task
  900/4,263=0.2111；
- train 对 156 held runs 的 physical-run、node、raw code SHA-256 三层交集均为 0；
- 四个 deterministic shards 为 1,390/1,388/1,331/1,390 endpoints，174 个原子 NPZ chunks；
- token min/median/max = 644/3,803/8,192，截断占比 0.1058374；这次不是短 context 代理；
- 16-card smoke 71.091 秒；正式四 shard 各 236.4--247.3 秒，合计约 0.269 GPU·h；
- OOF head 16.116 秒；API=0；底座权重更新=0；四个 GPU jobs、五个 OOF folds 和 verifier 均 rc=0；
- 独立 verifier 从原始 pair CSV、chunk 和 metadata 重算全部指标与门，状态一致。

完整包位于 `phase1/results/frozen_embed_v11_20260814_f339eb9/full_artifacts.tar.gz`（Git LFS），
SHA-256=`096a3581bfce48c83019f3440e88089d4b8a4dd0a768224493f892941a3d64f7`。包内 217 个文件在打包前
做过密钥模式和非 ASCII 路径扫描，结果均为 0；两份中文预注册文档已由普通 Git 单独保存，不在包内重复。
portable 包已在 Windows 解包并从运输后的 chunks 重跑独立 verifier 通过；两次 pre-outcome preflight
失败也原样保留。

## 允许与不允许的解释

允许：这个固定 global-linear pooling/head 不值得消耗一次 frozen look；“把 0.5B 上下文拉到 8192”本身不是
充分杠杆；pair accuracy 之外的 top-1/utility 同样没有正面结果。

不允许：不能写成“0.5B 无效”“frozen code representations 普遍无效”“长 context 无效”或“critic 无法做”。
模型在 supported tasks 的描述性 OOF accuracy 从约 0.37 到 0.67，说明同一全局方向可能掩盖任务交互；但这是
看过 outcome 后的机制线索，不是可发表效果，也不能按任务挑正例。

## 后续正面路线（新实验，不能追认本门）

1. **Task-conditioned parent-level head**：在相同 train-only embeddings 上显式建模 task×code interaction，
   优化 complete-parent top-1/ListNet 类 top-centered objective，而非继续优化 pooled pair accuracy；按 outer
   physical-run OOF，正则/混合权重只在 inner run folds 选。
2. **异构 predictor ensemble**：只有在 exact same-pool OOF 上证明 frozen、char-TFIDF、static family 的错误
   具有互补性，才做 nested stacking；不能用 oracle 路由或同一 OOF 行训练再评估 meta-head。
3. 两条都是 NAS 中已有的 loss/ensemble 思路，只能作为强方法资产；论文 novelty 仍落在 run-clean MLE-agent
   benchmark、真实 sibling/top-centered utility、成本分账、删失/标签协议和最终 prospective search A/B。
4. 新 discovery 仍不读 frozen；只有相对本次 global-linear baseline 的 parent top-1/utility 改善通过双聚类门，
   才允许一次 frozen 评分。
