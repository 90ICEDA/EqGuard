# _run_p3_56.ps1 -- 56-dim (39 base + 5 cone5 + 12 SAT) LOCO then LRO, seed42.
# Run only after stopping the old Cv2 LOCO queue.
$root = $PSScriptRoot
Set-Location $root
$env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'
$env:GNN_GRAD_CKPT = '1'
$gpy = Join-Path $root 'ginvenv_gpu\Scripts\python.exe'
$fold = Join-Path $root 'generate_trans\folds\hosts_bt31'
$log = Join-Path $root 'logs\c_p3_56.log'
$done = Join-Path $env:TEMP 'p3_56.done'
if (Test-Path $done) { Remove-Item $done -Force }

function Log($m) {
  $l = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $m
  Add-Content -Path $log -Value $l -Encoding UTF8
  Write-Host $l
}

$common = @(
  '-X','utf8','-u', (Join-Path $root 'train_test2.3.py'),
  '--work-dir', $fold,
  '--fold-json', (Join-Path $fold 'views.json'),
  '--pt-dir', (Join-Path $fold 'data\processed'),
  '--config', (Join-Path $root '_devcfg\dual.yaml'),
  '--steps-per-epoch','1','--val-every','10','--view-policy','all',
  '--amp','--resume','--epochs','100',
  '--train-mode','4','--label-mask','trust','--save-ckpt',
  '--circuits','s38584t100','--seed','42',
  '--extra-feats','satrel_node',
  '--extra-node-file','cone5_sat_p0clean2.npy',
  '--extra-dense-prefix','5'
)

function Run-One([string]$tag, [string]$fm) {
  Log ("--- {0} ({1})" -f $tag, $fm)
  $t0 = Get-Date
  & $gpy @common --fold-mode $fm --tag $tag 2>&1 |
    Out-File -FilePath (Join-Path $env:TEMP ("cp3_56_{0}.out" -f $tag)) -Encoding UTF8
  Log ("    rc={0} elapsed={1}min" -f $LASTEXITCODE, [int]((Get-Date) - $t0).TotalMinutes)
}

Log '=== 56-dim seed42: LOCO then LRO ==='
Run-One 'fghtl_P3locoC5S42' 'loco'
Run-One 'fghtl_P3lroC5S42' 'lro'
'P3_56_DONE ' + (Get-Date -Format s) | Out-File -FilePath $done -Encoding UTF8
Log '=== 56-dim done ==='
