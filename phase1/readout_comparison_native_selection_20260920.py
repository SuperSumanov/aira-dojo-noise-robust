"""Closed once-only diagnostic; original external grade is never a selector."""
import argparse,csv,json,os,re,subprocess
from pathlib import Path
from run_comparison_pool_native_selection_20260920 import rt,configure,safe,SOURCES,REWARD,REWARD_SHA,IDENTITY
from analyze_comparison_native_selection_20260920 import summarize

def join(cases,analyses,rewards,labels):
    tables=[]
    for values in (cases,analyses,rewards,labels):
        table={r['node']:r for r in values}
        if len(table)!=30 or len(values)!=30:raise ValueError('complete unique thirty')
        tables.append(table)
    if any(set(t)!=set(tables[0]) for t in tables):raise ValueError('population')
    rows=[]
    for case in cases:
        a,r,l=[t[case['node']] for t in tables[1:]]
        if any(any(row[k]!=case[k] for k in IDENTITY) for row in (a,r,l)):raise ValueError('identity join')
        if any(a[k]!=case[k] for k in ('index','request_seed','log_sha256','exit_code','timed_out')):raise ValueError('native input join')
        rows.append({k:case[k] for k in IDENTITY}|dict(index=case['index'],analysis_status=a['status'],
            native_accepted=a['native_accepted'],native_metric=a['native_metric'],native_is_bug=a.get('native_is_bug'),
            analysis_seconds=a['analysis_seconds'],wall_seconds=l['wall_seconds'],reward=r['reward'],inference_seconds=r['inference_seconds'],
            valid=l['valid'],score=l['score'],independent_score=l['independent_score'],exit_code=l['exit_code'],timed_out=l['timed_out']))
    return rows

def main(root,commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or commit=='0'*40:raise ValueError('commit')
    configure(root);p=rt.check_files();job=rt.read(root/'launch.json')['job']
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    a,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if a[1]!='COMPLETED' or a[3]!='gpu28' or not re.search(r'(?:^|,)gres/gpu=2(?:,|$)',a[4]) or int(a[2])>3000:raise ValueError('allocation not closed as planned')
    if rt.read(root/'closed.json')['status']!='all_thirty_analyses_closed' or rt.read(root/'analysis-complete.json')['cases']!=30:raise ValueError('analysis closure')
    service=rt.read(root/'service-native.json')
    if service['job']!=job or len(set(service['uuid']))!=2:raise ValueError('service identity')
    rt.write(root/'readout-claim.json',dict(utc=rt.utc(),reader_commit=commit,reader_sha256=rt.sha(Path(__file__)),prepared_sha256=rt.sha(root/'prepared.json')))
    cases=rt.read(root/'inputs.private.json')['cases'];analyses=[rt.read(root/f'analysis-{i}.json') for i in range(30)]
    reward=json.loads(safe(REWARD/'summary.json',REWARD_SHA));labels=[]
    for name,digest,seeds in SOURCES:
        labels.extend(row for row in json.loads(safe(rt.BASE/name/'summary.json',digest))['rows'] if row['seed'] in seeds)
    rows=join(cases,analyses,reward['rows'],labels);result=summarize(rows,reward['encoder']['load_seconds'])
    result.update(rows=rows,utc=rt.utc(),job=job,allocation_seconds=int(a[2]),gpu_hours=int(a[2])*2/3600,paid_api_calls=0,training=False,
        deployment_commit=p['commit'],reader_commit=commit,prepared_sha256=rt.sha(root/'prepared.json'),
        reward_summary_sha256=REWARD_SHA,source_summary_sha256={name:digest for name,digest,_ in SOURCES},
        analysis_sha256={str(i):rt.sha(root/f'analysis-{i}.json') for i in range(30)})
    digest=rt.write(root/'summary.json',result)
    with (root/'runs.csv').open('x',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(status=result['status'],job=job,summary_sha256=digest,runs_sha256=rt.sha(root/'runs.csv'),gpu_hours=result['gpu_hours'],pools=result['pools'],aggregate=result.get('aggregate')),allow_nan=False))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--reader-commit',required=True);a=p.parse_args();main(a.root,a.reader_commit)
