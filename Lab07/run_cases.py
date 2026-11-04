#!/usr/bin/env python3
import datetime,json,subprocess,sys,uuid,re
from pathlib import Path
import xml.etree.ElementTree as ET


def expected_outcome(case, returncode, junit_path):
    """A negative case must fail for its intended reason, not just exit 1."""
    root = ET.parse(junit_path).getroot()
    failures = list(root.iter('failure'))
    errors = list(root.iter('error'))
    tests = list(root.iter('testcase'))
    if len(tests) != 1 or errors or list(root.iter('skipped')):
        return False
    if case == 'positive':
        return returncode == 0 and not failures
    if returncode != 1 or len(failures) != 1:
        return False
    # The traceback may quote dormant asserts. Classify only the actual message.
    reason = failures[0].get('message', '')
    if case == 'low-rate':
        return bool(re.match(r'AssertionError:\s+(Transfer <= 2 MiB|Bitrate <= 20 Mbit/s)', reason))
    return bool(re.match(r'AssertionError:\s+iperf3 failed \(exit', reason)) and 'Connection refused' in reason


def main():
    root = Path(__file__).resolve().parent
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out = root/'results'/f'{stamp}-{uuid.uuid4().hex[:6]}'
    out.mkdir(parents=True)
    summary = []
    for case, expected in [('positive', 0), ('low-rate', 1), ('closed-port', 1)]:
        dest = out/case
        junit = out/(case+'.xml')
        result = subprocess.run([
            sys.executable, '-m', 'pytest', '-v', 'test_iperf.py', '--case', case,
            '--evidence', str(dest), '--junitxml', str(junit),
        ], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (out/(case+'.txt')).write_text(result.stdout)
        print(result.stdout)
        matched = junit.exists() and expected_outcome(case, result.returncode, junit)
        summary.append({
            'case': case, 'expected_exit': expected, 'actual_exit': result.returncode,
            'expected_failure_reason_verified': matched, 'matched': matched,
        })
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print('Evidence:', out)
    return 0 if all(row['matched'] for row in summary) else 1


if __name__ == '__main__':
    raise SystemExit(main())
