"""Credential-free host evidence for a specific owned worker and descendants.

Read-only, no signals/limit changes. No cmdline, environment, code or labels.
Call on the host from the worker or pass its known host PID. Container PID
numbers cannot be guessed as host PIDs. A sample is not an atomic kernel census.
"""
import json,os,re,time
from pathlib import Path
import resource_pressure as host

LIMITS={'Max processes':'RLIMIT_NPROC','Max open files':'RLIMIT_NOFILE',
        'Max address space':'RLIMIT_AS','Max stack size':'RLIMIT_STACK'}

def parse_limits(text):
    result={}
    for line in text.splitlines():
        parts=re.split(r'\s{2,}',line.strip())
        if len(parts)<3 or parts[0] not in LIMITS:continue
        vals=parts[1:3]
        if not all(x.isdigit() or x=='unlimited' for x in vals):raise ValueError('non-numeric limit')
        result[LIMITS[parts[0]]]=[int(x) if x.isdigit() else x for x in vals]
    return result

def stat_identity(text):
    # comm may contain spaces and parentheses. Do not export it.
    pid=int(text.split('(',1)[0]);fields=text.rsplit(')',1)[1].split()
    return dict(pid=pid,ppid=int(fields[1]),start_ticks=int(fields[19]))

def numeric_status(text):
    fields=dict(x.split(':',1) for x in text.splitlines() if ':' in x)
    row=host.status_fields(text)
    for name in ('VmSize','VmPeak','VmRSS','VmHWM','VmData','VmStk'):
        value=fields.get(name,'').split()
        row[name+'_kib']=int(value[0]) if len(value)==2 and value[0].isdigit() and value[1]=='kB' else None
    ids=fields.get('NSpid','').split();row['namespace_pids']=[int(x) for x in ids] if all(x.isdigit() for x in ids) else []
    return row

def descendants(rows,root_pid):
    chosen={root_pid}
    while True:
        new={pid for pid,row in rows.items() if row['ppid'] in chosen}
        if new<=chosen:return chosen & rows.keys()
        chosen|=new

def process_record(directory,uid):
    before=stat_identity((directory/'stat').read_text())
    state=numeric_status((directory/'status').read_text())
    if state['uid']!=uid:raise PermissionError('different real UID')
    limits=parse_limits((directory/'limits').read_text())
    after=stat_identity((directory/'stat').read_text())
    if before!=after:raise ProcessLookupError('process identity changed during observation')
    return dict(**before,**{k:v for k,v in state.items() if k!='ppid'},limits=limits)

def snapshot(root_pid,proc=Path('/proc')):
    started=time.time();uid=os.getuid();root=proc/str(root_pid)
    first=process_record(root,uid)
    candidates={};unreadable=0
    for entry in proc.iterdir():
        if not entry.name.isdigit():continue
        try:
            # Never inspect another user's limits, command line or environment.
            if entry.stat().st_uid!=uid:continue
            fields=host.status_fields((entry/'status').read_text())
            if fields['uid']==uid:candidates[int(entry.name)]=fields
        except (OSError,KeyError,ValueError):unreadable+=1
    selected=descendants(candidates,root_pid);records=[];racing=[]
    for pid in sorted(selected):
        try:records.append(process_record(proc/str(pid),uid))
        except (OSError,KeyError,ValueError):racing.append(pid)
    try:
        last=process_record(root,uid)
        stable=(first['pid'],first['start_ticks'])==(last['pid'],last['start_ticks'])
    except (OSError,KeyError,ValueError):stable=False
    return dict(started=started,ended=time.time(),root_pid=root_pid,root_start_ticks=first['start_ticks'],
        root_identity_stable=stable,owned_descendants=records,unreadable_or_racing=racing,
        uid_scan_unreadable=unreadable,visible_descendant_threads=sum(x['threads'] for x in records),
        host_pressure=host.snapshot(),
        boundary='Sampled host real-UID and owned worker-descendant evidence,not atomic/exhaustive ucounts or EAGAIN causal proof. Supervisor and kernel limits can differ. Capture alongside the actual failure timestamp.')

if __name__=='__main__':
    import sys
    pid=int(sys.argv[1]) if len(sys.argv)>1 else os.getpid()
    print(json.dumps(snapshot(pid),sort_keys=True,allow_nan=False))
