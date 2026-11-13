# _run_sat_deep2.ps1 -- PHASE B/C/D only (A already done); deadlines are RELATIVE (bug fix)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\sat_deep2.log'
$flag = Join-Path $env:TEMP 'sat_deep2.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

$tdir = Join-Path $root 'generate_trans\folds\hosts_bt31\trans'
$specs = @()
foreach ($f in (Get-ChildItem $tdir -Filter '*_d1_s42__*.v')) {
  if ($f.BaseName -notmatch '^(?<h>[^_]+)__(?<i>.+?)_d1_s42__') { continue }
  $h = $Matches['h']; $i = $Matches['i']
  if ($i -like 'inj*' -or $i -like 'a4*') { $specs += ,@($h, $i) }
}
$specs = $specs | Sort-Object { $_[0] }, { $_[1] } -Unique
Log ("specs = {0}" -f $specs.Count)

function Run-Phase([string]$name, [string]$pairs, [int]$budget, [datetime]$stopAt) {
  Log ("=== PHASE {0}: pairs={1} budget={2} stopAt={3:HH:mm} ===" -f $name, $pairs, $budget, $stopAt)
  $i = 0
  foreach ($s in $specs) {
    $i++
    if ((Get-Date) -gt $stopAt) { Log ("time guard {0:HH:mm} hit -> PHASE {1} stopped" -f $stopAt, $name); break }
    $h = $s[0]; $inst = $s[1]
    & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
        --host $h --inst $inst --pairs $pairs `
        --anchor all --budget $budget --per-sig 20 --batch 200 --timeout 300 `
        --workers 3 --skip-covered --force 2>&1 |
      Out-File -FilePath (Join-Path $n4.FullName ("logs\deep{0}_{1}_{2}.log" -f $name, $h, $inst)) -Encoding UTF8
    Log ("  [{0} {1}/{2}] {3}|{4} rc={5}" -f $name, $i, $specs.Count, $h, $inst, $LASTEXITCODE)
  }
}

Run-Phase 'B' 'ys_abc:ys_aig,ys_abc:ys_nand' 0     ((Get-Date).AddHours(4))
Run-Phase 'C' 'ys_opt:ys_aig,ys_opt:ys_nand' 3000  ((Get-Date).AddHours(7))
Run-Phase 'D' 'ys_id:ys_abc,ys_id:ys_opt'    1500  ((Get-Date).AddHours(9))

Log '--- rebuild node features (INCIDENT = training) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident 2>&1 | Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- driver-only copy (strict) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --tag-suffix '_driver' 2>&1 | Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- node-pair index + table ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-String -Pattern 'n_pairs' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
'SAT_DEEP2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== deep2 done ==='
