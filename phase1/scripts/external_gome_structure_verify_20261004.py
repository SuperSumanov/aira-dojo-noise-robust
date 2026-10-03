"""Independent structure recount. No source execution or score/feedback analysis."""
import hashlib
import json
from pathlib import Path
import time

ROOT = Path('/research/d7/spc/yzyang4/external-gome-structure-20261004-v1')


def run():
    started = time.time()
    summary = json.loads((ROOT/'structure.json').read_bytes())
    plan = json.loads((ROOT/'plan.json').read_bytes())
    assert summary['status'] == 'COMPLETE' and summary['completed_files'] == summary['assigned_files'] == 3
    duplicates = [0]
    def pairs_hook(pairs):
        keys = [key for key, value in pairs]
        duplicates[0] += len(keys)-len(set(keys))
        return dict(pairs)
    checked = []
    tasks = set()
    for row in summary['files']:
        name = row['file']
        expected = plan['files'][name]
        h = hashlib.sha256()
        with (ROOT/name).open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''):
                h.update(block)
        assert h.hexdigest() == row['sha256'] == expected['sha256']
        assert (ROOT/name).stat().st_size == expected['size'] == row['bytes']
        with (ROOT/name).open(encoding='utf-8') as f:
            data = json.load(f, object_pairs_hook=pairs_hook)
        tasks.update(data)
        assert sorted(data) == row['task_names']
        loops = [v for task in data.values() for k, v in task.items() if k != 'scenario']
        base = [v.get('base_code') for v in loops]
        code = [v.get('code') for v in loops]
        paired = [i for i, (b, c) in enumerate(zip(base, code)) if isinstance(b, str) and isinstance(c, str) and b.strip() and c.strip()]
        independent = {
            'tasks': len(data), 'loops': len(loops),
            'scenario_containers': sum('scenario' in task for task in data.values()),
            'base_code_present': sum('base_code' in v for v in loops),
            'code_present': sum('code' in v for v in loops),
            'base_code_is_string': sum(isinstance(v, str) for v in base),
            'code_is_string': sum(isinstance(v, str) for v in code),
            'nonempty_code_pairs': len(paired),
            'byte_equal_code_pairs': sum(base[i] == code[i] for i in paired),
            'has_final_hypothesis': sum(isinstance(v.get('final_hypothesis'), dict) for v in loops),
            'has_task_specification': sum(isinstance(v.get('task'), dict) for v in loops),
            'paired_with_intent_and_task': sum(isinstance(loops[i].get('final_hypothesis'), dict) and isinstance(loops[i].get('task'), dict) for i in paired),
        }
        assert independent == row['counts']
        checked.append({'file': name, 'all_count_fields_equal': True, 'sha256_pass': True})
        del data, loops, base, code
    assert duplicates[0] == 0 and sorted(tasks) == summary['unique_task_names']
    result = {'status': 'PASS', 'schema': 'external-gome-structure-verification-v1',
              'files': checked, 'duplicate_json_keys': duplicates[0],
              'unique_tasks': len(tasks),
              'total_loops': sum(r['counts']['loops'] for r in summary['files']),
              'total_nonempty_code_pairs_with_intent_and_task': sum(r['counts']['paired_with_intent_and_task'] for r in summary['files']),
              'elapsed_seconds': time.time()-started,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'summary_sha256': hashlib.sha256((ROOT/'structure.json').read_bytes()).hexdigest(),
              'boundary': 'Metadata recount after primary summary, not independent scientific review. No outcome/feedback analysis, source execution, source export or efficacy claim.'}
    with (ROOT/'verification.json').open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    run()
