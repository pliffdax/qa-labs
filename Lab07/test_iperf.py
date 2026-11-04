from parser import parser, check_thresholds


def test_throughput(client):
    assert client.returncode == 0, (
        f'iperf3 failed (exit {client.returncode}): {client.stderr}'
    )
    assert not client.stderr.strip(), client.stderr
    check_thresholds(parser(client.stdout))
