"""Record one SMTP exchange with a local sink, then decode the capture."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import os
import selectors
import signal
import smtplib
import socketserver
import subprocess
import time


HOST = "127.0.0.1"
PORT = 35206
SENDER = "sender@lab06.test"
RECIPIENT = "recipient@lab06.test"
MESSAGE = (
    f"From: {SENDER}\r\n"
    f"To: {RECIPIENT}\r\n"
    "Subject: QA 3520 SMTP loopback\r\n"
    "\r\n"
    "QA3520-SMTP: local delivery check.\r\n"
).encode("ascii")

TAGS = (
    (b"EHLO client.lab06.test\r\n", b"250 sink.lab06.test\r\n"),
    (f"MAIL FROM:<{SENDER}>\r\n".encode("ascii"), b"250 sender accepted\r\n"),
    (f"RCPT TO:<{RECIPIENT}>\r\n".encode("ascii"), b"250 recipient accepted\r\n"),
    (b"DATA\r\n", b"354 end with a line containing a dot\r\n"),
)


class LocalSink(socketserver.StreamRequestHandler):
    """Accept the fixture envelope and spool the test message locally."""

    def handle(self):
        self.connection.settimeout(5)
        self.wfile.write(b"220 sink.lab06.test ESMTP\r\n")
        for expected, reply in TAGS:
            if self.rfile.readline(1024).upper() != expected.upper():
                self.wfile.write(b"503 unexpected command\r\n")
                return
            self.wfile.write(reply)

        payload = bytearray()
        for line in iter(lambda: self.rfile.readline(1024), b""):
            if line == b".\r\n":
                break
            payload.extend(line[1:] if line.startswith(b"..") else line)
            if len(payload) > 4096:
                self.wfile.write(b"552 message too large\r\n")
                return
        else:
            return

        self.server.spool.write_bytes(payload)
        self.wfile.write(b"250 stored locally\r\n")
        if self.rfile.readline(1024).upper() == b"QUIT\r\n":
            self.wfile.write(b"221 closing connection\r\n")


def send_fixture():
    with smtplib.SMTP(HOST, PORT, local_hostname="client.lab06.test", timeout=5) as client:
        client_port = client.sock.getsockname()[1]
        for call, expected in (
            (client.ehlo, 250),
            (lambda: client.mail(SENDER), 250),
            (lambda: client.rcpt(RECIPIENT), 250),
            (lambda: client.data(MESSAGE), 250),
        ):
            code, reply = call()
            if code != expected:
                raise RuntimeError(f"SMTP {code}: {reply!r}")
    return client_port


def wait_for_capture(process, capture_log):
    deadline = time.monotonic() + 5
    with selectors.DefaultSelector() as selector:
        selector.register(process.stderr, selectors.EVENT_READ)
        while b"listening on" not in capture_log:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise RuntimeError("tcpdump did not get ready")
            chunk = os.read(process.stderr.fileno(), 4096)
            if not chunk:
                raise RuntimeError(capture_log.decode(errors="replace"))
            capture_log.extend(chunk)


def capture(interface, output):
    pcap = output / "smtp-loopback.pcap"
    spool = output / "smtp-accepted.eml"
    command = [
        "tcpdump", "--immediate-mode", "-p", "-U", "-nn", "-s", "0",
        "-i", interface, "-w", str(pcap),
        f"ip and src host {HOST} and dst host {HOST} and tcp port {PORT}",
    ]
    capture_log = bytearray()
    with socketserver.TCPServer((HOST, PORT), LocalSink) as server:
        server.spool = spool
        server.timeout = 5
        with subprocess.Popen(command, stderr=subprocess.PIPE) as process:
            try:
                wait_for_capture(process, capture_log)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    request = executor.submit(server.handle_request)
                    client_port = send_fixture()
                    request.result()
                time.sleep(0.1)
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                try:
                    _, tail = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    _, tail = process.communicate()
                capture_log.extend(tail)
                (output / "tcpdump.log").write_bytes(capture_log)
            if process.returncode != 0:
                raise RuntimeError(f"tcpdump exited with {process.returncode}")

    accepted = spool.read_bytes()
    if accepted != MESSAGE:
        raise RuntimeError("Local sink did not preserve the message bytes")
    print(f"PASS: local SMTP sink stored {len(accepted)} identical bytes")
    print(f"TCP: {HOST}:{client_port} -> {HOST}:{PORT}")
    print(f"Message SHA-256: {sha256(accepted).hexdigest()}")
    return pcap


def decode(tshark, pcap):
    base = [tshark, "-n", "-r", str(pcap), "-d", f"tcp.port=={PORT},smtp"]
    fields = [
        "frame.number", "frame.time_relative", "frame.len", "tcp.srcport", "tcp.dstport",
        "tcp.flags", "tcp.len", "smtp.req.command", "smtp.req.parameter", "smtp.response.code",
    ]
    extract = base + ["-T", "fields", "-E", "header=y"]
    for field in fields:
        extract.extend(["-e", field])
    tsv = subprocess.check_output(extract)
    (pcap.parent / "smtp-frames.tsv").write_bytes(tsv)
    dialogue = subprocess.check_output(base + ["-q", "-z", "follow,tcp,ascii,0"])
    (pcap.parent / "smtp-stream.txt").write_bytes(dialogue)
    print("Frame   Source > target       TCP flags   SMTP command / reply")
    for line in tsv.decode().splitlines()[1:]:
        number, _, _, src, dst, flags, length, command, _, reply = line.split("\t")
        if command or reply or int(length) or int(flags, 16) & 3:
            print(f"{number:>5}   {src:>6} > {dst:<6}      {flags:<9}   {command or reply}")
    print(f"PCAP SHA-256: {sha256(pcap.read_bytes()).hexdigest()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new directory for evidence")
    parser.add_argument("--interface", default="lo0")
    parser.add_argument("--tshark", default="tshark")
    args = parser.parse_args()
    args.output.mkdir()
    decode(args.tshark, capture(args.interface, args.output))


if __name__ == "__main__":
    main()
