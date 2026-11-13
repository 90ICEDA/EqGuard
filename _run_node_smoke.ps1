# _run_node_smoke.ps1 -- SMALL-SAMPLE test of the 4 node-level P2 variants (NOT 100 ep)
#   0) wait for 'FULL BATCH DONE' (GPU must be idle for timing)
#   1) rebuild features / pairs with netmap
#   2) probe: 2 ep, all views  -> epoch time + peak VRAM
#   3) 4 smoke runs x 3 ep, 40 views/epoch (C_n / C_nn / D_n / E_n) -> check losses fire, no NaN
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4  = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\node_smoke.log'
$fb  = Join-Path $n4.FullName 'logs\full_batch.log'
$flag = Join-Path $env:TEMP 'node_smoke.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}

Log '=== node SMOKE start: waiting for sat_full_batch ==='
$deadline = Get-Date '18:00'
while ($true) {
  $done = $false
  if (Test-Path $fb) {
    $tail = Get-Content $fb -Tail 40 -ErrorAction SilentlyContinue
    if ($tail -match 'FULL BATCH DONE') { $done = $true }
  }
  if ($done) { Log 'sat_full_batch: FULL BATCH DONE detected'; break }
  if ((Get-Date) -gt $deadline) { Log 'timeout 18:00 -> proceed anyway'; break }
  Start-Sleep -Seconds 60
}

Log '--- rebuild node features (netmap) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
Log '--- rebuild node-pair index ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$base = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
          '--work-dir', $fold,
          '--fold-json', (Join-Path $fold 'views.json'),
          '--pt-dir', (Join-Path $fold 'data\processed'),
          '--config', (Join-Path $root '_devcfg\dual.yaml'),
          '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '2',
          '--amp', '--resume', '--train-mode', '4', '--label-mask', 'trust')

# ---------- probe: 2 ep, ALL views (timing / VRAM) ----------
Log '--- probe: 2 ep, view-policy=all (tag=node_probe2) ---'
& $gpy @base --view-policy all --epochs 2 --seed 42 --tag node_probe2 --extra-feats satrel_node 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'node_probe2.out') -Encoding UTF8
Log "    probe rc=$LASTEXITCODE"
$pr = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_fold_node_probe2\run_config.json'
if (Test-Path $pr) {
  $cfg = Get-Content $pr -Raw | ConvertFrom-Json
  Log ("    probe peak_vram_mb={0}" -f $cfg.peak_vram_mb)
}
$tl = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_fold_node_probe2\train_log.csv'
if (Test-Path $tl) {
  Get-Content $tl | Select-Object -Last 2 | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
}

# ---------- 4 smoke runs: 3 ep, 40 views/epoch ----------
foreach ($g in @(
    @{n='Cn';  extra=@()},
    @{n='Cnn'; extra=@('--no-cov-flag')},
    @{n='Dn';  extra=@('--eq-loss-node','0.1')},
    @{n='En';  extra=@('--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5')})) {
  $tag = "fghtl_$($g.n)Smoke4"
  Log ("--- [smoke] $($g.n) 3 ep / 40 views  tag=$tag")
  $ex = @('--view-policy','random','--view-budget','40','--epochs','3','--seed','42',
          '--tag',$tag,'--extra-feats','satrel_node') + $g.extra
  & $gpy @base @ex 2>&1 | Out-File -FilePath (Join-Path $env:TEMP "$tag.out") -Encoding UTF8
  Log ("    [smoke] $($g.n) rc=$LASTEXITCODE")
}

Log '--- summary of smoke runs ---'
foreach ($g in @('Cn','Cnn','Dn','En')) {
  $rd = Join-Path $root ("results\hosts_bt31_seed42mode4_allb1_fold_fghtl_{0}Smoke4" -f $g)
  $f  = Join-Path $rd 'train_log.csv'
  if (Test-Path $f) {
    $row = (Get-Content $f | Select-Object -Last 1)
    Log ("    {0}: {1}" -f $g, $row)
    $out = Join-Path $env:TEMP ("fghtl_{0}Smoke4.out" -f $g)
    if (Test-Path $out) {
      $hits = Select-String -Path $out -Pattern 'P2-node|EXTRA|NORM|WARN' | Select-Object -First 6
      foreach ($h in $hits) { Add-Content -Path $log -Value ("      " + $h.Line.Trim()) -Encoding UTF8 }
    }
  } else { Log ("    {0}: NO train_log" -f $g) }
}
'SMOKE_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== node SMOKE done ==='
