import json,os,socket,subprocess,time
from pathlib import Path
import pytest
from iperf_client import client as run_client

def pytest_addoption(parser):
 parser.addoption('--ssh',action='store_true',help='Start server via verified SSH to this VM on 127.0.0.1')
 parser.addoption('--case',choices=['positive','low-rate','closed-port'],default='positive')
 parser.addoption('--evidence',default='results/manual')

@pytest.fixture
def server(request):
 # Reserve a free local port first; closed-port leaves it bound but not listening.
 reservation=socket.socket();reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
 if request.config.getoption('--case')=='closed-port':
  try:yield port
  finally:reservation.close()
  return
 reservation.close()
 if request.config.getoption('--ssh'):
  import getpass,paramiko
  # Local host public key is trusted from the local OS, not from a blind network scan.
  public=Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()
  hosts=Path(request.config.getoption('--evidence'))/'ssh_known_hosts'
  hosts.parent.mkdir(parents=True,exist_ok=True)
  hosts.write_text('127.0.0.1 '+public[0]+' '+public[1]+'\n')
  ssh=paramiko.SSHClient();ssh.load_host_keys(str(hosts))
  try:
   ssh.connect('127.0.0.1',username=getpass.getuser(),password=getpass.getpass('SSH password (not saved): '),look_for_keys=False,allow_agent=False,timeout=5)
   stdin,stdout,stderr=ssh.exec_command(f'timeout 15s iperf3 -s -1 -B 127.0.0.1 -p {port}',get_pty=True)
   time.sleep(.5)
   if stdout.channel.exit_status_ready():raise RuntimeError(stdout.read().decode())
   try:yield port
   finally:
    # One-off server exits after the client. Ctrl+C stops it if the test was interrupted.
    if not stdout.channel.exit_status_ready():stdout.channel.send('\x03')
    stdout.channel.settimeout(17)
    serverlog=stdout.read().decode(errors='replace')
    (hosts.parent/'ssh-server.log').write_text(serverlog)
    stdout.channel.close()
  finally:ssh.close()
  return
 proc=subprocess.Popen(['iperf3','-s','-B','127.0.0.1','-p',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
 try:
  time.sleep(.4)
  if proc.poll() is not None:raise RuntimeError(proc.stderr.read())
  yield port
 finally:
  if proc.poll() is None:
   proc.terminate()
   try:proc.wait(3)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
  proc.stderr.close()

@pytest.fixture
def client(server,request):
 case=request.config.getoption('--case');rate='1M' if case=='low-rate' else '100M'
 result=run_client(port=server,rate=rate)
 p=Path(request.config.getoption('--evidence'));p.mkdir(parents=True,exist_ok=True)
 (p/'stdout.txt').write_text(result.stdout);(p/'stderr.txt').write_text(result.stderr)
 (p/'command.json').write_text(json.dumps({'command':result.args,'returncode':result.returncode,'case':case},indent=2))
 return result
