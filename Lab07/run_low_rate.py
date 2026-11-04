import json, sys
from pathlib import Path
from iperf_client import client
from parser import parser, check_thresholds
p = Path(sys.argv[1]) / 'manual-low-rate'; p.mkdir()
r = client(rate='1M')
(p / 'stdout.txt').write_text(r.stdout)
(p / 'stderr.txt').write_text(r.stderr)
(p / 'command.json').write_text(json.dumps({'args': r.args, 'returncode': r.returncode}))
print(r.stdout); print('stderr:', r.stderr or '<empty>'); print('returncode:', r.returncode)
if r.returncode:
    raise SystemExit(r.returncode)
if r.stderr.strip():
    print('Unexpected stderr; this is not a threshold failure.')
    raise SystemExit(1)
rows = parser(r.stdout); (p / 'parsed.json').write_text(json.dumps(rows, indent=2))
for row in rows:
    print(row)
try:
    check_thresholds(rows)
except AssertionError as error:
    print('Threshold check: FAIL')
    print('Reason:', error)
    raise SystemExit(1)
print('Threshold check: PASS')
