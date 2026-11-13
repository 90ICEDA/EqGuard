# _run_node_judge.ps1 -- node-level SAT JUDGMENT runs (seed 42) AFTER the SAT batch finishes
#   0) wait for 'FULL BATCH DONE' in full_batch.log (deadline 18:00; GPU must be exclusive)
#   1) rebuild node features / pair index with netmap (assign-alias + net->driver cell)
#   2) probe: 2 epochs (measure s/epoch + peak VRAM under exclusive GPU)
#   3) 4 runs x 100 ep: C_n / C_nn(no covered flag) / D_n(+L_eq) / E_n(+L_pair)
#   4) refresh fg_htl_ablation.csv
#   NOTE: ASCII-only paths (PowerShell 5.1 reads .ps1 as ANSI -> CJK literals break)
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$py  = Join-Path $root 'ginvenv\Scripts\python.exe'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$d15 = @(Get-ChildItem -Path (Join-Path $root '10.15') -Directory | Where-Object { $_.Name -like '06_*' })[0]
$n4  = @(Get-ChildItem -Path $d15.FullName -Directory | Where-Object { $_.Name -like 'N4_*' -and $_.Name -notlike '*_100ep*' })[0]
$log = Join-Path $n4.FullName 'logs\node_judge.log'
$fb  = Join-Path $n4.FullName 'logs\full_batch.log'
$flag = Join-Path $env:TEMP 'node_judge.done'
if (Test-Path $flag) { Remove-Item $flag -Force }

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $line -Encoding UTF8
  Write-Host $line
}
function Wait-Ram {
  while (((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB) -lt 6) {
    Log '    [wait] free RAM < 6GB -> sleep 30s'; Start-Sleep -Seconds 30
  }
}

Log '=== node judge start: waiting for sat_full_batch ==='
$deadline = Get-Date '18:00'
while ($true) {
  $done = $false
  if (Test-Path $fb) {
    $tail = Get-Content $fb -Tail 40 -ErrorAction SilentlyContinue
    if ($tail -match 'FULL BATCH DONE') { $done = $true }
  }
  if ($done) { Log 'sat_full_batch: FULL BATCH DONE detected'; break }
  if ((Get-Date) -gt $deadline) { Log 'timeout 18:00 -> proceed anyway (check GPU contention!)'; break }
  Start-Sleep -Seconds 60
}

Log '--- rebuild node features (netmap: direct -> alias -> driver cell) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_feats_sat.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
Log '--- rebuild node-pair index (train-only) ---'
& $py -X utf8 -u 'phase2\ys\satrel_node_pairs_npz.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
Log '--- refresh fg_htl_ablation.csv ---'
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }

$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$base = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
          '--work-dir', $fold,
          '--fold-json', (Join-Path $fold 'views.json'),
          '--pt-dir', (Join-Path $fold 'data\processed'),
          '--config', (Join-Path $root '_devcfg\dual.yaml'),
          '--fold-mode', 'fold', '--steps-per-epoch', '1', '--val-every', '5',
          '--view-policy', 'all', '--amp', '--resume',
          '--train-mode', '4', '--label-mask', 'trust')

# ---------- probe (2 epochs) ----------
Wait-Ram
Log '--- probe: 2 ep, mode4 + satrel_node (tag=node_probe) ---'
& $gpy @base --epochs 2 --seed 42 --tag node_probe --extra-feats satrel_node 2>&1 |
  Out-File -FilePath (Join-Path $env:TEMP 'node_probe.out') -Encoding UTF8
Log "    probe rc=$LASTEXITCODE"
$pr = Join-Path $root 'results\hosts_bt31_seed42mode4_allb1_fold_node_probe\run_config.json'
if (Test-Path $pr) {
  $cfg = Get-Content $pr -Raw | ConvertFrom-Json
  Log ("    probe peak_vram_mb={0}" -f $cfg.peak_vram_mb)
}

# ---------- 4 judgment runs ----------
foreach ($g in @(
    @{n='Cn';  extra=@()},
    @{n='Cnn'; extra=@('--no-cov-flag')},
    @{n='Dn';  extra=@('--eq-loss-node','0.1')},
    @{n='En';  extra=@('--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5')})) {
  $tag = "fghtl_$($g.n)s42"
  Wait-Ram
  Log ("--- [judge] $($g.n) seed=42 tag=$tag")
  $ex = @('--epochs','100','--seed','42','--tag',$tag,'--extra-feats','satrel_node') + $g.extra
  & $gpy @base @ex 2>&1 | Out-File -FilePath (Join-Path $env:TEMP "$tag.out") -Encoding UTF8
  Log ("    [judge] $($g.n) rc=$LASTEXITCODE")
}

Log '--- refresh fg_htl_ablation.csv (after judge runs) ---'
& $py -X utf8 -u 'phase2\ys\make_fghtl_ablation.py' 2>&1 | Select-Object -Last 1 |
  ForEach-Object { Add-Content -Path $log -Value $_ -Encoding UTF8 }
'JUDGE_DONE ' + (Get-Date -Format s) | Out-File -FilePath $flag -Encoding UTF8
Log '=== node judge done ==='
