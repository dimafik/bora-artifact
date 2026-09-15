#!/bin/bash
# Replay one delay track onto the netem band installed by potency_xhost.sh.
#
# This runs ON the orderer host. Driving the same loop over ssh would put a
# connection handshake inside a 0.15 s tick -- 1200 of them per round, which
# becomes the load being measured.
#
# It must be a FILE, not an inline `nohup bash -c "..."` over ssh: the delay
# value has to survive three levels of quoting (local shell, ssh, remote shell),
# and the version that did not survive passed tc a literal `\486.324ms`, which
# tc rejected with `Illegal "latency"` while the qdisc sat unchanged at its
# initial value. The run looked healthy and measured nothing.
#
# Usage: replay.sh <track-file> [tick-seconds]
IF=${IF:-ens5}
TRK=${1:?track file}
TICK=${2:-0.15}
rm -f /tmp/replay.stop
: > /tmp/replay.err
while [ ! -f /tmp/replay.stop ]; do
  while read -r d; do
    [ -f /tmp/replay.stop ] && break
    tc qdisc change dev "$IF" parent 1:3 handle 30: netem delay "${d}ms" limit 10000 2>>/tmp/replay.err
    sleep "$TICK"
  done < "$TRK"
done
