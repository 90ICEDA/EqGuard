# _run_after_third2.ps1 -- after ctl_third.done: FULL npz -> smoke ALL variants -> only then GPU queue v2
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\after_third2.log'
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

Log '=== waiting for ctl_third.done ==='
$dl = (Get-Date).AddHours(2)
while (-not (Test-Path (Join-Path $env:TEMP 'ctl_third.done'))) {
  if ((Get-Date) -gt $dl) { Log 'timeout 2h -> abort'; exit 1 }
  Start-Sleep -Seconds 30
}
# wait until no SAT/feature writer
while ($true) {
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'sat_node_pairs_batch|satrel_node_feats_sat|satrel_node_pairs_npz' } |
           Measure-Object).Count -gt 0
  if (-not $busy) { break }
  Start-Sleep -Seconds 20
}
Log 'ctl_third done + no SAT writer'

Log '--- rebuild FULL node-pair npz (--include-nontrain) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' --include-nontrain 2>&1 |
  Select-String -Pattern 'n_pairs|\[out\]' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8; Write-Host $_.Line }
$meta = Join-Path $root 'generate_trans\folds\hosts_bt31\data\processed\satrel_node_pairs_meta.json'
if (Test-Path $meta) {
  $m = Get-Content $meta -Raw | ConvertFrom-Json
  Log ("npz n_pairs={0} train_only={1}" -f $m.n_pairs, $m.train_only)
  if ($m.train_only) { Log 'ERROR: npz still train_only -> abort'; exit 1 }
}

Log '--- smoke ALL variants (C_n / D_n / E_n / P3-LRO) ---'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root '_smoke_all.ps1') 2>&1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }
$rc = $LASTEXITCODE
Log ("smoke-all rc={0}" -f $rc)
if ($rc -ne 0) { Log 'SMOKE FAILED -> GPU queue NOT started'; exit 1 }

Log 'all smokes OK -> launching _run_gpu_final2.ps1'
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root '_run_gpu_final2.ps1') -WindowStyle Hidden
Log 'launched'
