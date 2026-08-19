# E2-A DeBERTa 安全权重等价审计

该目录保存 2026-08-19 E2-A warm 环境失败后的结果前工程审计，不含分数、标签或科学 outcome。

- 审计器：`phase1/verify_safetensors_equivalence.py`；
- receipt：`tensor_equivalence.json`；
- receipt SHA256：`2156d53785303a4f203682e7c0eba7c9123ae63fe6f397d5473eee4444d25c01`；
- 结论：210/210 tensors 的 keys、shape、dtype 和 bitwise values 完全一致；
- 安全边界：原 PyTorch blob 只在 PyTorch 2.11 下以 `weights_only=True` 加载，脚本拒绝 PyTorch <2.6。

该结果只授权把同一权重改用 safetensors 封装；不授权改变任务、候选代码、timeout、样本或科学门槛。
