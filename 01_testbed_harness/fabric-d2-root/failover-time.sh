#!/bin/bash
# ι: Failover time measurement
# 1. Identify current Raft leader (osnadmin shows leader status)
# 2. Stop the leader
# 3. Measure time until a new leader is elected (via osnadmin polling)
set -e

RESULTS=/mnt/d/fabric-d2/results_failover
mkdir -p "$RESULTS"
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin

ORDERER_CA=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem

get_leader() {
  # Query each orderer's channel list; the leader has consensusRelation=consenter and active+follower or leader status
  # Use orderer metrics endpoint
  for n in 1 2 3 4 5; do
    case $n in
      1) ADM=7053  ; HOST=orderer  ; PORT=7050  ;;
      2) ADM=8053  ; HOST=orderer2 ; PORT=8050  ;;
      3) ADM=10053 ; HOST=orderer3 ; PORT=10050 ;;
      4) ADM=11053 ; HOST=orderer4 ; PORT=11050 ;;
      5) ADM=12053 ; HOST=orderer5 ; PORT=12050 ;;
    esac
    # Try to find leader by checking orderer logs for "became leader"
    LEAD=$(docker logs --tail 200 ${HOST}.example.com 2>&1 | grep -c "became leader")
    if [ "$LEAD" -gt 0 ]; then
      # Most recent "became leader" event
      LAST=$(docker logs --tail 500 ${HOST}.example.com 2>&1 | grep "became leader" | tail -1)
      echo "orderer$n (port $PORT): $LAST"
    fi
  done
}

# Trial 1: Kill orderer1 (which started leadership)
SUMMARY="$RESULTS/failover_summary.csv"
echo "trial,killed_orderer,detection_ms,new_leader_orderer" > "$SUMMARY"

for trial in 1 2 3; do
  echo ""
  echo "############# TRIAL $trial #############"

  echo "Pre-kill leader status:"
  get_leader | tail -3

  # Pick a victim that's currently leader. Look for most recent "became leader" across all 5
  CURRENT_LEADER_HOST=$(for n in 1 2 3 4 5; do
    case $n in
      1) HOST=orderer ;;
      2) HOST=orderer2 ;;
      3) HOST=orderer3 ;;
      4) HOST=orderer4 ;;
      5) HOST=orderer5 ;;
    esac
    L=$(docker logs --tail 100 ${HOST}.example.com 2>&1 | grep "became leader" | tail -1)
    if [ -n "$L" ]; then
      # Extract timestamp
      TS=$(echo "$L" | grep -oE '20[0-9]{2}-[0-9]{2}-[0-9]{2} [0-9:.]+' | head -1)
      echo "$TS $HOST"
    fi
  done | sort -r | head -1 | awk '{print $NF}')

  if [ -z "$CURRENT_LEADER_HOST" ]; then
    CURRENT_LEADER_HOST=orderer  # default to orderer1
    echo "Could not detect leader, defaulting to $CURRENT_LEADER_HOST"
  fi
  echo "Current leader: ${CURRENT_LEADER_HOST}.example.com"

  # Capture kill timestamp
  T_KILL=$(date +%s%N)
  echo "Killing ${CURRENT_LEADER_HOST}.example.com at $(date -Iseconds)..."
  docker stop "${CURRENT_LEADER_HOST}.example.com" 2>&1 | tail -1

  # Poll remaining orderers for new leader elected
  NEW_LEADER=""
  for attempt in $(seq 1 30); do
    sleep 1
    for n in 1 2 3 4 5; do
      case $n in
        1) HOST=orderer ;;
        2) HOST=orderer2 ;;
        3) HOST=orderer3 ;;
        4) HOST=orderer4 ;;
        5) HOST=orderer5 ;;
      esac
      if [ "$HOST" = "$CURRENT_LEADER_HOST" ]; then continue; fi
      # Check if this orderer became new leader AFTER the kill
      L=$(docker logs --since 30s "${HOST}.example.com" 2>&1 | grep "became leader" | tail -1)
      if [ -n "$L" ]; then
        T_DETECT=$(date +%s%N)
        DUR_MS=$(( (T_DETECT - T_KILL) / 1000000 ))
        NEW_LEADER=$HOST
        echo "New leader detected: $HOST after ${DUR_MS}ms"
        echo "$trial,$CURRENT_LEADER_HOST,$DUR_MS,$HOST" >> "$SUMMARY"
        break 2
      fi
    done
  done

  if [ -z "$NEW_LEADER" ]; then
    echo "No new leader detected within 30s"
    echo "$trial,$CURRENT_LEADER_HOST,TIMEOUT,NONE" >> "$SUMMARY"
  fi

  # Restart killed orderer for next trial
  echo "Restarting ${CURRENT_LEADER_HOST}.example.com..."
  docker start "${CURRENT_LEADER_HOST}.example.com" 2>&1 | tail -1
  sleep 8  # let it rejoin cluster
done

echo ""
echo "==================== FAILOVER SUMMARY ===================="
cat "$SUMMARY"
