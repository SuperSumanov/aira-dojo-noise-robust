"""Independent arithmetic verifier; no tokenizer, Cards, or producer import.

Reads only the approved historical train file and anonymous length receipts.
Does not independently attest source-tokenizer equivalence; that is the separate
source-vs-reference check. Deliberately not advertised as a second tokenizer run.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

TRAIN=Path('/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl')
EXPECTED='0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'


def verify(root):
    summary=json.loads((root/'summary.json').read_text())
    data=(root/'endpoint_lengths.csv').read_bytes()
    assert hashlib.sha256(data).hexdigest()==summary['endpoint_length_sha256']
    raw=TRAIN.read_bytes(); assert hashlib.sha256(raw).hexdigest()==EXPECTED
    pairs=[json.loads(line) for line in raw.splitlines()]
    assert all(x['intask_split']=='train' for x in pairs)
    identities=sorted({x[k] for x in pairs for k in ('better','worse')})
    counts=list(csv.DictReader(data.decode().splitlines()))
    assert len(counts)==len(identities)==summary['train_endpoints']
    lengths={}
    raw_n=[]
    for ordinal,(cid,row) in enumerate(zip(identities,counts)):
        assert int(row['ordinal'])==ordinal
        a,b=int(row['raw_tokens']),int(row['valid_tokens'])
        assert a>0 and b==min(a,16384)
        assert len(row['encoding_sha256'])==64 and int(row['encoding_sha256'],16)>=0
        lengths[cid]=b; raw_n.append(a)
    valid=sum(lengths[x[k]] for x in pairs for k in ('better','worse'))
    padded=0; batches=0
    for offset in range(0,len(pairs),8):
        block=pairs[offset:offset+8]
        padded+=2*len(block)*max(lengths[x[k]] for x in block for k in ('better','worse'))
        batches+=1
    expected={'train_pairs':len(pairs),'encoded_unique_valid_tokens':sum(lengths.values()),
        'encoded_pair_visit_valid_tokens':valid,'file_order_padded_slots':padded,
        'file_order_microbatches':batches,'truncated_unique_endpoints':sum(n>16384 for n in raw_n),
        'raw_length_min':min(raw_n),'raw_length_median':statistics.median(raw_n),'raw_length_max':max(raw_n),
        'canonical_flipped_pairs':sum(x['better']>x['worse'] for x in pairs),
        'source_reference_comparisons':len(identities),'source_collator_comparisons':batches}
    for k,v in expected.items(): assert summary[k]==v,k
    for shape in summary['candidate_shapes_not_authorized']:
        effective=shape['world_size']*shape['pairs_per_rank']*shape['accumulation']
        q,r=divmod(len(pairs),effective)
        assert (q,r)==(shape['complete_steps'],shape['remaining_pairs'])
        assert shape['strict_once_through_plan_admissible']==(r==0)
    assert summary['dev_test_vault_files_opened']==summary['model_fits']==summary['model_weights_loaded']==0
    assert summary['denied_attempts']=={} and not summary['gpu_context_created']
    return {'status':'PASS_INDEPENDENT_COUNTS_NOT_SECOND_TOKENIZER_ATTESTATION',
            'summary_sha256':hashlib.sha256((root/'summary.json').read_bytes()).hexdigest(),
            'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'recomputed_fields':expected,'weight_or_cards_files_opened':0,
            'length_receipt_sha256':hashlib.sha256(data).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True)
    args=p.parse_args()
    result=verify(args.root.resolve())
    print(json.dumps(result,sort_keys=True))
