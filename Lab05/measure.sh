#!/usr/bin/env bash
set -euo pipefail
server=${1:?Usage: measure.sh server output-directory}
out=${2:?Missing output directory}
mkdir -p "$out"
iperf -c "$server" -i 1 -t 30 -f m | tee "$out/tcp.txt"
python3 - "$out" <<'PY'
import re,sys
from pathlib import Path
p=Path(sys.argv[1]);rows=[]
for line in (p/'tcp.txt').read_text().splitlines():
 m=re.search(r'\[\s*\d+\]\s*([\d.]+)-\s*([\d.]+)\s+sec\s+[\d.]+\s+\w+Bytes\s+([\d.]+)\s+Mbits/sec',line)
 if m:
  start,end,rate=map(float,m.groups())
  if 0<end-start<=1.1:rows.append((end,rate))
if not rows:raise SystemExit('No one-second samples parsed')
(p/'tcp.tsv').write_text(''.join(f'{t}\t{r}\n' for t,r in rows))
PY
