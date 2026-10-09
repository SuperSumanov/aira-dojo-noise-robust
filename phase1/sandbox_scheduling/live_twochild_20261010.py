"""New common-baseline study, NOT a repair or continuation of v7/exposure.

Both policies use 2 children and 1500s fresh search. Only within-study FIFO
execution permits 1/2 differ. The 600s/root5 results cannot be pooled with this.
ABBA16 assignments, 4x2300s all-pool slots, 3GPUsx160min <=8GPUh.
"""
import inspect
import sys
import live_27b_trial

t=live_27b_trial.trial
t.R=t.B/'scheduling-live-twochild-20261010-v1'
t.NAME='live_twochild_20261010.py'
t.CAP=9600;t.FIXED_BLOCK_SECONDS=2300
t.PHYSICAL_CPU_BINDING=True;t.NODE_QUALIFICATION=False
t.GENERATOR_ELIGIBILITY_GATE=False;t.SEED_BASE=175001
t.FILES=(t.NAME,'test_live_twochild.py')+t.FILES


def transform(source,before,after,count=1):
    if source.count(before)!=count:raise ValueError('literal interface drift: '+before)
    return source.replace(before,after)


def host_source(source):
    source=transform(source,'m.SECONDS=600','m.SECONDS=1500')
    anchor="    exec(compile(source,'live-native-worker','exec'),m.__dict__)"
    insertion="    source=replace_once(source,\"TIME_LIMIT='10 minutes',TIME_LIMIT_SECS='600'\",\"TIME_LIMIT='25 minutes',TIME_LIMIT_SECS='1500'\")\n"
    return transform(source,anchor,insertion+anchor)


def prepare_source(source):
    anchor="        cfg['solver']['checkpoint_path']=str(ep/'checkpoint')"
    source=transform(source,anchor,anchor+"\n        cfg['solver'].update(num_children=2,time_limit_secs=1500)")
    source=transform(source,'--time=01:30:00','--time=02:40:00')
    source=transform(source,'5320s','9520s')
    source=transform(source,'gpu_hours_cap=4.5','gpu_hours_cap=8.0',count=2)
    source=transform(source,'run_seconds=600','run_seconds=1500')
    anchor="        active_runs=4,rolling_replacement=False,service_restart_between_blocks=True,"
    source=transform(source,anchor,anchor+"\n        common_baseline='New2-child/1500s configuration shared by both policies; not comparable as treatment against oldroot5/600s.',\n        rationale='Senior24efc2e0 outcome uses2 children; this borrows breadth only, not its9B/SFT/memory/data or24h result. Previous50min root5 pilot has a repeated local gain but failed cross-task qualification. No proof this setting is more effective.',\n        preflight_items=['exact fresh source/seeds','paired policy configs equal','same public-dev inputs/scorer','no hidden/test paths','pinned unchanged model/image','same12+6 physical CPU and2+1GPU','4 whole2300s slots incl cold service/idle','all16 outcomes and failures','no retries or seed replacements','identity cleanup before next block','8GPUh noAPI/base update'],")
    return source


def controller_source(source):
    source=transform(source,'--time=00:25:00','--time=00:40:00')
    source=transform(source,'--time=00:13:00','--time=00:30:00')
    source=transform(source,'remaining=800 if not FIXED_BLOCK_SECONDS else min(800,','remaining=1700 if not FIXED_BLOCK_SECONDS else min(1700,')
    source=transform(source,'if remaining<690:','if remaining<1590:')
    return transform(source,"['elapsed_seconds']<=600","['elapsed_seconds']<=1500")


for name,fn in (('host',host_source),('prepare',prepare_source),('controller',controller_source)):
    exec(compile(fn(inspect.getsource(getattr(t,name))),'twochild-'+name,'exec'),t.__dict__)
exec(compile(transform(inspect.getsource(t.run_one),'timeout=690','timeout=1590'),'twochild-supervisor','exec'),t.__dict__)
source=transform(inspect.getsource(t.cpu),'cfg.solver.time_limit_secs!=600','cfg.solver.time_limit_secs!=1500 or cfg.solver.num_children!=2')
exec(compile(source,'twochild-cpu','exec'),t.__dict__)
exec(compile(transform(inspect.getsource(t.submit),'gpu_hours_cap=4.5','gpu_hours_cap=8.0',count=2),'twochild-submit','exec'),t.__dict__)


def host():return t.host()


if __name__=='__main__':sys.exit(t.main())
