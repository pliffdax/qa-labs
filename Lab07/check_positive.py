import json, sys
from pathlib import Path
from parser import parser, check_thresholds
p = Path(sys.argv[1]) / 'manual-positive'
command = json.loads((p / 'command.json').read_text())
if command['returncode'] != 0 or (p / 'stderr.txt').read_text().strip():
    print('Client error; parsing not performed.')
    raise SystemExit(1)
rows = parser((p / 'stdout.txt').read_text())
(p / 'parsed.json').write_text(json.dumps(rows, indent=2))
for row in rows:
    print(row)
try:
    check_thresholds(rows)
except AssertionError as error:
    print('Threshold check: FAIL')
    print('Reason:', error)
    raise SystemExit(1)
print('Threshold check: PASS')
