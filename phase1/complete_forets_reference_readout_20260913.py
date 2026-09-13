"""Continue a preserved partial readout; no rerun, rescore choice or overwrite."""
import datetime as dt
import json
from pathlib import Path
import sys
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')
PRESERVED={
    'wallclock-summary.json':'4d89d47dd47877c04ceebeb24adc6a7773f13cfbe3bdc65517eef878b933d11e',
    'wallclock-runs.csv':'39ccfd4672179918d6acc3e96ef160f07922845e2302f84c2880f4a563bbbe3e',
    'singlevote-attribution.json':'ac18632a3460c8992f4ad12f0e7374cfe1ff120af80b30b55ddfc3adfe35d46f',
    'readout-intent.json':'4d9798580760847677dd4bb22656158d22731dddfabe0f2f0b3614c882439efa',
}


def main():
    plan=read(ROOT/'readout-plan.json')
    if (plan['root'],plan['source_tree'])!=(str(ROOT),'f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798'):
        raise ValueError('exact closed matrix')
    for name,h in PRESERVED.items():read(ROOT/name,h) if name.endswith('.json') else None
    if {n:sha((ROOT/n).read_bytes()) for n in PRESERVED}!=PRESERVED:raise ValueError('partial result drift')
    for n in ('common-start-summary.json','common-start-runs.csv','readout-finished.json'):
        if (ROOT/n).exists():raise ValueError('continuation already started')
    for n,h in plan['readers'].items():
        if sha(Path(__file__).with_name(n).read_bytes())!=h:raise ValueError('frozen reader changed')
    journal=ROOT/'source/src/dojo/core/solvers/utils/journal.py'
    source=journal.read_text()
    if '"metric": metric_value' not in source or '"metric_maximize": node.metric.maximize' not in source:
        raise ValueError('serialization evidence absent')
    import readout_forets_reference_20260913 as original
    script=Path(original.__file__).read_text()
    start=script.index('    from verify_branching_selection_20260913 import verify_pool')
    end=script.index('\n\n\nif __name__')
    tail='\n'.join(line[4:] if line.startswith('    ') else line for line in script[start:end].splitlines())
    before='from verify_forets_reference_records_20260913 import verify_reference'
    if tail.count(before)!=1:raise ValueError('exact continuation anchor')
    tail=tail.replace(before,'from verify_forets_reference_flat_journal_20260913 import verify_reference')
    marker="write(root/'readout-finished.json',encode(finish))"
    if tail.count(marker)!=1:raise ValueError('completion marker')
    tail=tail.replace(marker,"finish['readout_compatibility_recovery']=recovery\n"+marker)
    recovery=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        cause='frozen reference verifier expected nested metric; actual journal stores scalar metric and metric_maximize',
        preserved=PRESERVED,journal_serializer_sha256=sha(journal.read_bytes()),
        recovery_script_sha256=sha(Path(__file__).read_bytes()),
        compatibility_verifier_sha256=sha(Path(__file__).with_name('verify_forets_reference_flat_journal_20260913.py').read_bytes()),
        continuation_sha256=sha(tail.encode()),
        policy='original source/configs/selection/metrics/eligibility/primary scores unchanged; only journal schema normalization')
    write(ROOT/'readout-recovery-intent.json',encode(recovery))
    sys.path[:0]=[str(ROOT/'source/src'),str(ROOT/'code')]
    namespace=vars(original).copy()
    namespace.update(root=ROOT,TREE=plan['source_tree'],prepared=read(ROOT/'prepared.json',plan['prepared_sha256']),
        actual=plan['readers'],recovery=recovery)
    exec(compile(tail,'<preserved-original-readout-continuation>','exec'),namespace)
    if {n:sha((ROOT/n).read_bytes()) for n in PRESERVED}!=PRESERVED:raise ValueError('continuation changed preserved files')


if __name__=='__main__':main()
