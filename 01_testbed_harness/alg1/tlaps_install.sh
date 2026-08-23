#!/usr/bin/env bash
# No-sudo TLAPS install to ~/tlaps (bundles Isabelle/Zenon/tlapm).
set -u
cd /tmp
URL="https://github.com/tlaplus/tlapm/releases/download/202210041448/tlaps-1.5.0-x86_64-linux-gnu-inst.bin"
echo "=== download installer ==="
timeout 300 curl -sSL -o /tmp/tlaps.bin "$URL" 2>&1 | tail -2
ls -la /tmp/tlaps.bin
echo "=== build tools present? ==="
which gcc make 2>/dev/null || echo "no gcc/make (may be needed)"
echo "=== run installer -> ~/tlaps ==="
chmod +x /tmp/tlaps.bin
rm -rf ~/tlaps
bash /tmp/tlaps.bin -d "$HOME/tlaps" >/tmp/tlaps_inst.log 2>&1
echo "installer exit=$?"
tail -8 /tmp/tlaps_inst.log
echo "=== verify tlapm ==="
~/tlaps/bin/tlapm --version 2>&1 | head -2 || echo "TLAPM_NOT_FOUND"
echo "TLAPS_INSTALL_DONE"
