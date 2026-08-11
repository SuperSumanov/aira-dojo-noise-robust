# 8B 决策点 critic:数据包与冻结评测协议(给学长,2026-08-12)

## 一句话

我们在干净的兄弟决策集上把所有决策时预测器测到随机(1.5B RM / tfidf / 手工特征 /
frozen embedding / LLM judge;难区精确噪声上界 0.8962,self-report 0.6643 显著)。
审稿人最可能的反击是「critic 太弱」。你那边 pro6000 + 8B + 16384 ctx 是当前最干净的
上限测试:**打不过随机 → 负面主张对容量免疫;打得过 → 我们有正面结果**。两头都赢。

## 数据(集群路径,全部现成)

```
/research/d7/spc/yzyang4/aira-dojo/phase1/
  cards_current_v9.jsonl            # 14,323 节点,22 任务,含 code/graded/val_at_low/lineage/run_id
  value_pairs_runsplit.jsonl        # 前瞻对(训练主料,intask_split 字段分 train/test)
  decision_clean_b0.jsonl           # 兄弟决策对 K=0(1471 train + 1498/1499 test 行内 intask_split)
  decision_clean_b1.jsonl           # K=1 前瞻兄弟对(train+test)
  decision_clean_b2.jsonl           # K=2
  task_orientation.json             # 23 任务的 lower_is_better 表(奖牌几何审计过)
  card_run_map.json                 # 节点→物理 run
```

## 必须遵守的一条(公平契约)

**`decision_clean_b0.jsonl` 里 `intask_split=="test"` 的行是论文的冻结评测集,
绝不能进训练**(b1/b2 的 test 行同理)。切分是 run 级冻结 holdout:
`value-TRAIN runs ∩ decision-TEST runs = 0` 已验证;训练随便用所有 `train` 行。

## 建议配置(可自行调整,单 seed 先看方向)

| run | 模型 | ctx | 训练数据 | 目的 |
|---|---|---|---|---|
| R1 | Qwen3-8B | 16384 | value-pair train | 容量+ctx 主测 |
| R2 | 同上 | 16384 | + decision b0/b1/b2 train 混入 | 排除「训练分布不含决策对」 |
| R3 | qwen2.5-1.5B | 16384 | 同 R2 | 隔离容量变量 |

训练脚本可直接用 `phase1/rm_train_hf.py`(BT 成对损失,--lora --max-len 16384,
支持 ZeRO-3;--save-adapter 请开)。

## 评测(我们来跑,你只要给分)

对 b0/b1/b2 的 **test** 行逐对输出 0/1(1 = 模型把 `better` 排在 `worse` 前),存成:

```json
{"rm_8b_16k": {"<better_id>|<worse_id>": 1, ...}}
```

发回该 json(或放在 phase1/ 下任意文件名),我们的 `gap_strat4.py` 直接读进
分层表:难/易区 × 精确噪声上界 × parent 聚类 CI,和其他 15 个预测器同表可比。

## 背景数字(v9,供校准预期)

- 难区(gap<1e-2,751 对,占 50.1%):rm_1.5b 0.5128 / tfidf 0.5100 / self-report 0.6643;上界 0.8962(此集精确)
- 易区(747 对):rm_1.5b 0.5628 / self-report 0.7533;上界 0.9981
- K=1/K=2:现有一切预测器 ≈ 或低于随机(rm K=2 0.400 [0.309,0.493])
- 你 pairwise 训练时 0.6B/1.7B/4B 差别不大的观察,是「不是容量」的旁证;8B+16k 是它的上限延伸
