# _trial_third_pair.ps1 -- time ONE spec for a candidate 3rd ctl pair
#   writes to %TEMP% only (never touches the main node_pairs_sat_node.csv)
param([string]$h = 's38584t100', [string]$inst = 'ctlxor',
      [string]$pairs = 'ys_opt:ys_aig', [string]$tag = '')
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
if (-not $tag) { $tag = ($pairs -replace ':', '_') }
$out = Join-Path $env:TEMP ("third_pair_{0}_{1}_{2}.csv" -f $h, $inst, $tag)
$log = Join-Path $env:TEMP ("third_pair_{0}_{1}_{2}.log" -f $h, $inst, $tag)
if (Test-Path $out) { Remove-Item $out -Force }
if (Test-Path $log) { Remove-Item $log -Force }
$t0 = Get-Date
& $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
    --host $h --inst $inst --pairs $pairs `
    --anchor all --budget 2500 --per-sig 20 --prove-mode simple `
    --batch 200 --timeout 300 --workers 6 --out $out --force *> $log
$rc = $LASTEXITCODE
$dt = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
"ELAPSED_S=$dt RC=$rc PAIRS=$pairs OUT=$out" | Tee-Object -FilePath $log -Append
