# _bench_workers2.ps1 -- does higher parallelism help at scale? (separate --out, no main-CSV writes)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$tmp = Join-Path $env:TEMP 'bench_w.csv'
$log = Join-Path $env:TEMP 'bench_workers2.log'
if (Test-Path $tmp) { Remove-Item $tmp -Force }
foreach ($w in @(1,6)) {
  $t0 = Get-Date
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' --host s38584t100 --inst injepsilon `
      --pairs ys_opt:ys_nand --anchor all --budget 2400 --per-sig 20 --batch 200 `
      --timeout 300 --workers $w --force --out $tmp *> $null
  $dt = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
  Add-Content -Path $log -Value ("workers={0} wall={1}s" -f $w, $dt) -Encoding UTF8
  Write-Host ("workers={0} wall={1}s" -f $w, $dt)
}
Add-Content -Path $log -Value '=== bench2 done ===' -Encoding UTF8
