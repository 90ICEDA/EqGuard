# _bench_batch.ps1 -- measure pairs/second vs batch size (same 300 candidates, abc:aig)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\bench_batch.log'
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

$base = @('-X','utf8','-u','phase2\ys\sat_node_pairs_batch.py','--host','s38417t100','--inst','injalpha',
          '--pairs','ys_abc:ys_aig','--anchor','all','--budget','300','--per-sig','20','--timeout','120','--force')
foreach ($cfg in @(@{b=600;w=1}, @{b=300;w=3}, @{b=300;w=6})) {
  $t0 = Get-Date
  & $py @base --batch $cfg.b --workers $cfg.w 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("bench_b{0}.log" -f $cfg.b)) -Encoding UTF8
  $dt = ((Get-Date) - $t0).TotalSeconds
  Log ("batch={0} workers={1} wall={2:N1}s  -> {3:N2} pair/s" -f $cfg.b, $cfg.w, $dt, (300.0/$dt))
}
Log '=== bench done ==='
