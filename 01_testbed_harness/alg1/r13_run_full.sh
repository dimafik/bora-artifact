#!/usr/bin/env bash
# Zero-argument wrapper for the R1-3 full run.
#
# Everything -- the cd, the timeout, the redirect -- lives here rather than in
# the launching command line.  Three launch attempts failed today purely on
# quoting and process ownership:
#   * `wsl -e bash -lc '... & disown'`  -> child dies when the wsl session ends
#   * `setsid nohup ... &` inside that  -> same
#   * PowerShell Start-Process with an -ArgumentList containing `&&` and `>`
#                                       -> the redirect never reached bash
# With no arguments to quote, the only thing the caller supplies is this path.
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 16200 bash alg1/r13_authority.sh 7 3 300 0 5 10 20 \
  > /mnt/d/fabric-d2/results/r13_full3.log 2>&1
