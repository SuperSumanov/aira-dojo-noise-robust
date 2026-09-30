"""Describe parser-rejection components without reading score values.

Intervals are timestamp spans in already-observed logs, NOT saved GPU time,
generation latency, or counterfactual search utility. No rows are excluded from
the original comparison. A directory is not certified as an independent run.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

EVENTS_SHA = '401d36b7af50b8cacc515c69758f4e3141b87a5f3f0f3359ea6a39fe4af7f469'
TRACE_SHA = 'b419063798df48d75875e28c4d8f32143a851ac362f0e6cdba1715f5825ed7c8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(census, events):
    index = {}
    for event in events:
        key = (event['run_digest'], event['segment'], event['step'])
        assert key not in index
        # Deliberate allowlist: never inspect score/metric/fitness fields.
        index[key] = {k: event[k] for k in ('timestamp', 'exec_seconds', 'exit_code', 'operator', 'parent_steps')}
    rows = {}
    for row in census['rows']:
        key = (row['run_digest'], row['segment'], row['step'])
        assert key not in rows and key in index
        assert index[key]['parent_steps'] == [row['parent_step']]
        assert index[key]['operator'] == row['operator']
        rows[key] = row
    rejected = {key for key, row in rows.items() if row['generic_feedback_exact']}
    groups = collections.defaultdict(list)
    for key in sorted(rejected):
        current = key
        visited = set()
        while current in rejected:
            assert current not in visited
            visited.add(current)
            parent = (*current[:2], rows[current]['parent_step'])
            assert parent[2] < current[2]
            if parent not in rejected:
                entry = current
                break
            current = parent
        assert index[key]['exec_seconds'] == 0 and index[key]['exit_code'] == 0
        groups[entry].append(key)
    components = []
    for entry, keys in sorted(groups.items()):
        stamps = [dt.datetime.fromisoformat(index[key]['timestamp']) for key in keys]
        first = dt.datetime.fromisoformat(index[entry]['timestamp'])
        assert min(stamps) == first
        keyset = set(keys)
        boundary_children = [key for key, row in rows.items()
                             if (*key[:2], row['parent_step']) in keyset and key not in keyset]
        components.append({
            'run_digest': entry[0], 'segment': entry[1], 'entry_step': entry[2],
            'task': rows[entry]['task'], 'arm': rows[entry]['arm'], 'seed': rows[entry]['seed'],
            'entry_operator': rows[entry]['operator'], 'rejected_actions': len(keys),
            'debug_actions': sum(rows[key]['operator'] == 'debug' for key in keys),
            'internal_parent_edges': len(keys)-1,
            'recorded_nonrejected_children': len(boundary_children),
            'first_to_last_logged_rejection_seconds': (max(stamps)-first).total_seconds(),
            'logged_execution_seconds': sum(index[key]['exec_seconds'] for key in keys),
        })
    strata = []
    for task, arm in sorted({(r['task'],r['arm']) for r in rows.values()}):
        selected = [(key,r) for key,r in rows.items() if (r['task'],r['arm']) == (task,arm)]
        bad = [(key,r) for key,r in selected if key in rejected]
        strata.append({'task':task,'arm':arm,'all_logged_actions':len(selected),
                       'parser_rejections':len(bad),
                       'directories':len({key[0] for key,r in selected}),
                       'affected_directories':len({key[0] for key,r in bad}),
                       'debug_rejections':sum(r['operator']=='debug' for key,r in bad)})
    return {'counts':{'logged_actions':len(rows),'parser_rejections':len(rejected),
                       'affected_directories':len({key[0] for key in rejected}),
                       'rejection_components':len(components),
                       'internal_parent_edges':sum(c['internal_parent_edges'] for c in components),
                       'recorded_nonrejected_children':sum(c['recorded_nonrejected_children'] for c in components)},
            'components':components,'strata':strata}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--census',type=Path,required=True)
    inputs=ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--events',type=Path)
    inputs.add_argument('--numeric-trace',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    census=json.loads(args.census.read_text())
    if args.events:
        assert sha(args.events)==EVENTS_SHA
        events=json.loads(args.events.read_text());input_path=args.events;input_kind='original_event_table'
    else:
        assert sha(args.numeric_trace)==TRACE_SHA
        bykey={(r['run_digest'],r['segment'],r['step']):r for r in census['rows']}
        events=[]
        for run in json.loads(args.numeric_trace.read_text()):
            segment=0
            for node in run['nodes']:
                if node['step']==0:segment+=1;continue
                key=(run['run_digest'],segment,node['step']);c=bykey[key]
                events.append(dict(run_digest=key[0],segment=key[1],step=key[2],
                    timestamp=node['timestamp'],exec_seconds=node['exec_seconds'],exit_code=node['exit_code'],
                    operator=c['operator'],parent_steps=[c['parent_step']]))
        input_path=args.numeric_trace;input_kind='published_trace_joined_to_raw_census'
    result=analyze(census,events)
    result.update({'status':'DESCRIPTIVE_ONLY','census_sha256':sha(args.census),'context_sha256':sha(input_path),'context_kind':input_kind,
                   'script_sha256':sha(Path(__file__)),
                   'boundary':'Repeated logged rejections, not independent trials. Log spans are not compute savings. No scores read or outcome-dependent exclusion.'})
    with args.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
