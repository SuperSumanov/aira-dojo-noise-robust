"""Extract only stack categories and scoped device samples; never source/locals."""
import re,statistics
SECRET=re.compile(r'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|bearer\s+\S{12,})')

def stack_evidence(raw):
    hits=len(SECRET.findall(raw));raw=SECRET.sub('[REDACTED]',raw)
    dumps=[];current=None;group=None
    for line in raw.splitlines():
        if line.startswith('Timeout ('):
            current=dict(ordinal=len(dumps),threads=[]);dumps.append(current);group=None;continue
        if line.startswith(('Thread ','Current thread ')) and current is not None:
            group=dict(frames=[],kernel_cell=False);current['threads'].append(group);continue
        if group is None:continue
        match=re.search(r'File "([^"\n]+)", line (\d+)(?:,)? in ([A-Za-z0-9_<>]+)',line)
        if not match:continue
        path,num,fn=match.groups();package=None
        if '/tmp/ipykernel_' in path or path.startswith('<ipython-input'):
            package='candidate';leaf='<withheld>';fn='<withheld>';group['kernel_cell']=True
        else:
            leaf=path.rsplit('/',1)[-1]
            for fragment,label in [('torch/utils/data/','torch-data'),('torch/nn/','torch-nn'),('/torch/','torch'),('/IPython/','IPython'),('/ipykernel/','ipykernel'),('/numpy/','numpy'),('/multiprocessing/','multiprocessing')]:
                if fragment in path:package=label;break
            if leaf in ('threading.py','queue.py','selectors.py','select.py','socket.py'):package='stdlib'
            if package=='IPython':group['kernel_cell']=True
        if package and re.fullmatch(r'[A-Za-z0-9_.<>-]{1,100}',leaf) and re.fullmatch(r'[A-Za-z0-9_<>]{1,100}',fn):
            group['frames'].append(dict(package=package,module=leaf,line=int(num),function=fn))
    for dump in dumps:
        for thread in dump['threads']:
            frames=thread['frames']
            thread['category']='dataloader_wait' if thread['kernel_cell'] and any(x['package']=='torch-data' and x['function'] in ('_next_data','_try_get_data','_get_data') for x in frames) else 'torch_compute' if thread['kernel_cell'] and any(x['package']=='torch-nn' for x in frames) else 'other'
    return dict(credential_shape_hits_redacted=hits,dumps=dumps,
        boundary='Parent-kernel thread stacks only;30s nominal watchdog interval, actual emission times unavailable. A single waiting stack does not prove deadlock. No local variables or source lines.')

def gpu_evidence(rows,start,end):
    scope=[r for r in rows if start<=r['time']<=end]
    valid=[r for r in scope if r.get('query_ok') and r['values']['utilization.gpu']!='[N/A]']
    util=[float(r['values']['utilization.gpu']) for r in valid]
    assert all(0<=x<=100 for x in util)
    times=sorted(r['time'] for r in valid)
    return dict(samples_in_call=len(scope),valid_utilization_samples=len(valid),
        utilization_min=min(util) if util else None,utilization_max=max(util) if util else None,
        utilization_median=statistics.median(util) if util else None,
        maximum_sample_gap=max([b-a for a,b in zip(times,times[1:])],default=None),
        sample_span_fraction=(times[-1]-times[0])/(end-start) if len(times)>1 and end>start else None,
        boundary='Assigned device, sampled whole-GPU utilization during the candidate execute call, not per-process kernel time; errors/missing values are not zero.')
