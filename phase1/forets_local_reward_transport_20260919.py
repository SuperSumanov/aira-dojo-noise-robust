"""Local-only, no-retry, full-code transport for a FUTURE frozen-critic search.

Model ownership/readiness is supplied by the paired supervisor; this module is
not a launcher. Uniform arms retain their normal no-scoring behavior. Complete
pool and uncertain-call handling remain in the actual CandidateLedger runtime.
"""
import json,math,time,urllib.request

def validate_config(solver):
    cfg=solver.cfg
    if cfg.cheap_ranker!='none' or cfg.critic_max_attempts!=1:raise ValueError('no alternate ranker or critic retries')
    if solver.critic_host!='127.0.0.1' or type(solver.critic_port) is not int or not 1024<=solver.critic_port<=65535:raise ValueError('owned loopback critic only')

def request_score(task,code,*,host,port,deadline_ns,clock_ns=time.monotonic_ns,opener=None):
    if host!='127.0.0.1' or type(port) is not int or not 1024<=port<=65535:raise ValueError('loopback endpoint')
    if not isinstance(task,str) or not task or not isinstance(code,str) or not code:raise ValueError('task and full code required')
    remaining=(deadline_ns-clock_ns())/1e9
    if remaining<=0:raise TimeoutError('critic deadline before request')
    request=urllib.request.Request(f'http://{host}:{port}/score',json.dumps(dict(task=task,code=code)).encode(),{'Content-Type':'application/json'})
    if opener is None:opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # No inherited HTTP proxy, key, task result or extra clipping. The frozen
    # server's task-conditioned tokenizer remains the only input truncation.
    with opener.open(request,timeout=min(600.,remaining)) as response:
        raw=response.read(65537)
    if len(raw)>65536:raise ValueError('oversized critic reply')
    value=json.loads(raw)['score']
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite numeric critic score required')
    if clock_ns()>=deadline_ns:raise TimeoutError('critic reply after search deadline')
    return float(value)

async def rank_nodes(solver,nodes):
    validate_config(solver)
    from dojo.solvers.fore_ts.wallclock import budget
    spec=budget()
    if spec is None:raise ValueError('explicit shared search clock required')
    values=[]
    for node in nodes:
        values.append(request_score(solver.task_name,node.code,host=solver.critic_host,port=solver.critic_port,deadline_ns=spec[1]))
    return values
