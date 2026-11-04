"""Run iperf3 without a shell, retaining stdout, stderr and return code."""
import os,subprocess

def client(server_ip='127.0.0.1',port=35207,rate='100M',seconds=3):
 return subprocess.run(['iperf3','-c',server_ip,'-p',str(port),'-t',str(seconds),'-i','1','-b',rate,'--connect-timeout','2000'],capture_output=True,text=True,timeout=seconds+8,env={**os.environ,'LC_ALL':'C'})
