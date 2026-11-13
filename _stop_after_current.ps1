# _stop_after_current.ps1 -- let the currently running safe_nomux finish, then kill
# all remaining watchers and any newly spawned training (user is going to shut down).
$root = $PSScriptRoot
$out = Join-Path $env:TEMP 'fl_fghtl_CncleanV4smuxD42.out'
$log = Join-Path $root 'logs\stop_after_current.log'
function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}
Log 'waiting for safe_nomux to finish'
$deadline = (Get-Date).AddHours(2)
while ((Get-Date) -lt $deadline) {
  $done = $false
  if (Test-Path $out) {
    $tail = Get-Content $out -Tail 5 -ErrorAction SilentlyContinue
    if ($tail -match '完成') { $done = $true }
  }
  $proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
          Where-Object { $_.CommandLine -match 'train_test2.3' -and $_.CommandLine -match 'safe_nomux' }
  if ($done -or (-not $proc)) { break }
  Start-Sleep -Seconds 15
}
Log 'safe_nomux finished (or vanished) -> stopping all watchers'
Start-Sleep -Seconds 3

# 1) kill watchers / launchers
$pat = '_run_c_v4_featloc|_run_c_v4_rand2|_run_c_v4_randsupport|_run_after_reboot|_run_c_v4_vpermD|_run_c_v4_dump2'
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $pat } | ForEach-Object {
  Log ("kill watcher {0}" -f $_.ProcessId)
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

# 2) kill any training python (including the next run that may have just started)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'train_test2.3' } | ForEach-Object {
    Log ("kill training {0}" -f $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Start-Sleep -Seconds 5

$left = (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'train_test2.3|_run_c_v4' } |
         Select-Object -ExpandProperty ProcessId) -join ','
Log ("remaining pids: [{0}]" -f $left)
try { & nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | ForEach-Object { Log ("GPU {0}" -f $_) } } catch {}
Log '=== all training stopped ==='
