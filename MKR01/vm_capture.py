#!/usr/bin/env python3
"""Check a 60-second PCAP workflow on synthetic, loopback-only traffic."""

from datetime import datetime, timezone
from pathlib import Path
import platform
import re
import secrets
import socket
import subprocess
import sys
import time


def main():
    run = Path(sys.argv[1]).resolve()
    run.mkdir(parents=True, exist_ok=False)
    print(f"UTC start: {datetime.now(timezone.utc).isoformat()}")
    print(f"Host: {socket.gethostname()} ({platform.machine()})")
    capture_path = run / "loopback.pcap"
    marker_prefix = f"MKR-{secrets.token_hex(4)}-"
    schedule = [(1, "first"), (30, "middle"), (57, "last")]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        endpoint.settimeout(1)
        capture_filter = (
            f"udp and dst host 127.0.0.1 and dst port {endpoint.getsockname()[1]}"
        )

        def send_marker(label):
            marker = (marker_prefix + label).encode()
            endpoint.sendto(marker, endpoint.getsockname())
            packet, _ = endpoint.recvfrom(1024)
            if packet != marker:
                raise RuntimeError(f"Unexpected datagram before {label}")
            print(f"Sent and received on loopback: {marker.decode()}", flush=True)

        send_marker("before")
        command = [
            "dumpcap", "-i", "lo", "-p", "-P", "-f", capture_filter,
            "-a", "duration:60", "-w", str(capture_path),
        ]
        print("Capture command:", " ".join(command), flush=True)
        with (run / "dumpcap.log").open("wb") as capture_log:
            with subprocess.Popen(command, stdout=capture_log, stderr=capture_log) as capture:
                started = time.monotonic()
                try:
                    while not capture_path.exists():
                        if capture.poll() is not None or time.monotonic() - started > 2:
                            raise RuntimeError("Capture failed to initialize")
                        time.sleep(0.02)
                    for offset, label in schedule:
                        time.sleep(max(0, started + offset - time.monotonic()))
                        send_marker(label)
                    if capture.wait(timeout=10):
                        raise RuntimeError("Capture did not finish successfully")
                finally:
                    if capture.poll() is None:
                        capture.terminate()
                elapsed = time.monotonic() - started
        print(f"Monotonic capture duration: {elapsed:.3f} s")
        send_marker("after")

    decoded = subprocess.run(
        ["tcpdump", "-nn", "-tt", "-A", "-r", str(capture_path)],
        capture_output=True, text=True, check=True,
    )
    (run / "tcpdump.txt").write_text(decoded.stdout)
    markers = re.findall(re.escape(marker_prefix) + r"[a-z]+", decoded.stdout)
    expected = [marker_prefix + label for _, label in schedule]
    if sorted(markers) != sorted(expected) or not 59 <= elapsed <= 63:
        raise RuntimeError(f"Unexpected capture result: {markers!r}")
    print(f"PASS: {len(markers)} in-window markers; both outside markers absent.")


if __name__ == "__main__":
    main()
