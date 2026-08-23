# Restart the BORA predictor daemon for a given cluster size.
#
# The daemon runs on the Windows host (it needs torch and the trained model) with
# its working directory set to the model tree, because predictor_daemon_n.py
# resolves "predictor/" and "model_small/best.pt" relatively.
#
#   powershell -NoProfile -File restart_daemon.ps1 9 4
param(
    [Parameter(Mandatory = $true)][int]$N,
    [Parameter(Mandatory = $true)][int]$F
)

# ASCII-only path on purpose. Windows PowerShell 5.1 reads a .ps1 as ANSI (cp949
# here) unless the file carries a UTF-8 BOM, so a Korean path literal in this
# script is mangled when it is invoked as `powershell -File ...` from bash. That
# is exactly how the N=9 daemon failed to start: -WorkingDirectory pointed at a
# garbled path, Start-Process returned nothing, and the run proceeded against a
# frozen bt.json. alg1/model/ is a 700 KB copy of predictor/ + model_small/ +
# predictor_daemon_n.py, kept in sync by refresh_model.sh.
$modelDir = "D:\fabric-d2\alg1\model"
$log = "D:\fabric-d2\results\daemon_n$N.out"

Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*predictor_daemon_n*' } |
    ForEach-Object {
        "stopping old daemon PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 2

$daemonLog = "D:\fabric-d2\results\predictor_daemon.log"
$before = if (Test-Path $daemonLog) { (Get-Item $daemonLog).Length } else { 0 }

$p = Start-Process -FilePath "python" `
    -ArgumentList "predictor_daemon_n.py 0.65 $N $F" `
    -WorkingDirectory $modelDir `
    -RedirectStandardOutput $log `
    -RedirectStandardError "$log.err" `
    -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 10

# $p can be $null when Start-Process fails to hand back a process object, and
# $null.HasExited is itself $null -- which is falsy, so the old check sailed past
# a daemon that had never started. That cost a full N=9 run: bt.json stayed
# frozen at the previous N's output, the pusher replayed it for an hour, and the
# predictor arm was a second oracle arm wearing the predictor's name.
if ($null -eq $p) {
    "DAEMON_FAILED for N=${N}: Start-Process returned no process object"
    exit 1
}
if ($p.HasExited) {
    "DAEMON_FAILED for N=${N}: process exited immediately (code $($p.ExitCode))"
    if (Test-Path "$log.err") { Get-Content "$log.err" -Tail 10 }
    exit 1
}

# Authoritative check: the daemon itself must have appended its start banner with
# the N and f we asked for. Process liveness alone is not evidence it is the
# right daemon, or that it got far enough to load the model.
$after = if (Test-Path $daemonLog) { Get-Content $daemonLog -Tail 40 } else { @() }
$banner = $after | Where-Object { $_ -match "daemon start .*N=$N f=$F " } | Select-Object -Last 1
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
