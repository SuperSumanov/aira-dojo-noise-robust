"""Read one Git document through redaction. Never write raw input or matches.

Use remotely before consuming unreviewed collaborator text. Shape screening is
defence in depth, not a proof that arbitrary text cannot contain a credential.
"""
import re
import subprocess
import sys
from urllib.parse import parse_qsl,urlsplit,urlunsplit,urlencode

NAMES=re.compile(r'(?i)^(?:api[_-]?key|access[_-]?token|token|secret|password|authorization|signature|x-amz-signature)$')
SHAPES=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[0-9A-Za-z-]{10,})')
BEARER=re.compile(r'(?i)(bearer\s+)(?!\[REDACTED\])([A-Za-z0-9._~+/-]{12,}=*)')
ASSIGN=re.compile(r'''(?ix)((?:api[_-]?key|access[_-]?token|token|secret|password|authorization)\s*(?:[:=]|%3d)\s*["']?)(?!\[REDACTED\])([^\s&'"`)\]}>,]+)''')
URL=re.compile(r'''https?://[^\s<>"'`]+''')


def redact(raw):
    counts=[]
    raw,n=SHAPES.subn('[REDACTED]',raw);counts.append(n)
    # Bearer must precede generic Authorization assignment, otherwise only the
    # word Bearer is erased and its credential is left exposed.
    raw,n=BEARER.subn(r'\1[REDACTED]',raw);counts.append(n)
    urls=[0]
    def url(m):
        value=m.group();u=urlsplit(value);pairs=parse_qsl(u.query,keep_blank_values=True)
        if not any(NAMES.fullmatch(k) for k,v in pairs):return value
        urls[0]+=sum(bool(NAMES.fullmatch(k)) for k,v in pairs)
        return urlunsplit((u.scheme,u.netloc,u.path,urlencode([(k,'[REDACTED]' if NAMES.fullmatch(k) else v) for k,v in pairs],safe='[]'),u.fragment))
    raw=URL.sub(url,raw);counts.append(urls[0])
    raw,n=ASSIGN.subn(r'\1[REDACTED]',raw);counts.append(n)
    if SHAPES.search(raw):raise ValueError('residual credential shape')
    return raw,counts


def main():
    if len(sys.argv)!=3:raise SystemExit('usage: safe_senior_reader.py REF PATH')
    raw=subprocess.check_output(['git','show',sys.argv[1]+':'+sys.argv[2]]).decode('utf-8',errors='strict')
    safe,counts=redact(raw)
    print('REDACTION_COUNTS='+','.join(map(str,counts)),file=sys.stderr)
    sys.stdout.write(safe)


if __name__=='__main__':main()
