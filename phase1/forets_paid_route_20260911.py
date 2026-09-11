"""Two actual strict-tool fixtures per block, all charged to the same ledger."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import io
import json
import os
import subprocess
import sys

from forets_paid_budget_20260911 import AUTH, AUTH_SHA, MODEL, snapshot


def catalog_valid(entry):
    endpoints = entry.get('data',{}).get('endpoints',[])
    matches = [x for x in endpoints if x.get('tag')=='alibaba']
    if len(matches)!=1:
        raise ValueError('exact provider absent')
    e=matches[0]
    if (e.get('context_length')!=1000000 or e.get('max_completion_tokens',0)<8192
            or not {'tools','tool_choice'}<=set(e.get('supported_parameters',[]))
            or e.get('supports_tool_choice',{}).get('function') is not True):
        raise ValueError('model capability changed')
    from decimal import Decimal
    pricing=e['pricing']
    tiers=[pricing]+pricing.get('overrides',[])
    for tier in tiers:
        for name,limit in [('prompt','0.00000065'),('completion','0.0000026'),
                            ('input_cache_read','0.00000065'),('input_cache_write','0.00000065')]:
            if name in tier:
                val=Decimal(str(tier[name]))
                if not val.is_finite() or not 0<=val<=Decimal(limit):
                    raise ValueError('endpoint price changed')
        for name,val in tier.items():
            if name not in {'prompt','completion','input_cache_read','input_cache_write','overrides','min_prompt_tokens'}:
                if Decimal(str(val))!=0:
                    raise ValueError('unpriced billing dimension')
    return dict(model=MODEL,provider='alibaba',context_tokens=e['context_length'],
                price_bound_verified=True,named_tools_supported=True)


def route(directory, block):
    from forets_native_run_20260911 import static_ready
    from forets_native_context_20260911 import ROOT
    from forets_block_runtime_20260911 import write_once
    from forets_stage_gate import validate_route_receipt
    from forets_e2e_campaign import install_process_credential
    raw,commit=static_ready(directory,block)
    target=ROOT/f'block-{block}.route.json'
    output=ROOT/f'block-{block}.route-check'
    if target.exists() or output.exists():
        raise ValueError('route window already attempted; cannot overwrite or retry')
    state=snapshot(ROOT/'paid.sqlite')
    if state['stopped']: raise RuntimeError('campaign billing stopped')
    os.environ.update(FORETS_PAID_LEDGER=str(ROOT/'paid.sqlite'),FORETS_PAID_SCOPE='route')
    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        install_process_credential()
        import httpx
        with httpx.Client(timeout=30,follow_redirects=False) as client:
            response=client.get('https://openrouter.ai/api/v1/models/'+MODEL+'/endpoints')
            response.raise_for_status()
            checked=catalog_valid(response.json())
    write_once(ROOT/f'block-{block}.catalog.json',checked|dict(
        utc=datetime.now(timezone.utc).isoformat(),authorization_sha256=AUTH_SHA,controller_commit=commit))
    result=subprocess.run([sys.executable,'-B',str(directory/'check_forets_resilience_live_20260910.py'),
        '--source',str(ROOT/'source'),'--package',str(ROOT),'--output',str(output),
        '--max-attempts','1'],capture_output=True,text=True,timeout=280)
    report=json.loads((output/'finished.json').read_text()) if (output/'finished.json').exists() else {}
    state=snapshot(ROOT/'paid.sqlite')
    write_once(ROOT/f'block-{block}.route-cost.json',state)
    if (result.returncode or report.get('status')!='READY' or state['stopped'] or state['unresolved']):
        print(json.dumps(dict(status='PAID_ROUTE_NOT_READY_NO_GPU',block=block,
            report=str(output/'finished.json'),returncode=result.returncode,billing=state)),flush=True)
        return 2
    report['paid_authorization_sha256']=AUTH_SHA
    report['paid_ledger']=str(ROOT/'paid.sqlite')
    write_once(target,report)
    validate_route_receipt(target,ROOT/'source')
    print(json.dumps(dict(status='PAID_ROUTE_READY',block=block,billing=state,receipt=str(target))),flush=True)
    return 0
