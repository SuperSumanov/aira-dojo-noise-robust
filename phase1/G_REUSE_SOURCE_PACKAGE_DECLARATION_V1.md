# G-reuse 同producer来源包：声明与验收接口 v1

这是学长交付历史开发包时的包级入口，不是来源真伪的自动证明，也不授权训练。

manifest 顶层必须且只能包含：`protocol, package_id, producer, declarations, artifacts`。七个artifact角色必须各出现一次：
`cards, global_pairs, local_pairs, split_manifest, source_provenance, producer_receipt, evaluator_receipt`。
每项固定为 `role,path,bytes,sha256,lfs_oid_sha256`；LFS OID未知时显式为null。

`producer`固定字段为：`producer_commit, stable_release_id, exact_config_stratum_id`。`declarations`固定字段为：
`historical_development_only=true, whole_experiment_split_declared=true, source_provenance_schema=source-declaration-v2`。
manifest与两个小receipt都拒绝重复JSON key、未知字段和credential shape；所有路径必须是包根内不同的普通文件，
拒绝symlink、hardlink alias、traversal、大小/SHA漂移和角色缺失。

producer receipt仅允许：`protocol,producer_commit,stable_release_id,exact_config_stratum_id,command_argv_sha256,
instance_manifest_sha256,run_count,executed_at_utc`；它必须与manifest三项producer声明一致。evaluator receipt仅允许：
`protocol,evaluator_commit,evaluator_id,score_schema_id,execution_records_sha256`。命令、key和真实payload不写入小receipt。

成功状态故意是`PACKAGE_DECLARATION_HASH_BOUND_NOT_EFFECT_ELIGIBLE`：它只证明包结构、bytes/hash及两份声明互相一致；
不能证明producer commit真的执行、config真实、run实例独立、evaluator pristine或split确实按whole experiment隔离。
后续仍必须运行`validate_senior_source_provenance_v2.py`、解析物化文件并做pair/card/run零交集、config与执行回执核验，
再做结果盲功效检查。任何一项缺失都不能把`g_reuse_effect_protocol_v1.json`的pending contract改成true。

