# _run_ctl_third.ps1 -- 3rd ctl pair (abc:nand) for all ctl specs + rebuild + incident-perm control
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\ctl_third.log'
$flag = Join-Path $env:TEMP 'ctl_third.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

$tdir = Join-Path $root 'generate_trans\folds\hosts_bt31\trans'
$ctl = @()
foreach ($f in (Get-ChildItem $tdir -Filter '*__ctl*_d1_s42__*.v')) {
  if ($f.BaseName -notmatch '^(?<h>[^_]+)__(?<i>ctl[^_]+)_d1_s42__') { continue }
  $ctl += ,@($Matches['h'], $Matches['i'])
}
$ctl = $ctl | Sort-Object { $_[0] }, { $_[1] } -Unique
Log ("=== 3rd ctl pair abc:nand | specs={0} | budget 2500 ===" -f $ctl.Count)

$i = 0
foreach ($s in $ctl) {
  $i++
  $h = $s[0]; $inst = $s[1]
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_abc:ys_nand' `
      --anchor all --budget 2500 --per-sig 20 --prove-mode simple `
      --batch 200 --timeout 300 --workers 6 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\third_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("  [third {0}/{1}] {2}|{3} rc={4}" -f $i, $ctl.Count, $h, $inst, $LASTEXITCODE)
}

Log '--- rebuild: INCIDENT (train) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident 2>&1 |
  Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- rebuild: DRIVER (strict) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --tag-suffix '_driver' 2>&1 |
  Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- build: INCIDENT-PERM control (matched to main training) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident --permute-within-view `
    --tag-suffix '_perm_incident' 2>&1 |
  Select-String -Pattern 'coverage_any|\[PERM\]' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- node-pair index + ablation ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-String -Pattern 'n_pairs' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

'SAT_CTL_THIRD_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== ctl-third done ==='
