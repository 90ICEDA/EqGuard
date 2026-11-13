# _run_sat_node_pairs.ps1 -- P2-D/E node-level SAT pair batch (background, resumable)
#   output: <N4>/tables/node_pairs_sat_node.csv
#   policy: --anchor all (unbiased mask) ; --budget 600 ; --batch 25
#   NOTE: ASCII-only paths on purpose (PowerShell 5.1 reads .ps1 as ANSI -> CJK literals break)
$root = $PSScriptRoot
Set-Location $root
$py   = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15  = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4   = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' })[0]
$out  = Join-Path $n4.FullName 'tables\node_pairs_sat_node.csv'
$log  = Join-Path $n4.FullName 'logs\sat_node_pairs_run.log'

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

Log '=== SAT node-pair batch start ==='

# ---- Phase A：小宿主（快 ✓ 覆盖率高 ✓）----
$small = @{
  'rs232t1000' = @('injalpha','injbeta','injepsilon','injgamma','injzeta')
  's15850t100' = @('injalpha','injdelta','injepsilon','injgamma','injzeta')
}
foreach ($h in $small.Keys) {
  foreach ($i in $small[$h]) {
    Log "A $h/$i"
    & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' --host $h --inst $i `
        --pairs 'ys_id:ys_abc,ys_abc:ys_opt,ys_id:ys_opt' --anchor all `
        --budget 600 --batch 25 --timeout 90 --out $out 2>&1 |
      Select-Object -Last 4 | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
  }
}

# ---- Phase B：大宿主（慢 ✓ 每 spec ≈2–3 min ✓）----
$big = @{
  's35932t200' = @('injalpha','injbeta','injepsilon','injzeta')
  's38417t100' = @('injalpha','injbeta','injepsilon','injgamma','injzeta')
  's38584t100' = @('injalpha','injdelta','injepsilon','injgamma','injzeta')
}
foreach ($h in $big.Keys) {
  foreach ($i in $big[$h]) {
    Log "B $h/$i"
    & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' --host $h --inst $i `
        --pairs 'ys_id:ys_abc,ys_abc:ys_opt,ys_id:ys_opt' --anchor all `
        --budget 600 --batch 25 --timeout 120 --out $out 2>&1 |
      Select-Object -Last 4 | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
  }
}

# ---- Phase C：a4 三胞胎【跨实例】✓（E 组节点级 L_pair 必需 ✓）----
foreach ($h in @('rs232t1000','s15850t100')) {
  foreach ($s in @('s0','s1')) {
    foreach ($rcp in @('ys_abc','ys_id')) {
      foreach ($pair in @(
          @{a="a4trojan_$s"; b="a4ctlequiv_$s"},
          @{a="a4trojan_$s"; b="a4ctldead_$s"},
          @{a="a4ctlequiv_$s"; b="a4ctldead_$s"})) {
        Log "C $h $($pair.a) vs $($pair.b) $rcp"
        & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' --host $h `
            --inst $pair.a --inst-b $pair.b --recipe $rcp --anchor all `
            --budget 200 --batch 25 --timeout 90 --out $out 2>&1 |
          Select-Object -Last 4 | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
      }
    }
  }
}

Log '=== SAT node-pair batch done ==='
'DONE ' + (Get-Date -Format s) | Add-Content -Path $log -Encoding UTF8
