import ast,json,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/implementation-reset-20261005-v1')
assert (R/'closed.json').exists()
sys.path.insert(0,str(R))
from implementation_reset_20261005 import read,write,structural_idea_check
rows=[]
for i in range(4):
    for ap in sorted((R/f'episode-{i}').glob('action-*')):
        gp=ap/'generation.private.json';cp=ap/'code.private.json'
        if not gp.exists():continue
        g=read(gp);messages=g.get('info',{}).get('prompt_messages',[])
        text='\n'.join(str(m.get('content','')) for m in messages)
        row={'index':i,'action':ap.name,'fixed_idea_in_actual_prompt':'sparse word TF-IDF' in text,
             'forbidden_extra_family_instruction_present':'No additional character' in text,'prompt_messages':len(messages)}
        if cp.exists():
            code=read(cp)['code'];row['structural_screen']=structural_idea_check(code)
        rows.append(row)
report={'scope':'closed input-adherence diagnostic; syntactic not semantic proof','rows':rows}
write(R/'readout-v1'/'adherence.json',report)
print(json.dumps(report))
