import io, os, re, glob
RES = "D:/fabric-d2/results"
ARMS = ["C_clean", "F_follower", "L_leader", "C_clean_post"]
row_re = re.compile(
    r"\|\s*rate-(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|"
    r"\s*([\d.-]+)\s*\|\s*([\d.-]+)\s*\|\s*([\d.-]+)\s*\|\s*([\d.]+)\s*\|")

def parse(d):
    p = os.path.join(d, "summary.txt")
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    out, arm = {}, None
    for line in txt.splitlines():
        m = re.match(r"=====\s*(\w+)", line.strip())
        if m and m.group(1) in ARMS:
            arm = m.group(1); out.setdefault(arm, {}); continue
        r = row_re.search(line)
        if r and arm:
            rt = int(r.group(1))
            if rt in out[arm]: continue
            out[arm][rt] = dict(succ=int(r.group(2)), fail=int(r.group(3)),
                                lat=r.group(7), tput=float(r.group(8)))
    return out

runs = []
for d in sorted(glob.glob(os.path.join(RES, "r25c_2*"))):
    p = parse(d)
    if all(a in p and 500 in p[a] for a in ("C_clean", "F_follower", "L_leader")):
        runs.append((os.path.basename(d)[5:], p))

print("rate-500, all six valid runs")
print("%-16s %9s %9s %9s %9s | %8s %8s" % (
    "run", "clean", "follow", "leader", "post", "L fail%", "post f%"))
for n, p in runs:
    c = p["C_clean"][500]; f = p["F_follower"][500]; l = p["L_leader"][500]
    po = p.get("C_clean_post", {}).get(500)
    lf = 100.0*l["fail"]/max(1, l["succ"]+l["fail"])
    pf = 100.0*po["fail"]/max(1, po["succ"]+po["fail"]) if po else float("nan")
    print("%-16s %9.1f %9.1f %9.1f %9s | %7.1f%% %7.1f%%" % (
        n, c["tput"], f["tput"], l["tput"],
        ("%.1f" % po["tput"]) if po else "-", lf, pf))

print()
print("C_clean_post by rate (does the cluster recover within the bracket?)")
print("%-16s %8s %8s %8s %8s %8s" % ("run", "100", "200", "300", "400", "500"))
for n, p in runs:
    po = p.get("C_clean_post", {})
    cells = []
    for rt in (100, 200, 300, 400, 500):
        cells.append(("%.1f" % po[rt]["tput"]) if rt in po else "-")
    print("%-16s %8s %8s %8s %8s %8s" % (n, *cells))

print()
print("C_clean by rate (is there drift BEFORE L_leader?)")
print("%-16s %8s %8s %8s %8s %8s" % ("run", "100", "200", "300", "400", "500"))
for n, p in runs:
    c = p["C_clean"]
    print("%-16s %8.1f %8.1f %8.1f %8.1f %8.1f" % (
        n, c[100]["tput"], c[200]["tput"], c[300]["tput"], c[400]["tput"], c[500]["tput"]))

print()
print("the two anomalous follower runs (Rf=0.321): F_follower by rate")
for n, p in runs:
    f = p["F_follower"]
    if abs(f[500]["tput"] - 150.0) < 1.0:
        print("  %s : %s" % (n, " ".join("%.1f" % f[rt]["tput"] for rt in (100,200,300,400,500))))
        print("      fails: %s" % " ".join(str(f[rt]["fail"]) for rt in (100,200,300,400,500)))
