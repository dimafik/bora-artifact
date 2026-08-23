// BORA sidecar — minimal UDS server for NE26 end-to-end demo.
// Each orderer container runs one instance.
// Reads advice from /tmp/bora-advice.json, serves to local orderer
// through Unix-domain socket /var/run/raft-advisor.sock.
//
// Build:    GOOS=linux CGO_ENABLED=0 go build -o bora-sidecar bora_sidecar.go
// Run:      /tmp/bora-sidecar
// Stop:     send SIGTERM
//
// Advice file schema (the only operator-controlled input):
//   {"blacklist":[3], "seq":42, "fail_open":false}
// Sidecar reloads the file on every accept (no caching, ~5us cost).
package main

import (
	"encoding/json"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const (
	sockPath    = "/var/run/raft-advisor.sock"
	advicePath  = "/tmp/bora-advice.json"
	connTimeout = 50 * time.Millisecond
)

type advice struct {
	Blacklist []uint64 `json:"blacklist"`
	Seq       uint64   `json:"seq"`
	FailOpen  bool     `json:"fail_open"`
}

func loadAdvice() advice {
	a := advice{Blacklist: []uint64{}, Seq: 0, FailOpen: false}
	data, err := os.ReadFile(advicePath)
	if err != nil {
		return a
	}
	_ = json.Unmarshal(data, &a)
	return a
}

func main() {
	_ = os.Remove(sockPath)
	ln, err := net.Listen("unix", sockPath)
	if err != nil {
		log.Fatalf("listen unix %s: %v", sockPath, err)
	}
	defer ln.Close()
	if err := os.Chmod(sockPath, 0600); err != nil {
		log.Printf("chmod warning: %v", err)
	}
	log.Printf("BORA sidecar listening on %s", sockPath)

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
	_ = c.SetDeadline(time.Now().Add(connTimeout))
	a := loadAdvice()
	if err := json.NewEncoder(c).Encode(a); err != nil {
		log.Printf("encode: %v", err)
	}
}
