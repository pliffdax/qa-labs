import json, sys
from pathlib import Path
from iperf_client import client
p = Path(sys.argv[1]) / 'manual-positive'; p.mkdir()
r = client(rate='100M')
(p / 'stdout.txt').write_text(r.stdout)
(p / 'stderr.txt').write_text(r.stderr)
(p / 'command.json').write_text(json.dumps({'args': r.args, 'returncode': r.returncode}))
print(r.stdout)
print('stderr:', r.stderr or '<empty>')
print('returncode:', r.returncode)
if r.returncode:
    raise SystemExit(r.returncode)
if r.stderr.strip():
    print('Unexpected stderr; do not run the parser.')
    raise SystemExit(1)
