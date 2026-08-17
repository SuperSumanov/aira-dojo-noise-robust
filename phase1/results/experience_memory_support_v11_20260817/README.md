# Experience-memory support audit v1

日期：2026-08-17。状态：`VERIFIED_SUPPORT_WITH_GENERALIZATION_LIMITS`。

本审计只回答 v11 是否有足够、且与 frozen decision test 无 physical-run 交集的历史材料，支撑后续
evaluator-verified experience memory 研究。它不是方法效果实验，不改变当前 score-channel 主实验，
没有读取前瞻 outcome、原始 journal、异常文本、stdout 或环境变量；GPU=0，API=0。

## 锁定输入与复现

```text
cards_current_v11.jsonl  sha256=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
decision_clean_b0.jsonl sha256=a04b5b805d0bc59b068cbb4df52bcbf23ea429f1b552022829671483eb6d1909
decision_clean_b1.jsonl sha256=c2e38643cf2bb78e207964252af4f665961ab81416a762def04226b07c0d9258
decision_clean_b2.jsonl sha256=10cbcc86ea8e5861eea3ad6da183e3dac5579533ee8be9890277be98f5de0903
failure summary          sha256=4d094aa119c25c2f0639fc4315e70e85b297f3d9afd808b0a39d15726b17fedc
```

复现命令：

```bash
python phase1/audit_experience_memory_support.py . \
  --out phase1/results/experience_memory_support_v11_20260817/audit.json
python -m pytest phase1/tests/test_experience_memory_support.py -q
```

两次独立进程输出逐字节相同，`audit.json` SHA256=
`769acc3d198dadb5643e3557f57c738967806546e212c258d0de51ad794a53f0`；聚焦测试为 `1 passed`。
本地完整测试在 collection 阶段因环境缺少 `scikit-learn` 中止；随后在远端精确 base commit
`858785fcdea77f2e4e1e8688970a0900a2917f36` 的一次性 clean worktree、既有实验环境中补入本轮两个文件，
完整 `phase1/tests` 为 `340 passed in 34.18s`。worktree 已验证清理。

## 精确结果

- 三份 `decision_clean_b*` 共 2,087 行，全部是 `intask_split=test`；涉及 2,030 个 endpoint、
  92 个 physical runs、22 个任务。
- 只要一个 frozen endpoint 属于某 run，就排除该 run 的全部卡片。排除后 memory pool 为
  12,316 cards / 575 physical runs / 25 tasks；endpoint overlap=0、physical-run overlap=0、
  非空代码精确 SHA overlap=0。
- 以已经方向归一化的 `y_norm` 选每 run 最优成功 episode，共 575 个；其中 567/575=0.986087
  的代码含静态 artifact-writer marker。该 marker 只是静态文本规则，不冒充执行验证。
- 22/22 frozen tasks 至少有一个同任务成功 episode，21/22 至少有 5 个；因此只支持 seen-task
  memory baseline，不支持 unseen-task 泛化。
- 训练侧 769 个 missing sibling identities 中恢复 699 个状态，691 为 `EXECUTION_ERROR`、8 为
  `OFFICIAL_GRADE_ABSENT`，仍有 70 个未恢复。registry 不含可行动的错误诊断。
- memory 卡片中非平凡任务描述为 0；现有 schema 只有任务 ID/类型等元数据，不能据此声称语义检索能力。

## 裁决

允许：构建严格 train-only、物理 run 隔离的成功/失败数据资产与未来预注册。

不允许：声称通用 learned harness、未见任务迁移、因果方法收益，或据此直接启动付费实验。
