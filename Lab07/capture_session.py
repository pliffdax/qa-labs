"""Capture one short Lab07 experiment on Ubuntu loopback with an automatic stop."""
import argparse
import datetime
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--seconds', default=20, type=int)
    parser.add_argument('--port', type=int, help='Manual server port; omit for dynamic pytest ports')
    args = parser.parse_args()
    if not 5 <= args.seconds <= 120:
        parser.error('--seconds must be between 5 and 120')
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    if os.geteuid() == 0:
        parser.error('Run Python as your normal user; authenticate separately with sudo -v')
    for name in ('sudo', 'timeout', 'tcpdump'):
        if not shutil.which(name):
            parser.error(f'Missing command: {name}')
    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    log = out.with_suffix(out.suffix + '.log')
    metadata = out.with_suffix(out.suffix + '.json')
    if any(p.exists() for p in (out, log, metadata)):
        parser.error('Capture destination already exists; choose a new name')
    # Reserve the file as the student user. tcpdump drops privileges to that user.
    with out.open('xb'):
        pass
    expression = 'tcp and host 127.0.0.1 and not port 22'
    if args.port is not None:
        expression += f' and port {args.port}'
    command = ['sudo', '-n', 'timeout', '--signal=INT', '--kill-after=3s',
               f'{args.seconds}s', 'tcpdump', '-n', '-U', '-i', 'lo', '-s', '0',
               '-Z', getpass.getuser(), '-w', str(out), expression]
    start = datetime.datetime.now().astimezone().isoformat()
    print('Capture:', out, flush=True)
    code = 130
    try:
        with log.open('x') as stream:
            proc = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 5
            while proc.poll() is None and time.monotonic() < deadline:
                if 'listening on lo' in log.read_text(errors='replace'):
                    print(f'Capture ready. Run the experiment in A now; timer is {args.seconds}s.', flush=True)
                    break
                time.sleep(.1)
            else:
                print('Capture is not ready; check the log before running the experiment.', flush=True)
            code = proc.wait(timeout=args.seconds + 10)
    except KeyboardInterrupt:
        print('Interrupted. The capture timer still limits its lifetime; check the log.')
    except subprocess.TimeoutExpired:
        print('Capture exceeded its deadline; do not count this capture as successful.')
        code = 125
    text = log.read_text(errors='replace') if log.exists() else ''
    match = re.search(r'(?m)^(\d+) packets captured\s*$', text)
    packets = int(match.group(1)) if match else 0
    valid = code in (0, 124) and packets > 0 and out.stat().st_size > 24
    metadata.write_text(json.dumps({
        'started': start, 'finished': datetime.datetime.now().astimezone().isoformat(),
        'command': command, 'capture_exit': code, 'packets_captured': packets,
        'capture_completed': valid,
    }, indent=2))
    print(text)
    print('Capture completed:', valid)
    print('A PCAP is evidence of packets, not a throughput test verdict.')
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
