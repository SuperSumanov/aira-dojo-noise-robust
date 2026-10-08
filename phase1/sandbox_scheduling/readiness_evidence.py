"""Read only closed 17021 handshake evidence; never export raw private logs."""
import ast
from collections import Counter
import json
from pathlib import Path
import re
from lifecycle_pilot import read,sha,SECRET

ROOT=Path('/research/d7/spc/yzyang4/scheduling-neural-overlap-retry-20261008-v2')
PIN='528026478eff9138b06ff53023d5793139ea3bd9246fc3082cc3d749c8c25dfc'
EVENTS={
 'waiting_ready':'Waiting for ready',
 'kernel_not_ready':'Kernel did not become ready in time',
 'client_created':'Kernel client ',
 'starting_kernel':'Starting kernel ',
 'getting_kernel_client':'Getting kernel client',
 'executing_code':'Executing code',
 'websocket_error':'WebSocket error:',
 'connection_closed':'Connection to remote host was lost',
 'address_in_use':'Address already in use',
 'kernel_died':'KernelRestarter',
 'received_kernel_reply':'kernel_info_reply',
 'unauthorized':'401 Unauthorized',
 'forbidden':'403 Forbidden',
 'connection_refused':'Connection refused',
}

def main():
 if sha(ROOT/'plan.json')!=PIN or not (ROOT/'closed.json').exists():raise ValueError('scope not closed')
 result=dict(job=read(ROOT/'launch.json')['job'],plan_sha256=PIN,analysis_sha256=sha(__file__),episodes=[])
 for index in (0,1,6,7,8,9):
  ep=ROOT/f'episode-{index}'
  raw=(ep/'worker.private.log').read_bytes()
  credential_hits=len(SECRET.findall(raw))
  # Only named event counts/order are emitted. No line text, URLs or messages.
  events=[name for line in raw.decode('utf-8',errors='replace').splitlines()
          for name,needle in EVENTS.items() if needle in line]
  result['episodes'].append(dict(index=index,credential_shape_hit_count=credential_hits,
   event_counts=dict(Counter(events)),event_order=events,
   candidate_started=(ep/'candidate_started.json').exists(),
   complete=read(ep/'completed.json').get('complete'),
   returncode=read(ep/'closed.json')['returncode']))
 source=ROOT/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py'
 raw=source.read_bytes()
 if SECRET.search(raw):raise ValueError('source credential hit; no source export')
 tree=ast.parse(raw)
 cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='JupyterKernelClient')
 selected=[]
 for name in ('wait_for_ready','_on_error','_on_close'):
  node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
  selected.append(dict(name=name,source=ast.get_source_segment(raw.decode(),node)))
 result.update(client_source_sha256=sha(source),client_methods=selected,
  boundary='Allowlisted event trace only; absence of logged events is not proof of network/kernel health. Source properties and hypothetical message-loss behavior are not a causal diagnosis of this run.')
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
