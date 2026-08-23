// BORA sidecar v3 — standing-advice mode with per-read monotonic seq.
//
// Motivation: the etcdraft hook accepts advice only when seq strictly
// increases (replay protection), then suppresses the local election tick if
// this node's raftID is in B_t. With v1 (static seq read from the file) the
// suppression therefore fired for a SINGLE tick per file write, which is far
// too weak to prevent a campaign (the election timer needs ~10 consecutive
// suppressed ticks). v3 fixes this: it reloads the OPERATOR-controlled
// blacklist + fail_open from /tmp/bora-advice.json on every accept, but
// serves a seq from an atomic counter that increments on EVERY read. Because
// the orderer reads the socket once per Raft tick, seq is fresh every tick,
// so a standing B_t is enforced every tick — i.e. continuous leadership
// exclusion, which is exactly the mechanism the paper describes.
//
// Replay protection of the ADVICE CONTENT is preserved: when the operator
// clears the blacklist to [], the sidecar serves [] (fresh seq) and the
// orderer immediately stops suppressing. Only the nonce is auto-fresh.
//
// Build: GOOS=linux CGO_ENABLED=0 go build -o bora-sidecar-v3 bora_sidecar_v3.go
package main

import (
	"encoding/json"
	"log"
	"net"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

const (
	sockPath   = "/var/run/raft-advisor.sock"
	advicePath = "/tmp/bora-advice.json"
)

type fileAdvice struct {
	Blacklist []uint64 `json:"blacklist"`
	Seq       uint64   `json:"seq"` // ignored for emission; content nonce only
	FailOpen  bool     `json:"fail_open"`
}

type wireAdvice struct {
	Blacklist []uint64 `json:"blacklist"`
	Seq       uint64   `json:"seq"`
	FailOpen  bool     `json:"fail_open"`
}

var seqCounter uint64 // monotonic, incremented per read

func loadFile() fileAdvice {
	a := fileAdvice{Blacklist: []uint64{}, FailOpen: false}
	data, err := os.ReadFile(advicePath)
	if err != nil {
		return a
	}
	_ = json.Unmarshal(data, &a)
	if a.Blacklist == nil {
		a.Blacklist = []uint64{}
	}
	return a
}

func main() {
	_ = os.Remove(sockPath)
	ln, err := net.Listen("unix", sockPath)
	if err != nil {
		log.Fatalf("listen unix %s: %v", sockPath, err)
	}
	defer ln.Close()
	_ = os.Chmod(sockPath, 0600)
	log.Printf("BORA sidecar v3 (per-read seq) listening on %s", sockPath)

	sigC := make(chan os.Signal, 1)
	signal.Notify(sigC, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigC
		log.Printf("shutdown")
		_ = ln.Close()
		_ = os.Remove(sockPath)
		os.Exit(0)
	}()

	for {
		conn, err := ln.Accept()
		if err != nil {
			log.Printf("accept: %v", err)
			continue
		}
		go handle(conn)
	}
}

func handle(c net.Conn) {
	defer c.Close()
	_ = c.SetDeadline(time.Now().Add(50 * time.Millisecond))
	f := loadFile()
	w := wireAdvice{
		Blacklist: f.Blacklist,
		Seq:       atomic.AddUint64(&seqCounter, 1), // fresh every read
		FailOpen:  f.FailOpen,
	}
	if err := json.NewEncoder(c).Encode(w); err != nil {
		log.Printf("encode: %v", err)
	}
}
