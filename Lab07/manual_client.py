#!/usr/bin/env python3
"""Display and retain the manual client/parser experiment for QA 7 part 1."""
import argparse
import datetime
import json
from pathlib import Path
import uuid

from iperf_client import client
from parser import parser as parse, check_thresholds


def main():
    args_parser = argparse.ArgumentParser(description=__doc__)
    args_parser.add_argument('--host', default='127.0.0.1')
    args_parser.add_argument('--port', type=int, default=35207)
    args_parser.add_argument('--rate', default='100M')
    args = args_parser.parse_args()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out = Path(__file__).resolve().parent / 'results' / f'manual-client-{stamp}-{uuid.uuid4().hex[:6]}'
    out.mkdir(parents=True)
    result = client(args.host, args.port, args.rate)
    (out / 'stdout.txt').write_text(result.stdout)
    (out / 'stderr.txt').write_text(result.stderr)
    (out / 'command.json').write_text(json.dumps({'command': result.args, 'returncode': result.returncode}, indent=2))
    print(result.stdout)
    print('stderr:', result.stderr or '<empty>')
    print('returncode:', result.returncode)
    if result.returncode:
        print('Connection failed. Results:', out)
        return result.returncode
    if result.stderr.strip():
        print('Unexpected stderr; parsing not performed. Results:', out)
        return 1
    rows = parse(result.stdout)
    (out / 'parsed.json').write_text(json.dumps(rows, indent=2))
    for row in rows:
        print(row)
    try:
        check_thresholds(rows)
    except AssertionError as error:
        print('Manual threshold check: FAIL')
        print('Reason:', error)
        print('Results:', out)
        return 1
    print('Manual threshold check: PASS')
    print('Results:', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
