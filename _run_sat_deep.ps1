# _run_sat_deep.ps1 -- DEEP node-pair SAT run (target: coverage 10% -> 30%)
#   waits for the GPU smoke test to finish (avoid GPU/SAT contention)
#   for each inj*/a4* spec: 3 recipe pairs, full-ish pool, 5 parallel yosys batches
#   then rebuilds features / pairs / ablation table and prints coverage
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$py   = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15  = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4   = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log  = Join-Path $n4.FullName 'logs\sat_deep.log'
$flag = Join-Path $env:TEMP 'sat_deep.done'
$smoke = Join-Path $env:TEMP 'node_smoke.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

Log '=== SAT deep start: waiting for GPU smoke to finish ==='
$deadline = Get-Date '16:45'
while ($true) {
  if (Test-Path $smoke) { Log 'node smoke done -> start SAT'; break }
  if ((Get-Date) -gt $deadline) { Log 'timeout 16:45 -> start SAT now (GPU smoke may run in parallel) -> start SAT anyway'; break }
  Start-Sleep -Seconds 30
}

# ---- spec list: inj*/a4* instances (a4 has no canonical -> keep* variant is fine) ----
$tdir = Join-Path $root 'generate_trans\folds\hosts_bt31\trans'
$specs = @()
foreach ($f in (Get-ChildItem $tdir -Filter '*_d1_s42__*.v')) {
  $stem = $f.BaseName                       # host__inst_d1_s42__<recipe>
  if ($stem -notmatch '^(?<h>[^_]+)__(?<i>.+?)_d1_s42__') { continue }
  $h = $Matches['h']; $i = $Matches['i']
  if ($i -like 'inj*' -or $i -like 'a4*') { $specs += ,@($h, $i) }
}
$specs = $specs | Sort-Object { $_[0] }, { $_[1] } -Unique
Log ("specs = {0}" -f $specs.Count)

# ---- Phase A: ys_abc:ys_opt (measured 99.9% proved) ----
Log '=== PHASE A: abc:opt (99.9% proved) ==='
$i = 0
foreach ($s in $specs) {
  $i++
  $h = $s[0]; $inst = $s[1]
  Log ("--- [A {0}/{1}] {2}|{3}" -f $i, $specs.Count, $h, $inst)
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_abc:ys_opt' `
      --anchor all --budget 0 --per-sig 20 --batch 200 --timeout 300 `
      --workers 3 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\deepA_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("    rc={0}" -f $LASTEXITCODE)
}

# ---- Phase B: abc->aig / abc->nand (measured 300/300 proved on abc:aig) ----
Log '=== PHASE B: abc:aig + abc:nand (ABC-output pairs, ~100% proved) ==='
$stopB = Get-Date '00:30'
$i = 0
foreach ($s in $specs) {
  $i++
  if ((Get-Date) -gt $stopB) { Log 'time guard 00:30 hit -> PHASE B stopped'; break }
  $h = $s[0]; $inst = $s[1]
  Log ("--- [B {0}/{1}] {2}|{3}" -f $i, $specs.Count, $h, $inst)
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_abc:ys_aig,ys_abc:ys_nand' `
      --anchor all --budget 0 --per-sig 20 --batch 200 --timeout 300 `
      --workers 3 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\deepB_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("    rc={0}" -f $LASTEXITCODE)
}

# ---- Phase C: opt->aig / opt->nand (same ABC family) ----
Log '=== PHASE C: opt:aig + opt:nand (budget 3000/pair) ==='
$stopC = Get-Date '02:30'
$i = 0
foreach ($s in $specs) {
  $i++
  if ((Get-Date) -gt $stopC) { Log 'time guard 02:30 hit -> PHASE C stopped'; break }
  $h = $s[0]; $inst = $s[1]
  Log ("--- [C {0}/{1}] {2}|{3}" -f $i, $specs.Count, $h, $inst)
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_opt:ys_aig,ys_opt:ys_nand' `
      --anchor all --budget 3000 --per-sig 20 --batch 200 --timeout 300 `
      --workers 3 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\deepC_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("    rc={0}" -f $LASTEXITCODE)
}

# ---- Phase D: id -> abc/opt (low yield 20-27%, lowest priority) ----
Log '=== PHASE D: id:abc + id:opt (low yield, budget 1500/pair) ==='
$stopD = Get-Date '03:00'
$i = 0
foreach ($s in $specs) {
  $i++
  if ((Get-Date) -gt $stopD) { Log 'time guard 03:00 hit -> PHASE D stopped'; break }
  $h = $s[0]; $inst = $s[1]
  Log ("--- [D {0}/{1}] {2}|{3}" -f $i, $specs.Count, $h, $inst)
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_id:ys_abc,ys_id:ys_opt' `
      --anchor all --budget 1500 --per-sig 20 --batch 200 --timeout 300 `
      --workers 3 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\deepD_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("    rc={0}" -f $LASTEXITCODE)
}
Log '--- rebuild node features (INCIDENT = training version) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident 2>&1 | Select-String -Pattern 'coverage_any|\[out\]' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- also write DRIVER-ONLY copy (strict paper number) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --tag-suffix '_driver' 2>&1 | Select-String -Pattern 'coverage_any|\[out\]' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- rebuild node-pair index ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-String -Pattern 'n_pairs|\[out\]' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- refresh fg_htl_ablation.csv ---'
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
'SAT_DEEP_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== SAT deep done ==='
