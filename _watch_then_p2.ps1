# _watch_then_p2.ps1 -- wait for sat_full_batch to finish, rebuild node artifacts, then run P2
#   step 1: poll <N4>/logs/full_batch.log for 'FULL BATCH DONE' (or until 18:10 timeout)
#   step 2: rebuild satrel_node_feats_sat.npy + satrel_node_pairs.npz
#   step 3: refresh fg_htl_ablation.csv
#   step 4: run _run_p2_all.ps1 (18 runs, sequential)
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$py   = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15  = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4   = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$fb   = Join-Path $n4.FullName 'logs\full_batch.log'
$log  = Join-Path $n4.FullName 'logs\watch_p2.log'

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

Log '=== watcher start: waiting for sat_full_batch ==='
$deadline = Get-Date '18:10'
while ($true) {
  $done = $false
  if (Test-Path $fb) {
    $tail = Get-Content $fb -Tail 40 -ErrorAction SilentlyContinue
    if ($tail -match 'FULL BATCH DONE') { $done = $true }
  }
  if ($done) { Log 'sat_full_batch: FULL BATCH DONE detected'; break }
  if ((Get-Date) -gt $deadline) { Log 'timeout 18:10 -> proceed anyway (tables may be partial)'; break }
  Start-Sleep -Seconds 60
}

Log '--- stop sat node-pair runner (free CPU for GPU) ---'
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*_run_sat_node_pairs2.ps1*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*sat_node_pairs_batch.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3
Log '  node-pair runner stopped (partial results kept, rows are written per batch)'

Log '--- rebuild node features (SAT-only, 9-dim core) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' 2>&1 | Select-Object -Last 2 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

Log '--- rebuild node-pair index (train-only) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-Object -Last 2 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

Log '--- refresh fg_htl_ablation.csv ---'
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

Log '--- launching _run_p2_all.ps1 (18 runs, sequential) ---'
& (Join-Path $root '_run_p2_all.ps1')
Log '=== watcher done ==='
