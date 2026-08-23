#!/usr/bin/env python3
"""Validate the artifacts gen_nnode.py produces for a given N.

Checks that the compose file and configtx actually describe N distinct orderers:
service count, unique container names, unique published host ports, unique
listen/admin/ops triples, no cross-contaminated MSP or TLS paths, and a consenter
set of size N with unique host:port. Run inside test-network:
    python3 _validate_gen.py 11 21
"""
import sys, collections, yaml

BAD = 0


def walk(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(o, list):
        for i in o:
            yield from walk(i, key)


def check(label, cond, detail=""):
    global BAD
    if not cond:
        BAD += 1
    print("  %-34s %s %s" % (label, "OK  " if cond else "FAIL", detail))


for N in [int(a) for a in sys.argv[1:]]:
    print("=" * 52)
    print("N =", N)
    c = yaml.safe_load(open("%dnode-raft.yaml" % N))
    svc = [s for s in c["services"] if "orderer" in s]
    vols = [v for v in (c.get("volumes") or []) if "orderer" in v]

    check("orderer services == N", len(svc) == N, "(%d)" % len(svc))
    check("orderer volumes == N", len(vols) == N, "(%d)" % len(vols))

    names = [c["services"][s].get("container_name") for s in svc]
    check("container_name unique", len(set(names)) == len(names))

    ports = []
    for s in c["services"]:
        for p in c["services"][s].get("ports") or []:
            ports.append(str(p).split(":")[0])
    dup = [p for p, k in collections.Counter(ports).items() if k > 1]
    check("published host ports unique", not dup, "(%d ports, dup=%s)" % (len(ports), dup or "none"))

    triples = []
    for s in svc:
        d = dict(x.split("=", 1) for x in c["services"][s]["environment"] if "=" in x)
        triples.append((d["ORDERER_GENERAL_LISTENPORT"],
                        d["ORDERER_ADMIN_LISTENADDRESS"].split(":")[-1],
                        d["ORDERER_OPERATIONS_LISTENADDRESS"].split(":")[-1]))
    check("(listen,admin,ops) unique", len(set(triples)) == len(triples))

    # every mounted MSP/TLS path must belong to that same orderer
    bad = []
    for s in svc:
        cn = c["services"][s]["container_name"]
        for v in c["services"][s]["volumes"]:
            if "orderers/" in v and cn not in v:
                bad.append((cn, v))
    check("MSP/TLS paths not cross-wired", not bad, str(bad[:2]))

    # operations address must name its own host, not a stale orderer5
    stale = [s for s in svc
             if dict(x.split("=", 1) for x in c["services"][s]["environment"] if "=" in x)
             ["ORDERER_OPERATIONS_LISTENADDRESS"].split(":")[0] != c["services"][s]["container_name"]]
    check("ops address matches own host", not stale, str(stale[:3]))

    t = yaml.safe_load(open("configtx/configtx-%dnode.yaml" % N))
    cons = [x for x in walk(t, "Consenters") if x]
    eps = [x for x in walk(t, "OrdererEndpoints") if x]
    check("configtx Consenters == N", all(len(x) == N for x in cons), str([len(x) for x in cons]))
    check("configtx OrdererEndpoints == N", all(len(x) == N for x in eps), str([len(x) for x in eps]))
    hp = ["%s:%s" % (x["Host"], x["Port"]) for x in cons[0]]
    check("consenter host:port unique", len(set(hp)) == len(hp), "last=%s" % hp[-1])

    # consenter ports must match the compose published ports for the same host
    compose_lp = {}
    for s in svc:
        d = dict(x.split("=", 1) for x in c["services"][s]["environment"] if "=" in x)
        compose_lp[c["services"][s]["container_name"]] = int(d["ORDERER_GENERAL_LISTENPORT"])
    mism = [(x["Host"], x["Port"], compose_lp.get(x["Host"]))
            for x in cons[0] if compose_lp.get(x["Host"]) != x["Port"]]
    check("consenter port == compose port", not mism, str(mism[:3]))

    crypto = yaml.safe_load(open("organizations/cryptogen/crypto-config-orderer-%dnode.yaml" % N))
    specs = crypto["OrdererOrgs"][0]["Specs"]
    check("cryptogen Specs == N", len(specs) == N, "(%d)" % len(specs))

print("=" * 52)
print("FAILURES:", BAD)
sys.exit(1 if BAD else 0)
