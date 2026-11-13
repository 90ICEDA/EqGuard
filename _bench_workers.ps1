# _bench_workers.ps1 -- proper parallelism test (budget 1200 => 6 batches of 200)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\bench_workers.log'
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

$base = @('-X','utf8','-u','phase2\ys\sat_node_pairs_batch.py','--host','s38417t100','--inst','injalpha',
          '--pairs','ys_opt:ys_aig','--anchor','all','--budget','1200','--per-sig','20',
          '--batch','200','--timeout','300','--force')
foreach ($w in @(1,3,6)) {
  $t0 = Get-Date
  & $py @base --workers $w 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("bench_w{0}.log" -f $w)) -Encoding UTF8
  $dt = ((Get-Date) - $t0).TotalSeconds
  Log ("workers={0} wall={1:N1}s" -f $w, $dt)
}
Log '=== bench workers done ==='
