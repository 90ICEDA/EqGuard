# _run_ctl_fix2.ps1 -- rerun the 8 s38584 ctl specs (0-byte struct JSON fixed) + rebuild
#   waits for no SAT writer / no ctl_fix runner
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\ctl_fix2.log'
$flag = Join-Path $env:TEMP 'ctl_fix2.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }

Log '=== ctl-fix2 start: waiting for no SAT writer / no ctl_fix runner ==='
$dl = (Get-Date).AddHours(1)
while ($true) {
  $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
           Where-Object { $_.CommandLine -match 'sat_node_pairs_batch|satrel_node_feats_sat' } |
           Measure-Object).Count -gt 0
  $runner = (Get-CimInstance Win32_Process |
             Where-Object { $_.CommandLine -match '_run_ctl_fix\.ps1' } |
             Measure-Object).Count -gt 0
  if (-not $busy -and -not $runner) { Log 'clean -> start'; break }
  if ((Get-Date) -gt $dl) { Log 'timeout 1h -> start anyway'; break }
  Start-Sleep -Seconds 20
}

$specs = @(
  ,@('s38584t100', 'ctldup')
  ,@('s38584t100', 'ctlmatcha')
  ,@('s38584t100', 'ctlmatchb')
  ,@('s38584t100', 'ctlmatchc')
  ,@('s38584t100', 'ctlmatchd')
  ,@('s38584t100', 'ctlmatche')
  ,@('s38584t100', 'ctlmatchf')
  ,@('s38584t100', 'ctlxor')
)
Log ("=== rerun {0} s38584 ctl specs (abc:opt + abc:aig, budget 2500) ===" -f $specs.Count)
$i = 0
foreach ($s in $specs) {
  $i++
  $h = $s[0]; $inst = $s[1]
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_abc:ys_opt,ys_abc:ys_aig' `
      --anchor all --budget 2500 --per-sig 20 --prove-mode simple `
      --batch 200 --timeout 300 --workers 6 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\fix2_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("  [fix2 {0}/{1}] {2}|{3} rc={4}" -f $i, $specs.Count, $h, $inst, $LASTEXITCODE)
}

Log '--- rebuild: INCIDENT (train) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident 2>&1 |
  Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- rebuild: DRIVER (strict) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --tag-suffix '_driver' 2>&1 |
  Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- rebuild: PERM (control) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --permute-within-view --tag-suffix '_perm' 2>&1 |
  Select-String -Pattern 'coverage_any' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
Log '--- node-pair index + ablation ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-String -Pattern 'n_pairs' |
  ForEach-Object { Add-Content -Path $log -Value $_.Line -Encoding UTF8 }
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

'SAT_CTL_FIX2_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== ctl-fix2 done ==='
