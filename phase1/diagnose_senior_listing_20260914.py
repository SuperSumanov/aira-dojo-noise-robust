"""Only print enumerated safe metadata failure reasons, never response contents."""
import json
import re
import inspect_senior_complete_root_20260912 as m

SAFE={'parent metadata changed or unsafe','invalid root scope','legacy parser changed','request cap',
    'listing HTTP status','listing byte cap','missing listing title','invalid metadata name',
    'empty, excessive or duplicate listing','credential-shaped metadata','duplicate identity',
    'unstable embedded listings','legacy item absent or changed'}
original_validate=m.validate
def diagnostic_validate(a,b,old):
    first,second,prior=m.comparable(a),m.comparable(b),m.comparable(old)
    missing=set(prior)-set(first);changed={k for k in prior.keys()&first.keys() if prior[k]!=first[k]}
    if missing or changed:
        dates=lambda x: sorted(v[0] for v in x.values() if v[1] and re.fullmatch(r'09[0-3][0-9]',v[0]))
        print(json.dumps(dict(metadata_only=True,stable=first==second,current_count=len(first),comparison_count=len(prior),
            missing_count=len(missing),changed_count=len(changed),added_count=len(set(first)-set(prior)),
            current_date_directories=dates(first),comparison_date_directories=dates(prior))))
        print(json.dumps(dict(changes=[dict(name_same=first[k][0]==prior[k][0],
            current_is_directory=first[k][1],comparison_is_directory=prior[k][1],
            current_safe_date=first[k][0] if re.fullmatch(r'09[0-3][0-9]',first[k][0]) else None,
            old_safe_date=prior[k][0] if re.fullmatch(r'09[0-3][0-9]',prior[k][0]) else None) for k in sorted(changed)])))
    return original_validate(a,b,old)
m.validate=diagnostic_validate
try:m.main()
except Exception as e:
    print(json.dumps(dict(status='METADATA_FAILED_CLOSED',error_type=type(e).__name__,
        reason=str(e) if str(e) in SAFE else 'not_in_safe_reason_allowlist')))
    raise SystemExit(2)
