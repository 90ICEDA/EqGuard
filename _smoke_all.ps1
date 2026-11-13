# _smoke_all.ps1 -- sequential 2-epoch validation of ALL node-level training variants
#   C_n (no extra loss) -> D_n (L_eq) -> E_n (L_eq+L_pair) -> P3 LRO (L_eq+L_pair)
#   MUST run with NO SAT writer (GPU+SAT concurrency causes OOM on the 8 GB card).
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$common = @('-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
            '--work-dir', $fold,
            '--fold-json', (Join-Path $fold 'views.json'),
            '--pt-dir', (Join-Path $fold 'data\processed'),
            '--config', (Join-Path $root '_devcfg\dual.yaml'),
            '--steps-per-epoch', '1', '--val-every', '5',
            '--view-policy', 'all', '--amp', '--resume',
            '--train-mode', '4', '--label-mask', 'trust', '--save-ckpt')

function Wait-GpuFree {
  for ($i = 0; $i -lt 30; $i++) {
    $free = (& nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -as [int]
    if ($free -gt 5000) { return $true }
    Start-Sleep -Seconds 5
  }
  return $false
}

function Run-Smoke([string]$name, [string[]]$argv) {
  if (-not (Wait-GpuFree)) { Write-Host "[ABORT] GPU not free before $name"; exit 1 }
  Write-Host ("=== {0} ===" -f $name)
  & $gpy @argv 2>&1 | Out-File -FilePath (Join-Path $env:TEMP ("smoke_{0}.out" -f $name)) -Encoding UTF8
  $rc = $LASTEXITCODE
  Write-Host ("{0} rc={1}" -f $name, $rc)
  if ($rc -ne 0) { exit 1 }
}

Run-Smoke 'C2' ($common + @('--fold-mode','fold','--epochs','2','--seed','42','--tag','gpu_probeC2',
                            '--extra-feats','satrel_node'))
Run-Smoke 'N2' ($common + @('--fold-mode','fold','--epochs','2','--seed','42','--tag','gpu_probeN2',
                            '--extra-feats','satrel_node','--no-cov-flag'))
Run-Smoke 'P2' ($common + @('--fold-mode','fold','--epochs','2','--seed','42','--tag','gpu_probeP2',
                            '--extra-feats','satrel_node','--extra-node-file','satrel_node_feats_sat_perm_incident.npy'))
Run-Smoke 'V2' ($common + @('--fold-mode','fold','--epochs','2','--seed','42','--tag','gpu_probeV2',
                            '--extra-feats','satrel_node','--extra-node-file','satrel_node_feats_sat_driver.npy'))
Run-Smoke 'D2' ($common + @('--fold-mode','fold','--epochs','2','--seed','42','--tag','gpu_probeD2',
                            '--extra-feats','satrel_node','--eq-loss-node','0.1','--node-pair-cap','2048'))
Run-Smoke 'E2' ($common + @('--fold-mode','fold','--epochs','2','--seed','42','--tag','gpu_probeE2',
                            '--extra-feats','satrel_node','--eq-loss-node','0.1',
                            '--pair-loss-node','0.1','--pair-margin','0.5','--node-pair-cap','2048'))
Run-Smoke 'P3b' ($common + @('--fold-mode','lro','--circuits','s38584t100','--epochs','2','--seed','42',
                             '--tag','gpu_probeP3b','--extra-feats','satrel_node',
                             '--eq-loss-node','0.1','--pair-loss-node','0.1','--pair-margin','0.5',
                             '--node-pair-cap','2048'))
Write-Host 'ALL_SMOKES_OK'
exit 0

$env:GNN_GRAD_CKPT = '1'

