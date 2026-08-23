// BORA sidecar v2 — telemetry-driven detection.
//
// Each orderer container runs one instance. The sidecar opens a UDS at
// /var/run/raft-advisor.sock and serves an advice JSON.  Unlike v1
// (which simply mirrored /tmp/bora-advice.json) v2 derives B_t from
// live RTT probes against each peer orderer's admin port.
//
// Detection pipeline (one probe per second):
//   1. tcp_dial RTT to each orderer in PEERS list (admin port 9443)
//   2. rolling window WINDOW seconds per orderer
//   3. trigger = rolling_p95(orderer_i) > BASE_RTT * MULT
//   4. emit B_t = {i | trigger(i)}  with cap |B_t| < f
//   5. fail-open after K_FAIL consecutive empty windows
//   6. log every accept and every B_t change with timestamp (for
//      detection-latency analysis).
//
// Build:  GOOS=linux CGO_ENABLED=0 go build -o bora-sidecar-v2 bora_sidecar_v2.go
package main

import (
	"encoding/json"
	"flag"
	"log"
	"net"
	"os"
	"os/signal"
	"sort"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

type advice struct {
	Blacklist []uint64 `json:"blacklist"`
	Seq       uint64   `json:"seq"`
	FailOpen  bool     `json:"fail_open"`
}

type rollingRTT struct {
	mu     sync.Mutex
	window []time.Duration
	max    int
}

func (r *rollingRTT) push(d time.Duration) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.window = append(r.window, d)
	if len(r.window) > r.max {
		r.window = r.window[len(r.window)-r.max:]
	}
}

func (r *rollingRTT) p95() time.Duration {
	r.mu.Lock()
	defer r.mu.Unlock()
	if len(r.window) < 10 {
		return 0
	}
	cpy := make([]time.Duration, len(r.window))
	copy(cpy, r.window)
	sort.Slice(cpy, func(i, j int) bool { return cpy[i] < cpy[j] })
	idx := int(float64(len(cpy)) * 0.95)
	if idx >= len(cpy) {
		idx = len(cpy) - 1
	}
	return cpy[idx]
}

var probeErrLogged = false

func probeRTT(addr string) time.Duration {
	t0 := time.Now()
	conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
	if err != nil {
		if !probeErrLogged {
			log.Printf("probe err for %s: %v", addr, err)
			probeErrLogged = true
		}
		return 500 * time.Millisecond
	}
	conn.Close()
	return time.Since(t0)
}

