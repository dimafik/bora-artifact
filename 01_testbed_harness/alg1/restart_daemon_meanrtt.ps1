# Restart the B-20 zero-parameter advisor daemon for a given cluster size.
#
# Same contract as restart_daemon.ps1: it kills whatever advisor is publishing,
# starts this one, and refuses to report success unless the daemon's own start
# banner names the N and f that were asked for. Process liveness is not evidence
# that the right daemon started -- that mistake cost a whole N=9 arm once, and
# the check below is the one that would have caught it.
#
#   powershell -NoProfile -File restart_daemon_meanrtt.ps1 7 3
param(
    [Parameter(Mandatory = $true)][int]$N,
    [Parameter(Mandatory = $true)][int]$F
)

# ASCII-only path on purpose; see restart_daemon.ps1 for why.
$alg1 = "D:\fabric-d2\alg1"
$log = "D:\fabric-d2\results\daemon_meanrtt_n$N.out"
$daemonLog = "D:\fabric-d2\results\predictor_daemon_meanrtt.log"

# Stop BOTH advisors: the Transformer one would otherwise keep rewriting the
# same bt.json this daemon publishes to, and the arm would be a mixture.
Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*predictor_daemon_n*' -or
                   $_.CommandLine -like '*predictor_daemon_meanrtt*' } |
    ForEach-Object {
        "stopping advisor PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 2

$before = if (Test-Path $daemonLog) { (Get-Item $daemonLog).Length } else { 0 }

$p = Start-Process -FilePath "python" `
    -ArgumentList "predictor_daemon_meanrtt.py 0.65 $N $F 50" `
    -WorkingDirectory $alg1 `
    -RedirectStandardOutput $log `
    -RedirectStandardError "$log.err" `
    -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 8

if ($null -eq $p) {
    "DAEMON_FAILED for N=${N}: Start-Process returned no process object"
    exit 1
}

$after = if (Test-Path $daemonLog) { Get-Content $daemonLog -Tail 40 } else { @() }
$banner = $after | Where-Object { $_ -match "meanrtt daemon start .*N=$N f=$F " } | Select-Object -Last 1
if (-not $banner) {
    "DAEMON_FAILED for N=${N}: no 'N=$N f=$F' start banner in $daemonLog"
    if (Test-Path "$log.err") { Get-Content "$log.err" -Tail 10 }
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
if ((Get-Item $daemonLog).Length -le $before) {
    "DAEMON_FAILED for N=${N}: daemon log did not grow"
    exit 1
}

"DAEMON_OK N=$N f=$F PID=$($p.Id)"
"  banner: $banner"
exit 0
