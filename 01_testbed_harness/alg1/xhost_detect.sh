#!/usr/bin/env bash
# B: multi-host ML detection. From orderer1's host, probe real cross-host TCP-connect
# RTT to all 5 orderers' :7050 over the AWS network. Baseline phase, then inject
# netem delay on orderer3's eth0 (iproute2 netns container) -> orderer3's cross-host
# RTT separates. Demonstrates detection on REAL multi-host telemetry (not the
# single-host RTT-shift), closing the "RTT-only single-host" disclosure.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
H1=3.35.4.99           # orderer1 host (probe runs here)
H3=52.78.62.61         # orderer3 host (attack target)
PRIV=(172.31.39.233 172.31.44.2 172.31.37.115 172.31.46.160 172.31.39.145)
OUT=/mnt/d/fabric-d2/results/xhost_detect_$(date +%H%M%S); mkdir -p "$OUT"

# probe script staged on orderer1 host: 200 ticks, ~0.3s each; netem onset at tick 70
cat > /tmp/probe.py <<'PY'
import socket, time, sys
TARGETS=["172.31.39.233","172.31.44.2","172.31.37.115","172.31.46.160","172.31.39.145"]
def rtt(ip):
    t=time.time()
    try:
        s=socket.create_connection((ip,7050),timeout=1.0); s.close()
    except Exception:
        return 1000.0
    return (time.time()-t)*1000.0
with open("/tmp/feed.csv","w") as f:
    for k in range(200):
        row=[f"{time.time():.3f}"]+[f"{rtt(ip):.3f}" for ip in TARGETS]
        f.write(",".join(row)+"\n"); f.flush()
        time.sleep(0.3)
PY
$SSH ubuntu@$H1 'cat > /tmp/probe.py' < /tmp/probe.py
echo "=== start probe on orderer1 host (background) ==="
$SSH ubuntu@$H1 'nohup python3 /tmp/probe.py >/tmp/probe.log 2>&1 & echo started'
sleep 22   # ~70 ticks baseline
echo "=== inject netem 40ms+-10ms on orderer3 host primary iface (--network host => orderer's iface) ==="
IF=$($SSH ubuntu@$H3 "ip route get 8.8.8.8 | grep -oP 'dev \K\S+' | head -1")
echo "  orderer3 iface=$IF"
$SSH ubuntu@$H3 "sudo tc qdisc replace dev $IF root netem delay 40ms 10ms distribution normal && echo netem-applied; tc qdisc show dev $IF | grep -o 'netem.*'"
echo "ATTACK_ONSET_TICK~70"
sleep 42   # ~130 ticks attack
echo "=== clear netem ==="
$SSH ubuntu@$H3 "sudo tc qdisc del dev $IF root 2>/dev/null; echo netem-cleared"
$SSH ubuntu@$H1 'pkill -f probe.py 2>/dev/null; wc -l /tmp/feed.csv'
$SSH ubuntu@$H1 'cat /tmp/feed.csv' > "$OUT/feed.csv"
echo "feed rows: $(wc -l < "$OUT/feed.csv")"
echo "=== quick separation: mean RTT(ms) baseline(ticks1-65) vs attack(ticks75-) per orderer ==="
awk -F, 'NR>=1&&NR<=65{for(i=2;i<=6;i++)b[i]+=$i;nb++} NR>=75{for(i=2;i<=6;i++)a[i]+=$i;na++} END{for(i=2;i<=6;i++)printf "  orderer%d: base=%.3f attack=%.3f\n",i-1,b[i]/nb,a[i]/na}' "$OUT/feed.csv"
echo "XHOST_DETECT_DONE feed=$OUT/feed.csv"