func main() {
	sockPath := flag.String("sock", "/var/run/raft-advisor.sock", "UDS path")
	myID := flag.Uint64("id", 0, "this orderer's raftID (0 = unused)")
	peersFlag := flag.String("peers",
		"orderer.example.com:7055=1,orderer2.example.com:7055=2,orderer3.example.com:7055=3,orderer4.example.com:7055=4,orderer5.example.com:7055=5",
		"comma-separated host:port=raftID list of peer orderers")
	pollMs := flag.Int("poll-ms", 1000, "RTT probe interval (ms)")
	windowSec := flag.Int("window", 16, "rolling window size in seconds")
	mult := flag.Float64("mult", 5.0, "trigger threshold = base_rtt * mult")
	fCap := flag.Int("f", 2, "fault bound; |B_t| < f")
	kFail := flag.Int("kfail", 3, "fail-open threshold (consecutive empty windows)")
	logPath := flag.String("log", "/tmp/bora-sidecar-v2.log", "log file path")
	flag.Parse()

	// Parse peers spec
	type peer struct {
		addr string
		id   uint64
		rtt  *rollingRTT
	}
	var peers []*peer
	for _, p := range splitComma(*peersFlag) {
		parts := splitEq(p)
		if len(parts) != 2 {
			continue
		}
		var id uint64
		for _, c := range parts[1] {
			id = id*10 + uint64(c-'0')
		}
		peers = append(peers, &peer{
			addr: parts[0],
			id:   id,
			rtt:  &rollingRTT{max: *windowSec},
		})
	}

	// Set up logging
	logF, err := os.OpenFile(*logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err == nil {
		log.SetOutput(logF)
	}
	log.Printf("BORA sidecar v2 start: id=%d peers=%d window=%ds mult=%.1f f=%d kfail=%d",
		*myID, len(peers), *windowSec, *mult, *fCap, *kFail)

	// Periodic stats line for debugging and detection-latency analysis.
	statsTicker := time.NewTicker(2 * time.Second)
	defer statsTicker.Stop()

	// Atomic advice state
	curAdvice := &advice{Blacklist: []uint64{}, Seq: 0, FailOpen: false}
	var seqCounter uint64 = 0
	var advicePtr atomic.Pointer[advice]
	advicePtr.Store(curAdvice)

	// Probe loop
	go func() {
		emptyStreak := 0
		baseRTT := time.Duration(0)
		tick := time.NewTicker(time.Duration(*pollMs) * time.Millisecond)
		defer tick.Stop()
		for range tick.C {
			// Update base_rtt = min p95 across all peers (estimate of healthy floor)
			for _, p := range peers {
				if p.id == *myID {
					continue
				}
				rtt := probeRTT(p.addr)
				p.rtt.push(rtt)
			}

			minP95 := time.Hour
			for _, p := range peers {
				if p.id == *myID {
					continue
				}
				p95 := p.rtt.p95()
				if p95 > 0 && p95 < minP95 {
					minP95 = p95
				}
			}
			if minP95 < time.Hour {
				baseRTT = minP95
			}

			// Identify outliers
			var newBL []uint64
			if baseRTT > 0 {
				type cand struct {
					id   uint64
					p95  time.Duration
				}
				var cands []cand
				for _, p := range peers {
					if p.id == *myID {
						continue
					}
					p95 := p.rtt.p95()
					if p95 > time.Duration(float64(baseRTT)*(*mult)) {
						cands = append(cands, cand{p.id, p95})
					}
				}
				sort.Slice(cands, func(i, j int) bool { return cands[i].p95 > cands[j].p95 })
				for i, c := range cands {
					if i >= *fCap-1 { // cap |B_t| < f
						break
					}
					newBL = append(newBL, c.id)
				}
			}

			// Fail-open after K_FAIL consecutive empty windows
			failOpen := false
			if len(newBL) == 0 {
				emptyStreak++
				if emptyStreak >= *kFail {
					failOpen = true
				}
			} else {
				emptyStreak = 0
			}

			// Bump seq; emit
			seqCounter++
			next := &advice{Blacklist: newBL, Seq: seqCounter, FailOpen: failOpen}
			prev := advicePtr.Load()
			advicePtr.Store(next)

			// Log B_t changes always (compact).
			if !sameBL(prev.Blacklist, next.Blacklist) || prev.FailOpen != next.FailOpen {
				log.Printf("Bt_change t=%d seq=%d Bt=%v failopen=%v baseRTT=%v",
					time.Now().UnixMilli(), seqCounter, newBL, failOpen, baseRTT)
			}
			// Periodic stats: per-peer p95 RTT every 2 seconds.
			select {
			case <-statsTicker.C:
				p95s := make(map[uint64]time.Duration)
				for _, pr := range peers {
					if pr.id != *myID {
						p95s[pr.id] = pr.rtt.p95()
					}
				}
				log.Printf("stats t=%d seq=%d baseRTT=%v p95=%v",
					time.Now().UnixMilli(), seqCounter, baseRTT, p95s)
			default:
			}
		}
	}()

	// Serve UDS
	_ = os.Remove(*sockPath)
	ln, err := net.Listen("unix", *sockPath)
	if err != nil {
		log.Fatalf("listen unix %s: %v", *sockPath, err)
	}
	defer ln.Close()
	_ = os.Chmod(*sockPath, 0600)
	log.Printf("UDS up on %s", *sockPath)

	// Signals
	go func() {
		sigC := make(chan os.Signal, 1)
		signal.Notify(sigC, syscall.SIGINT, syscall.SIGTERM)
		<-sigC
		log.Printf("shutdown")
		_ = ln.Close()
		_ = os.Remove(*sockPath)
		os.Exit(0)
	}()

	for {
		conn, err := ln.Accept()
		if err != nil {
			log.Printf("accept: %v", err)
			continue
		}
		go func(c net.Conn) {
			defer c.Close()
			_ = c.SetDeadline(time.Now().Add(50 * time.Millisecond))
			_ = json.NewEncoder(c).Encode(advicePtr.Load())
		}(conn)
	}
}

func splitComma(s string) []string {
	var out []string
	cur := ""
	for _, c := range s {
		if c == ',' {
			out = append(out, cur)
			cur = ""
		} else {
			cur += string(c)
		}
	}
	if cur != "" {
		out = append(out, cur)
	}
	return out
}

func splitEq(s string) []string {
	for i := 0; i < len(s); i++ {
		if s[i] == '=' {
			return []string{s[:i], s[i+1:]}
		}
	}
	return []string{s}
}

func sameBL(a, b []uint64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
