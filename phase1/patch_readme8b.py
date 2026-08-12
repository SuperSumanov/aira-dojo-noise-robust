"""README_8B.md pointed the senior at cluster paths he cannot read; his channel is the git
repo (LFS). Rewrite the data section to repo-relative paths + lfs pull, and replace the R2
suggestion -- his 0812 outcomes doc already ran the decision+value 1:1 mix on the old data
and it LOST 1.13pp, so asking again would ignore his result. What remains valuable is
scoring his existing checkpoints on the clean per-K test rows, and optionally one clean
per-K retrain.
"""
P = "phase1/README_8B.md"
s = open(P, encoding="utf-8").read()

a = """## 数据(集群路径,全部现成)

```
/research/d7/spc/yzyang4/aira-dojo/phase1/
  cards_current_v9.jsonl            # 14,323 节点,22 任务,含 code/graded/val_at_low/lineage/run_id
  value_pairs_runsplit.jsonl        # 前瞻对(训练主料,intask_split 字段分 train/test)
  decision_clean_b0.jsonl           # 兄弟决策对 K=0(1471 train + 1498/1499 test 行内 intask_split)
  decision_clean_b1.jsonl           # K=1 前瞻兄弟对(train+test)
  decision_clean_b2.jsonl           # K=2
  task_orientation.json             # 23 任务的 lower_is_better 表(奖牌几何审计过)
  card_run_map.json                 # 节点→物理 run
```"""
assert a in s, "data section anchor not found"
b = """## 数据(全部在本分支 `phase1/`,大文件走 LFS)

```bash
git checkout phase1-value-critic && git lfs pull
```

```
phase1/
  cards_current_v9.jsonl            # 14,323 节点,22 任务,含 code/graded/val_at_low/lineage/run_id(LFS)
  value_pairs_runsplit.jsonl        # 前瞻对(训练主料,intask_split 字段分 train/test)(LFS)
  decision_clean_b0.jsonl           # 兄弟决策对 K=0(3777 train + 1498 test,行内 intask_split)
  decision_clean_b1.jsonl           # K=1 前瞻兄弟对(train+test)
  decision_clean_b2.jsonl           # K=2
  task_orientation.json             # 23 任务的 lower_is_better 表(奖牌几何审计过)
  card_run_map.json                 # 节点→物理 run
```"""
s = s.replace(a, b)

c = """| R2 | 同上 | 16384 | + 决策对 train 混入(decision_clean_b0 的 3777 train 对) | 排除「训练分布不含决策对」 |"""
if c in s:
    s = s.replace(c, """| R2 | 同上 | 16384 | + 决策对 train 混入 | ~~已由你 0812 文档回答~~:旧数据上 1:1 混合 −1.13pp,**跳过**;若重试建议用拆干净的 per-K train |""")

d = "## 评测(我们来跑,你只要给分)"
assert d in s
s = s.replace(d, """## 最省事的路径(优先):直接评现有 checkpoint

不用重训:把你 0812 那批里最好的 1-2 个 checkpoint(Qwen3-4B/8B base)对
`decision_clean_b0/b1/b2.jsonl` 中 `intask_split=="test"` 的行逐对打分即可。
你的模型在旧 train 侧训练,对这些 test 行干净(run 级冻结切分,零交集已验证)。

## 评测(我们来跑,你只要给分)""")

open(P, "w", encoding="utf-8").write(s)
print("patched", P)
