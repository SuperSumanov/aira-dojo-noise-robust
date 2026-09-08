"""Independent Git-blob / tar-byte comparison, no source contents printed."""
import hashlib
import json
import subprocess
import sys
import tarfile

COMMIT = '73fbb82252309e40456f879650cb8c4a7c410fbe'
with tarfile.open(sys.argv[1]) as archive:
    rows = []
    for member in archive.getmembers():
        if not member.isfile() or not member.name.endswith('.py'):
            continue
        data = archive.extractfile(member).read()
        blob = subprocess.check_output(['git', 'show', COMMIT + ':' + member.name])
        rows.append(dict(path=member.name, git_bytes=len(blob), archive_bytes=len(data),
                         git_sha256=hashlib.sha256(blob).hexdigest(),
                         archive_sha256=hashlib.sha256(data).hexdigest(),
                         git_crlf=blob.count(b'\r\n'), archive_crlf=data.count(b'\r\n'),
                         byte_equal=blob == data, lf_equal=blob.replace(b'\r\n', b'\n') == data.replace(b'\r\n', b'\n')))
print(json.dumps(dict(source_commit=COMMIT, files=rows, all_exact=all(r['byte_equal'] for r in rows)), sort_keys=True))
