#!/usr/bin/env python3
"""Generate crypto-config / configtx / compose for an N-orderer Raft network by
extending the existing 5-node templates. Ports: orderer=7050, orderer2=8050,
then orderer_i = 10050 + 1000*(i-3) for i >= 3 (9050 is skipped because the
test-network peer and orderer CA already own 9051/9052/9054). admin=+3, ops=+5.
Run inside test-network dir."""
import sys, re, pathlib
MAXN = 21                                  # X1 sweep runs N = 7, 9, 11, 15, 21
N = int(sys.argv[1])
TN = pathlib.Path("/mnt/d/fabric-d2/fabric-samples/test-network")
PORT = {1: 7050, 2: 8050}
PORT.update({i: 10050 + 1000 * (i - 3) for i in range(3, MAXN + 1)})
# Guard: the N=5/7/9 assignments below are baked into already-published results,
# so a future change to the formula must not silently move them.
assert [PORT[i] for i in range(1, 10)] == \
    [7050, 8050, 10050, 11050, 12050, 13050, 14050, 15050, 16050], "port scheme drift"
assert N in PORT, f"N={N} exceeds the port table (MAXN={MAXN})"
def host(i): return "orderer.example.com" if i==1 else f"orderer{i}.example.com"
def hn(i):   return "orderer" if i==1 else f"orderer{i}"

# 1) crypto-config
specs = "\n".join(f"      - Hostname: {hn(i)}\n        SANS:\n          - localhost" for i in range(1,N+1))
crypto = f"""# {N}-orderer Raft cryptogen config
OrdererOrgs:
  - Name: Orderer
    Domain: example.com
    EnableNodeOUs: true
    Specs:
{specs}
"""
(TN/"organizations/cryptogen"/f"crypto-config-orderer-{N}node.yaml").write_text(crypto)

# 2) configtx: take 5node, splice extra consenters + OrdererAddresses
src = (TN/"configtx/configtx-5node.yaml").read_text()
def cons(i):
    p=f"../organizations/ordererOrganizations/example.com/orderers/{host(i)}/tls/server.crt"
    return (f"          - Host: {host(i)}\n            Port: {PORT[i]}\n"
            f"            ClientTLSCert: {p}\n            ServerTLSCert: {p}\n")
extra_cons = "".join(cons(i) for i in range(6,N+1))
# insert extra consenters right after orderer5 consenter ServerTLSCert line
anchor_c = ("            ServerTLSCert: ../organizations/ordererOrganizations/example.com/"
            "orderers/orderer5.example.com/tls/server.crt\n")
assert src.count(anchor_c) >= 1, "consenter anchor not found"
src = src.replace(anchor_c, anchor_c + extra_cons, 1)
# OrdererEndpoints (6-space list): append orderer6..N after orderer5 (full-line match)
extra_addr_block = "".join(f"      - {host(i)}:{PORT[i]}\n" for i in range(6,N+1))
src = src.replace("      - orderer5.example.com:12050\n",
                  "      - orderer5.example.com:12050\n"+extra_addr_block)
(TN/"configtx"/f"configtx-{N}node.yaml").write_text(src)

# 3) compose: take 5node, clone orderer5 SERVICE block (anchored on container_name) for 6..N
comp = (TN/"5node-raft.yaml").read_text()
m = re.search(r"(?ms)^(  orderer5\.example\.com:\n    container_name: orderer5\.example\.com\n.*?networks:\n      - test\n)", comp)
assert m, "orderer5 service block not found"
block5 = m.group(1)
new_services = ""
for i in range(6,N+1):
    b = block5
    b = b.replace("orderer5.example.com", host(i))
    b = b.replace("12050", str(PORT[i])).replace("12053", str(PORT[i]+3)).replace("12055", str(PORT[i]+5))
    new_services += "\n" + b
comp = comp.replace(block5, block5 + new_services, 1)
# volumes
vol_extra = "".join(f"  {host(i)}:\n" for i in range(6,N+1))
comp = comp.replace("  orderer5.example.com:\n", "  orderer5.example.com:\n"+vol_extra, 1)
(TN/f"{N}node-raft.yaml").write_text(comp)
print(f"generated crypto-config-orderer-{N}node.yaml, configtx-{N}node.yaml, {N}node-raft.yaml "
      f"for N={N} (orderers {', '.join(host(i) for i in range(1,N+1))})")
