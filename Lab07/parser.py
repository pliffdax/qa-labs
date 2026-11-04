"""Parse every iperf3 TCP interval, keeping bytes and bit/s explicit."""
import re

ROW = re.compile(
    r'\[\s*\d+\]\s*([\d.]+)\s*-\s*([\d.]+)\s+sec\s+'
    r'([\d.]+)\s+([KMGT]?)Bytes\s+([\d.]+)\s+([KMGT]?)bits/sec'
    r'(?:\s+(\d+)\s+([\d.]+)\s+([KMGT]?)Bytes)?'
)
POW = {'': 0, 'K': 1, 'M': 2, 'G': 3, 'T': 4}
TRANSFER_LIMIT = 2 * 1024**2  # 2 MiB, matching iperf3's MBytes display.
BITRATE_LIMIT = 20_000_000


def parser(text):
    rows = []
    for line in text.splitlines():
        if re.search(r'\b(sender|receiver)\s*$', line):
            continue
        if not re.match(r'\s*\[\s*\d+\]', line) or not re.search(r'\bsec\b', line):
            continue
        match = ROW.fullmatch(line.strip())
        if not match:
            raise ValueError(f'Unrecognized interval row: {line}')
        start, end, transfer, tunit, rate, runit, retr, cwnd, cunit = match.groups()
        start, end = float(start), float(end)
        if end <= start:
            raise ValueError(f'Invalid interval bounds: {line}')
        rows.append({
            'Interval': f'{start:.2f}-{end:.2f}',
            'StartSeconds': start,
            'EndSeconds': end,
            'Seconds': end - start,
            'TransferBytes': float(transfer) * 1024**POW[tunit],
            'Bitrate': float(rate) * 1000**POW[runit],
            'Retr': int(retr) if retr is not None else None,
            'CwndBytes': float(cwnd) * 1024**POW[cunit] if cwnd else None,
        })
    if not rows:
        raise ValueError('No interval measurements found in iperf3 output')
    return rows


def complete_intervals(rows, expected_seconds=3):
    """Validate coverage; exclude only one final short trailing interval."""
    assert rows, 'No interval measurements'
    assert abs(rows[0]['StartSeconds']) <= .02, 'Measurements do not start at zero'
    for previous, current in zip(rows, rows[1:]):
        assert abs(current['StartSeconds'] - previous['EndSeconds']) <= .02, (
            f'Gap or overlap between intervals: {previous["Interval"]}, '
            f'{current["Interval"]}'
        )
    for row in rows[:-1]:
        assert .9 <= row['Seconds'] <= 1.1, f'Incomplete middle interval: {row}'
    assert rows[-1]['Seconds'] <= 1.1, f'Unexpected aggregate interval: {rows[-1]}'
    full = rows[:-1] if rows[-1]['Seconds'] < .9 else rows
    assert full, 'No complete intervals'
    assert full[-1]['EndSeconds'] >= expected_seconds - .1, (
        f'Missing measurement coverage: {full[-1]["EndSeconds"]} '
        f'of {expected_seconds} seconds'
    )
    return full


def check_thresholds(rows, expected_seconds=3):
    full = complete_intervals(rows, expected_seconds)
    for row in full:
        assert row['TransferBytes'] > TRANSFER_LIMIT, f'Transfer <= 2 MiB: {row}'
        assert row['Bitrate'] > BITRATE_LIMIT, f'Bitrate <= 20 Mbit/s: {row}'
    return full
