"""Export historical source locations for the producer, never raw experiment data."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

ROOT = Path('/research/d7/spc/yzyang4')
INPUTS = {
    'ledger': ('historical-source-ledger-faf04cc-20260905/source_ledger.private.json',
               '8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'),
    'lineage': ('historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json',
                'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981'),
    'scope': ('historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json',
              'fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b'),
}
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def h(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2).encode() + b'\n'

def load(name):
    path, sha = INPUTS[name]
    raw = (ROOT / path).read_bytes()
    require(h(raw) == sha, 'input_hash_drift')
    require(not SECRET.search(raw), 'input_credential_shape')
    return json.loads(raw)

def main():
    os.umask(0o077)
    ledger, lineage, scope = load('ledger'), load('lineage'), load('scope')
    selected = set(scope['selected_runs'])
    require(len(selected) == 84, 'fixed_scope_changed')
    covered = {t['run_id'] for m in lineage['manifests'] for t in m['tasks'] if t['run_id']}
    blocked = {lineage['closure'][rid]['component_sha256'] for rid in ledger if rid not in covered}
    for m in lineage['manifests']:
        if any(t['run_id'] is None or t['step_matches_recorded_config'] is False for t in m['tasks']):
            blocked.update(lineage['closure'][t['run_id']]['component_sha256'] for t in m['tasks'] if t['run_id'])
    recomputed = {r for r, v in lineage['closure'].items() if not v['old_hold_closure_blocks_train'] and v['component_sha256'] not in blocked}
    require(selected == recomputed, 'scope_binding_disagreement')
    grouped = defaultdict(list)
    for m in lineage['manifests']:
        if any(t['run_id'] in selected for t in m['tasks']):
            grouped[m['identity']['snapshot_path']].append(m)
    require(len(grouped) == 24, 'snapshot_scope_changed')
    rows = []
    union = set()
    for path, manifests in sorted(grouped.items()):
        require(PurePosixPath(path).is_absolute() and not any(c in path for c in ('\n', '\r', '|', '`')), 'invalid_path')
        runs = {t['run_id'] for m in manifests for t in m['tasks'] if t['run_id'] in selected}
        union.update(runs)
        try:
            path_state = 'accessible_directory' if Path(path).is_dir() else 'absent_on_linux5'
        except PermissionError:
            path_state = 'permission_denied_on_linux5'
        rows.append({
            'request_id': f'S{len(rows)+1:02d}',
            'recorded_snapshot_path': path,
            'recorded_python_executables': sorted({m['identity']['python_executable'] for m in manifests}),
            'recorded_pool_dirs': sorted({m['identity']['pool_dir'] for m in manifests}),
            'recorded_pool_created_at': sorted({m['identity']['created_at'] for m in manifests}),
            'instance_sha256': sorted({m['instance_sha256'] for m in manifests}),
            'fixed_scope_run_count': len(runs),
            'access_check_linux5': path_state,
        })
    require(union == selected, 'missing_run_binding')
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        'classification': 'PRODUCER_SOURCE_LOCATION_REQUEST_NOT_TRAINING_ADMISSION',
        'created_at_utc': now,
        'script_sha256': h(Path(__file__).read_bytes()),
        'input_sha256': {k: v[1] for k, v in INPUTS.items()},
        'fixed_runs': len(selected), 'snapshots': len(rows),
        'access_counts': dict(Counter(r['access_check_linux5'] for r in rows)),
        'raw_archives_opened': 0, 'journal_payloads_opened': 0,
        'source_snapshots_opened': 0, 'model_fits_started': 0,
        'training_qualified': False,
    }
    doc = ['# 供学长私下核对：24份历史生产快照定位清单', '',
           '请勿上传含密钥的快照或环境文件。本清单仅供定位原代码/依赖/外部评分记录，不需重传语料。',
           '请在每个S编号旁回复可访问副本位置；若不可恢复，明确写不可恢复即可，不必补造记录。',
           '路径是原清单记载，不代表当前机器存在，也不证明当时实际执行了该环境。',
           '这些84个run仍不是合格训练集；另需真实experiment边界和历史开发资格。', '',
           f'核查UTC：{now}', '当前核查机器：linux5。不要把本机不存在理解为所有生产机均不存在。', '',
           '|编号|固定范围run数|linux5状态|原snapshot路径|', '|---|---:|---|---|']
    for r in rows:
        doc.append(f"|{r['request_id']}|{r['fixed_scope_run_count']}|{r['access_check_linux5']}|`{r['recorded_snapshot_path']}`|")
    doc.extend(['', '## 对应启动位置和解释器（协助定位）', ''])
    for r in rows:
        doc.extend([f"### {r['request_id']}", '',
                    '清单创建时间：' + ', '.join(r['recorded_pool_created_at']), '',
                    *['- Pool：`'+v+'`' for v in r['recorded_pool_dirs']],
                    *['- Python：`'+v+'`' for v in r['recorded_python_executables']], ''])
    doc.extend(['## 还请一并说明', '',
                '1. 上述运行实际使用的MLE-bench commit、已有修改及外部评分执行记录在哪里；安装README或今天的环境版本不替代历史事实。',
                '2. 是否存在跨这些启动批次共享的experiment，以及其现成映射位置；未知请保留未知。',
                '3. 是否允许这一固定历史范围用于开发；不占用first-960/Target-300/Target-522。',
                '4. 若旧快照已删除，可否提供另一个已有完整来源且不涉及保护确认人口的开发包。不要仅把新run改目录/标签就当隔离。', '',
                '这份文档可直接转发，不要求学长访问我方私人研究盘。仅定位元数据，未导出程序、标签或结果。', ''])
    outputs = {'snapshot_locations_for_senior.private.json': canonical({**meta, 'requests': rows}),
               'snapshot_locations_for_senior.private.md': '\n'.join(doc).encode('utf-8')}
    for raw in outputs.values():
        require(not SECRET.search(raw), 'output_credential_shape')
    out = ROOT / 'snapshot-source-request-20260906'
    require(not out.exists(), 'output_already_exists')
    out.mkdir(mode=0o700)
    for name, raw in outputs.items():
        with (out / name).open('xb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        (out / name).chmod(0o400)
    meta['files'] = {name: {'bytes': len(raw), 'sha256': h(raw)} for name, raw in outputs.items()}
    with (out / 'summary.json').open('xb') as f:
        f.write(canonical(meta))
    (out / 'summary.json').chmod(0o400)
    out.chmod(0o500)
    print(json.dumps(meta, sort_keys=True))

if __name__ == '__main__':
    main()
