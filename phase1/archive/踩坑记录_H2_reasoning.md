# Phase-1 H2（reasoning-first critic）踩坑与调试记录

日期：2026-07-08 ~ 2026-07-09 ｜ 硬件：单卡 RTX 3090 24GB ｜ 代码：`aira-dojo/phase1/`

> 背景：C1（噪声感知偏好蒸馏）主线被 G0 gate 证伪后，退回 Phase-1 价值 critic 主线，
> 修 reasoning critic 攻 H2（reasoning-first 是否更省样本）。调试过程连撞多个坑，
> **最有价值的发现是 reasoning 从 P1b 起从没真正跑过**（一个 prompt 截断 bug）。
> 更早的坑（aira guard bug、QLoRA 工程、C1 证伪）见 `README.md` / `phase1_进度报告_20260707.md` / memory。

---

## 坑 1（最重要）：reasoning 截断 bug —— reasoning 从没真正跑过

**现象**：reasoning 预测全是垃圾（spaceship intra spearman **−0.299**），但看起来"有信号"（非常数）。

**定位手段**：写 `dump_reasoning.py` dump 出**原始生成文本**——发现 reasoning 生成的不是分析，而是在**续写候选代码**：
```
y=0.940 pred=1.0 :: 'Freq"] = surname_count\n# ===== 6. Feature Engineering =====\ndf.fillna(-1...'
y=0.954 pred=0.0 :: 'test_eng[c] = test_eng[c].fillna("Missing")...'
```

**根因**：`build_value_prompt` 把 `code[:4000字符]`（≈1200 token）放在 `# Instructions`（要求"分析 + 输出 predicted_final_score"）**前面**。当 prompt 被截到 768 token 时：
1. code 占满整个 prompt，`# Instructions` 被挤出去（模型根本没看到要它分析）；
2. 代码块结尾的 ``` 也被截掉 → **未闭合代码块**；
3. 模型的自然反应 = 继续写代码；
4. `parse_score` 从生成的代码里抓最后一个数字当预测 → std=0.35 有变化，但全是垃圾。

**影响（严重）**：**P1b 至今所有 reasoning 结果全部作废**——包括一度误判的"nomad reasoning +0.425 说明它能学"，那也只是 parse 从代码里抓的数字碰巧和 nomad 真值正相关。**reasoning 从没被公平测试过**，之前所有"reasoning 弱/退化"的结论都建立在这个 bug 上。

**修复**：`qwen_backend.py` 里 `code[:4000] → code[:1200]`，保证闭合代码块 + `# Instructions` 都进得了 768 的 prompt。

**验证**（dump 前后对比）：
| | bug（code[:4000]） | 修复（code[:1200]） |
|---|---|---|
| 生成内容 | 续写代码 | 真 analysis（"self-reported score appears reasonable" / "code incomplete lacks..."） |
| parse_fail | 6/36 | 1/36 |
| n_unique | 5/36 | 12/36 |
| spaceship intra spearman | −0.299（假） | **−0.050（真实弱信号）** |

**教训**：generate 型 critic 的 prompt，**指令必须放在会被截断保护的位置**（放前面，或保证内容短到指令进得来）。光看指标（spearman −0.299）会误判"方法不行"，**必须 dump 原始输出**才能发现是 bug。

---

## 坑 2：显存 OOM 调试链（连撞 4 次）

reasoning SFT 在单卡 24GB 上反复 OOM，逐步定位：

| 尝试 | 配置 | OOM 根因 |
|---|---|---|
| ① | max_len 1536 | scalar 的 `output_hidden_states=True` 收集**全 28 层** hidden × 1536 seq，与 gradient-checkpointing 冲突（ckpt 靠不存中间激活省显存，output_hidden_states 强制保留） |
| ② | max_len 1024，一个进程串 scalar+reasoning | scalar 跑完显存碎片没完全还清，reasoning SFT 叠加 → OOM（`VRAM after freeing teacher: 0.02GB` 证明 teacher 已释放，不是 2×7B） |
| ③ | 拆独立进程 + `logits_to_keep` | 单卡干净进程**仍差 176MB**——证明瓶颈**不是 vocab logits**（logits_to_keep 省了也没用），是 reasoning SFT 的 full-vocab cross-entropy × 长 seq 的 activation |
| ④ | **两臂 prompt 768 / SFT 序列 1024** | ✅ 跑通 |

**关键教训**：
- reasoning SFT（full-vocab CE，152064 词表）比 scalar（单标量 regression head）**吃显存得多**；同样 seq 长度下 reasoning 峰值远超 scalar。scalar 能跑的 1024，reasoning 加上 256 的 target 就爆。
- 单卡要给 reasoning SFT 留足余量 → 最终两臂都退到 prompt 768、SFT 序列 1024。

---

## 坑 3：sbatch 退出码被掩盖（假 COMPLETED）

**现象**：job 显示 `COMPLETED`、只跑了 1-2 分钟，其实是 python OOM 崩了。

**根因**：sbatch 脚本最后一行 `echo "=== done rc=$? ==="` 本身成功（rc=0），把前面 python 的 rc=1 **覆盖**成 job 的最终退出码 → SLURM 记为 COMPLETED。监控据此误报"完成"。

**修复**：
```bash
python -m phase1.run_full_matrix ...
rc=$?
echo "=== done rc=$rc ==="
exit $rc          # ← 让 job 状态如实反映 python 的退出码
```

---

## 坑 4：多 job 共享卡的确认（虚惊但必查）

**担忧**：同节点起多个 `--gres=gpu:1` 的 job，且 sbatch 硬编 `CUDA_VISIBLE_DEVICES=0`，怕它们抢**同一张物理卡** → 显存翻倍 OOM。

**实测**：SLURM 有 **cgroup 隔离**——`scontrol show job <id> -d | grep GRES` 显示同节点的两个 job 分到**不同 IDX**（如 IDX:0 和 IDX:1），`CUDA_VISIBLE_DEVICES=0` 在各自 cgroup 内指的是各自分配到的那张卡。安全。

**教训**：起多 job 前用 `scontrol show job <id> -d` 确认 IDX 不同，别假设。

---

## 通用诊断工具：`dump_reasoning.py`

训一个 fold 后 dump：预测的 **mean/std/min/max/唯一值数/parse失败率** + **8 条原始生成文本**。
这是区分以下几种失败的唯一手段：
- 退化成常数（std≈0，spearman≈0/NaN）
- 学成负相关（std 正常，spearman 负，生成合理）
- 生成乱码/续写代码（← 本次的 bug，光看 spearman 发现不了）

**没有这个脚本就发现不了坑 1。**

---

## 公平性代价（写汇报时要说明）

为让 reasoning SFT 在单卡跑通，最终两臂 prompt 都降到 **768 token** + code 截到 **1200 字符**（原本想要 1024 / 4000）。
- **代价**：context 变短，截掉更多 code 尾部；
- **但公平契约保住**：scalar 和 reasoning **用完全相同的 prompt 长度和 code 截断**，唯一变量仍是「reasoning-then-value 格式」。汇报时应注明这是单卡显存约束下的妥协，未来多卡/更省显存的实现可放宽到更长 context。
