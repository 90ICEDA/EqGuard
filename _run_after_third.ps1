# _run_after_third.ps1 -- after ctl_third.done: rebuild FULL node-pair npz (all views) then start GPU queue v2
#   The full npz is required for LOCO/LIO/LRO; train_test2.3.py now filters by the current split train_mask.
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\after_third.log'
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

Log '=== waiting for ctl_third.done ==='
$dl = (Get-Date).AddHours(2)
while (-not (Test-Path (Join-Path $env:TEMP 'ctl_third.done'))) {
  if ((Get-Date) -gt $dl) { Log 'timeout 2h -> abort'; exit 1 }
  Start-Sleep -Seconds 30
}
Log 'ctl_third done -> rebuild FULL node-pair npz (--include-nontrain)'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' --include-nontrain 2>&1 |
  Select-String -Pattern 'n_pairs|\[out\]' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8; Write-Host $_.Line }
Log 'full npz done -> launching _run_gpu_final2.ps1'
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root '_run_gpu_final2.ps1') -WindowStyle Hidden
Log 'launched'
