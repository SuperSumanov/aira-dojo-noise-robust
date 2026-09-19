"""Supplement, never replace the closed original prefix gate/readout."""
import hashlib,json,re
from pathlib import Path

TRAILER=re.compile(r'\s*Execution time: [0-9]+(?:\.[0-9]+)? seconds? \(time limit is [0-9]+(?:\.[0-9]+)? (?:seconds?|minutes?|hours?)\)\.?\s*\Z')
ERROR=re.compile(r'(?m)^\s*((?:\w+Error|Exception):[^\n]*)')
ROOT=Path('/research/d7/spc/yzyang4/comparison-third-bank-20260919-7b544kbs')
SUMMARY='7dd466d42627e642ded6cd34af5660e0d0f6f76ed1150fb423565e13f7fb9371'

def core(text):
    clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
    matches=ERROR.findall(clean)
    if not matches:raise ValueError('no recognized terminal error')
    return TRAILER.sub('',matches[-1].strip())

def main():
    from run_comparison_spooky_pool_20260919 import read,write,sha
    from readout_comparison_reuse_20260919 import compare
    s=read(ROOT/'summary.json',SUMMARY);p=read(ROOT/'prepared.json',s['prepared_sha256'])
    row,=[r for r in s['rows'] if r['role']=='prefix']
    log=ROOT/f'output-{row["index"]}.private.log'
    if log.is_symlink():raise ValueError('log identity')
    expected=p['extension_context']['historical_prefix_error']
    fresh=log.read_text();same=core(expected)==core(fresh)
    if row['exit_code']!=1 or row['timed_out'] or row['valid'] is not False:raise ValueError('prefix outcome')
    if s['groups'][0]['prefix_matches'] is not False:raise ValueError('original gate must remain false')
    result=dict(role='posthoc_supplement_to_timing_trailer_gate_not_preregistered_pass',
        source_summary_sha256=SUMMARY,log_sha256=sha(log.read_bytes()),reader_sha256=sha(Path(__file__).read_bytes()),
        original_gate=False,known_timing_trailer_removed=True,core_error_equal=same,
        physical_runs=1,original_summary_unchanged=True,
        conditional_comparison=compare(s['rows'],same),
        limitation='Recorded code replay only. No new generation, native acceptance, live budget or E2E inference.')
    result['conditional_comparison']['caveat']='One exploratory physical run; four alternatives are not independent runs. Fixed historical direct debug, not a live scheduler.'
    if sha((ROOT/'summary.json').read_bytes())!=SUMMARY:raise ValueError('immutable summary')
    write(ROOT/'prefix-supplement.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
