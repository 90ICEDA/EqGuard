# _run_ctl_fix.ps1 -- repair CSV + rerun the 9 ctl specs killed by "No space left" + rebuild
#   waits for sat_phase3.done (phase3 pipeline finished) and for no SAT writer
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$py = Join-Path $root 'ginvenv\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4 = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\ctl_fix.log'
$flag = Join-Path $env:TEMP 'ctl_fix.done'
if (Test-Path $flag) { Remove-Item $flag -Force }
function Log($m) { $l = "[{0}] {1}" -f (Get-Date -Format 'HH:mm'), $m; Add-Content -Path $log -Value $l -Encoding UTF8; Write-Host $l }
function Wait-NoSat {
  while ($true) {
    $busy = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'sat_node_pairs_batch|sat_functional_relations|sat_sweep_pairs|satrel_node_feats_sat' } |
             Measure-Object).Count -gt 0
    if (-not $busy) { return }
    Start-Sleep -Seconds 30
  }
}

Log '=== ctl-fix start: waiting for sat_phase3.done ==='
$dl = (Get-Date).AddHours(2)
while (-not (Test-Path (Join-Path $env:TEMP 'sat_phase3.done'))) {
  if ((Get-Date) -gt $dl) { Log 'timeout 2h -> stop waiting'; break }
  Start-Sleep -Seconds 30
}
Wait-NoSat
Log 'phase3 finished + no SAT writer'

# ---------- 0) repair the truncated CSV row ----------
Log '--- repair node_pairs_sat_node.csv (drop truncated row from disk-full crash) ---'
& $py -X utf8 -u 'phase2\ys\fix_node_pairs_csv.py' 2>&1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8; Write-Host $_ }

# ---------- 1) rerun specs killed at 23:52 (rc=1 / rc=-1) ----------
$specs = @(
  ,@('s38417t100', 'ctlxor')
  ,@('s38584t100', 'ctldup')
  ,@('s38584t100', 'ctlmatcha')
  ,@('s38584t100', 'ctlmatchb')
  ,@('s38584t100', 'ctlmatchc')
  ,@('s38584t100', 'ctlmatchd')
  ,@('s38584t100', 'ctlmatche')
  ,@('s38584t100', 'ctlmatchf')
  ,@('s38584t100', 'ctlxor')
)
Log ("=== rerun {0} ctl specs (abc:opt + abc:aig, budget 2500) ===" -f $specs.Count)
$i = 0
foreach ($s in $specs) {
  $i++
  $h = $s[0]; $inst = $s[1]
  & $py -X utf8 -u 'phase2\ys\sat_node_pairs_batch.py' `
      --host $h --inst $inst --pairs 'ys_abc:ys_opt,ys_abc:ys_aig' `
      --anchor all --budget 2500 --per-sig 20 --prove-mode simple `
      --batch 200 --timeout 300 --workers 6 --skip-covered --force 2>&1 |
    Out-File -FilePath (Join-Path $n4.FullName ("logs\fix_{0}_{1}.log" -f $h, $inst)) -Encoding UTF8
  Log ("  [fix {0}/{1}] {2}|{3} rc={4}" -f $i, $specs.Count, $h, $inst, $LASTEXITCODE)
  if ($LASTEXITCODE -ne 0) { Log '  WARN: non-zero rc -> continue (other specs still useful)' }
}

# ---------- 2) rebuild node features / index / tables ----------
Log '--- rebuild: INCIDENT (train) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' --incident 2>&1 |
  Select-String -Pattern 'coverage_any|\[fix\]|\[bad rows\]' |
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

'SAT_CTL_FIX_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== ctl-fix done ==='
