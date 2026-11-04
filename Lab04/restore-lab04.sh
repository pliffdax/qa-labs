#!/usr/bin/env bash
set -euo pipefail
source /etc/qa3520-lab04.env
[[ "$CLIENT_IP" =~ ^10\.35\.20\.(10[0-9]|110)$ ]] || { echo 'Invalid CLIENT_IP'; exit 1; }
[[ "$UPLINK" == enp0s3 ]] || { echo 'Unexpected uplink'; exit 1; }

rule() { iptables -C "$@" 2>/dev/null || iptables -I "$@"; }
nat_rule() { iptables -t nat -C "$@" 2>/dev/null || iptables -t nat -A "$@"; }

if [[ "${1:-}" == --stop ]]; then
    iptables -D FORWARD -i qa35-up -o "$UPLINK" -s 172.30.35.2/32 -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -i "$UPLINK" -o qa35-up -d 172.30.35.2/32 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
    iptables -t nat -D POSTROUTING -s 172.30.35.2/32 -o "$UPLINK" -j MASQUERADE 2>/dev/null || true
    ip netns exec qa3520-r iptables -t nat -D POSTROUTING -s 10.35.20.0/24 -o r2 -j MASQUERADE 2>/dev/null || true
    ip link del qa35-up 2>/dev/null || true
    exit 0
fi

ip link show "$UPLINK" >/dev/null
ip -4 route show default | grep -F "dev $UPLINK" >/dev/null
count=0
for ns in qa3520-c qa3520-r qa3520-s; do
    [[ ! -e /run/netns/$ns ]] || count=$((count + 1))
done
if [[ "$count" == 0 ]]; then
    for ns in qa3520-c qa3520-r qa3520-s; do
        ip netns add "$ns"
        ip -n "$ns" link set lo up
    done
    ip -n qa3520-c link add c0 type veth peer name r0
    ip -n qa3520-c link set r0 netns qa3520-r
    ip -n qa3520-r link add r1 type veth peer name s0
    ip -n qa3520-r link set s0 netns qa3520-s
    ip -n qa3520-r addr add 10.35.20.1/24 dev r0
    ip -n qa3520-r addr add 172.22.20.1/24 dev r1
    ip -n qa3520-s addr add 172.22.20.2/24 dev s0
    ip -n qa3520-c addr add "$CLIENT_IP/24" dev c0
    ip -n qa3520-c link set c0 up
    ip -n qa3520-r link set r0 up
    ip -n qa3520-r link set r1 up
    ip -n qa3520-s link set s0 up
    ip -n qa3520-c route replace default via 10.35.20.1
elif [[ "$count" != 3 ]]; then
    echo 'Partial topology: stop and inspect namespaces' >&2
    exit 1
else
    ip -n qa3520-c -4 addr show dev c0 | grep -F "inet $CLIENT_IP/24 " >/dev/null
    ip -n qa3520-r -4 addr show dev r0 | grep -F 'inet 10.35.20.1/24 ' >/dev/null
fi

if ip link show qa35-up >/dev/null 2>&1; then
    ip -4 addr show dev qa35-up | grep -F 'inet 172.30.35.1/30 ' >/dev/null
    ip -n qa3520-r -4 addr show dev r2 | grep -F 'inet 172.30.35.2/30 ' >/dev/null
else
    if ip -4 route show | grep -E '^172\.30\.35\.' >/dev/null; then
        echo 'Uplink subnet already in use' >&2
        exit 1
    fi
    ip -n qa3520-r link show r2 >/dev/null 2>&1 && { echo 'r2 already exists'; exit 1; }
    ip link add qa35-up type veth peer name r2
    ip link set r2 netns qa3520-r
    ip addr add 172.30.35.1/30 dev qa35-up
    ip -n qa3520-r addr add 172.30.35.2/30 dev r2
fi
ip link set qa35-up up
ip -n qa3520-r link set r2 up
ip -n qa3520-r route replace default via 172.30.35.1 dev r2
sysctl -w net.ipv4.ip_forward=1
ip netns exec qa3520-r sysctl -w net.ipv4.ip_forward=1
if [[ -f /var/lib/qa3520-lab04/router.rules ]]; then
    ip netns exec qa3520-r iptables-restore < /var/lib/qa3520-lab04/router.rules
fi
ip netns exec qa3520-r iptables -t nat -C POSTROUTING -s 10.35.20.0/24 -o r1 -j MASQUERADE 2>/dev/null ||
    ip netns exec qa3520-r iptables -t nat -A POSTROUTING -s 10.35.20.0/24 -o r1 -j MASQUERADE
ip netns exec qa3520-r iptables -t nat -C POSTROUTING -s 10.35.20.0/24 -o r2 -j MASQUERADE 2>/dev/null ||
    ip netns exec qa3520-r iptables -t nat -A POSTROUTING -s 10.35.20.0/24 -o r2 -j MASQUERADE
rule FORWARD -i qa35-up -o "$UPLINK" -s 172.30.35.2/32 -j ACCEPT
rule FORWARD -i "$UPLINK" -o qa35-up -d 172.30.35.2/32 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
nat_rule POSTROUTING -s 172.30.35.2/32 -o "$UPLINK" -j MASQUERADE
echo 'qa3520 Internet path restored; DHCP/DNS/HTTP services are not started by this unit'
